"""啟動：python -m gt"""

import signal
import sys
import threading

from PySide6.QtCore import QObject, QTimer, Signal
from PySide6.QtWidgets import QApplication

from gt import config, platform_win
from gt.panel_state import Command, Event, PanelStateMachine, State
from gt.translate import GoogleTranslator
from gt.ui import EXPAND_MS, HostWindow, Panel, Strip

HOVER_DELAY_MS = 1500 - EXPAND_MS               # 從進入邊條到面板完全展開共 1.5 秒
# 按下 Alt+Tab 期間 explorer 暫時接手前景的視窗 class（實測，無官方文件）
ALT_TAB_CLASSES = {"ForegroundStaging", "XamlExplorerHostIslandWindow"}
HANDOFF_FALLBACK_MS = 1000                      # host 一直沒失去啟用時，最晚在這之後解除抑制


class _Relay(QObject):
    """把背景執行緒的翻譯結果以 queued signal 送回 UI 執行緒。"""

    done = Signal(object)


def main():
    signal.signal(signal.SIGINT, signal.SIG_DFL)  # 終端機 Ctrl+C 直接結束程式
    cfg = config.load()                          # 首次啟動建立 config.json 並寫入預設值
    app = QApplication(sys.argv)
    app.setQuitOnLastWindowClosed(False)
    screen = app.primaryScreen()
    machine = PanelStateMachine()
    strip = Strip(screen)
    panel = Panel(screen, cfg["google_api_key"])
    relay = _Relay()
    relay.done.connect(panel.show_result)

    def on_translate(text):
        translator = GoogleTranslator(cfg["google_api_key"])
        src, dst = cfg["source_lang"], cfg["target_lang"]
        # 網路請求在背景執行緒，不卡 UI
        threading.Thread(target=lambda: relay.done.emit(translator.translate(text, src, dst)),
                         daemon=True).start()

    def on_api_key(key):
        if key != cfg["google_api_key"]:
            cfg["google_api_key"] = key
            config.save(cfg)

    panel.translate_requested.connect(on_translate)
    panel.api_key_changed.connect(on_api_key)
    host = HostWindow(screen)
    handoff = {"active": False}                   # host 短暫啟用、交還前景期間為 True

    def is_ours(hwnd):
        return hwnd in (int(panel.winId()), int(host.winId()))

    def end_handoff():
        handoff["active"] = False

    handoff_timer = QTimer()
    handoff_timer.setSingleShot(True)
    handoff_timer.setInterval(HANDOFF_FALLBACK_MS)
    handoff_timer.timeout.connect(end_handoff)

    def hand_back_foreground():
        """讓 host 短暫取得前景再交還原本的 app，使 host 排在 Alt+Tab 清單第二。
        原本的 app＝呼叫當下的前景視窗（面板已隱藏，或程式剛啟動）。"""
        original = platform_win.foreground_window()
        if not original or is_ours(original) or platform_win.class_name(original) in ALT_TAB_CLASSES:
            return
        handoff["active"] = True
        handoff_timer.start()
        platform_win.bring_to_foreground(int(host.winId()))
        platform_win.set_foreground(original)

    def on_foreground(hwnd):
        if is_ours(hwnd):
            return
        if platform_win.class_name(hwnd) in ALT_TAB_CLASSES:
            return                                   # 等 Alt+Tab 真正的目標視窗再判斷
        send(Event.FOCUS_LOST)

    foreground = platform_win.ForegroundWatcher(on_foreground)
    hover = QTimer()
    hover.setSingleShot(True)
    hover.setInterval(HOVER_DELAY_MS)

    def send(event):
        if handoff["active"] and event in (Event.APP_ACTIVATED, Event.FOCUS_LOST):
            return
        for command in machine.handle(event):
            if command is Command.PLAY_EXPAND:
                panel.play_expand()
                foreground.start()                   # 面板展開期間才監看前景視窗
            elif command is Command.PLAY_COLLAPSE:
                foreground.stop()
                panel.play_collapse()
            elif command is Command.FOCUS_INPUT:
                panel.focus_input()

    def on_enter():
        hover.start()
        send(Event.STRIP_ENTER)

    def on_leave():
        hover.stop()
        send(Event.STRIP_LEAVE)

    strip.entered.connect(on_enter)
    strip.left.connect(on_leave)
    hover.timeout.connect(lambda: send(Event.HOVER_TIMEOUT))
    panel.esc_pressed.connect(lambda: send(Event.ESC_PRESSED))
    panel.focus_lost.connect(lambda: send(Event.FOCUS_LOST))
    def on_panel_activated():
        if host.isVisible():
            host.hide()                              # 面板已是前景才隱藏，Alt+Tab 清單不再有 host

    def on_animation_done():
        send(Event.ANIMATION_DONE)
        if machine.state is State.COLLAPSED and not host.isVisible():
            host.show()                              # WA_ShowWithoutActivating：不啟用
            hand_back_foreground()

    panel.activated.connect(on_panel_activated)
    panel.animation_done.connect(on_animation_done)
    host.activated.connect(lambda: send(Event.APP_ACTIVATED))
    host.deactivated.connect(lambda: handoff["active"] and end_handoff())  # 交還完成，host 失去啟用
    strip.show()
    host.show()
    hand_back_foreground()                           # 原本的 app＝啟動當下的前景視窗
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
