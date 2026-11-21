"""面板位置：視窗貼螢幕左緣或右緣的 x；設定頁開關的圓鈕位置。"""

import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest
from PySide6.QtCore import QRect, Qt
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication

from gt.ui import SideSwitch, edge_x


@pytest.fixture(scope="module")
def app():
    return QApplication.instance() or QApplication([])


def test_edge_x_right_and_left():
    g = QRect(2560, 0, 1920, 1080)
    assert edge_x(g, "right", 420) == 2560 + 1920 - 420
    assert edge_x(g, "left", 420) == 2560


def test_switch_click_requests_other_side(app):
    s = SideSwitch("right")
    s.animated = False
    calls = []
    s.requested.connect(calls.append)
    QTest.mouseClick(s, Qt.LeftButton)
    assert calls == ["left"] and s.side == "left" and s._pos == 0.0
    s.set_side("right")                              # 取消：圓鈕回右
    assert s.side == "right" and s._pos == 1.0


def test_overlay_locks_widgets_below(app):
    from PySide6.QtWidgets import QPushButton, QWidget
    from gt.ui import ConfirmOverlay
    host = QWidget()
    host.resize(420, 640)
    below = QPushButton("翻譯", host)
    overlay = ConfirmOverlay(host)
    overlay.animated = False
    locked = []
    lock = lambda on: (below.setEnabled(not on), locked.append(on))
    overlay.rejected.connect(lambda: lock(False))
    host.show()
    lock(True)
    overlay.ask("切換到左側？")
    assert overlay.isVisible() and not below.isEnabled()
    overlay.cancel_btn.click()
    assert not overlay.isVisible() and below.isEnabled()


def test_overlay_enter_accepts_esc_rejects(app):
    from PySide6.QtWidgets import QWidget
    from gt.ui import ConfirmOverlay
    host = QWidget()
    host.resize(420, 640)
    overlay = ConfirmOverlay(host)
    overlay.animated = False
    got = []
    overlay.accepted.connect(lambda: got.append("ok"))
    overlay.rejected.connect(lambda: got.append("cancel"))
    host.show()
    overlay.ask("切換到左側？")
    QTest.keyClick(overlay, Qt.Key_Escape)
    assert got == ["cancel"] and not overlay.is_open()
    overlay.ask("切換到左側？")
    QTest.keyClick(overlay, Qt.Key_Return)
    assert got == ["cancel", "ok"] and not overlay.is_open()
