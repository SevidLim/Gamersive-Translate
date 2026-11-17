"""拼音：以 uroman 把原文轉成拉丁字母；與原文相同時回傳空字串。"""

import pytest

pytest.importorskip("uroman")

from gt.romanize import romanize


def test_romanize_non_latin_text():
    assert romanize("Игорь Стравинский") == "Igor Stravinsky"


def test_romanize_returns_empty_when_same_as_source():
    assert romanize("Hello, world\nline two") == ""
