"""OCR 引擎共同介面：以固定遊戲截圖（2560x1440，英文任務文字與俄文標語）驗證辨識出的文字區塊。"""

from pathlib import Path

import pytest

pytest.importorskip("rapidocr")

import cv2

from gt.ocr import RapidOCREngine

FIXTURE = Path(__file__).with_name("fixtures") / "game-en-ru.png"


def test_rapidocr_recognizes_english_lines_of_game_screenshot():
    blocks = RapidOCREngine().recognize(cv2.imread(str(FIXTURE)))
    for line in ["Read the assignment order on", "the desk (0/1)", "Tear open a sack (0/1)",
                 "Take a potato to the workbench and", "start peeling (0/1)", "Journal",
                 "Read directive", "[F] Focus"]:
        assert line in blocks
