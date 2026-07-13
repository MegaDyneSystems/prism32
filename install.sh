#!/usr/bin/env bash
# ═══════════════════════════════════════════════════════════════
#  Prism32 — MegaDyne Systems Installer v6.9
#  Idempotent, validated, user-friendly
# ═══════════════════════════════════════════════════════════════
set -euo pipefail

# ── Defaults (must be set before any code references them) ─────
LOW_RAM=0

# Trap for cleanup on interrupt
_INSTALL_TMPFILES=""
trap 'rm -f $_INSTALL_TMPFILES 2>/dev/null || true' EXIT INT TERM HUP

# Pre-create runtime dir so log() works before Step 1
mkdir -p "$HOME/.prism32" 2>/dev/null || true

NAME="prism32"
# Resolve SRC_DIR from this script's location (works whether cloned to
# ~/prism32-project, ~/src/prism32, or anywhere else)
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SRC_DIR="$SCRIPT_DIR"
SRC_FILE="$SRC_DIR/prism32.py"
BIN="${PREFIX:-/usr/local}/bin/$NAME"
BIN_BACKUP="${PREFIX:-/usr/local}/bin/$NAME.bak.$(date +%s).$$"
RUNTIME_DIR="$HOME/.prism32"
SESSIONS_DIR="$RUNTIME_DIR/sessions"
SKILLS_DIR="$RUNTIME_DIR/skills"
PLUGINS_DIR="$RUNTIME_DIR/plugins"
EVOLVE_DIR="$RUNTIME_DIR/evolve"
CONFIG_FILE="$RUNTIME_DIR/config.json"
CONFIG_BACKUP="$RUNTIME_DIR/config.json.bak.$(date +%s).$$"
LOG_FILE="$RUNTIME_DIR/install.log"
NEED_ROOT=0
AUTO=0

# ── Find Python 3 (macOS frameworks, BSD pkgsrc, etc.) ──
PY3=""
if ! command -v python3 &>/dev/null; then
  for py in \
    /opt/homebrew/bin/python3 \
    /opt/local/bin/python3 \
    /Library/Frameworks/Python.framework/Versions/*/bin/python3 \
    /usr/pkg/bin/python3.[0-9]* \
    /usr/local/bin/python3 \
    /usr/bin/python3 \
  ; do
    [ -x "$py" ] && PY3="$py" && break
  done
  if [ -z "${PY3:-}" ]; then
    _os="$(uname -s)"
    case "$_os" in
      Darwin)  echo "Python 3 not found. Install via: brew install python3" ;;
      FreeBSD) echo "Python 3 not found. Install via: sudo pkg install python3" ;;
      NetBSD)  echo "Python 3 not found. Install via: pkgin install python311" ;;
      OpenBSD) echo "Python 3 not found. Install via: pkg_add python3" ;;
      Linux)   echo "Python 3 not found. Install via your package manager (apt/pacman/dnf/yum)" ;;
      *)       echo "Python 3 not found. Install from https://python.org" ;;
    esac
    exit 1
  fi
else
  PY3="python3"
fi

# ── ANSI + log helpers (needed early for macOS SSL fix) ──
RST='\033[0m'; BLD='\033[1m'; DIM='\033[2m'
G='\033[92m'; Y='\033[93m'; CY='\033[96m'; R='\033[91m'

log()   { echo -e "$(date '+%H:%M:%S') $*" >> "$LOG_FILE"; echo -e "$*"; }
ok()    { log "  ${G}*${RST} $*"; }
warn()  { log "  ${Y}w${RST} $*"; }
fail()  { log "  ${R}!${RST} $*"; }
header(){ echo -e "\n${CY}${BLD}--- $*${RST}"; }
sub()   { echo -e "  ${DIM}|${RST}  $*"; }

# ── macOS: fix SSL certificates ──
if [ "$(uname -s)" = "Darwin" ]; then
  "$PY3" -c "import urllib.request; urllib.request.urlopen('https://google.com', timeout=3)" 2>/dev/null ||
  {
    echo "  macOS SSL certificates need setup."
    shopt -s nullglob 2>/dev/null || true
    for s in "/Applications/Python 3.*/Install Certificates.command"; do
      [ -x "$s" ] && { "$s" 2>/dev/null && ok "SSL certificates installed" && break; } || true
    done
    shopt -u nullglob 2>/dev/null || true
    "$PY3" -m pip install --upgrade certifi 2>/dev/null || true
    # Verify
    "$PY3" -c "import urllib.request; urllib.request.urlopen('https://google.com', timeout=3)" 2>/dev/null \
      || warn "SSL still not working — run manually: open /Applications/Python\\ 3.9/Install\\ Certificates.command"
  }
