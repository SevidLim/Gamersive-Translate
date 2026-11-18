"""目標語言下拉選單：初始值取自 config，選了送出自己那一頁的鍵。"""

import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest
from PySide6.QtWidgets import QApplication

from gt.ui import target_box


@pytest.fixture(scope="module")
def app():
    return QApplication.instance() or QApplication([])


def test_boxes_write_their_own_key(app):
    cfg = {"target_lang": "zh-TW", "ocr_target_lang": "zh-TW"}
    calls = []
    text_box = target_box(cfg, "target_lang", lambda k, v: calls.append((k, v)))
    ocr_box = target_box(cfg, "ocr_target_lang", lambda k, v: calls.append((k, v)))
    ocr_box.setCurrentIndex(ocr_box.findData("en-US"))
    assert calls == [("ocr_target_lang", "en-US")]
    assert text_box.currentData() == "zh-TW"
    text_box.setCurrentIndex(text_box.findData("en-US"))
    assert calls[-1] == ("target_lang", "en-US")


def test_box_starts_from_config(app):
    box = target_box({"target_lang": "en-US"}, "target_lang", lambda k, v: None)
    assert box.currentText() == "英文（美國）"
