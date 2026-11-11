"""截圖：以 dxcam 擷取工具所在螢幕，依截圖區域裁切。

截圖區域：region 為 "full"（全畫面）、"top"（上半部）、"bottom"（下半部）；
cells 為九宮格格號集合（1–9，左上到右下），有 cells 時取所選格子的外框矩形。
"""

import time

GRAB_TIMEOUT_S = 2                               # 一直沒有新畫面時最多等多久
_camera = None                                   # dxcam 相機，第一次截圖時才建立
_camera_key = None                               # 相機對應的 (device_idx, output_idx)


def crop_box(w, h, region, cells):
    """螢幕 w x h 中截圖區域的矩形 (x1, y1, x2, y2)。"""
    if cells:
        cols = [(c - 1) % 3 for c in cells]
        rows = [(c - 1) // 3 for c in cells]
        return (min(cols) * w // 3, min(rows) * h // 3,
                (max(cols) + 1) * w // 3, (max(rows) + 1) * h // 3)
    return {"full": (0, 0, w, h), "top": (0, 0, w, h // 2), "bottom": (0, h // 2, w, h)}[region]


def output_index(outputs, hmonitor):
    """dxcam 的輸出清單（outputs[device][output]）中 hmonitor 相同者的 (device_idx, output_idx)；找不到回傳 (0, 0)。"""
    for d, row in enumerate(outputs):
        for o, out in enumerate(row):
            if int(out.hmonitor or 0) == int(hmonitor or 0):
                return d, o
    return 0, 0


def grab(region, cells, hmonitor=None, timeout=GRAB_TIMEOUT_S):
    """擷取 hmonitor 所指螢幕（None 為 output 0）並裁切，回傳 BGR 圖片；逾時重置相機並丟出 TimeoutError。"""
    global _camera, _camera_key
    key = (0, 0)
    if hmonitor is not None:
        import dxcam                             # 只在 Windows 可用，延後匯入讓測試環境可載入本模組
        factory = type(dxcam.DXFactory)._instances[dxcam.DXFactory]    # 已建立的單例，避免重複建立時的 warning
        key = output_index(factory.outputs, hmonitor)
    if _camera is not None and _camera_key not in (None, key):                     # 螢幕換了就重建相機
        _camera.release()
        _camera = None
    if _camera is None:
        import dxcam
        _camera = dxcam.create(device_idx=key[0], output_idx=key[1], output_color="BGR")
        _camera_key = key
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
