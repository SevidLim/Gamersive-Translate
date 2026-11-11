"""螢幕選擇：記下的螢幕不存在時改用主螢幕。"""

from gt import config
from gt.config import pick_screen, screen_after_removal


class FakeScreen:
    def __init__(self, name):
        self._name = name

    def name(self):
        return self._name


def test_pick_saved_screen():
    a, b = FakeScreen("A"), FakeScreen("B")
    assert pick_screen([a, b], "B", a) is b


def test_missing_saved_screen_falls_back_to_primary():
    a, b = FakeScreen("A"), FakeScreen("B")
    assert pick_screen([a, b], "C", a) is a
    assert pick_screen([a, b], "", b) is b


def test_removed_current_screen_falls_back_to_primary():
    a, b = FakeScreen("A"), FakeScreen("B")
    assert screen_after_removal(b, b, a) is a


def test_removing_other_screen_keeps_current():
    a, b, c = FakeScreen("A"), FakeScreen("B"), FakeScreen("C")
    assert screen_after_removal(b, c, a) is b


def test_font_defaults(tmp_path):
    cfg = config.load(tmp_path / "config.json")
    assert cfg["font_family"] == ""                 # 空字串＝QApplication 目前預設字型
    assert cfg["font_size"] == 14
