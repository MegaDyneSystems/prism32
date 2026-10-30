#!/usr/bin/env bash
# ═══════════════════════════════════════════════════════════════
#  Prism32 — MegaDyne Systems Installer v7.2
#  Idempotent, validated, user-friendly
# ═══════════════════════════════════════════════════════════════
set -euo pipefail

# ── Defaults (must be set before any code references them) ─────
LOW_RAM=0

# Trap for cleanup on interrupt
_INSTALL_TMPFILES=""
trap 'rm -f $_INSTALL_TMPFILES 2>/dev/null || true' EXIT INT TERM HUP

# Pre-create runtime dir so log() works before Step 1. Resolution ladder
# (must stay in sync with prism32.py's _resolve_prism32_home):
#   1. ~/.prism32                          — the normal case
#   2. $XDG_DATA_HOME/prism32              — if set
#   3. /volume1/homes/<user>/.prism32       — Synology DSM: $HOME dangles
#      (/var/services/homes -> missing target) but /volume1/homes/<user> is
#      the real, persistent, exec-capable home
#   4. /volume1/<user>/.prism32            — secondary DSM location
#   5. /tmp/prism32                        — volatile LAST resort (DSM /tmp is
#                                            noexec AND tmpfs-wiped on reboot)
_resolve_runtime_base() {
  if mkdir -p "$HOME/.prism32" 2>/dev/null && [ -w "$HOME/.prism32" ]; then
    printf '%s\n' "$HOME/.prism32"; return 0
  fi
  if [ -n "${XDG_DATA_HOME:-}" ] && mkdir -p "$XDG_DATA_HOME/prism32" 2>/dev/null && [ -w "$XDG_DATA_HOME/prism32" ]; then
    printf '%s\n' "$XDG_DATA_HOME/prism32"; return 0
  fi
  if [ -d /volume1 ]; then
    _nas_user="$(id -un 2>/dev/null || true)"
    if [ -n "$_nas_user" ]; then
      for _vh in "/volume1/homes/$_nas_user" "/volume1/$_nas_user"; do
        if mkdir -p "$_vh/.prism32" 2>/dev/null && [ -w "$_vh/.prism32" ]; then
          printf '%s\n' "$_vh/.prism32"; return 0
        fi
      done
    fi
  fi
  mkdir -p /tmp/prism32 2>/dev/null || true
  printf '%s\n' "/tmp/prism32"
}

RUNTIME_BASE="$(_resolve_runtime_base)"
ALT_HOME=""
case "$RUNTIME_BASE" in
  "$HOME/.prism32") ;;
  /tmp/prism32)
    echo "  ! No persistent writable home found — runtime dir: $RUNTIME_BASE (volatile!)"
    echo "  ! On Synology DSM: enable the user home service (Control Panel ->"
    echo "  ! User & Group -> Advanced) or run with HOME=/volume1/homes/\$(id -un)" ;;
  *)
    ALT_HOME="$(dirname "$RUNTIME_BASE")"
    echo "  ! Home not usable ($HOME) — using persistent NAS location instead"
    echo "  ! Runtime dir: $RUNTIME_BASE" ;;
esac

NAME="prism32"
# Resolve SRC_DIR from this script's location (works whether cloned to
# ~/prism32-project, ~/src/prism32, or anywhere else)
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SRC_DIR="$SCRIPT_DIR"
SRC_FILE="$SRC_DIR/prism32.py"
BIN="${PREFIX:-/usr/local}/bin/$NAME"
BIN_BACKUP="${PREFIX:-/usr/local}/bin/$NAME.bak.$(date +%s).$$"
RUNTIME_DIR="$RUNTIME_BASE"
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
      NetBSD)  echo "Python 3 not found. Install via: pkgin install python312" ;;
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
echo -e "${CY}${BLD}  |       Prism32 Installer v7.2           |${RST}"
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

# Detect RAM BEFORE the syntax check — a 32-64MB device must not run
# py_compile (the very OOM LOW_RAM mode exists to prevent); this block
# used to live in Step 2, after the check.
_RAM_KB=0
if [ -r /proc/meminfo ]; then
  _RAM_KB=$(awk '/MemTotal/{print $2}' /proc/meminfo 2>/dev/null || echo 0)