fi

# Parse --yes / -y flag
for arg in "$@"; do
  if [ "$arg" = "--yes" ] || [ "$arg" = "-y" ]; then AUTO=1; fi
done

# ── Provider presets ──
EP_KEYS=(local ollama openai anthropic groq together openrouter neuralwatt custom)
EP_NAME=("Local LLaMA" "Ollama" "OpenAI" "Anthropic" "Groq" "Together AI" "OpenRouter" "Neuralwatt Cloud" "Custom")
EP_BASE=(
  "http://127.0.0.1:8080"         "http://localhost:11434/v1"
  "https://api.openai.com/v1"     "https://api.anthropic.com/v1"
  "https://api.groq.com/openai/v1" "https://api.together.xyz/v1"
  "https://openrouter.ai/api/v1"  "https://api.neuralwatt.com/v1"
  "http://localhost:8080"
)
EP_ENV=("" "" "OPENAI_API_KEY" "ANTHROPIC_API_KEY" "GROQ_API_KEY" "TOGETHER_API_KEY" "OPENROUTER_API_KEY" "NEURALWATT_API_KEY" "")
# Fallback models when live fetch fails
EP_MODELS_FALLBACK=(
  "model.gguf" "qwen3:14b" "gpt-4o" "claude-sonnet-4-20250514"
  "llama-3.3-70b-versatile" "meta-llama/Llama-3.3-70b"
  "openai/gpt-4o" "glm-5.2" "model-name"
)

# ═══════════════════════════════════════════════════════════════
#  BANNER
# ═══════════════════════════════════════════════════════════════
echo ""
echo -e "${CY}${BLD}  +========================================+${RST}"
echo -e "${CY}${BLD}  |       Prism32 Installer v6.9           |${RST}"
echo -e "${CY}${BLD}  |   MegaDyne Systems (MDS) Edition       |${RST}"
echo -e "${CY}${BLD}  +========================================+${RST}"
echo ""

rm -f "$LOG_FILE"
mkdir -p "$RUNTIME_DIR" 2>/dev/null || true

# ═══════════════════════════════════════════════════════════════
#  1. Validate source
# ═══════════════════════════════════════════════════════════════
header "Step 1/9 - Validating Source"

if [ ! -f "$SRC_FILE" ]; then
  fail "Source not found: $SRC_FILE"
  echo -e "  ${DIM}Expected: $SRC_DIR/prism32.py${RST}"
  echo -e "  ${DIM}Clone the repo first, then run this installer from the project dir.${RST}"
  exit 1
fi
ok "Source file: $SRC_FILE"
chmod +x "$SRC_FILE" && ok "Made executable"

if [ "$LOW_RAM" = "1" ]; then
  warn "Skipping py_compile syntax check to avoid OOM on low-RAM system."
else
  py_err="$("$PY3" -c "
import py_compile, sys
py_compile.compile(sys.argv[1], doraise=True)
" "$SRC_FILE" 2>&1)" && ok "Python syntax valid" \
    || { fail "Python syntax error"; echo -e "  ${R}$py_err${RST}"; exit 1; }
