"""Hermetic test environment.

pytest imports conftest.py before any test module, so setting HOME here
guarantees that both `import prism32` and the exec-based test files
resolve ~/.prism32 (config.json, sessions, memory, logs) inside a throwaway
sandbox. Without this, Config.save_config() calls in tests overwrite the
developer's real config with factory defaults.
"""
import os
import tempfile

_tmp_home = tempfile.mkdtemp(prefix="prism32-tests-")
os.environ["HOME"] = _tmp_home
