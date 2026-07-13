"""Tests for cost-saving context compression (compress_tool_turns).

Verifies:
- Older verbose tool results are collapsed (middle elided).
- Recent turns are preserved VERBATIM (no fidelity loss where it matters).
- The caller's history list is never mutated (non-destructive).
- Command output containing early blank lines is still compressed (robustness).
"""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

exec(open('prism32.py').read().split('if __name__')[0])


def _tool_msg(cmd, result_lines, continuation="Command output above. Continue with your task."):
    body = "\n".join(result_lines)
    cont = f"\n\n{continuation}" if continuation else ""
    return {"role": "user", "content": f"Executed: {cmd}\nResult:\n{body}{cont}"}


def test_collapse_text_middle_keeps_head_and_tail():
    text = "\n".join(f"line {i}" for i in range(40))
    out = _collapse_text_middle(text, head_lines=4, tail_lines=3, max_chars=200)
    assert out.startswith("line 0\nline 1\nline 2\nline 3\n")
    assert out.endswith("line 37\nline 38\nline 39")
    assert "lines trimmed" in out
    assert "line 5" not in out  # middle elided


def test_collapse_text_middle_short_unchanged():
    short = "only a few\nlines\nhere"
    assert _collapse_text_middle(short, max_chars=400) == short


def test_compress_recent_turns_verbatim():
    """The most recent CONTEXT_COMPRESS_KEEP turns must be untouched."""
    Config.CONTEXT_COMPRESS_KEEP = 2
    # ~60 rows of ~25 chars = ~1500 chars of result (well above the 400 threshold)
    big = [f"row {i:03d} padded padding padding" for i in range(60)]
    msgs = [
        {"role": "system", "content": "sys"},
        _tool_msg("ls -la", big),                 # old -> compress
        {"role": "assistant", "content": "ok"},
        _tool_msg("pwd", [f"entry line {i} " * 5 for i in range(40)]),  # old -> compress
        _tool_msg("date", ["Mon Jul 13"]),        # recent -> verbatim
        {"role": "assistant", "content": "done"},  # recent -> verbatim
    ]
    # deep-copy-ish snapshot of contents to detect mutation
    orig_contents = [m.get("content") for m in msgs]
    out = compress_tool_turns(msgs, recent_keep=2)

    # Non-destructive: originals unchanged
    assert [m.get("content") for m in msgs] == orig_contents
    # Output length same
    assert len(out) == len(msgs)
    # System prompt untouched
    assert out[0]["content"] == "sys"
    # Recent two turns verbatim (index 4 and 5)
    assert out[4]["content"] == msgs[4]["content"]
    assert out[5]["content"] == msgs[5]["content"]
    # Old tool result (index 1) was compressed
    assert "lines trimmed" in out[1]["content"]
    assert "Executed: ls -la" in out[1]["content"]  # header preserved in head


def test_compress_robust_to_early_blank_line():
    """A long tool result with an early blank line must still be compressed.
    Regression: an earlier fragile version split on the first '\\n\\n' and
    kept everything after it verbatim, defeating compression."""
    Config.CONTEXT_COMPRESS_KEEP = 1
    result_lines = ["Package: foo", "Version: 1.0", ""] + [f"desc line {i}" for i in range(50)]
    msgs = [
        {"role": "system", "content": "sys"},
        _tool_msg("apt show foo", result_lines),
        {"role": "assistant", "content": "got it"},  # recent (keep=1) -> verbatim
    ]
    out = compress_tool_turns(msgs, recent_keep=1)
    assert "lines trimmed" in out[1]["content"]      # compressed despite early blank line
    assert "Executed: apt show foo" in out[1]["content"]  # header preserved
    assert "desc line 49" in out[1]["content"]       # tail preserved


def test_compress_skips_short_history():
    Config.CONTEXT_COMPRESS_KEEP = 6
    msgs = [
        {"role": "system", "content": "sys"},
        {"role": "user", "content": "hi"},
        {"role": "assistant", "content": "hello"},
    ]
    out = compress_tool_turns(msgs)
    assert out is msgs or [m.get("content") for m in out] == [m.get("content") for m in msgs]


def test_compress_subagent_format():
    """Subagent tool messages use 'Command succeeded=...Continue...' suffix — tail must survive."""
    Config.CONTEXT_COMPRESS_KEEP = 1
    big = [f"output line {i}" for i in range(40)]
    msgs = [
        {"role": "system", "content": "sys"},
        _tool_msg("scan", big, continuation="Command succeeded=True. Continue with task or give final answer."),
        {"role": "assistant", "content": "ok"},
    ]
    out = compress_tool_turns(msgs, recent_keep=1)
    assert "lines trimmed" in out[1]["content"]
    assert "Continue with task" in out[1]["content"]  # continuation preserved in tail