fi

# ═══════════════════════════════════════════════════════════════
#  2. Platform check
# ═══════════════════════════════════════════════════════════════
header "Step 2/9 - Platform Check"

echo -e "  ${DIM}OS:${RST}     $(uname -s)  $(uname -m)"
echo -e "  ${DIM}Python:${RST}  $("$PY3" --version 2>&1)"
echo -e "  ${DIM}User:${RST}    $(whoami)"

# Detect RAM (Linux/BSD /proc fallback; Darwin sysctl)
_RAM_KB=0
# Detect RAM (Linux /proc; BSD/macOS sysctl; unknown = 0)
_RAM_KB=0
if [ -r /proc/meminfo ]; then
  _RAM_KB=$(awk '/MemTotal/{print $2}' /proc/meminfo 2>/dev/null || echo 0)
elif command -v sysctl >/dev/null 2>&1; then
  _RAM_KB=$(sysctl -n hw.memsize 2>/dev/null | awk '{print int($1/1024)}' || echo 0)
fi
if [ "$_RAM_KB" -gt 0 ] && [ "$_RAM_KB" -lt 65536 ]; then
  LOW_RAM=1
  warn "Low RAM detected (~$((_RAM_KB / 1024)) MB). Parser may OOM on first run."
  sub "Tip: compile to .pyc on a host with more RAM and copy prism32.pyc here."
fi

if [ ! -w "${PREFIX:-/usr/local}/bin" ]; then
  NEED_ROOT=1
  if [ "$AUTO" = "0" ] && [ -z "${SU_PASS+x}" ] && [ -t 0 ]; then
    echo ""
    echo -e "  ${Y}w${RST} Root access required for symlink in /usr/local/bin/"
    echo -n "  Root password: "; read -rs SU_PASS || true; echo ""
  fi
fi

root() {
  if [ "$NEED_ROOT" = "1" ]; then
    if [ -n "${SU_PASS:-}" ]; then
      echo "$SU_PASS" | su -c "$*" 2>/dev/null || echo "$SU_PASS" | sudo -S sh -c "$*" 2>/dev/null
    elif [ "$AUTO" = "1" ]; then
      return 0
    else
      su -c "$*" 2>/dev/null || sudo sh -c "$*" 2>/dev/null
    fi
  else
    eval "$*"
  fi
}

# ═══════════════════════════════════════════════════════════════
#  3. Backup
# ═══════════════════════════════════════════════════════════════
header "Step 3/9 - Backing Up"

backups=0
if [ -f "$BIN" ] || [ -L "$BIN" ]; then
  if root cp -P "$BIN" "$BIN_BACKUP"; then
    ok "Backed up $BIN"
    backups=$((backups+1))
    root rm -f "$BIN"
  else
    fail "Backup failed — keeping existing binary, aborting"
    exit 1
  fi
fi
if [ -f "$CONFIG_FILE" ]; then
  cp "$CONFIG_FILE" "$CONFIG_BACKUP" && ok "Backed up config" && backups=$((backups+1))
fi
[ "$backups" -eq 0 ] && ok "Nothing to back up"

# ═══════════════════════════════════════════════════════════════
#  4. Symlink + directories
# ═══════════════════════════════════════════════════════════════
header "Step 4/9 - Installing"

_install_wrapper() {
  local target="$1"
  mkdir -p "$(dirname "$target")"
  mkdir -p "$RUNTIME_DIR"
  local local_py="$RUNTIME_DIR/prism32.py"
  cp "$SRC_FILE" "$local_py" && ok "Copied prism32.py to $RUNTIME_DIR"
  if [ "$LOW_RAM" != "1" ]; then
    # Generate .pyc for faster startup and lower memory on embedded targets
    "$PY3" -c "import py_compile, sys; py_compile.compile(sys.argv[1], doraise=True)" "$local_py" 2>/dev/null && ok "Generated .pyc bytecode" || true
  fi
  cat > "$target" << WRAP
#!/bin/sh
exec "$PY3" "$local_py" "\$@"
WRAP
  chmod +x "$target"
}