elif command -v sysctl >/dev/null 2>&1; then
  case "$(uname -s)" in
    NetBSD) _MEM=$(sysctl -n hw.physmem 2>/dev/null || echo 0) ;;
    *) _MEM=$(sysctl -n hw.memsize 2>/dev/null || echo 0) ;;
  esac
  _RAM_KB=$(echo "$_MEM" | awk '{print int($1/1024)}')
fi
if [ "$_RAM_KB" -gt 0 ] && [ "$_RAM_KB" -lt 65536 ]; then
  LOW_RAM=1
  warn "Low RAM detected (~$((_RAM_KB / 1024)) MB). Parser may OOM on first run."
  sub "Tip: compile to .pyc on a host with more RAM and copy prism32.pyc here."
fi

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
echo -e "  ${DIM}Python:${RST}  $("$PY3" --version 2>&1)${DIM} ($PY3)${RST}"
echo -e "  ${DIM}User:${RST}    $(whoami)"

# A PREFIX whose bin/ doesn't exist yet is not a root problem — create it
# (a nonexistent dir used to fail -w and misroute the wrapper to ~/.local/bin).
if [ ! -d "${PREFIX:-/usr/local}/bin" ] && ! mkdir -p "${PREFIX:-/usr/local}/bin" 2>/dev/null; then
  NEED_ROOT=1
fi
if [ ! -w "${PREFIX:-/usr/local}/bin" ]; then
  NEED_ROOT=1
  if [ "$AUTO" = "0" ] && [ -z "${SU_PASS+x}" ] && [ -t 0 ]; then
    echo ""
    echo -e "  ${Y}w${RST} Root access required for symlink in ${PREFIX:-/usr/local}/bin/"
    echo -n "  Root password: "; read -rs SU_PASS || true; echo ""
  fi
fi

