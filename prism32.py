#!/usr/bin/env python3
"""
Prism32 v6.7 - MegaDyne Systems Terminal Agent
Green phosphor vibes. Pure terminal energy.
"""
import urllib.request
import urllib.error
import json
import sys
import os
import subprocess
import time
import socket
import shutil
import re
import signal
import argparse
import textwrap
import difflib
from datetime import datetime
import platform
import atexit
import math
import base64
import threading
stdout_lock = threading.Lock()
import queue
import hashlib
import importlib.util
try:
    import pty
except ImportError:
    pty = None
try:
    import select
except ImportError:
    select = None
try:
    import readline
except ImportError:
    pass

# ── Plugin & Extension System ──────────────────────────────

class Command:
    """A registered command with metadata."""
    def __init__(self, name, handler, *, aliases=None, description="", category="", hidden=False):
        self.name = name
        self.handler = handler
        self.aliases = list(aliases) if aliases else []
        self.description = description
        self.category = category
        self.hidden = hidden

    def all_names(self):
        return [self.name] + self.aliases

class CommandRegistry:
    """Registry of commands (built-in + plugins)."""
    def __init__(self):
        self._cmds = {}

    def register(self, name, handler=None, **kwargs):
        if handler is None:
            return lambda h: self.register(name, h, **kwargs)
        cmd = Command(name, handler, **kwargs) if not isinstance(handler, Command) else handler
        self._cmds[cmd.name] = cmd
        for alias in cmd.aliases:
            self._cmds[alias] = cmd
        return cmd

    def get(self, name):
        return self._cmds.get(name)

    def all(self):
        seen = set()
        for cmd in self._cmds.values():
            if id(cmd) not in seen:
                seen.add(id(cmd))
                yield cmd

    def names(self):
        return {cmd.name for cmd in self.all()} | {a for cmd in self.all() for a in cmd.aliases}

    def dispatch(self, name, args_str, history, cmd_log):
        cmd = self.get(name)
        if cmd:
            cmd.handler(args_str, history, cmd_log)
            return True
        return False

    def dispatch_capture(self, name, args_str):
        """Dispatch a command and return its output as a string (for AI use)."""
        import io
        cmd = self.get(name)
        if not cmd:
            return None
        old_stdout = sys.stdout
        sys.stdout = io.StringIO()
        try:
            cmd.handler(args_str, [], [])
            result = sys.stdout.getvalue()
        finally:
            sys.stdout = old_stdout
        return result

registry = CommandRegistry()

# ── Provider Registry (extensible) ─────────────────────────
PROVIDER_REGISTRY = {}

def register_provider(provider_id, **config):
    PROVIDER_REGISTRY[provider_id] = dict(config)
    return config

# ── Theme Registry (extensible) ─────────────────────────────
THEME_REGISTRY = {}

def register_theme(name, **colors):
    THEME_REGISTRY[name] = dict(colors)
    return colors

# ── Plugin Loader ──────────────────────────────────────────
PLUGIN_DIR = os.path.join(os.path.expanduser("~"), ".prism32", "plugins")
_PLUGINS = {}


class PluginAPI:
    """API object passed to plugins for accessing agent internals."""
    def __init__(self, plugin_name):
        self.name = plugin_name
        self._timers = []
        self._running = True
        self.registry = registry
        self.register_provider = register_provider
        self.register_theme = register_theme
        self.plugins = _PLUGINS

    @property
    def config(self):
        return Config

    @property
    def memory(self):
        return _mem_cache

    @property
    def history(self):
        return _PluginHooks._history if hasattr(_PluginHooks, '_history') else []

    def inject_context(self, text):
        """Add text to the AI system prompt context."""
        _PluginHooks._extra_context.append(text)

    def schedule(self, interval_sec, callback):
        """Schedule a callback to run every interval_sec seconds."""
        t = threading.Timer(interval_sec, self._run_scheduled, [callback])
        t.daemon = True
        self._timers.append(t)
        t.start()
        return t

    def _run_scheduled(self, callback):
        if not self._running:
            return
        try:
            callback(self)
        except Exception as e:
            with stdout_lock:
                print(f"  [plugin:{self.name}] timer error: {e}")
        if self._running:
            t = threading.Timer(self._timers[-1].interval if hasattr(self._timers[-1], 'interval') else 60, 
                               self._run_scheduled, [callback])
            t.daemon = True
            self._timers.append(t)
            t.start()

    def http_get(self, url, headers=None, timeout=10):
        import urllib.request
        req = urllib.request.Request(url, headers=headers or {})
        try:
            with urllib.request.urlopen(req, timeout=timeout) as r:
                return r.read().decode('utf-8', errors='replace')
        except Exception as e:
            return f"Error: {e}"

    def http_post(self, url, data=None, headers=None, timeout=10):
        import urllib.request
        import json as _j
        data_bytes = _j.dumps(data).encode() if isinstance(data, dict) else (data.encode() if isinstance(data, str) else data)
        req = urllib.request.Request(url, data=data_bytes, headers=headers or {}, method='POST')
        try:
            with urllib.request.urlopen(req, timeout=timeout) as r:
                return r.read().decode('utf-8', errors='replace')
        except Exception as e:
            return f"Error: {e}"

    def log(self, msg):
        with stdout_lock:
            print(f"  [plugin:{self.name}] {msg}")
            sys.stdout.flush()

    def stop(self):
        self._running = False
        for t in self._timers:
            t.cancel()


class _PluginHooks:
    """Internal hook dispatcher. Plugins define methods, we call them."""
    _extra_context = []
    _history = []
    _boot_callbacks = []
    _message_callbacks = []
    _response_callbacks = []
    _command_callbacks = []
    _shutdown_callbacks = []
    _tick_callbacks = []
    _tick_thread = None

    @classmethod
    def register_plugin(cls, mod, api):
        if hasattr(mod, 'on_boot'):
            cls._boot_callbacks.append((mod.on_boot, api))
        if hasattr(mod, 'on_message'):
            cls._message_callbacks.append((mod.on_message, api))
        if hasattr(mod, 'on_response'):
            cls._response_callbacks.append((mod.on_response, api))
        if hasattr(mod, 'on_command'):
            cls._command_callbacks.append((mod.on_command, api))
        if hasattr(mod, 'on_shutdown'):
            cls._shutdown_callbacks.append((mod.on_shutdown, api))
        if hasattr(mod, 'on_tick'):
            cls._tick_callbacks.append((mod.on_tick, api))

    @classmethod
    def fire_boot(cls):
        for cb, api in cls._boot_callbacks:
            try:
                cb(api)
            except Exception as e:
                with stdout_lock:
                    print(f"  [plugin] on_boot error: {e}")

    @classmethod
    def fire_message(cls, user_input):
        for cb, api in cls._message_callbacks:
            try:
                cb(api, user_input)
            except Exception as e:
                with stdout_lock:
                    print(f"  [plugin] on_message error: {e}")

    @classmethod
    def fire_response(cls, response):
        for cb, api in cls._response_callbacks:
            try:
                cb(api, response)
            except Exception as e:
                with stdout_lock:
                    print(f"  [plugin] on_response error: {e}")

    @classmethod
    def fire_command(cls, cmd_name, args, result):
        for cb, api in cls._command_callbacks:
            try:
                cb(api, cmd_name, args, result)
            except Exception as e:
                with stdout_lock:
                    print(f"  [plugin] on_command error: {e}")

    @classmethod
    def fire_shutdown(cls):
        for cb, api in cls._shutdown_callbacks:
            try:
                cb(api)
            except Exception as e:
                pass
        for api_name in list(_PLUGINS.keys()):
            _plugin_apis.get(api_name, _PluginAPI_placeholder).stop()

    @classmethod
    def start_tick(cls, interval=5):
        if not cls._tick_callbacks:
            return
        def _tick_loop():
            while not _shutdown_flag:
                time.sleep(interval)
                for cb, api in cls._tick_callbacks:
                    try:
                        cb(api)
                    except Exception:
                        pass
        cls._tick_thread = threading.Thread(target=_tick_loop, daemon=True)
        cls._tick_thread.start()

_plugin_apis = {}
_PluginAPI_placeholder = object()

def _load_plugin_file(mod_path, mod_name=None, quiet=False):
    """Load one plugin file and register its commands/hooks."""
    mod_name = mod_name or os.path.splitext(os.path.basename(mod_path))[0]
    if mod_name in _PLUGINS:
        return True, f"Already loaded: {mod_name}"
    try:
        spec = importlib.util.spec_from_file_location(mod_name, mod_path)
        if not spec or not spec.loader:
            return False, f"Could not create plugin spec: {mod_path}"
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        api = PluginAPI(mod_name)
        _plugin_apis[mod_name] = api
        if hasattr(mod, "register"):
            mod.register(api)
        _PluginHooks.register_plugin(mod, api)
        _PLUGINS[mod_name] = mod
        if not quiet:
            print(f"  [plugin] Loaded: {mod_name}")
        return True, f"Loaded: {mod_name}"
    except Exception as e:
        if not quiet:
            print(f"  [plugin] Error loading {mod_name}: {e}")
        return False, f"Error loading {mod_name}: {e}"

def load_plugins():
    """Load external command plugins from ~/.prism32/plugins/.
    Uses importlib.util to load from file path (no sys.path manipulation needed)."""
    if not os.path.isdir(PLUGIN_DIR):
        os.makedirs(PLUGIN_DIR, exist_ok=True)
        return
    for f in sorted(os.listdir(PLUGIN_DIR)):
        if f.endswith(".py") and not f.startswith("_"):
            mod_path = os.path.join(PLUGIN_DIR, f)
            _load_plugin_file(mod_path, mod_name=f[:-3])

# ── Self-Evolving Memory System ─────────────────────────────
# Small persistent file (~/.prism32/memory.json) that tracks
# usage patterns, errors, and preferences to improve over time.

MEMORY_FILE = os.path.join(os.path.expanduser("~"), ".prism32", "memory.json")
STARTUP_MEMORY_FILE = os.path.join(os.path.expanduser("~"), ".prism32", "startup_memory.md")
QUANTUM_FILE = os.path.join(os.path.expanduser("~"), ".prism32", "quantum.json")
SOUL_FILE = os.path.join(os.path.expanduser("~"), ".prism32", "soul.md")
PROMPTSHARD_FILE = os.path.join(os.path.expanduser("~"), ".prism32", "promptshard.md")
HARNESS_FILE = os.path.join(os.path.expanduser("~"), ".prism32", "harnesses.json")
EVOLVE_DIR = os.path.join(os.path.expanduser("~"), ".prism32", "evolve")
EVOLVE_DOC_FILE = os.path.join(EVOLVE_DIR, "evolve.md")
EVOLVE_TOOL_FILE = os.path.join(EVOLVE_DIR, "tools.json")
EVOLVE_BASELINE_DIR = os.path.join(EVOLVE_DIR, "baseline")
EVOLVE_BASELINE_FILE = os.path.join(EVOLVE_BASELINE_DIR, "prism32.py")
EVOLVE_BASELINE_CONFIG_FILE = os.path.join(EVOLVE_BASELINE_DIR, "config.default.json")
EVOLVE_TEMP_PLUGIN_DIR = os.path.join(EVOLVE_DIR, "tmp_plugins")

# Secrets vault: stored separately from promptshard to prevent injection
SECRETS_FILE = os.path.join(os.path.expanduser("~"), ".prism32", ".secrets.json")

_MEMORY_DIRTY = False
_MEMORY_FLUSH_COUNTER = 0
_LAST_INTERJECT = ""
_CURRENT_SESSION_ID = None
_EVOLVE_MODE = False

# ── Interjection state ────────────────────────────────────────
_INTERJECTION_ACTIVE = False
_INTERJECTION_BUF = ""
_INTERJECTION_CURSOR = 0
_INTERJECTION_RESULT = None
_SAVED_TERMIOS = None
_INTERJECTION_HAS_TYPED = False
_INTERJECTION_ESCAPE = False
_INTERJECTION_ESCAPE_BUF = ""
_INTERJECTION_HISTORY = []
_INTERJECTION_HISTORY_IDX = -1
_INTERJECTION_SAVED_BUF = ""
_INTERJECTION_CANCEL = object()
AGENT_CANCELLED_RESPONSE = "[CANCELLED] Agent stopped by Escape"
_AGENT_CANCEL_REQUESTED = False
_AGENT_CANCEL_REASON = ""

def _flush_memory():
    global _MEMORY_DIRTY, _MEMORY_FLUSH_COUNTER
    if _MEMORY_DIRTY:
        try:
            save_memory(_mem_cache)
            _MEMORY_DIRTY = False
        except Exception:
            pass

def _default_memory():
    return {
        "version": 2,
        "last_updated": "",
        "command_stats": {},
        "error_patterns": {},
        "preferences": {},
        "system_profile": {},
        "startup_memory_file": STARTUP_MEMORY_FILE,
        "session_count": 0,
        "suggestions_shown": [],
    }

def load_memory():
    try:
        with open(MEMORY_FILE) as f:
            mem = json.load(f)
        if mem.get("version", 0) < 2:
            mem = _default_memory()
        mem.setdefault("system_profile", {})
        mem.setdefault("startup_memory_file", STARTUP_MEMORY_FILE)
        return mem
    except (FileNotFoundError, json.JSONDecodeError):
        return _default_memory()

_mem_cache = load_memory()
_mem_cache_loaded = True

def save_memory(memory):
    try:
        memory["last_updated"] = datetime.now().isoformat()
        # Auto-consolidate: keep only top 30 commands, 15 error patterns
        if len(memory.get("command_stats", {})) > 30:
            sorted_cmds = sorted(memory["command_stats"].items(), key=lambda x: -x[1]["uses"])
            memory["command_stats"] = dict(sorted_cmds[:30])
        if len(memory.get("error_patterns", {})) > 15:
            sorted_errs = sorted(memory["error_patterns"].items(), key=lambda x: -x[1]["count"])
            memory["error_patterns"] = dict(sorted_errs[:15])
        with open(MEMORY_FILE, 'w', encoding='utf-8') as f:
            json.dump(memory, f, indent=2)
    except Exception:
        pass

# ── Startup Memory, Harness Absorption, and Evolve Support ─────

STARTUP_AUTO_START = "<!-- PRISM32_AUTO_START -->"
STARTUP_AUTO_END = "<!-- PRISM32_AUTO_END -->"

HARNESS_CANDIDATES = [
    {
        "id": "opencode",
        "display": "OpenCode",
        "executables": ["opencode"],
        "abilities": ["codebase editing", "tool calling", "subagents", "repo automation"],
        "hint": "Use for multi-file software engineering after inspecting its help output.",
    },
    {
        "id": "codex",
        "display": "OpenAI Codex CLI",
        "executables": ["codex"],
        "abilities": ["code editing", "repo repair", "command execution"],
        "hint": "Use for focused coding tasks when its CLI is configured.",
    },
    {
        "id": "claude-code",
        "display": "Claude Code",
        "executables": ["claude", "claude-code"],
        "abilities": ["code editing", "repo analysis", "agentic terminal work"],
        "hint": "Use for coding tasks after checking authentication and CLI syntax.",
    },
    {
        "id": "kimicode",
        "display": "KimiCode",
        "executables": ["kimicode", "kimi"],
        "abilities": ["code editing", "long context analysis", "repo assistance"],
        "hint": "Use when Kimi-based coding tools are installed and authenticated.",
    },
    {
        "id": "pi",
        "display": "Pi AI CLI",
        "executables": ["pi"],
        "abilities": ["assistant CLI", "terminal assistance"],
        "hint": "Inspect help first; command names vary between Pi-related tools.",
    },
    {
        "id": "aider",
        "display": "Aider",
        "executables": ["aider"],
        "abilities": ["git-aware coding", "multi-file edits", "LLM pair programming"],
        "hint": "Useful for git-backed code edits when configured with an API key.",
    },
    {
        "id": "gemini-cli",
        "display": "Gemini CLI",
        "executables": ["gemini"],
        "abilities": ["assistant CLI", "large context analysis", "code help"],
        "hint": "Use for large context inspection if installed and authenticated.",
    },
    {
        "id": "goose",
        "display": "Goose",
        "executables": ["goose"],
        "abilities": ["desktop/terminal agent", "tool use", "automation"],
        "hint": "Use for autonomous local automation after checking available extensions.",
    },
    {
        "id": "cursor-agent",
        "display": "Cursor Agent",
        "executables": ["cursor-agent"],
        "abilities": ["codebase editing", "repo automation"],
        "hint": "Use for Cursor-backed coding workflows when present.",
    },
]

TOOL_SCAN_GROUPS = {
    "shells": ["bash", "sh", "zsh", "fish", "ksh", "dash", "ash", "busybox", "cmd", "powershell", "pwsh"],
    "python": ["python3", "python", "py"],
    "vcs": ["git", "hg", "svn"],
    "editors": ["nano", "vim", "vi", "nvim", "ed", "notepad", "code"],
    "build": ["make", "cmake", "ninja", "gcc", "clang", "cc", "msbuild", "cl"],
    "network": ["ssh", "scp", "sftp", "curl", "wget", "ftp", "nc", "ncat", "telnet", "ifconfig", "ip", "netstat", "ss"],
    "archives": ["tar", "gzip", "gunzip", "zip", "unzip", "7z", "certutil"],
    "package": ["apt", "apt-get", "dnf", "microdnf", "tdnf", "yum", "pacman", "zypper", "apk", "rpm-ostree", "swupd", "opkg", "ipkg", "emerge", "xbps-install", "eopkg", "slackpkg", "guix", "nix-env", "pkg", "pkgin", "pkg_add", "pkgadd", "pkgutil", "pkgman", "brew", "port", "winget", "choco", "scoop", "synopkg"],
    "services": ["systemctl", "service", "rc-service", "rcctl", "svcadm", "initctl", "launchctl", "synoservice", "svcs"],
    "embedded": ["busybox", "opkg", "ipkg", "uci", "ubus", "procd", "fw_printenv", "fw_setenv", "termux-setup-storage"],
    "containers": ["docker", "podman", "kubectl", "nerdctl", "ctr", "crictl", "lxc", "lxc-info", "systemd-detect-virt"],
    "storage_appliance": ["midclt", "cli", "synoshare", "synoservice", "synopkg", "qm", "pvesh", "pveversion"],
    "windows": ["cmd", "powershell", "pwsh", "where", "wmic", "tasklist", "netstat", "ipconfig", "route", "reg", "wsl"],
}

def _runtime_dir():
    return os.path.dirname(MEMORY_FILE)

def _now_iso():
    return datetime.now().isoformat()

def _detect_shell_name():
    if os.environ.get("COMSPEC"):
        return os.environ.get("COMSPEC", "")
    return os.environ.get("SHELL", "") or os.environ.get("0", "") or "unknown"

def _safe_read(path, default=""):
    try:
        with open(path, "r", encoding="utf-8") as f:
            return f.read()
    except (FileNotFoundError, IOError, OSError):
        return default

def _safe_write(path, text):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        f.write(text)

def _startup_auto_block():
    try:
        info = get_system_info(force=True)
    except Exception:
        info = {}
    shell = _detect_shell_name()
    term = os.environ.get("TERM") or os.environ.get("WT_SESSION") or os.environ.get("TERM_PROGRAM") or "unknown"
    pkg = info.get("pkg_mgr") or "unknown"
    lines = [
        STARTUP_AUTO_START,
        "## Auto-Detected System Snapshot",
        "",
        f"- Updated: {_now_iso()}",
        f"- OS: {info.get('os', platform.system() or 'unknown')}",
        f"- Architecture: {info.get('arch', platform.machine() or 'unknown')}",
        f"- CPU: {info.get('cpu', 'unknown')}",
        f"- RAM: {info.get('ram', 'unknown')}",
        f"- Disk: {info.get('disk', 'unknown')}",
        f"- Package manager: {pkg}",
        f"- Shell: {shell}",
        f"- Terminal: {term}",
        f"- Python: {sys.version.split()[0]}",
        f"- Home: {os.path.expanduser('~')}",
        f"- Current working directory at last refresh: {os.getcwd()}",
        "",
        "## Cross-Platform Command Notes",
        "",
        "- Unix/macOS/BSD: prefer sh-compatible commands unless bash is detected.",
        "- Android/Termux: prefer pkg, termux-setup-storage, and normal POSIX shell commands.",
        "- Solaris/SunOS/Oracle Solaris: prefer /usr/bin sh tools, ps/netstat/ifconfig, pkg or pkgadd, and avoid GNU-only flags.",
        "- Embedded Linux/OpenWrt/BusyBox/NAS: prefer sh/ash, busybox applets, opkg/ipkg/synopkg, and avoid GNU-only flags.",
        "- ChromeOS/Crostini, WSL, containers, CI runners: treat as Linux but verify mounts, networking, and package permissions first.",
        "- Proxmox/TrueNAS/pfSense/OPNsense/Unraid/SteamOS: use appliance-native tools carefully; avoid changing host networking/storage without explicit instruction.",
        "- Immutable Linux (SteamOS, Fedora CoreOS/Silverblue/Kinoite, rpm-ostree systems, Clear Linux): prefer toolbox/container workflows or native transactional managers.",
        "- Server Unix: AIX uses installp, HP-UX uses swinstall, IRIX uses inst, Tru64 uses setld, Haiku uses pkgman, QNX may use pkg/opkg.",
        "- Windows: prefer cmd.exe built-ins, PowerShell, tasklist, ipconfig, route, netstat, findstr, where, and dir.",
        "- NetBSD/OpenBSD/FreeBSD: prefer ifconfig/netstat/pkgin/pkg_add/pkg and avoid Linux-only flags.",
        STARTUP_AUTO_END,
    ]
    return "\n".join(lines)

def _default_startup_memory_text():
    return "\n".join([
        "# Prism32 Startup Memory",
        "",
        "This Markdown file is injected into Prism32's startup context.",
        "Edit it with /memory edit or open the path shown by /memory path.",
        "Keep it short, factual, and useful for future terminal work.",
        "",
        _startup_auto_block(),
        "",
        "## Hardware Tips",
        "",
        "- Add machine-specific CPU, RAM, storage, GPU, battery, or thermal notes here.",
        "",
        "## Software Tips",
        "",
        "- Add package manager quirks, installed language runtimes, local services, and API tools here.",
        "",
        "## Terminal And Shell Quirks",
        "",
        "- Add terminal rendering issues, shell differences, PATH notes, sudo/su quirks, and remote login details here.",
        "",
        "## User Workflow",
        "",
        "- Add preferred project directories, build/test commands, deployment habits, and naming conventions here.",
        "",
        "## Recurring Fixes",
        "",
        "- Add errors Prism32 has solved before and the fix that worked.",
        "",
    ])

def ensure_startup_memory(refresh=False):
    os.makedirs(_runtime_dir(), exist_ok=True)
    if not os.path.exists(STARTUP_MEMORY_FILE):
        _safe_write(STARTUP_MEMORY_FILE, _default_startup_memory_text())
        return STARTUP_MEMORY_FILE
    if refresh:
        existing = _safe_read(STARTUP_MEMORY_FILE)
        block = _startup_auto_block()
        if STARTUP_AUTO_START in existing and STARTUP_AUTO_END in existing:
            start = existing.index(STARTUP_AUTO_START)
            end = existing.index(STARTUP_AUTO_END) + len(STARTUP_AUTO_END)
            existing = existing[:start] + block + existing[end:]
        else:
            existing = block + "\n\n" + existing
        _safe_write(STARTUP_MEMORY_FILE, existing.rstrip() + "\n")
    return STARTUP_MEMORY_FILE

def read_startup_memory():
    ensure_startup_memory(refresh=False)
    return _safe_read(STARTUP_MEMORY_FILE).strip()

def startup_memory_context(limit=2200):
    text = read_startup_memory()
    if not text:
        return ""
    if len(text) > limit:
        text = text[:limit] + "\n...(startup memory truncated; use /memory show or /memory path for full file)"
    return text

def refresh_memory_profile(save=True):
    try:
        info = get_system_info(force=True)
    except Exception:
        info = {}
    profile = {
        "updated": _now_iso(),
        "os": info.get("os", platform.system()),
        "arch": info.get("arch", platform.machine()),
        "cpu": info.get("cpu", ""),
        "ram": info.get("ram", ""),
        "disk": info.get("disk", ""),
        "package_manager": info.get("pkg_mgr", ""),
        "shell": _detect_shell_name(),
        "terminal": os.environ.get("TERM") or os.environ.get("TERM_PROGRAM") or os.environ.get("WT_SESSION") or "",
        "python": sys.version.split()[0],
        "home": os.path.expanduser("~"),
        "path_separator": os.pathsep,
    }
    if sys.platform.startswith("win"):
        profile["windows"] = platform.win32_ver()[0:3]
    _mem_cache["system_profile"] = profile
    if save:
        save_memory(_mem_cache)
    return profile

def _probe_version(exe_path):
    for args in ([exe_path, "--version"], [exe_path, "version"], [exe_path, "-v"]):
        try:
            result = subprocess.run(args, capture_output=True, text=True, timeout=2)
            out = (result.stdout or result.stderr or "").strip().splitlines()
            if out:
                return out[0][:120]
        except Exception:
            continue
    return ""

def detect_harnesses(probe_versions=True):
    installed = []
    missing = []
    seen_paths = set()
    for cand in HARNESS_CANDIDATES:
        found = None
        for exe in cand.get("executables", []):
            try:
                path = shutil.which(exe)
            except Exception:
                path = None
            if path:
                found = (exe, path)
                break
        if found:
            exe, path = found
            key = os.path.normcase(os.path.abspath(path))
            if key in seen_paths:
                continue
            seen_paths.add(key)
            item = dict(cand)
            item["command"] = exe
            item["path"] = path
            item["version_text"] = _probe_version(path) if probe_versions else ""
            installed.append(item)
        else:
            missing.append(cand.get("id", "unknown"))
    data = {
        "version": 1,
        "scanned_at": _now_iso(),
        "platform": platform.platform(),
        "shell": _detect_shell_name(),
        "installed": installed,
        "missing": missing,
    }
    return data

def save_harnesses(data):
    _safe_write(HARNESS_FILE, json.dumps(data, indent=2) + "\n")

