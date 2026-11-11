"""截圖區域換算：各種螢幕尺寸與區域組合的裁切矩形 (x1, y1, x2, y2)。"""

import pytest

from gt import capture
from gt.capture import crop_box, scale_box


@pytest.mark.parametrize("w, h, region, cells, box", [
    (2560, 1440, "full", set(), (0, 0, 2560, 1440)),
    (2560, 1440, "top", set(), (0, 0, 2560, 720)),
    (2560, 1440, "bottom", set(), (0, 720, 2560, 1440)),
    (2560, 1440, "full", {1}, (0, 0, 853, 480)),
    (2560, 1440, "full", {5}, (853, 480, 1706, 960)),
    (2560, 1440, "full", {9}, (1706, 960, 2560, 1440)),
    (2560, 1440, "full", {3, 6}, (1706, 0, 2560, 960)),
    (2560, 1440, "full", {1, 9}, (0, 0, 2560, 1440)),
    (2560, 1440, "full", {2, 3}, (853, 0, 2560, 480)),
    (1920, 1080, "full", set(), (0, 0, 1920, 1080)),
    (1920, 1080, "top", set(), (0, 0, 1920, 540)),
    (1920, 1080, "bottom", set(), (0, 540, 1920, 1080)),
    (1920, 1080, "full", {1}, (0, 0, 640, 360)),
    (1920, 1080, "full", {5}, (640, 360, 1280, 720)),
    (1920, 1080, "full", {9}, (1280, 720, 1920, 1080)),
    (1920, 1080, "full", {3, 6}, (1280, 0, 1920, 720)),
    (1920, 1080, "full", {1, 9}, (0, 0, 1920, 1080)),
    (1920, 1080, "full", {2, 3}, (640, 0, 1920, 360)),
])
def test_crop_box(w, h, region, cells, box):
    assert crop_box(w, h, region, cells) == box


class NoFrameCamera:
    """假相機：grab 永遠沒有新畫面，記下是否被釋放。"""

    def __init__(self):
        self.released = False

    def grab(self):
        return None

    def release(self):
        self.released = True


def test_grab_times_out_and_resets_camera(monkeypatch):
    cam = NoFrameCamera()
    monkeypatch.setattr(capture, "_camera", cam)
    with pytest.raises(TimeoutError, match="^截圖逾時$"):
        capture.grab("full", set(), timeout=0.05)
    assert cam.released is True
    assert capture._camera is None


class Out:
    def __init__(self, hmonitor):
        self.hmonitor = hmonitor


def test_output_index_matches_hmonitor():
    outputs = [[Out(11), Out(22)], [Out(33)]]
    assert capture.output_index(outputs, 22) == (0, 1)
    assert capture.output_index(outputs, 33) == (1, 0)


def test_output_index_falls_back_to_first_output():
    assert capture.output_index([[Out(11)]], 99) == (0, 0)


@pytest.mark.parametrize("box, logical, image, expected", [
    ((100, 50, 300, 250), (1920, 1080), (1920, 1080), (100, 50, 300, 250)),     # 100% 縮放
    ((100, 50, 300, 250), (1280, 720), (1920, 1080), (150, 75, 450, 375)),      # 150% 縮放
    ((100, 50, 300, 250), (1536, 864), (1920, 1080), (125, 62, 375, 312)),      # 125% 縮放
    ((-5, -5, 2000, 2000), (1920, 1080), (1920, 1080), (0, 0, 1920, 1080)),     # 超出螢幕時夾在範圍內
])
def test_scale_box(box, logical, image, expected):
    assert scale_box(box, *logical, *image) == expected