root() {
  if [ "$NEED_ROOT" = "1" ]; then
    if [ -n "${SU_PASS:-}" ]; then
      echo "$SU_PASS" | su root -c "$*" 2>/dev/null || echo "$SU_PASS" | sudo -S sh -c "$*" 2>/dev/null
    elif [ "$AUTO" = "1" ]; then
      return 0
    else
      # `su root -c` (not `su -c`): NetBSD su rejects userless -c for non-root
      # ("Only root may use -c"), while Linux/macOS accept both forms.
      su root -c "$*" 2>/dev/null || sudo sh -c "$*" 2>/dev/null
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
if [ "$AUTO" = "1" ] && [ "$NEED_ROOT" = "1" ]; then
  # root() no-ops in auto mode without credentials — don't claim backups
  # that were never made; leave existing files untouched and let the
  # per-user path take over.
  ok "Auto mode, no root credentials — leaving system paths untouched"
elif [ -f "$BIN" ] || [ -L "$BIN" ]; then
  # -L (not the invalid -l): a dangling symlink from a broken prior
  # install must still be detected, or the backup branch is skipped and
  # the wrapper write below dies writing THROUGH the dead link.
  if root cp -P "$BIN" "$BIN_BACKUP"; then
    ok "Backed up $BIN"
    backups=$((backups+1))
    root rm -f "$BIN" || warn "Could not remove old $BIN (backup at $BIN_BACKUP)"
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
  # Prefer ~/.local/bin; on NAS/DSM with an unusable $HOME, try the persistent
  # volume location before volatile (usually noexec) /tmp.
  LOCAL_BIN=""
  if mkdir -p "${HOME}/.local/bin" 2>/dev/null && [ -w "${HOME}/.local/bin" ]; then
    LOCAL_BIN="${HOME}/.local/bin"
  elif [ -n "$ALT_HOME" ] && mkdir -p "${ALT_HOME}/.local/bin" 2>/dev/null && [ -w "${ALT_HOME}/.local/bin" ]; then
    LOCAL_BIN="${ALT_HOME}/.local/bin"
  elif [ "$RUNTIME_BASE" != "/tmp/prism32" ] && mkdir -p "${RUNTIME_BASE}/bin" 2>/dev/null && [ -w "${RUNTIME_BASE}/bin" ]; then
    LOCAL_BIN="${RUNTIME_BASE}/bin"
  else
    LOCAL_BIN="${RUNTIME_BASE}/bin"
    mkdir -p "$LOCAL_BIN"
  fi
  # noexec mounts (Synology DSM /tmp is noexec): a wrapper there can't run — verify first
  printf '#!/bin/sh\nexit 0\n' > "$LOCAL_BIN/.exectest.$$"
  chmod +x "$LOCAL_BIN/.exectest.$$" 2>/dev/null
  if "$LOCAL_BIN/.exectest.$$" 2>/dev/null; then
    rm -f "$LOCAL_BIN/.exectest.$$"
  else
    rm -f "$LOCAL_BIN/.exectest.$$"
    warn "Local bin dir is noexec — skipping wrapper"
    warn "Run prism32 via: $PY3 $RUNTIME_DIR/prism32.py"
    unset LOCAL_BIN
  fi
  if [ -n "${LOCAL_BIN:-}" ]; then
    _install_wrapper "$LOCAL_BIN/$NAME"
    ok "Wrapper: $LOCAL_BIN/$NAME"
    export PATH="$LOCAL_BIN:$PATH"
    # Persist PATH for fresh logins — previously only this process got the
    # export, so /bin/sh NAS logins never found the wrapper (and could find a
    # stale prism32 elsewhere in PATH instead).
    _persist_path_line() {
      # Never return non-zero: install.sh runs under `set -e`, so a failed
      # PATH persistence (broken $HOME) must be skipped, not abort Step 4.
      # Never mkdir either — creating the parent of .profile could resurrect
      # a dangling $HOME symlink (DSM /var/services/homes -> missing target).
      _pf="$1"
      _pd="$(dirname "$_pf")"
      [ -d "$_pd" ] || return 0
      [ -w "$_pd" ] || return 0
      grep -qs '# Added by prism32 installer' "$_pf" 2>/dev/null && return 0
      printf '\n# Added by prism32 installer\n[ -d "%s" ] && PATH="%s:$PATH"\nexport PATH\n' "$LOCAL_BIN" "$LOCAL_BIN" >> "$_pf" 2>/dev/null \
        && ok "PATH updated: $_pf" || true
    }
    [ -n "$ALT_HOME" ] && _persist_path_line "$ALT_HOME/.profile"
    _persist_path_line "$HOME/.profile"
    _persist_path_line "$HOME/.bashrc"
  else
    _install_wrapper_runonly=1
    mkdir -p "$RUNTIME_DIR"
    cp "$SRC_FILE" "$RUNTIME_DIR/prism32.py" && ok "Copied prism32.py to $RUNTIME_DIR"
    if [ "$LOW_RAM" != "1" ]; then
      "$PY3" -c "import py_compile, sys; py_compile.compile(sys.argv[1], doraise=True)" "$RUNTIME_DIR/prism32.py" 2>/dev/null && ok "Generated .pyc bytecode" || true
    fi
  fi
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
  SYSTEM_BIN_INSTALLED=1
  # Best-effort PATH persistence for system installs (openwrt-install.sh
  # pattern): non-interactive /bin/sh logins (Synology DSM) source nothing.
  if [ -d /etc/profile.d ]; then
    _PFX="${PREFIX:-/usr/local}"
    root "printf '%s\n' 'PATH=\"$_PFX/bin:\$PATH\"' 'export PATH' > /etc/profile.d/prism32.sh" 2>/dev/null \
      && root chmod 755 /etc/profile.d/prism32.sh 2>/dev/null \
      && ok "PATH updated: /etc/profile.d/prism32.sh" || true
  fi
else
  _install_wrapper "$BIN" && ok "Wrapper: $BIN" || { fail "Install failed"; exit 1; }
  SYSTEM_BIN_INSTALLED=1
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
  # Validate first: a corrupt config must not be silently "preserved"
  # (the old path claimed preservation while substituting defaults).
  if ! "$PY3" -c "import json, sys; json.load(open(sys.argv[1]))" "$CONFIG_FILE" >/dev/null 2>&1; then
    warn "Config is corrupt — quarantining (kept as config.json.corrupt.<ts>)"
    mv "$CONFIG_FILE" "$CONFIG_FILE.corrupt.$(date +%s)" 2>/dev/null || true
    PROV="local"; MODEL=""; API_BASE="http://127.0.0.1:8080"
    ALL_PROVIDERS="{}"
    skip_config_write=0
  else
    ok "Auto-update mode: preserving existing config (provider, model, API key)"
    # Load current values so Steps 6-9 have them. shlex.quote: these
    # assignments are eval'd — a quote/backtick/$(...) in a config value
    # used to execute arbitrary shell code on every update run.
    eval "$("$PY3" -c "
import json, shlex, sys
c = json.load(open(sys.argv[1]))
print('PROV=' + shlex.quote(str(c.get('provider', 'local'))))
print('MODEL=' + shlex.quote(str(c.get('model', ''))))
print('API_BASE=' + shlex.quote(str(c.get('api_base', ''))))
" "$CONFIG_FILE")" || {
      PROV="local"; MODEL=""; API_BASE="http://127.0.0.1:8080"
    }
    ALL_PROVIDERS="{}"
    skip_config_write=1
  fi
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
    read -r -p "  Select provider [1-${#EP_KEYS[@]}] (default: 1): " sel || sel=""
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
    read -r -p "  API endpoint [$api_default]: " api_val || api_val=""
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
      read -r -p "  Model name [$fb]: " model_name || model_name=""
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
      read -r -p "  Select model [1-${#MODELS[@]}] (default: 1): " mdl_sel || mdl_sel=""
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
if [ "$AUTO" = "1" ]; then
  # Auto mode, no existing config: write neutral local defaults. Previously
  # the interactive menu ran anyway — piped/non-tty installs dumped the whole
  # 9-provider menu to the pipe and silently configured a dead endpoint.
  ok "Auto mode: skipping interactive provider setup"
  sub "Defaults: local provider @ http://127.0.0.1:8080"
  sub "Run 'prism32' then /provider to configure a real endpoint"
  PROV="local"
  API_BASE="http://127.0.0.1:8080"
  MODEL=""
  api_key=""
else
  _configure_provider

  # Ask for more
  while [ -t 0 ]; do
    echo ""
    read -r -p "  Configure another provider? (y/N): " more || more=""
    more="${more:-n}"
    [ "$more" != "y" ] && [ "$more" != "Y" ] && [ "$more" != "yes" ] && break
    _configure_provider
  done
fi

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
else
  if [ ! -f "$CONFIG_FILE" ]; then
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
  fi
  # Merge/normalize via Python in BOTH paths: provider fields, the installer
  # providers section, and — critically — the ACTIVE provider's key lifted to
  # top-level api_key so prism32 has a working key on first boot.
  "$PY3" -c "
import json, sys
path, prov, model, base, allp = sys.argv[1:6]
c = {}
try:
    c = json.load(open(path)) or {}
except Exception:
    c = {}
c['provider'] = prov
c['model'] = model
c['api_base'] = base
c.setdefault('providers', {}).update(json.loads(allp))
k = (c.get('providers') or {}).get(prov, {}).get('api_key', '')
if k:
    # switching providers — the ACTIVE provider's key must reach
    # top-level api_key or the old provider's key 401s after reinstall
    c['api_key'] = k
json.dump(c, open(path, 'w'), indent=2)
" "$CONFIG_FILE" "$PROV" "$MODEL" "$API_BASE" "$ALL_PROVIDERS" \
    && ok "Config written (active key is top-level api_key)" \
    || { fail "Config write failed"; exit 1; }
  chmod 600 "$CONFIG_FILE" 2>/dev/null || true
fi

# Remember the root password collected earlier, so the AGENT can use it too
# (auto-fed to its su/sudo commands via pty). Without this, the password
# given at install was lost the moment the installer exited and every later
# agent root command failed auth. Interactive only; auto mode never collects
# SU_PASS in the first place.
if [ -n "${SU_PASS:-}" ] && [ -t 0 ]; then
  echo -n "  Remember this root password for the agent (su/sudo)? [Y/n] "
  read -r _rp_ok || _rp_ok=""
  case "$_rp_ok" in
    n*|N*)
      echo -e "  ${DIM}Not stored. Set it anytime inside prism32: /rootpass <pw>${RST}" ;;
    *)
      PRISM32_ROOT_PASS="$SU_PASS" "$PY3" - "$CONFIG_FILE" <<'PYEOF'
