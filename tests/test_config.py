"""螢幕選擇：記下的螢幕不存在時改用主螢幕。"""

from gt.config import pick_screen


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
