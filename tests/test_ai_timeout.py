"""Tests for the AI request timeout (flex-model fix): Config.AI_TIMEOUT
default, ask_ai passing it to urlopen, config round-trip with a 60s floor,
and the timed-out network error pointing at /aitimeout."""
import sys, os, json, tempfile, unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))
exec(open(os.path.join(os.path.dirname(__file__), '..', 'prism32.py')).read().split("if __name__")[0])


class AITimeoutTestCase(unittest.TestCase):

    def setUp(self):
        self._saved_ai_timeout = Config.AI_TIMEOUT
        self._saved_timeout = Config.CMD_TIMEOUT
        self._saved_urlopen = globals()['urlopen_with_ssl']

    def tearDown(self):
        Config.AI_TIMEOUT = self._saved_ai_timeout
        Config.CMD_TIMEOUT = self._saved_timeout
        globals()['urlopen_with_ssl'] = self._saved_urlopen

    def test_default_is_one_hour(self):
        self.assertEqual(Config.AI_TIMEOUT, 3600)

    def test_ask_ai_passes_configured_timeout(self):
        seen = {}

        class FakeResp:
            def __enter__(self):
                return self
            def __exit__(self, *a):
                return False
            def read(self):
                return json.dumps({
                    'choices': [{'message': {'role': 'assistant',
                                            'content': 'ok'}}]}).encode()

        def fake_urlopen(req, timeout=None, **kw):
            seen['timeout'] = timeout
            return FakeResp()

        globals()['urlopen_with_ssl'] = fake_urlopen
        Config.AI_TIMEOUT = 1800
        out = ask_ai([{'role': 'user', 'content': 'hi'}], stream=False)
        self.assertEqual(out, 'ok')
        self.assertEqual(seen['timeout'], 1800)

    def test_config_roundtrip_persists_ai_timeout(self):
        tmp = tempfile.mkdtemp(prefix="prism32_aitimeout_test_")
        orig_file = Config.CONFIG_FILE
        try:
            Config.CONFIG_FILE = os.path.join(tmp, 'config.json')
            Config.AI_TIMEOUT = 7200
            Config.save_config()
            with open(Config.CONFIG_FILE) as f:
                data = json.load(f)
            self.assertEqual(data['ai_timeout'], 7200)
            Config.AI_TIMEOUT = 3600
            Config.load_config()
            self.assertEqual(Config.AI_TIMEOUT, 7200)
        finally:
            Config.CONFIG_FILE = orig_file
            import shutil
            shutil.rmtree(tmp, ignore_errors=True)

    def test_config_floor_rejects_tiny_values(self):
        tmp = tempfile.mkdtemp(prefix="prism32_aitimeout_test_")
        orig_file = Config.CONFIG_FILE
        try:
            Config.CONFIG_FILE = os.path.join(tmp, 'config.json')
            with open(Config.CONFIG_FILE, 'w') as f:
                json.dump({'ai_timeout': 5}, f)
            Config.AI_TIMEOUT = 3600
            Config.load_config()
            self.assertEqual(Config.AI_TIMEOUT, 60)
        finally:
            Config.CONFIG_FILE = orig_file
            import shutil
            shutil.rmtree(tmp, ignore_errors=True)

    def test_timeout_error_mentions_aitimeout(self):
        import urllib.error

        def fake_urlopen(req, timeout=None, **kw):
            raise urllib.error.URLError('timed out')

        globals()['urlopen_with_ssl'] = fake_urlopen
        out = ask_ai([{'role': 'user', 'content': 'hi'}], stream=False)
        self.assertTrue(out.startswith('[NETWORK ERROR]'))
        self.assertIn('/aitimeout', out)

    def test_help_lists_aitimeout(self):
        self.assertIn('/aitimeout', get_cmd_help())


if __name__ == '__main__':
    unittest.main()