import json, os, sys
path = sys.argv[1]
pw = os.environ.pop('PRISM32_ROOT_PASS', '')
try:
    c = json.load(open(path)) or {}
except Exception:
    c = {}
c['root_pass'] = pw
json.dump(c, open(path, 'w'), indent=2)
PYEOF
      chmod 600 "$CONFIG_FILE" 2>/dev/null || true
      echo -e "  ${G}+${RST} Root password stored in config (chmod 600) — agent su/sudo now work"
      ;;
  esac
fi

echo ""
# Mask secrets: this dump used to print api_key and root_pass in cleartext
# into piped logs and terminal recordings.
"$PY3" -c "
import json, sys
c = json.load(open(sys.argv[1]))
for k, v in c.items():
    if k in ('api_key', 'root_pass') and v:
        v = str(v)[:4] + '***'
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
# Verify the wrapper THIS install actually wrote — `command -v` alone reports
# any stale prism32 earlier in PATH (a v6.x leftover at /usr/bin on a NAS was
# previously shown as a successful v7 install).
INSTALLED_WRAPPER=""
if [ -n "${LOCAL_BIN:-}" ] && [ -x "$LOCAL_BIN/$NAME" ]; then
  INSTALLED_WRAPPER="$LOCAL_BIN/$NAME"
