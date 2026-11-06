"""面板狀態機：輸入事件序列，檢查狀態與副作用指令。"""

from gt.panel_state import Command, Event, PanelStateMachine, State


def feed(machine, *events):
    """依序送入事件，回傳最後一個事件產生的指令。"""
    commands = []
    for event in events:
        commands = machine.handle(event)
    return commands


def test_hover_on_strip_for_full_delay_starts_expanding_and_focuses_input():
    m = PanelStateMachine()
    commands = feed(m, Event.STRIP_ENTER, Event.HOVER_TIMEOUT)
    assert m.state is State.EXPANDING
    assert commands == [Command.PLAY_EXPAND, Command.FOCUS_INPUT]


def test_leaving_strip_before_delay_does_not_expand():
    m = PanelStateMachine()
    commands = feed(m, Event.STRIP_ENTER, Event.STRIP_LEAVE, Event.HOVER_TIMEOUT)
    assert m.state is State.COLLAPSED
    assert commands == []


def test_expand_animation_finishing_leaves_panel_expanded():
    m = PanelStateMachine()
    commands = feed(m, Event.STRIP_ENTER, Event.HOVER_TIMEOUT, Event.ANIMATION_DONE)
    assert m.state is State.EXPANDED
    assert commands == []


def expanded_machine():
    m = PanelStateMachine()
    feed(m, Event.STRIP_ENTER, Event.HOVER_TIMEOUT, Event.STRIP_LEAVE, Event.ANIMATION_DONE)
    return m


def test_clicking_outside_expanded_panel_starts_collapsing():
    m = expanded_machine()
    commands = feed(m, Event.FOCUS_LOST)
    assert m.state is State.COLLAPSING
    assert commands == [Command.PLAY_COLLAPSE]


def test_pressing_esc_on_expanded_panel_starts_collapsing():
    m = expanded_machine()
    commands = feed(m, Event.ESC_PRESSED)
    assert m.state is State.COLLAPSING
    assert commands == [Command.PLAY_COLLAPSE]


def test_collapse_animation_finishing_leaves_panel_collapsed():
    m = expanded_machine()
    commands = feed(m, Event.ESC_PRESSED, Event.ANIMATION_DONE)
    assert m.state is State.COLLAPSED
    assert commands == []


def test_esc_during_expand_animation_reverses_into_collapse():
    m = PanelStateMachine()
    commands = feed(m, Event.STRIP_ENTER, Event.HOVER_TIMEOUT, Event.ESC_PRESSED)
    assert m.state is State.COLLAPSING
    assert commands == [Command.PLAY_COLLAPSE]


def test_hovering_strip_again_while_expanded_does_nothing():
    m = expanded_machine()
    commands = feed(m, Event.STRIP_ENTER, Event.HOVER_TIMEOUT)
    assert m.state is State.EXPANDED
    assert commands == []


def test_hovering_strip_during_collapse_animation_reverses_into_expand():
    m = expanded_machine()
    commands = feed(m, Event.FOCUS_LOST, Event.STRIP_ENTER, Event.HOVER_TIMEOUT)
    assert m.state is State.EXPANDING
    assert commands == [Command.PLAY_EXPAND, Command.FOCUS_INPUT]


def test_switching_to_app_while_collapsed_expands_and_focuses_input():
    m = PanelStateMachine()
    commands = feed(m, Event.APP_ACTIVATED)
    assert m.state is State.EXPANDING
    assert commands == [Command.PLAY_EXPAND, Command.FOCUS_INPUT]


def test_switching_away_after_app_activation_collapses():
    m = PanelStateMachine()
    commands = feed(m, Event.APP_ACTIVATED, Event.ANIMATION_DONE, Event.FOCUS_LOST)
    assert m.state is State.COLLAPSING
    assert commands == [Command.PLAY_COLLAPSE]


def test_switching_to_app_while_expanded_only_refocuses_input():
    m = expanded_machine()
    commands = feed(m, Event.APP_ACTIVATED)
    assert m.state is State.EXPANDED
    assert commands == [Command.FOCUS_INPUT]


def test_app_activation_during_collapse_animation_reverses_into_expand():
    m = PanelStateMachine()
    feed(m, Event.STRIP_ENTER, Event.HOVER_TIMEOUT, Event.ANIMATION_DONE, Event.ESC_PRESSED)
    commands = feed(m, Event.APP_ACTIVATED)
    assert m.state is State.EXPANDING
    assert commands == [Command.PLAY_EXPAND, Command.FOCUS_INPUT]
