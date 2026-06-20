#!/usr/bin/env python3
"""Build a Prism32 floppy disk installer image.
FAT12 filesystem - cross-platform, works on Linux/macOS/BSD.
Can be written to USB floppy drives, SD cards, or USB flash drives.

Usage:
  python3 make_floppy.py                    # build image to /tmp
  python3 make_floppy.py --write             # build + write to detected device
  python3 make_floppy.py --write /dev/sdc    # build + write to specific device
  python3 make_floppy.py -o floppy.img       # build to custom path
  python3 make_floppy.py --format 525-hd     # 5.25" high-density (1.2MB)
  python3 make_floppy.py --format 35-hd      # 3.5" high-density (1.44MB, default)
"""
import os, sys, struct, time, subprocess, platform

# Auto-detect project directory
PRISM32_DIR = os.path.dirname(os.path.abspath(__file__))
OUTPUT_IMG = os.path.join("/tmp", "prism32_floppy.img")

# Floppy format presets
FLOPPY_FORMATS = {
    "525-double": {   # 5.25" 360K DD
        "total_sectors": 720,
        "sectors_per_track": 9,
        "num_heads": 2,
        "sectors_per_fat": 3,
        "root_entries": 112,
        "media_byte": 0xFD,
        "label": "525DD",
    },
    "525-hd": {       # 5.25" 1.2M HD
        "total_sectors": 2400,
        "sectors_per_track": 15,
        "num_heads": 2,
        "sectors_per_fat": 7,
        "root_entries": 224,
        "media_byte": 0xF9,
        "label": "525HD",
    },
    "35-hd": {        # 3.5" 1.44M HD (default)
        "total_sectors": 2880,
        "sectors_per_track": 18,
        "num_heads": 2,
        "sectors_per_fat": 9,
        "root_entries": 224,
        "media_byte": 0xF0,
        "label": "35HD",
    },
}

BYTES_PER_SECTOR = 512
SECTORS_PER_CLUSTER = 1
RESERVED_SECTORS = 1
NUM_FATS = 2
FAT12_EOC = 0xFFF

# Will be set by build()
fmt = None
TOTAL_SECTORS = None
SECTORS_PER_FAT = None
ROOT_ENTRIES = None
SECTORS_PER_TRACK = None
NUM_HEADS = None
MEDIA_BYTE = None
VOLUME_LABEL = None
root_dir_sectors = None
data_start_sector = None
total_data_sectors = None
total_clusters = None

FILES = [
    ("prism32.py",  os.path.join(PRISM32_DIR, "prism32.py")),
    ("install.sh",  os.path.join(PRISM32_DIR, "install.sh")),
    ("README.md",   os.path.join(PRISM32_DIR, "README.md")),
    ("LICENSE",     os.path.join(PRISM32_DIR, "LICENSE")),
    ("pyproject.toml", os.path.join(PRISM32_DIR, "pyproject.toml")),
]

# Bundle user configuration from ~/.prism32/ if available
_RUNTIME_DIR = os.path.join(os.path.expanduser("~"), ".prism32")
_USER_BUNDLE_FILES = [
    ("CONFIG.JSON",    os.path.join(_RUNTIME_DIR, "config.json")),
    ("MEMORY.JSON",    os.path.join(_RUNTIME_DIR, "memory.json")),
    ("STARTUP.MD",     os.path.join(_RUNTIME_DIR, "startup_memory.md")),
    ("SOUL.MD",        os.path.join(_RUNTIME_DIR, "soul.md")),
    ("HARNESSES.JSON", os.path.join(_RUNTIME_DIR, "harnesses.json")),
    ("PROMPTSHARD.MD", os.path.join(_RUNTIME_DIR, "promptshard.md")),
]

# Bundle plugins from repo and user dir
_PLUGIN_DIRS = [
    os.path.join(PRISM32_DIR, "plugins"),
    os.path.join(_RUNTIME_DIR, "plugins"),
]

