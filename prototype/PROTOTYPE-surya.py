"""PROTOTYPE（用完即丟）
問題：Surya 不指定語言，能否在 CPU 上正確辨識同一張截圖（英文＋俄文），耗時與記憶體峰值多少？
用法（在 .venv-surya 裡）：python PROTOTYPE-surya.py
llama-server 路徑由環境變數 LLAMA_CPP_BINARY 指定（見下方預設）。
"""
import os
import re
import time
from pathlib import Path

HERE = Path(__file__).parent
# 用法：python PROTOTYPE-surya.py [llama 資料夾名稱，預設 llama.cpp；GPU 版用 llama.cpp-cuda]
import sys  # noqa: E402
LLAMA_DIR = sys.argv[1] if len(sys.argv) > 1 else "llama.cpp"
os.environ.setdefault("LLAMA_CPP_BINARY", str(HERE / LLAMA_DIR / "llama-server.exe"))
os.environ.setdefault("SURYA_INFERENCE_BACKEND", "llamacpp")

from PIL import Image  # noqa: E402
from surya.inference import SuryaInferenceManager  # noqa: E402
from surya.recognition import RecognitionPredictor  # noqa: E402

from importlib import import_module  # noqa: E402
mw = import_module("PROTOTYPE-memwatch")

IMG = HERE / "PROTOTYPE-shot-000539.png"


def vram_mb():
    """整張顯卡目前已用的 VRAM（MB），用 nvidia-smi 查；查不到回傳 None。"""
    import subprocess
    try:
        out = subprocess.run(["nvidia-smi", "--query-gpu=memory.used", "--format=csv,noheader,nounits"],
                             capture_output=True, text=True, timeout=5).stdout
        return int(out.strip().splitlines()[0])
    except Exception:
        return None


def main():
    img = Image.open(IMG).convert("RGB")
    print(f"[讀取截圖] {IMG.name}  {img.size[0]}x{img.size[1]}  LLAMA_CPP_BINARY={os.environ['LLAMA_CPP_BINARY']}")
    print(f"[開始前 VRAM 已用] {vram_mb()}MB")
    with mw.MemWatch() as w:
        t = time.perf_counter()
        manager = SuryaInferenceManager()
        pred = RecognitionPredictor(manager)
        print(f"[建立] {time.perf_counter() - t:.2f}s")
        res = None
        for r in range(1, 4):
            t = time.perf_counter()
            res = pred([img])
            print(f"[辨識 第{r}次] {time.perf_counter() - t:.2f}s  目前峰值 {mw.mb(w.peak)}  VRAM 已用 {vram_mb()}MB")
        print(f"[記憶體峰值（含 llama-server 子程序）] {mw.mb(w.peak)}")
        print("\n===== 辨識結果 =====")
        for b in res[0].blocks:
            text = re.sub(r"<[^>]+>", " ", b.html)
            text = re.sub(r"\s+", " ", text).strip()
            print(f"[{b.label}] {text}")
        manager.stop()


if __name__ == "__main__":
    main()
