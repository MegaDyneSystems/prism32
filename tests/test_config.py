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
    original_file = Config.CONFIG_FILE
    original = Config.ROOT_PASS
    tmpdir = tempfile.mkdtemp(prefix="prism32-cfg-")
    Config.CONFIG_FILE = os.path.join(tmpdir, "config.json")
    try:
        Config.ROOT_PASS = "test_password"
        Config.save_config()

        # Reload from the fresh file
        Config.ROOT_PASS = ""
        Config.load_config()
        assert Config.ROOT_PASS == "test_password"
    finally:
        Config.CONFIG_FILE = original_file
        Config.ROOT_PASS = original

def test_config_session_only_keys_not_persisted():
    """CLI-overridden fields (SESSION_ONLY_KEYS) must keep their on-disk
    values when anything triggers a save mid-session."""
    import json
    original_file = Config.CONFIG_FILE
    tmpdir = tempfile.mkdtemp(prefix="prism32-cfg-")
    Config.CONFIG_FILE = os.path.join(tmpdir, "config.json")
    old_model, old_key = Config.MODEL, Config.API_KEY
    old_keys = set(Config.SESSION_ONLY_KEYS)
    try:
        # Persist a baseline config with real-looking values
        Config.MODEL = "saved-model"
        Config.API_KEY = "saved-key"
        Config.SESSION_ONLY_KEYS.clear()
        Config.save_config()

        # Simulate CLI overrides + a later save (e.g. /stream off)
        Config.MODEL = "cli-model"
        Config.API_KEY = "cli-key"
        Config.SESSION_ONLY_KEYS.update({"model", "api_key"})
        Config.save_config()

        with open(Config.CONFIG_FILE) as f:
            data = json.load(f)
        assert data["model"] == "saved-model"
        assert data["api_key"] == "saved-key"
    finally:
        Config.CONFIG_FILE = original_file
        Config.MODEL, Config.API_KEY = old_model, old_key
        Config.SESSION_ONLY_KEYS.clear()
        Config.SESSION_ONLY_KEYS.update(old_keys)

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
