"""Windows 專用：Acrylic 毛玻璃、把視窗帶到前景。非 Windows 不做事。

enable_acrylic 沿用 Desktop-Agent-Pet 的 src/platform_win.py（做法照 PyQt-Frameless-Window 的 AcrylicWindow）。
"""

import ctypes
import sys

IS_WIN = sys.platform == "win32"

if IS_WIN:
    from ctypes import wintypes
    user32 = ctypes.windll.user32
    dwmapi = ctypes.windll.dwmapi
    kernel32 = ctypes.windll.kernel32
    user32.GetForegroundWindow.restype = wintypes.HWND
    user32.GetWindowThreadProcessId.restype = wintypes.DWORD
    user32.GetWindowThreadProcessId.argtypes = [wintypes.HWND, ctypes.c_void_p]

DWMWA_USE_IMMERSIVE_DARK_MODE = 20
DWMWA_WINDOW_CORNER_PREFERENCE = 33
DWMWCP_ROUND = 2
WCA_ACCENT_POLICY = 19
ACCENT_ENABLE_ACRYLICBLURBEHIND = 4
ACCENT_FLAGS_SHADOW = 0x20 | 0x40 | 0x80 | 0x100


def windows_build():
    try:
        return sys.getwindowsversion().build
    except AttributeError:
        return 0


def enable_acrylic(hwnd, tint):
    """視窗背後套 Acrylic 模糊。tint＝RRGGBBAA（疊在模糊上的顏色）。成功回傳 True。"""
    if not IS_WIN:
        return False

    class MARGINS(ctypes.Structure):
        _fields_ = [("l", ctypes.c_int), ("r", ctypes.c_int), ("t", ctypes.c_int), ("b", ctypes.c_int)]

    class DWM_BLURBEHIND(ctypes.Structure):
        _fields_ = [("dwFlags", wintypes.DWORD), ("fEnable", wintypes.BOOL),
                    ("hRgnBlur", wintypes.HRGN), ("fTransitionOnMaximized", wintypes.BOOL)]

    class ACCENT_POLICY(ctypes.Structure):
        _fields_ = [("AccentState", wintypes.DWORD), ("AccentFlags", wintypes.DWORD),
                    ("GradientColor", wintypes.DWORD), ("AnimationId", wintypes.DWORD)]

    class WINCOMPATTRDATA(ctypes.Structure):
        _fields_ = [("Attribute", wintypes.DWORD), ("Data", ctypes.POINTER(ACCENT_POLICY)),
                    ("SizeOfData", wintypes.ULONG)]

    h = wintypes.HWND(int(hwnd))

    def set_attr(attr, value):
        v = ctypes.c_int(value)
        return dwmapi.DwmSetWindowAttribute(h, attr, ctypes.byref(v), ctypes.sizeof(v))

    bb = DWM_BLURBEHIND(1, True, None, False)
    dwmapi.DwmEnableBlurBehindWindow(h, ctypes.byref(bb))
    abgr = "".join(tint[i:i + 2] for i in range(6, -1, -2))      # RRGGBBAA → AABBGGRR
    accent = ACCENT_POLICY(ACCENT_ENABLE_ACRYLICBLURBEHIND, ACCENT_FLAGS_SHADOW, int(abgr, 16), 0)
    data = WINCOMPATTRDATA(WCA_ACCENT_POLICY, ctypes.pointer(accent), ctypes.sizeof(accent))
    swca = user32.SetWindowCompositionAttribute
    swca.argtypes = [wintypes.HWND, ctypes.POINTER(WINCOMPATTRDATA)]
    swca.restype = wintypes.BOOL
    ok = bool(swca(h, ctypes.byref(data)))
    if windows_build() >= 22000:
        set_attr(DWMWA_USE_IMMERSIVE_DARK_MODE, 1)
        set_attr(DWMWA_WINDOW_CORNER_PREFERENCE, DWMWCP_ROUND)
        m = MARGINS(-1, -1, -1, -1)
        dwmapi.DwmExtendFrameIntoClientArea(h, ctypes.byref(m))
    return ok


def bring_to_foreground(hwnd):
    """把視窗設為前景（才收得到鍵盤與失去焦點事件）。
    前景是別的程式（例如遊戲）時，Windows 會擋 SetForegroundWindow，先 AttachThreadInput 到前景執行緒再設定。"""
    if not IS_WIN:
        return
    h = wintypes.HWND(int(hwnd))
    fg = user32.GetForegroundWindow()
    fg_thread = user32.GetWindowThreadProcessId(fg, None) if fg else 0
    me = kernel32.GetCurrentThreadId()
    attached = bool(fg_thread) and fg_thread != me and bool(user32.AttachThreadInput(me, fg_thread, True))
    try:
        user32.BringWindowToTop(h)
        user32.SetForegroundWindow(h)
    finally:
        if attached:
            user32.AttachThreadInput(me, fg_thread, False)


EVENT_SYSTEM_FOREGROUND = 0x0003
WINEVENT_OUTOFCONTEXT = 0x0000


class ForegroundWatcher:
    """前景視窗改變時呼叫 callback(hwnd)。用 SetWinEventHook(EVENT_SYSTEM_FOREGROUND)，
    只在 start() 到 stop() 之間掛鉤；事件由呼叫 start() 的執行緒（Qt 主執行緒的訊息迴圈）送達。"""

    def __init__(self, callback):
        self.callback = callback
        self.hook = None
        self._proc = None

    def start(self):
        if not IS_WIN or self.hook:
            return
        proc_type = ctypes.WINFUNCTYPE(None, wintypes.HANDLE, wintypes.DWORD, wintypes.HWND,
                                       wintypes.LONG, wintypes.LONG, wintypes.DWORD, wintypes.DWORD)
        self._proc = proc_type(lambda _h, _e, hwnd, _o, _c, _t, _ms: self.callback(int(hwnd or 0)))
        user32.SetWinEventHook.restype = wintypes.HANDLE
        self.hook = user32.SetWinEventHook(EVENT_SYSTEM_FOREGROUND, EVENT_SYSTEM_FOREGROUND, None,
                                           self._proc, 0, 0, WINEVENT_OUTOFCONTEXT) or None

    def stop(self):
        if self.hook:
            user32.UnhookWinEvent(wintypes.HANDLE(self.hook))
            self.hook = None


def foreground_window():
    if not IS_WIN:
        return 0
    return int(user32.GetForegroundWindow() or 0)


def set_foreground(hwnd):
    """本程序是前景程序時把前景交給 hwnd，回傳 SetForegroundWindow 的結果。"""
    if not IS_WIN:
        return False
    return bool(user32.SetForegroundWindow(wintypes.HWND(int(hwnd))))


def class_name(hwnd):
    if not IS_WIN:
        return ""
    buf = ctypes.create_unicode_buffer(256)
    user32.GetClassNameW(wintypes.HWND(int(hwnd)), buf, 256)
    return buf.value

