"""Tests for Prism32 plugin self-extension helpers."""
import os
import sys
import tempfile

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

exec(open('prism32.py').read().split('if __name__')[0])


def test_plugin_cheat_sheet_is_pasteable_prompt():
    text = plugin_cheat_sheet_text()
    assert "Prism32 plugin" in text
    assert "def register(api):" in text
    assert "Return ONLY Python source code" in text
    assert "api.registry.register" in text


def test_extract_python_source_from_markdown_fence():
    raw = "Here is the plugin:\n```python\ndef register(api):\n    pass\n```"
    assert _extract_python_source(raw) == "def register(api):\n    pass\n"


def test_validate_plugin_source_requires_register():
    err = _validate_plugin_source("print('no register')\n", "test_plugin.py")
    assert err == "Plugin must define register(api)."


def test_extend_load_existing_plugin_registers_command():
    with tempfile.TemporaryDirectory() as d:
        plugin_path = os.path.join(d, "xtest_plugin.py")
        _safe_write(plugin_path, """
def register(api):
    def xtest(args_str, history, cmd_log):
        print("xtest ready " + args_str)
    api.registry.register("xtest-ext", xtest, description="test extension")
""".lstrip())

        history = [{"role": "system", "content": "system"}]
        result = extend_with_plugin(f"load {plugin_path}", history=history)

    assert result.startswith("[EXTENSION LOADED]")
    assert "/xtest-ext" in result
    assert registry.get("xtest-ext") is not None
    assert "xtest-ext" in history[0]["content"]
