"""Tests for the NetBSD 10.1 bug-test round: sysctl absolute-path probing
(NetBSD keeps sysctl in /sbin, absent from non-login PATHs), bare-epoch
kern.boottime parsing, BSD CPU arch-ladder fallback, and the get_os()
platform name (was generic "BSD")."""
import sys, os, time, unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))
exec(open(os.path.join(os.path.dirname(__file__), '..', 'prism32.py')).read().split("if __name__")[0])


class NetBSDPlatformTestCase(unittest.TestCase):
    """Simulate NetBSD: BSD platform flags, sysctl off-PATH, bare boottime."""

    def setUp(self):
        self._saved = {
            'LINUX': Platform.LINUX, 'MACOS': Platform.MACOS,
            'WINDOWS': Platform.WINDOWS, 'BSD': Platform.BSD,
            'SYSCTL': Platform._SYSCTL_EXE,
            'which': shutil.which,
            'run_cmd': Platform._run_cmd,
        }

    def tearDown(self):
        Platform.LINUX = self._saved['LINUX']
        Platform.MACOS = self._saved['MACOS']
        Platform.WINDOWS = self._saved['WINDOWS']
        Platform.BSD = self._saved['BSD']
        Platform._SYSCTL_EXE = self._saved['SYSCTL']
        shutil.which = self._saved['which']
        Platform._run_cmd = staticmethod(self._saved['run_cmd'])
    def _make_netbsd(self, sysctl_map=None, sysctl_on_path=False):
        Platform.LINUX = False
        Platform.MACOS = False
        Platform.WINDOWS = False
        Platform.BSD = True
        Platform._SYSCTL_EXE = None
        real_which = self._saved['which']

        def fake_which(cmd):
            if cmd == 'sysctl':
                return '/usr/bin/sysctl' if sysctl_on_path else None
            if cmd in ('/sbin/sysctl', '/usr/sbin/sysctl'):
                return cmd if sysctl_map is not None else None
            return real_which(cmd)

        shutil.which = fake_which
        if sysctl_map is not None:
            Platform._run_cmd = staticmethod(
                lambda args, **kw: sysctl_map.get(args[-1], ""))

    def test_sysctl_found_via_sbin_absolute_path(self):
        # NetBSD: bare `sysctl` not on PATH, but /sbin/sysctl exists
        self._make_netbsd(sysctl_map={'hw.physmem': '535293952'})
        self.assertEqual(Platform._find_sysctl(), '/sbin/sysctl')
        self.assertEqual(Platform._sysctl('hw.physmem'), '535293952')
        self.assertEqual(Platform.get_ram(), 510)  # 535293952 // 1024**2

    def test_sysctl_nowhere_returns_empty(self):
        self._make_netbsd(sysctl_map=None)
        self.assertEqual(Platform._find_sysctl(), '')
        self.assertEqual(Platform._sysctl('hw.physmem'), '')

    def test_sysctl_on_path_preferred(self):
        self._make_netbsd(sysctl_map={'hw.model': 'Intel 686-class'}, sysctl_on_path=True)
        self.assertEqual(Platform._find_sysctl(), 'sysctl')
        self.assertEqual(Platform.get_cpu(), 'Intel 686-class')

    def test_get_cpu_falls_back_to_arch_ladder(self):
        # sysctl unreachable → humanized arch, not "Unknown CPU"
        self._make_netbsd(sysctl_map=None)
        cpu = Platform.get_cpu()
        self.assertNotEqual(cpu, "Unknown CPU")
        self.assertEqual(cpu, Platform._humanize_arch(platform.machine()))

    def test_get_uptime_netbsd_bare_epoch(self):
        # NetBSD prints a bare epoch; FreeBSD/macOS print { sec = ... }
        boot = int(time.time()) - 7200  # 2h uptime
        self._make_netbsd(sysctl_map={'kern.boottime': str(boot)})
        up = Platform.get_uptime()
        self.assertNotEqual(up, "N/A")
        self.assertIn("h", up)

    def test_get_uptime_struct_format_still_works(self):
        boot = int(time.time()) - 90
        self._make_netbsd(sysctl_map={'kern.boottime': '{ sec = %d, usec = 0 } Tue Oct 11...' % boot})
        self.assertNotEqual(Platform.get_uptime(), "N/A")

    def test_get_system_returns_platform_system_not_generic_bsd(self):
        self._make_netbsd(sysctl_map=None)
        real_system = platform.system
        platform.system = lambda: "NetBSD"
        try:
            self.assertEqual(Platform.get_system(), "NetBSD")
        finally:
            platform.system = real_system


if __name__ == '__main__':
    unittest.main()
