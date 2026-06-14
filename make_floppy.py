#!/usr/bin/env python3
"""Build a Prism32 floppy disk installer image.
FAT12 filesystem - can be dd'd directly to a floppy disk (/dev/sdc)."""
import os, sys, struct, time

PRISM32_DIR = os.path.expanduser("~/Documents/Programs/Palmcoder95")
OUTPUT_IMG = "/tmp/opencode/prism32_floppy.img"

BYTES_PER_SECTOR = 512
SECTORS_PER_CLUSTER = 1
RESERVED_SECTORS = 1
NUM_FATS = 2
ROOT_ENTRIES = 224
TOTAL_SECTORS = 2880
SECTORS_PER_FAT = 9
SECTORS_PER_TRACK = 18
NUM_HEADS = 2
FAT12_EOC = 0xFFF

root_dir_sectors = (ROOT_ENTRIES * 32 + BYTES_PER_SECTOR - 1) // BYTES_PER_SECTOR
data_start_sector = RESERVED_SECTORS + NUM_FATS * SECTORS_PER_FAT + root_dir_sectors
total_data_sectors = TOTAL_SECTORS - data_start_sector
total_clusters = total_data_sectors // SECTORS_PER_CLUSTER

FILES = [
    ("prism32.py",  os.path.join(PRISM32_DIR, "prism32.py")),
    ("install.sh",  os.path.join(PRISM32_DIR, "install.sh")),
    ("README.md",   os.path.join(PRISM32_DIR, "README.md")),
]

# Autorun script stored as a file on the floppy
AUTORUN = b"""#!/bin/sh
echo ""
echo "  ==========================================="
echo "   Prism32 v6.7 - MegaDyne Systems"
echo "   Floppy Disk Installer"
echo "  ==========================================="
echo ""
echo "  Installing Prism32 to this system..."
echo ""
if [ -f install.sh ]; then
    sh install.sh
else
    SRC="$(dirname "$0")"
    cp "$SRC/prism32.py" ~/.local/bin/prism32 2>/dev/null
    install -m 755 "$SRC/prism32.py" ~/.local/bin/prism32
    echo "  Installed."
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
    bs = bytearray(512)
    bs[0:3] = b'\xeb\x3c\x90'
    bs[3:11] = b'PRISM32 '
    struct.pack_into('<H', bs, 11, BYTES_PER_SECTOR)
    bs[13] = SECTORS_PER_CLUSTER
    struct.pack_into('<H', bs, 14, RESERVED_SECTORS)
    bs[16] = NUM_FATS
    struct.pack_into('<H', bs, 17, ROOT_ENTRIES)
    struct.pack_into('<H', bs, 19, TOTAL_SECTORS)
    bs[21] = 0xF0
    struct.pack_into('<H', bs, 22, SECTORS_PER_FAT)
    struct.pack_into('<H', bs, 24, SECTORS_PER_TRACK)
    struct.pack_into('<H', bs, 26, NUM_HEADS)
    struct.pack_into('<I', bs, 28, 0)
    struct.pack_into('<I', bs, 32, 0)
    bs[36] = 0x00
    bs[37] = 0x00
    bs[38] = 0x29
    struct.pack_into('<I', bs, 39, int(time.time()) & 0xFFFFFFFF)
    bs[43:54] = b'PRISM32_FLP'
    bs[54:62] = b'FAT12   '
    msg = b'Prism32 v6.7 - Boot from HD' + b'\x00' * 16
    bs[62:62+len(msg)] = msg
    bs[510:512] = b'\x55\xAA'
    return bytes(bs)


def build_fat(chain):
    """Build FAT12 table bytes from a cluster chain list.
    chain[n] = next cluster for cluster n, or 0xFFF for EOC, or 0 for free."""
    total = total_clusters + 2
    fat = bytearray(SECTORS_PER_FAT * BYTES_PER_SECTOR)
    entries = [0xFF0, 0xFFF]  # FAT[0] = media desc (0xF0) + 0xFF, FAT[1] = EOC
    entries.extend(chain)

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


def build():
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
    fat_data = build_fat(chain)
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
    print(f"  Size: {kb:.1f} KB  ({os.path.getsize(OUTPUT_IMG)} bytes)")
    print(f"  Files: {len(file_entries)}  (clusters used: {used}/{total_clusters})")
    print(f"  Free: {(total_clusters - used) / total_clusters * 100:.0f}%")
    print(f"\n  To write to floppy: dd if={OUTPUT_IMG} of=/dev/sdc bs=512")
    print(f"  To mount:          mount -o loop {OUTPUT_IMG} /mnt/floppy")
    print(f"  To install:        mount -o loop {OUTPUT_IMG} /mnt/floppy &&")
    print(f"                     cd /mnt/floppy && sh autorun.sh")
    return True


if __name__ == '__main__':
    build()