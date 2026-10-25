"""Tests for hot-reload update plumbing: the re-exec argv builder and the
--resume-session session restore data path."""
import sys, os, json, tempfile, unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))
exec(open(os.path.join(os.path.dirname(__file__), '..', 'prism32.py')).read().split("if __name__")[0])


class HotReloadTestCase(unittest.TestCase):

    def test_argv_builder_passthrough_and_resume(self):
        argv = _hot_reload_argv('/runtime/prism32.py', 'sess-42',
                                ['--api-key', 'k', '--model', 'm'])
        self.assertEqual(argv[0], sys.executable)
        self.assertEqual(argv[1], '/runtime/prism32.py')
        self.assertEqual(argv[2:], ['--api-key', 'k', '--model', 'm',
                                     '--resume-session', 'sess-42'])

    def test_argv_builder_strips_prior_resume_pair(self):
        argv = _hot_reload_argv('/r.py', 'new-id',
                                ['--resume-session', 'old-id', '--model', 'm'])
        self.assertNotIn('old-id', argv)
        self.assertEqual(argv[-2:], ['--resume-session', 'new-id'])

    def test_argv_builder_no_session(self):
        argv = _hot_reload_argv('/r.py', None, ['--model', 'm'])
        self.assertNotIn('--resume-session', argv)

    def test_resume_session_round_trip(self):
        tmp = tempfile.mkdtemp(prefix="prism32_hotreload_test_")
        orig_dir = Config.SESSION_DIR
        try:
            Config.SESSION_DIR = tmp
            hist = [
                {'role': 'system', 'content': 'old system prompt'},
                {'role': 'user', 'content': 'hello'},
                {'role': 'assistant', 'content': 'hi there'},
            ]
            path = save_session('hot-test-1', hist, ['ls -la'])
            self.assertTrue(os.path.exists(path))
            data = load_session('hot-test-1')
            self.assertIsNotNone(data)
            self.assertEqual(data['id'], 'hot-test-1')
            self.assertEqual(len(data['history']), 3)
            self.assertEqual(data['cmd_log'], ['ls -la'])
        finally:
            Config.SESSION_DIR = orig_dir
            import shutil
            shutil.rmtree(tmp, ignore_errors=True)

    def test_resume_arg_declared(self):
        with open(os.path.join(os.path.dirname(__file__), '..', 'prism32.py')) as f:
            src = f.read()
        self.assertIn('"--resume-session"', src)
        self.assertIn('_hot_reload', src)


if __name__ == '__main__':
    unittest.main()
