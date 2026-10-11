"""Tests for the persistent prism32 home resolution ladder and /version
(verified against Synology DSM 7.1.1 — broken home, /volume1/homes/<user> real,
noexec volatile /tmp)."""
import sys, os, shutil, tempfile, unittest, subprocess

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))
exec(open(os.path.join(os.path.dirname(__file__), '..', 'prism32.py')).read().split("if __name__")[0])

_PRISM32 = os.path.join(os.path.dirname(__file__), '..', 'prism32.py')


class TestHomeResolution(unittest.TestCase):

    def setUp(self):
        self._tmp = tempfile.mkdtemp(prefix="prism32_home_test_")
        self._orig_expanduser = os.path.expanduser
        self._orig_xdg = os.environ.get('XDG_DATA_HOME')
        self._orig_v1 = _PRISM32_VOLUME1
        os.environ.pop('XDG_DATA_HOME', None)

    def tearDown(self):
        os.path.expanduser = self._orig_expanduser
        if self._orig_xdg is None:
            os.environ.pop('XDG_DATA_HOME', None)
        else:
            os.environ['XDG_DATA_HOME'] = self._orig_xdg
        globals()['_PRISM32_VOLUME1'] = self._orig_v1
        shutil.rmtree(self._tmp, ignore_errors=True)

    def _force_home(self, path):
        """Point expanduser('~') at an arbitrary path (valid or broken)."""
        def fake_expanduser(user):
            if user == '~':
                return path
            return self._orig_expanduser(user)
        os.path.expanduser = fake_expanduser

    def test_normal_home_wins(self):
        home = os.path.join(self._tmp, "home")
        os.makedirs(home)
        self._force_home(home)
        self.assertEqual(_resolve_prism32_home(), os.path.join(home, ".prism32"))
        self.assertTrue(os.path.isdir(os.path.join(home, ".prism32")))

    def test_broken_home_falls_to_volume1_homes(self):
        # DSM: /var/services/homes/<user> dangles, but /volume1/homes/<user> is real
        self._force_home("/var/services/homes/nosuchuser")
        globals()['_PRISM32_VOLUME1'] = self._tmp  # fake the NAS volume
        user = pwd_getpwname()
        homes = os.path.join(self._tmp, "homes", user)
        os.makedirs(homes)
        self.assertEqual(_resolve_prism32_home(), os.path.join(homes, ".prism32"))

    def test_broken_home_creates_volume1_homes_when_volume_exists(self):
        # /volume1 exists (isdir) but homes/<user> doesn't — the candidate is
        # still creatable, and must be preferred over volatile /tmp
        self._force_home("/var/services/homes/nosuchuser")
        globals()['_PRISM32_VOLUME1'] = self._tmp
        user = pwd_getpwname()
        self.assertEqual(_resolve_prism32_home(),
                         os.path.join(self._tmp, "homes", user, ".prism32"))
        self.assertTrue(os.path.isdir(os.path.join(self._tmp, "homes", user, ".prism32")))

    def test_xdg_before_volume1(self):
        self._force_home("/var/services/homes/nosuchuser")
        xdg = os.path.join(self._tmp, "xdg")
        os.makedirs(xdg)
        os.environ['XDG_DATA_HOME'] = xdg
        globals()['_PRISM32_VOLUME1'] = self._tmp  # even if the volume exists
        self.assertEqual(_resolve_prism32_home(), os.path.join(xdg, "prism32"))

    def test_all_persistent_candidates_fail_ends_in_tmp(self):
        # No usable home, no XDG, and /volume1 absent → volatile last resort
        self._force_home("/var/services/homes/nosuchuser")
        globals()['_PRISM32_VOLUME1'] = os.path.join(self._tmp, "novolume")
        self.assertEqual(_resolve_prism32_home(), "/tmp/prism32")

    def test_candidates_ladder_order(self):
        self._force_home("/var/services/homes/nosuchuser")
        os.environ.pop('XDG_DATA_HOME', None)
        globals()['_PRISM32_VOLUME1'] = self._tmp
        user = pwd_getpwname()
        cands = _prism32_home_candidates()
        self.assertEqual(cands[0], "/var/services/homes/nosuchuser/.prism32")
        self.assertEqual(cands[1], os.path.join(self._tmp, "homes", user, ".prism32"))
        self.assertEqual(cands[2], os.path.join(self._tmp, user, ".prism32"))


def pwd_getpwname():
    import pwd
    return pwd.getpwuid(os.getuid()).pw_name


class TestVersionCLI(unittest.TestCase):

    def test_dash_v_alias(self):
        r = subprocess.run([sys.executable, _PRISM32, "-v"],
                           capture_output=True, text=True, timeout=60)
        self.assertEqual(r.returncode, 0)
        self.assertIn("MegaDyne", r.stdout)

    def test_dash_upper_v(self):
        r = subprocess.run([sys.executable, _PRISM32, "-V"],
                           capture_output=True, text=True, timeout=60)
        self.assertEqual(r.returncode, 0)
        self.assertIn("MegaDyne", r.stdout)


if __name__ == '__main__':
    unittest.main()
