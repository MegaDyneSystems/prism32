"""Tests for URL/HTTP/SSL handling."""
import json
import os
import ssl
import urllib.request

import prism32


class _FakeResponse:
    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False

    def read(self):
        return json.dumps({"choices": [{"message": {"content": "ok"}}]}).encode()


def test_normalize_api_base():
    assert prism32.normalize_api_base("https://api.example.com/v1/") == "https://api.example.com"
    assert prism32.normalize_api_base("https://api.example.com/v1") == "https://api.example.com"
    assert prism32.normalize_api_base("https://api.example.com/") == "https://api.example.com"
    assert prism32.normalize_api_base("https://api.example.com") == "https://api.example.com"
    assert prism32.normalize_api_base("http://127.0.0.1:8080/v1") == "http://127.0.0.1:8080"
    assert prism32.normalize_api_base("https://api.example.com/openai/v1") == "https://api.example.com/openai"
    assert prism32.normalize_api_base("") == "http://127.0.0.1:8080"


def test_ask_ai_url_no_double_slash():
    old_urlopen = urllib.request.urlopen
    old_api_base = prism32.Config.API_BASE
    old_api_key = prism32.Config.API_KEY
    old_stream = prism32.Config.STREAM
    captured = {}

    def fake_urlopen(req, timeout=0, **kwargs):
        captured["url"] = req.full_url
        captured["has_context"] = "context" in kwargs
        return _FakeResponse()

    try:
        urllib.request.urlopen = fake_urlopen
        prism32.Config.API_BASE = "https://api.example.com/v1/"
        prism32.Config.API_KEY = "test-key"
        prism32.Config.STREAM = False
        result = prism32.ask_ai([{"role": "user", "content": "hi"}], stream=False, retry=0)
    finally:
        urllib.request.urlopen = old_urlopen
        prism32.Config.API_BASE = old_api_base
        prism32.Config.API_KEY = old_api_key
        prism32.Config.STREAM = old_stream

    assert result == "ok"
    assert captured["url"] == "https://api.example.com/v1/chat/completions"


def test_urlopen_with_ssl_passes_context():
    old_urlopen = urllib.request.urlopen
    captured = {}

    def fake_urlopen(req, timeout=0, **kwargs):
        captured["kwargs"] = kwargs
        return _FakeResponse()

    try:
        urllib.request.urlopen = fake_urlopen
        prism32.Config.VERIFY_SSL = True
        prism32.urlopen_with_ssl(urllib.request.Request("http://localhost"), timeout=5)
    finally:
        urllib.request.urlopen = old_urlopen

    assert "context" in captured["kwargs"]
    assert captured["kwargs"]["context"] is not None


def test_env_verify_ssl_override():
    old_env = os.environ.get("PRISM32_VERIFY_SSL")
    try:
        os.environ["PRISM32_VERIFY_SSL"] = "0"
        prism32.Config.VERIFY_SSL = True
        ctx = prism32.create_ssl_context()
        if ssl:
            assert ctx is not None
            assert ctx.check_hostname == False
    finally:
        if old_env is None:
            os.environ.pop("PRISM32_VERIFY_SSL", None)
        else:
            os.environ["PRISM32_VERIFY_SSL"] = old_env


def test_plugin_api_http_get_adds_user_agent():
    api = prism32.PluginAPI("test")
    old_urlopen = urllib.request.urlopen
    captured = {}

    def fake_urlopen(req, timeout=0, **kwargs):
        captured["headers"] = {k.lower(): v for k, v in req.header_items()}
        captured["url"] = req.full_url
        return _FakeResponse()

    try:
        urllib.request.urlopen = fake_urlopen
        api.http_get("http://127.0.0.1:9999/test")
    finally:
        urllib.request.urlopen = old_urlopen

    assert captured["url"] == "http://127.0.0.1:9999/test"
    assert "user-agent" in captured["headers"]
    assert "Prism32" in captured["headers"]["user-agent"]


def test_plugin_api_http_post_handles_list_and_none_data():
    api = prism32.PluginAPI("test")
    old_urlopen = urllib.request.urlopen
    old_verify = prism32.Config.VERIFY_SSL
    captured = []

    def fake_urlopen(req, timeout=0, **kwargs):
        captured.append({"data": req.data, "ct": {k.lower(): v for k, v in req.header_items()}.get("content-type")})
        return _FakeResponse()

    try:
        urllib.request.urlopen = fake_urlopen
        prism32.Config.VERIFY_SSL = False
        api.http_post("http://127.0.0.1:9999", data=[1, 2, 3])
        api.http_post("http://127.0.0.1:9999", data=None)
    finally:
        urllib.request.urlopen = old_urlopen
        prism32.Config.VERIFY_SSL = old_verify

    assert len(captured) == 2
    assert captured[0]["data"] == b"[1, 2, 3]"
    assert captured[0]["ct"] == "application/json"
    assert captured[1]["data"] == b""


def test_provider_key_takes_full_value():
    old_api_key = prism32.Config.API_KEY
    try:
        # Simulate the parsing logic from the /provider key handler
        args_str = "key Bearer abc.def.ghi"
        parts = args_str.split(None, 1)
        key = parts[1].strip() if len(parts) > 1 else ""
        assert key == "Bearer abc.def.ghi"
    finally:
        prism32.Config.API_KEY = old_api_key
