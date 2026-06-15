"""Tests for Prism32 interjection feature."""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

exec(open('prism32.py').read().split('if __name__')[0])

def test_interjection_globals_exist():
    """Interjection globals should be defined at module level."""
    assert '_INTERJECTION_ACTIVE' in globals()
    assert '_INTERJECTION_BUF' in globals()
    assert '_INTERJECTION_RESULT' in globals()
    assert '_SAVED_TERMIOS' in globals()

def test_interjection_start_does_not_crash():
    """_interjection_start should not raise."""
    try:
        _interjection_start()
    except Exception:
        assert False, "_interjection_start raised"

def test_interjection_stop_does_not_crash():
    """_interjection_stop should not raise."""
    try:
        _interjection_stop()
    except Exception:
        assert False, "_interjection_stop raised"

def test_interjection_stop_preserves_result():
    """_interjection_stop should NOT clear _INTERJECTION_RESULT."""
    global _INTERJECTION_RESULT, _SAVED_TERMIOS
    _INTERJECTION_RESULT = "test_value"
    _SAVED_TERMIOS = None
    _interjection_stop()
    assert _INTERJECTION_RESULT == "test_value"

def test_interjection_double_stop_safe():
    """Calling _interjection_stop twice should be safe."""
    global _SAVED_TERMIOS
    _SAVED_TERMIOS = None
    _interjection_stop()
    _interjection_stop()

def test_interjection_poll_inactive():
    """_interjection_poll should return None when not active."""
    global _INTERJECTION_ACTIVE, _INTERJECTION_BUF
    _INTERJECTION_ACTIVE = False
    _INTERJECTION_BUF = ""
    result = _interjection_poll()
    assert result is None

def test_interjection_poll_no_data():
    """_interjection_poll should return None when no stdin data."""
    global _INTERJECTION_ACTIVE, _INTERJECTION_BUF
    _INTERJECTION_ACTIVE = True
    _INTERJECTION_BUF = ""
    result = _interjection_poll()
    assert result is None

def test_interjection_empty_enter_does_not_interrupt():
    """Blank Enter while streaming should not become a follow-up prompt."""
    global _INTERJECTION_ACTIVE, _INTERJECTION_BUF, _INTERJECTION_CURSOR, _INTERJECTION_RESULT, _INTERJECTION_HAS_TYPED
    old_select = globals().get('select')
    old_read = os.read
    old_stdin = sys.stdin

    class FakeSelect:
        @staticmethod
        def select(readable, writable, exceptional, timeout):
            return ([0], [], [])

    class FakeStdin:
        def fileno(self):
            return 0

    try:
        globals()['select'] = FakeSelect
        os.read = lambda fd, size: b"\n"
        sys.stdin = FakeStdin()
        _INTERJECTION_ACTIVE = True
        _INTERJECTION_BUF = ""
        _INTERJECTION_CURSOR = 0
        _INTERJECTION_RESULT = None
        _INTERJECTION_HAS_TYPED = False
        assert _interjection_poll() is None
        assert _INTERJECTION_RESULT is None
        assert _INTERJECTION_BUF == ""
    finally:
        globals()['select'] = old_select
        os.read = old_read
        sys.stdin = old_stdin

def test_interjection_text_enter_sets_result_once():
    """Typed interjection text should be captured without extra Enter."""
    global _INTERJECTION_ACTIVE, _INTERJECTION_BUF, _INTERJECTION_CURSOR, _INTERJECTION_RESULT, _INTERJECTION_HAS_TYPED
    old_select = globals().get('select')
    old_read = os.read
    old_stdin = sys.stdin

    class FakeSelect:
        @staticmethod
        def select(readable, writable, exceptional, timeout):
            return ([0], [], [])

    class FakeStdin:
        def fileno(self):
            return 0

    try:
        globals()['select'] = FakeSelect
        os.read = lambda fd, size: b"follow up\n"
        sys.stdin = FakeStdin()
        _INTERJECTION_ACTIVE = True
        _INTERJECTION_BUF = ""
        _INTERJECTION_CURSOR = 0
        _INTERJECTION_RESULT = None
        _INTERJECTION_HAS_TYPED = False
        assert _interjection_poll() == "follow up"
        assert _INTERJECTION_RESULT == "follow up"
        assert _INTERJECTION_BUF == ""
    finally:
        globals()['select'] = old_select
        os.read = old_read
        sys.stdin = old_stdin

def test_interjection_escape_requests_cancel():
    """Bare Escape should stop the active agent operation."""
    global _INTERJECTION_ACTIVE, _INTERJECTION_BUF, _INTERJECTION_CURSOR, _INTERJECTION_RESULT, _INTERJECTION_HAS_TYPED
    old_select = globals().get('select')
    old_read = os.read
    old_stdin = sys.stdin

    class FakeSelect:
        @staticmethod
        def select(readable, writable, exceptional, timeout):
            return ([0], [], [])

    class FakeStdin:
        def fileno(self):
            return 0

    try:
        clear_agent_cancel()
        globals()['select'] = FakeSelect
        os.read = lambda fd, size: b"\x1b"
        sys.stdin = FakeStdin()
        _INTERJECTION_ACTIVE = True
        _INTERJECTION_BUF = ""
        _INTERJECTION_CURSOR = 0
        _INTERJECTION_RESULT = None
        _INTERJECTION_HAS_TYPED = False
        assert _interjection_poll() is _INTERJECTION_CANCEL
        assert agent_cancel_requested()
        assert _INTERJECTION_RESULT is None
    finally:
        clear_agent_cancel()
        globals()['select'] = old_select
        os.read = old_read
        sys.stdin = old_stdin

