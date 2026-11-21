"""系統匣：右鍵選單只有「結束」，按下呼叫結束函式。"""

import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest
from PySide6.QtWidgets import QApplication

from gt import config
from gt.ui import make_tray


@pytest.fixture(scope="module")
def app():
    return QApplication.instance() or QApplication([])


def test_tray_menu_has_quit_only(app):
    calls = []
    tray = make_tray(config.APP_ROOT / "assets" / "icon.png", lambda: calls.append("quit"))
    actions = tray.contextMenu().actions()
    assert [a.text() for a in actions] == ["結束"]
    actions[0].trigger()
    assert calls == ["quit"]


def test_icon_file_exists():
    assert (config.APP_ROOT / "assets" / "icon.png").exists()
    assert (config.APP_ROOT / "assets" / "icon.ico").exists()
