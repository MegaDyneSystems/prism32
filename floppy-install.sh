#!/bin/sh
# Prism32 Floppy Installer - Cross-platform floppy/SD/USB writer
# Usage: sh floppy-install.sh [image_file] [device]
#   image_file:  path to floppy image (default: prism32_floppy.img)
#   device:      target device (auto-detected if omitted)

set -e

RST='\033[0m'
BOLD='\033[1m'
RED='\033[31m'
GRN='\033[32m'
YEL='\033[33m'
CYN='\033[36m'
DIM='\033[2m'

detect_platform() {
    case "$(uname -s)" in
        Linux)      echo "linux" ;;
        Darwin)     echo "macos" ;;
        NetBSD)     echo "netbsd" ;;
        OpenBSD)    echo "openbsd" ;;
        FreeBSD)    echo "freebsd" ;;
        *)          echo "unknown" ;;
    esac
}

find_floppy() {
    PLATFORM=$(detect_platform)
    echo "${DIM}  Scanning for removable media...${RST}" >&2
    CANDIDATES=""
    
    case "$PLATFORM" in
        linux)
            # Find removable USB block devices (floppy, SD, USB flash)
            for dev in /sys/block/sd* /sys/block/mmcblk* /sys/block/fd*; do
                [ -e "$dev" ] || continue
                DEVNAME=$(basename "$dev")
                SIZE=$(cat "$dev/size" 2>/dev/null || echo 0)
                REMOVABLE=$(cat "$dev/removable" 2>/dev/null || echo 0)
                
                # Must be removable, 1.44MB to 4GB (floppy to small USB)
                [ "$REMOVABLE" = "1" ] || continue
                [ "$SIZE" -ge 2880 ] && [ "$SIZE" -le 8388608 ] || continue
                
                DEV_PATH="/dev/$DEVNAME"
                MODEL=$(cat "$dev/device/model" 2>/dev/null || echo "")
                echo "${DIM}  Found: $DEV_PATH ($MODEL, ${SIZE}sectors)${RST}" >&2
                CANDIDATES="$CANDIDATES $DEV_PATH"
            done
            ;;
        macos)
            for dev in /dev/disk{1,2,3,4,5,6,7,8,9}; do
                [ -e "$dev" ] || continue
                INFO=$(diskutil info "$dev" 2>/dev/null || true)
                if echo "$INFO" | grep -qi "Ejectable: Yes"; then
                    echo "${DIM}  Found: $dev${RST}" >&2
                    CANDIDATES="$CANDIDATES $dev"
                fi
            done
            ;;
        netbsd|openbsd|freebsd)
            # Safe: only check /dev/fd? (actual floppy drives)
            for dev in /dev/fd?; do
                [ -e "$dev" ] || continue
                echo "${DIM}  Found: $dev${RST}" >&2
                CANDIDATES="$CANDIDATES $dev"
            done
            # Also check da? (USB mass storage on BSD)
            for dev in /dev/da?; do
                [ -e "$dev" ] || continue
                echo "${DIM}  Found: $dev${RST}" >&2
                CANDIDATES="$CANDIDATES $dev"
            done
            ;;
    esac
    
    # Handle candidates
    CANDIDATES=$(echo $CANDIDATES | tr ' ' '\n' | grep -v '^$' | sort -u)
    COUNT=$(echo "$CANDIDATES" | wc -l)
    if [ "$COUNT" -eq 0 ]; then
        echo ""
        return 0
    fi
    if [ "$COUNT" -eq 1 ]; then
        echo "$CANDIDATES"
        return 0
    fi
    # Multiple candidates: ask user
    echo "  ${YEL}Multiple removable devices found:${RST}" >&2
    IFS=$'\n'
    i=1
    for c in $CANDIDATES; do
        echo "  $i. $c" >&2
        i=$((i+1))
    done
    printf "  Select device [1-%d]: " "$((i-1))" >&2
    read -r CHOICE
    echo "$CANDIDATES" | sed -n "${CHOICE}p"
}

write_image() {
    IMAGE="$1"
    DEVICE="$2"
    PLATFORM=$(detect_platform)
    
    if [ ! -f "$IMAGE" ]; then
        echo "  ${RED}Image not found: $IMAGE${RST}"
        return 1
    fi
    
    IMG_SIZE=$(stat -f%z "$IMAGE" 2>/dev/null || stat -c%s "$IMAGE" 2>/dev/null || echo 1474560)
    
    echo ""
    echo "  ${BOLD}Prism32 Floppy Image Writer${RST}"
    echo "  ${DIM}Platform: $PLATFORM${RST}"
    echo "  ${DIM}Image:    $IMAGE (${IMG_SIZE} bytes)${RST}"
    echo "  ${DIM}Device:   $DEVICE${RST}"
    echo ""
    
    if [ ! -b "$DEVICE" ] && [ ! -c "$DEVICE" ]; then
        echo "  ${RED}Not a valid block device: $DEVICE${RST}"
        return 1
    fi
    
    echo "  ${YEL}WARNING: This will erase ALL data on $DEVICE${RST}"
    printf "  Continue? (y/N): "
    read -r CONFIRM
    case "$CONFIRM" in
        y|Y|yes|YES) ;;
        *) echo "  ${DIM}Cancelled.${RST}"; return 1 ;;
    esac
    
    # Determine write command
    case "$PLATFORM" in
        linux|netbsd|openbsd|freebsd)
            if command -v sudo >/dev/null 2>&1; then
                DO="sudo"
            else
                DO=""
            fi
            echo "  ${CYN}Writing...${RST}"
            $DO dd if="$IMAGE" of="$DEVICE" bs=512 conv=fsync status=progress 2>&1 || \
            $DO dd if="$IMAGE" of="$DEVICE" bs=512 conv=fsync
            $DO sync
            ;;
        macos)
            # Unmount first
            diskutil unmountDisk "$DEVICE" 2>/dev/null || true
            echo "  ${CYN}Writing...${RST}"
            sudo dd if="$IMAGE" of="$DEVICE" bs=512
            sudo sync
            diskutil eject "$DEVICE" 2>/dev/null || true
            ;;
    esac
    
    echo "  ${GRN}Done.${RST}"
    echo "  ${DIM}To install: mount the media and run: sh AUTORUN.SH${RST}"
    echo ""
}

# ── Main ──
IMAGE="${1:-prism32_floppy.img}"
if [ ! -f "$IMAGE" ]; then
    IMAGE="/tmp/opencode/prism32_floppy.img"
fi

if [ -n "$2" ]; then
    DEVICE="$2"
else
    DEVICE=$(find_floppy)
fi

if [ -z "$DEVICE" ]; then
    echo ""
    echo "  ${YEL}No removable media detected.${RST}"
    echo ""
    echo "  Usage: $0 [image_file] [device]"
    echo ""
    echo "  Examples:"
    echo "    $0                                          # auto-detect"
    echo "    $0 prism32_floppy.img /dev/sdc              # Linux USB floppy"
    echo "    $0 /tmp/img.bin /dev/disk2                  # macOS"
    echo "    $0 prism32_floppy.img /dev/rsd1c            # NetBSD"
    echo ""
    echo "  ${DIM}You can also use SD cards or USB flash drives${RST}"
    echo "  ${DIM}(minimum 1.44MB, will be reformatted)${RST}"
    echo ""
    exit 1
fi

write_image "$IMAGE" "$DEVICE"