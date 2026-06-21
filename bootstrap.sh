#!/usr/bin/env sh
# ═══════════════════════════════════════════════════════════════
#  Prism32 Universal Bootstrap Installer
#  Auto-detects platform and installs Prism32 + dependencies
#
#  Usage:
#    curl -fsSL https://raw.githubusercontent.com/MegaDyneSystems/prism32/main/bootstrap.sh | sh
#    wget -qO- https://raw.githubusercontent.com/MegaDyneSystems/prism32/main/bootstrap.sh | sh
#
#  Or save and run:
#    sh bootstrap.sh
# ═══════════════════════════════════════════════════════════════
set -eu

REPO="https://github.com/MegaDyneSystems/prism32"
RAW="https://raw.githubusercontent.com/MegaDyneSystems/prism32/main"
RUNTIME_DIR="$HOME/.prism32"
BIN_TYPE=""

# ── ANSI ──
if [ -t 1 ]; then
  RST='\033[0m'; BLD='\033[1m'; DIM='\033[2m'
  G='\033[92m'; Y='\033[93m'; CY='\033[96m'; R='\033[91m'
else
  RST=''; BLD=''; DIM=''; G=''; Y=''; CY=''; R=''
fi

log()   { echo -e "$*"; }
ok()    { echo -e "  ${G}*${RST} $*"; }
warn()  { echo -e "  ${Y}w${RST} $*"; }
fail()  { echo -e "  ${R}!${RST} $*"; }
header(){ echo -e "\n${CY}${BLD}--- $*${RST}"; }

echo ""
echo -e "${CY}${BLD}  +========================================+${RST}"
echo -e "${CY}${BLD}  |  Prism32 Universal Bootstrap Installer  |${RST}"
echo -e "${CY}${BLD}  |  MegaDyne Systems (MDS) Edition         |${RST}"
echo -e "${CY}${BLD}  +========================================+${RST}"
echo ""

# ── Detect platform ──
header "Detecting Platform"

OS="$(uname -s)"
ARCH="$(uname -m)"

echo -e "  ${DIM}OS:${RST}    $OS"
echo -e "  ${DIM}Arch:${RST}  $ARCH"

# Find Python 3
PY3=""
for py in python3 python3.11 python3.10 python3.9 python3.8 python3.7; do
  if command -v "$py" >/dev/null 2>&1; then
    PY3="$py"
    break
  fi
done

# ── Termux / Android ──
if [ -n "${TERMUX_VERSION:-}" ] || [ -d "/data/data/com.termux" ]; then
  ok "Platform: Android (Termux)"
  if [ -z "$PY3" ]; then
    warn "Installing Python..."
    pkg install -y python git
    PY3="python3"
  fi
  if ! command -v git >/dev/null 2>&1; then
    pkg install -y git
  fi
  # Clone and install
  CLONE_DIR="$HOME/prism32"
  if [ -d "$CLONE_DIR/.git" ]; then
    ok "Updating existing clone..."
    git -C "$CLONE_DIR" pull origin main 2>/dev/null || true
  else
    git clone --depth 1 "$REPO" "$CLONE_DIR"
  fi
  cd "$CLONE_DIR"
  sh install.sh -y
  exit 0
fi

# ── OpenWrt ──
if [ -f "/etc/openwrt_release" ]; then
  ok "Platform: OpenWrt"
  if [ -z "$PY3" ]; then
    if command -v opkg >/dev/null 2>&1; then
      opkg update
      opkg install python3-light python3-openssl git-http
    elif command -v apk >/dev/null 2>&1; then
      apk add python3 git-http
    fi
    PY3="python3"
  fi
  CLONE_DIR="$HOME/prism32"
  if [ -d "$CLONE_DIR/.git" ]; then
    git -C "$CLONE_DIR" pull origin main 2>/dev/null || true
  else
    git clone --depth 1 "$REPO" "$CLONE_DIR" 2>/dev/null || {
      # Git not available — download directly
      warn "git not available, downloading files directly..."
      mkdir -p "$RUNTIME_DIR"
      wget -qO- "$RAW/prism32.py" > "$RUNTIME_DIR/prism32.py" 2>/dev/null || \
        curl -fsSL "$RAW/prism32.py" > "$RUNTIME_DIR/prism32.py"
      wget -qO- "$RAW/openwrt-install.sh" > "/tmp/prism32-install.sh" 2>/dev/null || \
        curl -fsSL "$RAW/openwrt-install.sh" > "/tmp/prism32-install.sh"
      sh /tmp/prism32-install.sh -y
      exit 0
    }
  fi
  cd "$CLONE_DIR"
  sh openwrt-install.sh -y
  exit 0
fi

