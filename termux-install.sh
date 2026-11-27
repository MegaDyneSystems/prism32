#!/usr/bin/env sh
# ═══════════════════════════════════════════════════════════════
#  Prism32 Termux Quick Installer
#
#  One-liner:
#    pkg install curl && curl -fsSL https://raw.githubusercontent.com/MegaDyneSystems/prism32/main/termux-install.sh | sh
#
#  Or with wget:
#    pkg install wget && wget -qO- https://raw.githubusercontent.com/MegaDyneSystems/prism32/main/termux-install.sh | sh
# ═══════════════════════════════════════════════════════════════
set -eu

REPO="https://github.com/MegaDyneSystems/prism32"
RAW="https://raw.githubusercontent.com/MegaDyneSystems/prism32/main"
RUNTIME_DIR="$HOME/.prism32"
CLONE_DIR="$HOME/prism32"

echo ""
echo -e "\033[96m\033[1m  +========================================+\033[0m"
echo -e "\033[96m\033[1m  |  Prism32 Termux Quick Installer         |\033[0m"
echo -e "\033[96m\033[1m  |  MegaDyne Systems (MDS) Edition         |\033[0m"
echo -e "\033[96m\033[1m  +========================================+\033[0m"
echo ""

# Install dependencies
echo -e "  \033[2mInstalling Python 3 and git...\033[0m"
pkg install -y python3 git 2>/dev/null || {
  echo -e "  \033[91m!\033[0m pkg install failed. Trying apt..."
  apt-get update -qq && apt-get install -y python3 git
}

PY3="python3"
ok() { echo -e "  \033[92m*\033[0m $*"; }
warn() { echo -e "  \033[93mw\033[0m $*"; }

# Verify Python version
"$PY3" -c "import sys; exit(0 if sys.version_info >= (3,7) else 1)" 2>/dev/null || {
  echo -e "  \033[91m!\033[0m Python 3.7+ required. Found: $("$PY3" --version 2>&1)"
  exit 1
}
ok "Python: $("$PY3" --version 2>&1)"

# Clone or update
if [ -d "$CLONE_DIR/.git" ]; then
  ok "Updating existing Prism32 clone..."
  # Hard-sync (not pull): a dirty clone makes pull a silent no-op while
  # reporting success — the stale-version pattern bootstrap.sh fixed.
  git -C "$CLONE_DIR" fetch origin 2>/dev/null \
    && git -C "$CLONE_DIR" reset --hard origin/main 2>/dev/null || true
else
  echo -e "  \033[2mCloning repository...\033[0m"
  git clone --depth 1 "$REPO" "$CLONE_DIR"
fi

cd "$CLONE_DIR"

# Verify syntax
"$PY3" -c "import py_compile; py_compile.compile('prism32.py', doraise=True)" 2>/dev/null || {
  echo -e "  \033[91m!\033[0m Syntax check failed"
  exit 1
}
ok "Syntax OK"

# Install
mkdir -p "$RUNTIME_DIR" "$RUNTIME_DIR/plugins" "$RUNTIME_DIR/sessions" "$RUNTIME_DIR/skills" "$RUNTIME_DIR/evolve"
cp prism32.py "$RUNTIME_DIR/prism32.py"

