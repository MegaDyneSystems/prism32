"""Tests for Prism32 harness, startup memory, and evolve support."""
import os
import sys
import tempfile

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

exec(open('prism32.py').read().split('if __name__')[0])


def test_startup_memory_is_editable_markdown():
    """Startup memory should be a readable Markdown file with editable sections."""
    global STARTUP_MEMORY_FILE, MEMORY_FILE
    old_startup = STARTUP_MEMORY_FILE
    old_memory = MEMORY_FILE
    with tempfile.TemporaryDirectory() as d:
        STARTUP_MEMORY_FILE = os.path.join(d, "startup_memory.md")
        MEMORY_FILE = os.path.join(d, "memory.json")
        path = ensure_startup_memory(refresh=True)
        content = read_startup_memory()
        assert path == STARTUP_MEMORY_FILE
        assert os.path.exists(path)
        assert "# Prism32 Startup Memory" in content
        assert "Hardware Tips" in content
        assert STARTUP_AUTO_START in content
    STARTUP_MEMORY_FILE = old_startup
    MEMORY_FILE = old_memory


def test_harness_scan_save_load_shape():
    """Harness scans should save/load a stable JSON shape."""
    global HARNESS_FILE
    old_harness = HARNESS_FILE
    with tempfile.TemporaryDirectory() as d:
        HARNESS_FILE = os.path.join(d, "harnesses.json")
        data = detect_harnesses(probe_versions=False)
        save_harnesses(data)
        loaded = load_harnesses()
        assert loaded["version"] == 1
        assert "installed" in loaded
        assert "missing" in loaded
        assert isinstance(loaded["installed"], list)
    HARNESS_FILE = old_harness


def test_evolve_files_and_plugin_template():
    """Evolve setup should create docs, baseline, tool scan, and plugin templates."""
    global EVOLVE_DIR, EVOLVE_DOC_FILE, EVOLVE_TOOL_FILE
    global EVOLVE_BASELINE_DIR, EVOLVE_BASELINE_FILE, EVOLVE_BASELINE_CONFIG_FILE
    global EVOLVE_TEMP_PLUGIN_DIR
    old_vals = (EVOLVE_DIR, EVOLVE_DOC_FILE, EVOLVE_TOOL_FILE,
                EVOLVE_BASELINE_DIR, EVOLVE_BASELINE_FILE,
                EVOLVE_BASELINE_CONFIG_FILE, EVOLVE_TEMP_PLUGIN_DIR)
    with tempfile.TemporaryDirectory() as d:
        EVOLVE_DIR = d
        EVOLVE_DOC_FILE = os.path.join(d, "evolve.md")
        EVOLVE_TOOL_FILE = os.path.join(d, "tools.json")
        EVOLVE_BASELINE_DIR = os.path.join(d, "baseline")
        EVOLVE_BASELINE_FILE = os.path.join(EVOLVE_BASELINE_DIR, "prism32.py")
        EVOLVE_BASELINE_CONFIG_FILE = os.path.join(EVOLVE_BASELINE_DIR, "config.default.json")
        EVOLVE_TEMP_PLUGIN_DIR = os.path.join(d, "tmp_plugins")
        ensure_evolve_files(force_baseline=True, refresh_tools=True)
        assert os.path.exists(EVOLVE_DOC_FILE)
        assert os.path.exists(EVOLVE_BASELINE_FILE)
        assert os.path.exists(EVOLVE_TOOL_FILE)
        assert "Plugin" in _safe_read(EVOLVE_DOC_FILE)
        plugin_path = write_evolve_plugin("temp", "My Plugin")
        assert os.path.exists(plugin_path)
        assert plugin_path.startswith(EVOLVE_TEMP_PLUGIN_DIR)
    (EVOLVE_DIR, EVOLVE_DOC_FILE, EVOLVE_TOOL_FILE,
     EVOLVE_BASELINE_DIR, EVOLVE_BASELINE_FILE,
     EVOLVE_BASELINE_CONFIG_FILE, EVOLVE_TEMP_PLUGIN_DIR) = old_vals
