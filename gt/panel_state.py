"""面板狀態機：純邏輯，不依賴 Qt。

handle(事件) 更新 state，回傳要執行的副作用指令清單。
停留計時由呼叫端負責：滑鼠進入邊條時開始計時，離開時取消，滿 1.5 秒送 HOVER_TIMEOUT。
"""

from enum import Enum, auto


class State(Enum):
    COLLAPSED = auto()
    EXPANDING = auto()
    EXPANDED = auto()
    COLLAPSING = auto()


class Event(Enum):
    STRIP_ENTER = auto()
    STRIP_LEAVE = auto()
    HOVER_TIMEOUT = auto()
    ANIMATION_DONE = auto()
    FOCUS_LOST = auto()
    ESC_PRESSED = auto()
    APP_ACTIVATED = auto()                      # 本程式被啟用（例如 Alt+Tab 切到本程式）


class Command(Enum):
    PLAY_EXPAND = auto()
    PLAY_COLLAPSE = auto()
    FOCUS_INPUT = auto()                        # 焦點移到文字翻譯頁的輸入框


class PanelStateMachine:
    def __init__(self):
        self.state = State.COLLAPSED
        self.hovering = False

    def handle(self, event):
        if event is Event.STRIP_ENTER:
            self.hovering = True
        elif event is Event.STRIP_LEAVE:
            self.hovering = False
        elif event is Event.HOVER_TIMEOUT and self.hovering and self.state in (State.COLLAPSED, State.COLLAPSING):
            self.state = State.EXPANDING
            return [Command.PLAY_EXPAND, Command.FOCUS_INPUT]
        elif event is Event.APP_ACTIVATED and self.state in (State.COLLAPSED, State.COLLAPSING):
            self.state = State.EXPANDING
            return [Command.PLAY_EXPAND, Command.FOCUS_INPUT]
        elif event is Event.APP_ACTIVATED:
            return [Command.FOCUS_INPUT]
        elif event is Event.ANIMATION_DONE and self.state is State.EXPANDING:
            self.state = State.EXPANDED
        elif event in (Event.FOCUS_LOST, Event.ESC_PRESSED) and self.state in (State.EXPANDING, State.EXPANDED):
            self.state = State.COLLAPSING
            return [Command.PLAY_COLLAPSE]
        elif event is Event.ANIMATION_DONE and self.state is State.COLLAPSING:
            self.state = State.COLLAPSED
        return []