# Autorun script stored as a file on the floppy
AUTORUN = b"""#!/bin/sh
echo ""
echo "  ==========================================="
echo "   Prism32 v6.8 - MegaDyne Systems"
echo "   Portable Floppy Installer"
echo "  ==========================================="
echo ""
echo "  Installing Prism32 to this system..."
echo ""
SRC="$(dirname "$0")"
# Pre-copy user config so install.sh can merge instead of prompting
mkdir -p ~/.prism32/plugins ~/.prism32/sessions
for f in CONFIG.JSON MEMORY.JSON STARTUP.MD SOUL.MD HARNESSES.JSON PROMPTSHARD.MD; do
    [ -f "$SRC/$f" ] && cp "$SRC/$f" ~/.prism32/$(echo "$f" | tr 'A-Z' 'a-z') 2>/dev/null
done
# Copy bundled plugins
for p in "$SRC/"*.PY; do
    [ -f "$p" ] && [ "$(basename "$p")" != "PRISM32.PY" ] && cp "$p" ~/.prism32/plugins/ 2>/dev/null
done
if [ -f install.sh ]; then
    sh install.sh
else
    mkdir -p ~/.local/bin
    cp "$SRC/prism32.py" ~/.prism32/prism32.py
    cat > ~/.local/bin/prism32 << 'WRAPPER'
#!/bin/sh
exec python3 "$HOME/.prism32/prism32.py" "$@"
WRAPPER
    chmod +x ~/.local/bin/prism32
    echo "  Installed to ~/.prism32/prism32.py"
    echo "  Run: ~/.local/bin/prism32"
fi
echo ""
echo "  Run 'prism32' to start."
echo ""
"""