if [ "$AUTO" = "1" ] && [ "$NEED_ROOT" = "1" ]; then
  LOCAL_BIN="${HOME}/.local/bin"
  mkdir -p "$LOCAL_BIN"
  _install_wrapper "$LOCAL_BIN/$NAME"
  ok "Wrapper: $LOCAL_BIN/$NAME"
  export PATH="$LOCAL_BIN:$PATH"
elif [ "$NEED_ROOT" = "1" ]; then
  mkdir -p "$RUNTIME_DIR"
  cp "$SRC_FILE" "$RUNTIME_DIR/prism32.py" 2>/dev/null || true
  TMP_WRAP="$(mktemp)"
  _INSTALL_TMPFILES="$_INSTALL_TMPFILES $TMP_WRAP"
  cat > "$TMP_WRAP" << WRAP
#!/bin/sh
exec "$PY3" "$RUNTIME_DIR/prism32.py" "\$@"
WRAP
  chmod +x "$TMP_WRAP"
  root cp "$TMP_WRAP" "$BIN" && root chmod 755 "$BIN" && ok "Wrapper: $BIN" || { fail "Install failed"; rm -f "$TMP_WRAP"; exit 1; }
  rm -f "$TMP_WRAP"
else
  _install_wrapper "$BIN" && ok "Wrapper: $BIN" || { fail "Install failed"; exit 1; }
fi
hash -r 2>/dev/null || true

mkdir -p "$RUNTIME_DIR" "$SESSIONS_DIR" "$SKILLS_DIR" "$PLUGINS_DIR" "$EVOLVE_DIR" && ok "Directories created"
touch "$LOG_FILE"

# Copy bundled default plugins from repo into runtime plugin dir
if [ -d "$SRC_DIR/plugins" ]; then
  for p in "$SRC_DIR/plugins/"*.py; do
    [ -f "$p" ] || continue
    bn=$(basename "$p")
    [ "$bn" = "__init__.py" ] && continue
    if [ ! -f "$PLUGINS_DIR/$bn" ]; then
      cp "$p" "$PLUGINS_DIR/$bn" && ok "Plugin copied: $bn"
    fi
  done
fi

# ═══════════════════════════════════════════════════════════════
#  5. API config (multi-provider) — skipped in auto mode if config exists
# ═══════════════════════════════════════════════════════════════
header "Step 5/9 - API Configuration"

# In auto-update mode, preserve existing config — don't clobber provider info
if [ "$AUTO" = "1" ] && [ -f "$CONFIG_FILE" ]; then
  ok "Auto-update mode: preserving existing config (provider, model, API key)"
  # Load current values from config so Steps 6-9 have them
  eval "$("$PY3" -c "
import json, sys
c = json.load(open(sys.argv[1]))
print(f'PROV=\"{c.get(\"provider\",\"local\")}\"')
print(f'MODEL=\"{c.get(\"model\",\"\")}\"')
print(f'API_BASE=\"{c.get(\"api_base\",\"\")}\"')
" "$CONFIG_FILE" 2>/dev/null)" 2>/dev/null || {
    PROV="local"; MODEL=""; API_BASE="http://127.0.0.1:8080"
  }
  ALL_PROVIDERS="{}"
  # Skip to step 6
  skip_config_write=1
else
  skip_config_write=0
  ALL_PROVIDERS="{}"

