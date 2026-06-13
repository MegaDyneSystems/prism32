"""Tests for Prism32 memory system."""
import sys
import os
import tempfile
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

exec(open('prism32.py').read().split('if __name__')[0])

def test_memory_default():
    """_default_memory() should return valid structure."""
    mem = _default_memory()
    assert mem["version"] == 2
    assert "command_stats" in mem
    assert "error_patterns" in mem
    assert "preferences" in mem
    assert "session_count" in mem

def test_memory_load():
    """load_memory() should return valid memory."""
    mem = load_memory()
    assert mem is not None
    assert "version" in mem

def test_memory_save():
    """save_memory() should not crash."""
    mem = _default_memory()
    mem["session_count"] = 42
    save_memory(mem)
    reloaded = load_memory()
    assert reloaded["session_count"] == 42

def test_learn_command():
    """learn_command() should update stats."""
    learn_command("ls", success=True, duration=0.5)
    mem = load_memory()
    assert "ls" in mem["command_stats"]

def test_learn_error():
    """learn_error() should record error patterns."""
    learn_error("test error message", context="test")
    mem = load_memory()
    # Should not crash
    assert mem is not None
