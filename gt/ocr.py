"""OCR 引擎。

共同介面：recognize(圖片) -> 文字區塊清單（list[str]），依閱讀順序排列。
圖片為 BGR 的 numpy 陣列（dxcam、cv2.imread 的格式）。
"""

import os
import re
import socket
import subprocess
import time
import urllib.request
from pathlib import Path

from gt import config
from gt.debuglog import log

LLAMA_SERVER = Path(__file__).resolve().parents[1] / "llama.cpp-cuda" / "llama-server.exe"
SURYA_MODEL = "datalab-to/surya-ocr-2.5"         # surya 檢查 /v1/models 的 model id，由 --alias 提供
STARTUP_TIMEOUT = 30                             # 等 llama-server /health 回 200 的上限秒數
os.environ["HF_HUB_OFFLINE"] = "1"                 # 模型檔已在本機快取，不向 Hugging Face Hub 送請求


def _free_port():
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


def _health_ok(url):
    try:
        with urllib.request.urlopen(url, timeout=1) as r:
            return r.status == 200
    except Exception:
        return False                             # 未就緒（連不上或 503 載入中）


def _model_files():
    from huggingface_hub import hf_hub_download
    repo = "datalab-to/surya-ocr-2.5-gguf"
    return (hf_hub_download(repo_id=repo, filename="surya-2.5.gguf"),
            hf_hub_download(repo_id=repo, filename="surya-2.5-mmproj.gguf"))


def _clean(html):
    return re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", html)).strip()


def surya_blocks(pred, img):
    """整頁辨識；surya 對 Figure、Image、Diagram 區塊不輸出文字（html 為空），
    這些區塊改以 Text 標籤用 surya 區塊模式再辨識一次，結果依原閱讀順序放回。"""
    from surya.layout.schema import LayoutBox, LayoutResult
    page = pred([img])[0]
    redo = [b for b in page.blocks if b.skipped and b.label != "Blank-Page"]
    if redo:
        layout = LayoutResult(image_bbox=page.image_bbox, bboxes=[
            LayoutBox(polygon=b.polygon, label="Text", raw_label="Text", position=i, count=4000)
            for i, b in enumerate(redo)])
        again = pred([img], [layout], full_page=False)[0].blocks
        html = {id(b): a.html for b, a in zip(redo, again)}
    else:
        html = {}
    blocks = []
    for b in page.blocks:
        text = _clean(html.get(id(b), b.html))
        if text:
            blocks.append(text)
    return blocks


class SuryaEngine:
    """Surya：每次辨識啟動 llama-server（GPU），辨識完關閉；一個區塊一個文字區塊。
    不走 surya 自己的啟動與清理（其 Windows 清理會送 Ctrl+C 並停住）。"""

    name = "Surya"

    def __init__(self, binary=LLAMA_SERVER, popen=subprocess.Popen, probe=_health_ok,
                 model_files=_model_files, startup_timeout=STARTUP_TIMEOUT):
        self._binary, self._popen, self._probe = binary, popen, probe
        self._model_files, self._timeout = model_files, startup_timeout
        self._proc = None
        self._log_fp = None

    def recognize(self, image):
        port = _free_port()
        model, mmproj = self._model_files()
        path = config.config_path().with_name("llama-server.log")
        path.parent.mkdir(parents=True, exist_ok=True)
        self._log_fp = open(path, "ab")              # llama-server 自己的輸出，追查啟動失敗用
        self._proc = self._popen(
            [str(self._binary), "-m", model, "--mmproj", mmproj, "-ngl", "99", "--host", "127.0.0.1",
             "--port", str(port), "--parallel", "8", "--ctx-size", str(8 * 12288),
             "--alias", SURYA_MODEL, "--jinja", "--special"],
            stdout=self._log_fp, stderr=subprocess.STDOUT,
            creationflags=getattr(subprocess, "CREATE_NEW_PROCESS_GROUP", 0))
        log(f"llama-server 啟動 pid={self._proc.pid} port={port}")
        try:
            self._wait_ready(port)
            return self._run(image, port)
        finally:
            self.close()

    def _wait_ready(self, port):
        deadline = time.monotonic() + self._timeout
        while not self._probe(f"http://127.0.0.1:{port}/health"):
            if self._proc.poll() is not None:
                raise RuntimeError(f"llama-server 啟動失敗（退出碼 {self._proc.returncode}）")
            if time.monotonic() >= deadline:
                raise RuntimeError("llama-server 啟動逾時")
            time.sleep(0.2)

    def _run(self, image, port):
        from PIL import Image
        from surya.settings import settings
        from surya.inference import SuryaInferenceManager
        from surya.recognition import RecognitionPredictor
        # settings 於執行期讀取；設 URL 時 surya 只連線不自己啟動。URL 在 manager 建立後固定，故每次重建
        settings.SURYA_INFERENCE_URL = f"http://127.0.0.1:{port}/v1"
        pred = RecognitionPredictor(SuryaInferenceManager(method="llamacpp"))
        return surya_blocks(pred, Image.fromarray(image[:, :, ::-1].copy()))    # BGR → RGB

    def close(self):
        """關閉 llama-server 並確認結束（辨識完成、失敗或程式結束時）。"""
        proc, self._proc = self._proc, None
        if proc is None:
            return
        proc.terminate()
        try:
            proc.wait(timeout=5)
        except subprocess.TimeoutExpired:
            proc.kill()
            proc.wait()
        log(f"llama-server 結束 pid={proc.pid} 退出碼={proc.returncode}")
        if self._log_fp is not None:
            self._log_fp.close()
            self._log_fp = None


class RapidOCREngine:
    """RapidOCR 3.10.0（ONNX Runtime CPU）；一行一個文字區塊，照 RapidOCR 輸出順序。
    預設參數為 PP-OCRv6 small；v5=True 為 PP-OCRv5 mobile（預設模型）。"""

    def __init__(self, v5=False):
        self._v5 = v5
        self.name = "RapidOCR PP-OCRv5 mobile" if v5 else "RapidOCR PP-OCRv6 small"
        self._engine = None                      # 第一次辨識時才建立，啟動不等模型載入

    def recognize(self, image):
        if self._engine is None:
            from rapidocr import ModelType, OCRVersion, RapidOCR
            params = None
            if self._v5:
                params = {"Det.ocr_version": OCRVersion.PPOCRV5, "Det.model_type": ModelType.MOBILE,
                          "Rec.ocr_version": OCRVersion.PPOCRV5, "Rec.model_type": ModelType.MOBILE}
            self._engine = RapidOCR(params=params)
        return list(self._engine(image).txts or ())


class FallbackEngine:
    """依序使用 engines：目前引擎失敗就改用下一個並對同一張圖重試，之後留在新引擎。
    切換時呼叫 on_switch(新引擎名, 原因)；最後一個也失敗則丟出其例外。"""

    def __init__(self, engines, on_switch=lambda name, reason: None):
        self._engines = list(engines)
        self._on_switch = on_switch

    def recognize(self, image):
        while True:
            try:
                return self._engines[0].recognize(image)
            except Exception as e:
                if len(self._engines) == 1:
                    raise
                self._engines.pop(0)
                self._on_switch(self._engines[0].name, str(e) or type(e).__name__)