elif [ -n "${SYSTEM_BIN_INSTALLED:-}" ] && [ -x "$BIN" ]; then
  INSTALLED_WRAPPER="$BIN"
fi
# Resolve against a fresh login's PATH — the installer's own export
# (LOCAL_BIN prepended) would always find the new wrapper first and mask
# any stale prism32 shadowing it in default shells. `|| true`: user-mode
# installs put the wrapper in ~/.local/bin, which is NOT on this restricted
# PATH — command -v exits 1 and `set -e` killed the whole install at Step 9
# ("Install failed" with empty output; only system-path installs survived).
LOGIN_CMD_PATH="$(PATH="/usr/local/bin:/usr/bin:/bin:/usr/sbin:/sbin" command -v "$NAME" 2>/dev/null || true)"
if [ -n "$INSTALLED_WRAPPER" ]; then
  if [ "$LOGIN_CMD_PATH" = "$INSTALLED_WRAPPER" ]; then
    ok "Command: $INSTALLED_WRAPPER"
  elif [ -n "$LOGIN_CMD_PATH" ]; then
    warn "Another prism32 shadows this install in default PATH:"
    sub "in PATH:  $LOGIN_CMD_PATH"
    sub "installed: $INSTALLED_WRAPPER"
    sub "Use the full path, or move $INSTALLED_WRAPPER earlier in PATH"
  else
    warn "Wrapper not on default PATH (fresh interactive logins pick it up via .profile)"
    sub "Installed: $INSTALLED_WRAPPER"
  fi
elif [ -n "$LOGIN_CMD_PATH" ]; then
  warn "Found unrelated prism32 in PATH: $LOGIN_CMD_PATH (not from this install)"
else
  warn "No launcher installed (run-only copy). Start with:"
  sub "$PY3 $RUNTIME_DIR/prism32.py"
fi

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
echo -e "  ${BLD}Model:${RST}     ${MODEL:-<unset — run /provider in prism32>}"
echo ""
if [ -n "$INSTALLED_WRAPPER" ]; then
  echo -e "  ${CY}Run:  $INSTALLED_WRAPPER${RST}"
elif [ "${_install_wrapper_runonly:-0}" = "1" ]; then
  echo -e "  ${CY}Run:  $PY3 $RUNTIME_DIR/prism32.py${RST}"
else
  echo -e "  ${CY}Run:  prism32${RST}"
fi
echo -e "  ${CY}Help: prism32 --help${RST}"
echo ""

if [ -n "${api_key:-}" ]; then
  echo -e "  ${G}+${RST} API key saved to ${CY}$CONFIG_FILE${RST} (top-level + providers.$PROV)"
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

echo -e "${DIM}  MegaDyne Systems (MDS) — Prism32 v7.2${RST}"
echo ""

# vim: set ts=2 sw=2 et:
