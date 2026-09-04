"""Tests for tool-call healing across non-standard model formats."""
import prism32


def test_bare_json_command_heals():
    text = 'Let me check the directory.\n{"command": "ls -la /tmp", "explanation": "list files"}'
    healed, was = prism32.heal_response(text)
    assert was
    assert "```execute" in healed
    assert "ls -la /tmp" in healed


def test_kimi_ascii_tokens_heal():
    text = ('<|tool_calls_section_begin|><|tool_call_begin|>function<|tool_call_argument_begin|>'
            '{"command": "df -h"}<|tool_call_end|><|tool_calls_section_end|>')
    healed, was = prism32.heal_response(text)
    assert was
    assert "df -h" in healed
    assert "```execute" in healed
    assert "<|tool_call" not in healed


def test_fullwidth_kimi_tokens_heal():
    text = ('<｜tool▁calls▁section▁begin｜><｜tool▁call▁begin｜>function<｜tool▁call▁argument▁begin｜>'
            '{"command": "free -m"}<｜tool▁call▁end｜><｜tool▁calls▁section▁end｜>')
    healed, was = prism32.heal_response(text)
    assert was
    assert "free -m" in healed
    assert "```execute" in healed
    assert "｜" not in healed


def test_antml_xml_tool_call_heals():
    text = 'I will check the time.\n<invoke name="execute">\n<parameter name="command">date</parameter>\n</invoke>'
    healed, was = prism32.heal_response(text)
    assert was
    assert "date" in healed
    assert "```execute" in healed
    assert "<invoke" not in healed


def test_openai_toolcall_json_heals():
    text = 'Checking disk usage.\n{"name": "execute", "arguments": {"command": "du -sh /var"}}'
    healed, was = prism32.heal_response(text)
    assert was
    assert "du -sh /var" in healed


def test_plain_prose_not_healed():
    text = "Reading all reference files now:"
    healed, was = prism32.heal_response(text)
    assert not was
    assert healed == text


def test_normal_execute_blocks_untouched():
    text = "Analysis:\n```execute\necho hi\n```\nDone."
    healed, was = prism32.heal_response(text)
    assert not was
    assert healed == text


def test_native_tool_calls_to_blocks():
    tcs = [
        {"function": {"name": "execute", "arguments": '{"command": "ls /var"}'}},
        {"function": {"name": "ask", "arguments": '{"question": "Which DB?"}'}},
        {"function": {"name": "execute", "arguments": "not json"}},
    ]
    out = prism32._tool_calls_to_blocks(tcs)
    assert "```execute\nls /var\n```" in out
    assert "```ask\nWhich DB?\n```" in out
    assert prism32._tool_calls_to_blocks(None) == ""
    assert prism32._tool_calls_to_blocks([]) == ""
    # aliased function names
    out2 = prism32._tool_calls_to_blocks([{"function": {"name": "bash", "arguments": '{"command": "date"}'}}])
    assert "date" in out2 and "```execute" in out2
