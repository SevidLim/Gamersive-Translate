"""截圖：以 dxcam 擷取主螢幕，依截圖區域裁切。

截圖區域：region 為 "full"（全畫面）、"top"（上半部）、"bottom"（下半部）；
cells 為九宮格格號集合（1–9，左上到右下），有 cells 時取所選格子的外框矩形。
"""

import time

GRAB_TIMEOUT_S = 2                               # 一直沒有新畫面時最多等多久
_camera = None                                   # dxcam 相機，第一次截圖時才建立


def crop_box(w, h, region, cells):
    """螢幕 w x h 中截圖區域的矩形 (x1, y1, x2, y2)。"""
    if cells:
        cols = [(c - 1) % 3 for c in cells]
        rows = [(c - 1) // 3 for c in cells]
        return (min(cols) * w // 3, min(rows) * h // 3,
                (max(cols) + 1) * w // 3, (max(rows) + 1) * h // 3)
    return {"full": (0, 0, w, h), "top": (0, 0, w, h // 2), "bottom": (0, h // 2, w, h)}[region]


def grab(region, cells, timeout=GRAB_TIMEOUT_S):
    """擷取主螢幕（output 0）並裁切，回傳 BGR 圖片；逾時重置相機並丟出 TimeoutError。"""
    global _camera
    if _camera is None:
        import dxcam                             # 只在 Windows 可用，延後匯入讓測試環境可載入本模組
        _camera = dxcam.create(output_idx=0, output_color="BGR")
    deadline = time.monotonic() + timeout
    frame = None
    while frame is None:                         # one-shot 模式沒有新畫面時會回傳 None
        if time.monotonic() > deadline:
            _camera.release()                    # 釋放後 dxcam.create 會丟棄這個實例，下次截圖重新建立
            _camera = None
            raise TimeoutError("截圖逾時")
        frame = _camera.grab()
    h, w = frame.shape[:2]
    x1, y1, x2, y2 = crop_box(w, h, region, cells)
    return frame[y1:y2, x1:x2]
