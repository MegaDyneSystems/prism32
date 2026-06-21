"""Tests for cross-architecture CPU detection."""
import builtins
import io
import platform

import prism32

_CPUINFO_SAMPLES = {
    "mips_24kc_openwrt": """system type             : Qualcomm Atheros QCA9533 ver 2 rev 0
machine                 : TP-Link TL-WR841N/ND v9
processor               : 0
cpu model               : MIPS 24Kc V7.4
BogoMIPS                : 366.18
isa                     : mips1 mips2 mips32r1 mips32r2
""",
    "mips_24kec_mediatek": """system type             : MediaTek MT7628AN ver:1 eco:2
processor               : 0
cpu model               : MIPS 24KEc V5.0
BogoMIPS                : 385.84
""",
    "mips_1004kc_mt7621": """system type             : MediaTek MT7621 ver:1 eco:3
processor               : 0
cpu model               : MIPS 1004Kc V2.15
""",
    "riscv_sifive": """processor       : 0
hart            : 0
isa             : rv64imafdc
mmu             : sv39
uarch           : sifive,u74-mc
""",
    "powerpc_power9": """processor       : 0
cpu             : POWER9 (raw), altivec supported
clock           : 2160.000000MHz
revision        : 2.2 (pvr 004e 1202)
""",
    "sparc_ultrasparc": """CPU            : UltraSparc T1 (Niagara)
fpu           : UltraSparc T1 integrated FPU
type          : sun4v
ncpus probed  : 16
""",
    "s390x_ibmz": """vendor_id       : IBM/S390
# processors    : 2
bogomips per cpu: 3241.00
features        : esan3 zarch stfle
""",
    "x86_intel": """processor       : 0
vendor_id       : GenuineIntel
model name      : Intel(R) Core(TM) i7-7700HQ CPU @ 2.80GHz
stepping        : 4
""",
    "arm_android": """processor       : 0
model name      : ARMv7 Processor rev 1 (v7l)
BogoMIPS        : 1484.78
Hardware        : Qualcomm Snapdragon 810
""",
}


def _patch_open_with_cpuinfo(cpuinfo_text):
    real_open = builtins.open

    def fake_open(path, *a, **kw):
        if path == "/proc/cpuinfo":
            return io.StringIO(cpuinfo_text)
        return real_open(path, *a, **kw)

    return real_open, fake_open


def test_humanize_arch():
    assert prism32.Platform._humanize_arch("mips") == "MIPS"
    assert prism32.Platform._humanize_arch("mipsel") == "MIPS (LE)"
    assert prism32.Platform._humanize_arch("mips64") == "MIPS64"
    assert prism32.Platform._humanize_arch("riscv64") == "RISC-V 64"
    assert prism32.Platform._humanize_arch("ppc") == "PowerPC"
    assert prism32.Platform._humanize_arch("aarch64") == "ARM64"
    assert prism32.Platform._humanize_arch("x86_64") == "x86_64"
    assert prism32.Platform._humanize_arch("s390x") == "IBM Z"


def test_mips_24kc_openwrt():
    real_open, fake_open = _patch_open_with_cpuinfo(_CPUINFO_SAMPLES["mips_24kc_openwrt"])
    try:
        builtins.open = fake_open
        cpu = prism32.Platform._get_cpu_linux()
    finally:
        builtins.open = real_open
    assert "MIPS 24Kc" in cpu
    assert "QCA9533" in cpu or "Qualcomm" in cpu


def test_mips_24kec_mediatek():
    real_open, fake_open = _patch_open_with_cpuinfo(_CPUINFO_SAMPLES["mips_24kec_mediatek"])
    try:
        builtins.open = fake_open
        cpu = prism32.Platform._get_cpu_linux()
    finally:
        builtins.open = real_open
    assert "MIPS 24KEc" in cpu
    assert "MT7628" in cpu


def test_mips_1004kc_mt7621():
    real_open, fake_open = _patch_open_with_cpuinfo(_CPUINFO_SAMPLES["mips_1004kc_mt7621"])
    try:
        builtins.open = fake_open
        cpu = prism32.Platform._get_cpu_linux()
    finally:
        builtins.open = real_open
    assert "1004Kc" in cpu
    assert "MT7621" in cpu


def test_riscv():
    real_open, fake_open = _patch_open_with_cpuinfo(_CPUINFO_SAMPLES["riscv_sifive"])
    try:
        builtins.open = fake_open
        cpu = prism32.Platform._get_cpu_linux()
    finally:
        builtins.open = real_open
    assert "sifive" in cpu.lower() or "risc-v" in cpu.lower()


def test_powerpc():
    real_open, fake_open = _patch_open_with_cpuinfo(_CPUINFO_SAMPLES["powerpc_power9"])
    try:
        builtins.open = fake_open
        cpu = prism32.Platform._get_cpu_linux()
    finally:
        builtins.open = real_open
    assert "POWER9" in cpu


def test_sparc():
    real_open, fake_open = _patch_open_with_cpuinfo(_CPUINFO_SAMPLES["sparc_ultrasparc"])
    try:
        builtins.open = fake_open
        cpu = prism32.Platform._get_cpu_linux()
    finally:
        builtins.open = real_open
    assert "UltraSparc" in cpu


def test_s390x():
    real_open, fake_open = _patch_open_with_cpuinfo(_CPUINFO_SAMPLES["s390x_ibmz"])
    try:
        builtins.open = fake_open
        cpu = prism32.Platform._get_cpu_linux()
    finally:
        builtins.open = real_open
    assert "IBM" in cpu


def test_x86_still_works():
    real_open, fake_open = _patch_open_with_cpuinfo(_CPUINFO_SAMPLES["x86_intel"])
    try:
        builtins.open = fake_open
        cpu = prism32.Platform._get_cpu_linux()
    finally:
        builtins.open = real_open
    assert "Intel" in cpu


def test_arm_android():
    real_open, fake_open = _patch_open_with_cpuinfo(_CPUINFO_SAMPLES["arm_android"])
    try:
        builtins.open = fake_open
        cpu = prism32.Platform._get_cpu_linux()
    finally:
        builtins.open = real_open
    assert "ARMv7" in cpu
