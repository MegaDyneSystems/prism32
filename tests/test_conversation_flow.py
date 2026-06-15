"""Tests for Prism32 multi-turn AI conversation flow helpers."""
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

exec(open('prism32.py').read().split('if __name__')[0])


def test_handle_ask_blocks_ask_only_returns_flag_and_history():
    """Ask-only responses should record the answer and tell the loop to continue."""
    old_ask_user = globals()['ask_user']
    history = []
    try:
        globals()['ask_user'] = lambda question: "blue"
        cleaned, asked = handle_ask_blocks("```ask\nFavorite color?\n```", history, return_asked=True)
    finally:
        globals()['ask_user'] = old_ask_user

    assert asked is True
    assert cleaned == ""
    assert history == [
        {"role": "assistant", "content": "[User was asked]: Favorite color?"},
        {"role": "user", "content": "[User answered]: blue"},
    ]


def test_handle_ask_blocks_preserves_execute_blocks_without_input():
    """Subagent ask stripping must not remove execute blocks."""
    resp = "```ask\nCan I run this?\n```\n```execute\necho ok\n```"
    cleaned, asked = handle_ask_blocks(resp, [], allow_input=False, return_asked=True)

    assert asked is True
    assert extract_blocks(cleaned, 'execute') == ["echo ok"]
    assert "Can I run this?" not in cleaned


def test_handle_ask_blocks_subagent_ask_only_is_deferred():
    """Subagents should report needed input instead of reading from stdin."""
    cleaned, asked = handle_ask_blocks("```ask\nNeed details?\n```", [], allow_input=False, return_asked=True)

    assert asked is True
    assert cleaned == "[SUBAGENT NEEDS INPUT] Need details?"


def test_ask_ai_filters_empty_assistant_messages():
    """Provider payloads should not include empty assistant turns."""
    old_urlopen = urllib.request.urlopen
    old_stream = Config.STREAM
    captured = {}

    class FakeResponse:
        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):
            return False

        def read(self):
            return json.dumps({"choices": [{"message": {"content": "ok"}}]}).encode()

    def fake_urlopen(req, timeout=0):
        captured['payload'] = json.loads(req.data.decode())
        return FakeResponse()

    try:
        Config.STREAM = False
        urllib.request.urlopen = fake_urlopen
        result = ask_ai([
            {"role": "system", "content": "system prompt"},
            {"role": "assistant", "content": ""},
            {"role": "user", "content": "hello"},
            {"role": "assistant", "content": "   "},
        ], stream=False, retry=0)
    finally:
        urllib.request.urlopen = old_urlopen
        Config.STREAM = old_stream

    assert result == "ok"
    assert captured['payload']['messages'] == [
        {"role": "system", "content": "system prompt"},
        {"role": "user", "content": "hello"},
    ]
