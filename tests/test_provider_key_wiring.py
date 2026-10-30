"""Tests for provider API-key wiring: the 401-no-key-sent bug where
/providers.<name>.api_key never reached the request path because the
top-level api_key was empty (persisted as "" by save_config) and the
load-time registry lift was skipped."""
import sys, os, json, tempfile, unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))
exec(open(os.path.join(os.path.dirname(__file__), '..', 'prism32.py')).read().split("if __name__")[0])


class ProviderKeyWiringTestCase(unittest.TestCase):

    def setUp(self):
        self._tmp = tempfile.mkdtemp(prefix="prism32_keywire_test_")
        self._orig_file = Config.CONFIG_FILE
        self._orig_provider = Config.PROVIDER
        self._orig_key = Config.API_KEY
        self._orig_model = Config.MODEL
        self._orig_registry = {k: dict(v) for k, v in PROVIDER_REGISTRY.items()}
        Config.CONFIG_FILE = os.path.join(self._tmp, 'config.json')

    def tearDown(self):
        Config.CONFIG_FILE = self._orig_file
        Config.PROVIDER = self._orig_provider
        Config.API_KEY = self._orig_key
        Config.MODEL = self._orig_model
        PROVIDER_REGISTRY.clear()
        PROVIDER_REGISTRY.update(self._orig_registry)
        import shutil
        shutil.rmtree(self._tmp, ignore_errors=True)

    def _write_config(self, cfg):
        with open(Config.CONFIG_FILE, 'w') as f:
            json.dump(cfg, f)

    def test_empty_toplevel_key_lifts_provider_key_on_load(self):
        # The user bug: key set via /provider key <name> <key>, but the
        # top-level api_key persisted as "" shadowed it on every boot.
        self._write_config({
            "provider": "neuralwatt",
            "model": "kimi-k3",
            "api_base": "https://api.neuralwatt.com/v1",
            "api_key": "",
            "providers": {
                "neuralwatt": {
                    "api_base": "https://api.neuralwatt.com/v1",
                    "model": "glm-5.2",
                    "api_key": "sk-provider-key-123",
                }
            },
        })
        Config.API_KEY = ""
        Config.load_config()
        self.assertEqual(Config.API_KEY, "sk-provider-key-123")

    def test_nonempty_toplevel_key_wins(self):
        self._write_config({
            "provider": "neuralwatt",
            "api_key": "sk-top-level-key",
            "providers": {
                "neuralwatt": {"api_base": "https://x", "api_key": "sk-provider-key"}
            },
        })
        Config.API_KEY = ""
        Config.load_config()
        self.assertEqual(Config.API_KEY, "sk-top-level-key")

    def test_set_provider_entry_wires_active_provider_key(self):
        self._write_config({
            "provider": "neuralwatt",
            "api_key": "",
            "providers": {"neuralwatt": {"api_base": "https://x"}},
        })
        Config.PROVIDER = "neuralwatt"
        Config.API_KEY = ""
        Config.load_config()
        ok = Config.set_provider_entry("neuralwatt", api_key="sk-fresh-key")
        self.assertTrue(ok)
        self.assertEqual(Config.API_KEY, "sk-fresh-key")
        with open(Config.CONFIG_FILE) as f:
            disk = json.load(f)
        self.assertEqual(disk.get("api_key"), "sk-fresh-key")
        self.assertEqual(disk["providers"]["neuralwatt"]["api_key"], "sk-fresh-key")

    def test_set_provider_entry_nonactive_keeps_active_key(self):
        self._write_config({
            "provider": "neuralwatt",
            "api_key": "sk-active",
            "providers": {},
        })
        Config.PROVIDER = "neuralwatt"
        Config.API_KEY = "sk-active"
        Config.load_config()
        Config.set_provider_entry("otherprov", api_key="sk-other")
        self.assertEqual(Config.API_KEY, "sk-active")

    def test_apply_model_selection_same_provider_lifts_key(self):
        self._write_config({
            "provider": "neuralwatt",
            "model": "kimi-k3",
            "api_key": "",
            "providers": {
                "neuralwatt": {"api_base": "https://x", "model": "kimi-k3",
                               "api_key": "sk-registry-key"}
            },
        })
        Config.PROVIDER = "neuralwatt"
        Config.MODEL = "kimi-k3"
        Config.API_KEY = ""
        Config.load_config()
        PROVIDER_REGISTRY["neuralwatt"]["default_key"] = "sk-registry-key"
        Config.API_KEY = ""  # simulate the pre-fix runtime state
        _apply_model_selection("neuralwatt", "kimi-k3", "main")
        self.assertEqual(Config.API_KEY, "sk-registry-key")


if __name__ == '__main__':
    unittest.main()
