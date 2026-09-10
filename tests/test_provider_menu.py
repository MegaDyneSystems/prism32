"""Tests for the interactive /provider manager.

Covers the v7.1 redesign:
- detect_local_servers: TCP probing, closed ports ignored, probes injectable
- numbered picker: registry rows + detected-but-unregistered servers
- edit wizard: prefilled values, Enter keeps / type replaces / '-' clears key
- switching through the menu wires provider + base + key
- removing a built-in resets to factory defaults instead of deleting it
- removing a user-added provider removes it from registry and config
"""
import socket
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import prism32
from prism32 import (
    Config,
    PROVIDER_REGISTRY,
    _BUILTIN_PROVIDER_DEFAULTS,
    _base_endpoint,
    _provider_menu_rows,
    cmd_provider_edit,
    cmd_provider_menu,
    cmd_provider_remove,
    detect_local_servers,
)


def _listener():
    s = socket.socket()
    s.bind(("127.0.0.1", 0))
    s.listen(1)
    return s, s.getsockname()[1]


def _closed_port():
    s = socket.socket()
    s.bind(("127.0.0.1", 0))
    port = s.getsockname()[1]
    s.close()  # port is now free → connections are refused
    return port


class ScriptedInput:
    """input() stand-in feeding scripted answers in order."""
    def __init__(self, answers):
        self._it = iter(answers)
        self.seen = []

    def __call__(self, prompt=""):
        ans = next(self._it)
        self.seen.append((prompt, ans))
        return ans


def test_detect_local_servers_finds_open_port():
    srv, port = _listener()
    try:
        probes = [("llamacpp", "llama.cpp server", f"http://127.0.0.1:{port}/v1")]
        det = detect_local_servers(timeout=0.5, probes=probes)
        assert len(det) == 1
        assert det[0]["suggest"] == "llamacpp"
        assert det[0]["api_base"] == f"http://127.0.0.1:{port}/v1"
    finally:
        srv.close()


def test_detect_local_servers_ignores_closed_port():
    probes = [("ollama", "Ollama", f"http://127.0.0.1:{_closed_port()}/v1")]
    assert detect_local_servers(timeout=0.5, probes=probes) == []


def test_menu_rows_append_unregistered_detected_server():
    srv, port = _listener()
    try:
        probes = [("llamacpp", "llama.cpp server", f"http://127.0.0.1:{port}/v1")]
        det = detect_local_servers(timeout=0.5, probes=probes)
        rows = _provider_menu_rows(det)
        new = [r for r in rows if r.get("detected_new")]
        assert len(new) == 1
        assert new[0]["suggest"] == "llamacpp"
        # an unused suggest name stays un-suffixed
        if "llamacpp" not in PROVIDER_REGISTRY:
            assert new[0]["suggest"] == "llamacpp"
        # registered built-ins are present exactly once, never re-detected
        assert sum(1 for r in rows if r["name"] == "openai") == 1
    finally:
        srv.close()


def test_menu_rows_skip_detection_matching_registry_base():
    # a detection whose base already belongs to a registry entry must not
    # produce a duplicate row
    rows = _provider_menu_rows([{"suggest": "x", "label": "dup",
                                "api_base": "https://api.openai.com/v1"}])
    assert not any(r.get("detected_new") for r in rows)


def test_menu_rows_dedupe_localhost_spellings():
    # 'localhost' (ollama builtin) and '127.0.0.1' (probe result) are the
    # same server — one row, not two
    assert _base_endpoint("http://localhost:11434/v1") == \
           _base_endpoint("http://127.0.0.1:11434/v1")
    rows = _provider_menu_rows([{"suggest": "ollama", "label": "Ollama",
                                "api_base": "http://127.0.0.1:11434/v1"}])
    assert not any(r.get("detected_new") for r in rows)
    # https default port differs from http
    assert _base_endpoint("https://a.example/v1") != _base_endpoint("http://a.example/v1")


