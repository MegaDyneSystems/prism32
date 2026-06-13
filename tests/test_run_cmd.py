"""Tests for Prism32 command execution."""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

exec(open('prism32.py').read().split('if __name__')[0])

def test_run_cmd_simple():
    """run_cmd should execute basic commands."""
    result = run_cmd("echo 'hello world'")
    assert result is not None
    assert 'hello world' in result

def test_run_cmd_error():
    """run_cmd should handle errors gracefully."""
    result = run_cmd("nonexistent_command_xyz")
    assert result is not None
    # Should contain error message, not crash

def test_run_cmd_timeout():
    """run_cmd should handle timeout gracefully."""
    result = run_cmd("sleep 0.1", timeout=0.05)
    assert result is not None
    assert 'TIMEOUT' in result

def test_run_cmd_empty():
    """run_cmd should handle empty commands."""
    result = run_cmd("")
    assert result is not None
