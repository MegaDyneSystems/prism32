#!/bin/sh
# ═══════════════════════════════════════════════════════════════
#  Prism32 — MegaDyne Systems OpenWrt Installer
#  One-click install for OpenWrt routers (ash/POSIX sh)
#  Works on 4MB+ flash, 32MB+ RAM, with USB/SD extroot support
# ═══════════════════════════════════════════════════════════════
# Usage:
#   wget -O /tmp/openwrt-install.sh http://your-server/prism32/openwrt-install.sh
#   sh /tmp/openwrt-install.sh           # interactive
#   sh /tmp/openwrt-install.sh -y        # auto (no prompts)
#   sh /tmp/openwrt-install.sh /mnt/usb  # install to USB mount
# ═══════════════════════════════════════════════════════════════
set -e

NAME="prism32"
AUTO=0
USB_DEST=""
SRC_DIR="$(cd "$(dirname "$0")" && pwd)"
SRC_FILE="$SRC_DIR/prism32.py"

# Parse args
for arg in "$@"; do
    case "$arg" in
        -y|--yes) AUTO=1 ;;
        /*) USB_DEST="$arg" ;;
    esac
done

# ── Colors (if terminal supports) ──
RST=""
BLD=""
DIM=""
G=""
Y=""
R=""
if [ -t 1 ] && [ -z "$NO_COLOR" ]; then
    RST='\033[0m'; BLD='\033[1m'; DIM='\033[2m'
    G='\033[92m'; Y='\033[93m'; R='\033[91m'
fi

ok()    { printf "  ${G}*${RST} %s\n" "$*"; }
warn()  { printf "  ${Y}w${RST} %s\n" "$*"; }
fail()  { printf "  ${R}!${RST} %s\n" "$*"; }
header(){ printf "\n${BLD}--- %s${RST}\n" "$*"; }
sub()   { printf "  ${DIM}|${RST}  %s\n" "$*"; }

# ── Banner ──
printf "\n"
printf "  ${BLD}+========================================+${RST}\n"
printf "  ${BLD}|  Prism32 OpenWrt Installer v6.8      |${RST}\n"
printf "  ${BLD}|  MegaDyne Systems Edition             |${RST}\n"
printf "  ${BLD}+========================================+${RST}\n"
printf "\n"

# ═══════════════════════════════════════════════════════════════
#  1. Detect package manager and bootstrap SSL
# ═══════════════════════════════════════════════════════════════
header "Step 1/6 - Bootstrap"

# Detect package manager (opkg for OpenWrt <24, apk for >=24)
PM=""
if command -v opkg >/dev/null 2>&1; then
    PM="opkg"
elif command -v apk >/dev/null 2>&1; then
    PM="apk"
else
    fail "No package manager found (opkg/apk). Is this OpenWrt?"
    exit 1
fi
ok "Package manager: $PM"

# Update package lists
sub "Updating package lists..."
if [ "$PM" = "opkg" ]; then
    opkg update >/dev/null 2>&1 || true
else
    apk update >/dev/null 2>&1 || true
fi

# Bootstrap HTTPS support (needed for git clone / downloads)
_install_pkg() {
    if [ "$PM" = "opkg" ]; then
        opkg install "$@" >/dev/null 2>&1 || true
    else
        apk add "$@" >/dev/null 2>&1 || true
    fi
}

# Check if HTTPS works already
if ! wget -q --spider https://github.com 2>/dev/null; then
    sub "Installing HTTPS/SSL support..."
    _install_pkg libustream-mbedtls ca-bundle
    _install_pkg libustream-openssl ca-certificates
fi

# Verify wget works now
if command -v wget >/dev/null 2>&1; then
    ok "wget available"
else
    _install_pkg wget-ssl
    if ! command -v wget >/dev/null 2>&1; then
        fail "wget not available and could not install"
        exit 1
    fi
fi

# ═══════════════════════════════════════════════════════════════
#  2. Install Python 3
# ═══════════════════════════════════════════════════════════════
header "Step 2/6 - Python 3"

PY3=""
if command -v python3 >/dev/null 2>&1; then
    PY3="python3"
    ok "Python 3 found: $(python3 --version 2>&1)"
else
    sub "Installing Python 3 (light)..."
    
    # If USB dest specified, install there
    if [ -n "$USB_DEST" ]; then
        if [ "$PM" = "opkg" ]; then
            # Add USB destination to opkg config
            grep -q "dest usb" /etc/opkg.conf 2>/dev/null || \
                echo "dest usb $USB_DEST" >> /etc/opkg.conf
            opkg -d usb install python3-light python3-openssl >/dev/null 2>&1 || true
            PY3="$USB_DEST/usr/bin/python3"
        else
            apk add --root "$USB_DEST" python3 >/dev/null 2>&1 || true
            PY3="$USB_DEST/usr/bin/python3"
        fi
    else
        # Check available flash space
        FREE_KB=$(df /usr 2>/dev/null | tail -1 | awk '{print $4}')
        if [ -n "$FREE_KB" ] && [ "$FREE_KB" -lt 8000 ]; then
            warn "Low flash space (${FREE_KB}KB free). Consider using USB:"
            warn "  sh openwrt-install.sh /mnt/usb"
            printf "  Continue installing to flash? (y/N): "
            if [ "$AUTO" = "0" ]; then
                read -r confirm
                case "$confirm" in
                    y|Y|yes) ;;
                    *) warn "Aborted. Try: sh $0 /mnt/usb"; exit 0 ;;
                esac
            fi
        fi
        
        # Install python3-light (smaller) first, fallback to python3
        _install_pkg python3-light python3-openssl
        if ! command -v python3 >/dev/null 2>&1; then
            sub "python3-light failed, trying full python3..."
            _install_pkg python3
        fi
        PY3="python3"
        
        # Also install python3-ctypes (needed by some stdlib)
        _install_pkg python3-ctypes
    fi
    
    if ! command -v python3 >/dev/null 2>&1 && [ -z "$USB_DEST" ]; then
        fail "Python 3 installation failed"
        fail "On low-flash routers, use USB: sh $0 /mnt/usb"
        exit 1
    fi
fi

# Verify Python works
if ! "$PY3" -c "print(1+1)" >/dev/null 2>&1; then
    fail "Python 3 is not working properly"
    exit 1
fi
ok "Python 3 verified"

# ═══════════════════════════════════════════════════════════════
#  3. Get prism32.py
# ═══════════════════════════════════════════════════════════════
header "Step 3/6 - Download"

# Determine runtime dir
if [ -n "$USB_DEST" ]; then
    RUNTIME_DIR="$USB_DEST/$NAME"
    BIN_DIR="$USB_DEST/bin"
else
    RUNTIME_DIR="/usr/lib/$NAME"
    BIN_DIR="/usr/bin"
fi
PLUGINS_DIR="$RUNTIME_DIR/plugins"
SESSIONS_DIR="$RUNTIME_DIR/sessions"

mkdir -p "$RUNTIME_DIR" "$PLUGINS_DIR" "$SESSIONS_DIR" "$BIN_DIR"

# If prism32.py is next to this script, copy it
if [ -f "$SRC_FILE" ]; then
    cp "$SRC_FILE" "$RUNTIME_DIR/prism32.py"
    ok "Copied prism32.py from $SRC_DIR"
else
    # Download from GitHub
    sub "Downloading prism32.py from GitHub..."
    URL="https://raw.githubusercontent.com/MegaDyneSystems/prism32/main/prism32.py"
    if wget -q -O "$RUNTIME_DIR/prism32.py" "$URL" 2>/dev/null; then
        ok "Downloaded prism32.py"
    else
        fail "Download failed. Try manually:"
        fail "  wget -O $RUNTIME_DIR/prism32.py $URL"
        exit 1
    fi
fi

# Verify it's valid Python (skip on very low RAM to avoid OOM)
_RAM_KB=$(awk '/MemTotal/{print $2}' /proc/meminfo 2>/dev/null || echo 0)
if [ "$_RAM_KB" -gt 0 ] && [ "$_RAM_KB" -lt 65536 ]; then
    warn "Low RAM (~$((_RAM_KB / 1024)) MB). Skipping py_compile to avoid OOM."
    warn "Compile .pyc on a host with more RAM if first run fails."
else
    if ! "$PY3" -c "import py_compile; py_compile.compile('$RUNTIME_DIR/prism32.py', doraise=True)" 2>/dev/null; then
        fail "prism32.py syntax validation failed"
        exit 1
    fi
    ok "prism32.py syntax valid"
fi

# Download plugins if not present
if [ ! -f "$PLUGINS_DIR/web_scraper.py" ]; then
    sub "Downloading web_scraper plugin..."
    PLUGIN_URL="https://raw.githubusercontent.com/MegaDyneSystems/prism32/main/plugins/web_scraper.py"
    wget -q -O "$PLUGINS_DIR/web_scraper.py" "$PLUGIN_URL" 2>/dev/null && ok "Downloaded web_scraper plugin" || warn "Plugin download skipped (non-critical)"
fi

chmod +x "$RUNTIME_DIR/prism32.py"

# ═══════════════════════════════════════════════════════════════
#  4. Create wrapper
# ═══════════════════════════════════════════════════════════════
header "Step 4/6 - Wrapper"

WRAPPER="$BIN_DIR/$NAME"

# Find the actual python3 path
PY3_PATH="$(command -v python3 2>/dev/null || which python3 2>/dev/null || echo "$PY3")"

cat > "$WRAPPER" << WRAP
#!/bin/sh
# Prism32 launcher - generated by openwrt-install.sh
exec "$PY3_PATH" "$RUNTIME_DIR/prism32.py" "\$@"
WRAP
chmod +x "$WRAPPER"

ok "Wrapper: $WRAPPER"

# Add to PATH if not in standard location
case ":$PATH:" in
    *":$BIN_DIR:"*) ;;
    *)
        sub "Adding $BIN_DIR to PATH"
        export PATH="$BIN_DIR:$PATH"
        ;;
esac

# ═══════════════════════════════════════════════════════════════
#  5. Configuration
# ═══════════════════════════════════════════════════════════════
header "Step 5/6 - Configuration"

CONFIG_FILE="$RUNTIME_DIR/config.json"

if [ -f "$CONFIG_FILE" ]; then
    ok "Existing config preserved at $CONFIG_FILE"
else
    # Determine provider
    PROVIDER="local"
    API_BASE="http://127.0.0.1:8080"
    MODEL="model.gguf"
    API_KEY=""

    if [ "$AUTO" = "0" ] && [ -t 0 ]; then
        printf "\n  Select provider:\n"
        printf "    1. Local (llama.cpp on this router)\n"
        printf "    2. Ollama (localhost)\n"
        printf "    3. OpenAI\n"
        printf "    4. Anthropic\n"
        printf "    5. Groq\n"
        printf "    6. Together AI\n"
        printf "    7. OpenRouter\n"
        printf "    8. Neuralwatt Cloud\n"
        printf "    9. Custom\n"
        printf "  Choice [1-9] (default: 1): "
        read -r sel
        sel="${sel:-1}"
        case "$sel" in
            2) PROVIDER="ollama"; API_BASE="http://localhost:11434/v1"; MODEL="qwen3:14b" ;;
            3) PROVIDER="openai"; API_BASE="https://api.openai.com/v1"; MODEL="gpt-4o" ;;
            4) PROVIDER="anthropic"; API_BASE="https://api.anthropic.com/v1"; MODEL="claude-sonnet-4-20250514" ;;
            5) PROVIDER="groq"; API_BASE="https://api.groq.com/openai/v1"; MODEL="llama-3.3-70b-versatile" ;;
            6) PROVIDER="together"; API_BASE="https://api.together.xyz/v1"; MODEL="meta-llama/Llama-3.3-70b" ;;
            7) PROVIDER="openrouter"; API_BASE="https://openrouter.ai/api/v1"; MODEL="deepseek/deepseek-v4-flash" ;;
            8) PROVIDER="neuralwatt"; API_BASE="https://api.neuralwatt.com/v1"; MODEL="glm-5.2" ;;
            9) printf "  API base: "; read -r API_BASE; printf "  Model: "; read -r MODEL ;;
        esac

        # API key for cloud providers
        case "$PROVIDER" in
            local|ollama) ;;
            *)
                printf "  API key (or Enter to skip): "
                read -r API_KEY
                ;;
        esac

        printf "  Model [%s]: " "$MODEL"
        read -r model_override
        [ -n "$model_override" ] && MODEL="$model_override"
    fi

    # Write config using printf (no Python dependency for this step)
    cat > "$CONFIG_FILE" << JSONEOF
{
  "theme": "phosphor",
  "provider": "$PROVIDER",
  "model": "$MODEL",
  "api_base": "$API_BASE",
  "api_key": "$API_KEY",
  "max_history": 500,
  "max_response_tokens": 4096,
  "cmd_timeout": 300,
  "timeout": 120,
  "stream": false,
  "debug": false,
  "max_memory_ctx": 512,
  "goal_max_steps": 1000,
  "subagent_model": "",
  "autosave_interval": 60
}
JSONEOF
    chmod 600 "$CONFIG_FILE" 2>/dev/null || true
    ok "Config written to $CONFIG_FILE"
fi

# ═══════════════════════════════════════════════════════════════
#  6. Summary
# ═══════════════════════════════════════════════════════════════
header "Step 6/6 - Complete"

printf "  ${BLD}Prism32 v6.8 installed!${RST}\n"
printf "\n"
printf "  ${DIM}Install location:${RST}  $RUNTIME_DIR\n"
printf "  ${DIM}Wrapper:${RST}           $WRAPPER\n"
printf "  ${DIM}Python:${RST}            $($PY3 --version 2>&1)\n"
printf "  ${DIM}Config:${RST}             $CONFIG_FILE\n"
printf "  ${DIM}Plugins:${RST}            $PLUGINS_DIR\n"
printf "\n"

# Check if the bin dir is in PATH permanently
if [ -n "$USB_DEST" ]; then
    # Check if profile.d exists
    if [ -d /etc/profile.d ]; then
        echo "export PATH=\"$BIN_DIR:\$PATH\"" > /etc/profile.d/prism32.sh 2>/dev/null || true
        ok "Added to PATH (reboot or: export PATH=$BIN_DIR:\$PATH)"
    else
        warn "Add to PATH: export PATH=$BIN_DIR:\$PATH"
    fi
fi

printf "  ${G}Run:${RST}  $NAME\n"
printf "\n"

if [ "$AUTO" = "0" ] && [ -t 0 ]; then
    printf "  Run Prism32 now? (Y/n): "
    read -r runnow
    case "$runnow" in
        n|N|no) ;;
        *) exec "$WRAPPER" ;;
    esac
fi

# Show router-specific tips
printf "  ${DIM}Router tips:${RST}\n"
printf "  ${DIM}  - Use /goal for autonomous multi-step tasks${RST}\n"
printf "  ${DIM}  - Low RAM? Use simpler models (Groq, Together)${RST}\n"
printf "  ${DIM}  - Remote access: ssh root@router 'prism32'{RST}\n"
if [ -z "$USB_DEST" ]; then
    printf "  ${DIM}  - Flash full? Install to USB: sh %s /mnt/usb${RST}\n" "$0"
fi
printf "\n"
