"""loading 按鈕：loading → 成功顯示 ✓ 再換回、失敗直接換回；loading 與 ✓ 期間停用。"""

import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication

from gt.ui import COLLAPSE_MS, DONE_MS, EXPAND_MS, SHAKE_MS, LoadingButton


@pytest.fixture(scope="module")
def app():
    return QApplication.instance() or QApplication([])


def make(app, animated, morph=True, celebrate=False):
    b = LoadingButton("截圖", morph=morph, celebrate=celebrate)
    b.animated = animated
    b.resize(80, 32)
    b.show()
    return b


def test_success_shows_check_then_idle(app):
    b = make(app, animated=False)
    b.start_loading()
    assert b.state == "loading" and not b.isEnabled()
    b.finish(True)
    assert b.state == "done" and not b.isEnabled()
    QTest.qWait(DONE_MS + 100)
    assert b.state == "idle" and b.isEnabled()


def test_failure_returns_to_idle(app):
    b = make(app, animated=False)
    b.start_loading()
    b.finish(False)
    assert b.state == "idle" and b.isEnabled()


def test_external_disable_applies_after_loading(app):
    b = make(app, animated=False)
    b.start_loading()
    b.setEnabled(False)
    b.finish(False)
    assert b.state == "idle" and not b.isEnabled()
    b.setEnabled(True)
    assert b.isEnabled()


def test_setenabled_during_loading_keeps_disabled(app):
    b = make(app, animated=False)
    b.start_loading()
    b.setEnabled(True)
    assert not b.isEnabled()


def test_finish_when_idle_does_nothing(app):
    b = make(app, animated=False)
    b.finish(True)
    assert b.state == "idle"


def test_animation_off_spinner_still(app):
    b = make(app, animated=False)
    b.start_loading()
    QTest.qWait(100)
    assert b._angle == 0.0 and b._shape == 1.0


def test_animated_morph_and_spin(app):
    b = make(app, animated=True)
    b.start_loading()
    QTest.qWait(COLLAPSE_MS + 150)
    assert b._shape == 1.0 and b._spin.state() == b._spin.State.Running
    b.finish(True)
    assert b._spin.state() == b._spin.State.Stopped
    QTest.qWait(EXPAND_MS + 150)
    assert b._shape == 0.0 and b.state == "done"


def test_icon_button_keeps_shape(app):
    b = make(app, animated=True, morph=False)
    b.start_loading()
    assert b._shape == 0.0 and b._spin.state() == b._spin.State.Running
    b.finish(True)
    assert b.state == "done"


def test_listen_check_then_stop_icon(app):
    b = make(app, animated=True, morph=False, celebrate=True)
    b.start_loading()
    b.finish(True)
    assert b.state == "done" and b.isEnabled()          # ✓ 期間可按（停止）
    QTest.qWait(DONE_MS + 50)
    assert b.state == "playing" and b.isEnabled()       # ⏹


def test_listen_ended_while_playing_returns_with_animation(app):
    b = make(app, animated=True, morph=False, celebrate=True)
    b.start_loading()
    b.finish(True)
    QTest.qWait(DONE_MS + 50)
    b.ended()
    assert b.state == "returning" and b._from == "stop" and b._phase == "shrink"
    QTest.qWait(COLLAPSE_MS + EXPAND_MS + SHAKE_MS + 300)
    assert b.state == "idle" and b.isEnabled()


def test_listen_ended_during_check_shrinks_check(app):
    b = make(app, animated=True, morph=False, celebrate=True)
    b.start_loading()
    b.finish(True)
    b.ended()
    assert b.state == "returning" and b._from == "check"


def test_listen_ended_animation_off_returns_directly(app):
    b = make(app, animated=False, morph=False, celebrate=True)
    b.start_loading()
    b.finish(True)
    QTest.qWait(DONE_MS + 100)
    assert b.state == "playing"
    b.ended()
    assert b.state == "idle" and b.isEnabled()


def test_ended_when_loading_does_nothing(app):
    b = make(app, animated=False, morph=False, celebrate=True)
    b.start_loading()
    b.ended()
    assert b.state == "loading"


def test_loading_interrupts_return(app):
    b = make(app, animated=True, morph=False, celebrate=True)
    b.start_loading()
    b.finish(True)
    QTest.qWait(DONE_MS + 50)
    b.ended()
    b.start_loading()
    assert b.state == "loading" and b._phase is None
