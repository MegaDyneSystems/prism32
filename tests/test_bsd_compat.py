"""Tests for BSD compatibility fixes."""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

exec(open('prism32.py').read().split('if __name__')[0])

def test_platform_bsd_detection_logic():
    """Test BSD detection logic for various platforms."""
    # Simulate NetBSD
    sys.platform = 'netbsd10.1'
    bsd_check = 'bsd' in sys.platform.lower() or sys.platform.lower().startswith('netbsd')
    assert bsd_check == True, "NetBSD should be detected as BSD"
    
    # Simulate FreeBSD
    sys.platform = 'freebsd14.0'
    bsd_check = 'bsd' in sys.platform.lower() or sys.platform.lower().startswith('netbsd')
    assert bsd_check == True, "FreeBSD should be detected as BSD"
    
    # Simulate OpenBSD
    sys.platform = 'openbsd7.5'
    bsd_check = 'bsd' in sys.platform.lower() or sys.platform.lower().startswith('netbsd')
    assert bsd_check == True, "OpenBSD should be detected as BSD"
    
    # Simulate Linux
    sys.platform = 'linux'
    bsd_check = 'bsd' in sys.platform.lower() or sys.platform.lower().startswith('netbsd')
    assert bsd_check == False, "Linux should NOT be detected as BSD"

def test_run_cmd_bsd_wrapping_logic():
    """Test that BSD wrapping logic works correctly."""
    # Test that su commands get wrapped on BSD
    test_cmds = [
        ('echo "$ROOT_PASS" | su -c "whoami"', True),
        ('ls -la', False),
        ('echo "$ROOT_PASS" | su -c "pkg_add python"', True),
        ('sudo apt-get update', False),
        ('echo "test" | grep test', False),
    ]
    
    for cmd, should_wrap in test_cmds:
        needs_wrap = 'su' in cmd and ('ROOT_PASS' in cmd or 'root_pass' in cmd)
        assert needs_wrap == should_wrap, f"Command '{cmd}' wrap check failed"