def load_harnesses():
    try:
        with open(HARNESS_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
        if isinstance(data, dict) and "installed" in data:
            return data
    except (FileNotFoundError, IOError, json.JSONDecodeError):
        pass
    return {"version": 1, "scanned_at": "", "installed": [], "missing": []}

def ensure_harness_scan(force=False):
    stale = True
    try:
        stale = (time.time() - os.path.getmtime(HARNESS_FILE)) > 86400
    except OSError:
        stale = True
    if force or stale:
        data = detect_harnesses(probe_versions=force)
        save_harnesses(data)
        return data
    return load_harnesses()

def format_harnesses(data=None, verbose=True):
    data = data or load_harnesses()
    installed = data.get("installed", [])
    lines = [f"Scanned: {data.get('scanned_at') or 'never'}", f"File: {HARNESS_FILE}", ""]
    if not installed:
        lines.append("No external AI harnesses detected.")
        lines.append("Run /harness scan after installing tools like opencode, codex, claude, kimicode, aider, goose, or gemini.")
        return "\n".join(lines)
    lines.append("Detected AI harnesses:")
    for h in installed:
        abilities = ", ".join(h.get("abilities", [])[:4])
        version = f" [{h.get('version_text')}]" if verbose and h.get("version_text") else ""
        lines.append(f"- {h.get('display', h.get('id'))}: {h.get('command')} at {h.get('path')}{version}")
        if abilities:
            lines.append(f"  abilities: {abilities}")
        if verbose and h.get("hint"):
            lines.append(f"  hint: {h.get('hint')}")
    return "\n".join(lines)

def harness_context(limit=1600):
    data = ensure_harness_scan(force=False)
    installed = data.get("installed", [])
    if not installed:
        return "AI harnesses: none detected yet. Use /harness scan after installing external agent CLIs."
    lines = ["AI HARNESS ABSORPTION: external agent CLIs detected and usable from execute blocks:"]
    for h in installed[:8]:
        abilities = ", ".join(h.get("abilities", [])[:4])
        lines.append(f"- {h.get('display', h.get('id'))} command '{h.get('command')}' abilities: {abilities}. {h.get('hint', '')}")
    lines.append("Use /harness delegate <task> to spawn a super subagent seeded with these capabilities.")
    text = "\n".join(lines)
    return text[:limit]

def _harness_super_task(task):
    return (
        "SUPER HARNESS SUBAGENT TASK\n"
        "You are a Prism32 super subagent. You can use normal execute blocks and the detected external AI harness CLIs below. "
        "Before invoking an external harness, inspect its help/version and avoid destructive actions unless explicitly required.\n\n"
        f"{format_harnesses(load_harnesses(), verbose=False)}\n\n"
        f"User task: {task}"
    )

def scan_available_tools():
    tools = {}
    for group, names in TOOL_SCAN_GROUPS.items():
        found = []
        for name in names:
            try:
                path = shutil.which(name)
            except Exception:
                path = None
            if path:
                found.append({"name": name, "path": path})
        tools[group] = found
    data = {
        "version": 1,
        "scanned_at": _now_iso(),
        "platform": platform.platform(),
        "shell": _detect_shell_name(),
        "cwd": os.getcwd(),
        "tools": tools,
        "harnesses": load_harnesses().get("installed", []),
    }
    _safe_write(EVOLVE_TOOL_FILE, json.dumps(data, indent=2) + "\n")
    return data

def load_tool_scan():
    try:
        with open(EVOLVE_TOOL_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except (FileNotFoundError, IOError, json.JSONDecodeError):
        return scan_available_tools()

def format_tool_scan(data=None):
    data = data or load_tool_scan()
    lines = [f"Scanned: {data.get('scanned_at')}", f"Shell: {data.get('shell')}", f"File: {EVOLVE_TOOL_FILE}", ""]
    for group, found in sorted(data.get("tools", {}).items()):
        names = ", ".join(item.get("name", "") for item in found) or "none"
        lines.append(f"- {group}: {names}")
    return "\n".join(lines)

def _current_prism_source():
    candidates = []
    gfile = globals().get("__file__")
    if gfile:
        candidates.append(gfile)
    if sys.argv and sys.argv[0]:
        candidates.append(sys.argv[0])
    candidates.append(os.path.join(os.getcwd(), "prism32.py"))
    for path in candidates:
        try:
            real = os.path.realpath(path)
            if os.path.basename(real) == "prism32.py" and os.path.exists(real):
                return real
        except Exception:
            pass
    return os.path.join(os.getcwd(), "prism32.py")

def _default_config_snapshot():
    return {
        "theme": "phosphor",
        "provider": "local",
        "model": "deepseek-v4-flash",
        "api_base": "http://127.0.0.1:8080",
        "max_history": 2000,
        "max_response_tokens": 8192,
        "cmd_timeout": 600,
        "max_memory_ctx": 1024,
        "subagent_model": "",
        "agent_name": "MDS",
    }

def evolve_doc_text():
    help_text = globals().get("CMD_HELP", "Use /help inside Prism32 for command help.")
    return f"""# Prism32 Evolve Mode Documentation

This file is generated by Prism32 and injected into AI context when /evolve is on.
It is designed for self-repair, temporary tooling, permanent plugins, and safe system exploration.

## Runtime Paths

- Main script: {_current_prism_source()}
- Config: {Config.CONFIG_FILE if 'Config' in globals() else os.path.join(os.path.expanduser('~'), '.prism32', 'config.json')}
- Startup memory: {STARTUP_MEMORY_FILE}
- Plugins: {PLUGIN_DIR}
- Temporary evolve plugins: {EVOLVE_TEMP_PLUGIN_DIR}
- Baseline Prism32 copy: {EVOLVE_BASELINE_FILE}
- Baseline default config: {EVOLVE_BASELINE_CONFIG_FILE}
- Tool scan: {EVOLVE_TOOL_FILE}
- Harness scan: {HARNESS_FILE}

## Safe Self-Repair Workflow

1. Inspect the failure and reproduce it with the smallest command.
2. Compare current Prism32 to the baseline with /evolve diff.
3. Patch only the needed area. Keep stdlib-only Python 3.7+ compatibility.
4. Run py_compile and the focused tests before claiming success.
5. If terminal rendering is broken, prefer plain output and avoid cursor-control changes.
6. Never store API keys, passwords, host-specific private details, or internal server names in repo files.

## Plugin Options

Permanent plugins:

- Put Python files in ~/.prism32/plugins/<name>.py.
- They load on startup.
- Each plugin may define register(api) and optional hooks.

Temporary evolve plugins:

- Put Python files in ~/.prism32/evolve/tmp_plugins/<name>.py.
- They are scratch files for repair or one-off experiments.
- Copy to ~/.prism32/plugins/ only when the user wants them to persist.

Minimal permanent plugin:

```python
def register(api):
    def hello(args, history, cmd_log):
        print("hello from plugin")
    api.registry.register("hello", hello, description="Example command")
```

Useful PluginAPI fields:

- api.registry.register(name, handler, aliases=[], description="", category="")
- api.inject_context(text)
- api.http_get(url, headers=None, timeout=10)
- api.http_post(url, data=None, headers=None, timeout=10)
- api.config, api.memory, api.history, api.plugins
- Hooks used in normal operation: on_boot, on_message, on_command, on_tick

## Self-Extension

Use /extend temp <goal> to have Prism32 generate, syntax-check, write, and load a temporary plugin for a missing capability. Use /extend permanent <goal> only when the operator explicitly wants the plugin to load on future startups.

Use /extend prompt to print a pasteable plugin-generation prompt for another AI chatbot.

## Harness Absorption

Use /harness scan to detect external AI CLIs. If present, /harness delegate <task> creates a super subagent seeded with those capabilities. Always inspect a harness help screen before using it because command syntaxes differ.

## Windows Compatibility Notes

- Prism32 targets Python 3.7+, which covers old supported Windows installs such as Windows 7/Vista-era systems when Python 3.7 is available, plus Windows 10/11.
- Prefer tasklist, ipconfig, route print, netstat -ano, findstr, where, dir, cmd.exe, and PowerShell over Unix-only tools.
- Avoid ANSI-heavy assumptions on old consoles. If output looks corrupt, use a plain terminal or Windows Terminal where available.

## Current Command Help Snapshot

```text
{help_text[:5000]}
```
"""

def ensure_evolve_files(force_baseline=False, refresh_tools=False):
    os.makedirs(EVOLVE_DIR, exist_ok=True)
    os.makedirs(EVOLVE_BASELINE_DIR, exist_ok=True)
    os.makedirs(EVOLVE_TEMP_PLUGIN_DIR, exist_ok=True)
    _safe_write(EVOLVE_DOC_FILE, evolve_doc_text())
    source = _current_prism_source()
    if (force_baseline or not os.path.exists(EVOLVE_BASELINE_FILE)) and os.path.exists(source):
        try:
            shutil.copy2(source, EVOLVE_BASELINE_FILE)
        except Exception:
            pass
    if force_baseline or not os.path.exists(EVOLVE_BASELINE_CONFIG_FILE):
        _safe_write(EVOLVE_BASELINE_CONFIG_FILE, json.dumps(_default_config_snapshot(), indent=2) + "\n")
    if refresh_tools or not os.path.exists(EVOLVE_TOOL_FILE):
        scan_available_tools()
    return EVOLVE_DOC_FILE

def evolve_context(limit=5200):
    ensure_evolve_files(refresh_tools=False)
    tools = format_tool_scan(load_tool_scan())
    doc = _safe_read(EVOLVE_DOC_FILE).strip()
    text = (
        "EVOLVE MODE ACTIVE\n"
        "Prism32 may create temporary or permanent stdlib-only plugins, compare against its baseline, and use tool scans for self-repair.\n\n"
        f"{doc}\n\nTOOL SCAN SUMMARY\n{tools}\n"
    )
    if len(text) > limit:
        text = text[:limit] + "\n...(evolve context truncated; use /evolve docs and /evolve tools for full details)"
    return text

def evolve_diff(limit_lines=220):
    ensure_evolve_files(refresh_tools=False)
    source = _current_prism_source()
    try:
        with open(EVOLVE_BASELINE_FILE, "r", encoding="utf-8", errors="replace") as f:
            base = f.readlines()
        with open(source, "r", encoding="utf-8", errors="replace") as f:
            cur = f.readlines()
    except Exception as e:
        return f"Diff unavailable: {e}"
    diff = list(difflib.unified_diff(base, cur, fromfile="baseline/prism32.py", tofile=source, lineterm=""))
    if not diff:
        return "No differences from evolve baseline."
    shown = diff[:limit_lines]
    if len(diff) > limit_lines:
        shown.append(f"... ({len(diff) - limit_lines} more diff lines)")
    return "\n".join(shown)

def _sanitize_plugin_name(name):
    name = name.strip().lower().replace(" ", "_")
    name = re.sub(r"[^a-z0-9_]", "_", name)
    name = re.sub(r"_+", "_", name).strip("_")
    return name or "evolve_plugin"

def evolve_plugin_template(name):
    cmd_name = name.replace("_", "-")
    return f'''"""Prism32 evolve plugin: {name}

Stdlib-only. Generated by /evolve plugin.
"""

def register(api):
    def {name}_cmd(args, history, cmd_log):
        print("{cmd_name}: ready")
        if args:
            print("args:", args)

    api.registry.register("{cmd_name}", {name}_cmd, description="Evolve-generated helper command")
'''

def write_evolve_plugin(kind, name):
    safe = _sanitize_plugin_name(name)
    if kind == "permanent":
        directory = PLUGIN_DIR
    else:
        directory = EVOLVE_TEMP_PLUGIN_DIR
    os.makedirs(directory, exist_ok=True)
    path = os.path.join(directory, safe + ".py")
    if not os.path.exists(path):
        _safe_write(path, evolve_plugin_template(safe))
    return path

def plugin_cheat_sheet_text():
    return textwrap.dedent("""\
    You are writing a Prism32 plugin.

    Goal: create one small, useful extension for the operator's requested task.

    Output rules:
    - Return ONLY Python source code. No Markdown fences. No explanation.
    - Use Python 3.7+ standard library only. No pip dependencies.
    - Do not hardcode API keys, passwords, private hostnames, or secrets.
    - Do not perform network, filesystem, subprocess, or destructive work at import time.
    - Put side effects only inside registered command handlers or explicit hooks.
    - Define a USAGE_CONTEXT string that explains every command/option the plugin adds.
    - Add def on_boot(api): api.inject_context(USAGE_CONTEXT) so Prism32 agents know how to use it.
    - Prefer lowercase command names with hyphens, such as "weather" or "repo-report".
    - Handler signature: def handler(args_str, history, cmd_log):
    - Use print() for command output. Use api.log() for diagnostics.
    - Keep the plugin self-contained in one file.
    - If an operation can modify or delete data, require explicit command arguments.

    Required shape:

    USAGE_CONTEXT = (
        "Plugin available:\n"
        "- /my-command <args>: what it does, its options, and when agents should use it.\n"
    )

    def register(api):
        def my_command(args_str, history, cmd_log):
            print("ready")
        api.registry.register("my-command", my_command, description="Short description")

    def on_boot(api):
        api.inject_context(USAGE_CONTEXT)

    Available PluginAPI:
    - api.registry.register(name, handler, aliases=[], description="", category="", hidden=False)
    - api.registry.dispatch_capture(name, args_str) -> str or None
    - api.register_provider(id, **config)
    - api.register_theme(name, **colors)
    - api.config: runtime config class
    - api.memory: memory dict
    - api.history: current session history
    - api.inject_context(text): add context to future AI prompts
    - api.schedule(interval_sec, callback): run periodic callback
    - api.http_get(url, headers=None, timeout=10) -> str
    - api.http_post(url, data=None, headers=None, timeout=10) -> str
    - api.log(text): diagnostic output
    - api.plugins: loaded plugin modules

    Optional hooks:
    - def on_boot(api): called after startup initialization
    - def on_message(api, text): called for operator input
    - def on_command(api, name, args, result): called for slash commands; result is currently None
    - def on_tick(api): called about every 5 seconds while Prism32 is running

    Good plugin ideas:
    - add a focused slash command for a repeated workflow
    - parse and summarize local files
    - call a simple HTTP API with api.http_get()
    - inject task-specific context with api.inject_context()
    - add a provider or theme
    - create a report generator, log parser, release checklist, inventory scanner, or API helper
    """).strip()

def _extension_plugin_name(goal):
    words = re.findall(r"[a-zA-Z0-9]+", goal.lower())[:6]
    base = "_".join(words) or "extension"
    digest = hashlib.sha1(goal.encode("utf-8", errors="replace")).hexdigest()[:8]
    return _sanitize_plugin_name(f"auto_{base}_{digest}")[:64]

def _extract_python_source(text):
    text = (text or "").strip()
    if not text:
        return ""
    fenced = re.search(r"```(?:python|py)\s*\n(.*?)```", text, flags=re.IGNORECASE | re.DOTALL)
    if not fenced:
        fenced = re.search(r"```\s*\n(.*?)```", text, flags=re.DOTALL)
    if fenced:
        text = fenced.group(1).strip()
    # Some models still prefix a short sentence before code. Keep from the first
    # import or function definition if that makes the response look like source.
    markers = [m.start() for m in re.finditer(r"(?m)^(import |from |def |class )", text)]
    if markers and markers[0] > 0:
        text = text[markers[0]:].strip()
    return text.rstrip() + "\n" if text else ""

def _validate_plugin_source(source, path):
    if not source.strip():
        return "Model returned no Python source."
    if not re.search(r"def\s+register\s*\(", source):
        return "Plugin must define register(api)."
    try:
        compile(source, path, "exec")
    except SyntaxError as e:
        return f"Syntax error on line {e.lineno}: {e.msg}"
    except Exception as e:
        return f"Compile failed: {e}"
    return None

def _extend_plugin_prompt(goal, safe_name, cmd_name, kind):
    return [
        {"role": "system", "content": plugin_cheat_sheet_text()},
        {"role": "user", "content": textwrap.dedent(f"""\
        Create a Prism32 plugin for this goal:
        {goal}

        Plugin file basename: {safe_name}
        Suggested primary slash command: /{cmd_name}
        Persistence mode: {kind}

        Make it useful immediately after loading. Register at least one command.
        Return only Python source code.
        """).strip()},
    ]

def _extend_result_rebuild_context(history):
    if history:
        try:
            history[0] = {"role": "system", "content": SYSTEM_PROMPT + "\n" + build_context()}
        except Exception:
            pass

def extend_with_plugin(args_str, history=None):
    raw = (args_str or "").strip()
    if not raw:
        return (
            "Usage:\n"
            "  /extend <goal>                  Generate/load a temporary plugin\n"
            "  /extend temp <goal>             Generate/load a temporary plugin\n"
            "  /extend permanent <goal>        Generate/load a persistent plugin\n"
            "  /extend load <path>             Load an existing plugin file\n"
            "  /extend prompt                  Show pasteable plugin prompt"
        )

    head, _, rest = raw.partition(" ")
    head_l = head.lower()
    if head_l in ("prompt", "cheat", "cheatsheet", "cheat-sheet"):
        return plugin_cheat_sheet_text()

    if head_l in ("load", "reload"):
        path = os.path.expanduser(rest.strip())
        if not path:
            return "Usage: /extend load <path>"
        if not os.path.isfile(path):
            return f"[EXTEND FAILED] Plugin file not found: {path}"
        before = registry.names()
        safe_name = _sanitize_plugin_name(os.path.splitext(os.path.basename(path))[0])
        ok, msg = _load_plugin_file(path, mod_name=safe_name, quiet=True)
        if not ok:
            return f"[EXTEND FAILED] {msg}"
        _extend_result_rebuild_context(history)
        new_cmds = sorted(registry.names() - before)
        commands = ", ".join("/" + c for c in new_cmds) or "(no new commands registered)"
        return f"[EXTENSION LOADED]\nPlugin: {path}\nCommands: {commands}"

    if head_l in ("permanent", "perm", "persist", "persistent", "save"):
        kind = "permanent"
        goal = rest.strip()
    elif head_l in ("temp", "temporary", "scratch"):
        kind = "temp"
        goal = rest.strip()
    else:
        kind = "temp"
        goal = raw
    if not goal:
        return f"Usage: /extend {kind} <goal>"

    ensure_evolve_files(refresh_tools=False)
    safe_name = _extension_plugin_name(goal)
    cmd_name = safe_name.replace("_", "-")
    directory = PLUGIN_DIR if kind == "permanent" else EVOLVE_TEMP_PLUGIN_DIR
    os.makedirs(directory, exist_ok=True)
    path = os.path.join(directory, safe_name + ".py")

    messages = _extend_plugin_prompt(goal, safe_name, cmd_name, kind)
    response = ask_ai_cancelable(messages, history=history)
    if response == AGENT_CANCELLED_RESPONSE or agent_cancel_requested():
        return AGENT_CANCELLED_RESPONSE

    source = _extract_python_source(response)
    err = _validate_plugin_source(source, path)
    if err:
        failed_path = os.path.join(EVOLVE_TEMP_PLUGIN_DIR, safe_name + ".failed.txt")
        _safe_write(failed_path, response or "")
        return f"[EXTEND FAILED] {err}\nRaw model response saved: {failed_path}"

    _safe_write(path, source)
    before = registry.names()
    ok, msg = _load_plugin_file(path, mod_name=safe_name, quiet=True)
    if not ok:
        return f"[EXTEND FAILED] {msg}\nPlugin source saved: {path}"
    _extend_result_rebuild_context(history)
    new_cmds = sorted(registry.names() - before)
    commands = ", ".join("/" + c for c in new_cmds) or "(no new commands registered)"
    lifetime = "loads on startup" if kind == "permanent" else "loaded for this Prism32 process"
    return (
        "[EXTENSION LOADED]\n"
        f"Mode: {kind} ({lifetime})\n"
        f"Goal: {goal}\n"
        f"Plugin: {path}\n"
        f"Commands: {commands}"
    )

# ── Soul (persistent custom rules) ────────────────────────────

def read_soul():
    """Read the soul.md file. Returns empty string if not found."""
    try:
        with open(SOUL_FILE, 'r', encoding='utf-8') as f:
            return f.read().strip()
    except (FileNotFoundError, IOError):
        return ""

def write_soul(text):
    """Write text to soul.md file."""
    os.makedirs(os.path.dirname(SOUL_FILE), exist_ok=True)
    with open(SOUL_FILE, 'w', encoding='utf-8') as f:
        f.write(text.strip() + "\n")

# ── Secrets Vault ─────────────────────────────────────────
def _secrets_load():
    """Load secrets vault. Returns dict."""
    try:
        with open(SECRETS_FILE) as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return {}

def _secrets_save(secrets):
    """Save secrets vault."""
    os.makedirs(os.path.dirname(SECRETS_FILE), exist_ok=True)
    with open(SECRETS_FILE, 'w') as f:
        json.dump(secrets, f, indent=2)

# ── Promptshard System ────────────────────────────────────
# promptshard.md is a modular job assignment format.
# Each shard defines: objective, agent type, model caps, tools,
# skills, environment, domain prompt, secrets, and status.
# The captain agent reads shards and delegates to subagent teams.

PROMPTSHARD_DEFAULTS = """# promptshard: root
## objective: main session objective
## agent: captain
## model_capabilities: chat
## tools: bash, git, python3
## skills: 
## environment: terminal session
## prompt: |-
You are the captain agent coordinating specialized agent teams. Delegate tasks using /delegate or /spawn with quantum context syncing.
## secrets_requested: 
## status: active
## parent: 
"""

def read_promptshard():
    """Read promptshard.md. Returns parsed dict or defaults."""
    try:
        with open(PROMPTSHARD_FILE, 'r', encoding='utf-8') as f:
            raw = f.read()
    except (FileNotFoundError, IOError):
        raw = PROMPTSHARD_DEFAULTS
        os.makedirs(os.path.dirname(PROMPTSHARD_FILE), exist_ok=True)
        with open(PROMPTSHARD_FILE, 'w', encoding='utf-8') as f:
            f.write(raw)

    shard = {"raw": raw, "id": "root", "objective": "",
             "agent": "captain", "model_capabilities": "chat",
             "tools": "", "skills": "", "environment": "",
             "prompt": "", "secrets_requested": "",
             "status": "active", "parent": ""}
    for line in raw.split('\n'):
        if line.startswith('# promptshard:'):
            shard["id"] = line.split(':', 1)[1].strip()
        elif line.startswith('## objective:'):
            shard["objective"] = line.split(':', 1)[1].strip()
        elif line.startswith('## agent:'):
            shard["agent"] = line.split(':', 1)[1].strip()
        elif line.startswith('## model_capabilities:'):
            shard["model_capabilities"] = line.split(':', 1)[1].strip()
        elif line.startswith('## tools:'):
            shard["tools"] = line.split(':', 1)[1].strip()
        elif line.startswith('## skills:'):
            shard["skills"] = line.split(':', 1)[1].strip()
        elif line.startswith('## environment:'):
            shard["environment"] = line.split(':', 1)[1].strip()
        elif line.startswith('## prompt: |-'):
            shard["prompt"] = ""  # multi-line follows
        elif line.startswith('## secrets_requested:'):
            shard["secrets_requested"] = line.split(':', 1)[1].strip()
        elif line.startswith('## status:'):
            shard["status"] = line.split(':', 1)[1].strip()
        elif line.startswith('## parent:'):
            shard["parent"] = line.split(':', 1)[1].strip()
        elif shard["prompt"] is not None and not line.startswith('#') and not line.startswith('##'):
            if line.strip():
                if shard["prompt"] == "":
                    shard["prompt"] = line.strip()
                else:
                    shard["prompt"] += "\n" + line.strip()
    shard["prompt"] = shard["prompt"].rstrip('\n')
    return shard

def write_promptshard(shard):
    """Write a promptshard dict back to file."""
    lines = [f"# promptshard: {shard.get('id', 'root')}",
             f"## objective: {shard.get('objective', '')}",
             f"## agent: {shard.get('agent', 'captain')}",
             f"## model_capabilities: {shard.get('model_capabilities', 'chat')}",
             f"## tools: {shard.get('tools', '')}",
             f"## skills: {shard.get('skills', '')}",
             f"## environment: {shard.get('environment', '')}",
             f"## prompt: |-",
             shard.get('prompt', ''),
             f"## secrets_requested: {shard.get('secrets_requested', '')}",
             f"## status: {shard.get('status', 'active')}",
             f"## parent: {shard.get('parent', '')}",
             ""]
    text = "\n".join(lines)
    os.makedirs(os.path.dirname(PROMPTSHARD_FILE), exist_ok=True)
    with open(PROMPTSHARD_FILE, 'w', encoding='utf-8') as f:
        f.write(text)
    return shard

def shard_approve_secrets(shard, secrets):
    """Approve secrets for a shard. Stores in vault, injects into quantum."""
    vault = _secrets_load()
    vault[shard['id']] = secrets
    _secrets_save(vault)
    for k, v in secrets.items():
        _quantum.put(f"secret:{shard['id']}:{k}", v)

def shard_spawn_agent(shard):
    """Spawn a subagent from a promptshard definition."""
    if shard.get('status') in ('completed', 'expired'):
        return None
    task = f"{shard.get('objective', '')}\n\n{shard.get('prompt', '')}"
    model = shard.get('model_capabilities', '')
    # Pick a subagent model based on capabilities
    model_name = Config.SUBAGENT_MODEL or Config.MODEL
    caps = model.lower()
    if 'vision' in caps or 'image' in caps:
        pass  # Use current model (likely supports vision)
    sa = SubAgent(task, model=model_name, max_steps=Config.GOAL_MAX_STEPS)
    # Store shard context in quantum for this agent
    _quantum.put(f"shard:{sa.id}:id", shard['id'])
    _quantum.put(f"shard:{sa.id}:objective", shard['objective'])
    _quantum.put(f"shard:{sa.id}:tools", shard['tools'])
    _quantum.put(f"shard:{sa.id}:skills", shard['skills'])
    _quantum.put(f"shard:{sa.id}:environment", shard['environment'])
    # Mark status
    shard['status'] = 'active'
    write_promptshard(shard)
    return sa

def shard_mark_complete(shard_id, result=""):
    """Mark a promptshard as completed."""
    shard = read_promptshard()
    if shard.get('id') == shard_id:
        shard['status'] = 'completed'
        write_promptshard(shard)
    _quantum.put(f"shard:{shard_id}:result", result)
    _quantum.put(f"shard:{shard_id}:status", "completed")

# ── File-Cabinet Long-Term Memory (6,000 files) ─────────────
LONGTERM_DIR = os.path.join(os.path.expanduser("~"), ".prism32", "longterm")
LONGTERM_INDEX_FILE = os.path.join(LONGTERM_DIR, "index.json")
LONGTERM_MAX = 6000
_ltm_lock = threading.Lock()

def _default_ltm_index():
    return {"next_id": 1, "memories": {}}

def _load_ltm_index():
    try:
        with open(LONGTERM_INDEX_FILE) as f:
            idx = json.load(f)
        if "next_id" not in idx or "memories" not in idx:
            return _default_ltm_index()
        return idx
    except (FileNotFoundError, json.JSONDecodeError):
        return _default_ltm_index()

def _save_ltm_index(idx):
    os.makedirs(LONGTERM_DIR, exist_ok=True)
    try:
        with open(LONGTERM_INDEX_FILE, 'w') as f:
            json.dump(idx, f)
    except Exception:
        pass

def _ltm_path(mem_id):
    return os.path.join(LONGTERM_DIR, f"mem_{mem_id:07d}.json")

def ltm_store(content, source="user", tags=None, summary=None):
    with _ltm_lock:
        idx = _load_ltm_index()
        mid = idx["next_id"]
        idx["next_id"] = mid + 1
        now = datetime.now().isoformat()
        tags = tags or []
        summary = summary or (content[:120] + "..." if len(content) > 120 else content)
        entry = {
            "id": mid,
            "timestamp": now,
            "source": source,
            "summary": summary,
            "tags": tags,
        }
        idx["memories"][str(mid)] = entry
        # Prune oldest if over max
        memories = idx["memories"]
        while len(memories) > LONGTERM_MAX:
            oldest = min(memories.items(), key=lambda kv: kv[1].get("timestamp", ""))
            del memories[oldest[0]]
            try:
                os.remove(_ltm_path(int(oldest[0])))
            except OSError:
                pass
        _save_ltm_index(idx)
        # Write content file
        content_entry = {
            "id": mid,
            "timestamp": now,
            "content": content,
            "tags": tags,
        }
        os.makedirs(LONGTERM_DIR, exist_ok=True)
        with open(_ltm_path(mid), 'w') as f:
            json.dump(content_entry, f)
        return mid

def ltm_search(query, top_k=8):
    idx = _load_ltm_index()
    memories = idx.get("memories", {})
    query_lower = query.lower()
    scored = []
    for mid, entry in memories.items():
        score = 0
        if query_lower in entry.get("summary", "").lower():
            score += 3
        if query_lower in entry.get("tags", []):
            score += 2
        if query_lower in entry.get("source", "").lower():
            score += 1
        if score > 0:
            scored.append((score, mid, entry))
    scored.sort(key=lambda x: -x[0])
    results = []
    for score, mid, entry in scored[:top_k]:
        try:
            with open(_ltm_path(int(mid))) as f:
                content_entry = json.load(f)
            results.append({
                "id": mid,
                "score": score,
                "summary": entry.get("summary", ""),
                "timestamp": entry.get("timestamp", ""),
                "source": entry.get("source", ""),
                "content": content_entry.get("content", "")[:500],
            })
        except (FileNotFoundError, json.JSONDecodeError):
            pass
    return results

def ltm_list(limit=20):
    idx = _load_ltm_index()
    memories = idx.get("memories", {})
    sorted_mems = sorted(memories.items(), key=lambda kv: kv[1].get("timestamp", ""), reverse=True)
    results = []
    for mid, entry in sorted_mems[:limit]:
        try:
            with open(_ltm_path(int(mid))) as f:
                content_entry = json.load(f)
            results.append({
                "id": mid,
                "summary": entry.get("summary", ""),
                "timestamp": entry.get("timestamp", ""),
                "source": entry.get("source", ""),
                "content": content_entry.get("content", "")[:200],
            })
        except (FileNotFoundError, json.JSONDecodeError):
            pass
    return results

def ltm_delete(mid):
    with _ltm_lock:
        idx = _load_ltm_index()
        if str(mid) in idx["memories"]:
            del idx["memories"][str(mid)]
            _save_ltm_index(idx)
            try:
                os.remove(_ltm_path(mid))
            except OSError:
                pass
            return True
        return False

# ── Skill System (repeatable workflows/automations) ──────────
SKILLS_DIR = os.path.join(os.path.expanduser("~"), ".prism32", "skills")
AUTOMATIONS_DIR = os.path.join(os.path.expanduser("~"), ".prism32", "automations")

_AUTOMATION_SCHEDULER_RUNNING = False

def _skill_path(name):
    return os.path.join(SKILLS_DIR, f"{name}.json")

def skill_save(name, description, instructions, workflow=None, tags=None, source_session=""):
    os.makedirs(SKILLS_DIR, exist_ok=True)
    if not name.isalnum() and not name.replace("-", "").replace("_", "").isalnum():
        name = name.strip().lower().replace(" ", "-")
    path = _skill_path(name)
    skill = {
        "name": name,
        "version": 1,
        "description": description,
        "tags": tags or [],
        "instructions": instructions,
        "workflow": workflow or [],
        "created": datetime.now().isoformat(),
        "source_session": source_session,
    }
    with open(path, 'w') as f:
        json.dump(skill, f, indent=2)
    return name

def skill_load(name):
    path = _skill_path(name)
    try:
        with open(path) as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return None

def skill_list():
    os.makedirs(SKILLS_DIR, exist_ok=True)
    skills = []
    for fname in sorted(os.listdir(SKILLS_DIR)):
        if fname.endswith(".json"):
            try:
                with open(os.path.join(SKILLS_DIR, fname)) as f:
                    skill = json.load(f)
                skills.append(skill)
            except Exception:
                pass
    return skills

def skill_delete(name):
    path = _skill_path(name)
    if os.path.exists(path):
        os.remove(path)
        return True
    return False

def skill_inject(name):
    skill = skill_load(name)
    if not skill:
        return False
    instr = skill.get("instructions", "")
    workflow = skill.get("workflow", [])
    wf_text = ""
    if workflow:
        wf_text = "\nWorkflow steps:\n" + "\n".join(f"  {s['step']}. {s['action']}" for s in workflow)
    text = f"\n--- SKILL ACTIVE: {name} ---\n{skill.get('description', '')}\n{instr}{wf_text}\n---"
    marker = f"--- SKILL ACTIVE: {name} ---"
    for i, c in enumerate(_PluginHooks._extra_context):
        if marker in c:
            _PluginHooks._extra_context[i] = text
            return True
    _PluginHooks._extra_context.append(text)
    return True

def _prompt_skill_wizard():
    t = T()
    print(f"\n  {t['bright']}SKILL CREATION WIZARD{RST}")
    print(f"  {t['dim']}I will guide you through turning a workflow into a reusable skill.{RST}\n")
    try:
        name = input(rl_prompt(f"  {t['primary']}Skill name{RST} (e.g. install-nginx): ")).strip()
        if not name: return None
        name = name.lower().replace(" ", "-")
        desc = input(rl_prompt(f"  {t['primary']}Description{RST}: ")).strip()
        if not desc: desc = name
        print(f"\n  {t['dim']}Now describe the instructions for this skill: (end with empty line){RST}")
        lines = []
        while True:
            line = input(f"  {t['primary']}>{RST} ")
            if not line: break
            lines.append(line)
        instructions = "\n".join(lines)
        tags_raw = input(f"  {t['primary']}Tags{RST} (comma-separated, optional): ").strip()
        tags = [t.strip() for t in tags_raw.split(",")] if tags_raw else []
        print(f"\n  {t['dim']}Add workflow steps? (commands to run automatically){RST}")
        workflow = []
        step_num = 1
        if input(f"  Add step {step_num}? (Y/n): ").strip().lower() not in ("n", "no"):
            while True:
                action = input(f"  {t['primary']}Step {step_num} description{RST}: ").strip()
                if not action: break
                cmd = input(f"  {t['primary']}Command{RST} (leave empty if manual): ").strip()
                workflow.append({"step": step_num, "action": action, "command": cmd or None})
                step_num += 1
                if input(f"  Add another? (Y/n): ").strip().lower() in ("n", "no"):
                    break
        final_name = skill_save(name, desc, instructions, workflow, tags)
        print(f"\n  {t['ok']}Skill '{final_name}' saved!{RST}")
        print(f"  Load it anytime with:  {t['bright']}/skill-load {final_name}{RST}\n")
        return final_name
    except (KeyboardInterrupt, EOFError):
        print(f"\n  {t['warn']}Cancelled.{RST}")
        return None

# ── Automation System (scheduled / one-shot tasks) ────────────
_AUTO_LOCK = threading.Lock()

def _auto_path(aid):
    return os.path.join(AUTOMATIONS_DIR, f"{aid}.json")

def _auto_generate_id(description):
    h = hashlib.md5((description + str(time.time())).encode()).hexdigest()[:8]
    return f"auto_{datetime.now().strftime('%Y%m%d_%H%M%S')}_{h}"

def _auto_default(description, task, auto_type, interval=None, due_at=None):
    now = datetime.now()
    nxt = None
    if auto_type == "scheduled" and interval:
        nxt = (now.timestamp() + interval * 60)
    elif auto_type == "oneshot" and due_at:
        nxt = due_at
    return {
        "id": _auto_generate_id(description),
        "type": auto_type,
        "description": description,
        "task": task,
        "interval_minutes": interval,
        "due_at": due_at,
        "next_run": nxt,
        "last_run": None,
        "last_result": None,
        "last_success": None,
        "status": "active",
        "run_count": 0,
        "created_at": now.isoformat(),
        "history": [],
    }

def automation_save(auto):
    os.makedirs(AUTOMATIONS_DIR, exist_ok=True)
    with _AUTO_LOCK:
        with open(_auto_path(auto["id"]), "w") as f:
            json.dump(auto, f, indent=2)

def automation_load(aid):
    try:
        with open(_auto_path(aid)) as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return None

def automation_list():
    os.makedirs(AUTOMATIONS_DIR, exist_ok=True)
    results = []
    for fname in sorted(os.listdir(AUTOMATIONS_DIR)):
        if not fname.endswith(".json"):
            continue
        try:
            with open(os.path.join(AUTOMATIONS_DIR, fname)) as f:
                results.append(json.load(f))
        except (json.JSONDecodeError, OSError):
            continue
    return results

def automation_delete(aid):
    path = _auto_path(aid)
    if os.path.exists(path):
        os.remove(path)
        return True
    return False

def _extract_schedule_text(text):
    """Extract schedule portion from a natural language string by searching for known patterns."""
    t = text.strip().lower()
    
    # Try to find "every <daypart>" pattern
    for phrase in ["every morning", "every afternoon", "every evening", "every night", "every midnight",
                    "every hour", "hourly", "every monday", "every tuesday", "every wednesday",
                    "every thursday", "every friday", "every saturday", "every sunday"]:
        if phrase in t:
            return phrase
    
    # Try to find "every X minutes/hours/days" pattern
    m = re.search(r'every\s+\d+\s+(min|minute|minutes|hour|hours|day|days)\b', t)
    if m:
        return m.group(0)
    
    # Try to find "in X minutes/hours/days" pattern
    m = re.search(r'in\s+\d+\s+(min|minute|minutes|hour|hours|day|days)\b', t)
    if m:
        return m.group(0)
    
    # Try "tomorrow" or "tomorrow at..."
    m = re.search(r'tomorrow(?:\s+at\s+\d{1,2}(?::\d{2})?\s*(?:am|pm)?)?', t)
    if m:
        return m.group(0)
    
    # Try "now", "immediately", "asap"
    if t.endswith("now") or t.endswith("immediately") or t.endswith("asap"):
        return "now"
    
    return t

def _parse_schedule_text(text):
    """Parse natural language schedule into (auto_type, interval_minutes, due_timestamp, description)."""
    text = text.strip().lower()
    now = time.time()
    
    # "every X minutes" / "every X hours" / "every X days"
    m = re.match(r'every\s+(\d+)\s+(min|minute|minutes|hour|hours|day|days)\s*$', text)
    if m:
        num = int(m.group(1))
        unit = m.group(2)
        if unit.startswith("min"):
            return ("scheduled", num, None, text)
        elif unit.startswith("hour"):
            return ("scheduled", num * 60, None, text)
        else:
            return ("scheduled", num * 1440, None, text)
    
    # "every morning" → daily at 7:00
    if text == "every morning":
        nxt = int(now) - int(now) % 86400 + 25200  # today 07:00
        if nxt <= now:
            nxt += 86400
        return ("scheduled", 1440, nxt, "daily at 7:00 AM")
    
    # "every afternoon" → daily at 13:00
    if text == "every afternoon":
        nxt = int(now) - int(now) % 86400 + 46800
        if nxt <= now:
            nxt += 86400
        return ("scheduled", 1440, nxt, "daily at 1:00 PM")
    
    # "every evening" → daily at 18:00
    if text == "every evening":
        nxt = int(now) - int(now) % 86400 + 64800
        if nxt <= now:
            nxt += 86400
        return ("scheduled", 1440, nxt, "daily at 6:00 PM")
    
    # "every night" / "every midnight" → daily at 0:00
    if text in ("every night", "every midnight"):
        nxt = int(now) - int(now) % 86400
        if nxt <= now:
            nxt += 86400
        return ("scheduled", 1440, nxt, "daily at midnight")
    
    # "every hour" / "hourly"
    if text in ("every hour", "hourly"):
        nxt = int(now) - int(now) % 3600 + 3600
        return ("scheduled", 60, nxt, "every hour")
    
    # "every <weekday>" → weekly
    day_names = {"monday":0,"tuesday":1,"wednesday":2,"thursday":3,"friday":4,"saturday":5,"sunday":6}
    m = re.match(r'every\s+(monday|tuesday|wednesday|thursday|friday|saturday|sunday)\s*$', text)
    if m:
        target_wd = day_names[m.group(1)]
        current_wd = datetime.fromtimestamp(now).weekday()
        days_ahead = (target_wd - current_wd) % 7
        if days_ahead == 0:
            days_ahead = 7
        nxt = int(now) - int(now) % 86400 + days_ahead * 86400 + 32400  # 9:00 AM
        return ("scheduled", 10080, nxt, f"weekly on {m.group(1).title()} at 9:00 AM")
    
    # "in X minutes" / "in X hours" / "in X days"
    m = re.match(r'in\s+(\d+)\s+(min|minute|minutes|hour|hours|day|days)\s*$', text)
    if m:
        num = int(m.group(1))
        unit = m.group(2)
        if unit.startswith("min"):
            return ("oneshot", None, now + num * 60, text)
        elif unit.startswith("hour"):
            return ("oneshot", None, now + num * 3600, text)
        else:
            return ("oneshot", None, now + num * 86400, text)
    
    # "tomorrow" / "tomorrow at <time>"
    m = re.match(r'tomorrow(?:\s+at\s+(\d{1,2})(?::(\d{2}))?\s*(am|pm)?)?', text)
    if m:
        tomorrow = int(now) - int(now) % 86400 + 86400
        if m.group(1):
            hour = int(m.group(1))
            minute = int(m.group(2) or 0)
            if m.group(3) == "pm" and hour < 12:
                hour += 12
            if m.group(3) == "am" and hour == 12:
                hour = 0
            nxt = tomorrow + hour * 3600 + minute * 60
        else:
            nxt = tomorrow + 32400  # default 9:00 AM
        return ("oneshot", None, nxt, text)
    
    # "now" → immediate one-shot
    if text in ("now", "immediately", "asap"):
        return ("oneshot", None, now, "immediately")
    
    return None

def automation_parse_nl(user_text):
    """Parse natural language into automation fields using a compact AI call."""
    sys_msg = {"role": "system", "content": (
        "You extract automation parameters from user requests. "
        "Return ONLY valid JSON with these fields: "
        '{"type":"scheduled"|"oneshot", "description":"...", "task":"...", '
        '"schedule_text":"..."}. '
        "Examples:\n"
        '- "check my email every morning" → {"type":"scheduled", '
        '"description":"Check email daily", "task":"Check email and report new messages", '
        '"schedule_text":"every morning"}\n'
        '- "write a report with CNN top stories in 3 days" → {"type":"oneshot", '
        '"description":"Write CNN report", "task":"Scrape CNN top stories and write a report", '
        '"schedule_text":"in 3 days"}\n'
        "- Extract the actionable task clearly. Keep descriptions short."
    )}
    usr_msg = {"role": "user", "content": user_text}
    t = T()
    saved_stream = Config.STREAM
    Config.STREAM = False
    try:
        resp = ask_ai([sys_msg, usr_msg], stream=False)
    finally:
        Config.STREAM = saved_stream
    if not resp or resp.startswith("["):
        return None
    json_match = re.search(r'\{.*\}', resp, re.DOTALL)
    if not json_match:
        return None
    try:
        parsed = json.loads(json_match.group(0))
    except json.JSONDecodeError:
        return None
    return parsed

def automation_create_from_nl(user_text):
    """Full workflow: parse NL, resolve schedule, create automation."""
    parsed = automation_parse_nl(user_text)
    
    if parsed:
        auto_type = parsed.get("type", "oneshot")
        description = parsed.get("description", user_text[:80])
        task = parsed.get("task", user_text)
        schedule_text = parsed.get("schedule_text", "")
    else:
        auto_type = "oneshot"
        description = user_text[:80]
        task = user_text
        schedule_text = user_text
    
    # Try to match schedule_text against rule-based patterns
    result = _parse_schedule_text(schedule_text)
    
    if not result and not parsed:
        # Fallback: try to find a schedule pattern within the full text
        schedule_text = _extract_schedule_text(user_text)
        result = _parse_schedule_text(schedule_text)
    
    if result:
        ptype, interval, due_ts, sched_desc = result
    else:
        # Default: one-shot, 24h from now
        ptype, interval, due_ts = "oneshot", None, time.time() + 86400
        sched_desc = schedule_text
    
    auto = _auto_default(description, task, ptype, interval, due_ts)
    automation_save(auto)
    return auto

def _automation_next_run(auto):
    """Calculate and update next_run for a scheduled automation."""
    if auto["status"] != "active":
        return None
    if auto["type"] == "oneshot" and auto["run_count"] > 0:
        auto["status"] = "completed"
        automation_save(auto)
        return None
    if auto["type"] == "scheduled" and auto.get("interval_minutes"):
        auto["next_run"] = time.time() + auto["interval_minutes"] * 60
        automation_save(auto)
        return auto["next_run"]
    return None

def automation_execute(auto_id):
    """Execute an automation task. Called from scheduler thread."""
    auto = automation_load(auto_id)
    if not auto or auto["status"] != "active":
        return
    
    with stdout_lock:
        t = T()
        print(f"\n {t['bright']}[AUTO] Executing: {auto['description']}{RST}")
    
    sa = SubAgent(auto["task"], max_steps=Config.GOAL_MAX_STEPS)
    sa.run()
    
    auto = automation_load(auto_id)
    if not auto:
        return
    auto["last_run"] = time.time()
    auto["last_result"] = (sa.result or "")[:500]
    auto["last_success"] = sa.result is not None
    auto["run_count"] = auto.get("run_count", 0) + 1
    history_entry = {
        "timestamp": datetime.now().isoformat(),
        "success": sa.result is not None,
        "snippet": (sa.result or "")[:200],
    }
    auto.setdefault("history", []).append(history_entry)
    if auto["type"] == "oneshot":
        auto["status"] = "completed"
    _automation_next_run(auto)
    automation_save(auto)
    
    with stdout_lock:
        if sa.result:
            print(f" {t['ok']}[AUTO] Completed: {auto['description']}{RST}")
        else:
            print(f" {t['err']}[AUTO] Failed: {auto['description']}{RST}")

def _automation_scheduler_loop():
    """Daemon thread: check for due automations every 30s."""
    global _AUTOMATION_SCHEDULER_RUNNING
    _AUTOMATION_SCHEDULER_RUNNING = True
    while not _shutdown_flag:
        time.sleep(30)
        if _shutdown_flag:
            break
        try:
            all_autos = automation_list()
            now_ts = time.time()
            for auto in all_autos:
                if auto.get("status") != "active":
                    continue
                nxt = auto.get("next_run")
                if nxt and nxt <= now_ts:
                    automation_execute(auto["id"])
        except Exception:
            pass
    _AUTOMATION_SCHEDULER_RUNNING = False

def learn_command(cmd_name, success=True, duration=0):
    global _MEMORY_DIRTY, _MEMORY_FLUSH_COUNTER
    stats = _mem_cache.setdefault("command_stats", {})
    entry = stats.setdefault(cmd_name, {"uses": 0, "failures": 0, "total_time": 0})
    entry["uses"] += 1
    if not success:
        entry["failures"] += 1
    entry["total_time"] += duration
    _MEMORY_DIRTY = True
    _MEMORY_FLUSH_COUNTER += 1
    _flush_memory()
    _MEMORY_FLUSH_COUNTER = 0

def learn_error(error_msg, context=""):
    mem = load_memory()
    patterns = mem.setdefault("error_patterns", {})
    fp = error_msg[:80] if error_msg else "unknown"
    entry = patterns.setdefault(fp, {"count": 0, "contexts": [], "fixed": False})
    entry["count"] += 1
    if context and len(entry["contexts"]) < 5:
        entry["contexts"].append(context[:120])
    save_memory(mem)

def learn_session(history_len, cmd_count, goal_mode=False):
    mem = load_memory()
    mem["session_count"] = mem.get("session_count", 0) + 1
    mem["last_session"] = {
        "time": datetime.now().isoformat(),
        "messages": history_len,
        "commands": cmd_count,
        "goal": goal_mode
    }
    save_memory(mem)

def get_memory_suggestions():
    mem = load_memory()
    hints = []
    for cmd, data in mem.get("command_stats", {}).items():
        f = data.get("failures", 0)
        if f > 3:
            hints.append(f"'{cmd}' has {f} failures -- check config or retry logic")
    for err, data in mem.get("error_patterns", {}).items():
        c = data.get("count", 0)
        if c > 2 and not data.get("fixed"):
            hints.append(f"Recurring error ({c}x): {err[:50]}")
    return hints

def memory_context():
    mem = _mem_cache
    parts = []
    # System context
    info = get_system_info()
    parts.append(f"{info.get('os', '')[:12]} {info.get('arch', '')}")
    parts.append(f"{info.get('cpu', '')[:20]}")
    parts.append(f"ram:{info.get('ram', '')}mb")
    parts.append(f"disk:{info.get('disk', '')[:10]}")
    parts.append(f"ip:{info.get('ip', '')}")
    parts.append(f"cwd:{os.getcwd()}")
    parts.append(f"user:{os.getenv('USER') or os.getenv('USERNAME') or '?'}")
    profile = mem.get("system_profile", {})
    if profile:
        if profile.get("shell"):
            parts.append(f"shell:{os.path.basename(profile.get('shell', ''))[:16]}")
        if profile.get("package_manager"):
            parts.append(f"pkg:{profile.get('package_manager')}")
        if profile.get("terminal"):
            parts.append(f"term:{str(profile.get('terminal'))[:16]}")
    from datetime import datetime
    parts.append(f"time:{datetime.now().strftime('%H:%M')}")
    # Learned patterns
    stats = mem.get("command_stats", {})
    if stats:
        top = sorted(stats.items(), key=lambda x: -x[1]["uses"])[:3]
        parts.append("top:" + ",".join(f"{n}({d['uses']})" for n, d in top))
    errors = mem.get("error_patterns", {})
    bad = {k: v for k, v in errors.items() if v["count"] > 1}
    if bad:
        worst = max(bad.items(), key=lambda x: x[1]["count"])
        parts.append(f"err_rep:{worst[1]['count']}x")
    sess = mem.get("session_count", 0)
    if sess:
        parts.append(f"sessions:{sess}")
    try:
        hdata = load_harnesses()
        if hdata.get("installed"):
            parts.append("harness:" + ",".join(h.get("id", "?") for h in hdata.get("installed", [])[:3]))
    except Exception:
        pass
    result = " [" + " | ".join(parts) + "]" if parts else ""
    limit = getattr(Config, "MAX_MEMORY_CTX", 1024)
    if limit <= 0:
        return ""
    return result[:limit]

# Resilient shutdown
def _cleanup():
    _flush_memory()

    if ansi_enabled():
        print("\r" + SHOW + RST, end="", flush=True)
atexit.register(_cleanup)

_shutdown_flag = False
def _do_git_update(project_dir=None):
    t = T()
    if not project_dir:
        project_dir = os.path.dirname(os.path.realpath(sys.argv[0]))
    install_sh = os.path.join(project_dir, "install.sh")
    if not os.path.exists(os.path.join(project_dir, ".git")):
        print(f"  {t['err']}No .git directory found in {project_dir}{RST}")
        print(f"  {t['dim']}Clone the repo first: git clone <url> prism32{RST}")
        return
    if not os.path.exists(install_sh):
        print(f"  {t['err']}install.sh not found in {project_dir}{RST}")
        return
    print(f"  {t['bright']}Updating prism32 from {project_dir}...{RST}")
    pull = subprocess.run("git pull", shell=True, capture_output=True, text=True, cwd=project_dir)
    if pull.returncode != 0:
        print(f"  {t['err']}git pull failed:{RST}\n  {pull.stderr[:300]}")
        return
    print(f"  {pull.stdout.strip()}")
    result = subprocess.run(["bash", install_sh, "-y"], capture_output=True, text=True, cwd=project_dir)
    if result.returncode == 0:
        print(f"  {t['ok']}Update complete. Restart prism32 to use the new version.{RST}")
    else:
        print(f"  {t['err']}Install failed:{RST}\n  {result.stderr[:500]}")

def _handle_sigterm(sig, frame):
    global _shutdown_flag
    _shutdown_flag = True
    # Do NOT write to stdout here -- can race with SpinnerThread
    sys.exit(0)

if hasattr(signal, 'SIGTERM'):
    signal.signal(signal.SIGTERM, _handle_sigterm)
signal.signal(signal.SIGINT, _handle_sigterm)

# ── Platform Detection ──────────────────────────────────────────

_legacy_plat = sys.platform.lower()
class Platform:
    """Cross-platform detection and compatibility."""

    LINUX = _legacy_plat.startswith("linux")
    MACOS = _legacy_plat == 'darwin'
    WINDOWS = _legacy_plat == 'win32'
    BSD = 'bsd' in _legacy_plat or _legacy_plat.startswith('netbsd')
    IRIX = _legacy_plat.startswith('irix')
    HPUX = _legacy_plat.startswith('hp-ux') or _legacy_plat.startswith('hpux')
    AIX = _legacy_plat.startswith('aix')
    SOLARIS = _legacy_plat.startswith('sunos')  # sunos5 = Solaris 10+
    TRU64 = _legacy_plat.startswith('osf1')     # Tru64 / Digital UNIX
    HAIKU = _legacy_plat.startswith('haiku')
    QNX = _legacy_plat.startswith('nto') or _legacy_plat.startswith('qnx')
    MINIX = _legacy_plat.startswith('minix')
    CYGWIN = _legacy_plat.startswith('cygwin')
    MSYS = _legacy_plat.startswith('msys') or _legacy_plat.startswith('mingw')
    ZOS = _legacy_plat.startswith('zos')
    IBM_I = _legacy_plat.startswith('os400') or _legacy_plat.startswith('as400')
    OPENVMS = 'openvms' in _legacy_plat or _legacy_plat.startswith('vms')
    TERMUX = LINUX and os.environ.get('TERMUX_VERSION', '') != ''
    ANDROID = TERMUX or os.environ.get('ANDROID_ROOT', '') != ''

    @staticmethod
    def _read_key_value_file(path):
        data = {}
        try:
            with open(path) as f:
                for line in f:
                    if '=' in line:
                        key, val = line.split('=', 1)
                        data[key.strip()] = val.strip().strip('"')
        except Exception:
            pass
        return data

    @staticmethod
    def _linux_release_name():
        data = Platform._read_key_value_file('/etc/os-release')
        return data.get('PRETTY_NAME') or data.get('NAME') or ""

    @staticmethod
    def is_wsl():
        if os.environ.get('WSL_DISTRO_NAME') or os.environ.get('WSL_INTEROP'):
            return True
        try:
            with open('/proc/version') as f:
                return 'microsoft' in f.read().lower()
        except Exception:
            return False

    @staticmethod
    def is_container():
        if os.environ.get('container') or os.path.exists('/.dockerenv') or os.path.exists('/run/.containerenv'):
            return True
        try:
            with open('/proc/1/cgroup') as f:
                text = f.read().lower()
            return any(x in text for x in ('docker', 'kubepods', 'containerd', 'podman', 'lxc'))
        except Exception:
            return False

    @staticmethod
    def _linux_special_name():
        checks = [
            ('/etc/unraid-version', 'Unraid'),
            ('/etc/truenas-release', 'TrueNAS SCALE'),
            ('/etc/ix-release', 'TrueNAS SCALE'),
            ('/etc/openwrt_release', 'OpenWrt'),
            ('/etc/os-release', ''),
        ]
        for path, name in checks:
            if name and os.path.exists(path):
                return name
        if os.path.exists('/etc/pve') or shutil.which('pveversion'):
            return 'Proxmox VE'
        if os.path.exists('/mnt/chromeos') or os.path.exists('/dev/.cros_milestone'):
            return 'ChromeOS/Crostini'
        return ""

    @staticmethod
    def get_windows_name():
        """Return a friendly Windows version name without requiring new APIs."""
        try:
            release, version, csd, ptype = platform.win32_ver()
            build = 0
            parts = (version or "").split('.')
            if len(parts) >= 3:
                build = int(parts[2])
            if release == "10" and build >= 22000:
                return "Windows 11"
            if release:
                return f"Windows {release}"
        except Exception:
            pass
        return "Windows"

    @staticmethod
    def get_system():
        """Get the operating system name."""
        if Platform.TERMUX:
            return "Android (Termux)"
        if Platform.ANDROID:
            return "Android"
        if Platform.MACOS:
            return "macOS"
        if Platform.IRIX:
            return "IRIX"
        if Platform.HPUX:
            return "HP-UX"
        if Platform.AIX:
            return "AIX"
        if Platform.SOLARIS:
            try:
                with open('/etc/release') as f:
                    first = f.readline().strip()
                    if first:
                        return first
            except Exception:
                pass
            try:
                result = subprocess.run(['uname', '-sr'], capture_output=True, text=True)
                if result.returncode == 0 and result.stdout.strip():
                    return result.stdout.strip()
            except Exception:
                pass
            return "Solaris/SunOS"
        if Platform.TRU64:
            return "Tru64"
        if Platform.HAIKU:
            return "Haiku"
        if Platform.QNX:
            return "QNX Neutrino"
        if Platform.MINIX:
            return "MINIX"
        if Platform.CYGWIN:
            return "Cygwin"
        if Platform.MSYS:
            return "MSYS2/MinGW"
        if Platform.ZOS:
            return "IBM z/OS"
        if Platform.IBM_I:
            return "IBM i PASE"
        if Platform.OPENVMS:
            return "OpenVMS"
        if Platform.LINUX:
            special = Platform._linux_special_name()
            base = special or Platform._linux_release_name()
            for rel in ('/etc/redhat-release', '/etc/SuSE-release',
                        '/etc/slackware-version', '/etc/gentoo-release'):
                try:
                    with open(rel) as f:
                        base = base or f.readline().strip()
                except Exception:
                    pass
            try:
                import subprocess
                result = subprocess.run(['uname', '-sr'], capture_output=True, text=True)
                if result.returncode == 0 and not base:
                    base = result.stdout.strip()
            except Exception:
                pass
            base = base or "Linux"
            tags = []
            if Platform.is_wsl():
                tags.append("WSL")
            if Platform.is_container():
                tags.append("container")
            if os.path.exists('/.flatpak-info'):
                tags.append("Flatpak sandbox")
            return base + (" (" + ", ".join(tags) + ")" if tags else "")
        if Platform.WINDOWS:
            return Platform.get_windows_name()
        if Platform.BSD:
            for path in ('/etc/version', '/etc/platform', '/conf/base/etc/version'):
                try:
                    with open(path) as f:
                        val = f.readline().strip()
                    low = val.lower()
                    if 'pfsense' in low:
                        return 'pfSense'
                    if 'opnsense' in low:
                        return 'OPNsense'
                    if 'truenas' in low or 'freenas' in low:
                        return val
                except Exception:
                    pass
            if os.path.exists('/etc/rc.freenas'):
                return 'TrueNAS/FreeNAS'
            return "BSD"
        return platform.system()

    @staticmethod
    def get_arch():
        """Get system architecture, with custom chip override support.

        Resolution order:
        1. PRISM32_ARCH environment variable (manual override)
        2. Exact match in built-in arch_map
        3. Prefix match in built-in arch_map
        4. Config.CUSTOM_ARCH_MAP (user-defined patterns, supports * wildcard)
        5. platform.machine() raw value
        """
        override = os.environ.get('PRISM32_ARCH', '')
        if override:
            return override

        machine = platform.machine()
        arch_map = {
            'x86_64': 'x86_64',
            'AMD64': 'x86_64',
            'amd64': 'x86_64',
            'i386': 'i686',
            'i486': 'i686',
            'i586': 'i686',
            'i686': 'i686',
            'i86pc': 'Solaris x86',
            'aarch64': 'ARM64',
            'aarch64_be': 'ARM64 BE',
            'arm64': 'ARM64',
            'armv8l': 'ARMv8',
            'armv8': 'ARMv8',
            'armv7l': 'ARMv7',
            'armv7': 'ARMv7',
            'armv7a': 'ARMv7',
            'armhf': 'ARM hard-float',
            'armv6l': 'ARMv6',
            'armv6': 'ARMv6',
            'armv5tel': 'ARMv5TE',
            'armel': 'ARM soft-float',
            'arm': 'ARM',
            'loongarch64': 'LoongArch 64',
            'loong64': 'LoongArch 64',
            'riscv64': 'RISC-V 64',
            'riscv32': 'RISC-V 32',
            'riscv': 'RISC-V',
            'ppc': 'PowerPC',
            'ppc64': 'PowerPC 64',
            'ppc64le': 'PowerPC 64 LE',
            'powerpc': 'PowerPC',
            'powerpc64': 'PowerPC 64',
            'mips': 'MIPS',
            'mips64': 'MIPS64',
            'mips64el': 'MIPS64 LE',
            'mipsel': 'MIPS LE',
            'mipsisa32r2el': 'MIPS32r2 LE',
            'mipsisa32r6el': 'MIPS32r6 LE',
            'mipsisa64r6el': 'MIPS64r6 LE',
            'sparc': 'SPARC',
            'sparc64': 'SPARC 64',
            'sparcv9': 'SPARC 64',
            'sun4u': 'SPARC 64',
            'sun4v': 'SPARC 64',
            'sun4us': 'SPARC 64',
            'sun4m': 'SPARC',
            'sun4d': 'SPARC',
            'sun4': 'SPARC',
            's390': 'S/390',
            's390x': 'S/390x',
            'zarch': 'IBM Z',
            'alpha': 'Alpha',
            'hppa': 'PA-RISC',
            'parisc': 'PA-RISC',
            'ia64': 'Itanium',
            'rs6000': 'POWER',
            'power': 'POWER',
            'powerpcspe': 'PowerPC SPE',
            'pmac': 'PowerPC',
            'e2k': 'Elbrus',
            'vax': 'VAX',
            'IP': 'MIPS',  # SGI IP* (IP27, IP30, IP35)
        }

        # 1. Exact match
        result = arch_map.get(machine)
        if result:
            return result

        # 2. Prefix match for entries that are prefixes of the machine string
        for pattern, label in sorted(arch_map.items(), key=lambda x: -len(x[0])):
            if machine.startswith(pattern):
                return label

        # 3. Custom user-defined arch map (supports * wildcard)
        machine_lower = machine.lower()
        for pattern, label in Config.CUSTOM_ARCH_MAP.items():
            pat = pattern.lower()
            if '*' in pat:
                prefix, suffix = pat.split('*', 1)
                if machine_lower.startswith(prefix) and machine_lower.endswith(suffix):
                    return label
            elif machine_lower == pat or machine.startswith(pattern):
                return label

        return machine

    @staticmethod
    def _run_cmd(args):
        try:
            import subprocess
            result = subprocess.run(args, capture_output=True, text=True, timeout=5)
            return result.stdout.strip()
        except Exception:
            return ""

    @staticmethod
    def get_cpu():
        """Get CPU model name."""
        try:
            if Platform.LINUX:
                with open('/proc/cpuinfo') as f:
                    for line in f:
                        if line.startswith('model name'):
                            return line.split(':')[1].strip()
            elif Platform.MACOS:
                return Platform._run_cmd(['sysctl', '-n', 'machdep.cpu.brand_string'])
            elif Platform.WINDOWS:
                result = Platform._run_cmd(['wmic', 'cpu', 'get', 'name'])
                lines = result.strip().split('\n')
                if len(lines) > 1:
                    return lines[1].strip()
            elif Platform.BSD:
                return Platform._run_cmd(['sysctl', '-n', 'hw.model']) or "Unknown CPU"
            elif Platform.AIX:
                out = Platform._run_cmd(['prtconf'])
                for line in out.split('\n'):
                    if 'Processor Type' in line or 'Number Of Processors' in line:
                        return line.split(':')[-1].strip()
                return Platform._run_cmd(['lsattr', '-El', 'proc0', '-a', 'type']) or "Unknown CPU"
            elif Platform.HPUX:
                out = Platform._run_cmd(['machinfo'])
                for line in out.split('\n'):
                    if 'processor' in line.lower() and 'Intel' in line or 'model' in line.lower():
                        return line.strip()
                return Platform._run_cmd(['ioscan', '-kfC', 'processor']) or "Unknown CPU"
            elif Platform.SOLARIS:
                out = Platform._run_cmd(['psrinfo', '-v'])
                for line in out.split('\n'):
                    if 'processor' in line.lower() and 'operates' in line.lower():
                        return line.strip()
                return Platform._run_cmd(['isainfo', '-v']) or "Unknown CPU"
            elif Platform.IRIX:
                out = Platform._run_cmd(['hinv'])
                for line in out.split('\n'):
                    if 'CPU' in line or 'Processor' in line or 'MIPS' in line:
                        return line.strip()
                return "Unknown CPU"
            elif Platform.TRU64:
                out = Platform._run_cmd(['sizer', '-v'])
                if out:
                    return out
                return Platform._run_cmd(['psrinfo']) or "Unknown CPU"
        except Exception:
            pass
        return platform.processor() or "Unknown CPU"

    @staticmethod
    def get_ram():
        """Get total RAM in MB."""
        try:
            if Platform.LINUX:
                with open('/proc/meminfo') as f:
                    total = int(f.readline().split()[1])
                    return total // 1024
            elif Platform.MACOS:
                return int(Platform._run_cmd(['sysctl', '-n', 'hw.memsize']) or '0') // (1024 * 1024)
            elif Platform.WINDOWS:
                result = Platform._run_cmd(['wmic', 'OS', 'get', 'TotalVisibleMemorySize'])
                lines = result.strip().split('\n')
                if len(lines) > 1:
                    return int(lines[1].strip()) // 1024
            elif Platform.BSD:
                return int(Platform._run_cmd(['sysctl', '-n', 'hw.physmem']) or '0') // (1024 * 1024)
            elif Platform.AIX:
                out = Platform._run_cmd(['prtconf'])
                for line in out.split('\n'):
                    if 'Memory' in line or 'Good Size' in line:
                        parts = line.split()
                        for p in parts:
                            try:
                                return int(p)
                            except ValueError:
                                continue
                return 0
            elif Platform.HPUX:
                out = Platform._run_cmd(['machinfo'])
                for line in out.split('\n'):
                    if 'Memory' in line or 'RAM' in line or 'Physical' in line:
                        parts = line.split()
                        for i, p in enumerate(parts):
                            if p == 'MB':
                                return int(parts[i-1])
                            if p == 'GB':
                                return int(float(parts[i-1]) * 1024)
                return 0
            elif Platform.SOLARIS:
                out = Platform._run_cmd(['prtconf'])
                for line in out.split('\n'):
                    if 'Memory' in line or 'memory' in line:
                        parts = line.split()
                        for i, p in enumerate(parts):
                            if p in ('MB', 'megabytes'):
                                return int(parts[i-1])
                            if p in ('GB', 'gigabytes'):
                                return int(float(parts[i-1]) * 1024)
                return 0
            elif Platform.IRIX:
                out = Platform._run_cmd(['hinv'])
                for line in out.split('\n'):
                    if 'Memory' in line or 'Main memory' in line:
                        parts = line.split()
                        for i, p in enumerate(parts):
                            if p == 'MB':
                                return int(parts[i-1])
                            if p == 'GB':
                                return int(float(parts[i-1]) * 1024)
                return 0
            elif Platform.TRU64:
                out = Platform._run_cmd(['uerf', '-r', '300'])
                if not out:
                    out = Platform._run_cmd(['vmstat', '-P'])
                return 0
        except Exception:
            pass
        return 0

    @staticmethod
    def get_uptime():
        """Get system uptime as string."""
        try:
            secs = 0
            if Platform.LINUX:
                with open('/proc/uptime') as f:
                    secs = float(f.read().split()[0])
            elif Platform.MACOS or Platform.BSD:
                import re, time
                result = Platform._run_cmd(['sysctl', '-n', 'kern.boottime'])
                m = re.search(r'sec\s*=\s*(\d+)', result)
                boot_time = int(m.group(1)) if m else 0
                secs = time.time() - boot_time
            elif Platform.AIX:
                import re
                out = Platform._run_cmd(['uptime'])
                m = re.search(r'up\s+(\d+)\s+days?', out)
                if m:
                    return f"{m.group(1)}d 0h"
                m = re.search(r'up\s+(\d+):(\d+)', out)
                if m:
                    return f"0d {m.group(1)}h"
                return "N/A"
            elif Platform.HPUX:
                import re
                out = Platform._run_cmd(['uptime'])
                m = re.search(r'up\s+(\d+)\s+days?', out)
                if m:
                    return f"{m.group(1)}d 0h"
                m = re.search(r'up\s+(\d+):(\d+)', out)
                if m:
                    return f"0d {m.group(1)}h"
                return "N/A"
            elif Platform.SOLARIS:
                import re
                out = Platform._run_cmd(['prtconf', '-v'])
                out2 = Platform._run_cmd(['kstat', '-p', 'unix:0:system_misc:boot_time'])
                if out2:
                    try:
                        boot_time = int(out2.split()[-1])
                        import time
                        secs = time.time() - boot_time
                    except (ValueError, IndexError):
                        out = Platform._run_cmd(['uptime'])
                        m = re.search(r'up\s+(\d+)\s+days?', out)
                        if m:
                            return f"{m.group(1)}d 0h"
                        return "N/A"
                else:
                    return "N/A"
            elif Platform.IRIX:
                import re
                out = Platform._run_cmd(['uptime'])
                m = re.search(r'up\s+(\d+)\s+days?', out)
                if m:
                    return f"{m.group(1)}d 0h"
                return "N/A"
            elif Platform.TRU64:
                import re
                out = Platform._run_cmd(['uptime'])
                m = re.search(r'up\s+(\d+)\s+days?', out)
                if m:
                    return f"{m.group(1)}d 0h"
                return "N/A"
            elif Platform.WINDOWS:
                out = Platform._run_cmd(['wmic', 'os', 'get', 'lastbootuptime', '/value'])
                for line in out.split('\n'):
                    if line.lower().startswith('lastbootuptime='):
                        stamp = line.split('=', 1)[1].strip()[:14]
                        try:
                            boot = datetime.strptime(stamp, '%Y%m%d%H%M%S')
                            secs = (datetime.now() - boot).total_seconds()
                            break
                        except Exception:
                            return "N/A"
                else:
                    return "N/A"
            else:
                return "N/A"

            days = int(secs // 86400)
            hours = int((secs % 86400) // 3600)
            return f"{days}d {hours}h"
        except Exception:
            return "N/A"

    @staticmethod
    def get_package_manager():
        """Detect available package manager (OS-aware)."""
        plat = sys.platform.lower()

        if Platform.TERMUX:
            check_order = [
                ('pkg', 'termux-pkg'), ('apt', 'apt'), ('apt-get', 'apt'),
            ]
        elif plat == 'darwin':
            check_order = [
                ('brew', 'brew'), ('port', 'macports'),
                ('pkgin', 'pkgin'), ('pkg_add', 'pkg_add'), ('pkg', 'pkg'),
            ]
        elif 'bsd' in plat:
            check_order = [
                ('pkgin', 'pkgin'), ('pkg_add', 'pkg_add'), ('pkg', 'pkg'),
                ('brew', 'brew'), ('port', 'macports'),
            ]
        elif 'linux' in plat:
            check_order = [
                ('apt', 'apt'), ('apt-get', 'apt'), ('dnf', 'dnf'), ('microdnf', 'microdnf'), ('tdnf', 'tdnf'), ('yum', 'yum'),
                ('pacman', 'pacman'), ('zypper', 'zypper'), ('apk', 'apk'),
                ('rpm-ostree', 'rpm-ostree'), ('swupd', 'swupd'),
                ('opkg', 'opkg'), ('ipkg', 'ipkg'), ('emerge', 'emerge'),
                ('xbps-install', 'xbps'), ('eopkg', 'eopkg'), ('slackpkg', 'slackpkg'),
                ('pkgtool', 'pkgtool'), ('guix', 'guix'), ('nix-env', 'nix'),
                ('snap', 'snap'), ('flatpak', 'flatpak'), ('synopkg', 'synopkg'),
                ('brew', 'brew'), ('port', 'macports'),
                ('pkgin', 'pkgin'), ('pkg_add', 'pkg_add'), ('pkg', 'pkg'),
            ]
        elif 'win32' in plat:
            check_order = [
                ('winget', 'winget'), ('choco', 'chocolatey'), ('scoop', 'scoop'),
            ]
        elif 'hp-ux' in plat or 'hpux' in plat:
            check_order = [
                ('swinstall', 'swinstall'), ('swlist', 'swinstall'),
            ]
        elif plat.startswith('aix'):
            check_order = [
                ('installp', 'installp'), ('yum', 'yum'), ('rpm', 'rpm'),
            ]
        elif plat.startswith('sunos'):
            check_order = [
                ('pkg', 'solaris-pkg'), ('pkgin', 'pkgin'), ('pkgadd', 'pkgadd'), ('pkgutil', 'pkgutil'), ('pkgrm', 'pkgadd'),
            ]
        elif Platform.HAIKU:
            check_order = [
                ('pkgman', 'pkgman'),
            ]
        elif Platform.QNX:
            check_order = [
                ('pkg', 'qnx-pkg'), ('opkg', 'opkg'),
            ]
        elif Platform.CYGWIN:
            check_order = [
                ('apt-cyg', 'apt-cyg'), ('setup-x86_64', 'cygwin-setup'), ('setup-x86', 'cygwin-setup'),
            ]
        elif Platform.MSYS:
            check_order = [
                ('pacman', 'pacman'),
            ]
        elif plat.startswith('irix'):
            check_order = [
                ('inst', 'inst'), ('versions', 'inst'),
            ]
        elif plat.startswith('osf1'):
            check_order = [
                ('setld', 'setld'), ('dpkg', 'dpkg'), ('rpm', 'rpm'),
            ]
        else:
            check_order = [
                ('brew', 'brew'), ('port', 'macports'),
                ('apt', 'apt'), ('apt-get', 'apt'), ('dnf', 'dnf'), ('microdnf', 'microdnf'), ('tdnf', 'tdnf'), ('yum', 'yum'),
                ('pacman', 'pacman'), ('zypper', 'zypper'), ('apk', 'apk'), ('rpm-ostree', 'rpm-ostree'), ('swupd', 'swupd'), ('opkg', 'opkg'), ('ipkg', 'ipkg'),
                ('emerge', 'emerge'), ('xbps-install', 'xbps'), ('eopkg', 'eopkg'), ('slackpkg', 'slackpkg'),
                ('guix', 'guix'), ('nix-env', 'nix'), ('snap', 'snap'), ('flatpak', 'flatpak'),
                ('pkgin', 'pkgin'), ('pkg_add', 'pkg_add'), ('pkg', 'pkg'),
                ('swinstall', 'swinstall'), ('inst', 'inst'), ('setld', 'setld'),
                ('installp', 'installp'), ('pkgadd', 'pkgadd'), ('pkgman', 'pkgman'), ('pkgutil', 'pkgutil'),
            ]

        for cmd_name, name in check_order:
            try:
                if shutil.which(cmd_name):
                    return name
            except Exception:
                pass

        return None

    @staticmethod
    def get_install_command(package):
        """Get the install command for the detected package manager."""
        pm = Platform.get_package_manager()

        commands = {
            'apt': f'sudo apt-get install -y {package}',
            'dnf': f'sudo dnf install -y {package}',
            'microdnf': f'sudo microdnf install -y {package}',
            'tdnf': f'sudo tdnf install -y {package}',
            'yum': f'sudo yum install -y {package}',
            'pacman': f'sudo pacman -S --noconfirm {package}',
            'zypper': f'sudo zypper install -y {package}',
            'apk': f'sudo apk add {package}',
            'rpm-ostree': f'sudo rpm-ostree install {package} && systemctl reboot',
            'swupd': f'sudo swupd bundle-add {package}',
            'termux-pkg': f'pkg install -y {package}',
            'opkg': f'opkg install {package}',
            'ipkg': f'ipkg install {package}',
            'emerge': f'sudo emerge {package}',
            'xbps': f'sudo xbps-install -S {package}',
            'eopkg': f'sudo eopkg install -y {package}',
            'slackpkg': f'sudo slackpkg install {package}',
            'pkgtool': f'sudo pkgtool # install {package} manually',
            'guix': f'guix install {package}',
            'nix': f'nix-env -iA {package}',
            'snap': f'sudo snap install {package}',
            'flatpak': f'flatpak install -y flathub {package}',
            'brew': f'brew install {package}',
            'macports': f'sudo port install {package}',
            'pkgin': f'sudo pkgin install {package}',
            'pkg_add': f'sudo pkg_add {package}',
            'pkg': f'sudo pkg install -y {package}',
            'pkgman': f'pkgman install {package}',
            'qnx-pkg': f'pkg install {package}',
            'winget': f'winget install {package}',
            'chocolatey': f'choco install {package}',
            'scoop': f'scoop install {package}',
            'swinstall': f'sudo swinstall -x mount_all=false {package}',
            'inst': f'sudo inst -f {package}',
            'setld': f'sudo setld -l {package}',
            'installp': f'sudo installp -acgXd . {package}',
            'solaris-pkg': f'sudo pkg install {package}',
            'pkgutil': f'sudo pkgutil -i {package}',
            'pkgadd': f'sudo pkgadd -d . {package}',
            'apt-cyg': f'apt-cyg install {package}',
            'cygwin-setup': f'setup-x86_64 -q -P {package}',
            'synopkg': f'synopkg # install {package} from Package Center or Entware',
        }

        return commands.get(pm, f'echo "Install {package} using your package manager"')

    @staticmethod
    def get_ip():
        """Get a best-effort primary IPv4 address without platform tools."""
        try:
            s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            s.connect(("8.8.8.8", 80))
            ip = s.getsockname()[0]
            s.close()
            return ip
        except Exception:
            try:
                return socket.gethostbyname(socket.gethostname())
            except Exception:
                return "N/A"

    @staticmethod
    def get_network_command():
        """Get the appropriate network command."""
        if Platform.WINDOWS:
            return "ipconfig"
        if Platform.LINUX:
            return "ip"
        return "ifconfig"

    @staticmethod
    def is_root():
        """Check if running as root."""
        if Platform.WINDOWS:
            import ctypes
            return ctypes.windll.shell32.IsUserAnAdmin() != 0
        return os.geteuid() == 0

# ── Config ───────────────────────────────────────────────────

class Config:
    API_BASE = "http://127.0.0.1:8080"
    MODEL = "deepseek/deepseek-v4-flash"
    API_KEY = ""
    MAX_HISTORY = 2000
    CMD_TIMEOUT = 600
    MAX_RESPONSE_TOKENS = 8192
    TEMPERATURE = 0.7
    THEME = "phosphor"
    GOAL_MAX_STEPS = 50
    GOAL_STEP_DELAY = 1
    SESSION_DIR = os.path.join(os.path.expanduser("~"), ".prism32", "sessions")
    AUTO_SAVE_INTERVAL = 0    # 0 = save-on-interaction instead of timed
    THINKING_EFFORT = ""
    SLOW_CPU = False  # "", "low", "medium", "high"

    SUBAGENT_MODEL = ""  # model for subagents (empty = use main model)
    ROOT_PASS = ""  # root password for su/sudo commands (injected as $ROOT_PASS env)
    STREAM = False
    MAX_MEMORY_CTX = 1024  # max chars for memory context in system prompt (0 = disable)
    AGENT_NAME = "MDS"     # name displayed before assistant responses
    MODEL_CONTEXT_MAP = {
        # Pattern -> context window in tokens (used for history trimming)
        "deepseek/deepseek-v4": 262144,
        "deepseek/deepseek-chat": 65536,
        "qwen": 131072,
        "qwen3": 131072,
        "claude": 200000,
        "gpt-4": 128000,
        "gpt-4o": 128000,
        "gpt-4-turbo": 128000,
        "gpt-3.5": 16385,
        "llama": 131072,
        "llama3": 131072,
        "mistral": 32768,
        "mixtral": 32768,
        "command-r": 131072,
        "gemini": 1048576,
        "gemma": 8192,
        "phi": 131072,
    }

    # Computed: context budget = min(model_window, MAX_CONTEXT_TOKENS)
    MAX_CONTEXT_TOKENS = 220000  # user override

    @staticmethod
    def resolve_context_window(model_name=None):
        """Return the safe context budget for the given model.
        Uses MAX_CONTEXT_TOKENS override if set, otherwise auto-detects from model name."""
        if Config.MAX_CONTEXT_TOKENS != 220000:
            return min(Config.MAX_CONTEXT_TOKENS, 220000)
        model = model_name or Config.MODEL or ""
        model_lower = model.lower()
        for pattern, window in sorted(Config.MODEL_CONTEXT_MAP.items(), key=lambda x: -len(x[0])):
            if pattern in model_lower:
                budget = int(window * 0.85)  # 15% headroom for response
                return budget
        return 220000  # fallback

    PROVIDER = "local"  # Current provider name
    DEBUG = False  # Debug logging enabled
    CONFIG_FILE = os.path.join(os.path.expanduser("~"), ".prism32", "config.json")
    CUSTOM_THEME = None  # User-defined theme name
    CUSTOM_ARCH_MAP = {}  # User-defined arch pattern -> label mappings
    
    @classmethod
    def save_config(cls):
        """Save current config to file."""
        config_dir = os.path.dirname(cls.CONFIG_FILE)
        os.makedirs(config_dir, exist_ok=True)
        
        data = {
            "api_base": cls.API_BASE,
            "model": cls.MODEL,
            "subagent_model": cls.SUBAGENT_MODEL,
            "root_pass": cls.ROOT_PASS,
            "api_key": cls.API_KEY,
            "temperature": cls.TEMPERATURE,
            "theme": cls.THEME,
            "provider": cls.PROVIDER,
            "max_history": cls.MAX_HISTORY,
            "max_response_tokens": cls.MAX_RESPONSE_TOKENS,
            "cmd_timeout": cls.CMD_TIMEOUT,
            "goal_max_steps": cls.GOAL_MAX_STEPS,
            "auto_save_interval": cls.AUTO_SAVE_INTERVAL,
            "thinking_effort": cls.THINKING_EFFORT,
            "max_memory_ctx": cls.MAX_MEMORY_CTX,
            "agent_name": cls.AGENT_NAME,
            "custom_arch_map": cls.CUSTOM_ARCH_MAP,
        }
        
        with open(cls.CONFIG_FILE, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=2)
    
    @classmethod
    def load_config(cls):
        """Load config from file."""
        if not os.path.exists(cls.CONFIG_FILE):
            return
        try:
            with open(cls.CONFIG_FILE, 'r', encoding='utf-8') as f:
                data = json.load(f)
            if "api_base" in data: cls.API_BASE = data["api_base"]
            if "model" in data: cls.MODEL = data["model"]
            if "api_key" in data: cls.API_KEY = data["api_key"]
            if "temperature" in data: cls.TEMPERATURE = data["temperature"]
            if "theme" in data: cls.THEME = data["theme"]
            if "provider" in data:
                cls.PROVIDER = data["provider"]
                if data["provider"] in PROVIDER_REGISTRY:
                    if "api_base" not in data:
                        cls.API_BASE = PROVIDER_REGISTRY[data["provider"]]["api_base"]
                    if "model" not in data:
                        cls.MODEL = PROVIDER_REGISTRY[data["provider"]]["model"]
                    if "api_key" not in data and PROVIDER_REGISTRY[data["provider"]].get("default_key"):
                        cls.API_KEY = PROVIDER_REGISTRY[data["provider"]]["default_key"]
            if "max_history" in data: cls.MAX_HISTORY = data["max_history"]
            if "max_response_tokens" in data: cls.MAX_RESPONSE_TOKENS = data["max_response_tokens"]
            if "cmd_timeout" in data: cls.CMD_TIMEOUT = data["cmd_timeout"]
            if "goal_max_steps" in data: cls.GOAL_MAX_STEPS = data["goal_max_steps"]
            if "auto_save_interval" in data: cls.AUTO_SAVE_INTERVAL = data["auto_save_interval"]
            if "thinking_effort" in data: cls.THINKING_EFFORT = data["thinking_effort"]
            if "max_memory_ctx" in data: cls.MAX_MEMORY_CTX = data["max_memory_ctx"]
            # Live stream rendering is intentionally session-only. Older saved
            # configs may contain stream=true, which can re-enable fragile
            # token-level terminal output on legacy systems.
            if "slow_cpu" in data: cls.SLOW_CPU = data["slow_cpu"]
            if "subagent_model" in data: cls.SUBAGENT_MODEL = data["subagent_model"]
            if "root_pass" in data: cls.ROOT_PASS = data["root_pass"]
            if "agent_name" in data: cls.AGENT_NAME = data["agent_name"]
            if "custom_arch_map" in data and isinstance(data["custom_arch_map"], dict):
                cls.CUSTOM_ARCH_MAP = data["custom_arch_map"]
            if "providers" in data:
                for prov_name, prov_cfg in data["providers"].items():
                    if prov_name not in PROVIDER_REGISTRY:
                        PROVIDER_REGISTRY[prov_name] = {}
                    PROVIDER_REGISTRY[prov_name].update({
                        "name": prov_name.replace("_", " ").title(),
                        "api_base": prov_cfg.get("api_base", cls.API_BASE),
                        "model": prov_cfg.get("model", cls.MODEL),
                        "description": f"Configured via installer",
                    })
                    if prov_cfg.get("api_key"):
                        PROVIDER_REGISTRY[prov_name]["default_key"] = prov_cfg["api_key"]
        except Exception:
            pass

# ── Resilient helpers ──
def estimate_tokens(text):
    '''Rough token count (4 chars per token average).'''
    return len(text) // 4

def context_pct(history):
    total = sum(estimate_tokens(m.get("content", "")) for m in history)
    budget = Config.resolve_context_window()
    return int(total / budget * 100) if budget > 0 else 0

def trim_history(history, max_tokens=None):
    '''Trim history to stay within context window, preserving system prompt.
    O(n) -- running sum instead of re-summing all kept messages per iteration.'''
    if max_tokens is None:
        max_tokens = Config.resolve_context_window()
    if not history:
        return history
    total = sum(estimate_tokens(m.get("content", "")) for m in history)
    if total <= max_tokens:
        return history
    kept = [history[0]]
    running = estimate_tokens(history[0].get("content", ""))
    for m in history[1:]:
        tok = estimate_tokens(m.get("content", ""))
        if running + tok <= max_tokens:
            kept.append(m)
            running += tok
        else:
            break
    return kept

# ── Theme Registry (built-ins) ────────────────────────────
register_theme("phosphor", primary="\x1b[92m", bright="\x1b[1;92m", dim="\x1b[2;32m", accent="\x1b[96m", warn="\x1b[93m", err="\x1b[91m", glow="\x1b[5;92m", bar="\x1b[42m")
register_theme("amber", primary="\x1b[33m", bright="\x1b[1;93m", dim="\x1b[2;33m", accent="\x1b[96m", warn="\x1b[92m", err="\x1b[91m", glow="\x1b[5;93m", bar="\x1b[43m")
register_theme("cyan", primary="\x1b[96m", bright="\x1b[1;96m", dim="\x1b[2;36m", accent="\x1b[92m", warn="\x1b[93m", err="\x1b[91m", glow="\x1b[5;96m", bar="\x1b[46m")
# ── Community Themes ─────────────────────────────────────────

register_theme("vapor",
    primary="\033[38;5;219m", bright="\033[1;95m", dim="\033[2;38;5;245m",
    accent="\033[38;5;87m", warn="\033[38;5;228m", err="\033[38;5;203m",
    glow="\033[5;95m", bar="\033[48;5;201m")

register_theme("nord",
    primary="\033[38;5;109m", bright="\033[1;94m", dim="\033[2;38;5;60m",
    accent="\033[38;5;143m", warn="\033[38;5;223m", err="\033[38;5;167m",
    glow="\033[5;94m", bar="\033[48;5;67m")

register_theme("solarized",
    primary="\033[38;5;37m", bright="\033[1;36m", dim="\033[2;38;5;66m",
    accent="\033[38;5;42m", warn="\033[38;5;3m", err="\033[38;5;124m",
    glow="\033[5;36m", bar="\033[48;5;23m")

register_theme("neon",
    primary="\033[38;5;51m", bright="\033[1;96m", dim="\033[2;38;5;239m",
    accent="\033[38;5;200m", warn="\033[38;5;226m", err="\033[38;5;196m",
    glow="\033[5;96m", bar="\033[48;5;45m")

register_theme("retro",
    primary="\033[38;5;214m", bright="\033[1;33m", dim="\033[2;38;5;243m",
    accent="\033[38;5;228m", warn="\033[38;5;215m", err="\033[38;5;124m",
    glow="\033[5;33m", bar="\033[48;5;130m")

register_theme("ice",
    primary="\033[38;5;159m", bright="\033[1;97m", dim="\033[2;38;5;253m",
    accent="\033[38;5;195m", warn="\033[38;5;229m", err="\033[38;5;203m",
    glow="\033[5;97m", bar="\033[48;5;117m")

register_theme("ocean",
    primary="\033[38;5;45m", bright="\033[1;96m", dim="\033[2;38;5;24m",
    accent="\033[38;5;51m", warn="\033[38;5;214m", err="\033[38;5;196m",
    glow="\033[5;96m", bar="\033[48;5;30m")

register_theme("sunset",
    primary="\033[38;5;208m", bright="\033[1;91m", dim="\033[2;38;5;94m",
    accent="\033[38;5;213m", warn="\033[38;5;226m", err="\033[38;5;160m",
    glow="\033[5;91m", bar="\033[48;5;166m")

register_theme("forest",
    primary="\033[38;5;114m", bright="\033[1;32m", dim="\033[2;38;5;65m",
    accent="\033[38;5;150m", warn="\033[38;5;214m", err="\033[38;5;124m",
    glow="\033[5;32m", bar="\033[48;5;28m")

register_theme("plasma",
    primary="\033[38;5;183m", bright="\033[1;95m", dim="\033[2;38;5;61m",
    accent="\033[38;5;169m", warn="\033[38;5;226m", err="\033[38;5;196m",
    glow="\033[5;95m", bar="\033[48;5;128m")

# ── Transparent-terminal themes ───────────────────────────────
register_theme("clear",
    primary="\x1b[39m", bright="\x1b[1m", dim="\x1b[2m",
    accent="\x1b[36m", warn="\x1b[33m", err="\x1b[31m",
    glow="\x1b[5m", bar="")

register_theme("glass",
    primary="\x1b[38;5;250m", bright="\x1b[1;97m", dim="\x1b[2;38;5;245m",
    accent="\x1b[38;5;81m", warn="\x1b[38;5;220m", err="\x1b[38;5;203m",
    glow="\x1b[5;38;5;250m", bar="")

register_theme("ghost",
    primary="\x1b[38;5;252m", bright="\x1b[1;38;5;255m", dim="\x1b[2;38;5;244m",
    accent="\x1b[38;5;122m", warn="\x1b[38;5;178m", err="\x1b[38;5;204m",
    glow="\x1b[5;38;5;252m", bar="")

register_theme("smoke",
    primary="\x1b[38;5;240m", bright="\x1b[1;38;5;238m", dim="\x1b[2;38;5;245m",
    accent="\x1b[38;5;67m", warn="\x1b[38;5;130m", err="\x1b[38;5;124m",
    glow="\x1b[5;38;5;240m", bar="")

# ── Light / white-terminal themes ─────────────────────────────
register_theme("paper",
    primary="\x1b[30m", bright="\x1b[1;30m", dim="\x1b[2;30m",
    accent="\x1b[34m", warn="\x1b[33m", err="\x1b[31m",
    glow="\x1b[5;30m", bar="")

register_theme("ink",
    primary="\x1b[34m", bright="\x1b[1;34m", dim="\x1b[2;34m",
    accent="\x1b[32m", warn="\x1b[33m", err="\x1b[31m",
    glow="\x1b[5;34m", bar="")

register_theme("daylight",
    primary="\x1b[36m", bright="\x1b[1;90m", dim="\x1b[2;36m",
    accent="\x1b[34m", warn="\x1b[33m", err="\x1b[31m",
    glow="\x1b[5;36m", bar="")

register_theme("slate",
    primary="\x1b[38;5;238m", bright="\x1b[1;38;5;240m", dim="\x1b[2;38;5;244m",
    accent="\x1b[34m", warn="\x1b[38;5;130m", err="\x1b[31m",
    glow="\x1b[5;38;5;238m", bar="")

# ── Legacy 16-color / retro terminal themes ──────────────────
# These use ONLY standard ANSI 16-color codes (30-37, 90-97, 40-47, 100-107)
# plus SGR attributes (1-7). No 256-color (38;5;N) sequences.
# Safe on: IRIX iris-ansi, HP-UX hpterm, AIX xterm, Solaris CDE, DEC VTxxx,
#          old xterm, rxvt, and any terminal with basic ANSI color support.

register_theme("synthcity",
    primary="\x1b[96m", bright="\x1b[95m", dim="\x1b[36m",
    accent="\x1b[95m", warn="\x1b[93m", err="\x1b[91m",
    glow="\x1b[5;95m", bar="\x1b[45m")

register_theme("outrun",
    primary="\x1b[95m", bright="\x1b[93m", dim="\x1b[35m",
    accent="\x1b[96m", warn="\x1b[92m", err="\x1b[91m",
    glow="\x1b[5;95m", bar="\x1b[104m")

register_theme("laserdisc",
    primary="\x1b[94m", bright="\x1b[96m", dim="\x1b[34m",
    accent="\x1b[95m", warn="\x1b[93m", err="\x1b[91m",
    glow="\x1b[5;96m", bar="\x1b[44m")

register_theme("vapordark",
    primary="\x1b[95m", bright="\x1b[97m", dim="\x1b[35m",
    accent="\x1b[96m", warn="\x1b[93m", err="\x1b[91m",
    glow="\x1b[5;95m", bar="\x1b[45m")

register_theme("chromecrt",
    primary="\x1b[92m", bright="\x1b[97m", dim="\x1b[32m",
    accent="\x1b[96m", warn="\x1b[93m", err="\x1b[91m",
    glow="\x1b[5;92m", bar="\x1b[42m")

register_theme("sgi",
    primary="\x1b[96m", bright="\x1b[97m", dim="\x1b[36m",
    accent="\x1b[94m", warn="\x1b[93m", err="\x1b[91m",
    glow="\x1b[5;36m", bar="\x1b[46m")

register_theme("dec",
    primary="\x1b[32m", bright="\x1b[92m", dim="\x1b[2;32m",
    accent="\x1b[33m", warn="\x1b[33m", err="\x1b[91m",
    glow="\x1b[5;92m", bar="\x1b[42m")

register_theme("monoamber",
    primary="\x1b[33m", bright="\x1b[93m", dim="\x1b[2;33m",
    accent="\x1b[93m", warn="\x1b[93m", err="\x1b[91m",
    glow="\x1b[5;33m", bar="\x1b[43m")

register_theme("iris",
    primary="\x1b[37m", bright="\x1b[97m", dim="\x1b[2;37m",
    accent="\x1b[34m", warn="\x1b[33m", err="\x1b[31m",
    glow="\x1b[5;37m", bar="\x1b[44m")

register_theme("hpterm",
    primary="\x1b[92m", bright="\x1b[93m", dim="\x1b[32m",
    accent="\x1b[96m", warn="\x1b[93m", err="\x1b[91m",
    glow="\x1b[5;92m", bar="\x1b[46m")

# ── Model Providers ────────────────────────────────────────────

# ── Provider Registry (built-ins) ──────────────────────
register_provider("local", display_name="Local (llama.cpp)", api_base="http://127.0.0.1:8080", model="deepseek-v4-flash", description="Local llama.cpp server")
register_provider("ollama", display_name="Ollama (localhost)", api_base="http://localhost:11434/v1", model="deepseek-v4-flash", description="Local Ollama server")
register_provider("openai", display_name="OpenAI", api_base="https://api.openai.com/v1", model="gpt-4o", description="OpenAI GPT-4o (requires API key)")
register_provider("anthropic", display_name="Anthropic", api_base="https://api.anthropic.com/v1", model="claude-sonnet-4-20250514", description="Anthropic Claude (requires API key)")
register_provider("groq", display_name="Groq", api_base="https://api.groq.com/openai/v1", model="llama-3.3-70b-versatile", description="Groq fast inference")
register_provider("together", display_name="Together AI", api_base="https://api.together.xyz/v1", model="meta-llama/Llama-3-70b-chat-hf", description="Together AI inference")
register_provider("openrouter", display_name="OpenRouter", api_base="https://openrouter.ai/api/v1", model="deepseek/deepseek-v4-flash", description="OpenRouter multi-model gateway (set API key via /provider key or --api-key)")
register_provider("custom", display_name="Custom", api_base="http://localhost:8080", model="model-name", description="Custom provider (configure below)")


_T_CACHE = {}
def T():
    if not ansi_enabled():
        return _PLAIN_THEME
    theme = Config.THEME
    if theme not in _T_CACHE:
        data = dict(THEME_REGISTRY.get(theme, THEME_REGISTRY.get("phosphor", {})))
        data.setdefault("ok", data.get("bright", ""))
        _T_CACHE[theme] = data
    return _T_CACHE[theme]

def _clear_theme_cache():
    _T_CACHE.clear()

_RE_ANSI = re.compile(r'\x1b\[[0-9;?]*[a-zA-Z]')
_RE_STRIP_ANSI = re.compile(r'\x1b\[[0-9;?]*[a-zA-Z]')
_RE_EXEC_BLOCK = re.compile(r'```execute\n(.*?)```', re.DOTALL)
_RE_ASK_BLOCK = re.compile(r'```ask\n(.*?)```', re.DOTALL)

RST = "\x1b[0m"
BOLD = "\x1b[1m"
DIM  = "\x1b[2m"
HIDE = "\x1b[?25l"
SHOW = "\x1b[?25h"
CLS  = "\x1b[2J\x1b[H"
_ANSI_ENABLED = None
_PLAIN_THEME = {"primary": "", "bright": "", "dim": "", "accent": "", "warn": "", "err": "", "glow": "", "bar": "", "ok": ""}

def _no_braces(s):
    """Escape curly braces so content can be safely used in f-strings."""
    if '{' in s or '}' in s:
        return s.replace('{', '{{').replace('}', '}}')
    return s

def strip_ansi(text):
    return _RE_ANSI.sub('', text)

def _supports_ansi():
    """Check if terminal supports ANSI escape codes."""
    term = os.environ.get('TERM', '').lower()
    if 'NO_COLOR' in os.environ:
        return False
    if Platform.WINDOWS:
        try:
            import ctypes
            kernel32 = ctypes.windll.kernel32
            handle = kernel32.GetStdHandle(-11)
            mode = ctypes.c_uint32()
            if not kernel32.GetConsoleMode(handle, ctypes.byref(mode)):
                return False
            # Windows 10+ supports virtual terminal sequences when enabled.
            if kernel32.SetConsoleMode(handle, mode.value | 0x0004):
                return True
            return False
        except Exception:
            return False
    if term in ('dumb', 'emacs', '', 'none', 'unknown'):
        return False
    if not sys.stdout.isatty():
        return False
    if term:
        vt100_compat = (
            'vt100', 'xterm', 'ansi', 'linux', 'rxvt', 'putty',
            'dtterm', 'nsterm', 'konsole', 'gnome', 'screen',
            'tmux', 'iris-ansi', 'hpterm',
        )
        if any(t in term for t in vt100_compat):
            return True
        try:
            import subprocess
            result = subprocess.run(['tput', 'colors'], capture_output=True, text=True, timeout=2)
            if result.returncode == 0 and result.stdout.strip().isdigit():
                return int(result.stdout.strip()) >= 8
        except Exception:
            pass
    return True

def ansi_enabled():
    global _ANSI_ENABLED
    if _ANSI_ENABLED is None:
        _ANSI_ENABLED = _supports_ansi()
    return _ANSI_ENABLED

def apply_ansi_compat():
    """Disable escape sequences on consoles that cannot handle them."""
    global RST, BOLD, DIM, HIDE, SHOW, CLS
    if ansi_enabled():
        return
    RST = BOLD = DIM = HIDE = SHOW = CLS = ""
    _clear_theme_cache()

# ── Persistent footer / scroll region ───────────────────────
_term_size = os.terminal_size((80, 24))
_footer_reserved = False

def update_terminal_size():
    """Update cached terminal dimensions."""
    global _term_size
    try:
        _term_size = shutil.get_terminal_size()
    except Exception:
        pass

def set_scroll_region():
    """Reserve bottom line for the footer; everything else scrolls above."""
    global _footer_reserved
    if not ansi_enabled() or not sys.stdout.isatty():
        _footer_reserved = False
        return
    _footer_reserved = True
    h = _term_size.lines
    if h > 1:
        sys.stdout.write(f"\x1b[1;{h-1}r")
    sys.stdout.flush()

def reset_scroll_region():
    """Reset scrolling region to full screen."""
    global _footer_reserved
    _footer_reserved = False
    if not ansi_enabled():
        return
    sys.stdout.write("\x1b[r")
    sys.stdout.flush()

def release_footer_for_output():
    """Disable the reserved footer so normal output can scroll safely."""
    if not _footer_reserved:
        return
    reset_scroll_region()
    if not ansi_enabled():
        return
    h = _term_size.lines
    if h > 0:
        sys.stdout.write(f"\x1b[{h};1H\r\x1b[K\n")
    sys.stdout.flush()

def move_to_footer():
    """Move cursor to the bottom line (reserved footer)."""
    if not ansi_enabled():
        return
    sys.stdout.write(f"\x1b[{_term_size.lines};1H")
    sys.stdout.flush()

def move_to_scroll_bottom():
    """Move cursor to the last line of the scroll region (just above footer)."""
    if not _footer_reserved or not ansi_enabled():
        return
    h = _term_size.lines
    if h > 1:
        sys.stdout.write(f"\x1b[{h-1};1H")
    else:
        sys.stdout.write("\x1b[1;1H")
    sys.stdout.flush()

def clear_footer():
    """Clear the footer line."""
    if not _footer_reserved or not ansi_enabled():
        return
    move_to_footer()
    sys.stdout.write("\x1b[K")
    sys.stdout.flush()

def activity_vector(history=None, frame=0, busy=False):
    """Build the footer activity vector; width grows with context usage."""
    t = T()
    ctx = context_pct(history) if history else 0
    width = 2 + min(10, max(0, ctx) // 10)
    if busy:
        wave = ["▁", "▂", "▃", "▄", "▅", "▆", "▇", "█"]
        chars = "".join(wave[(frame + i) % len(wave)] for i in range(width))
        color = t['err'] if ctx >= 90 else (t['warn'] if ctx >= 75 else t['accent'])
        return f"{color}{chars}{RST}"
    return f"{t['dim']}{'░' * width}{RST}"

def draw_footer(status_bar, spin_char=None):
    """Draw the footer at the bottom of the screen."""
    if not _footer_reserved or not ansi_enabled():
        return
    t = T()
    indicator = spin_char if spin_char is not None else activity_vector()
    clear_footer()
    sys.stdout.write(f"{status_bar} {indicator} {t['primary']}>{RST} ")
    sys.stdout.flush()

def read_footer_input(status_bar):
    """Read one line from the reserved footer without confusing readline."""
    if not _footer_reserved:
        t = T()
        return input(rl_prompt(f" {t['primary']}prism32>{RST} ")).strip()
    draw_footer(status_bar)
    line = sys.stdin.readline()
    if line == "":
        raise EOFError
    clear_footer()
    return line.strip()

# ── Interjection (type while AI streams) ─────────────────────

def request_agent_cancel(reason="Agent stopped by Escape", cancel_event=None):
    global _AGENT_CANCEL_REQUESTED, _AGENT_CANCEL_REASON
    _AGENT_CANCEL_REQUESTED = True
    _AGENT_CANCEL_REASON = reason
    if cancel_event is not None:
        cancel_event.set()
    return _INTERJECTION_CANCEL

def clear_agent_cancel():
    global _AGENT_CANCEL_REQUESTED, _AGENT_CANCEL_REASON
    _AGENT_CANCEL_REQUESTED = False
    _AGENT_CANCEL_REASON = ""

def agent_cancel_requested(cancel_event=None):
    return _AGENT_CANCEL_REQUESTED or (cancel_event is not None and cancel_event.is_set())

def agent_cancel_message():
    return _AGENT_CANCEL_REASON or "Agent stopped by Escape"

def _interjection_start():
    global _INTERJECTION_ACTIVE, _INTERJECTION_BUF, _INTERJECTION_CURSOR, _INTERJECTION_RESULT, _SAVED_TERMIOS, _INTERJECTION_HAS_TYPED, _INTERJECTION_ESCAPE, _INTERJECTION_ESCAPE_BUF, _INTERJECTION_HISTORY, _INTERJECTION_HISTORY_IDX, _INTERJECTION_SAVED_BUF
    _INTERJECTION_ACTIVE = False
    _INTERJECTION_BUF = ""
    _INTERJECTION_CURSOR = 0
    _INTERJECTION_RESULT = None
    _SAVED_TERMIOS = None
    _INTERJECTION_HAS_TYPED = False
    _INTERJECTION_ESCAPE = False
    _INTERJECTION_ESCAPE_BUF = ""
    _INTERJECTION_HISTORY_IDX = -1
    _INTERJECTION_SAVED_BUF = ""
    if sys.platform == 'win32':
        return
    try:
        import termios
        fd = sys.stdin.fileno()
        _SAVED_TERMIOS = termios.tcgetattr(fd)
        new = termios.tcgetattr(fd)
        new[3] = new[3] & ~(termios.ECHO | termios.ICANON)
        new[6][termios.VMIN] = 1
        new[6][termios.VTIME] = 0
        termios.tcsetattr(fd, termios.TCSADRAIN, new)
        _INTERJECTION_ACTIVE = True
    except Exception:
        _INTERJECTION_ACTIVE = False

def _interjection_stop():
    global _INTERJECTION_ACTIVE, _INTERJECTION_BUF, _INTERJECTION_CURSOR, _INTERJECTION_RESULT, _SAVED_TERMIOS, _INTERJECTION_HAS_TYPED, _INTERJECTION_ESCAPE, _INTERJECTION_ESCAPE_BUF, _INTERJECTION_HISTORY_IDX, _INTERJECTION_SAVED_BUF
    _INTERJECTION_ACTIVE = False
    _INTERJECTION_BUF = ""
    _INTERJECTION_CURSOR = 0
    _INTERJECTION_HAS_TYPED = False
    _INTERJECTION_ESCAPE = False
    _INTERJECTION_ESCAPE_BUF = ""
    _INTERJECTION_HISTORY_IDX = -1
    _INTERJECTION_SAVED_BUF = ""
    if _SAVED_TERMIOS is not None:
        try:
            import termios
            termios.tcsetattr(sys.stdin.fileno(), termios.TCSADRAIN, _SAVED_TERMIOS)
        except Exception:
            pass
        _SAVED_TERMIOS = None
    with stdout_lock:
        if _footer_reserved:
            sys.stdout.write("\x1b[s")
            clear_footer()
            sys.stdout.write("\x1b[u")
            sys.stdout.flush()

def _interjection_poll():
    global _INTERJECTION_ACTIVE, _INTERJECTION_BUF, _INTERJECTION_CURSOR, _INTERJECTION_RESULT, _INTERJECTION_HAS_TYPED, _INTERJECTION_ESCAPE, _INTERJECTION_ESCAPE_BUF, _INTERJECTION_HISTORY, _INTERJECTION_HISTORY_IDX, _INTERJECTION_SAVED_BUF
    if not _INTERJECTION_ACTIVE:
        return None
    if select is None:
        return None
    try:
        fd = sys.stdin.fileno()
        has_input = select.select([fd], [], [], 0)[0]
        if has_input:
            data = os.read(fd, 4096)
            if not data:
                if _INTERJECTION_HAS_TYPED:
                    _draw_interjection_footer()
                return None
            if data == b'\x1b':
                return request_agent_cancel()
            text = data.decode('utf-8', errors='replace')
            for ch in text:
                if _INTERJECTION_ESCAPE:
                    _INTERJECTION_ESCAPE_BUF += ch
                    seq = _INTERJECTION_ESCAPE_BUF
                    b = ord(ch)
                    if seq in ('[', 'O'):
                        continue
                    if 0x40 <= b <= 0x7E or ch == '~':
                        _INTERJECTION_ESCAPE = False
                        _INTERJECTION_ESCAPE_BUF = ""
                        if seq in ('[A', 'OA'):  # Up
                            if _INTERJECTION_HISTORY:
                                if _INTERJECTION_HISTORY_IDX == -1:
                                    _INTERJECTION_SAVED_BUF = _INTERJECTION_BUF
                                    _INTERJECTION_HISTORY_IDX = len(_INTERJECTION_HISTORY) - 1
                                elif _INTERJECTION_HISTORY_IDX > 0:
                                    _INTERJECTION_HISTORY_IDX -= 1
                                _INTERJECTION_BUF = _INTERJECTION_HISTORY[_INTERJECTION_HISTORY_IDX]
                                _INTERJECTION_CURSOR = len(_INTERJECTION_BUF)
                                _INTERJECTION_HAS_TYPED = True
                        elif seq in ('[B', 'OB'):  # Down
                            if _INTERJECTION_HISTORY and _INTERJECTION_HISTORY_IDX >= 0:
                                _INTERJECTION_HISTORY_IDX += 1
                                if _INTERJECTION_HISTORY_IDX >= len(_INTERJECTION_HISTORY):
                                    _INTERJECTION_HISTORY_IDX = -1
                                    _INTERJECTION_BUF = _INTERJECTION_SAVED_BUF
                                else:
                                    _INTERJECTION_BUF = _INTERJECTION_HISTORY[_INTERJECTION_HISTORY_IDX]
                                _INTERJECTION_CURSOR = len(_INTERJECTION_BUF)
                                _INTERJECTION_HAS_TYPED = True
                        elif seq in ('[C', 'OC'):  # Right
                            _INTERJECTION_CURSOR = min(len(_INTERJECTION_BUF), _INTERJECTION_CURSOR + 1)
                            _INTERJECTION_HAS_TYPED = True
                        elif seq in ('[D', 'OD'):  # Left
                            _INTERJECTION_CURSOR = max(0, _INTERJECTION_CURSOR - 1)
                            _INTERJECTION_HAS_TYPED = True
                        elif seq == '[H':  # Home
                            _INTERJECTION_CURSOR = 0
                            _INTERJECTION_HAS_TYPED = True
                        elif seq == '[F':  # End
                            _INTERJECTION_CURSOR = len(_INTERJECTION_BUF)
                            _INTERJECTION_HAS_TYPED = True
                    continue
                if ch in ('\n', '\r'):
                    result = _INTERJECTION_BUF.strip()
                    if not result:
                        _INTERJECTION_BUF = ""
                        _INTERJECTION_CURSOR = 0
                        _INTERJECTION_HAS_TYPED = False
                        _draw_interjection_footer()
                        return None
                    _INTERJECTION_HISTORY.append(result)
                    _INTERJECTION_BUF = ""
                    _INTERJECTION_CURSOR = 0
                    _INTERJECTION_RESULT = result
                    return result
                elif ord(ch) == 3:
                    raise KeyboardInterrupt
                elif ch in ('\x7f', '\b'):
                    if _INTERJECTION_CURSOR > 0:
                        _INTERJECTION_BUF = _INTERJECTION_BUF[:_INTERJECTION_CURSOR - 1] + _INTERJECTION_BUF[_INTERJECTION_CURSOR:]
                        _INTERJECTION_CURSOR -= 1
                elif ord(ch) == 27:
                    _INTERJECTION_ESCAPE = True
                    _INTERJECTION_ESCAPE_BUF = ""
                elif ord(ch) >= 32:
                    _INTERJECTION_BUF = _INTERJECTION_BUF[:_INTERJECTION_CURSOR] + ch + _INTERJECTION_BUF[_INTERJECTION_CURSOR:]
                    _INTERJECTION_CURSOR += 1
                    _INTERJECTION_HAS_TYPED = True
        if _INTERJECTION_HAS_TYPED:
            _draw_interjection_footer()
    except Exception:
        pass
    return None

def _draw_interjection_footer():
    global _INTERJECTION_BUF, _INTERJECTION_CURSOR
    buf = _INTERJECTION_BUF
    cur = _INTERJECTION_CURSOR
    with stdout_lock:
        if not _footer_reserved:
            return
        sys.stdout.write("\x1b[s")
        if buf or _INTERJECTION_HAS_TYPED:
            t = T()
            clear_footer()
            visual = f" {t['bright']}interject>{RST} {buf}"
            sys.stdout.write(visual)
            move_back = len(buf) - cur
            if move_back > 0:
                sys.stdout.write(f"\x1b[{move_back}D")
        else:
            draw_footer(build_status_bar())
        sys.stdout.write("\x1b[u")
        sys.stdout.flush()

# ── ANSI Helpers ─────────────────────────────────────────────

def strip_ansi(text):
    return _RE_STRIP_ANSI.sub('', text)

def rl_prompt(text):
    """Wrap ANSI escapes in readline \x01/\x02 markers so cursor tracking works."""
    return re.sub(r'(\x1b\[[0-9;?]*[a-zA-Z])', '\x01\\1\x02', text)

def build_status_bar(spin_char=None, history=None, include_indicator=False):
    """Build the bottom status bar: Prism32 MDS:<think> <ctx%> <sa> <spin> > """
    t = T()
    parts = [f" {t['bright']}Prism32{RST} {t['dim']}MDS{RST}:"]
    if Config.THINKING_EFFORT:
        parts.append(f"{t['dim']}{Config.THINKING_EFFORT}{RST}")
    ctx = context_pct(history) if history else 0
    if ctx > 0:
        ctx_color = t['err'] if ctx >= 90 else (t['warn'] if ctx >= 75 else t['dim'])
        parts.append(f" {ctx_color}Ctx {ctx}%{RST}")
    sa_count = sum(1 for s in _SUBAGENTS.values() if not s.done)
    if sa_count > 0:
        parts.append(f" {t['warn']}SA:{sa_count}{RST}")
    if _quantum.was_used():
        parts.append(f" {t['accent']}Q{RST}")
    if include_indicator:
        indicator = spin_char if spin_char is not None else f"{t['dim']}░{RST}"
        parts.append(f" {indicator}")
    return "".join(parts)

def run_cancelable_blocking(fn, history=None, message="thinking", cancel_event=None):
    """Run a blocking foreground operation while Escape can stop waiting for it."""
    if threading.current_thread() is not threading.main_thread():
        return fn()
    if select is None or sys.platform == 'win32':
        return fn()

    clear_agent_cancel()
    if cancel_event is None:
        cancel_event = threading.Event()
    result_q = queue.Queue(maxsize=1)

    def _target():
        try:
            result_q.put((True, fn()))
        except BaseException as e:
            result_q.put((False, e))

    _interjection_start()
    worker = threading.Thread(target=_target, daemon=True)
    worker.start()
    frame = 0
    last_draw = 0
    try:
        while worker.is_alive():
            inj = _interjection_poll()
            if inj is _INTERJECTION_CANCEL or agent_cancel_requested(cancel_event):
                request_agent_cancel(cancel_event=cancel_event)
                return AGENT_CANCELLED_RESPONSE
            if inj is not None:
                request_agent_cancel("Agent interrupted by user input", cancel_event=cancel_event)
                return None
            now = time.monotonic()
            if now - last_draw >= 0.12:
                with stdout_lock:
                    if _footer_reserved:
                        spin = activity_vector(history=history, frame=frame, busy=True)
                        draw_footer(build_status_bar(history=history, include_indicator=False), spin_char=spin)
                    else:
                        t = T()
                        char = activity_vector(frame=frame, busy=True)
                        sys.stdout.write(f"\r\033[K {t['dim']}{char} {message}...{RST}")
                        sys.stdout.flush()
                frame += 1
                last_draw = now
            time.sleep(0.03)
        ok, value = result_q.get_nowait()
        if ok:
            return value
        raise value
    finally:
        _interjection_stop()

def ask_ai_cancelable(messages, history=None):
    cancel_event = threading.Event()
    return run_cancelable_blocking(
        lambda: ask_ai(messages, stream=False, cancel_event=cancel_event),
        history=history,
        cancel_event=cancel_event,
    )

# ── Box Drawing ──────────────────────────────────────────────

def _wrap_line(line, cw):
    """Word-wrap a single line to fit within cw columns, preserving ANSI codes."""
    visible = strip_ansi(line)
    if len(visible) <= cw:
        return [line]

    chunks = []
    words = line.split(' ')
    current = ''
    for word in words:
        test = current + (' ' if current else '') + word
        if len(strip_ansi(test)) > cw:
            if current:
                chunks.append(current)
            current = word
        else:
            current = test
    if current:
        chunks.append(current)
    return chunks

def box(title, content, color_key="primary", width=62):
    t = T()
    c = t[color_key]
    raw_lines = content.split('\n')
    iw = width - 2
    cw = width - 4
    print(f"{c}{'+' + '='*iw + '+'}{RST}")
    title_clean = strip_ansi(str(title))
    print(f"{c}|{RST} {c}{BOLD}{title_clean:<{cw}}{RST} {c}|{RST}")
    print(f"{c}|{'-'*iw}|{RST}")
    for raw_line in raw_lines:
        wrapped = _wrap_line(raw_line, cw)
        for chunk in wrapped:
            vis = len(strip_ansi(chunk))
            pad = cw - vis
            if pad < 0:
                chunk = chunk[:cw]
                pad = 0
            print(f"{c}|{RST} {chunk}{' '*pad} {c}|{RST}")
    print(f"{c}{'+' + '='*iw + '+'}{RST}")

def progress_bar(current, total, label="", width=40, color_key="primary"):
    t = T()
    c = t[color_key]
    filled = int(width * current / total) if total > 0 else 0
    bar = '#' * filled + '-' * (width - filled)
    pct = int(100 * current / total) if total > 0 else 0
    print(f"\r {c}[{bar}] {pct:3d}% {label}{RST}", end='', flush=True)

def step_header(step, total, goal_text):
    t = T()
    print(f"\n{t['bright']}{'='*62}{RST}")
    print(f" {t['bright']}STEP {step}/{total}{RST}  {t['dim']}{goal_text[:50]}{RST}")
    print(f"{t['bright']}{'='*62}{RST}")

# ── Spinner ──────────────────────────────────────────────────

def spinner(label="processing", timeout=8):
    t = T()
    frames = ["|", "/", "-", "\\"]
    start = time.time()
    i = 0
    while time.time() - start < timeout:
        sys.stdout.write(f"\r {t['glow']}{frames[i % len(frames)]} {label}...{RST}")
        sys.stdout.flush()
        time.sleep(0.1)
        i += 1
    sys.stdout.write(f"\r{' '*50}\r")

# ── Session Management ──────────────────────────────────────────

def ensure_session_dir():
    """Create session directory if it doesn't exist."""
    os.makedirs(Config.SESSION_DIR, exist_ok=True)

def get_session_path(session_id):
    """Get the file path for a session."""
    return os.path.join(Config.SESSION_DIR, f"{session_id}.json")

def generate_session_id(name=None):
    """Generate a unique session ID."""
    if name:
        clean_name = "".join(c if c.isalnum() or c in ('-', '_') else '_' for c in name)
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        return f"{clean_name}_{timestamp}"
    else:
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        import hashlib
        random_hash = hashlib.md5(str(time.time()).encode()).hexdigest()[:6]
        return f"session_{timestamp}_{random_hash}"

def _extract_title(history, metadata=None):
    """Derive a human-readable title from session history."""
    # Goal sessions: use the goal text from metadata or the GOAL: message
    if metadata and metadata.get("type") == "goal":
        goal = metadata.get("goal", "")
        if goal:
            return goal[:60]
    for msg in history:
        content = msg.get("content", "")
        role = msg.get("role", "")
        if role == "user" and content.startswith("GOAL:"):
            return content[5:65].strip().replace('\n', ' ')
        if role == "user" and not content.startswith("You are in") and len(content) > 10:
            return content[:60].replace('\n', ' ')
    return "untitled"

def save_session(session_id, history, cmd_log, metadata=None):
    """Save session to file."""
    ensure_session_dir()
    title = _extract_title(history, metadata)
    session_data = {
        "id": session_id,
        "title": title,
        "timestamp": datetime.now().isoformat(),
        "model": Config.MODEL,
        "api_base": Config.API_BASE,
        "theme": Config.THEME,
        "metadata": metadata or {},
        "history": history,
        "cmd_log": cmd_log,
        "stats": {
            "messages": len(history),
            "commands": len(cmd_log)
        }
    }
    path = get_session_path(session_id)
    with open(path, 'w', encoding='utf-8') as f:
        json.dump(session_data, f, indent=2)
    return path

def load_session(session_id):
    """Load session from file."""
    path = get_session_path(session_id)
    if not os.path.exists(path):
        return None
    with open(path, 'r', encoding='utf-8') as f:
        return json.load(f)

def _quick_scan_session(path, sid):
    '''Read metadata from a session file without full JSON parse.
    Reads first 4KB which covers the header fields (id, title, timestamp, model, stats).'''
    try:
        with open(path, 'r', encoding='utf-8') as f:
            chunk = f.read(4096)
        import re as _re
        def _grab(key, fallback=sid):
            m = _re.search(r'\"' + key + r'\":\s*\"([^\"]+)\"', chunk)
            return m.group(1) if m else fallback
        def _grab_int(key, fallback=0):
            m = _re.search(r'\"' + key + r'\":\s*(\d+)', chunk)
            return int(m.group(1)) if m else fallback
        return {
            "id": sid,
            "title": _grab("title"),
            "timestamp": _grab("timestamp", "unknown"),
            "model": _grab("model", "unknown"),
            "messages": _grab_int("messages"),
            "commands": _grab_int("commands"),
        }
    except Exception:
        return None

def list_sessions():
    '''List all saved sessions (fast -- header-only scan).'''
    ensure_session_dir()
    sessions = []
    for filename in os.listdir(Config.SESSION_DIR):
        if filename.endswith('.json'):
            sid = filename[:-5]
            path = os.path.join(Config.SESSION_DIR, filename)
            data = _quick_scan_session(path, sid)
            if data:
                sessions.append(data)
    sessions.sort(key=lambda x: x.get("timestamp", ""), reverse=True)
    return sessions

def delete_session(session_id):
    """Delete a session file."""
    path = get_session_path(session_id)
    if os.path.exists(path):
        os.remove(path)
        return True
    return False

def get_session_stats(session_data):
    """Calculate session statistics."""
    if not session_data:
        return {}
    history = session_data.get("history", [])
    cmd_log = session_data.get("cmd_log", [])
    user_msgs = sum(1 for m in history if m.get("role") == "user")
    assistant_msgs = sum(1 for m in history if m.get("role") == "assistant")
    cmd_types = {}
    for entry in cmd_log:
        if isinstance(entry, (list, tuple)) and len(entry) >= 2:
            cmd_type = entry[0]
            cmd_types[cmd_type] = cmd_types.get(cmd_type, 0) + 1
    return {
        "total_messages": len(history),
        "user_messages": user_msgs,
        "assistant_messages": assistant_msgs,
        "total_commands": len(cmd_log),
        "command_types": cmd_types,
        "created": session_data.get("timestamp"),
        "model": session_data.get("model")
    }

# ── Visual Feedback ────────────────────────────────────────────

class ToolVisualizer:
    def __init__(self):
        self.t = T()
        self.thinking_chars = ["⣾", "⣽", "⣻", "⢿", "⡿", "⣟", "⣯", "⣷"]
        self.thinking_idx = 0
    
    def thinking(self, message="thinking"):
        char = self.thinking_chars[self.thinking_idx % len(self.thinking_chars)]
        self.thinking_idx += 1
        sys.stdout.write(f"\r {self.t['dim']}{char} {message}...{RST}")
        sys.stdout.flush()
    
    def tool_call(self, tool_name, args=""):
        t = self.t
        args_preview = args[:50] + "..." if len(args) > 50 else args
        print(f"\n {t['accent']}\U0001f527 {t['bright']}{tool_name}{RST} {t['dim']}{args_preview}{RST}")
    
    def tool_result(self, success=True, preview=""):
        t = self.t
        icon = f"{t['bright']}\u2713{RST}" if success else f"{t['err']}\u2717{RST}"
        preview_trunc = preview[:80] + "..." if len(preview) > 80 else preview
        print(f"   {icon} {t['dim']}{preview_trunc}{RST}")
    
    def thinking_start(self):
        self.thinking_idx = 0
    
    def thinking_stop(self):
        sys.stdout.write("\r" + " " * 60 + "\r")
        sys.stdout.flush()

    def progress(self, current, total, label=""):
        t = self.t
        pct = int(current / total * 100) if total > 0 else 0
        bar_len = 20
        filled = int(bar_len * current / total) if total > 0 else 0
        bar = "\u2588" * filled + "\u2591" * (bar_len - filled)
        print(f"\n {t['primary']}[{bar}] {pct}% {label}{RST}")

    def status(self, message, msg_type="info"):
        t = self.t
        icons = {
            "info": f"{t['primary']}\u2139{RST}",
            "success": f"{t['bright']}\u2713{RST}",
            "warning": f"{t['warn']}\u26a0{RST}",
            "error": f"{t['err']}\u2717{RST}",
            "thinking": f"{t['dim']}\U0001f4ad{RST}",
            "tool": f"{t['accent']}\U0001f527{RST}",
            "save": f"{t['primary']}\U0001f4be{RST}",
            "load": f"{t['primary']}\U0001f4c2{RST}"
        }
        icon = icons.get(msg_type, icons["info"])
        print(f" {icon} {message}")

# ── Animated Spinner Thread ─────────────────────────────────

# State for inline bottom-bar spinner
_BOTTOM_BAR_SPINNER_STATE = {
    "enabled": False,
    "history": None,
}

def set_bottom_bar_spinner(history):
    """Enable inline bottom-bar spinner for the next blocking operation."""
    _BOTTOM_BAR_SPINNER_STATE["enabled"] = True
    _BOTTOM_BAR_SPINNER_STATE["history"] = history

def clear_bottom_bar_spinner():
    _BOTTOM_BAR_SPINNER_STATE["enabled"] = False
    _BOTTOM_BAR_SPINNER_STATE["history"] = None

class SpinnerThread(threading.Thread):
    """Background thread that animates a spinner in the persistent footer."""
    def __init__(self, message="processing"):
        super().__init__(daemon=True)
        self.message = message
        self._done = threading.Event()
        self.frames = list(range(8))

    def run(self):
        i = 0
        inline = _BOTTOM_BAR_SPINNER_STATE["enabled"]

        while not self._done.is_set():
            with stdout_lock:
                if inline:
                    history = _BOTTOM_BAR_SPINNER_STATE["history"]
                    char = activity_vector(history=history, frame=self.frames[i % len(self.frames)], busy=True)
                    draw_footer(build_status_bar(history=history, include_indicator=False), spin_char=char)
                    i += 1
                else:
                    t = T()
                    char = activity_vector(frame=self.frames[i % len(self.frames)], busy=True)
                    sys.stdout.write(f"\r\033[K {t['dim']}{char} {self.message}...{RST}")
                    sys.stdout.flush()
                    i += 1

            self._done.wait(0.12)
    def stop(self):
        self._done.set()
        self.join(timeout=2)
        with stdout_lock:
            if _BOTTOM_BAR_SPINNER_STATE["enabled"]:
                history = _BOTTOM_BAR_SPINNER_STATE["history"]
                draw_footer(build_status_bar(history=history, include_indicator=False), spin_char=activity_vector(history=history))
            else:
                sys.stdout.write("\r" + " " * 75 + "\r")
                sys.stdout.flush()
            clear_bottom_bar_spinner()
    
viz = ToolVisualizer()
# ── Debug / Logging ──────────────────────────────────────────────

LOG_FILE = os.path.join(os.path.expanduser("~"), ".prism32", "debug.log")

def debug_log(message, level="INFO"):
    """Write debug message to log file."""
    if not Config.DEBUG and level not in ("ERROR", "WARN"):
        return
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    with open(LOG_FILE, 'a', encoding='utf-8') as f:
        f.write(f"[{timestamp}] [{level}] {message}\n")

def debug_enable():
    """Enable debug logging."""
    Config.DEBUG = True
    os.makedirs(os.path.dirname(LOG_FILE), exist_ok=True)
    viz.status("Debug logging enabled: " + LOG_FILE, "info")

def debug_disable():
    """Disable debug logging."""
    Config.DEBUG = False
    viz.status("Debug logging disabled", "info")

# ── Status Panel ─────────────────────────────────────────────────

def panel(items, title="STATUS", color="primary"):
    """Display a multi-line status panel."""
    t = T()
    tc = t.get(color, t["primary"])
    td = t["dim"]
    
    # Calculate width
    max_len = max(len(str(item)) for item in items) if items else 20
    w = min(max_len + 6, 80)
    
    print(f"\n {tc}+{'─' * (w - 2)}+{RST}")
    print(f" {tc}|{RST} {t['bright']}{title.center(w - 4)}{RST} {tc}|{RST}")
    print(f" {tc}|{td}{'─' * (w - 4)}{RST}{tc}|{RST}")
    for item in items:
        s = str(item)
        print(f" {tc}|{RST} {s:<{w-4}} {tc}|{RST}")
    print(f" {tc}+{'─' * (w - 2)}+{RST}")

def header(text, char="=", width=62):
    """Display a section header."""
    t = T()
    print(f"\n {t['bright']}{char * width}{RST}")
    print(f" {t['bright']} {text}{RST}")
    print(f" {t['dim']}{char * width}{RST}")

def divider(char="─", width=60):
    """Display a thin divider line."""
    t = T()
    print(f" {t['dim']}{char * width}{RST}")

def kv_table(data, indent=1):
    """Display key-value data as a formatted table."""
    t = T()
    pad = " " * indent
    max_key = max(len(str(k)) for k in data.keys()) if data else 10
    for key, val in data.items():
        print(f"{pad}{t['bright']}{str(key).upper():<{max_key+2}}{RST} {val}")

# ── Session Commands ────────────────────────────────────────────

def cmd_session_save(session_id, history, cmd_log, name=None):
    t = T()
    if not session_id:
        session_id = generate_session_id(name)
    path = save_session(session_id, history, cmd_log)
    viz.status(f"Session saved: {session_id}", "save")
    print(f"   {t['dim']}{path}{RST}")
    return session_id

def save_current_session(history, cmd_log):
    """Silently save current session state without showing status."""
    global _CURRENT_SESSION_ID
    if not _CURRENT_SESSION_ID:
        _CURRENT_SESSION_ID = generate_session_id("auto")
    save_session(_CURRENT_SESSION_ID, history, cmd_log)

def cmd_session_load(session_id):
    t = T()
    session_data = load_session(session_id)
    if not session_data:
        viz.status(f"Session not found: {session_id}", "error")
        return None, None
    history = session_data.get("history", [])
    cmd_log = session_data.get("cmd_log", [])
    stats = get_session_stats(session_data)
    viz.status(f"Loaded session: {session_id}", "load")
    print(f"   {t['dim']}Messages: {stats.get('total_messages', 0)}, Commands: {stats.get('total_commands', 0)}{RST}")
    return history, cmd_log

def cmd_session_list():
    t = T()
    sessions = list_sessions()
    if not sessions:
        viz.status("No saved sessions", "info")
        return
    print(f"\n {t['bright']}SAVED SESSIONS{RST}")
    print(f" {t['dim']}{'─' * 60}{RST}")
    for s in sessions[:10]:
        sid = s['id']
        title = s.get('title', sid)[:50]
        ts = s['timestamp'][:19] if s['timestamp'] else 'unknown'
        msgs = s.get('messages', 0)
        cmds = s.get('commands', 0)
        model = s.get('model', 'unknown')[:20]
        print(f" {t['primary']}{title}{RST}")
        print(f"   {t['dim']}{sid}  |  {ts}  |  {msgs} msgs  |  {cmds} cmds  |  {model}{RST}")
    print(f" {t['dim']}{'─' * 60}{RST}")
    print(f" {t['dim']}Total: {len(sessions)} sessions{RST}")

def cmd_session_delete(session_id):
    t = T()
    if delete_session(session_id):
        viz.status(f"Deleted session: {session_id}", "success")
    else:
        viz.status(f"Session not found: {session_id}", "error")

def cmd_session_resume():
    """Interactive session browser -- pick a session by number to load."""
    t = T()
    sessions = list_sessions()
    if not sessions:
        viz.status("No saved sessions", "info")
        return None

    page = 0
    per_page = 10
    total = len(sessions)

    while True:
        start = page * per_page
        end = min(start + per_page, total)
        batch = sessions[start:end]

        print(f"\n {t['bright']}RESUME SESSION{RST}  {t['dim']}(page {page + 1}/{(total - 1) // per_page + 1} | {total} total){RST}")
        print(f" {t['dim']}{'─' * 60}{RST}")
        for i, s in enumerate(batch, start + 1):
            sid = s['id']
            title = s.get('title', sid)[:50]
            ts = s['timestamp'][:19] if s['timestamp'] else 'unknown'
            msgs = s.get('messages', 0)
            cmds = s.get('commands', 0)
            model = s.get('model', 'unknown')[:20]
            label = "goal" if sid.startswith("goal") else "session" if sid.startswith("auto") else "manual"
            print(f" {t['bright']}{i:3d}.{RST} {t['primary']}{title}{RST}  {t['dim']}{label}{RST}")
            print(f"      {t['dim']}{ts}  |  {msgs} msgs  |  {cmds} cmds  |  {model}{RST}")
        print(f" {t['dim']}{'─' * 60}{RST}")
        print(f" {t['dim']}n next  p prev  <number> load  q quit{RST}")

        try:
            inp = input(rl_prompt(f" {t['bright']}resume{RST} {t['primary']}>{RST} ")).strip().lower()
        except (EOFError, KeyboardInterrupt):
            break

        if inp == 'q':
            break
        elif inp == 'n':
            if end < total:
                page += 1
        elif inp == 'p':
            if page > 0:
                page -= 1
        elif inp.isdigit():
            idx = int(inp) - 1
            if 0 <= idx < total:
                s = sessions[idx]
                data = load_session(s['id'])
                if data:
                    msgs = data.get("history", [])
                    print(f"\n  {t['warn']}⤻ loading: {s['id']}{RST}")
                    print(f"  {t['dim']}{'─' * 60}{RST}")
                    for m in msgs[-8:]:
                        role = m.get("role", "?")
                        content = m.get("content", "")
                        if role == "system":
                            continue
                        preview = content[:120].replace('\n', ' ')
                        print(f"  {t['bright'] if role == 'user' else t['primary']}{'you' if role == 'user' else 'ai'}:{RST} {preview}")
                    print(f"  {t['dim']}{'─' * 60}{RST}")
                    try:
                        confirm = input(rl_prompt(f"  {t['warn']}Load?{RST} {t['primary']}(Y/n){RST} ")).strip().lower()
                    except (EOFError, KeyboardInterrupt):
                        break
                    if confirm in ('', 'y', 'yes'):
                        print(f"  {t['bright']}+ Session loaded{RST}\n")
                        return data
                    else:
                        print(f"  {t['dim']}Cancelled{RST}")
                else:
                    print(f"  {t['err']}Failed to load session{RST}")
        else:
            print(f"  {t['dim']}n=next  p=prev  <number>=load  q=quit{RST}")

    return None

# ── History & Export ────────────────────────────────────────
def cmd_session_info(session_id):
    t = T()
    session_data = load_session(session_id)
    if not session_data:
        viz.status(f"Session not found: {session_id}", "error")
        return
    stats = get_session_stats(session_data)
    print(f"\n {t['bright']}SESSION INFO{RST}")
    print(f" {t['dim']}{'─' * 60}{RST}")
    print(f" {t['primary']}ID:{RST} {session_id}")
    print(f" {t['primary']}Created:{RST} {session_data.get('timestamp', 'unknown')}")
    print(f" {t['primary']}Model:{RST} {session_data.get('model', 'unknown')}")
    print(f" {t['primary']}API:{RST} {session_data.get('api_base', 'unknown')}")
    print(f" {t['primary']}Theme:{RST} {session_data.get('theme', 'unknown')}")
    print(f"\n {t['bright']}STATISTICS{RST}")
    print(f" {t['dim']}Messages: {stats.get('total_messages', 0)} (user: {stats.get('user_messages', 0)}, assistant: {stats.get('assistant_messages', 0)}){RST}")
    print(f" {t['dim']}Commands: {stats.get('total_commands', 0)}{RST}")
    cmd_types = stats.get('command_types', {})
    if cmd_types:
        print(f" {t['dim']}Command types:{RST}")
        for ctype, count in cmd_types.items():
            print(f"   {t['dim']}{ctype}: {count}{RST}")
    print(f" {t['dim']}{'─' * 60}{RST}")

# ── Banner ───────────────────────────────────────────────────

def banner():
    t = T()
    c = t['bright']
    d = t['dim']
    print(f"{c}")
    art = [
        " ____  ____  ___ ____  __  __ _________  ",
        "|  _ \\|  _ \\|_ _/ ___||  \\/  |___ /___ \\ ",
        "| |_) | |_) || |\\___ \\| |\\/| | |_ \\ __) |",
        "|  __/|  _ < | | ___) | |  | |___) / __/ ",
        "|_|   |_| \\_\\___|____/|_|  |_|____/_____|",
        "                                         ",
    ]
    for line in art:
        print(f"  {line}")
    print(f"{RST}")
    print(f"{d}  v6.7 - MegaDyne Systems MDS{RST}")
    print(f"{d}  {'='*80}{RST}")
def boot_sequence():
    t = T()
    steps = [
        ("BIOS check", "OK"),
        ("RAM", f"{get_mem()} MB"),
        ("Loading kernel modules", "OK"),
        ("Initializing CRT display", "MDS CRT phosphor glow"),
        ("MDS AI link", f"MDS/{Config.MODEL[:25]}..."),
        ("Subagent model", Config.SUBAGENT_MODEL[:25] + "..." if len(Config.SUBAGENT_MODEL) > 25 else (Config.SUBAGENT_MODEL or "(same as main)")),
        ("MDS system ready", ""),
    ]
    print(f"\n {t['dim']}POST Power-On Self Test{RST}")
    print(f" {t['dim']}{'─' * 54}{RST}")
    for label, extra in steps:
        extra_t = extra or "OK"
        pad = 44 - len(label)
        sys.stdout.write(f" {t['primary']}>{RST} {label}{' ' * max(0, pad)}{extra_t}")
        sys.stdout.flush()
        time.sleep(0.12)
        print()
        time.sleep(0.04)
    print(f" {t['dim']}{'─' * 54}{RST}\n")

def get_mem():
    try:
        with open('/proc/meminfo') as f:
            return int(f.readline().split()[1]) // 1024
    except Exception:
        ram = Platform.get_ram()
        return ram if ram > 0 else 0

# ── System Info ──────────────────────────────────────────────

_SYS_INFO_CACHE = None
def get_system_info(force=False):
    global _SYS_INFO_CACHE
    if _SYS_INFO_CACHE is not None and not force:
        return _SYS_INFO_CACHE
    """Get system information cross-platform."""
    info = {}
    
    # OS
    info['os'] = Platform.get_system()
    
    # CPU
    info['cpu'] = Platform.get_cpu()
    
    # RAM
    ram_mb = Platform.get_ram()
    info['ram'] = f"{ram_mb} MB" if ram_mb > 0 else "Unknown"
    
    # Disk
    try:
        root_path = os.environ.get('SystemDrive', '/') + os.sep if Platform.WINDOWS else '/'
        du = shutil.disk_usage(root_path)
        info['disk'] = f"{du.free / 1024**3:.1f}/{du.total / 1024**3:.1f} GB"
    except Exception:
        info['disk'] = "Unknown"
    
    # Architecture
    info['arch'] = Platform.get_arch()
    
    # IP
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        info['ip'] = s.getsockname()[0]
        s.close()
    except Exception:
        info['ip'] = "N/A"
    
    # Uptime
    info['uptime'] = Platform.get_uptime()
    
    # Package Manager
    pm = Platform.get_package_manager()
    if pm:
        info['pkg_mgr'] = pm
    
    _SYS_INFO_CACHE = info
    return info

def display_system_info():
    t = T()
    info = get_system_info()
    lines = []
    for key, val in info.items():
        lines.append(f"{t['bright']}{key.upper():<10}{RST} {val}")
    box("SYSTEM", "\n".join(lines), "accent")

# ── Shell Execution ──────────────────────────────────────────

def _pty_su_root(cmd, timeout=None):
    """Run command as root via pty-based su (platforms needing a TTY for su)."""
    if select is None:
        return "[ERROR] select module not available on this platform"
    if pty is None:
        return "[ERROR] pty module not available on this platform"
    password = Config.ROOT_PASS
    if not password:
        return "[ERROR] No root password set (use /rootpass)"
    su_path = shutil.which("su")
    if not su_path:
        return "[ERROR] su not found on this system"
    pid, fd = pty.fork()
    if pid == 0:
        if Platform.HPUX:
            os.execv(su_path, ["su", "root", "-c", cmd])
        elif Platform.AIX:
            os.execv(su_path, ["su", "root", "-c", cmd])
        elif Platform.SOLARIS:
            os.execv(su_path, ["su", "root", "-c", cmd])
        elif Platform.IRIX:
            os.execv(su_path, ["su", "root", "-c", cmd])
        elif Platform.TRU64:
            os.execv(su_path, ["su", "root", "-c", cmd])
        else:
            os.execv(su_path, ["su", "root", "-c", cmd])
    else:
        time.sleep(0.3)
        os.write(fd, (password + "\n").encode())
        time.sleep(0.5)
        out = b""
        t_max = timeout or Config.CMD_TIMEOUT
        deadline = time.time() + t_max
        try:
            while True:
                remaining = max(0.1, deadline - time.time())
                r, _, _ = select.select([fd], [], [], remaining)
                if r:
                    data = os.read(fd, 4096)
                    if not data:
                        break
                    out += data
                else:
                    break
        except:
            pass
        try:
            os.close(fd)
        except:
            pass
        output = out.decode(errors="replace")
        return output[-4000:] if len(output) > 4000 else output

def _cmd_succeeded(result):
    """Check if a command result indicates success."""
    low = (result or "").lower()[:60]
    return not any(w in low for w in ["error", "blocked", "timeout", "failed", "not found", "cancelled"])

def _try_plugin_cmd(c, history=None):
    """Check if c is a plugin command and dispatch it, returning result or None."""
    c_stripped = c.strip()
    cmd_name = c_stripped.split(None, 1)[0].lower()
    cmd_args = c_stripped.split(None, 1)[1] if ' ' in c_stripped else ""
    # Handle /quantum from execute blocks (subagents use this)
    if cmd_name == '/quantum' or cmd_name == 'quantum':
        parts = cmd_args.split(None, 1)
        if not cmd_args:
            return str(_quantum)
        if ':' in cmd_args:
            kv = cmd_args.split(':', 1)
            key = kv[0].strip()
            val = kv[1].strip() if len(kv) > 1 else ""
            if val:
                _quantum.put(key, val)
                return f"Quantum: {key} = {val}"
            v = _quantum.get(key)
            return f"Quantum: {key} = {v}" if v is not None else f"Key '{key}' not found"
        return f"Usage: /quantum <key>:<value> or /quantum <key>:"
    if cmd_name in ('/harness', 'harness'):
        sub = cmd_args.split(None, 1)[0].lower() if cmd_args else "show"
        if sub == "scan":
            return format_harnesses(ensure_harness_scan(force=True))
        if sub == "context":
            return harness_context()
        if sub == "path":
            return HARNESS_FILE
        return format_harnesses(load_harnesses())
    if cmd_name in ('/evolve', 'evolve'):
        sub = cmd_args.split(None, 1)[0].lower() if cmd_args else "context"
        if sub == "tools":
            return format_tool_scan(scan_available_tools())
        if sub in ("diff", "compare"):
            return evolve_diff()
        if sub in ("docs", "doc"):
            ensure_evolve_files(refresh_tools=False)
            return _safe_read(EVOLVE_DOC_FILE)[:4000]
        return evolve_context()
    if cmd_name in ('/extend', 'extend'):
        return extend_with_plugin(cmd_args, history=history)
    if cmd_name in ('/memory', 'memory'):
        sub = cmd_args.split(None, 1)[0].lower() if cmd_args else "startup"
        if sub in ("path", "paths"):
            return f"startup_memory={STARTUP_MEMORY_FILE}\nmemory_json={MEMORY_FILE}"
        return startup_memory_context(limit=3000)
    if registry.get(cmd_name):
        return registry.dispatch_capture(cmd_name, cmd_args)
    return None

def _tail_cmd_output(out):
    text = bytes(out).decode(errors="replace") if isinstance(out, bytearray) else str(out)
    return text[-4000:] if len(text) > 4000 else text

def _terminate_process(proc):
    try:
        if os.name == 'posix' and hasattr(os, 'killpg'):
            os.killpg(proc.pid, signal.SIGTERM)
        else:
            proc.terminate()
    except Exception:
        try:
            proc.terminate()
        except Exception:
            pass
    try:
        proc.wait(timeout=1)
    except Exception:
        try:
            if os.name == 'posix' and hasattr(os, 'killpg'):
                os.killpg(proc.pid, signal.SIGKILL)
            else:
                proc.kill()
        except Exception:
            pass

def _can_cancel_foreground_input():
    if select is None or sys.platform == 'win32':
        return False
    if threading.current_thread() is not threading.main_thread():
        return False
    try:
        return sys.stdin.isatty()
    except Exception:
        return False

def run_cmd(cmd, timeout=None):
    global _INTERJECTION_RESULT
    if timeout is None:
        timeout = Config.CMD_TIMEOUT
    try:
        if Config.ROOT_PASS and ('su' in cmd or 'sudo' in cmd):
            return _pty_su_root(cmd, timeout)
        if _can_cancel_foreground_input():
            clear_agent_cancel()
            out = bytearray()
            popen_kwargs = {
                "shell": True,
                "stdout": subprocess.PIPE,
                "stderr": subprocess.STDOUT,
            }
            if os.name == 'posix':
                popen_kwargs["start_new_session"] = True
            proc = subprocess.Popen(cmd, **popen_kwargs)
            deadline = time.time() + timeout
            _interjection_start()
            try:
                while True:
                    inj = _interjection_poll()
                    if inj is _INTERJECTION_CANCEL or agent_cancel_requested():
                        request_agent_cancel()
                        _terminate_process(proc)
                        output = _tail_cmd_output(out)
                        suffix = ("\n" + output) if output else ""
                        return f"[CANCELLED] Command stopped by Escape{suffix}"
                    if inj is not None:
                        _INTERJECTION_RESULT = None
                        request_agent_cancel("Command interrupted by user input")
                        _terminate_process(proc)
                        output = _tail_cmd_output(out)
                        suffix = ("\n" + output) if output else ""
                        return f"[CANCELLED] Command interrupted by user input{suffix}"

                    if proc.stdout is not None:
                        readable, _, _ = select.select([proc.stdout], [], [], 0.05)
                        if readable:
                            data = os.read(proc.stdout.fileno(), 4096)
                            if data:
                                out.extend(data)
                    if proc.poll() is not None:
                        if proc.stdout is not None:
                            while True:
                                readable, _, _ = select.select([proc.stdout], [], [], 0)
                                if not readable:
                                    break
                                data = os.read(proc.stdout.fileno(), 4096)
                                if not data:
                                    break
                                out.extend(data)
                        break
                    if time.time() > deadline:
                        _terminate_process(proc)
                        output = _tail_cmd_output(out)
                        suffix = ("\n" + output) if output else ""
                        return f"[TIMEOUT] Command exceeded {timeout}s{suffix}"
            finally:
                _interjection_stop()
            return _tail_cmd_output(out)
        result = subprocess.run(cmd, shell=True, capture_output=True, text=True, timeout=timeout)
        out = result.stdout + result.stderr
        return out[-4000:] if len(out) > 4000 else out
    except subprocess.TimeoutExpired:
        return f"[TIMEOUT] Command exceeded {timeout}s"
    except Exception as e:
        return f"[ERROR] {e}"

def cmd_result(cmd, output, success=True):
    t = T()
    c = t['bright'] if success else t['err']
    icon = "+" if success else "!"
    print(f"{c} {icon} {cmd}{RST}")
    for line in output.split('\n')[:25]:
        print(f"  {DIM}{line}{RST}")
    if output.count('\n') > 25:
        print(f"  {DIM}... ({output.count(chr(10)) + 1} lines){RST}")

# ── Quantum Entanglement Shared Context ─────────────────────
class QuantumContext:
    def __init__(self):
        self._data = {}
        self._lock = threading.Lock()
        self._used = False

    def put(self, key, value):
        with self._lock:
            self._data[key] = value
            self._used = True
        # Show indicator in footer on next redraw
        return key

    def get(self, key, default=None):
        with self._lock:
            val = self._data.get(key, default)
            if val is not None:
                self._used = True
            return val

    def delete(self, key):
        with self._lock:
            return self._data.pop(key, None)

    def items(self):
        with self._lock:
            return dict(self._data)

    def merge(self, data):
        with self._lock:
            self._data.update(data)
            self._used = True

    def clear(self):
        with self._lock:
            self._data.clear()

    def was_used(self):
        with self._lock:
            u = self._used
            self._used = False
            return u

    def __str__(self):
        with self._lock:
            if not self._data:
                return "(empty)"
            return "\n".join(f"  {k}: {str(v)[:120]}" for k, v in self._data.items())

_quantum = QuantumContext()
_SUBAGENTS = {}  # id -> SubAgent instance
_subagent_lock = threading.Lock()
_next_sa_id = 0

SUBAGENT_SYSTEM_PROMPT = """You are a Prism32 subagent. You have FULL bash access via:
```execute
command here
```

You are working on a subtask delegated by the main agent. Work autonomously step by step.

A shared quantum context is available between all agents. Read from it using:
```execute
/quantum
```
Write to it using:
```execute
/quantum <key>:<value>
```
Read a specific key using:
```execute
/quantum <key>:
```

Use /remember <text> to store important findings in long-term memory.
Use /recall <query> to search past memories from any agent.
Detected external AI harnesses are listed in context. If useful, inspect their help first and use them through execute blocks.
"""

class SubAgent:
    def __init__(self, task, model=None, max_steps=50, provider=None):
        global _next_sa_id
        self.id = f"sa_{_next_sa_id}"
        _next_sa_id += 1
        self.task = task
        self.model = model or Config.SUBAGENT_MODEL or Config.MODEL
        self.max_steps = max_steps
        self.provider = provider
        self.result = None
        self.error = None
        self.done = False
        self._step = 0
        self._history = []
        self._thread = None

    def _build_history(self):
        ctx = build_context()
        qctx = str(_quantum)
        extra = ""
        if qctx != "(empty)":
            extra = f"\nShared quantum context:\n{qctx}\n"
        sys = SUBAGENT_SYSTEM_PROMPT + "\n" + ctx + extra
        return [{"role": "system", "content": sys},
                {"role": "user", "content": f"Task: {self.task}\nWork autonomously. Use execute blocks."}]

    def _run_loop(self):
        t = T()
        self._history = self._build_history()
        old_model = Config.MODEL
        old_stream = Config.STREAM
        old_provider = Config.PROVIDER
        old_api_base = Config.API_BASE
        old_api_key = Config.API_KEY
        if self.provider and self.provider in PROVIDER_REGISTRY:
            prov = PROVIDER_REGISTRY[self.provider]
            Config.PROVIDER = self.provider
            Config.API_BASE = prov["api_base"]
            Config.MODEL = prov.get("model", self.model)
            if prov.get("default_key"):
                Config.API_KEY = prov["default_key"]
        else:
            Config.MODEL = self.model
        Config.STREAM = False
        try:
            for iteration in range(self.max_steps):
                self._step = iteration + 1
                with stdout_lock:
                    t = T()
                    print(f"  {t['dim']}[{self.id}] Step {self._step}/{self.max_steps}{RST}")
                resp = ask_ai(self._history, stream=False)
                if not resp or resp.startswith('['):
                    self.error = resp or "No response"
                    self.result = f"[SUBAGENT ERROR] {self.error}"
                    break
                resp, _asked = handle_ask_blocks(resp, self._history, allow_input=False, return_asked=True)
                commands = extract_blocks(resp, 'execute')
                if commands:
                    clean = clean_response(resp)
                    if resp.strip():
                        self._history.append({"role": "assistant", "content": resp})
                    for c in commands:
                        c = c.strip()
                        plugin_result = _try_plugin_cmd(c, history=self._history)
                        if plugin_result is not None:
                            result = plugin_result.strip()
                        else:
                            result = run_cmd(c)
                        success = _cmd_succeeded(result)
                        cmd_result(c, result, success)
                        msg = f"Executed: {c}\nResult:\n{result[:1500]}"
                        self._history.append({"role": "user", "content": f"{msg}\n\nCommand output above. Continue with task or give final answer."})
                    # Inject latest quantum context so subagent sees cross-agent data
                    self._history[0] = self._build_history()
                else:
                    clean = clean_response(resp)
                    self.result = clean
                    self.done = True
                    return
            self.result = self.result or "[SUBAGENT] Max steps reached without completion."
            self.done = True
        finally:
            Config.MODEL = old_model
            Config.STREAM = old_stream
            Config.PROVIDER = old_provider
            Config.API_BASE = old_api_base
            Config.API_KEY = old_api_key

    def run(self):
        with stdout_lock:
            t = T()
            print(f"\n  {t['primary']}╭─ SUBAGENT [{self.id}] ─────────────────────{RST}")
            print(f"  {t['primary']}│{RST}  {t['bright']}Task:{RST} {self.task[:80]}")
            prov_info = f"  {t['dim']}Provider:{RST} {self.provider}" if self.provider else ""
            print(f"  {t['primary']}│{RST}  {t['dim']}Model:{RST} {self.model[:40]}{prov_info}")
            print(f"  {t['primary']}╰{'─' * 50}{RST}")
        spin = SpinnerThread(f"subagent {self.id}")
        spin.start()
        try:
            self._run_loop()
        finally:
            spin.stop()
        with stdout_lock:
            t = T()
            status = "COMPLETE" if self.done and not self.error else "ERROR"
            color = t.get("ok", t.get("primary", "")) if self.done and not self.error else t.get("err", "")
            print(f"\n  {color}╭─ SUBAGENT [{self.id}] {status} ───────────{RST}")
            print(f"  {color}│{RST}  {t['bright']}Result:{RST} {(self.result or self.error or '?')[:200]}")
            print(f"  {color}╰{'─' * 50}{RST}")
        return self.result

    def run_async(self):
        self._thread = threading.Thread(target=self._run_loop, daemon=True)
        self._thread.start()
        with _subagent_lock:
            _SUBAGENTS[self.id] = self
        t = T()
        print(f"\n  {T()['warn']}╭─ SPAWNED SUBAGENT [{self.id}] ASYNC ────────{RST}")
        print(f"  {T()['warn']}│{RST}  {t['bright']}Task:{RST} {self.task[:80]}")
        prov_info = f"  {t['dim']}Provider:{RST} {self.provider}" if self.provider else ""
        print(f"  {T()['warn']}│{RST}  {t['dim']}Model:{RST} {self.model[:40]}{prov_info}")
        print(f"  {T()['warn']}╰{'─' * 50}{RST}")
        return self.id

    def status_str(self):
        if not self.done:
            return f"[{self.id}] RUNNING step {self._step}/{self.max_steps}  task: {self.task[:50]}"
        if self.error:
            return f"[{self.id}] ERROR    task: {self.task[:50]}  err: {self.error[:40]}"
        return f"[{self.id}] DONE     task: {self.task[:50]}  result: {(self.result or '?')[:40]}"

# ── AI Communication ────────────────────────────────────────

SYSTEM_PROMPT = """You are Prism32, an AI terminal agent running on a retro system.
You have FULL bash access. Execute commands directly using:

```execute
command here
```

When you need to ask the user a question or request clarification, use:

```ask
Your question here
```

You can also delegate work to subagents using the /delegate command.
Subagents run autonomously with their own execute-loop and report results.
Use /delegate <task description> when a task is self-contained and can run independently.
Add --provider <name> to run a subagent against a different provider (e.g. /delegate scan ports --provider groq).
Use /quantum <key>:<value> to share information between agents during this session.
Use /remember <text> to store important findings in long-term memory (persists across sessions).
Use /recall <query> to search past memories when you need relevant context on a topic.
Use /subagents to list running or completed subagents.
Skills are reusable workflows stored in ~/.prism32/skills/. Use /skill-list to see them and /skill-load <name> to activate a skill's instructions in context.
Use /harness scan to detect external AI agent CLIs and /harness delegate <task> to launch a super subagent seeded with those capabilities.
Use /evolve on when Prism32 needs self-repair/plugin-generation docs, baseline comparison, and local tool exploration.
Use /extend temp <goal> when a missing reusable capability would help complete the task. This generates, syntax-checks, writes, and loads a temporary Prism32 plugin. Use /extend permanent <goal> only when the operator explicitly asks for a persistent extension. Prefer plugin self-extension over editing prism32.py; edit core code only when the requested change cannot be solved as a plugin.

When given a GOAL, work autonomously step by step. After each command,
assess progress toward the goal. Use ```ask``` only if truly stuck.

CROSS-PLATFORM RULES:
1. Detect the OS first: uname -s when available, plus /sysinfo context. Targets include Linux, Android/Termux, ChromeOS/Crostini, WSL/WSL2, Docker/Podman/Kubernetes/CI containers, Proxmox, TrueNAS, pfSense, OPNsense, Unraid, SteamOS, macOS, BSD, Windows, SunOS/Solaris/illumos, AIX, HP-UX, IRIX, Tru64, Haiku, QNX, MINIX, Cygwin/MSYS2, IBM z/OS, IBM i PASE, OpenVMS, and embedded BusyBox systems.
2. Use the system's actual package manager: apt/apt-get, dnf/microdnf/tdnf/yum, pacman, zypper, apk, rpm-ostree, swupd, opkg/ipkg, emerge, xbps-install, eopkg, slackpkg, guix, nix, brew/port, pkgin/pkg_add/pkg, Solaris pkg/pkgadd/pkgutil, swinstall, inst, setld, installp, pkgman, winget/choco/scoop. Prefer OS-native over universal ones.
3. Use appropriate network command: ip/ss (modern Linux), busybox/ip/ifconfig/netstat (embedded), ifconfig/netstat (macOS/BSD/Solaris/old Unix), ipconfig/route/netstat/Get-NetAdapter (Windows). In containers/CI, check namespace and mounted filesystem limits before changing networking.
4. Prefer POSIX sh syntax on unknown Unix, embedded systems, containers, Solaris, AIX, HP-UX, IRIX, Tru64, QNX, and appliance/NAS platforms. Avoid GNU-only flags unless GNU tools are detected.
5. On appliances and immutable systems (Proxmox, TrueNAS, pfSense, OPNsense, Unraid, SteamOS, Fedora CoreOS/Silverblue/Kinoite, Clear Linux), inspect documentation/tooling first and avoid host storage/network changes unless explicitly requested.
6. For root access on Linux: echo "$ROOT_PASS" | su -c "command" or use sudo. For BSD/old Unix: su root -c "command". For macOS: sudo command. On Windows, use PowerShell or cmd; avoid Unix-only utilities unless in Cygwin/MSYS/WSL.

GENERAL RULES:
1. ALWAYS run commands to investigate - don't just suggest them
2. Verify fixes work by running check commands
3. Be concise and direct
4. Chain commands with && or ; when logical
5. When a goal is set, keep working until done or max steps reached
6. Report what you did and what remains after each step"""

def ask_ai(messages, stream=None, retry=2, base_delay=2, cancel_event=None):
    '''Resilient AI query with retry, backoff, and history trimming.'''
    # Filter empty messages
    clean_messages = []
    for m in messages:
        content = m.get("content", "")
        if isinstance(content, list):
            if content:
                clean_messages.append(m)
        elif str(content).strip():
            clean_messages.append(m)
    if not clean_messages:
        clean_messages = messages[:1]
    
    # Trim history if too large
    clean_messages = trim_history(clean_messages, 240000)
    
    url = f"{Config.API_BASE.rstrip('/').rstrip('v1').rstrip('/')}/v1/chat/completions"
    payload = {
        "model": Config.MODEL,
        "messages": clean_messages,
        "stream": stream if stream is not None else Config.STREAM,
        "max_tokens": Config.MAX_RESPONSE_TOKENS,
        "temperature": Config.TEMPERATURE,
    }
    if Config.THINKING_EFFORT:
        payload["reasoning_effort"] = Config.THINKING_EFFORT
    
    last_error = ""
    for attempt in range(retry + 1):
        if agent_cancel_requested(cancel_event):
            return AGENT_CANCELLED_RESPONSE
        try:
            req = urllib.request.Request(
                url,
                data=json.dumps(payload).encode(),
                headers=build_headers(),
            )
            with urllib.request.urlopen(req, timeout=600) as resp:
                if stream if stream is not None else Config.STREAM:
                    return stream_response(resp, cancel_event=cancel_event)
                data = json.loads(resp.read().decode())
                if agent_cancel_requested(cancel_event):
                    return AGENT_CANCELLED_RESPONSE
                return data.get('choices', [{}])[0].get('message', {}).get('content', '')
        except urllib.error.HTTPError as e:
            if agent_cancel_requested(cancel_event):
                return AGENT_CANCELLED_RESPONSE
            body = e.read().decode()[:500]
            if e.code == 401:
                last_error = f"[HTTP ERROR 401] Authentication failed. Set a valid API key via /provider key or --api-key"
                learn_error(last_error, f"HTTP 401: {body[:100]}")
            else:
                last_error = f"[HTTP ERROR {e.code}] {body}"
            if e.code in (400, 413, 429, 503) and attempt < retry:
                delay = base_delay * (2 ** attempt)
                viz.status(f"API error {e.code}, retrying in {delay}s...", "warning")
                time.sleep(delay)
                # Trim history more aggressively on retry
                if e.code in (400, 413):
                    clean_messages = trim_history(clean_messages, Config.resolve_context_window() // 2)
                    payload["messages"] = clean_messages
            continue
            break
        except (urllib.error.URLError, ConnectionError, TimeoutError) as e:
            if agent_cancel_requested(cancel_event):
                return AGENT_CANCELLED_RESPONSE
            last_error = f"[NETWORK ERROR] {e}"
            learn_error(str(e), "network")
            if attempt < retry:
                delay = base_delay * (2 ** attempt)
                viz.status(f"Network error, retrying in {delay}s...", "warning")
                time.sleep(delay)
                continue
            break
        except Exception as e:
            if agent_cancel_requested(cancel_event):
                return AGENT_CANCELLED_RESPONSE
            last_error = f"[ERROR] {e}"
            learn_error(str(e), "ask_ai exception")
            break
    
    return last_error

def stream_response(resp, cancel_event=None):
    full = ""
    t = T()
    reasoning_mode = False
    agent_prefix_printed = False
    stream_color = None
    display_buf = ""
    display_color = None
    last_flush = time.monotonic()
    fence_state = {"pending": "", "hidden": False}

    def _filter_visible_content(text, final=False):
        data = fence_state["pending"] + text
        fence_state["pending"] = ""
        out = []
        i = 0
        while i < len(data):
            if fence_state["hidden"]:
                end = data.find("```", i)
                if end == -1:
                    fence_state["pending"] = data[-2:] if len(data) > 2 else data
                    return "".join(out)
                fence_state["hidden"] = False
                i = end + 3
                if i < len(data) and data[i] == "\n":
                    i += 1
                continue

            start = data.find("```", i)
            if start == -1:
                if final:
                    out.append(data[i:])
                    fence_state["pending"] = ""
                else:
                    keep = 10
                    if len(data) - i > keep:
                        out.append(data[i:len(data)-keep])
                        fence_state["pending"] = data[len(data)-keep:]
                    else:
                        fence_state["pending"] = data[i:]
                return "".join(out)

            out.append(data[i:start])
            line_end = data.find("\n", start)
            if line_end == -1:
                fence_state["pending"] = data[start:]
                return "".join(out)
            fence_line = data[start:line_end].strip().lower()
            if fence_line.startswith("```execute") or fence_line.startswith("```ask"):
                fence_state["hidden"] = True
                i = line_end + 1
            else:
                out.append(data[start:line_end + 1])
                i = line_end + 1
        return "".join(out)

    def _queue_display(text, color_key):
        nonlocal display_buf, display_color, stream_color, agent_prefix_printed, last_flush
        if not text:
            return
        if display_color != color_key:
            _flush_display(force=True)
            display_color = color_key
        display_buf += text
        now = time.monotonic()
        if "\n" in display_buf or len(display_buf) >= 240 or now - last_flush >= 0.15:
            _flush_display(force=True)

    def _flush_display(force=False):
        nonlocal display_buf, stream_color, agent_prefix_printed, last_flush
        if not display_buf:
            return
        if not force and "\n" not in display_buf and len(display_buf) < 240:
            return
        color = t['dim'] if display_color == "reasoning" else t['primary']
        with stdout_lock:
            if not agent_prefix_printed:
                prefix_color = t['accent'] if display_color == "reasoning" else t['primary']
                sys.stdout.write(f" {prefix_color}<{Config.AGENT_NAME}>:{RST} ")
                agent_prefix_printed = True
                stream_color = None
            if stream_color != display_color:
                sys.stdout.write(color)
                stream_color = display_color
            sys.stdout.write(display_buf)
            sys.stdout.flush()
        display_buf = ""
        last_flush = time.monotonic()
    
    with stdout_lock:
        move_to_scroll_bottom()
    
    for line in resp:
        if agent_cancel_requested(cancel_event):
            break
        line = line.decode('utf-8', errors='ignore').strip()
        if not line or not line.startswith('data: '):
            continue
        data = line[6:]
        if data == '[DONE]':
            break
        try:
            chunk = json.loads(data)
            delta = chunk.get('choices', [{}])[0].get('delta', {})
            content = delta.get('content', '')
            reasoning = delta.get('reasoning_content', '') or delta.get('reasoning', '')
            
            if reasoning:
                _queue_display(reasoning, "reasoning")
                full += reasoning
                reasoning_mode = True
            
            if content:
                if reasoning_mode:
                    _queue_display("\n", "content")
                    reasoning_mode = False
                _queue_display(_filter_visible_content(content), "content")
                full += content
        except json.JSONDecodeError:
            continue

        inj = _interjection_poll()
        if inj is _INTERJECTION_CANCEL or agent_cancel_requested(cancel_event):
            request_agent_cancel(cancel_event=cancel_event)
            _queue_display(_filter_visible_content("", final=True), "content")
            _flush_display(force=True)
            _interjection_stop()
            with stdout_lock:
                sys.stdout.write(RST + SHOW)
            return AGENT_CANCELLED_RESPONSE
        if inj is not None:
            request_agent_cancel("Agent interrupted by user input", cancel_event=cancel_event)
            clear_agent_cancel()
            _queue_display(_filter_visible_content("", final=True), "content")
            _flush_display(force=True)
            _interjection_stop()
            with stdout_lock:
                sys.stdout.write(RST + SHOW)
            return full
    
    if agent_cancel_requested(cancel_event):
        _queue_display(_filter_visible_content("", final=True), "content")
        _flush_display(force=True)
        _interjection_stop()
        with stdout_lock:
            sys.stdout.write(RST + SHOW)
        return AGENT_CANCELLED_RESPONSE

    _queue_display(_filter_visible_content("", final=True), "content")
    _flush_display(force=True)
    _interjection_stop()
    with stdout_lock:
        sys.stdout.write(RST + SHOW)
    return full
def extract_blocks(text, tag):
    _re = _RE_EXEC_BLOCK if tag == 'execute' else _RE_ASK_BLOCK
    return [b.strip() for b in _re.findall(text)]

def clean_response(text):
    clean = text
    if '</think>' in clean:
        clean = clean.split('</think>')[-1].strip()
    for tag in ('execute', 'ask'):
        clean = re.sub(rf'```{tag}\n.*?```', '', clean, flags=re.DOTALL)
    return clean.strip()

def clean_ask_blocks(text):
    """Remove ask blocks while preserving execute blocks for the agent loop."""
    clean = text
    if '</think>' in clean:
        clean = clean.split('</think>')[-1].strip()
    clean = re.sub(r'```ask\n.*?```', '', clean, flags=re.DOTALL)
    return clean.strip()

# ── Context Builder ──────────────────────────────────────────

def build_context():
    info = get_system_info()
    mem = memory_context()
    extra = ""
    if _PluginHooks._extra_context:
        extra = "\n" + "\n".join(_PluginHooks._extra_context) + "\n"
    soul = read_soul()
    soul_block = f"\nCUSTOM RULES (soul.md):\n{soul}\n" if soul else ""
    startup_mem = startup_memory_context()
    startup_block = f"\nSTARTUP MEMORY ({STARTUP_MEMORY_FILE}):\n{startup_mem}\n" if startup_mem else ""
    harness_block = f"\n{harness_context()}\n"
    evolve_block = f"\n{evolve_context()}\n" if _EVOLVE_MODE else ""
    
    # List available plugin commands that the AI can invoke via execute blocks
    plugin_cmds = [cmd.name for cmd in registry.all()
                   if cmd.name not in ("help", "quit", "goal")]
    plugin_block = ""
    if plugin_cmds:
        plugin_block = f"\nAvailable plugin commands (use in ```execute blocks): {', '.join(sorted(plugin_cmds))}\n"
    
    return (
        f"System: {info.get('os', '')} {info.get('arch', '')}\n"
        f"CPU: {info.get('cpu', '')}\nRAM: {info.get('ram', '')}\n"
        f"Disk: {info.get('disk', '')}\nIP: {info.get('ip', '')}\n"
        f"Uptime: {info.get('uptime', '')}\nCWD: {os.getcwd()}\n"
        f"Memory:{mem}\n{extra}{startup_block}{soul_block}{harness_block}{evolve_block}{plugin_block}\nPROMPTSHARD status: {read_promptshard().get('status', 'active')} | Captain agent delegates using /delegate and /spawn with quantum context syncing."
    )

# ── User Interaction (ask / interject) ──────────────────────

def ask_user(question):
    t = T()
    if _footer_reserved:
        release_footer_for_output()
    print(f"\n{t['warn']}+ QUESTION FROM AI:{RST}")
    box("AI NEEDS INPUT", question, "warn")
    try:
        answer = input(rl_prompt(f" {t['bright']}answer{RST} {t['primary']}>{RST} ")).strip()
    except (EOFError, KeyboardInterrupt):
        answer = ""
    return answer

def handle_ask_blocks(resp, history, goal_mode=False, allow_input=True, return_asked=False):
    t = T()
    questions = extract_blocks(resp, 'ask')
    if not questions:
        return (resp, False) if return_asked else resp
    
    if goal_mode or not allow_input:
        # In goal mode, don't ask questions - strip them and continue
        cleaned = clean_ask_blocks(resp)
        if not cleaned:
            if allow_input:
                # Force the model to execute commands instead of asking
                cleaned = "Run commands. Do not ask questions."
            else:
                joined = " | ".join(q.strip() for q in questions if q.strip())
                cleaned = f"[SUBAGENT NEEDS INPUT] {joined}" if joined else "[SUBAGENT NEEDS INPUT]"
        if goal_mode:
            viz.status("Stripped question blocks in goal mode", "warning")
        return (cleaned, True) if return_asked else cleaned
    
    for q in questions:
        answer = ask_user(q.strip())
        history.append({"role": "assistant", "content": f"[User was asked]: {q.strip()}"})
        history.append({"role": "user", "content": f"[User answered]: {answer}"})
    cleaned = clean_ask_blocks(resp)
    return (cleaned, True) if return_asked else cleaned

# ── Goal Mode ────────────────────────────────────────────────

GOAL_PROMPT_TEMPLATE = """GOAL: {goal}

You are in GOAL MODE. You MUST run commands to accomplish this goal.
DO NOT claim completion without evidence. DO NOT hallucinate results.

REQUIRED WORKFLOW:
1. Run commands using ```execute blocks to investigate
2. Analyze actual command output
3. Only claim GOAL COMPLETE after you have run commands and verified results

NEVER say "GOAL COMPLETE" on your first response. You must execute at least 3 commands first.

Use ```execute``` for each step. Chain commands when logical.
Use ```ask``` ONLY if truly stuck.

Max steps: {max_steps}. Be efficient. When the goal is achieved, summarize what was done and verified."""

def cmd_goal(goal_text, history, cmd_log):
    global _INTERJECTION_RESULT
    t = T()
    if not goal_text:
        print(f"  Usage: goal <describe what to accomplish>")
        print(f"  Example: goal install nginx and configure it as a reverse proxy")
        return

    max_steps = Config.GOAL_MAX_STEPS
    goal_msg = GOAL_PROMPT_TEMPLATE.format(goal=goal_text, max_steps=max_steps)

    print(f"\n{t['bright']}{'='*62}{RST}")
    print(f" {t['bright']}GOAL MODE ACTIVATED{RST}")
    print(f" {t['dim']}{goal_text}{RST}")
    print(f" {t['dim']}Max steps: {max_steps}{RST}")
    print(f"{t['bright']}{'='*62}{RST}\n")

    history.append({"role": "user", "content": goal_msg})
    completed = False
    cancelled = False
    goal_session_id = datetime.now().strftime("goal_%Y%m%d_%H%M%S")

    for step in range(1, max_steps + 1):
        # Auto-save every 3 steps for crash recovery
        if step > 1 and step % 3 == 1:
            try:
                save_session(goal_session_id, history, cmd_log, {"type": "goal", "goal": goal_text, "step": step})
            except Exception:
                pass
        step_header(step, max_steps, goal_text)
        spin = None
        try:
            if Config.STREAM:
                move_to_scroll_bottom()
                _interjection_start()
                resp = ask_ai(history)
                print()
            else:
                resp = ask_ai_cancelable(history, history=history)
        except KeyboardInterrupt:
            resp = None
        finally:
            if spin is not None:
                spin.stop()
            _interjection_stop()
        if _INTERJECTION_RESULT is not None:
            _INTERJECTION_RESULT = None
            clear_agent_cancel()
            box("STOPPED", "Goal interrupted by user input", "warn")
            cancelled = True
            break
        if resp == AGENT_CANCELLED_RESPONSE or agent_cancel_requested():
            msg = agent_cancel_message()
            clear_agent_cancel()
            box("STOPPED", msg, "warn")
            cancelled = True
            break
        if resp and (resp.startswith('[HTTP ERROR 400]') or resp.startswith('[HTTP ERROR 413]')):
            if len(history) > 5:
                history = [history[0]] + history[:-4]
            viz.status("API error, trimming history and retrying...", "warning")
            resp = ask_ai_cancelable(history, history=history)
        if resp and (resp.startswith('[HTTP ERROR 400]') or resp.startswith('[HTTP ERROR 413]')):
            # Second failure - strip back to just system + goal, retry once more
            history = history[:2]
            viz.status("API error again, stripping history to system+goal...", "warning")
            resp = ask_ai_cancelable(history, history=history)
        if resp == AGENT_CANCELLED_RESPONSE or agent_cancel_requested():
            msg = agent_cancel_message()
            clear_agent_cancel()
            box("STOPPED", msg, "warn")
            cancelled = True
            break
        if not resp or resp.startswith('['):
            box("AI ERROR", resp or "No response", "err")
            break

        resp = handle_ask_blocks(resp, history, goal_mode=True)

        commands = extract_blocks(resp, 'execute')
        
        if 'GOAL COMPLETE' in resp.upper() and step > 1 and len(commands) == 0:
            # Only accept GOAL COMPLETE if we've actually done some work
            completed = True
            clean = clean_response(resp)
            box("GOAL COMPLETE", clean, "bright")
            history.append({"role": "assistant", "content": resp})
            break
        elif 'GOAL COMPLETE' in resp.upper() and step <= 1:
            # Model is hallucinating - force it to run commands
            resp = "You claimed GOAL COMPLETE without running any commands. You MUST execute commands using ```execute blocks to investigate the system first. Start with: ```execute\ndf -h\n```"
            commands = extract_blocks(resp, 'execute')

        if commands:
            clean = clean_response(resp)
            if clean:
                box(f"STEP {step} ANALYSIS", clean, "accent")

            command_cancelled = False
            for c in commands:
                c = c.strip()
                viz.tool_call("execute", c)
                result = run_cmd(c)
                command_cancelled = agent_cancel_requested() or (result or "").startswith("[CANCELLED]")
                success = _cmd_succeeded(result)
                viz.tool_result(success, result[:100])
                cmd_result(c, result, success)
                learn_command(c, success=success)
                cmd_log.append(("goal", c))
                viz.progress(step, max_steps, f"step {step}/{max_steps}")

                exec_msg = f"Executed: {c}\nResult:\n{result[:1500]}"
                continuation = f"Command succeeded={success}. Continue toward goal or report completion."
                if exec_msg.strip():
                    history.append({"role": "user", "content": f"{exec_msg}\n\n{continuation}"})
                else:
                    history.append({"role": "user", "content": continuation})
                if command_cancelled:
                    msg = agent_cancel_message()
                    clear_agent_cancel()
                    box("STOPPED", msg, "warn")
                    cancelled = True
                    break
            if command_cancelled:
                break
        else:
            clean = clean_response(resp)
            if not resp or not resp.strip():
                resp = "Continuing toward goal."
                clean = "Continuing toward goal."
            box(f"STEP {step} RESPONSE", clean, "bright")
            history.append({"role": "assistant", "content": resp})

        # Trim history if approaching context limit
        if step > 3 and len(history) > 10:
            history = trim_history(history)
        
        time.sleep(Config.GOAL_STEP_DELAY)

    if not completed and not cancelled:
        print(f"\n{t['warn']} Reached max steps ({max_steps}). Goal may be incomplete.{RST}")

    learn_session(len(history), len(cmd_log), goal_mode=True)
    print(f"\n{t['bright']}{'='*62}{RST}")
    print(f" {t['bright']}GOAL SESSION END{RST}")
    print(f" {t['dim']}Steps used: {step}/{max_steps}{RST}")
    print(f" {t['dim']}Commands run: {len([c for c in cmd_log if c[0] == 'goal'])}{RST}")
    print(f"{t['bright']}{'='*62}{RST}\n")

    if len(history) > Config.MAX_HISTORY:
        history = [history[0]] + history[-(Config.MAX_HISTORY - 1):]

# ── Built-in Commands ────────────────────────────────────────

# ── Dynamic command names ──────────────────────────────────
_ALL_CMDS = registry.names() | {
    'agentname', 'api', 'apikey', 'arch', 'autosave', 'bash', 'cat', 'clear', 'collect', 'config', 'debug', 'delegate', 'delete', 'edit', 'evolve', 'extend', 'exit', 'export', 'find', 'forget', 'git', 'goal', 'grep', 'harness', 'help', 'history', 'key', 'load', 'loadcfg', 'log', 'ls', 'maxhistory', 'maxsteps', 'maxtokens', 'memories', 'memory', 'model', 'net', 'ports', 'procs', 'provider', 'providers', 'q', 'quantum', 'quit', 'recall', 'remember', 'resume', 'rootpass', 'sam', 'save', 'savecfg', 'session', 'sessions', 'skill-create', 'skill-delete', 'skill-list', 'skill-load', 'spawn', 'stream', 'subagent-model', 'subagents', 'sysinfo', 'temperature', 'theme', 'thinking', 'timeout', 'update', 'usage', 'plugins'
, 'memctx', 'memory'
}

CMD_HELP = """{bold}== Prism32 by MegaDyne Systems (MDS) =={reset}
 All commands require the / prefix.

 {bold}AI Interaction{reset}
   <anything>           Talk to AI - it runs commands automatically
   /goal <task>         Autonomous multi-step goal mode
   /extend <goal>       AI-generate/load a temporary plugin
   /extend permanent <g> AI-generate/load persistent plugin

 {bold}Configuration{reset}
   /agentname <name>    Set the name shown before assistant responses
   /provider [name]    Switch provider (add|rm|api|key|list subcommands)
   /stream [on|off]     Toggle streaming AI responses
   /temperature <0-2>   Set AI temperature (default 0.7)
   /thinking <off|l|m|h> Set reasoning effort (off/low/medium/high)
   /timeout <sec>       Set command execution timeout
   /autosave <sec>      Set auto-save interval (>=10s)
   /maxhistory <n>      Set max conversation history length
   /maxtokens <n>       Override max context tokens (>=10000)
   /maxsteps <n>        Set max goal-mode steps
   /subagent-model [m]  Show/set default subagent model (/sam <m>)
   /rootpass <pw>       Set root password ($ROOT_PASS env for su/sudo)

 {bold}Manual Tools{reset}
   /bash <cmd>          Run shell command
   /edit <file> <text>  Append text to file
   /cat <file>          Show file contents
   /ls [path]           List directory
   /find <pattern>      Find files by name pattern
   /grep <pat> <file>   Search in file
   /git                 Git status + diff summary
   /image <path> [txt]  Send image (file or URL) to AI

 {bold}System{reset}
   /sysinfo             System information
   /arch [set <label>]  Show or override architecture detection
   /arch rm <pattern>   Remove a custom arch mapping
   /arch clear          Clear all custom arch mappings
   /procs               Top processes by CPU
   /net                 Network interfaces + routes
   /ports               Open listening ports
   /debug               Toggle debug logging
   /log                 Show debug log
    /memory              Show memory stats and startup memory help
    /memory show         Show editable startup memory Markdown
    /memory edit         Edit startup memory in $EDITOR/notepad

 {bold}Session{reset}
   /save [title]        Save current session
   /load <id>           Load a saved session
   /resume              Interactive session browser
   /sessions            List all sessions
   /session <id>        Show session info
   /delete <id>         Delete a session
   /export [file]       Export session to file
   /history             Show command history
   /clear               Clear conversation history
   /config              Show current config
   /savecfg             Save config to disk
   /loadcfg             Load config from disk
   /usage               Show API usage (OpenRouter)
   /theme               Cycle theme (31 built-in themes)
    /plugins             List loaded plugins
    /soul [show|set|...]  Manage persistent custom rules (soul.md)
    /harness [scan]      Detect external AI agent harness CLIs
     /evolve [on|docs]    Self-repair docs, baseline, tool scan mode
     /extend prompt       Pasteable plugin-generation prompt
    /update [dir]        Git pull + reinstall from project directory
   /help                This help
   /quit                Exit

 {bold}Subagents{reset}
    /delegate <task>     Sync subagent (--provider <name> for different provider)
    /spawn <task>        Async subagent (--provider <name> for different provider)
    /harness delegate    Super subagent with absorbed AI harness tools
   /subagents           List running/completed subagents
   /collect <id>        Get result from a completed async subagent
   /quantum [k]:[v]     View/write shared session context

 {bold}Memory & Skills{reset}
    /remember <text>     Store in long-term memory
    /recall <query>      Search long-term memory
    /forget <id>         Delete a memory
    /memories            List recent long-term memories
    /skill-create        Guided wizard to create a skill
    /skill-list          List all saved skills
    /skill-load <name>   Load a skill into AI context
    /skill-delete <name> Delete a saved skill

 {bold}Automation{reset}
    /auto <text>         Create automation from natural language
    /auto list           List all automations
    /auto show <id>      Show automation details
    /auto delete <id>    Delete an automation
    /auto pause <id>     Pause an automation
    /auto resume <id>    Resume a paused automation

 {bold}Promptshard{reset}
    /shard [show]        Display current promptshard
    /shard deploy        Spawn subagent from promptshard
    /shard complete      Mark promptshard as done
    /shard reset         Reset to active
    /shard set <k>:<v>   Update a promptshard field
    /shard secrets       Manage secrets vault
    """


 

def cmd_arch(args_str, history, cmd_log):
    """Display or override architecture detection."""
    t = T()
    args = args_str.strip()
    if not args:
        detected = Platform.get_arch()
        raw = platform.machine()
        print(f"  {t['bright']}Detected arch:{RST} {detected}")
        print(f"  {t['dim']}Raw machine:{RST} {raw}")
        if Config.CUSTOM_ARCH_MAP:
            print(f"  {t['dim']}Custom mappings:{RST}")
            for pat, label in Config.CUSTOM_ARCH_MAP.items():
                print(f"    {pat} -> {label}")
        print(f"  {t['dim']}Override:{RST} PRISM32_ARCH env var or /arch set <label>")
        return
    sub = args.split(None, 1)
    if sub[0] == 'set' and len(sub) > 1:
        Config.CUSTOM_ARCH_MAP[platform.machine()] = sub[1]
        Config.save_config()
        print(f"  {t['bright']}+ Custom arch mapping:{RST} {platform.machine()} -> {sub[1]}")
    elif sub[0] == 'rm':
        if len(sub) > 1 and sub[1] in Config.CUSTOM_ARCH_MAP:
            del Config.CUSTOM_ARCH_MAP[sub[1]]
            Config.save_config()
            print(f"  {t['bright']}- Removed mapping for:{RST} {sub[1]}")
        else:
            print(f"  {t['warn']}No mapping found for:{RST} {sub[1] if len(sub) > 1 else '(none)'}")
    elif sub[0] == 'clear':
        Config.CUSTOM_ARCH_MAP.clear()
        Config.save_config()
        print(f"  {t['bright']}* All custom arch mappings cleared{RST}")
    else:
        Config.CUSTOM_ARCH_MAP[platform.machine()] = args
        Config.save_config()
        print(f"  {t['bright']}+ Custom arch label:{RST} {platform.machine()} -> {args}")

def cmd_sysinfo():
    display_system_info()

def cmd_procs():
    if Platform.WINDOWS:
        out = run_cmd("tasklist /v")
    elif Platform.LINUX:
        out = run_cmd("ps aux --sort=-%cpu | head -12")
    elif Platform.MACOS:
        out = run_cmd("ps aux -r | head -12")
    elif Platform.BSD:
        out = run_cmd("ps aux -r | head -12")
    elif Platform.AIX:
        out = run_cmd("ps aux -k pcpu | head -12")
    elif Platform.HPUX:
        out = run_cmd("ps -e -o pcpu,pid,user,args | sort -rn | head -12")
    elif Platform.SOLARIS:
        out = run_cmd("ps -eo pcpu,pid,user,args -o pcpu | sort -rn | head -12")
    elif Platform.IRIX:
        out = run_cmd("ps -eo pcpu,pid,user,args | sort -rn | head -12")
    elif Platform.TRU64:
        out = run_cmd("ps aux | head -12")
    else:
        out = run_cmd("ps aux | head -12")
    box("TOP PROCESSES", out, "primary")
    if Platform.WINDOWS:
        mem = run_cmd("wmic OS get FreePhysicalMemory,TotalVisibleMemorySize /Value")
        if not mem.strip():
            mem = "Use Task Manager or systeminfo for detailed memory usage."
    elif Platform.LINUX:
        mem = run_cmd("free -h")
    elif Platform.MACOS:
        mem = run_cmd("vm_stat | head -10")
    elif Platform.BSD:
        mem = run_cmd("vmstat -s | head -10")
    elif Platform.AIX or Platform.HPUX:
        mem = run_cmd("vmstat -s | head -10")
    elif Platform.SOLARIS:
        mem = run_cmd("vmstat -s | head -10")
    elif Platform.IRIX:
        mem = run_cmd("top -n 1 2>/dev/null | head -5")
    elif Platform.TRU64:
        mem = run_cmd("vmstat -P | head -10")
    else:
        mem = f"RAM: {Platform.get_ram()} MB"
    box("MEMORY", mem, "accent")

def cmd_net():
    if Platform.WINDOWS:
        out = run_cmd("ipconfig /all")
        routes = run_cmd("route print")
    elif Platform.LINUX:
        out = run_cmd("ip -br addr 2>/dev/null")
        routes = run_cmd("ip route 2>/dev/null | head -5")
    elif Platform.MACOS or Platform.BSD:
        out = run_cmd("ifconfig -a 2>/dev/null | head -30")
        routes = run_cmd("netstat -rn -f inet 2>/dev/null | head -5")
    elif Platform.AIX:
        out = run_cmd("ifconfig -a 2>/dev/null | head -30")
        routes = run_cmd("netstat -rn 2>/dev/null | head -5")
    elif Platform.HPUX:
        out = run_cmd("ifconfig 2>/dev/null | head -30")
        routes = run_cmd("netstat -rn 2>/dev/null | head -5")
    elif Platform.SOLARIS:
        out = run_cmd("ifconfig -a 2>/dev/null | head -30")
        routes = run_cmd("netstat -rn 2>/dev/null | head -5")
    elif Platform.IRIX:
        out = run_cmd("ifconfig -a 2>/dev/null | head -30")
        routes = run_cmd("netstat -rn 2>/dev/null | head -5")
    elif Platform.TRU64:
        out = run_cmd("ifconfig -a 2>/dev/null | head -30")
        routes = run_cmd("netstat -rn 2>/dev/null | head -5")
    else:
        out = run_cmd("ifconfig 2>/dev/null | head -20")
        routes = ""
    box("INTERFACES", out, "primary")
    if routes:
        box("ROUTES", routes, "dim")

def cmd_ports():
    if Platform.WINDOWS:
        out = run_cmd("netstat -ano")
    elif Platform.LINUX:
        out = run_cmd("ss -tlnp 2>/dev/null | head -20")
        if not out.strip():
            out = run_cmd("netstat -tlnp 2>/dev/null | head -20")
    elif Platform.MACOS:
        out = run_cmd("lsof -iTCP -sTCP:LISTEN -P -n 2>/dev/null | head -20")
    elif Platform.BSD:
        out = run_cmd("sockstat -4 -l 2>/dev/null | head -20")
        if not out.strip():
            out = run_cmd("netstat -an -f inet 2>/dev/null | grep LISTEN | head -20")
    elif Platform.AIX:
        out = run_cmd("netstat -Aan 2>/dev/null | head -20")
    elif Platform.HPUX:
        out = run_cmd("netstat -an 2>/dev/null | grep LISTEN | head -20")
    elif Platform.SOLARIS:
        out = run_cmd("netstat -an 2>/dev/null | grep LISTEN | head -20")
    elif Platform.IRIX:
        out = run_cmd("netstat -an 2>/dev/null | head -20")
    elif Platform.TRU64:
        out = run_cmd("netstat -an 2>/dev/null | head -20")
    else:
        out = run_cmd("netstat -an 2>/dev/null | head -20")
    box("LISTENING PORTS", out, "warn")

def cmd_ls(path="."):
    t = T()
    entries = []
    try:
        for entry in sorted(os.scandir(path), key=lambda e: e.name):
            is_dir = entry.is_dir()
            try:
                sz = entry.stat().st_size
                sz_str = f"{sz / 1024:.1f}K" if sz > 1024 else f"{sz}B"
            except Exception:
                sz_str = "?"
            icon = t['accent'] + "d" + RST if is_dir else "f"
            color = t['accent'] if is_dir else t['primary']
            entries.append(f" {icon} {sz_str:>8}  {color}{entry.name}{RST}")
    except Exception as e:
        entries.append(f" {t['err']}{e}{RST}")
    box(f"LS {path}", "\n".join(entries), "primary")

def cmd_find(pattern):
    if Platform.WINDOWS:
        out = run_cmd(f'dir /s /b "*{pattern}*" 2>nul')
    else:
        out = run_cmd(f"find . -name '*{pattern}*' -type f 2>/dev/null | head -30")
    if not out.strip():
        out = "No files found"
    box(f"FIND: {pattern}", out, "accent")

def cmd_grep(args):
    parts = args.split(None, 1)
    if len(parts) < 2:
        print(f"  Usage: grep <pattern> <file>")
        return
    pat, fp = parts
    if Platform.WINDOWS:
        out = run_cmd(f'findstr /n /i "{pat}" "{fp}" 2>nul')
    else:
        out = run_cmd(f"grep -n -i '{pat}' '{fp}' 2>/dev/null | head -30")
    if not out.strip():
        out = "No matches"
    box(f"GREP: {pat} in {fp}", out, "accent")

def cmd_git():
    t = T()
    status = run_cmd("git status --short 2>/dev/null")
    branch = run_cmd("git branch --show-current 2>/dev/null").strip()
    diff = run_cmd("git diff --stat 2>/dev/null")
    log_out = run_cmd("git log --oneline -5 2>/dev/null")
    lines = [f" Branch: {t['bright']}{branch}{RST}"]
    if status.strip():
        lines.append(f"\n {t['warn']}Modified:{RST}")
        for l in status.split('\n')[:10]:
            lines.append(f"   {l}")
    if diff.strip():
        lines.append(f"\n {t['accent']}Diff stat:{RST}")
        lines.append(f"   {diff.strip()}")
    if log_out.strip():
        lines.append(f"\n {t['dim']}Recent:{RST}")
        for l in log_out.split('\n')[:5]:
            lines.append(f"   {l}")
    if len(lines) < 3:
        lines.append("  Not a git repo or clean state")
    box("GIT", "\n".join(lines), "accent")

def cmd_history(session_history):
    t = T()
    lines = []
    for msg in session_history[-25:]:
        role = msg['role']
        content = msg['content'][:80].replace('\n', ' ')
        if role == 'user':
            lines.append(f" {t['bright']}U>{RST} {content}")
        elif role == 'assistant':
            lines.append(f" {t['primary']}A>{RST} {content}")
    box("HISTORY", "\n".join(lines[-25:]) if lines else "Empty", "dim")

def cmd_export(session_history, filename=None):
    t = T()
    if filename is None:
        filename = f"prism32_session_{datetime.now().strftime('%Y%m%d_%H%M%S')}.txt"
    try:
        with open(filename, 'w', encoding='utf-8') as f:
            f.write(f"Prism32 Session Export - {datetime.now()}\n")
            f.write("=" * 50 + "\n\n")
            for msg in session_history:
                role = msg['role'].upper()
                f.write(f"[{role}]\n{msg['content']}\n\n")
        print(f"  {t['bright']}+ Exported to {filename}{RST}")
    except Exception as e:
        print(f"  {t['err']}! Error: {e}{RST}")

def _open_editor(path):
    editor = os.environ.get("EDITOR")
    if not editor:
        if Platform.WINDOWS:
            editor = os.environ.get("VISUAL") or "notepad"
        else:
            editor = "nano"
    if Platform.WINDOWS and editor.lower() in ("notepad", "notepad.exe"):
        subprocess.run([editor, path])
        return
    subprocess.run([editor, path], check=False)

def cmd_memory(args_str=""):
    t = T()
    parts = args_str.split(None, 1)
    subcmd = parts[0].lower() if parts else ""
    subarg = parts[1] if len(parts) > 1 else ""

    if subcmd in ("show", "startup", "notes"):
        content = read_startup_memory()
        box("STARTUP MEMORY", content if content else "(empty)", "accent")
        print(f"  {t['dim']}File: {STARTUP_MEMORY_FILE}{RST}")
        return
    if subcmd == "path":
        ensure_startup_memory(refresh=False)
        print(f"  Startup memory: {t['bright']}{STARTUP_MEMORY_FILE}{RST}")
        print(f"  JSON memory:    {t['bright']}{MEMORY_FILE}{RST}")
        print(f"  Harness scan:   {t['bright']}{HARNESS_FILE}{RST}")
        return
    if subcmd == "edit":
        ensure_startup_memory(refresh=False)
        try:
            _open_editor(STARTUP_MEMORY_FILE)
            print(f"  {t['bright']}Startup memory edited: {STARTUP_MEMORY_FILE}{RST}")
        except Exception as e:
            print(f"  {t['err']}Edit failed: {e}{RST}")
            print(f"  {t['dim']}Open manually: {STARTUP_MEMORY_FILE}{RST}")
        return
    if subcmd == "append":
        if not subarg:
            print("  Usage: /memory append <note>")
            return
        ensure_startup_memory(refresh=False)
        existing = _safe_read(STARTUP_MEMORY_FILE)
        stamp = datetime.now().strftime("%Y-%m-%d %H:%M")
        _safe_write(STARTUP_MEMORY_FILE, existing.rstrip() + f"\n\n- {stamp}: {subarg}\n")
        print(f"  {t['bright']}+ Startup memory note appended{RST}")
        return
    if subcmd == "refresh":
        ensure_startup_memory(refresh=True)
        refresh_memory_profile(save=True)
        print(f"  {t['bright']}+ Startup memory auto snapshot refreshed{RST}")
        print(f"  {t['dim']}File: {STARTUP_MEMORY_FILE}{RST}")
        return
    if subcmd == "reset":
        _safe_write(STARTUP_MEMORY_FILE, _default_startup_memory_text())
        refresh_memory_profile(save=True)
        print(f"  {t['warn']}Startup memory reset to template.{RST}")
        return
    if subcmd in ("json", "stats", ""):
        mem = load_memory()
        stats = mem.get('command_stats', {})
        errors = mem.get('error_patterns', {})
        sess = mem.get('session_count', 0)
        profile = mem.get('system_profile', {})
        lines = [f" Sessions:    {sess}",
                f" Commands tracked: {len(stats)}",
                f" Error patterns:   {len(errors)}",
                f" Startup file:     {STARTUP_MEMORY_FILE}",
                "", " Startup Profile:"]
        if profile:
            for key in ("os", "arch", "shell", "terminal", "package_manager", "python"):
                if profile.get(key):
                    lines.append(f"   {key:<16} {profile.get(key)}")
        else:
            lines.append("   (run /memory refresh)")
        lines.append("")
        lines.append(" Top Commands:")
        for name, data in sorted(stats.items(), key=lambda x: -x[1]['uses'])[:8]:
            u = data['uses']
            fc = data['failures']
            tt = data['total_time']
            avg = tt / u if u > 0 else 0
            pct = fc / u * 100 if u > 0 else 0
            lines.append(f"   {name:<14} {u:>4}x  fail:{pct:>6.2f}%  avg:{avg:.1f}s")
        if errors:
            lines.append("")
            lines.append(" Recurring Errors:")
            for err, edata in sorted(errors.items(), key=lambda x: -x[1]['count'])[:5]:
                lines.append(f"   {edata['count']}x  {err[:50]}")
        sug = get_memory_suggestions()
        if sug:
            lines.append("")
            lines.append(" Suggestions:")
            for s in sug[:3]:
                lines.append(f"   * {s}")
        lines.append("")
        lines.append(" Commands: /memory show | edit | append <note> | refresh | path | reset | json")
        box("MEMORY", "\n".join(lines), "accent")
        return
    print("  Usage: /memory [show|edit|append <note>|refresh|path|reset|json]")

def cmd_harness(args_str, history, cmd_log):
    t = T()
    parts = args_str.split(None, 1)
    subcmd = parts[0].lower() if parts else "show"
    subarg = parts[1] if len(parts) > 1 else ""
    if subcmd in ("show", "list", ""):
        box("AI HARNESSES", format_harnesses(load_harnesses()), "accent")
        return
    if subcmd == "scan":
        data = ensure_harness_scan(force=True)
        box("AI HARNESSES", format_harnesses(data), "accent")
        return
    if subcmd == "context":
        box("HARNESS CONTEXT", harness_context(), "primary")
        return
    if subcmd == "path":
        print(f"  Harness scan file: {t['bright']}{HARNESS_FILE}{RST}")
        return
    if subcmd == "clear":
        try:
            os.remove(HARNESS_FILE)
            print(f"  {t['bright']}Harness scan cleared. Run /harness scan to rebuild.{RST}")
        except OSError:
            print(f"  {t['dim']}No harness scan file to clear.{RST}")
        return
    if subcmd in ("delegate", "super"):
        if not subarg:
            print("  Usage: /harness delegate <task>")
            return
        ensure_harness_scan(force=False)
        sa = SubAgent(_harness_super_task(subarg))
        sa.run()
        _quantum.put(f"harness_super_{sa.id}_result", sa.result)
        if sa.result:
            ltm_store(sa.result, source=f"harness_super_{sa.id}", summary=f"Harness super subagent: {subarg[:80]}", tags=["subagent", "harness"])
        history.append({"role": "user", "content": f"[Harness super subagent {sa.id} completed]\nTask: {subarg}\nResult: {(sa.result or '')[:2000]}"})
        return
    print("  Usage: /harness [show|scan|context|delegate <task>|path|clear]")

def cmd_evolve(args_str, history, cmd_log):
    global _EVOLVE_MODE
    t = T()
    parts = args_str.split(None, 2)
    subcmd = parts[0].lower() if parts else "on"
    subarg = parts[1] if len(parts) > 1 else ""
    rest = parts[2] if len(parts) > 2 else ""

    if subcmd in ("on", "setup", "start", ""):
        ensure_harness_scan(force=False)
        ensure_startup_memory(refresh=True)
        refresh_memory_profile(save=True)
        ensure_evolve_files(force_baseline=(subcmd == "setup"), refresh_tools=True)
        _EVOLVE_MODE = True
        if history:
            history[0] = {"role": "system", "content": SYSTEM_PROMPT + "\n" + build_context()}
        lines = [
            "Evolve mode is ON.",
            f"Docs:     {EVOLVE_DOC_FILE}",
            f"Tools:    {EVOLVE_TOOL_FILE}",
            f"Baseline: {EVOLVE_BASELINE_FILE}",
            f"Memory:   {STARTUP_MEMORY_FILE}",
            "Commands: /evolve docs | tools | diff | plugin temp <name> | plugin permanent <name> | off",
        ]
        box("EVOLVE", "\n".join(lines), "bright")
        return
    if subcmd == "off":
        _EVOLVE_MODE = False
        if history:
            history[0] = {"role": "system", "content": SYSTEM_PROMPT + "\n" + build_context()}
        print(f"  {t['bright']}Evolve mode is OFF.{RST}")
        return
    if subcmd == "status":
        ensure_evolve_files(refresh_tools=False)
        lines = [
            f"Mode:     {'ON' if _EVOLVE_MODE else 'OFF'}",
            f"Docs:     {EVOLVE_DOC_FILE}",
            f"Tools:    {EVOLVE_TOOL_FILE}",
            f"Baseline: {EVOLVE_BASELINE_FILE}",
            f"Temp plugins: {EVOLVE_TEMP_PLUGIN_DIR}",
        ]
        box("EVOLVE STATUS", "\n".join(lines), "accent")
        return
    if subcmd in ("docs", "doc"):
        ensure_evolve_files(refresh_tools=False)
        text = _safe_read(EVOLVE_DOC_FILE).strip()
        box("EVOLVE DOCS", text[:5000] + ("\n...(truncated)" if len(text) > 5000 else ""), "primary")
        print(f"  {t['dim']}File: {EVOLVE_DOC_FILE}{RST}")
        return
    if subcmd == "context":
        box("EVOLVE CONTEXT", evolve_context(), "primary")
        return
    if subcmd == "tools":
        data = scan_available_tools()
        box("EVOLVE TOOL SCAN", format_tool_scan(data), "accent")
        return
    if subcmd in ("diff", "compare"):
        box("EVOLVE BASELINE DIFF", evolve_diff(), "warn")
        return
    if subcmd == "baseline":
        if subarg in ("refresh", "reset"):
            ensure_evolve_files(force_baseline=True, refresh_tools=False)
            print(f"  {t['warn']}Baseline refreshed from current Prism32 source.{RST}")
        else:
            ensure_evolve_files(refresh_tools=False)
            print(f"  Baseline source: {t['bright']}{EVOLVE_BASELINE_FILE}{RST}")
            print(f"  Baseline config: {t['bright']}{EVOLVE_BASELINE_CONFIG_FILE}{RST}")
            print("  Use /evolve diff to compare current Prism32 with the baseline.")
        return
    if subcmd == "plugin":
        kind = subarg.lower()
        name = rest.strip()
        if kind not in ("temp", "temporary", "permanent", "perm") or not name:
            print("  Usage: /evolve plugin temp <name>")
            print("         /evolve plugin permanent <name>")
            return
        kind = "permanent" if kind in ("permanent", "perm") else "temp"
        path = write_evolve_plugin(kind, name)
        print(f"  {t['bright']}Plugin template written:{RST} {path}")
        if kind == "temp":
            print(f"  {t['dim']}Temporary plugins are scratch files. Copy into {PLUGIN_DIR} to auto-load on startup.{RST}")
        else:
            print(f"  {t['dim']}Restart Prism32 or run /plugins after restart to load it.{RST}")
        return
    print("  Usage: /evolve [on|off|status|docs|context|tools|diff|baseline|plugin]")

def cmd_extend(args_str, history, cmd_log):
    t = T()
    result = extend_with_plugin(args_str, history=history)
    if result == AGENT_CANCELLED_RESPONSE:
        box("STOPPED", agent_cancel_message(), "warn")
        clear_agent_cancel()
        return
    color = "err" if result.startswith("[EXTEND FAILED]") else "accent"
    title = "EXTEND FAILED" if color == "err" else "EXTEND"
    box(title, result, color)

# ── Main Loop ────────────────────────────────────────────────

def main():
    global _shutdown_flag, _LAST_INTERJECT, _INTERJECTION_RESULT
    
    def _on_resize(sig, frame):
        update_terminal_size()
        set_scroll_region()
    if hasattr(signal, 'SIGWINCH'):
        signal.signal(signal.SIGWINCH, _on_resize)
    
    parser = argparse.ArgumentParser(description="Prism32 - Retro AI Terminal Agent")
    parser.add_argument("--model", "-m", help="Override model name")
    parser.add_argument("--api", "-a", help="Override API base URL")
    parser.add_argument("--api-key", "-k", help="Set API key (e.g. OpenRouter)")
    parser.add_argument("--theme", "-t", choices=["phosphor","amber","cyan","vapor","nord","solarized","neon","retro","ice","ocean","sunset","forest","plasma","clear","glass","ghost","smoke","paper","ink","daylight","slate"], help="Color theme")
    parser.add_argument("--turbo", action="store_true", help="Turbo mode: enable live streaming output")
    parser.add_argument("--slow-cpu", action="store_true", help=argparse.SUPPRESS)
    parser.add_argument("--no-boot", action="store_true", help="Skip boot sequence")
    parser.add_argument("--temperature", type=float, help="AI temperature (0.0-2.0)")
    parser.add_argument("--goal", "-g", help="Run in goal mode and exit")
    parser.add_argument("--set-timeout", type=int, help="Set command timeout in seconds and exit")
    parser.add_argument("--update", help="Update prism32 from a URL or file path and exit")
    parser.add_argument("--setup-runtime", action="store_true", help="Refresh startup memory, harness scan, and evolve baseline, then exit")
    parser.add_argument("--harness-scan", action="store_true", help="Scan for external AI harness CLIs, then exit")
    parser.add_argument("--evolve-setup", action="store_true", help="Create evolve docs/baseline/tool scan, then exit")
    args = parser.parse_args()

    # Auto-load saved config, then CLI args override
    Config.load_config()
    if args.model:
        Config.MODEL = args.model
    if args.api:
        Config.API_BASE = args.api
    if args.turbo:
        Config.SLOW_CPU = False
        Config.STREAM = True
    if args.slow_cpu:
        Config.SLOW_CPU = True
        Config.STREAM = False
        Config.AUTO_SAVE_INTERVAL = 0
    if args.api_key:
        Config.API_KEY = args.api_key
    if args.theme:
        Config.THEME = args.theme
        Config.save_config()
    if args.temperature is not None:
        Config.TEMPERATURE = args.temperature
    apply_ansi_compat()
    if args.set_timeout is not None:
        Config.CMD_TIMEOUT = max(1, args.set_timeout)
        Config.save_config()
        print(f"Command timeout set to {Config.CMD_TIMEOUT}s")
        return
    if args.update:
        _do_git_update(args.update)
        return
    if args.setup_runtime or args.harness_scan or args.evolve_setup:
        if args.setup_runtime:
            ensure_startup_memory(refresh=True)
            refresh_memory_profile(save=True)
            data = ensure_harness_scan(force=True)
            ensure_evolve_files(force_baseline=True, refresh_tools=True)
            print(f"Runtime setup complete. Harnesses detected: {len(data.get('installed', []))}")
            print(f"Startup memory: {STARTUP_MEMORY_FILE}")
            print(f"Evolve docs: {EVOLVE_DOC_FILE}")
        else:
            if args.harness_scan:
                data = ensure_harness_scan(force=True)
                print(format_harnesses(data))
            if args.evolve_setup:
                ensure_evolve_files(force_baseline=True, refresh_tools=True)
                print(f"Evolve docs: {EVOLVE_DOC_FILE}")
                print(f"Evolve baseline: {EVOLVE_BASELINE_FILE}")
        return

    t = T()

    print(HIDE + CLS)
    banner()

    load_plugins()
    ensure_startup_memory(refresh=False)
    refresh_memory_profile(save=True)
    ensure_harness_scan(force=False)
    if not args.no_boot:
        boot_sequence()

    t = T()
    print(f" {t['bright']}AI:{RST} {Config.MODEL[:40]}  {t['dim']}|{RST}  {t['primary']}theme:{RST} {Config.THEME}")
    display_system_info()
    print()

    history = [{"role": "system", "content": SYSTEM_PROMPT + "\n" + build_context()}]
    _CURRENT_SESSION_ID = None
    _PluginHooks._history = history
    _PluginHooks._extra_context = []
    _PluginHooks.fire_boot()
    _PluginHooks.start_tick(interval=5)
    _auto_scheduler_thread = threading.Thread(target=_automation_scheduler_loop, daemon=True)
    _auto_scheduler_thread.start()
    cmd_log = []

    if args.goal:
        cmd_goal(args.goal, history, cmd_log)
        print(SHOW)
        return

    print(f"  {t['dim']}Prism32 MDS terminal ready. Type /help for commands. Talk to the AI naturally.{RST}")
    print(f"  {t['dim']}Prism32 by MegaDyne Systems. Use /goal <task> for autonomous multi-step work.{RST}\n")

    # Set up persistent footer using terminal scroll regions
    update_terminal_size()
    set_scroll_region()

    while True:
        if not _footer_reserved:
            set_scroll_region()
        try:
            user_input = read_footer_input(build_status_bar(history=history))
        except (EOFError, KeyboardInterrupt):
            print()
            reset_scroll_region()
            print(f"  {t['bright']}Shutting down...{RST}")
            break

        if not user_input:
            continue
        is_slash = user_input.startswith("/")
        parts = user_input.lstrip("/").split(None, 1) if is_slash else []
        cmd = parts[0].lower() if parts else ""
        args_str = parts[1] if len(parts) > 1 else ""

        if is_slash:
            release_footer_for_output()
        _PluginHooks.fire_message(user_input)
        # Clear interject recall on new input
        _LAST_INTERJECT = ""

        # Echo user message in the scroll region when the footer is active.
        move_to_scroll_bottom()
        print(f" {t['primary']}You:{RST} {user_input}")

        if cmd in ("quit", "exit", "q"):
            save_current_session(history, cmd_log)
            learn_session(len(history), len(cmd_log))
            suggestions = get_memory_suggestions()
            print(f"\n{t['bright']}  == SESSION END =={RST}")
            print(f"  Commands run: {len(cmd_log)}")
            print(f"  Messages: {len(history)}")
            if suggestions:
                print(f"  {t['warn']}Suggestions:{RST}")
                for s in suggestions[:3]:
                    print(f"    {t['dim']}*{RST} {s}")
            print(f"  {t['primary']}Goodbye.   MegaDyne Systems{RST}\n")
            reset_scroll_region()
            break


        # ── Plugin command dispatch ─────────────────────────────
        if is_slash and registry.dispatch(cmd, args_str, history, cmd_log):
            learn_command(cmd, success=True, duration=0)
            _PluginHooks.fire_command(cmd, args_str, None)
            save_current_session(history, cmd_log)
            continue

        # ── Built-in commands ──
        if is_slash:
            learn_command(cmd, success=True, duration=0)
            _PluginHooks.fire_command(cmd, args_str, None)
        if cmd == 'help':
            print(f"\n{CMD_HELP.format(bold=BOLD, reset=RST)}\n")
            continue

        if cmd == 'clear':
            history = [{"role": "system", "content": SYSTEM_PROMPT + "\n" + build_context()}]
            cmd_log.clear()
            print(f"  {t['bright']}+ History cleared{RST}\n")
            continue

        if cmd == 'arch':
            cmd_arch(args_str, history, cmd_log)
            print()
            continue

        if cmd == 'sysinfo':
            cmd_sysinfo()
            print()
            continue

        if cmd == 'procs':
            cmd_procs()
            print()
            continue

        if cmd == 'net':
            cmd_net()
            print()
            continue

        if cmd == 'ports':
            cmd_ports()
            print()
            continue

        if cmd == 'ls':
            cmd_ls(args_str if args_str else ".")
            print()
            continue

        if cmd == 'find':
            if args_str:
                cmd_find(args_str)
            else:
                print(f"  Usage: find <pattern>")
            print()
            continue

        if cmd == 'grep':
            if args_str:
                cmd_grep(args_str)
            else:
                print(f"  Usage: grep <pattern> <file>")
            print()
            continue

        if cmd == 'git':
            cmd_git()
            print()
            continue

        if cmd == 'cat':
            if args_str:
                try:
                    with open(args_str) as f:
                        content = f.read()
                    if len(content) > 3000:
                        print(content[:3000] + f"\n  {t['warn']}... ({len(content)} chars){RST}")
                    else:
                        print(content)
                except Exception as e:
                    print(f"  {t['err']}{e}{RST}")
            else:
                print(f"  Usage: cat <file>")
            print()
            continue

        if cmd == 'bash':
            if args_str:
                print()
                result = run_cmd(args_str)
                cmd_result(args_str, result, "error" not in result.lower()[:50] and "blocked" not in result.lower())
                cmd_log.append(("bash", args_str))
            else:
                print(f"  Usage: bash <command>")
            print()
            continue

        if cmd == 'edit':
            if args_str:
                ep = args_str.split(None, 1)
                if len(ep) == 2:
                    try:
                        with open(ep[0], 'a', encoding='utf-8') as f:
                            f.write(ep[1] + "\n")
                        print(f"  {t['bright']}+ Appended to {ep[0]}{RST}")
                    except Exception as e:
                        print(f"  {t['err']}{e}{RST}")
                else:
                    print(f"  Usage: edit <file> <text>")
            else:
                print(f"  Usage: edit <file> <text>")
            print()
            continue

        if cmd == 'history':
            cmd_history(history)
            print()
            continue

        if cmd == 'export':
            cmd_export(history, args_str if args_str else None)
            print()
            continue

        if cmd == 'save':
            session_id = cmd_session_save(args_str, history, cmd_log)
            print()
            continue

        if cmd == 'resume':
            save_current_session(history, cmd_log)
            data = cmd_session_resume()
            if data:
                history = data.get("history", [])
                cmd_log = data.get("cmd_log", [])
            print()
            continue

        if cmd == 'load':
            if args_str:
                save_current_session(history, cmd_log)
                loaded_history, loaded_cmd_log = cmd_session_load(args_str)
                if loaded_history is not None:
                    history = loaded_history
                    cmd_log = loaded_cmd_log if loaded_cmd_log else []
                    viz.status("Session restored", "success")
            else:
                print(f"  Usage: load <session_id>")
            print()
            continue

        if cmd == 'sessions':
            cmd_session_list()
            print()
            continue

        if cmd in ('providers', 'provider'):
            if args_str:
                parts = args_str.split(None, 1)
                subcmd = parts[0].lower()
                
                if subcmd == 'add':
                    add_parts = args_str.split(None, 4)
                    if len(add_parts) >= 4:
                        name = add_parts[1]
                        api_base = add_parts[2]
                        model = add_parts[3]
                        desc = add_parts[4] if len(add_parts) > 4 else "Custom provider"
                        cmd_provider_add(name, api_base, model, desc)
                    else:
                        # Interactive prompt
                        print(f"\n  {t['bright']}Add a new provider:{RST}")
                        try:
                            name = input(rl_prompt(f"  Provider name: ")).strip()
                            if not name:
                                print(f"  {t['dim']}Cancelled.{RST}")
                            else:
                                api_base = input(rl_prompt(f"  API base URL: ")).strip()
                                if api_base:
                                    model = input(rl_prompt(f"  Model name: ")).strip()
                                    if model:
                                        desc = input(rl_prompt(f"  Description (optional): ")).strip() or "Custom provider"
                                        cmd_provider_add(name, api_base, model, desc)
                                    else:
                                        print(f"  {t['dim']}Cancelled.{RST}")
                                else:
                                    print(f"  {t['dim']}Cancelled.{RST}")
                        except (EOFError, KeyboardInterrupt):
                            print(f"\n  {t['dim']}Cancelled.{RST}")
                elif subcmd in ('rm', 'remove', 'delete'):
                    if len(parts) > 1:
                        cmd_provider_remove(parts[1])
                    else:
                        print(f"  Usage: provider rm <name>")
                elif subcmd == 'api':
                    url = parts[1].strip() if len(parts) > 1 else ""
                    if url:
                        Config.API_BASE = url
                        Config.save_config()
                        print(f"  {t['bright']}+ API set to: {url}{RST}")
                    else:
                        print(f"  Current API: {t['bright']}{Config.API_BASE}{RST}")
                        print(f"  Usage: provider api <url>")
                elif subcmd == 'key':
                    key = parts[1].strip() if len(parts) > 1 else ""
                    if key:
                        Config.API_KEY = key
                        Config.save_config()
                        mask = key[:4] + "..." + key[-4:] if len(key) > 8 else "***"
                        print(f"  {t['bright']}+ API key set: {mask}{RST}")
                    else:
                        has_key = bool(Config.API_KEY)
                        print(f"  API key: {t['bright']}{'<set>' if has_key else '<not set>'}{RST}")
                        print(f"  Usage: provider key <key>")
                elif subcmd in ('list', 'ls'):
                    cmd_provider_list()
                else:
                    # Treat as provider name to switch to
                    cmd_provider_set(subcmd)
            else:
                # No args → interactive provider selector
                provider_names = sorted(PROVIDER_REGISTRY.keys())
                print(f"\n  {t['bright']}Select a provider:{RST}")
                print(f"  {t['dim']}{'─' * 50}{RST}")
                for i, pname in enumerate(provider_names, 1):
                    prov = PROVIDER_REGISTRY[pname]
                    marker = f"{t['bright']}*{RST}" if pname == Config.PROVIDER else " "
                    label = prov.get('display_name', prov.get('name', pname))
                    print(f"  {marker} {t['primary']}{i:>2}.{RST} {label}")
                print(f"  {t['dim']}{'─' * 50}{RST}")
                print(f"  {t['primary']}  c.{RST} Custom (enter your own)")
                print(f"  {t['primary']}  q.{RST} Cancel")
                try:
                    sel = input(rl_prompt(f"  {t['bright']}choice{RST} {t['primary']}>{RST} ")).strip().lower()
                    if sel == 'q' or not sel:
                        print(f"  {t['dim']}Cancelled.{RST}")
                    elif sel == 'c':
                        print(f"\n  {t['bright']}Custom provider:{RST}")
                        cname = input(rl_prompt(f"  Provider name: ")).strip()
                        if cname:
                            cbase = input(rl_prompt(f"  API base URL: ")).strip()
                            if cbase:
                                cmodel = input(rl_prompt(f"  Model name: ")).strip()
                                if cmodel:
                                    cdesc = input(rl_prompt(f"  Description (optional): ")).strip() or "Custom provider"
                                    cmd_provider_add(cname, cbase, cmodel, cdesc)
                                    cmd_provider_set(cname)
                                else:
                                    print(f"  {t['dim']}Cancelled.{RST}")
                            else:
                                print(f"  {t['dim']}Cancelled.{RST}")
                        else:
                            print(f"  {t['dim']}Cancelled.{RST}")
                    else:
                        try:
                            idx = int(sel) - 1
                            if 0 <= idx < len(provider_names):
                                cmd_provider_set(provider_names[idx])
                            else:
                                print(f"  {t['dim']}Invalid choice.{RST}")
                        except ValueError:
                            print(f"  {t['dim']}Invalid choice.{RST}")
                except (EOFError, KeyboardInterrupt):
                    print(f"\n  {t['dim']}Cancelled.{RST}")
            print()
            continue

        if cmd == 'session':
            if args_str:
                cmd_session_info(args_str)
            else:
                print(f"  Usage: session <session_id>")
            print()
            continue

        if cmd == 'delete':
            if args_str:
                cmd_session_delete(args_str)
            else:
                print(f"  Usage: delete <session_id>")
            print()
            continue

        if cmd == 'model':
            if args_str and args_str.lower() not in ('list', 'ls', 'browse', 'select'):
                Config.MODEL = args_str
                print(f"  {t['bright']}+ Model set to: {Config.MODEL}{RST}")
                Config.save_config()
            else:
                cmd_model_list(history, cmd_log)
            continue

        if cmd == 'plugins':
            t = T()
            print(f"\n  {t['bright']}Loaded Plugins:{RST}")
            print(f"  {t['dim']}{'-' * 40}{RST}")
            if _PLUGINS:
                for pname, pmod in _PLUGINS.items():
                    fn = getattr(pmod, '__file__', 'built-in')
                    print(f"  {t['primary']}{pname}{RST}  {t['dim']}{fn}{RST}")
            else:
                print(f"  {t['dim']}No plugins loaded{RST}")
            print(f"  {t['dim']}Plugin directory: {PLUGIN_DIR}{RST}")
            print()
            continue
        if cmd == 'theme':
            themes = list(THEME_REGISTRY.keys())
            idx = (themes.index(Config.THEME) + 1) % len(themes)
            Config.THEME = themes[idx]
            Config.save_config()
            t = T()
            print(f"  {t['bright']}+ Theme: {Config.THEME}{RST}\n")
            continue

        if cmd == 'goal':
            cmd_goal(args_str, history, cmd_log)
            continue

        if cmd == 'autosave':
            if args_str:
                try:
                    val = int(args_str)
                    if val >= 10:
                        Config.AUTO_SAVE_INTERVAL = val
                        Config.save_config()
                        print(f"  {t['bright']}+ Auto-save interval set to: {val}s{RST}")
                    else:
                        print(f"  {t['dim']}Must be >= 10 seconds{RST}")
                except ValueError:
                    print(f"  {t['dim']}Usage: autosave <seconds>{RST}")
            else:
                print(f"  Auto-save: {t['bright']}every {Config.AUTO_SAVE_INTERVAL}s{RST}")
            print()
            continue

        if cmd == 'rootpass':
            if args_str:
                Config.ROOT_PASS = args_str
                Config.save_config()
                print(f"  {t['bright']}+ Root password stored.{RST}")
                print(f"  {t['dim']}  Available as \\$ROOT_PASS in shell commands. AI can use: echo \\\"\\$ROOT_PASS\\\" | su -c (Linux) or su root -c (BSD){RST}")
            else:
                has = bool(Config.ROOT_PASS)
                print(f"  Root password: {t['bright']}{'<set>' if has else '<not set>'}{RST}")
                print(f"  Usage: rootpass <password>")
            print()
            continue

        if cmd == 'agentname':
            if args_str:
                Config.AGENT_NAME = args_str.strip()
                Config.save_config()
                print(f"  {t['bright']}+ Agent name set to: {Config.AGENT_NAME}{RST}")
            else:
                print(f"  Agent name: {t['bright']}{Config.AGENT_NAME}{RST}")
                print(f"  Usage: agentname <name>")
            print()
            continue

        if cmd == 'soul':
            parts = args_str.split(None, 1)
            subcmd = parts[0].lower() if parts else ""
            subarg = parts[1] if len(parts) > 1 else ""
            if subcmd == 'show' or not subcmd:
                content = read_soul()
                print(f"\n {t['bright']}Soul (persistent rules){RST}")
                print(f" {t['dim']}{'─' * 60}{RST}")
                if content:
                    print(f" {content}")
                else:
                    print(f" {t['dim']}(empty){RST}")
                print(f" {t['dim']}{'─' * 60}{RST}")
                print(f" {t['dim']}File: {SOUL_FILE}{RST}")
            elif subcmd == 'set':
                if subarg:
                    write_soul(subarg)
                    print(f"  {t['bright']}+ Soul updated.{RST}")
                else:
                    print(f"  Usage: soul set <rules text>")
            elif subcmd == 'append':
                if subarg:
                    existing = read_soul()
                    write_soul(existing + ("\n" if existing else "") + subarg)
                    print(f"  {t['bright']}+ Soul appended.{RST}")
                else:
                    print(f"  Usage: soul append <rules text>")
            elif subcmd == 'clear':
                write_soul("")
                print(f"  {t['bright']}+ Soul cleared.{RST}")
            elif subcmd == 'edit':
                import tempfile, subprocess
                content = read_soul()
                editor = os.environ.get('EDITOR', 'nano')
                with tempfile.NamedTemporaryFile(mode='w', suffix='.md', delete=False, encoding='utf-8') as f:
                    f.write(content)
                    tmppath = f.name
                try:
                    subprocess.run([editor, tmppath], check=True)
                    with open(tmppath, 'r', encoding='utf-8') as f:
                        new_content = f.read().strip()
                    if new_content != content:
                        write_soul(new_content)
                        print(f"  {t['bright']}+ Soul updated.{RST}")
                    else:
                        print(f"  {t['dim']}(no changes){RST}")
                except Exception as e:
                    print(f"  {t['err']}Edit failed: {e}{RST}")
                finally:
                    try:
                        os.unlink(tmppath)
                    except Exception:
                        pass
            else:
                print(f"  Usage: soul [show|set <text>|append <text>|clear|edit]")
            print()
            # Rebuild history system prompt to include soul changes
            if history:
                history[0] = {"role": "system", "content": SYSTEM_PROMPT + "\n" + build_context()}
            continue

        # ── Promptshard command ──
        if cmd == 'shard':
            parts = args_str.split(None, 1)
            subcmd = parts[0].lower() if parts else ""
            subarg = parts[1] if len(parts) > 1 else ""
            t = T()

            if subcmd == 'show' or not subcmd:
                shard = read_promptshard()
                lines = []
                for k in ('id', 'objective', 'agent', 'model_capabilities',
                          'tools', 'skills', 'status', 'parent'):
                    v = shard.get(k, '')
                    lines.append(f"  {t['bright']}{k}:{RST} {v}")
                if shard.get('prompt'):
                    lines.append(f"  {t['bright']}prompt:{RST}")
                    for pl in shard['prompt'].split('\n'):
                        lines.append(f"    {pl}")
                box("PROMPTSHARD", "\n".join(lines), "accent")
                print()

            elif subcmd == 'deploy':
                shard = read_promptshard()
                if shard.get('status') == 'completed':
                    print(f"  {t['warn']}Promptshard already completed. Use /shard reset to redeploy.{RST}\n")
                    continue
                sa = shard_spawn_agent(shard)
                if sa:
                    print(f"  {t['ok']}+ Deployed promptshard as {sa.id}{RST}")
                    print(f"  {t['dim']}  Objective: {shard.get('objective', '')[:60]}{RST}")
                    print(f"  {t['dim']}  Use /collect {sa.id} when complete.{RST}\n")
                else:
                    print(f"  {t['err']}Failed to deploy promptshard.{RST}\n")

            elif subcmd == 'complete':
                shard = read_promptshard()
                shard_mark_complete(shard.get('id', 'root'), subarg)
                print(f"  {t['ok']}+ Promptshard marked complete.{RST}\n")

            elif subcmd == 'reset':
                shard = read_promptshard()
                shard['status'] = 'active'
                write_promptshard(shard)
                print(f"  {t['ok']}+ Promptshard reset to active.{RST}\n")

            elif subcmd == 'set':
                if ':' in subarg:
                    kv = subarg.split(':', 1)
                    key = kv[0].strip().lower()
                    val = kv[1].strip()
                    shard = read_promptshard()
                    if key in ('id', 'objective', 'agent', 'model_capabilities',
                              'tools', 'skills', 'environment', 'prompt',
                              'secrets_requested', 'status', 'parent'):
                        shard[key] = val
                        write_promptshard(shard)
                        print(f"  {t['ok']}+ Shard {key} updated.{RST}\n")
                    else:
                        print(f"  {t['err']}Unknown field: {key}{RST}\n")
                else:
                    print(f"  Usage: /shard set <field>:<value>\n")

            elif subcmd == 'secrets':
                vault = _secrets_load()
                if subarg:
                    kv = subarg.split(':', 1)
                    if len(kv) == 2:
                        vault[kv[0]] = kv[1]
                        _secrets_save(vault)
                        _quantum.put(f"secret:{kv[0]}", kv[1])
                        print(f"  {t['ok']}+ Secret stored: {kv[0]}{RST}\n")
                    else:
                        print(f"  {t['dim']}Usage: /shard secrets <name>:<value>{RST}\n")
                else:
                    if vault:
                        box("SECRETS VAULT", "\n".join(f"  {k}: {'*' * len(v)}" for k, v in vault.items()), "warn")
                    else:
                        print(f"  {t['dim']}No secrets stored.{RST}")
                    print()

            else:
                print(f"  Usage: /shard [show|deploy|complete|reset|set|secrets]")
                print(f"    show      - display current promptshard")
                print(f"    deploy    - spawn subagent from promptshard")
                print(f"    complete  - mark promptshard as done")
                print(f"    reset     - reset to active")
                print(f"    set k:v   - update a field")
                print(f"    secrets   - manage secrets vault")
                print()
            continue

        # ── Automation command ──
        if cmd == 'auto':
            t = T()
            parts = args_str.split(None, 1)
            subcmd = parts[0].lower() if parts and parts[0] else ""
            subargs = parts[1] if len(parts) > 1 else ""

            if subcmd == 'list' or (not subcmd and not args_str):
                all_autos = automation_list()
                if not all_autos:
                    print(f"  {t['dim']}No automations.{RST}\n")
                    continue
                print(f"\n {t['bright']}AUTOMATIONS{RST}")
                print(f" {t['dim']}{'─'*66}{RST}")
                for a in all_autos:
                    sid = a['id'][:30]
                    desc = a.get('description', '(no desc)')[:40]
                    st = a.get('status', 'unknown')
                    nxt = a.get('next_run')
                    nxt_str = datetime.fromtimestamp(nxt).strftime('%m/%d %H:%M') if nxt else '-'
                    runs = a.get('run_count', 0)
                    st_color = t['ok'] if st == 'active' else (t['warn'] if st == 'paused' else t['dim'])
                    print(f" {t['primary']}{desc}{RST}")
                    print(f"   {t['dim']}{sid}  |  {st_color}{st}{RST}  |  next: {nxt_str}  |  runs: {runs}{RST}")
                print(f" {t['dim']}{'─'*66}{RST}")
                print(f" {t['dim']}Total: {len(all_autos)} automations{RST}\n")
                continue

            if subcmd == 'show':
                auto = automation_load(subargs) if subargs else None
                if not auto:
                    print(f"  {t['err']}Automation not found: {subargs}{RST}\n")
                    continue
                print(f"\n {t['bright']}AUTOMATION DETAIL{RST}")
                print(f" {t['dim']}ID:          {auto['id']}{RST}")
                print(f" {t['primary']}Description: {auto.get('description', '')}{RST}")
                print(f" Task:       {auto.get('task', '')[:80]}")
                print(f" Type:       {auto.get('type', '')}")
                print(f" Status:     {auto.get('status', '')}")
                if auto.get('interval_minutes'):
                    print(f" Interval:   {auto['interval_minutes']} min")
                if auto.get('next_run'):
                    print(f" Next run:   {datetime.fromtimestamp(auto['next_run']).strftime('%Y-%m-%d %H:%M:%S')}")
                if auto.get('last_run'):
                    print(f" Last run:   {datetime.fromtimestamp(auto['last_run']).strftime('%Y-%m-%d %H:%M:%S')}")
                if auto.get('last_success') is not None:
                    print(f" Success:    {auto['last_success']}")
                if auto.get('last_result'):
                    print(f" Result:     {auto['last_result'][:200]}")
                print(f" Runs:       {auto.get('run_count', 0)}")
                print()
                continue

            if subcmd == 'delete':
                if automation_delete(subargs):
                    print(f"  {t['ok']}Automation deleted: {subargs}{RST}\n")
                else:
                    print(f"  {t['err']}Not found: {subargs}{RST}\n")
                continue

            if subcmd == 'pause':
                auto = automation_load(subargs) if subargs else None
                if not auto:
                    print(f"  {t['err']}Automation not found: {subargs}{RST}\n")
                    continue
                auto['status'] = 'paused'
                automation_save(auto)
                print(f"  {t['warn']}Automation paused: {auto.get('description', subargs)}{RST}\n")
                continue

            if subcmd == 'resume':
                auto = automation_load(subargs) if subargs else None
                if not auto:
                    print(f"  {t['err']}Automation not found: {subargs}{RST}\n")
                    continue
                auto['status'] = 'active'
                if auto['type'] == 'oneshot' and auto.get('last_run'):
                    auto['next_run'] = None
                elif auto['type'] == 'scheduled' and auto.get('interval_minutes'):
                    last = auto.get('last_run') or time.time()
                    auto['next_run'] = last + auto['interval_minutes'] * 60
                automation_save(auto)
                print(f"  {t['ok']}Automation resumed: {auto.get('description', subargs)}{RST}\n")
                continue

            if subcmd in ('run', 'execute'):
                auto = automation_load(subargs) if subargs else None
                if not auto:
                    print(f"  {t['err']}Automation not found: {subargs}{RST}\n")
                    continue
                print(f"  {t['bright']}+ Running automation: {auto.get('description', subargs)}{RST}")
                threading.Thread(target=automation_execute, args=(subargs,), daemon=True).start()
                continue

            # If no subcommand matched, treat as natural language creation
            if args_str:
                print(f"  {t['dim']}Parsing automation from natural language...{RST}")
                auto = automation_create_from_nl(args_str)
                if auto:
                    nxt_str = ""
                    if auto.get('next_run'):
                        nxt_str = f" next run: {datetime.fromtimestamp(auto['next_run']).strftime('%Y-%m-%d %H:%M:%S')}"
                    print(f"  {t['ok']}Automation created: {auto.get('description', '')}{RST}")
                    print(f"    {t['dim']}Type: {auto['type']}  |  ID: {auto['id']}{nxt_str}{RST}\n")
                else:
                    print(f"  {t['err']}Failed to parse automation. Try being more specific.{RST}\n")
            else:
                print(f"  Usage: /auto <describe what to automate>")
                print(f"         /auto list")
                print(f"         /auto show <id>")
                print(f"         /auto delete <id>")
                print(f"         /auto pause|resume <id>")
                print(f"         /auto run <id>")
                print(f"  Examples:")
                print(f"    /auto check my email every morning")
                print(f"    /auto write a CNN report in 3 days")
            continue

        if cmd in ('image', 'img'):
            img_content = cmd_image(args_str)
            if img_content:
                history.append({"role": "user", "content": img_content})
            else:
                print()
                continue
            # fall through to AI interaction

        if cmd == 'temperature':
            if args_str:
                try:
                    val = float(args_str)
                    if 0.0 <= val <= 2.0:
                        Config.TEMPERATURE = val
                        Config.save_config()
                        print(f"  {t['bright']}+ Temperature set to: {val}{RST}")
                    else:
                        print(f"  {t['dim']}Temperature must be between 0.0 and 2.0{RST}")
                except ValueError:
                    print(f"  {t['dim']}Usage: temperature <0.0-2.0>{RST}")
            else:
                print(f"  Temperature: {t['bright']}{Config.TEMPERATURE}{RST}")
                print(f"  {t['dim']}Usage: temperature <0.0-2.0>{RST}")
            print()
            continue

        if cmd == 'timeout':
            if args_str:
                try:
                    val = int(args_str)
                    if val >= 1:
                        Config.CMD_TIMEOUT = val
                        Config.save_config()
                        print(f"  {t['bright']}+ Command timeout set to: {val}s{RST}")
                    else:
                        print(f"  {t['dim']}Timeout must be >= 1 second{RST}")
                except ValueError:
                    print(f"  {t['dim']}Usage: timeout <seconds>{RST}")
            else:
                print(f"  Command timeout: {t['bright']}{Config.CMD_TIMEOUT}s{RST}")
                print(f"  {t['dim']}Usage: timeout <seconds>{RST}")
            print()
            continue

        if cmd in ('maxhistory', 'history-limit'):
            if args_str:
                try:
                    val = int(args_str)
                    if val >= 1:
                        Config.MAX_HISTORY = val
                        Config.save_config()
                        print(f"  {t['bright']}+ History limit set to: {val}{RST}")
                    else:
                        print(f"  {t['dim']}Must be >= 1{RST}")
                except ValueError:
                    print(f"  {t['dim']}Usage: maxhistory <count>{RST}")
            else:
                print(f"  History limit: {t['bright']}{Config.MAX_HISTORY}{RST}")
            print()
            continue

        if cmd in ('maxtokens', 'max-tokens'):
            if args_str:
                try:
                    val = int(args_str)
                    if val >= 10000:
                        Config.MAX_CONTEXT_TOKENS = val
                        Config.MAX_RESPONSE_TOKENS = val // 2
                        Config.save_config()
                        print(f"  {t['bright']}+ Max tokens set to: {val}{RST}")
                    else:
                        print(f"  {t['dim']}Must be >= 10000{RST}")
                except ValueError:
                    print(f"  {t['dim']}Usage: maxtokens <tokens>{RST}")
            else:
                ctx = Config.resolve_context_window()
                print(f"  Model:        {t['bright']}{Config.MODEL}{RST}")
                print(f"  Context win:  {t['bright']}{ctx}{RST}")
                print(f"  Max response: {t['bright']}{Config.MAX_RESPONSE_TOKENS}{RST}")
                print(f"  Override:     {t['bright']}{Config.MAX_CONTEXT_TOKENS}{RST}")
            print()
            continue

        if cmd in ('maxsteps', 'max-steps'):
            if args_str:
                try:
                    val = int(args_str)
                    if val >= 1:
                        Config.GOAL_MAX_STEPS = val
                        Config.save_config()
                        print(f"  {t['bright']}+ Goal max steps set to: {val}{RST}")
                    else:
                        print(f"  {t['dim']}Must be >= 1{RST}")
                except ValueError:
                    print(f"  {t['dim']}Usage: maxsteps <count>{RST}")
            else:
                print(f"  Goal max steps: {t['bright']}{Config.GOAL_MAX_STEPS}{RST}")
            print()
            continue

        if cmd == 'thinking':
            if args_str:
                val = args_str.strip().lower()
                if val in ("", "off", "none"):
                    Config.THINKING_EFFORT = ""
                    print(f"  {t['bright']}+ Thinking effort: off{RST}")
                elif val in ("low", "medium", "high"):
                    Config.THINKING_EFFORT = val
                    print(f"  {t['bright']}+ Thinking effort: {val}{RST}")
                else:
                    print(f"  {t['dim']}Usage: thinking <off|low|medium|high>{RST}")
            else:
                current = Config.THINKING_EFFORT if Config.THINKING_EFFORT else "off"
                print(f"  Thinking effort: {t['bright']}{current}{RST}")
                print(f"  {t['dim']}Options: off, low, medium, high{RST}")
            print()
            continue

        if cmd == 'usage':
            if not Config.API_KEY:
                print(f"  {t['warn']}No API key set. Usage tracking requires a provider API key.{RST}")
                print(f"  Set via: {t['bright']}/provider key <key>{RST}")
            elif "openrouter" not in Config.API_BASE.lower():
                print(f"  {t['dim']}Usage tracking is currently only available for OpenRouter.{RST}")
            else:
                try:
                    req = urllib.request.Request(
                        f"{Config.API_BASE.rstrip('/')}/auth/key",
                        headers=build_headers(),
                    )
                    with urllib.request.urlopen(req, timeout=10) as resp:
                        d = json.loads(resp.read().decode()).get("data", {})
                    limit = d.get("limit", 0)
                    remaining = d.get("limit_remaining", 0)
                    used = d.get("usage", 0)
                    daily = d.get("usage_daily", 0)
                    weekly = d.get("usage_weekly", 0)
                    monthly = d.get("usage_monthly", 0)
                    reset = d.get("limit_reset", "unknown")
                    free = d.get("is_free_tier", False)
                    lines = [
                        f"  Limit:     {t['bright']}${limit:.2f}{RST} /{reset}",
                        f"  Used:      {t['warn']}${used:.4f}{RST}",
                        f"  Remaining: {t['bright']}${remaining:.4f}{RST}",
                        f"  Today:     ${daily:.4f}",
                        f"  This week: ${weekly:.4f}",
                        f"  This month: ${monthly:.4f}",
                        f"  Free tier: {'Yes' if free else 'No'}",
                    ]
                    box("OPENROUTER USAGE", "\n".join(lines), "accent")
                except urllib.error.HTTPError as e:
                    body = e.read().decode()[:200]
                    print(f"  {t['err']}Failed to fetch usage: HTTP {e.code}{RST}")
                    print(f"  {t['dim']}{body}{RST}")
                except Exception as e:
                    print(f"  {t['err']}Failed to fetch usage: {e}{RST}")
            print()
            continue

        if cmd == 'update':
            project_dir = args_str.strip() if args_str else ""
            _do_git_update(project_dir if project_dir else None)
            print()
            continue

        if cmd == 'memctx':
            if args_str:
                try:
                    val = int(args_str)
                    Config.MAX_MEMORY_CTX = max(0, val)
                    Config.save_config()
                    print(f"  + Memory context limit: {Config.MAX_MEMORY_CTX} chars")
                except ValueError:
                    print(f"  Usage: memctx <chars (0=disable)>")
            else:
                print(f"  Memory context: {Config.MAX_MEMORY_CTX} chars")
            print()
            continue

        if cmd == 'memory':
            cmd_memory(args_str)
            print()
            if history:
                history[0] = {"role": "system", "content": SYSTEM_PROMPT + "\n" + build_context()}
            continue

        if cmd == 'harness':
            cmd_harness(args_str, history, cmd_log)
            print()
            if history:
                history[0] = {"role": "system", "content": SYSTEM_PROMPT + "\n" + build_context()}
            continue

        if cmd == 'evolve':
            cmd_evolve(args_str, history, cmd_log)
            print()
            continue

        if cmd == 'extend':
            cmd_extend(args_str, history, cmd_log)
            print()
            continue

        # ── Subagent commands ──
        if cmd == 'delegate':
            if args_str:
                task = args_str
                provider = None
                if ' --provider ' in task:
                    parts = task.split(' --provider ', 1)
                    task = parts[0]
                    provider = parts[1].strip().split()[0] if parts[1].strip() else None
                sa = SubAgent(task, provider=provider)
                sa.run()
                _quantum.put(f"subagent_{sa.id}_result", sa.result)
                if sa.result:
                    ltm_store(sa.result, source=f"subagent_{sa.id}", summary=f"Subagent result: {sa.task[:80]}", tags=["subagent", "auto"])
                history.append({"role": "user",
                    "content": f"[Subagent {sa.id} completed]\nTask: {args_str}\nResult: {(sa.result or '')[:2000]}"})
            else:
                print(f"  Usage: /delegate <task description>")
            continue

        if cmd == 'spawn':
            if args_str:
                task = args_str
                provider = None
                if ' --provider ' in task:
                    parts = task.split(' --provider ', 1)
                    task = parts[0]
                    provider = parts[1].strip().split()[0] if parts[1].strip() else None
                sa = SubAgent(task, provider=provider)
                sa.run_async()
                t = T()
                print(f"  {t['warn']}╭─ SPAWNED [{sa.id}] ASYNC ─────────────────{RST}")
                print(f"  {t['warn']}│{RST}  {t['bright']}Task:{RST} {task[:80]}")
                prov_info = f"  {t['dim']}Provider:{RST} {provider}" if provider else ""
                model_str = provider if provider else Config.MODEL
                print(f"  {t['warn']}│{RST}  {t['dim']}Model:{RST} {model_str[:40]}{prov_info}")
                print(f"  {t['warn']}╰{'─' * 50}{RST}")
                print(f"  {t['dim']}Use /collect {sa.id} to retrieve results.{RST}")
                _quantum.put(f"subagent_{sa.id}_spawned", True)
            else:
                print(f"  Usage: /spawn <task description>")
            continue

        if cmd == 'subagents':
            with _subagent_lock:
                if not _SUBAGENTS:
                    print(f"  No subagents.")
                else:
                    lines = []
                    for sid, sa in list(_SUBAGENTS.items()):
                        lines.append(f"  {sa.status_str()}")
                    box("SUBAGENTS", "\n".join(lines), "primary" if any(not s.done for s in _SUBAGENTS.values()) else "bright")
                    # Clean up done agents
                    for sid in list(_SUBAGENTS.keys()):
                        if _SUBAGENTS[sid].done and _SUBAGENTS[sid]._thread and not _SUBAGENTS[sid]._thread.is_alive():
                            del _SUBAGENTS[sid]
            print()
            continue

        if cmd == 'collect':
            sid = args_str.strip()
            if not sid:
                print(f"  Usage: /collect <subagent_id>")
                continue
            with _subagent_lock:
                sa = _SUBAGENTS.get(sid)
            if not sa:
                print(f"  No subagent with id '{sid}'")
                continue
            if not sa.done:
                print(f"  Subagent {sid} still running (step {sa._step}/{sa.max_steps}).")
                print(f"  Use /subagents for status.")
                continue
            t = T()
            result_text = (sa.result or sa.error or '?')[:2000]
            box(f"SUBAGENT {sid} RESULT", result_text, "primary")
            # Store result in quantum for other agents
            _quantum.put(f"subagent:{sid}:result", sa.result or sa.error or "")
            _quantum.put(f"subagent:{sid}:task", sa.task)
            history.append({"role": "user",
                "content": f"[Collected subagent {sid}]\n" + (sa.result or sa.error or '?')[:2000]})
            with _subagent_lock:
                if sid in _SUBAGENTS:
                    del _SUBAGENTS[sid]
            continue

        if cmd == 'quantum':
            parts = args_str.split(None, 1)
            if not args_str:
                qd = _quantum.items()
                if not qd:
                    print(f"  Quantum context is empty.")
                else:
                    lines = [f"  {k}: {str(v)[:120]}" for k, v in qd.items()]
                    box("QUANTUM CONTEXT", "\n".join(lines), "accent")
            elif len(parts) >= 1 and ':' in args_str:
                kv = args_str.split(':', 1)
                key = kv[0].strip()
                val = kv[1].strip() if len(kv) > 1 else ""
                if val:
                    _quantum.put(key, val)
                    print(f"  Quantum: {key} = {val[:80]}")
                else:
                    v = _quantum.get(key)
                    print(f"  Quantum: {key} = {str(v)[:80]}" if v is not None else f"  Key '{key}' not found")
            else:
                print(f"  Usage: /quantum                    (view all)")
                print(f"        /quantum <key>:<value>      (set)")
                print(f"        /quantum <key>:             (get)")
            print()
            continue

        # ── Long-Term Memory commands ──
        if cmd == 'remember':
            if args_str:
                rest = args_str
                tags = []
                if ' --tag ' in rest:
                    parts = rest.split(' --tag ', 1)
                    rest = parts[0]
                    tags = [t.strip() for t in parts[1].split(',') if t.strip()]
                mid = ltm_store(rest, source="user", tags=tags)
                print(f"  Remembered as mem_{mid:07d} ({len(rest)} chars)")
            else:
                print(f"  Usage: /remember <text> [--tag tag1,tag2]")
            print()
            continue

        if cmd == 'recall':
            if args_str:
                results = ltm_search(args_str)
                if not results:
                    print(f"  No memories matching '{args_str}'")
                else:
                    lines = []
                    for r in results:
                        lines.append(f"  mem_{int(r['id']):07d} [{r['score']}] {r['summary'][:80]}")
                        lines.append(f"       {r['timestamp'][:19]}  src:{r['source'][:20]}")
                        lines.append(f"       {r['content'][:100]}")
                        lines.append("")
                    box(f"LTM SEARCH: {args_str}", "\n".join(lines), "accent")
            else:
                print(f"  Usage: /recall <query>")
            print()
            continue

        if cmd == 'forget':
            mid_str = args_str.strip()
            if mid_str:
                try:
                    mid = int(mid_str.replace('mem_', ''))
                    if ltm_delete(mid):
                        print(f"  Deleted mem_{mid:07d}")
                    else:
                        print(f"  mem_{mid:07d} not found")
                except ValueError:
                    print(f"  Usage: /forget <id>  (e.g. /forget 42 or /forget mem_0000042)")
            else:
                print(f"  Usage: /forget <id>")
            print()
            continue

        if cmd == 'memories':
            results = ltm_list(25)
            if not results:
                print(f"  No long-term memories stored yet.")
            else:
                total = len(_load_ltm_index().get("memories", {}))
                lines = [f"  Total: {total}/{LONGTERM_MAX} entries"]
                for r in results:
                    lines.append(f"  mem_{int(r['id']):07d}  {r['timestamp'][:19]}  {r['source'][:15]}")
                    lines.append(f"       {r['summary'][:100]}")
                box("LONG-TERM MEMORIES", "\n".join(lines), "primary")
            print()
            continue

        # ── Skill commands ──
        if cmd == 'skill-create':
            _prompt_skill_wizard()
            continue

        if cmd == 'skill-list':
            skills = skill_list()
            if not skills:
                print(f"  No skills yet. Create one with /skill-create")
            else:
                lines = []
                for s in skills:
                    wf_count = len(s.get("workflow", []))
                    wf_info = f", {wf_count} workflow steps" if wf_count else ""
                    lines.append(f"  {t['primary']}{s['name']:<20}{RST}  {t['dim']}{s.get('description','')[:45]}{wf_info}{RST}")
                box("SKILLS", "\n".join(lines), "bright")
            print()
            continue

        if cmd == 'skill-load':
            name = args_str.strip()
            if not name:
                print(f"  Usage: /skill-load <name>")
                print(f"  See available: /skill-list")
            elif skill_inject(name):
                # Rebuild history system prompt to include skill context
                history[0] = {"role": "system", "content": SYSTEM_PROMPT + "\n" + build_context()}
                print(f"  Skill '{name}' loaded into context.")
                skill = skill_load(name)
                wf = skill.get("workflow", []) if skill else []
                if wf:
                    print(f"  Workflow steps:")
                    for s in wf:
                        cmd_hint = f"  [{s.get('command','manual')}]" if s.get("command") else ""
                        print(f"    {s['step']}. {s['action']}{cmd_hint}")
            else:
                print(f"  Skill '{name}' not found.")
            print()
            continue

        if cmd == 'skill-delete':
            name = args_str.strip()
            if not name:
                print(f"  Usage: /skill-delete <name>")
            elif skill_delete(name):
                print(f"  Skill '{name}' deleted.")
            else:
                print(f"  Skill '{name}' not found.")
            print()
            continue

        if cmd in ('subagent-model', 'sam'):
            if not args_str:
                current = Config.SUBAGENT_MODEL or f"{t['dim']}(same as main: {Config.MODEL}){RST}"
                print(f"  Current subagent model: {current}\n")
                try:
                    models = fetch_models()
                except Exception as e:
                    print(f"  {t['err']}Could not fetch models: {e}{RST}")
                    print()
                    continue
                if not models:
                    print(f"  No models available.")
                    print()
                    continue
                models.sort(key=lambda m: m["id"].lower())
                page_size = 30
                page = 0
                search_term = ""
                while True:
                    filtered = [m for m in models if search_term.lower() in m["id"].lower()] if search_term else models
                    tpages = max(1, (len(filtered) + page_size - 1) // page_size)
                    start, end = page * page_size, min(page * page_size + page_size, len(filtered))
                    page_models = filtered[start:end]
                    print(f" {t['bright']}SELECT SUBAGENT MODEL{RST}  {t['dim']}(page {page+1}/{tpages} | {len(filtered)} total){RST}")
                    print(f" {t['dim']}{'─' * 72}{RST}")
                    for i, m in enumerate(page_models, 1):
                        marker = " ←" if m["id"] == Config.SUBAGENT_MODEL else ""
                        pricing = _pricing_str(m.get("pricing"))
                        print(f"  {t['primary']}{start + i:>3}.{RST} {m['id'][:50]}{pricing}{t['bright']}{marker}{RST}")
                    print(f" {t['dim']}{'─' * 72}{RST}")
                    print(f"  {t['dim']}n next  p prev  /text{RST}{t['bright']} search  q{RST}{t['dim']}uit{RST}{t['bright']}  <number>{RST}{t['dim']} select  clear{RST}{t['dim']} (use main){RST}")
                    try:
                        sel = input(rl_prompt(f" {t['bright']}sam{RST} {t['primary']}>{RST} ")).strip().lower()
                    except (EOFError, KeyboardInterrupt):
                        print(); break
                    if not sel: continue
                    if sel == 'q': break
                    if sel == 'n':
                        if page < tpages - 1: page += 1
                        continue
                    if sel == 'p':
                        if page > 0: page -= 1
                        continue
                    if sel == 'clear':
                        Config.SUBAGENT_MODEL = ""
                        Config.save_config()
                        print(f"  Subagent model cleared (will use main model).")
                        break
                    if sel.startswith('/'):
                        search_term = sel[1:]
                        page = 0
                        continue
                    try:
                        num = int(sel) - 1
                        if 0 <= num < len(filtered):
                            Config.SUBAGENT_MODEL = filtered[num]["id"]
                            Config.save_config()
                            print(f"  Subagent model set to: {filtered[num]['id']}")
                            break
                    except ValueError:
                        pass
            else:
                Config.SUBAGENT_MODEL = args_str.strip()
                Config.save_config()
                print(f"  Subagent model set to: {args_str.strip()}")
            print()
            continue

        if cmd == 'config':
            lines = [
                f" Agent name: {Config.AGENT_NAME}",
                 f" Model:      {Config.MODEL}",
                f" API:        {Config.API_BASE}",
                f" API Key:    {'<set>' if Config.API_KEY else '<not set>'}",
                f" Theme:      {Config.THEME}",
                f" Provider:   {Config.PROVIDER}",
                f" Temp:       {Config.TEMPERATURE}",
                f" Max tokens: {Config.MAX_RESPONSE_TOKENS}",
                f" Context:     {t['dim']}{Config.resolve_context_window()}{RST}",
                f" History:    {Config.MAX_HISTORY}",
                f" Timeout:    {Config.CMD_TIMEOUT}s",
                f" Goal steps: {Config.GOAL_MAX_STEPS}",
                f" Autosave:   {Config.AUTO_SAVE_INTERVAL}s",
                f" Thinking:   {Config.THINKING_EFFORT if Config.THINKING_EFFORT else 'off'}",
                f" Debug:      {'ON' if Config.DEBUG else 'OFF'}",
                f" Subagent model: {Config.SUBAGENT_MODEL or '(same as main)'}",
                f" Root pass:   {'<set>' if Config.ROOT_PASS else '<not set>'}",
            ]
            box("CONFIG", "\n".join(lines), "accent")
            print()
            continue

        if cmd == 'savecfg':
            Config.save_config()
            debug_log("Config saved", "INFO")
            viz.status(f"Config saved to {Config.CONFIG_FILE}", "save")
            print()
            continue

        if cmd == 'loadcfg':
            Config.load_config()
            debug_log("Config loaded", "INFO")
            viz.status(f"Config loaded from {Config.CONFIG_FILE}", "load")
            print()
            continue

        if cmd == 'debug':
            if Config.DEBUG:
                debug_disable()
            else:
                debug_enable()
            print()
            continue

        if cmd == 'log':
            if os.path.exists(LOG_FILE):
                try:
                    with open(LOG_FILE) as f:
                        lines = f.readlines()
                    box("DEBUG LOG", "".join(lines[-30:]) if lines else "Empty", "dim")
                except Exception as e:
                    print(f"  {t['err']}{e}{RST}")
            else:
                print(f"  {t['dim']}No debug log yet. Enable with: debug{RST}")
            print()
            continue

        if cmd == 'stream':
            if args_str:
                if args_str.lower() in ('on', 'true', '1'):
                    Config.STREAM = True
                    print(f"  {T()['bright']}Stream: ON{RST}")
                elif args_str.lower() in ('off', 'false', '0'):
                    Config.STREAM = False
                    print(f"  {T()['bright']}Stream: OFF{RST}")
                else:
                    history.append({"role": "user", "content": args_str})
                    if Config.STREAM:
                        resp = ask_ai(history)
                    else:
                        resp = ask_ai(history, stream=False)
                    commands = extract_blocks(resp, 'execute')
                    if commands:
                        for c in commands:
                            c = c.strip()
                            print(f"\n  {T()['warn']}>{c}{RST}")
                            plugin_result = _try_plugin_cmd(c, history=history)
                            if plugin_result is not None:
                                result = plugin_result.strip()
                            else:
                                result = run_cmd(c)
                            success = _cmd_succeeded(result)
                            cmd_result(c, result, success)
                            cmd_log.append(("ai", c))
                            history.append({"role": "assistant", "content": f"Ran: {c}\n{result[:800]}"})
                            history.append({"role": "user", "content": "Output above. Continue."})
                    else:
                        history.append({"role": "assistant", "content": resp})
                    if len(history) > Config.MAX_HISTORY:
                        history = [history[0]] + history[-(Config.MAX_HISTORY - 1):]
                Config.save_config()
            else:
                print(f"  Stream: {T()['bright']}{('ON' if Config.STREAM else 'OFF')}{RST}")
            print()
            continue
        # ── Default AI interaction ──
        if not (history and isinstance(history[-1].get("content"), list)):
            history.append({"role": "user", "content": user_input})
        max_iter = 9999

        for iteration in range(max_iter):
            spin = None
            try:
                if Config.STREAM:
                    if not _footer_reserved:
                        set_scroll_region()
                    draw_footer(build_status_bar(history=history))
                    move_to_scroll_bottom()
                    _interjection_start()
                    resp = ask_ai(history)
                    print()
                else:
                    if not _footer_reserved:
                        set_scroll_region()
                    draw_footer(build_status_bar(history=history, include_indicator=False), spin_char=activity_vector(history=history, busy=True))
                    resp = ask_ai_cancelable(history, history=history)
                    release_footer_for_output()
            except KeyboardInterrupt:
                resp = None
            finally:
                if spin is not None:
                    spin.stop()
                    release_footer_for_output()
                _interjection_stop()

            # Handle interjection (user typed while AI was streaming)
            if _INTERJECTION_RESULT is not None:
                inj = _INTERJECTION_RESULT
                _INTERJECTION_RESULT = None
                clear_agent_cancel()
                if resp:
                    history.append({"role": "assistant", "content": resp + "\n\n[assistant response interrupted by user interjection]"})
                history.append({"role": "user", "content": inj})
                move_to_scroll_bottom()
                print(f" {T()['primary']}You:{RST} {inj}")
                save_current_session(history, cmd_log)
                continue
            if resp == AGENT_CANCELLED_RESPONSE or agent_cancel_requested():
                msg = agent_cancel_message()
                clear_agent_cancel()
                box("STOPPED", msg, "warn")
                break
            if not resp or resp.startswith('['):
                box("AI ERROR", resp or "No response", "err")
                break

            resp, asked = handle_ask_blocks(resp, history, return_asked=True)
            commands = extract_blocks(resp, 'execute')
            clean = clean_response(resp)

            if asked and not commands and not clean:
                save_current_session(history, cmd_log)
                continue

            if commands:
                if clean and iteration == 0 and not Config.STREAM:
                    box("AI ANALYSIS", clean, "accent")
                if resp.strip():
                    history.append({"role": "assistant", "content": resp})

                command_cancelled = False
                for c in commands:
                    c = c.strip()
                    viz.tool_call("execute", c)
                    plugin_result = _try_plugin_cmd(c, history=history)
                    if plugin_result is not None:
                        result = plugin_result.strip()
                    else:
                        result = run_cmd(c)
                    command_cancelled = agent_cancel_requested() or (result or "").startswith("[CANCELLED]")
                    success = _cmd_succeeded(result)
                    viz.tool_result(success, result[:100])
                    cmd_result(c, result, success)
                    cmd_log.append(("ai", c))

                    exec_msg = f"Executed: {c}\nResult:\n{result[:1500]}"
                    continuation = "Command output above. Continue with your task or give final answer."
                    if exec_msg.strip():
                        history.append({"role": "user", "content": f"{exec_msg}\n\n{continuation}"})
                    else:
                        history.append({"role": "user", "content": continuation})
                    if command_cancelled:
                        msg = agent_cancel_message()
                        clear_agent_cancel()
                        box("STOPPED", msg, "warn")
                        break
                if command_cancelled:
                    break
            else:
                if not clean:
                    box("AI ERROR", "Empty response", "err")
                    break
                if not Config.STREAM:
                    t2 = T()
                    print(f" {t2['primary']}<{Config.AGENT_NAME}>:{RST} {clean}")
                print()
                history.append({"role": "assistant", "content": resp})
                break

        # Apply both constraints: trim to max_history count, then to token budget
        if len(history) > Config.MAX_HISTORY:
            history = [history[0]] + history[-(Config.MAX_HISTORY - 1):]
        history = trim_history(history, 220000)

        # Save session after each interaction
        save_current_session(history, cmd_log)

        sys.stdout.write("\r\033[K")
        sys.stdout.flush()

    reset_scroll_region()
    print(SHOW)

# ── Model Selector ──────────────────────────────────────────

_IS_OPENROUTER = None
def build_headers(extra=None):
    global _IS_OPENROUTER
    _IS_OPENROUTER = "openrouter" in Config.API_BASE.lower()
    h = {"Content-Type": "application/json"}
    if Config.API_KEY:
        h["Authorization"] = f"Bearer {Config.API_KEY}"
    # OpenRouter-specific headers for rankings
    if _IS_OPENROUTER:
        h["HTTP-Referer"] = "https://github.com/prism32"
        h["X-Title"] = "Prism32"
    if extra:
        h.update(extra)
    return h

def fetch_models():
    """Fetch available models from the current provider's /v1/models endpoint.
    
    Returns a list of model IDs/names, or empty list on failure.
    """
    try:
        req = urllib.request.Request(
            f"{Config.API_BASE.rstrip('/').rstrip('v1').rstrip('/')}/v1/models",
            headers=build_headers(),
        )
        with urllib.request.urlopen(req, timeout=15) as resp:
            data = json.loads(resp.read().decode())
    except Exception:
        return []

    models = []
    if "data" in data and isinstance(data["data"], list):
        for m in data["data"]:
            if m.get("id"):
                pricing = m.get("pricing") or None
                models.append({"id": m["id"], "pricing": pricing})
    elif "models" in data and isinstance(data["models"], list):
        models = [{"id": m.get("name") or m.get("id") or "", "pricing": None} for m in data["models"]]
    elif isinstance(data, list):
        models = [{"id": m.get("name") or m.get("id") or "", "pricing": None} for m in data]
    elif data.get("id"):
        models = [{"id": data["id"], "pricing": None}]

    return [m for m in models if m.get("id")]

def _pricing_str(pricing):
    if not pricing or not isinstance(pricing, dict):
        return ""
    prompt = pricing.get("prompt", "")
    completion = pricing.get("completion", "")
    if not prompt and not completion:
        return ""
    def _fmt(val):
        if not val:
            return "?"
        try:
            v = float(val)
            if v == 0:
                return "free"
            if 0 < v < 0.001:
                v = v * 1_000_000
            if v >= 1000:
                return f"${v:.0f}"
            if v >= 1:
                return f"${v:.2f}"
            if v >= 0.01:
                return f"${v:.4f}"
            return f"${v:.6f}"
        except (ValueError, TypeError):
            return f"${val}"
    return f"  {_fmt(prompt)}/{_fmt(completion)}/M"

def cmd_model_list(history=None, cmd_log=None, provider=None):
    """Interactive model browser. Fetches models, paginates, lets user pick.
    If provider is given, temporarily switches to that provider for browsing."""
    t = T()
    _saved = {}
    if provider and provider in PROVIDER_REGISTRY:
        _saved = {"base": Config.API_BASE, "model": Config.MODEL, "key": Config.API_KEY}
        Config.API_BASE = PROVIDER_REGISTRY[provider]["api_base"]
        if PROVIDER_REGISTRY[provider].get("default_key"):
            Config.API_KEY = PROVIDER_REGISTRY[provider]["default_key"]
    
    try:
        models = fetch_models()
    except Exception as e:
        if _saved:
            Config.API_BASE = _saved["base"]
            Config.MODEL = _saved["model"]
            Config.API_KEY = _saved["key"]
        viz.status(f"Failed to fetch models: {e}", "error")
        return

    if not models:
        if "openrouter" in Config.API_BASE.lower() and not Config.API_KEY:
            print(f"\n  {t['warn']}OpenRouter requires an API key.{RST}")
            print(f"  Set it: {t['bright']}/provider key sk-or-v1-...{RST}")
            print(f"  Or:     {t['bright']}--api-key sk-or-v1-...{RST}")
        else:
            viz.status("No models returned by API. Check connection or API key.", "warning")
        return

    models.sort(key=lambda m: m["id"].lower())
    page_size = 30
    total_pages = max(1, (len(models) + page_size - 1) // page_size)
    page = 0
    search_term = ""

    while True:
        start = page * page_size
        end = min(start + page_size, len(models))
        page_models = models[start:end]

        if search_term:
            filtered = [m for m in models if search_term.lower() in m["id"].lower()]
            filtered_start = page * page_size
            filtered_end = min(filtered_start + page_size, len(filtered))
            page_models = filtered[filtered_start:filtered_end]
            total_pages = max(1, (len(filtered) + page_size - 1) // page_size)
        else:
            filtered = models
            total_pages = max(1, (len(models) + page_size - 1) // page_size)

        prov_name = provider if provider else Config.PROVIDER
        print(f"\n {t['bright']}MODELS -- {prov_name}{RST}  {t['dim']}(page {page+1}/{total_pages} | {len(filtered)} total){RST}")
        print(f" {t['dim']}{'─' * 72}{RST}")

        for i, m in enumerate(page_models, 1):
            is_current = " ←" if m["id"] == Config.MODEL else ""
            pricing = _pricing_str(m.get("pricing"))
            print(f"  {t['primary']}{start + i:>3}.{RST} {m['id'][:50]}{pricing}{t['bright']}{is_current}{RST}")

        print(f" {t['dim']}{'─' * 72}{RST}")
        print(f"  {t['dim']}n next  p prev  /text{RST}{t['bright']} search  q{RST}{t['dim']}uit{RST}{t['bright']}  <number>{RST}{t['dim']} select  clear{RST}{t['dim']} (default){RST}")
        thinking_tag = f" {t['dim']}{Config.THINKING_EFFORT}{RST}" if Config.THINKING_EFFORT else ""
        try:
            sel = input(rl_prompt(f" {t['bright']}model{RST}{thinking_tag} {t['primary']}>{RST} ")).strip().lower()
        except (EOFError, KeyboardInterrupt):
            print()
            break

        if not sel:
            continue
        if sel == 'q':
            if _saved:
                Config.API_BASE = _saved["base"]
                Config.MODEL = _saved["model"]
                Config.API_KEY = _saved["key"]
            break
        if sel == 'n':
            if page < total_pages - 1:
                page += 1
            continue
        if sel == 'p':
            if page > 0:
                page -= 1
            continue
        if sel.startswith('/'):
            search_term = sel[1:]
            page = 0
            continue
        if sel == 'clear':
            if Config.PROVIDER in PROVIDER_REGISTRY:
                Config.MODEL = PROVIDER_REGISTRY[Config.PROVIDER].get("model", Config.MODEL)
            Config.save_config()
            print(f"  {t['bright']}+ Model reset to provider default: {Config.MODEL}{RST}")
            break
        if sel == '*':
            search_term = ""
            page = 0
            continue

        try:
            idx = int(sel) - 1
            if 0 <= idx < len(filtered):
                chosen = filtered[idx]["id"]
                Config.MODEL = chosen
                if _saved:
                    Config.PROVIDER = provider
                    Config.API_KEY = _saved["key"]
                    Config.save_config()
                Config.save_config()
                print(f"  {t['bright']}+ Model set to: {Config.MODEL}{RST}")
                if _saved:
                    print(f"  {t['dim']}  Switched provider to: {provider}{RST}")
                break
            else:
                viz.status("Invalid number", "warning")
        except ValueError:
            pass

# ── Provider Commands ────────────────────────────────────────────

def cmd_provider_list():
    """List all available providers."""
    t = T()
    print(f"\n {t['bright']}MODEL PROVIDERS{RST}")
    print(f" {t['dim']}{'─' * 60}{RST}")
    
    for key, prov in PROVIDER_REGISTRY.items():
        marker = f"{t['bright']}*{RST}" if key == Config.PROVIDER else " "
        print(f" {marker} {t['primary']}{key:<12}{RST} {t['dim']}{prov.get('display_name', prov.get('name', ''))}{RST}")
        print(f"   {t['dim']}{prov.get('description', '')}{RST}")
        print(f"   {t['dim']}API: {prov.get('api_base', '')}{RST}")
        print(f"   {t['dim']}Model: {prov.get('model', '')[:40]}{RST}")
        print()
    
    print(f" {t['dim']}{'─' * 60}{RST}")
    print(f" {t['dim']}* = current provider{RST}")

def cmd_provider_set(provider_name):
    """Switch to a different provider."""
    t = T()
    
    if provider_name not in PROVIDER_REGISTRY:
        viz.status(f"Unknown provider: {provider_name}", "error")
        print(f"   {t['dim']}Use 'providers' to see available options{RST}")
        return False
    
    prov = PROVIDER_REGISTRY[provider_name]
    Config.PROVIDER = provider_name
    Config.API_BASE = prov["api_base"]
    Config.MODEL = prov["model"]
    Config.save_config()
    
    viz.status(f"Switched to: {prov.get('display_name', prov.get('name', ''))}", "success")
    print(f"   {t['dim']}API: {Config.API_BASE}{RST}")
    print(f"   {t['dim']}Model: {Config.MODEL}{RST}")
    
    needs_key = not Config.API_KEY and not prov.get("default_key")
    if needs_key:
        print(f"   {t['warn']}This provider may require an API key.{RST}")
        try:
            key = input(rl_prompt(f"   API key (or Enter to skip): ")).strip()
            if key:
                Config.API_KEY = key
                Config.save_config()
                print(f"   {t['bright']}+ API key set.{RST}")
        except (EOFError, KeyboardInterrupt):
            print()
    return True

def cmd_provider_add(name, api_base, model, description="Custom provider"):
    """Add a custom provider."""
    t = T()
    PROVIDER_REGISTRY[name] = {
        "name": name.replace("_", " ").title(),
        "api_base": api_base,
        "model": model,
        "description": description
    }
    viz.status(f"Added provider: {name}", "success")

def cmd_provider_remove(name):
    """Remove a provider."""
    t = T()
    if name in PROVIDER_REGISTRY:
        if name == "local":
            viz.status("Cannot remove built-in 'local' provider", "error")
            return
        del PROVIDER_REGISTRY[name]
        viz.status(f"Removed provider: {name}", "success")
    else:
        viz.status(f"Provider not found: {name}", "error")

# ── Image / Multimodal Input ──────────────────────────────────

def cmd_image(args_str):
    """Load an image from file or URL and return multimodal content list.
    Returns None on error, or a content list suitable for OpenAI API messages."""
    if not args_str:
        t = T()
        print(f"  {t['dim']}Usage: image <file_or_url> [prompt text]{RST}")
        print(f"  {t['dim']}  Loads an image and sends it to the AI with optional prompt.{RST}")
        return None
    
    parts = args_str.split(None, 1)
    path = parts[0]
    prompt = parts[1] if len(parts) > 1 else "What's in this image?"
    t = T()
    
    try:
        if path.startswith(('http://', 'https://')):
            print(f"  {t['dim']}Downloading image...{RST}")
            with urllib.request.urlopen(path, timeout=30) as r:
                data = r.read()
            ext = os.path.splitext(path.split('?')[0])[1].lower()
        else:
            path = os.path.expanduser(path)
            if not os.path.isfile(path):
                print(f"  {t['err']}File not found: {path}{RST}")
                return None
            with open(path, 'rb') as f:
                data = f.read()
            ext = os.path.splitext(path)[1].lower()
        
        mime_map = {
            '.jpg': 'image/jpeg', '.jpeg': 'image/jpeg',
            '.png': 'image/png', '.gif': 'image/gif',
            '.webp': 'image/webp', '.bmp': 'image/bmp',
            '.tiff': 'image/tiff', '.tif': 'image/tiff',
        }
        mime = mime_map.get(ext, 'image/png')
        b64 = base64.b64encode(data).decode('ascii')
        data_uri = f"data:{mime};base64,{b64}"
        
        size_mb = len(data) / (1024 * 1024)
        print(f"  {t['bright']}+ Image: {os.path.basename(path)} ({size_mb:.1f} MB){RST}")
        if size_mb > 20:
            print(f"  {t['warn']}Large image may exceed model context limits{RST}")
        
        return [
            {"type": "text", "text": prompt},
            {"type": "image_url", "image_url": {"url": data_uri}}
        ]
    except Exception as e:
        print(f"  {t['err']}Error loading image: {e}{RST}")
        return None

if __name__ == '__main__':
    main()