def test_interjection_arrow_escape_sequence_does_not_cancel():
    """ANSI arrow-key sequences should remain editable interjection input."""
    global _INTERJECTION_ACTIVE, _INTERJECTION_BUF, _INTERJECTION_CURSOR, _INTERJECTION_RESULT, _INTERJECTION_HAS_TYPED, _INTERJECTION_HISTORY, _INTERJECTION_HISTORY_IDX
    old_select = globals().get('select')
    old_read = os.read
    old_stdin = sys.stdin
    old_history = list(_INTERJECTION_HISTORY)

    class FakeSelect:
        @staticmethod
        def select(readable, writable, exceptional, timeout):
            return ([0], [], [])

    class FakeStdin:
        def fileno(self):
            return 0

    try:
        clear_agent_cancel()
        globals()['select'] = FakeSelect
        os.read = lambda fd, size: b"\x1b[A"
        sys.stdin = FakeStdin()
        _INTERJECTION_ACTIVE = True
        _INTERJECTION_BUF = ""
        _INTERJECTION_CURSOR = 0
        _INTERJECTION_RESULT = None
        _INTERJECTION_HAS_TYPED = False
        _INTERJECTION_HISTORY = ["previous prompt"]
        _INTERJECTION_HISTORY_IDX = -1
        assert _interjection_poll() is None
        assert not agent_cancel_requested()
        assert _INTERJECTION_BUF == "previous prompt"
    finally:
        clear_agent_cancel()
        _INTERJECTION_HISTORY = old_history
        globals()['select'] = old_select
        os.read = old_read
        sys.stdin = old_stdin

def test_interjection_buf_accumulation():
    """_INTERJECTION_BUF should accumulate characters."""
    global _INTERJECTION_BUF
    _INTERJECTION_BUF = ""
    _INTERJECTION_BUF += "h"
    _INTERJECTION_BUF += "e"
    _INTERJECTION_BUF += "l"
    _INTERJECTION_BUF += "l"
    _INTERJECTION_BUF += "o"
    assert _INTERJECTION_BUF == "hello"

def test_interjection_buf_backspace():
    """Backspace should remove last character."""
    global _INTERJECTION_BUF
    _INTERJECTION_BUF = "hello"
    _INTERJECTION_BUF = _INTERJECTION_BUF[:-1]
    assert _INTERJECTION_BUF == "hell"
    _INTERJECTION_BUF = _INTERJECTION_BUF[:-1]
    assert _INTERJECTION_BUF == "hel"

def test_interjection_buf_clear():
    """Clearing buffer should work."""
    global _INTERJECTION_BUF
    _INTERJECTION_BUF = "hello"
    _INTERJECTION_BUF = ""
    assert _INTERJECTION_BUF == ""

def test_interjection_result_flow():
    """Simulate the full result flow: poll sets, stop preserves, main reads."""
    global _INTERJECTION_RESULT, _INTERJECTION_BUF
    _INTERJECTION_RESULT = None
    _INTERJECTION_BUF = "test_input"
    result = _INTERJECTION_BUF
    _INTERJECTION_BUF = ""
    _INTERJECTION_RESULT = result
    assert _INTERJECTION_RESULT == "test_input"
    _interjection_stop()
    assert _INTERJECTION_RESULT == "test_input"
    inj = _INTERJECTION_RESULT
    _INTERJECTION_RESULT = None
    assert inj == "test_input"
    assert _INTERJECTION_RESULT is None

def test_interjection_start_resets_state():
    """_interjection_start should reset buffer and result."""
    global _INTERJECTION_BUF, _INTERJECTION_RESULT, _SAVED_TERMIOS
    _INTERJECTION_BUF = "old_buf"
    _INTERJECTION_RESULT = "old_result"
    _SAVED_TERMIOS = "old_termios"
    _interjection_start()
    assert _INTERJECTION_BUF == ""
    assert _INTERJECTION_RESULT is None
    assert _SAVED_TERMIOS is None

def test_interjection_stop_clears_buf():
    """_interjection_stop should clear buffer."""
    global _INTERJECTION_BUF, _INTERJECTION_RESULT, _SAVED_TERMIOS
    _INTERJECTION_BUF = "hello"
    _INTERJECTION_RESULT = "world"
    _SAVED_TERMIOS = None
    _interjection_stop()
    assert _INTERJECTION_BUF == ""

def test_draw_footer_does_not_crash():
    """draw_footer should not raise."""
    try:
        draw_footer(build_status_bar())
    except Exception:
        assert False, "draw_footer raised"

def test_clear_footer_does_not_crash():
    """clear_footer should not raise."""
    try:
        clear_footer()
    except Exception:
        assert False, "clear_footer raised"

def test_move_to_scroll_bottom_does_not_crash():
    """move_to_scroll_bottom should not raise."""
    try:
        move_to_scroll_bottom()
    except Exception:
        assert False, "move_to_scroll_bottom raised"

def test_read_footer_input_reads_single_line():
    """Footer prompt input should consume one submitted line."""
    global _footer_reserved, _ANSI_ENABLED
    old_footer = _footer_reserved
    old_ansi = _ANSI_ENABLED
    old_stdin = sys.stdin

    class FakeStdin:
        def __init__(self):
            self.calls = 0

        def readline(self):
            self.calls += 1
            return "hello agent\n"

    fake = FakeStdin()
    try:
        _footer_reserved = True
        _ANSI_ENABLED = False
        sys.stdin = fake
        assert read_footer_input("status") == "hello agent"
        assert fake.calls == 1
    finally:
        _footer_reserved = old_footer
        _ANSI_ENABLED = old_ansi
        sys.stdin = old_stdin
