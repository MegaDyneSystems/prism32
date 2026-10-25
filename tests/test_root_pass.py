"""Tests for the root-password plumbing: $ROOT_PASS env injection into
execute blocks, the echo-pipe rewrite (system prompt's documented idiom),
and pty routing for su/sudo commands."""
import sys, os, unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))
exec(open(os.path.join(os.path.dirname(__file__), '..', 'prism32.py')).read().split("if __name__")[0])


class RootPassTestCase(unittest.TestCase):

    def setUp(self):
        self._saved_root_pass = Config.ROOT_PASS
        self._saved_pty = globals()['_pty_su_root']

    def tearDown(self):
        Config.ROOT_PASS = self._saved_root_pass
        globals()['_pty_su_root'] = self._saved_pty

    def test_root_pass_env_is_injected(self):
        Config.ROOT_PASS = 'test-pw-123'
        out = run_cmd('printf %s "$ROOT_PASS"')
        self.assertIn('test-pw-123', out)

    def test_root_pass_env_absent_when_unset(self):
        Config.ROOT_PASS = ''
        out = run_cmd('printf %s "${ROOT_PASS:-unset}"')
        self.assertIn('unset', out)

    def test_echo_pipe_sudo_is_routed_to_pty(self):
        Config.ROOT_PASS = 'test-pw-123'
        seen = {}

        def fake_pty_su_root(cmd, timeout=None):
            seen['cmd'] = cmd
            return 'ok'

        globals()['_pty_su_root'] = fake_pty_su_root
        out = run_cmd('echo "$ROOT_PASS" | sudo apt update')
        self.assertEqual(out, 'ok')
        self.assertEqual(seen['cmd'], 'sudo apt update')

    def test_echo_pipe_su_single_quotes_routed(self):
        Config.ROOT_PASS = 'test-pw-123'
        seen = {}

        def fake_pty_su_root(cmd, timeout=None):
            seen['cmd'] = cmd
            return 'ok'

        globals()['_pty_su_root'] = fake_pty_su_root
        run_cmd("echo '$ROOT_PASS' | su root -c 'id -u'")
        self.assertEqual(seen['cmd'], "su root -c 'id -u'")

    def test_echo_pipe_non_root_command_not_rewritten(self):
        Config.ROOT_PASS = 'test-pw-123'
        seen = {}

        def fake_pty_su_root(cmd, timeout=None):
            seen['cmd'] = cmd
            return 'should not happen'

        globals()['_pty_su_root'] = fake_pty_su_root
        out = run_cmd('echo "$ROOT_PASS" | tr a-z A-Z')
        # The pipe stays intact; $ROOT_PASS is real in the child env.
        self.assertNotIn('cmd', seen)
        self.assertIn('TEST-PW-123', out)

    def test_bare_su_routed_when_root_pass_set(self):
        Config.ROOT_PASS = 'test-pw-123'
        seen = {}

        def fake_pty_su_root(cmd, timeout=None):
            seen['cmd'] = cmd
            return 'ok'

        globals()['_pty_su_root'] = fake_pty_su_root
        run_cmd('su -c "id -u"')
        self.assertEqual(seen['cmd'], 'su -c "id -u"')


if __name__ == '__main__':
    unittest.main()
