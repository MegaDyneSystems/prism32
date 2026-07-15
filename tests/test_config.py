"""Tests for Prism32 Config class."""
import sys
import os
import tempfile
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

exec(open('prism32.py').read().split('if __name__')[0])
_register_extended_themes()  # ensure deferred themes are loaded for tests

def test_config_defaults():
    """Config should have sensible defaults."""
    assert Config.API_BASE == "http://127.0.0.1:8080"
    assert Config.ROOT_PASS == ""
    assert Config.CMD_TIMEOUT >= 60
    assert Config.TEMPERATURE == 0.7
    assert Config.THEME == "ember"
    assert Config.MAX_HISTORY >= 1000
    assert Config.GOAL_MAX_STEPS >= 20

def test_config_save_load():
    """Config save/load should preserve values."""
    # Save current config
    original = Config.ROOT_PASS
    Config.ROOT_PASS = "test_password"
    Config.save_config()
    
    # Reload
    Config.load_config()
    assert Config.ROOT_PASS == "test_password"
    
    # Restore
    Config.ROOT_PASS = original
    Config.save_config()

def test_config_model_context_map():
    """MODEL_CONTEXT_MAP should have known models."""
    assert "qwen" in Config.MODEL_CONTEXT_MAP
    assert "llama" in Config.MODEL_CONTEXT_MAP
    assert "gpt-4" in Config.MODEL_CONTEXT_MAP
    assert "claude" in Config.MODEL_CONTEXT_MAP

def test_config_theme():
    """Config theme should be a valid theme."""
    assert Config.THEME in THEME_REGISTRY
    theme = THEME_REGISTRY[Config.THEME]
    assert 'primary' in theme
    assert 'bright' in theme
    assert 'dim' in theme
