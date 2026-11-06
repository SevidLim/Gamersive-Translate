"""啟動：python -m gt"""

import signal
import sys

from PySide6.QtCore import QTimer
from PySide6.QtWidgets import QApplication

from gt import config, platform_win
from gt.panel_state import Command, Event, PanelStateMachine
from gt.ui import EXPAND_MS, Panel, Strip

HOVER_DELAY_MS = 1500 - EXPAND_MS               # 從進入邊條到面板完全展開共 1.5 秒


def main():
    signal.signal(signal.SIGINT, signal.SIG_DFL)  # 終端機 Ctrl+C 直接結束程式
    config.load()                                # 首次啟動建立 config.json 並寫入預設值
    app = QApplication(sys.argv)
    app.setQuitOnLastWindowClosed(False)
    screen = app.primaryScreen()
    machine = PanelStateMachine()
    strip = Strip(screen)
    panel = Panel(screen)

    def on_foreground(hwnd):
        if hwnd != int(panel.winId()):
            send(Event.FOCUS_LOST)

    foreground = platform_win.ForegroundWatcher(on_foreground)
    hover = QTimer()
    hover.setSingleShot(True)
    hover.setInterval(HOVER_DELAY_MS)

    def send(event):
        for command in machine.handle(event):
            if command is Command.PLAY_EXPAND:
                panel.play_expand()
                foreground.start()                   # 面板展開期間才監看前景視窗
            elif command is Command.PLAY_COLLAPSE:
                foreground.stop()
                panel.play_collapse()

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
    panel.animation_done.connect(lambda: send(Event.ANIMATION_DONE))
    strip.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