def test_edit_wizard_replaces_and_keeps():
    Config.set_provider_entry("editme", api_base="http://old.example/v1",
                              model="m1", api_key="k1")
    si = ScriptedInput(["http://new.example/v1", "", "", "n"])  # base → new, key keep, model keep, no test
    cmd_provider_edit("editme", input_fn=si)
    reg = PROVIDER_REGISTRY["editme"]
    assert reg["api_base"] == "http://new.example/v1"
    assert reg["default_key"] == "k1"      # Enter kept the key
    assert reg["model"] == "m1"            # Enter kept the model


def test_edit_wizard_sets_and_clears_key():
    Config.set_provider_entry("editme2", api_base="http://a/v1",
                              model="m", api_key="secret-key-123")
    si = ScriptedInput(["", "fresh-key-456", "better-model", "n"])
    cmd_provider_edit("editme2", input_fn=si)
    reg = PROVIDER_REGISTRY["editme2"]
    assert reg["default_key"] == "fresh-key-456"
    assert reg["model"] == "better-model"
    assert reg["api_base"] == "http://a/v1"

    si = ScriptedInput(["", "-", "", "n"])  # '-' clears the key
    cmd_provider_edit("editme2", input_fn=si)
    assert not PROVIDER_REGISTRY["editme2"].get("default_key")


def test_menu_configures_and_switches_to_detected_server():
    srv, port = _listener()
    try:
        det = [{"suggest": "llamacpp", "label": "llama.cpp server",
                "api_base": f"http://127.0.0.1:{port}/v1"}]
        rows = _provider_menu_rows(det)
        idx = next(i for i, r in enumerate(rows, 1) if r.get("detected_new"))
        name = rows[idx - 1]["suggest"]

        old_provider = Config.PROVIDER
        si = ScriptedInput([str(idx), "y", "q"])  # select, configure, quit
        cmd_provider_menu(input_fn=si, detect_fn=lambda: det)
        assert Config.PROVIDER == name
        assert name != old_provider or name == "llamacpp"
        assert PROVIDER_REGISTRY[name]["api_base"] == f"http://127.0.0.1:{port}/v1"
        # persisted to config.json so it survives restart
        import json
        with open(Config.CONFIG_FILE) as f:
            data = json.load(f)
        assert name in (data.get("providers") or {})
    finally:
        srv.close()
        Config.PROVIDER = "local"


def test_menu_switch_to_registry_provider():
    si = ScriptedInput(["openai", "s", "b", "q"])  # unused direct loop path
    # switch via the detail menu on a builtin with a known model
    rows = _provider_menu_rows([])
    idx = next(i for i, r in enumerate(rows, 1) if r["name"] == "openai")
    si = ScriptedInput([str(idx), "s", "q"])
    cmd_provider_menu(input_fn=si, detect_fn=lambda: [])
    assert Config.PROVIDER == "openai"
    assert Config.MODEL == "gpt-4o"
    assert Config.API_BASE == "https://api.openai.com/v1"
    Config.PROVIDER = "local"


def test_remove_builtin_resets_factory_defaults():
    Config.set_provider_entry("deepseek", api_base="http://bad.example/v1",
                              model="wrong", api_key="k")
    assert PROVIDER_REGISTRY["deepseek"]["api_base"] == "http://bad.example/v1"
    cmd_provider_remove("deepseek")
    reg = PROVIDER_REGISTRY["deepseek"]
    assert reg["api_base"] == _BUILTIN_PROVIDER_DEFAULTS["deepseek"]["api_base"]
    assert reg["model"] == _BUILTIN_PROVIDER_DEFAULTS["deepseek"]["model"]
    assert "deepseek" in PROVIDER_REGISTRY  # still selectable


def test_remove_user_provider_deletes_it():
    Config.set_provider_entry("mine", api_base="http://mine/v1")
    assert "mine" in PROVIDER_REGISTRY
    cmd_provider_remove("mine")
    assert "mine" not in PROVIDER_REGISTRY
    import json
    with open(Config.CONFIG_FILE) as f:
        assert "mine" not in (json.load(f).get("providers") or {})


def test_builtin_snapshot_matches_registry_on_fresh_load():
    # the snapshot is taken after factory registrations; every factory id
    # must exist in the live registry (user entries may add more)
    for pid in _BUILTIN_PROVIDER_DEFAULTS:
        assert pid in PROVIDER_REGISTRY
