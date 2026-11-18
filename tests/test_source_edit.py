"""原文輸入框的上下鍵：第一行按上移到開頭，最後一行按下移到結尾。"""

import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest
from PySide6.QtCore import QEvent, Qt
from PySide6.QtGui import QKeyEvent
from PySide6.QtWidgets import QApplication

from gt.ui import SourceEdit


@pytest.fixture(scope="module")
def app():
    return QApplication.instance() or QApplication([])


def press(edit, key):
    edit.keyPressEvent(QKeyEvent(QEvent.KeyPress, key, Qt.NoModifier))


def make(app, text, pos):
    edit = SourceEdit()
    edit.resize(400, 300)
    edit.setPlainText(text)
    edit.show()
    app.processEvents()
    c = edit.textCursor()
    c.setPosition(pos)
    edit.setTextCursor(c)
    return edit


def test_up_on_first_line_moves_to_start(app):
    edit = make(app, "abc\ndef", 2)
    press(edit, Qt.Key_Up)
    assert edit.textCursor().position() == 0


def test_down_on_last_line_moves_to_end(app):
    edit = make(app, "abc\ndef", 5)
    press(edit, Qt.Key_Down)
    assert edit.textCursor().position() == 7


def test_single_line_up_and_down(app):
    edit = make(app, "hello", 2)
    press(edit, Qt.Key_Down)
    assert edit.textCursor().position() == 5
    press(edit, Qt.Key_Up)
    assert edit.textCursor().position() == 0


def test_middle_line_keeps_default_move(app):
    edit = make(app, "abc\ndef\nghi", 5)
    press(edit, Qt.Key_Up)
    assert edit.textCursor().position() == 1
    press(edit, Qt.Key_Down)
    press(edit, Qt.Key_Down)
    assert edit.textCursor().position() == 9