_configure_provider() {
  echo ""
  for i in "${!EP_KEYS[@]}"; do
    echo -e "  ${BLD}$((i+1)))${RST} ${EP_NAME[$i]}  ${DIM}${EP_BASE[$i]}${RST}"
  done
  echo ""

  sel="${PROVIDER_SELECT:-}"
  if [ -z "$sel" ] && [ -t 0 ]; then
    read -r -p "  Select provider [1-${#EP_KEYS[@]}] (default: 1): " sel
  fi
  sel="${sel:-1}"
  idx=$((sel - 1))
  [ "$idx" -ge 0 ] && [ "$idx" -lt "${#EP_KEYS[@]}" ] || idx=0
  local prov="${EP_KEYS[$idx]}"
  local pname="${EP_NAME[$idx]}"
  local pidx=$idx
  sub "Provider: $pname"

  local api_default="${EP_BASE[$pidx]}"
  local api_val=""
  if [ -t 0 ]; then
    read -r -p "  API endpoint [$api_default]: " api_val
  fi
  local api_base="${api_val:-$api_default}"
  sub "Endpoint: $api_base"

  local api_key_env="${EP_ENV[$pidx]}"
  local api_key_val=""
  if [ -n "$api_key_env" ] && [ -t 0 ]; then
    local current_key="${!api_key_env:-}"
    if [ -z "$current_key" ]; then
      read -rs -p "  $api_key_env: " api_key_val; echo
    else
      api_key_val="$current_key"
      ok "$api_key_env found in environment"
    fi
  fi

  # Fetch live model list
  echo ""
  echo -e "  ${DIM}Fetching available models...${RST}"
  local models_raw
  models_raw=$("$PY3" -c "
import urllib.request, json, sys
try:
    url = sys.argv[1] + '/models'
    req = urllib.request.Request(url)
    if sys.argv[2]:
        req.add_header('Authorization', 'Bearer ' + sys.argv[2])
    with urllib.request.urlopen(req, timeout=8) as r:
        data = json.loads(r.read())
        models = [m.get('id', m.get('name', '')) for m in data.get('data', data.get('models', [])) if m.get('id') or m.get('name')]
        print('|'.join(models[:200]) if models else 'FAIL')
except Exception:
    print('FAIL')
" "$api_base" "$api_key_val" 2>/dev/null)
  local model_name=""
  if [ "$models_raw" = "FAIL" ] || [ -z "$models_raw" ]; then
    local fb="${EP_MODELS_FALLBACK[$pidx]}"
    echo -e "  ${Y}w${RST} Could not fetch models — enter manually"
    if [ -t 0 ]; then
      read -r -p "  Model name [$fb]: " model_name
    fi
    model_name="${model_name:-$fb}"
  else
    IFS='|' read -ra MODELS <<< "$models_raw"
    echo -e "  ${DIM}Available models:${RST}"
    local max_show=30
    [ "${#MODELS[@]}" -lt "$max_show" ] && max_show="${#MODELS[@]}"
    local i=0; while [ "$i" -lt "$max_show" ]; do
      printf "  ${BLD}%2d)${RST} ${MODELS[$i]}\n" $((i+1))
      i=$((i+1))
    done
    if [ "${#MODELS[@]}" -gt "$max_show" ]; then
      echo -e "  ${DIM}  ... and $((${#MODELS[@]} - max_show)) more${RST}"
    fi
    echo ""
    local mdl_sel=""
    if [ -t 0 ]; then
      read -r -p "  Select model [1-${#MODELS[@]}] (default: 1): " mdl_sel
    fi
    mdl_sel="${mdl_sel:-1}"
    local mdl_idx=$((mdl_sel - 1))
    [ "$mdl_idx" -ge 0 ] && [ "$mdl_idx" -lt "${#MODELS[@]}" ] || mdl_idx=0
    model_name="${MODELS[$mdl_idx]}"
  fi
  sub "Model: $model_name"

  # Build JSON snippet for this provider
  local json_entry
  json_entry=$("$PY3" -c "
import json, sys
d = {'api_base': sys.argv[1], 'model': sys.argv[2]}
if sys.argv[3]: d['api_key'] = sys.argv[3]
print(json.dumps(d))
" "$api_base" "$model_name" "$api_key_val")
  ALL_PROVIDERS=$("$PY3" -c "
import json, sys
all_p = json.loads(sys.argv[1])
all_p[sys.argv[2]] = json.loads(sys.argv[3])
print(json.dumps(all_p))
" "$ALL_PROVIDERS" "$prov" "$json_entry")

  # Set as active if first provider
  if [ -z "${PROV:-}" ]; then
    PROV="$prov"
    API_BASE="$api_base"
    MODEL="$model_name"
    api_key="${api_key_val:-}"
  fi
}

# First provider
_configure_provider

# Ask for more
while [ -t 0 ]; do
  echo ""
  read -r -p "  Configure another provider? (y/N): " more
  more="${more:-n}"
  [ "$more" != "y" ] && [ "$more" != "Y" ] && [ "$more" != "yes" ] && break
  _configure_provider
done

fi  # end of else (non-auto or no config)

# ═══════════════════════════════════════════════════════════════
#  6. Connection test
# ═══════════════════════════════════════════════════════════════
header "Step 6/9 - Connection Test"

_test_url() {
  "$PY3" -c "
import urllib.request
try:
    req = urllib.request.Request('$1')
    with urllib.request.urlopen(req, timeout=5) as r:
        print(r.status)
except Exception as e:
    print(type(e).__name__)
" 2>/dev/null || echo "timeout"
}

echo -e "  ${DIM}Testing $API_BASE/models ...${RST}"
rc="$(_test_url "${API_BASE}/models")"
[ "$rc" = "200" ] && ok "API reachable" || {
  echo -e "  ${DIM}Testing $API_BASE/v1/models ...${RST}"
  rc2="$(_test_url "${API_BASE}/v1/models")"
  [ "$rc2" = "200" ] && ok "API reachable (via /v1)" || warn "Cannot reach API — verify later"
}

# ═══════════════════════════════════════════════════════════════
#  7. Write config
# ═══════════════════════════════════════════════════════════════

header "Step 7/9 - Writing Config"

if [ "$skip_config_write" = "1" ]; then
  ok "Config preserved (auto-update mode)"
elif [ -f "$CONFIG_FILE" ]; then
  "$PY3" -c "
import json, sys
c = json.load(open(sys.argv[1]))
c['provider'] = sys.argv[2]
c['model'] = sys.argv[3]
c['api_base'] = sys.argv[4]
c['providers'] = json.loads(sys.argv[5])
json.dump(c, open(sys.argv[1], 'w'), indent=2)
" "$CONFIG_FILE" "$PROV" "$MODEL" "$API_BASE" "$ALL_PROVIDERS" && ok "Config updated" || { fail "Config write failed"; exit 1; }
else
  cat > "$CONFIG_FILE" << JSONEOF
{
  "theme": "phosphor",
  "provider": "$PROV",
  "model": "$MODEL",
  "api_base": "$API_BASE",
  "providers": $ALL_PROVIDERS,
  "max_history": 2000,
  "max_tokens": 8192,
  "cmd_timeout": 600,
  "timeout": 120,
  "stream": false,
  "debug": false,
  "no_boot": false,
  "max_memory_ctx": 1024,
  "subagent_model": ""
}
JSONEOF
  "$PY3" -c "import json, sys; json.load(open(sys.argv[1]))" "$CONFIG_FILE" \
    && ok "Config written" \
    || { fail "Config JSON invalid"; exit 1; }
  chmod 600 "$CONFIG_FILE" 2>/dev/null || true
fi

echo ""
"$PY3" -c "
import json, sys
c = json.load(open(sys.argv[1]))
for k, v in c.items():
    print(f'    ${DIM}{k}:${RST} {v}')
" "$CONFIG_FILE" 2>/dev/null || true

# ═══════════════════════════════════════════════════════════════
#  8. Dependencies
# ═══════════════════════════════════════════════════════════════
header "Step 8/9 - Dependencies"

"$PY3" -c "import urllib.request, json, subprocess, shutil, socket, threading, queue" 2>/dev/null \
  && ok "All stdlib modules available" \
  || warn "Missing stdlib modules — check Python installation"

py_ver="$("$PY3" -c "import sys; print(f'{sys.version_info.major}.{sys.version_info.minor}')")"
if "$PY3" -c "import sys; exit(0 if sys.version_info >= (3,7) else 1)" 2>/dev/null; then
  ok "Python $py_ver (>= 3.7)"
else
  warn "Python $py_ver — upgrade to >= 3.7 for best compatibility"
fi

echo -e "  ${DIM}Refreshing startup memory, harness scan, and evolve baseline...${RST}"
"$PY3" "$SRC_FILE" --setup-runtime >/dev/null 2>&1 \
  && ok "Runtime memory/harness/evolve setup complete" \
  || warn "Runtime setup skipped — run: prism32 --setup-runtime"

# ═══════════════════════════════════════════════════════════════
#  9. Verify
# ═══════════════════════════════════════════════════════════════
header "Step 9/9 - Verification"

hash -r 2>/dev/null || true
CMD_PATH="$(command -v "$NAME" 2>/dev/null)"
[ -n "$CMD_PATH" ] && ok "Command: $CMD_PATH" || warn "Not in PATH — try: export PATH=\"\$HOME/.local/bin:\$PATH\""

HELP_OUT="$("$PY3" "$SRC_FILE" --help 2>&1 | head -3)"
echo ""
echo -e "  ${DIM}$HELP_OUT${RST}"
echo ""
sub "Skills:     $SKILLS_DIR"
sub "Plugin dir: $PLUGINS_DIR"
sub "Startup memory: $RUNTIME_DIR/startup_memory.md"
sub "Harnesses:  $RUNTIME_DIR/harnesses.json"
sub "Evolve:     $EVOLVE_DIR"
sub "Sessions:   $SESSIONS_DIR"
sub "Soul:       $RUNTIME_DIR/soul.md"
sub "Config:     $CONFIG_FILE"
sub "Log:        $LOG_FILE"

# ═══════════════════════════════════════════════════════════════
#  SUMMARY
# ═══════════════════════════════════════════════════════════════
echo ""
echo -e "${G}${BLD}  +========================================+${RST}"
echo -e "${G}${BLD}  |      Installation Complete             |${RST}"
echo -e "${G}${BLD}  +========================================+${RST}"
echo ""
# Find provider display name from PROV key
for i in "${!EP_KEYS[@]}"; do
  [ "${EP_KEYS[$i]}" = "$PROV" ] && prov_name="${EP_NAME[$i]}" && break
done
echo -e "  ${BLD}Provider:${RST}  ${prov_name:-$PROV}"
echo -e "  ${BLD}Endpoint:${RST}  $API_BASE"
echo -e "  ${BLD}Model:${RST}     $MODEL"
echo ""
echo -e "  ${CY}Run:  prism32${RST}"
echo -e "  ${CY}Help: prism32 --help${RST}"
echo ""

if [ -n "${api_key+x}" ]; then
  echo -e "  ${Y}w${RST} API key set in shell only. Use /provider key inside Prism32 to persist."
  echo ""
fi

if [ "$LOW_RAM" = "1" ]; then
  echo -e "  ${Y}w${RST} Low-RAM device detected."
  echo -e "     Compile .pyc on a machine with more RAM:"
  echo -e "     ${CY}python3.7 -m py_compile prism32.py${RST}"
  echo -e "     Then copy ${CY}prism32.pyc${RST} to this device and run:"
  echo -e "     ${CY}python3 prism32.pyc${RST}"
  echo ""
fi

echo -e "${DIM}  MegaDyne Systems (MDS) — Prism32 v6.9${RST}"
echo ""

# vim: set ts=2 sw=2 et:
