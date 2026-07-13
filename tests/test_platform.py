"""Tests for Prism32 Platform detection."""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Import Platform class directly
exec(open('prism32.py').read().split('if __name__')[0])

def test_platform_linux():
    """Linux should be detected on this system."""
    assert Platform.LINUX == True
    assert Platform.MACOS == False
    assert Platform.WINDOWS == False
    assert Platform.BSD == False

def test_platform_bsd_flag_exists():
    """Platform.BSD flag must exist for BSD support."""
    assert hasattr(Platform, 'BSD')
    assert isinstance(Platform.BSD, bool)

def test_platform_system():
    """get_system() should return something."""
    sysname = Platform.get_system()
    assert sysname is not None
    assert len(sysname) > 0

def test_platform_arch():
    """get_arch() should detect architecture."""
    arch = Platform.get_arch()
    assert arch is not None
    assert len(arch) > 0

def test_platform_cpu():
    """get_cpu() should return CPU model."""
    cpu = Platform.get_cpu()
    assert cpu is not None
    assert len(cpu) > 0

def test_platform_ram():
    """get_ram() should return total RAM."""
    ram = Platform.get_ram()
    assert ram > 0

def test_platform_ip():
    """get_ip() should return an IP address."""
    ip = Platform.get_ip()
    assert ip is not None
    assert len(ip) > 0

def test_platform_uptime():
    """get_uptime() should return uptime string."""
    uptime = Platform.get_uptime()
    assert uptime is not None
    assert len(uptime) > 0

def test_platform_package_manager():
    """get_package_manager() should detect pacman on Arch."""
    pm = Platform.get_package_manager()
    assert pm is not None  # Arch Linux has pacman
    assert isinstance(pm, str)

def test_platform_install_command():
    """get_install_command() should return a valid command."""
    cmd = Platform.get_install_command('python3')
    assert cmd is not None
    assert len(cmd) > 0
    assert 'python3' in cmd