def encode_dir_entry(name, ext, attrs, size, first_cluster, ts):
    name = name.ljust(8)[:8].upper().encode()
    ext = ext.ljust(3)[:3].upper().encode()
    tm = time.gmtime(ts)
    date = ((tm.tm_year - 1980) << 9) | (tm.tm_mon << 5) | tm.tm_mday
    time_bin = (tm.tm_hour << 11) | (tm.tm_min << 5) | (tm.tm_sec // 2)
    ent = bytearray(32)
    ent[0:8] = name
    ent[8:11] = ext
    ent[11] = attrs
    struct.pack_into('<H', ent, 22, time_bin)
    struct.pack_into('<H', ent, 24, date)
    struct.pack_into('<H', ent, 26, first_cluster)
    struct.pack_into('<I', ent, 28, size)
    return bytes(ent)


def build_boot_sector():
    global MEDIA_BYTE
    bs = bytearray(512)
    bs[0:3] = b'\xeb\x3c\x90'
    bs[3:11] = b'PRISM32 '
    struct.pack_into('<H', bs, 11, BYTES_PER_SECTOR)
    bs[13] = SECTORS_PER_CLUSTER
    struct.pack_into('<H', bs, 14, RESERVED_SECTORS)
    bs[16] = NUM_FATS
    struct.pack_into('<H', bs, 17, ROOT_ENTRIES)
    struct.pack_into('<H', bs, 19, TOTAL_SECTORS)
    bs[21] = MEDIA_BYTE
    struct.pack_into('<H', bs, 22, SECTORS_PER_FAT)
    struct.pack_into('<H', bs, 24, SECTORS_PER_TRACK)
    struct.pack_into('<H', bs, 26, NUM_HEADS)
    struct.pack_into('<I', bs, 28, 0)
    struct.pack_into('<I', bs, 32, 0)
    bs[36] = 0x00
    bs[37] = 0x00
    bs[38] = 0x29
    struct.pack_into('<I', bs, 39, int(time.time()) & 0xFFFFFFFF)
    bs[43:54] = (VOLUME_LABEL + "       ")[:11].encode()
    bs[54:62] = b'FAT12   '
    msg = b'Prism32 v6.8 by MegaDyne Systems' + b'\x00' * 4
    bs[62:62+len(msg)] = msg
    bs[510:512] = b'\x55\xAA'
    return bytes(bs)


def build_fat(chain, fat_sectors, total_clusters, media_byte):
    """Build FAT12 table bytes from a cluster chain list."""
    fat = bytearray(fat_sectors * BYTES_PER_SECTOR)
    entries_med = (media_byte & 0xFF) | 0xF00
    entries = [entries_med, 0xFFF]
    entries.extend(chain)
    total = len(entries)

    off = 0
    i = 0
    while i < total:
        e1 = entries[i] & 0xFFF
        if i + 1 < total:
            e2 = entries[i + 1] & 0xFFF
            fat[off] = e1 & 0xFF
            fat[off + 1] = ((e1 >> 8) & 0x0F) | ((e2 & 0x0F) << 4)
            fat[off + 2] = (e2 >> 4) & 0xFF
            off += 3
            i += 2
        else:
            fat[off] = e1 & 0xFF
            fat[off + 1] = (e1 >> 8) & 0x0F
            i += 1
    return bytes(fat)


def build(fmt_name="35-hd"):
    global TOTAL_SECTORS, SECTORS_PER_FAT, ROOT_ENTRIES, SECTORS_PER_TRACK
    global NUM_HEADS, MEDIA_BYTE, VOLUME_LABEL, root_dir_sectors
    global data_start_sector, total_data_sectors, total_clusters

    fmt = FLOPPY_FORMATS[fmt_name]
    TOTAL_SECTORS = fmt["total_sectors"]
    SECTORS_PER_FAT = fmt["sectors_per_fat"]
    SECTORS_PER_TRACK = fmt["sectors_per_track"]
    NUM_HEADS = fmt["num_heads"]
    ROOT_ENTRIES = fmt["root_entries"]
    MEDIA_BYTE = fmt["media_byte"]
    VOLUME_LABEL = fmt["label"]

    root_dir_sectors = (ROOT_ENTRIES * 32 + BYTES_PER_SECTOR - 1) // BYTES_PER_SECTOR
    data_start_sector = RESERVED_SECTORS + NUM_FATS * SECTORS_PER_FAT + root_dir_sectors
    total_data_sectors = TOTAL_SECTORS - data_start_sector
    total_clusters = total_data_sectors // SECTORS_PER_CLUSTER

    now = time.time()
    os.makedirs(os.path.dirname(OUTPUT_IMG) or '.', exist_ok=True)

    # Read source files
    name_data = []
    for disp_name, src_path in FILES:
        if not os.path.exists(src_path):
            print(f"Warning: {src_path} not found, skipping")
            continue
        with open(src_path, 'rb') as f:
            data = f.read()
        name_data.append((disp_name, data))
        print(f"  + {disp_name} ({len(data)} bytes)")

    # Add user config files if they exist
    for disp_name, src_path in _USER_BUNDLE_FILES:
        if os.path.exists(src_path):
            with open(src_path, 'rb') as f:
                data = f.read()
            name_data.append((disp_name, data))
            print(f"  + {disp_name} ({len(data)} bytes) [user config]")

    # Add plugins from repo and user dirs
    for pdir in _PLUGIN_DIRS:
        if os.path.isdir(pdir):
            for fn in sorted(os.listdir(pdir)):
                if fn.endswith('.py') and fn != '__init__.py':
                    src = os.path.join(pdir, fn)
                    with open(src, 'rb') as f:
                        data = f.read()
                    name_data.append((fn.upper(), data))
                    print(f"  + {fn} ({len(data)} bytes) [plugin]")

    # Add autorun as a file
    name_data.append(("autorun.sh", AUTORUN))
    print(f"  + autorun.sh ({len(AUTORUN)} bytes)")

    # Sort by size descending for allocation
    name_data.sort(key=lambda nd: -len(nd[1]))

    # Allocate clusters: build chain and data layout
    chain = [0] * total_clusters  # 0 = free
    next_free = 0

    file_entries = []
    data_blocks = bytearray()  # all file data concatenated

    for disp_name, data in name_data:
        # Split name into base + ext
        dot = disp_name.find('.')
        if dot >= 0:
            base = disp_name[:dot]
            ext = disp_name[dot+1:]
        else:
            base = disp_name
            ext = ''

        clusters_needed = (len(data) + BYTES_PER_SECTOR - 1) // BYTES_PER_SECTOR

        if clusters_needed == 0:
            # Empty file: no clusters allocated, first_cluster = 0
            file_entries.append((data, base, ext, 0, 0))
            print(f"  -> {disp_name}: empty file (0 sectors)")
            continue

        # Find contiguous free clusters
        start = None
        count = 0
        for i in range(total_clusters):
            if chain[i] == 0:
                if start is None:
                    start = i
                count += 1
                if count == clusters_needed:
                    break
            else:
                start = None
                count = 0

        if count < clusters_needed:
            print(f"ERROR: Not enough free clusters for {disp_name}")
            sys.exit(1)

        # Set chain values: FAT entries index = chain_index + 2
        # chain[i] = i + 3 (next cluster) or 0xFFF (EOC)
        for j in range(clusters_needed):
            idx = start + j
            if j < clusters_needed - 1:
                chain[idx] = idx + 3  # absolute FAT entry index for next cluster
            else:
                chain[idx] = FAT12_EOC

        file_entries.append((data, base, ext, start + 2, len(data)))
        print(f"  -> {disp_name}: cluster {start}, {clusters_needed} sectors")
        data_blocks.extend(data)
        # Align to sector boundary for next file
        pad = (BYTES_PER_SECTOR - len(data) % BYTES_PER_SECTOR) % BYTES_PER_SECTOR
        data_blocks.extend(b'\x00' * pad)

    # Create blank image
    img = bytearray(TOTAL_SECTORS * BYTES_PER_SECTOR)

    # Boot sector
    img[0:512] = build_boot_sector()

    # FATs
    fat_data = build_fat(chain, SECTORS_PER_FAT, total_clusters, MEDIA_BYTE)
    fat1_off = RESERVED_SECTORS * BYTES_PER_SECTOR
    img[fat1_off:fat1_off + len(fat_data)] = fat_data
    fat2_off = (RESERVED_SECTORS + SECTORS_PER_FAT) * BYTES_PER_SECTOR
    img[fat2_off:fat2_off + len(fat_data)] = fat_data

    # Root directory
    root_off = (RESERVED_SECTORS + NUM_FATS * SECTORS_PER_FAT) * BYTES_PER_SECTOR
    dir_entries = bytearray(ROOT_ENTRIES * 32)

    idx = 0
    for data, base, ext, cluster, size in file_entries:
        de = encode_dir_entry(base, ext, 0, size, cluster, now)
        dir_entries[idx*32:(idx+1)*32] = de
        idx += 1

    # Volume label
    vol = encode_dir_entry("PRISM32_V", "", 0x08, 0, 0, now)
    dir_entries[idx*32:(idx+1)*32] = vol
    idx += 1

    img[root_off:root_off + len(dir_entries)] = dir_entries

    # Data area
    data_off = data_start_sector * BYTES_PER_SECTOR
    img[data_off:data_off + len(data_blocks)] = data_blocks

    # Write
    with open(OUTPUT_IMG, 'wb') as f:
        f.write(bytes(img))

    kb = os.path.getsize(OUTPUT_IMG) / 1024
    used = sum(1 for c in chain if c != 0)
    print(f"\n  Floppy image: {OUTPUT_IMG}")
    print(f"  Format: {fmt_name} ({fmt['label']}, {fmt['total_sectors']} sectors)")
    print(f"  Size: {kb:.1f} KB  ({os.path.getsize(OUTPUT_IMG)} bytes)")
    print(f"  Files: {len(file_entries)}  (clusters used: {used}/{total_clusters})")
    print(f"  Free: {(total_clusters - used) / total_clusters * 100:.0f}%")
    print(f"\n  To write:  python3 make_floppy.py --write [device]")
    print(f"  To mount:  mount -o loop {OUTPUT_IMG} /mnt/floppy")
    print(f"  To install: mount -o loop {OUTPUT_IMG} /mnt/floppy &&")
    print(f"                     cd /mnt/floppy && sh AUTORUN.SH")
    return True


def detect_removable():
    """Detect removable media device (floppy, SD card, USB flash)."""
    system = platform.system()
    if system == "Linux":
        for prefix in ("sd", "mmcblk"):
            for entry in os.listdir("/sys/block/"):
                if not entry.startswith(prefix):
                    continue
                try:
                    path = f"/sys/block/{entry}"
                    rem = open(f"{path}/removable").read().strip()
                    size = int(open(f"{path}/size").read().strip())
                except (OSError, ValueError):
                    continue
                if rem == "1" and 2880 <= size <= 8388608:
                    return f"/dev/{entry}"
    elif system == "Darwin":
        for i in range(1, 10):
            dev = f"/dev/disk{i}"
            if os.path.exists(dev):
                try:
                    out = subprocess.check_output(
                        ["diskutil", "info", dev], stderr=subprocess.STDOUT
                    ).decode()
                    if "Ejectable: Yes" in out:
                        return dev
                except (subprocess.CalledProcessError, OSError):
                    pass
    elif system in ("NetBSD", "OpenBSD", "FreeBSD"):
        # Safe: only check floppy drives and USB mass storage
        for dev in ["/dev/fd0", "/dev/fd1", "/dev/da0", "/dev/da1"]:
            if os.path.exists(dev):
                return dev
    return None


def write_to_device(img_path, device=None):
    """Write the floppy image to a device. Auto-detect if not specified."""
    if device is None:
        device = detect_removable()
    if device is None:
        print("  No removable media detected.")
        print(f"  Specify device: python3 make_floppy.py --write /dev/sdc")
        return False
    if not os.path.exists(device):
        print(f"  Device not found: {device}")
        return False

    print(f"\n  Target: {device}")
    print(f"  WARNING: ALL DATA ON {device} WILL BE DESTROYED!")
    confirm = input("  Continue? (y/N): ").strip().lower()
    if confirm not in ("y", "yes"):
        print("  Cancelled.")
        return False

    system = platform.system()
    cmd = []
    if system in ("Linux", "NetBSD", "OpenBSD", "FreeBSD"):
        if os.geteuid() != 0:
            cmd = ["sudo", "dd", f"if={img_path}", f"of={device}", "bs=512", "conv=fsync"]
        else:
            cmd = ["dd", f"if={img_path}", f"of={device}", "bs=512", "conv=fsync"]
    elif system == "Darwin":
        subprocess.run(["diskutil", "unmountDisk", device],
                       capture_output=True)
        if os.geteuid() != 0:
            cmd = ["sudo", "dd", f"if={img_path}", f"of={device}", "bs=512"]
        else:
            cmd = ["dd", f"if={img_path}", f"of={device}", "bs=512"]

    print(f"  Running: {' '.join(cmd)}")
    try:
        subprocess.run(cmd, check=True)
        if system == "Darwin":
            subprocess.run(["diskutil", "eject", device], capture_output=True)
        print(f"\n  Device written successfully.")
        print(f"  Eject and insert the media, then run: sh AUTORUN.SH")
        return True
    except subprocess.CalledProcessError as e:
        print(f"\n  Error writing to device: {e}")
        return False


if __name__ == '__main__':
    import argparse
    parser = argparse.ArgumentParser(description="Prism32 Floppy Image Builder")
    parser.add_argument("--write", "-w", nargs="?", const=True, default=False,
                        help="Write image to device (auto-detect or specify)")
    parser.add_argument("--output", "-o", default=OUTPUT_IMG,
                        help=f"Output image path (default: {OUTPUT_IMG})")
    parser.add_argument("--format", "-f", default="35-hd",
                        choices=list(FLOPPY_FORMATS.keys()),
                        help="Floppy format: 35-hd (1.44MB, default), "
                             "525-hd (1.2MB), 525-double (360KB)")
    args = parser.parse_args()

    globals()['OUTPUT_IMG'] = args.output
    try:
        ok = build(fmt_name=args.format)
        if not ok:
            sys.exit(1)
    except Exception as e:
        print(f"Build failed: {e}")
        sys.exit(1)

    if args.write:
        device = args.write if isinstance(args.write, str) else None
        try:
            if not write_to_device(OUTPUT_IMG, device):
                sys.exit(1)
        except Exception as e:
            print(f"Write failed: {e}")
            sys.exit(1)