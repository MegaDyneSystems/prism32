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
  git -C "$CLONE_DIR" pull origin main 2>/dev/null || true
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

# Preserve existing config
if [ -f "$RUNTIME_DIR/config.json" ]; then
  ok "Config preserved"
else
  # Create default config for Termux (local model or ask)
  cat > "$RUNTIME_DIR/config.json" << JSONEOF
{
  "theme": "phosphor",
  "provider": "local",
  "model": "model-name",
  "api_base": "http://127.0.0.1:8080",
  "api_key": "",
  "max_history": 2000,
  "max_response_tokens": 8192,
  "cmd_timeout": 600,
  "goal_max_steps": 1000,
  "stream": false,
  "max_memory_ctx": 1024,
  "subagent_model": "",
  "verify_ssl": true,
  "agent_name": "MDS"
}
JSONEOF
  ok "Default config created"
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
echo -e "  \033[2mTo use a cloud provider (OpenRouter/Groq/etc.):${RST}"
echo -e "  \033[2m  prism32 --provider openrouter --api-key YOUR_KEY${RST}"
echo ""
echo -e "  \033[2mMegaDyne Systems (MDS) — Prism32 v6.8\033[0m"
echo ""