# Copy plugins
if [ -d "plugins" ]; then
  for p in plugins/*.py; do
    [ -f "$p" ] || continue
    bn=$(basename "$p")
    [ "$bn" = "__init__.py" ] && continue
    [ ! -f "$RUNTIME_DIR/plugins/$bn" ] && cp "$p" "$RUNTIME_DIR/plugins/$bn"
  done
fi

# Create wrapper script (no root needed in Termux)
BIN="$PREFIX/bin/prism32"
cat > "$BIN" << WRAP
#!/bin/sh
exec python3 "$RUNTIME_DIR/prism32.py" "\$@"
WRAP
chmod +x "$BIN"

ok "Installed: $BIN"

# ── Scan for remote llama.cpp instances ──
_scan_llama() {
  "$PY3" -c "
import socket, urllib.request, json, concurrent.futures, sys

def probe(ip, port):
    try:
        url = 'http://{0}:{1}/v1/models'.format(ip, port)
        req = urllib.request.Request(url, headers={'User-Agent': 'Prism32-Installer'})
        with urllib.request.urlopen(req, timeout=2) as r:
            data = json.loads(r.read().decode('utf-8', errors='replace'))
            models = [m.get('id', '') for m in data.get('data', [])]
            return {'ip': ip, 'port': port, 'models': models[:8]}
    except Exception:
        return None

# Get local subnet
subnet = None
try:
    import subprocess
    out = subprocess.check_output(['ip', 'route', 'show', 'default'], stderr=subprocess.DEVNULL, timeout=3).decode()
    for line in out.splitlines():
        if 'src' in line:
            src = line.split('src')[1].strip().split()[0]
            octets = src.split('.')
            subnet = '.'.join(octets[:3])
            break
except Exception:
    pass

if not subnet:
    try:
        h = socket.gethostname()
        ip = socket.gethostbyname(h)
        octets = ip.split('.')
        if len(octets) == 4 and not ip.startswith('127.'):
            subnet = '.'.join(octets[:3])
    except Exception:
        pass

if not subnet:
    print('[]')
    sys.exit(0)

PORTS = [8080, 8000, 8081, 5000, 11434]
ips = ['{0}.{1}'.format(subnet, i) for i in list(range(1, 31)) + list(range(100, 121))]
found = []

with concurrent.futures.ThreadPoolExecutor(max_workers=50) as ex:
    futures = {ex.submit(probe, ip, p): (ip, p) for ip in ips for p in PORTS}
    for f in concurrent.futures.as_completed(futures, timeout=10):
        try:
            r = f.result(timeout=2)
            if r:
                found.append(r)
        except Exception:
            pass

seen = set()
unique = []
for r in found:
    key = '{0}:{1}'.format(r['ip'], r['port'])
    if key not in seen:
        seen.add(key)
        unique.append(r)
print(json.dumps(unique))
"
}

# Preserve existing config
if [ -f "$RUNTIME_DIR/config.json" ]; then
  ok "Config preserved"
else
  # Scan network for remote llama.cpp instances
  echo ""
  echo "  Scanning network for remote llama.cpp instances..."
  SCAN="$(_scan_llama 2>/dev/null || echo '[]')"
  SCAN_N="$("$PY3" -c "import json,sys; print(len(json.loads(sys.argv[1])))" "$SCAN" 2>/dev/null || echo 0)"
  if [ "$SCAN_N" != "0" ]; then
    echo "  Found $SCAN_N remote instance(s)"
    "$PY3" -c "
import json, sys
for i, inst in enumerate(json.loads(sys.argv[1])):
    url = 'http://{0}:{1}'.format(inst['ip'], inst['port'])
    m = inst.get('models', [])
    print('  [{0}] {1}  (model: {2})'.format(i + 1, url, m[0] if m else 'default'))
" "$SCAN"
    # Use first found instance as default
    BASE="$("$PY3" -c "import json,sys; d=json.loads(sys.argv[1]); print('http://{0}:{1}'.format(d[0]['ip'], d[0]['port']) if d else '')" "$SCAN")"
    MODEL="$("$PY3" -c "import json,sys; d=json.loads(sys.argv[1]); m=d[0].get('models',[]) if d else []; print(m[0] if m else 'default')" "$SCAN")"
    PROVIDER="llama_remote_1"
    # Build all_providers JSON
    ALL_P="$("$PY3" -c "
import json, sys
scan = json.loads(sys.argv[1])
all_p = {}
for i, inst in enumerate(scan):
    key = 'llama_remote_{0}'.format(i + 1)
    url = 'http://{0}:{1}'.format(inst['ip'], inst['port'])
    models = inst.get('models', [])
    model = models[0] if models else 'default'
    all_p[key] = {'api_base': url, 'model': model, 'api_key': ''}
print(json.dumps(all_p))
" "$SCAN")"
  else
    echo "  No remote llama.cpp instances found"
    PROVIDER="local"
    BASE="http://127.0.0.1:8080"
    MODEL=""
    ALL_P="{}"
  fi

  # Create config with scanned/default provider
  "$PY3" -c "
import json, sys
config = {
    'theme': 'phosphor',
    'provider': sys.argv[1],
    'model': sys.argv[2],
    'api_base': sys.argv[3],
    'api_key': '',
    'max_history': 2000,
    'max_response_tokens': 8192,
    'cmd_timeout': 600,
    'goal_max_steps': 1000,
    'stream': False,
    'max_memory_ctx': 1024,
    'subagent_model': '',
    'verify_ssl': True,
    'agent_name': 'MDS'
}
all_p = json.loads(sys.argv[4]) if sys.argv[4] else {}
if all_p:
    config['providers'] = all_p
print(json.dumps(config, indent=2))
" "$PROVIDER" "$MODEL" "$BASE" "$ALL_P" > "$RUNTIME_DIR/config.json"
  ok "Config created (provider: $PROVIDER)"
fi

# Setup runtime
"$PY3" "$RUNTIME_DIR/prism32.py" --setup-runtime >/dev/null 2>&1 && ok "Runtime setup complete" || warn "Runtime setup skipped"

echo ""
echo -e "  \033[92m\033[1m+========================================+\033[0m"
echo -e "  \033[92m\033[1m|  Installation Complete!                |\033[0m"
echo -e "  \033[92m\033[1m+========================================+\033[0m"
echo ""
echo -e "  \033[1mRun:\033[0m  prism32"
echo -e "  \033[1mHelp:\033[0m prism32 --help"
echo -e "  \033[1mConfig:\033[0m $RUNTIME_DIR/config.json"
echo ""
echo -e "  \033[2mTo use a cloud provider (OpenRouter/Groq/etc.):${RST:-}"
echo -e "  \033[2m  prism32  then inside: /provider key openrouter sk-or-...${RST:-}"
echo ""
echo -e "  \033[2mMegaDyne Systems (MDS) — Prism32 v7.4.0\033[0m"
echo ""