# ── macOS ──
if [ "$OS" = "Darwin" ]; then
  ok "Platform: macOS"
  if [ -z "$PY3" ]; then
    warn "Python 3 not found. Installing via Homebrew..."
    if ! command -v brew >/dev/null 2>&1; then
      /bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"
    fi
    brew install python git
    PY3="python3"
  fi
  # macOS SSL fix
  "$PY3" -c "import urllib.request; urllib.request.urlopen('https://google.com', timeout=3)" 2>/dev/null || {
    warn "Fixing SSL certificates..."
    "$PY3" -m pip install --upgrade certifi 2>/dev/null || true
  }
  CLONE_DIR="$HOME/prism32"
  if [ -d "$CLONE_DIR/.git" ]; then
    ok "Updating existing clone..."
    git -C "$CLONE_DIR" pull origin main 2>/dev/null || true
  else
    git clone --depth 1 "$REPO" "$CLONE_DIR"
  fi
  cd "$CLONE_DIR"
  sh install.sh -y
  exit 0
fi

# ── Linux (generic) ──
if [ "$OS" = "Linux" ]; then
  ok "Platform: Linux"

  # Check for package managers and install Python+git if needed
  if [ -z "$PY3" ]; then
    warn "Python 3 not found, installing..."
    if command -v apt-get >/dev/null 2>&1; then
      sudo apt-get update -qq && sudo apt-get install -y python3 git
    elif command -v dnf >/dev/null 2>&1; then
      sudo dnf install -y python3 git
    elif command -v yum >/dev/null 2>&1; then
      sudo yum install -y python3 git
    elif command -v pacman >/dev/null 2>&1; then
      sudo pacman -S --noconfirm python git
    elif command -v zypper >/dev/null 2>&1; then
      sudo zypper install -y python3 git
    elif command -v apk >/dev/null 2>&1; then
      sudo apk add python3 git
    elif command -v emerge >/dev/null 2>&1; then
      sudo emerge python git
    elif command -v xbps-install >/dev/null 2>&1; then
      sudo xbps-install -y python3 git
    elif command -v pkg >/dev/null 2>&1; then
      # FreeBSD/TrueOS
      sudo pkg install -y python3 git
    else
      fail "No recognized package manager found."
      echo -e "  ${DIM}Install Python 3.7+ and git manually, then run:${RST}"
      echo -e "  ${DIM}git clone $REPO ~/prism32 && cd ~/prism32 && sh install.sh -y${RST}"
      exit 1
    fi
    PY3="python3"
  fi

  if ! command -v git >/dev/null 2>&1; then
    # Try to install git without sudo (may already be available on some systems)
    if command -v apt-get >/dev/null 2>&1; then sudo apt-get install -y git
    elif command -v dnf >/dev/null 2>&1; then sudo dnf install -y git
    elif command -v pacman >/dev/null 2>&1; then sudo pacman -S --noconfirm git
    fi
  fi

  CLONE_DIR="$HOME/prism32"
  if [ -d "$CLONE_DIR/.git" ]; then
    ok "Updating existing clone..."
    git -C "$CLONE_DIR" pull origin main 2>/dev/null || true
  else
    git clone --depth 1 "$REPO" "$CLONE_DIR"
  fi
  cd "$CLONE_DIR"
  sh install.sh -y
  exit 0
fi

# ── FreeBSD / BSD ──
if [ "$OS" = "FreeBSD" ] || [ "$OS" = "OpenBSD" ] || [ "$OS" = "NetBSD" ] || [ "$OS" = "DragonFly" ]; then
  ok "Platform: BSD ($OS)"
  if [ -z "$PY3" ]; then
    if command -v pkg >/dev/null 2>&1; then
      sudo pkg install -y python3 git
    elif command -v pkgin >/dev/null 2>&1; then
      sudo pkgin install python3 git
    elif command -v pkg_add >/dev/null 2>&1; then
      sudo pkg_add python3 git
    fi
    PY3="python3"
  fi
  CLONE_DIR="$HOME/prism32"
  if [ -d "$CLONE_DIR/.git" ]; then
    git -C "$CLONE_DIR" pull origin main 2>/dev/null || true
  else
    git clone --depth 1 "$REPO" "$CLONE_DIR"
  fi
  cd "$CLONE_DIR"
  sh install.sh -y
  exit 0
fi

# ── Fallback: download prism32.py directly ──
warn "Unrecognized platform: $OS"
echo -e "  ${DIM}Attempting direct download of prism32.py...${RST}"
mkdir -p "$RUNTIME_DIR"
if command -v wget >/dev/null 2>&1; then
  wget -qO- "$RAW/prism32.py" > "$RUNTIME_DIR/prism32.py"
elif command -v curl >/dev/null 2>&1; then
  curl -fsSL "$RAW/prism32.py" > "$RUNTIME_DIR/prism32.py"
elif [ -n "$PY3" ]; then
  "$PY3" -c "
import urllib.request
urllib.request.urlretrieve('$RAW/prism32.py', '$RUNTIME_DIR/prism32.py')
"
else
  fail "Cannot download — no wget, curl, or python3 available."
  echo -e "  ${DIM}Download manually from: $RAW/prism32.py${RST}"
  exit 1
fi

if [ -s "$RUNTIME_DIR/prism32.py" ]; then
  ok "Downloaded to $RUNTIME_DIR/prism32.py"
  echo -e "\n  ${CY}Run with: python3 $RUNTIME_DIR/prism32.py${RST}\n"
else
  fail "Download failed"
  exit 1
fi
