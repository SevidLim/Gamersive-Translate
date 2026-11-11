"""獨佔全螢幕判斷：查詢結果為 QUNS_RUNNING_D3D_FULL_SCREEN (3) 才算偵測到。"""

import pytest

from gt.platform_win import exclusive_fullscreen


@pytest.mark.parametrize("state, detected", [(3, True), (0, False), (1, False), (2, False), (4, False), (5, False)])
def test_exclusive_fullscreen(state, detected):
    assert exclusive_fullscreen(lambda: state) is detected
