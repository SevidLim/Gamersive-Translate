"""OCR 引擎共同介面：以固定遊戲截圖（2560x1440，英文任務文字與俄文標語）驗證辨識出的文字區塊；
備用切換與 llama-server 啟動關閉以假引擎、假行程驗證。"""

from pathlib import Path

import numpy as np
import pytest

from gt import ocr
from gt.ocr import LLAMA_SERVER, FallbackEngine, RapidOCREngine, SuryaEngine

FIXTURE = Path(__file__).with_name("fixtures") / "game-en-ru.png"


@pytest.fixture(autouse=True)
def _no_debuglog(monkeypatch):
    monkeypatch.setattr(ocr, "log", lambda msg: None)


def _read_fixture():
    cv2 = pytest.importorskip("cv2")
    return cv2.imread(str(FIXTURE))


class _Engine:
    def __init__(self, name, result=None, error=None):
        self.name, self.result, self.error, self.calls = name, result, error, 0

    def recognize(self, image):
        self.calls += 1
        if self.error:
            raise self.error
        return self.result


def test_fallback_switches_to_backup_and_stays_there():
    main, backup = _Engine("Surya", error=RuntimeError("llama-server 啟動逾時")), _Engine("備用", ["a"])
    switches = []
    engine = FallbackEngine([main, backup], lambda name, reason: switches.append((name, reason)))
    assert engine.recognize("img") == ["a"]
    assert switches == [("備用", "llama-server 啟動逾時")]
    assert engine.recognize("img") == ["a"]
    assert main.calls == 1 and backup.calls == 2


def test_fallback_raises_when_all_engines_fail():
    engine = FallbackEngine([_Engine("a", error=RuntimeError("x")), _Engine("b", error=RuntimeError("y"))])
    with pytest.raises(RuntimeError, match="y"):
        engine.recognize("img")


class _Proc:
    pid, returncode = 1234, None

    def __init__(self):
        self.terminated = self.waited = False

    def poll(self):
        return self.returncode

    def terminate(self):
        self.terminated = True

    def wait(self, timeout=None):
        self.waited, self.returncode = True, 0


def _surya(proc, probe, **kw):
    return SuryaEngine(popen=lambda *a, **k: proc, probe=probe, model_files=lambda: ("m", "mm"), **kw)


def test_surya_closes_llama_server_after_recognize(monkeypatch):
    proc = _Proc()
    engine = _surya(proc, lambda url: True)
    monkeypatch.setattr(engine, "_run", lambda image, port: ["x"])
    assert engine.recognize(np.zeros((1, 1, 3), np.uint8)) == ["x"]
    assert proc.terminated and proc.waited


def test_surya_startup_timeout_raises_and_closes_llama_server():
    proc = _Proc()
    engine = _surya(proc, lambda url: False, startup_timeout=0)
    with pytest.raises(RuntimeError, match="llama-server 啟動逾時"):
        engine.recognize(np.zeros((1, 1, 3), np.uint8))
    assert proc.terminated and proc.waited


def test_rapidocr_recognizes_english_lines_of_game_screenshot():
    pytest.importorskip("rapidocr")
    blocks = RapidOCREngine().recognize(_read_fixture())
    for line in ["Read the assignment order on", "the desk (0/1)", "Tear open a sack (0/1)",
                 "Take a potato to the workbench and", "start peeling (0/1)", "Journal",
                 "Read directive", "[F] Focus"]:
        assert line in blocks


def test_surya_recognizes_english_and_russian_of_game_screenshot():
    pytest.importorskip("surya")
    if not LLAMA_SERVER.exists():
        pytest.skip("llama-server.exe 不存在")
    blocks = SuryaEngine().recognize(_read_fixture())
    for text in ["КАРТОФЕЛИНА", "Read directive", "Journal"]:
        assert any(text in b for b in blocks)


def test_surya_figure_block_is_recognized_again_in_block_mode():
    pytest.importorskip("surya")
    from types import SimpleNamespace as NS
    from gt.ocr import surya_blocks
    calls = []

    def pred(images, layouts=None, full_page=None):
        calls.append(layouts)
        if layouts is None:                              # 整頁：Figure 區塊 html 為空
            return [NS(image_bbox=[0, 0, 10, 10], blocks=[
                NS(label="Text", skipped=False, html="<p>Journal</p>", polygon=[[0, 0], [1, 0], [1, 1], [0, 1]]),
                NS(label="Figure", skipped=True, html="", polygon=[[0, 2], [9, 2], [9, 9], [0, 9]])])]
        assert [b.label for b in layouts[0].bboxes] == ["Text"]
        assert full_page is False
        return [NS(blocks=[NS(html="<p>Read  directive</p>")])]

    assert surya_blocks(pred, object()) == ["Journal", "Read directive"]
    assert len(calls) == 2
