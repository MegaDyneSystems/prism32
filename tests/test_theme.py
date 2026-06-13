"""Tests for Prism32 theme system."""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

exec(open('prism32.py').read().split('if __name__')[0])

def test_theme_registry_has_themes():
    """THEME_REGISTRY should have multiple themes."""
    assert len(THEME_REGISTRY) >= 10

def test_theme_phosphor():
    """Phosphor theme should have green colors."""
    theme = THEME_REGISTRY['phosphor']
    assert theme['primary'] == '\033[92m'  # Green
    assert theme['bright'] == '\033[1;92m'  # Bold green


def test_theme_amber():
    """Amber theme should have amber colors."""
    theme = THEME_REGISTRY['amber']
    assert theme['primary'] == '\033[33m'  # Yellow/Amber


def test_theme_nord():
    """Nord theme should have blue colors."""
    theme = THEME_REGISTRY['nord']
    assert theme['primary'] == '\033[38;5;109m'  # Nord blue

def test_t_function():
    """T() should return current theme colors."""
    t = T()
    assert 'primary' in t
    assert 'bright' in t
    assert 'dim' in t
    assert 'err' in t
    assert 'warn' in t

def test_strip_ansi():
    """strip_ansi() should remove ANSI codes."""
    text = '\033[92mHello\033[0m World'
    stripped = strip_ansi(text)
    assert stripped == 'Hello World'
    assert '\033' not in stripped
