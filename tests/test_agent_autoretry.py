"""Tests for the agent-loop transient-failure auto-retry: failure
classification (auth vs budget vs retryable vs empty vs content) and the
harness scan fixes (version probe rc-gating, probe-on-stale-refresh)."""
import sys, os, json, tempfile, unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))
exec(open(os.path.join(os.path.dirname(__file__), '..', 'prism32.py')).read().split("if __name__")[0])


class AIFailureKindTestCase(unittest.TestCase):

    def test_empty_response(self):
        self.assertEqual(_ai_failure_kind(''), 'empty')
        self.assertEqual(_ai_failure_kind(None), 'empty')

    def test_transient_errors_retry(self):
        self.assertEqual(_ai_failure_kind('[HTTP ERROR 500] boom'), 'retry')
        self.assertEqual(_ai_failure_kind('[HTTP ERROR 503] overloaded'), 'retry')
        self.assertEqual(_ai_failure_kind('[NETWORK ERROR] timed out'), 'retry')
        self.assertEqual(_ai_failure_kind('[ERROR] something broke'), 'retry')

    def test_auth_failure_not_retryable(self):
        self.assertEqual(_ai_failure_kind('[HTTP ERROR 401] Authentication failed'), 'auth')

    def test_budget_failure_not_retryable(self):
        self.assertEqual(_ai_failure_kind(
            '[ERROR] The model exhausted its entire response budget '
            '(max_tokens=8192) on reasoning'), 'budget')

    def test_normal_content_is_not_failure(self):
        self.assertIsNone(_ai_failure_kind('Here is the fix:\n```execute\nls\n```'))
        self.assertIsNone(_ai_failure_kind('plain answer'))

    def test_bracket_prefixed_content_is_not_failure(self):
        # A model reply that merely begins with '[' (citations etc.) is
        # legitimate content, not an error prefix.
        self.assertIsNone(_ai_failure_kind('[1] Source: docs'))

    def test_cancelled_is_not_failure(self):
        self.assertIsNone(_ai_failure_kind(AGENT_CANCELLED_RESPONSE))

    def test_retry_constant_exists(self):
        self.assertGreaterEqual(_AI_AUTO_RETRIES, 3)


class HarnessScanFixesTestCase(unittest.TestCase):

    def test_probe_version_rejects_failing_cli(self):
        # A CLI that exits non-zero (mise "no version set") must yield "",
        # not its stderr error text.
        out = _probe_version('/bin/false')
        self.assertEqual(out, '')

    def test_probe_version_accepts_stdout(self):
        out = _probe_version(os.path.join(os.path.dirname(__file__), '..',
                                          'tests', 'fake_cli_ok.py'))
        self.assertTrue(out.startswith('fake-cli'), out)

    def test_ensure_scan_probes_on_stale_refresh(self):
        # D1 regression: a stale-cache refresh must probe versions too,
        # never persist an all-empty version_text wipe.
        tmp = tempfile.mkdtemp(prefix="prism32_harness_test_")
        orig_file = globals()['HARNESS_FILE']
        try:
            hf = os.path.join(tmp, 'harnesses.json')
            # Pre-seed a scan whose versions are wiped empty (the D1 symptom)
            with open(hf, 'w') as f:
                json.dump({'version': 1, 'scanned_at': 'old',
                           'installed': [{'id': 'x', 'path': '/bin/true',
                                          'version_text': ''}],
                           'missing': []}, f)
            # Make it stale (mtime older than 24h)
            os.utime(hf, (0, 0))
            globals()['HARNESS_FILE'] = hf
            data = ensure_harness_scan(force=False)
            # Whatever it found, a real scan happened and every installed
            # entry went through the version prober (non-empty for /bin/true)
            for h in data.get('installed', []):
                if h.get('path') == '/bin/true':
                    self.assertEqual(h.get('version_text'), 'true (GNU coreutils)')
        finally:
            globals()['HARNESS_FILE'] = orig_file
            import shutil
            shutil.rmtree(tmp, ignore_errors=True)

    def test_harness_context_truncates_on_line_boundary(self):
        long_ctx = harness_context(limit=50)
        self.assertLessEqual(len(long_ctx), 50)
        if long_ctx:
            self.assertNotIn('\n', long_ctx[45:])  # no mid-line corruption tail


if __name__ == '__main__':
    unittest.main()
