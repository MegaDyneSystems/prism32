#!/usr/bin/env python3
"""
Prism32 v6.6 - MegaDyne Systems Terminal Agent
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
from datetime import datetime
import platform
import atexit
import math
import threading
stdout_lock = threading.Lock()
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

def load_plugins():
    """Load external command plugins from ~/.prism32/plugins/.
    Uses importlib.util to load from file path (no sys.path manipulation needed)."""
    if not os.path.isdir(PLUGIN_DIR):
        os.makedirs(PLUGIN_DIR, exist_ok=True)
        return
    for f in sorted(os.listdir(PLUGIN_DIR)):
        if f.endswith(".py") and not f.startswith("_"):
            mod_name = f[:-3]
            mod_path = os.path.join(PLUGIN_DIR, f)
            try:
                spec = importlib.util.spec_from_file_location(mod_name, mod_path)
                if spec and spec.loader:
                    mod = importlib.util.module_from_spec(spec)
                    spec.loader.exec_module(mod)
                    api = PluginAPI(mod_name)
                    _plugin_apis[mod_name] = api
                    if hasattr(mod, "register"):
                        mod.register(api)
                    _PluginHooks.register_plugin(mod, api)
                    _PLUGINS[mod_name] = mod
                    print(f"  [plugin] Loaded: {mod_name}")
            except Exception as e:
                print(f"  [plugin] Error loading {mod_name}: {e}")

# ── Self-Evolving Memory System ─────────────────────────────
# Small persistent file (~/.prism32/memory.json) that tracks
# usage patterns, errors, and preferences to improve over time.

MEMORY_FILE = os.path.join(os.path.expanduser("~"), ".prism32", "memory.json")
QUANTUM_FILE = os.path.join(os.path.expanduser("~"), ".prism32", "quantum.json")

_MEMORY_DIRTY = False
_MEMORY_FLUSH_COUNTER = 0
_LAST_INTERJECT = ""
_CURRENT_SESSION_ID = None

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
        "session_count": 0,
        "suggestions_shown": [],
    }

def load_memory():
    try:
        with open(MEMORY_FILE) as f:
            mem = json.load(f)
        if mem.get("version", 0) < 2:
            mem = _default_memory()
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
    if _MEMORY_FLUSH_COUNTER >= 10:
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
    parts.append(f"user:{os.getenv('USER', '?')}")
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
    result = " [" + " | ".join(parts) + "]" if parts else ""
    limit = getattr(Config, "MAX_MEMORY_CTX", 1024)
    if limit <= 0:
        return ""
    return result[:limit]

# Resilient shutdown
def _cleanup():
    _flush_memory()

    print("\r\x1b[?25h\x1b[0m", end="", flush=True)
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

class Platform:
    """Cross-platform detection and compatibility."""
    
    LINUX = sys.platform.startswith("linux")
    MACOS = sys.platform == 'darwin'
    WINDOWS = sys.platform == 'win32'
    BSD = 'bsd' in sys.platform.lower()
    TERMUX = LINUX and os.environ.get('TERMUX_VERSION', '') != ''
    ANDROID = TERMUX or os.environ.get('ANDROID_ROOT', '') != ''
    
    @staticmethod
    def get_system():
        """Get the operating system name."""
        if Platform.TERMUX:
            return "Android (Termux)"
        if Platform.ANDROID:
            return "Android"
        if Platform.MACOS:
            return "macOS"
        elif Platform.LINUX:
            try:
                with open('/etc/os-release') as f:
                    for line in f:
                        if line.startswith('PRETTY_NAME'):
                            return line.split('=', 1)[1].strip().strip('"')
            except Exception:
                pass
            return "Linux"
        elif Platform.WINDOWS:
            return "Windows"
        elif Platform.BSD:
            return "BSD"
        return platform.system()
    
    @staticmethod
    def get_arch():
        """Get system architecture."""
        machine = platform.machine()
        arch_map = {
            'x86_64': 'x86_64',
            'AMD64': 'x86_64',
            'amd64': 'x86_64',
            'i386': 'i686',
            'i486': 'i686',
            'i586': 'i686',
            'i686': 'i686',
            'aarch64': 'ARM64',
            'arm64': 'ARM64',
            'armv7l': 'ARMv7',
            'armv7': 'ARMv7',
            'armv6l': 'ARMv6',
            'armv6': 'ARMv6',
            'arm': 'ARM',
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
            'mipsel': 'MIPS LE',
            'sparc': 'SPARC',
            'sparc64': 'SPARC 64',
            's390': 'S/390',
            's390x': 'S/390x',
            'alpha': 'Alpha',
            'hppa': 'PA-RISC',
            'parisc': 'PA-RISC',
            'ia64': 'Itanium',
        }
        return arch_map.get(machine, machine)
    
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
                import subprocess
                result = subprocess.run(['sysctl', '-n', 'machdep.cpu.brand_string'], 
                                      capture_output=True, text=True)
                return result.stdout.strip()
            elif Platform.WINDOWS:
                import subprocess
                result = subprocess.run(['wmic', 'cpu', 'get', 'name'],
                                      capture_output=True, text=True)
                lines = result.stdout.strip().split('\n')
                if len(lines) > 1:
                    return lines[1].strip()
            elif Platform.BSD:
                import subprocess
                result = subprocess.run(['sysctl', '-n', 'hw.model'],
                                      capture_output=True, text=True)
                return result.stdout.strip() or "Unknown CPU"
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
                import subprocess
                result = subprocess.run(['sysctl', '-n', 'hw.memsize'], 
                                      capture_output=True, text=True)
                return int(result.stdout.strip()) // (1024 * 1024)
            elif Platform.WINDOWS:
                import subprocess
                result = subprocess.run(['wmic', 'OS', 'get', 'TotalVisibleMemorySize'],
                                      capture_output=True, text=True)
                lines = result.stdout.strip().split('\n')
                if len(lines) > 1:
                    return int(lines[1].strip()) // 1024
            elif Platform.BSD:
                import subprocess
                result = subprocess.run(['sysctl', '-n', 'hw.physmem'],
                                      capture_output=True, text=True)
                return int(result.stdout.strip()) // (1024 * 1024)
        except Exception:
            pass
        return 0
    
    @staticmethod
    def get_uptime():
        """Get system uptime as string."""
        try:
            if Platform.LINUX:
                with open('/proc/uptime') as f:
                    secs = float(f.read().split()[0])
            elif Platform.MACOS or Platform.BSD:
                import subprocess, re
                result = subprocess.run(['sysctl', '-n', 'kern.boottime'],
                                      capture_output=True, text=True)
                import time
                m = re.search(r'sec\s*=\s*(\d+)', result.stdout)
                boot_time = int(m.group(1)) if m else 0
                secs = time.time() - boot_time
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
        # Use sys.platform directly — Platform.get_system() returns friendly
        # names like 'macOS', 'BSD', or 'Ubuntu 22.04.4 LTS' that are not
        # reliable for platform matching.
        plat = sys.platform.lower()

        # OS-specific priority order
        if plat == 'darwin':
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
                ('apt', 'apt'), ('apt-get', 'apt'), ('dnf', 'dnf'), ('yum', 'yum'),
                ('pacman', 'pacman'), ('zypper', 'zypper'), ('apk', 'apk'),
                ('nix-env', 'nix'), ('snap', 'snap'), ('flatpak', 'flatpak'),
                ('brew', 'brew'), ('port', 'macports'),
                ('pkgin', 'pkgin'), ('pkg_add', 'pkg_add'), ('pkg', 'pkg'),
            ]
        elif 'win32' in plat:
            check_order = [
                ('winget', 'winget'), ('choco', 'chocolatey'), ('scoop', 'scoop'),
            ]
        else:
            check_order = [
                ('brew', 'brew'), ('port', 'macports'),
                ('apt', 'apt'), ('apt-get', 'apt'), ('dnf', 'dnf'), ('yum', 'yum'),
                ('pacman', 'pacman'), ('zypper', 'zypper'), ('apk', 'apk'),
                ('nix-env', 'nix'), ('snap', 'snap'), ('flatpak', 'flatpak'),
                ('pkgin', 'pkgin'), ('pkg_add', 'pkg_add'), ('pkg', 'pkg'),
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
            'yum': f'sudo yum install -y {package}',
            'pacman': f'sudo pacman -S --noconfirm {package}',
            'zypper': f'sudo zypper install -y {package}',
            'apk': f'sudo apk add {package}',
            'nix': f'nix-env -iA {package}',
            'snap': f'sudo snap install {package}',
            'flatpak': f'flatpak install -y flathub {package}',
            'brew': f'brew install {package}',
            'macports': f'sudo port install {package}',
            'pkgin': f'sudo pkgin install {package}',
            'pkg_add': f'sudo pkg_add {package}',
            'pkg': f'sudo pkg install -y {package}',
            'winget': f'winget install {package}',
            'chocolatey': f'choco install {package}',
            'scoop': f'scoop install {package}',
        }
        
        return commands.get(pm, f'echo "Install {package} using your package manager"')
    
    @staticmethod
    def get_network_command():
        """Get the appropriate network command."""
        if Platform.MACOS or Platform.BSD:
            return "ifconfig"
        return "ip"
    
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
    MODEL = "qwen/qwen3.7-max"
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
    STREAM = True
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
            if "stream" in data: cls.STREAM = data["stream"]
            if "slow_cpu" in data: cls.SLOW_CPU = data["slow_cpu"]
            if "subagent_model" in data: cls.SUBAGENT_MODEL = data["subagent_model"]
            if "root_pass" in data: cls.ROOT_PASS = data["root_pass"]
            if "agent_name" in data: cls.AGENT_NAME = data["agent_name"]
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

# ── Model Providers ────────────────────────────────────────────

# ── Provider Registry (built-ins) ──────────────────────
register_provider("local", display_name="Local (llama.cpp)", api_base="http://127.0.0.1:8080", model="qwen-3.7", description="Local llama.cpp server")
register_provider("ollama", display_name="Ollama (localhost)", api_base="http://localhost:11434/v1", model="qwen3:14b", description="Local Ollama server")
register_provider("openai", display_name="OpenAI", api_base="https://api.openai.com/v1", model="gpt-4o", description="OpenAI GPT-4o (requires API key)")
register_provider("anthropic", display_name="Anthropic", api_base="https://api.anthropic.com/v1", model="claude-sonnet-4-20250514", description="Anthropic Claude (requires API key)")
register_provider("groq", display_name="Groq", api_base="https://api.groq.com/openai/v1", model="llama-3.3-70b-versatile", description="Groq fast inference")
register_provider("together", display_name="Together AI", api_base="https://api.together.xyz/v1", model="meta-llama/Llama-3-70b-chat-hf", description="Together AI inference")
register_provider("openrouter", display_name="OpenRouter", api_base="https://openrouter.ai/api/v1", model="qwen/qwen3.7-max", description="OpenRouter multi-model gateway (set API key via /provider key or --api-key)")
register_provider("custom", display_name="Custom", api_base="http://localhost:8080", model="model-name", description="Custom provider (configure below)")


_T_CACHE = {}
def T():
    theme = Config.THEME
    if theme not in _T_CACHE:
        _T_CACHE[theme] = THEME_REGISTRY.get(theme, THEME_REGISTRY.get("phosphor", {}))
    return _T_CACHE[theme]

def _clear_theme_cache():
    _T_CACHE.clear()

_RE_ANSI = re.compile(r'\x1b\[[0-9;]*[a-zA-Z]')
_RE_STRIP_ANSI = re.compile(r'\x1b\[[0-9;]*m')
_RE_EXEC_BLOCK = re.compile(r'```execute\n(.*?)```', re.DOTALL)
_RE_ASK_BLOCK = re.compile(r'```ask\n(.*?)```', re.DOTALL)

RST = "\x1b[0m"
BOLD = "\x1b[1m"
DIM  = "\x1b[2m"
HIDE = "\x1b[?25l"
SHOW = "\x1b[?25h"
CLS  = "\x1b[2J\x1b[H"

# ── Persistent footer / scroll region ───────────────────────
_term_size = os.terminal_size((80, 24))

def update_terminal_size():
    """Update cached terminal dimensions."""
    global _term_size
    try:
        _term_size = shutil.get_terminal_size()
    except Exception:
        pass

def set_scroll_region():
    """Reserve bottom line for the footer; everything else scrolls above."""
    h = _term_size.lines
    if h > 1:
        sys.stdout.write(f"\x1b[1;{h-1}r")
    sys.stdout.flush()

def reset_scroll_region():
    """Reset scrolling region to full screen."""
    sys.stdout.write("\x1b[r")
    sys.stdout.flush()

def move_to_footer():
    """Move cursor to the bottom line (reserved footer)."""
    sys.stdout.write(f"\x1b[{_term_size.lines};1H")
    sys.stdout.flush()

def move_to_scroll_bottom():
    """Move cursor to the last line of the scroll region (just above footer)."""
    h = _term_size.lines
    if h > 1:
        sys.stdout.write(f"\x1b[{h-1};1H")
    else:
        sys.stdout.write("\x1b[1;1H")
    sys.stdout.flush()

def clear_footer():
    """Clear the footer line."""
    move_to_footer()
    sys.stdout.write("\x1b[K")
    sys.stdout.flush()

def draw_footer(status_bar, spin_char=None):
    """Draw the footer at the bottom of the screen."""
    t = T()
    indicator = spin_char if spin_char is not None else f"{t['dim']}░{RST}"
    clear_footer()
    sys.stdout.write(f"{status_bar} {indicator} {t['primary']}>{RST} ")
    sys.stdout.flush()

# ── Interjection (type while AI streams) ─────────────────────

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
        clear_footer()

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
            text = data.decode('utf-8', errors='replace')
            for ch in text:
                if _INTERJECTION_ESCAPE:
                    _INTERJECTION_ESCAPE_BUF += ch
                    seq = _INTERJECTION_ESCAPE_BUF
                    b = ord(ch)
                    if 0x40 <= b <= 0x7E or ch == '~':
                        _INTERJECTION_ESCAPE = False
                        _INTERJECTION_ESCAPE_BUF = ""
                        if seq == '[A':  # Up
                            if _INTERJECTION_HISTORY:
                                if _INTERJECTION_HISTORY_IDX == -1:
                                    _INTERJECTION_SAVED_BUF = _INTERJECTION_BUF
                                    _INTERJECTION_HISTORY_IDX = len(_INTERJECTION_HISTORY) - 1
                                elif _INTERJECTION_HISTORY_IDX > 0:
                                    _INTERJECTION_HISTORY_IDX -= 1
                                _INTERJECTION_BUF = _INTERJECTION_HISTORY[_INTERJECTION_HISTORY_IDX]
                                _INTERJECTION_CURSOR = len(_INTERJECTION_BUF)
                                _INTERJECTION_HAS_TYPED = True
                        elif seq == '[B':  # Down
                            if _INTERJECTION_HISTORY and _INTERJECTION_HISTORY_IDX >= 0:
                                _INTERJECTION_HISTORY_IDX += 1
                                if _INTERJECTION_HISTORY_IDX >= len(_INTERJECTION_HISTORY):
                                    _INTERJECTION_HISTORY_IDX = -1
                                    _INTERJECTION_BUF = _INTERJECTION_SAVED_BUF
                                else:
                                    _INTERJECTION_BUF = _INTERJECTION_HISTORY[_INTERJECTION_HISTORY_IDX]
                                _INTERJECTION_CURSOR = len(_INTERJECTION_BUF)
                                _INTERJECTION_HAS_TYPED = True
                        elif seq == '[C':  # Right
                            _INTERJECTION_CURSOR = min(len(_INTERJECTION_BUF), _INTERJECTION_CURSOR + 1)
                            _INTERJECTION_HAS_TYPED = True
                        elif seq == '[D':  # Left
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
                    if _INTERJECTION_BUF:
                        _INTERJECTION_HISTORY.append(_INTERJECTION_BUF)
                    result = _INTERJECTION_BUF
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
        if buf or _INTERJECTION_HAS_TYPED:
            t = T()
            clear_footer()
            visual = f" {t['bright']}interject>{RST} {buf}"
            sys.stdout.write(visual)
            move_back = len(buf) - cur
            if move_back > 0:
                sys.stdout.write(f"\x1b[{move_back}D")
            sys.stdout.flush()
        else:
            draw_footer(build_status_bar())

# ── ANSI Helpers ─────────────────────────────────────────────

def strip_ansi(text):
    return _RE_STRIP_ANSI.sub('', text)

def rl_prompt(text):
    """Wrap ANSI escapes in readline \x01/\x02 markers so cursor tracking works."""
    return re.sub(r'(\x1b\[[0-9;?]*[a-zA-Z])', '\x01\\1\x02', text)

def build_status_bar(spin_char=None, history=None, include_indicator=True):
    """Build the bottom status bar: Prism32 MDS:<think> <ctx%> <spin> > """
    t = T()
    parts = [f" {t['bright']}Prism32{RST} {t['dim']}MDS{RST}:"]
    if Config.THINKING_EFFORT:
        parts.append(f"{t['dim']}{Config.THINKING_EFFORT}{RST}")
    ctx = context_pct(history) if history else 0
    if ctx > 0:
        ctx_color = t['err'] if ctx >= 90 else (t['warn'] if ctx >= 75 else t['dim'])
        parts.append(f" {ctx_color}Ctx {ctx}%{RST}")
    if include_indicator:
        indicator = spin_char if spin_char is not None else f"{t['dim']}░{RST}"
        parts.append(f" {indicator}")
    return "".join(parts)

# ── Box Drawing ──────────────────────────────────────────────

def _wrap_line(line, cw):
    """Word-wrap a single line to fit within cw columns, preserving ANSI codes."""
    safe = line.replace('{', '').replace('}', '')
    visible = strip_ansi(safe)
    if len(visible) <= cw:
        return [line]

    # Word-wrap: split on spaces, accumulate until width exceeded
    chunks = []
    words = safe.split(' ')
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
    print(f"{c}|{RST} {c}{BOLD}{str(title):<{cw}}{RST} {c}|{RST}")
    print(f"{c}|{'-'*iw}|{RST}")
    for raw_line in raw_lines:
        wrapped = _wrap_line(raw_line, cw)
        for chunk in wrapped:
            safe = chunk.replace('{', '').replace('}', '')
            vis = len(strip_ansi(safe))
            pad = cw - vis
            if pad < 0:
                safe = safe[:cw]
                vis = cw
                pad = 0
            print(f"{c}|{RST} {safe}{' '*pad} {c}|{RST}")
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
        self.frames = ["⣾", "⣽", "⣻", "⢿", "⡿", "⣟", "⣯", "⣷"]

    def run(self):
        i = 0
        inline = _BOTTOM_BAR_SPINNER_STATE["enabled"]

        while not self._done.is_set():
            with stdout_lock:
                if inline:
                    char = self.frames[i % len(self.frames)]
                    history = _BOTTOM_BAR_SPINNER_STATE["history"]
                    draw_footer(build_status_bar(history=history, include_indicator=False), spin_char=char)
                    i += 1
                else:
                    t = T()
                    char = self.frames[i % len(self.frames)]
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
                draw_footer(build_status_bar(history=history, include_indicator=False), spin_char=None)
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
    print(f"{d}  v6.6 - MegaDyne Systems MDS{RST}")
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
        return 0

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
    """Run command as root via pty-based su (BSD needs a TTY for su)."""
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

def run_cmd(cmd, timeout=None):
    if timeout is None:
        timeout = Config.CMD_TIMEOUT
    try:
        if Platform.BSD and Config.ROOT_PASS and ('su' in cmd or 'sudo' in cmd):
            return _pty_su_root(cmd, timeout)
        env = None
        if Config.ROOT_PASS and ('su' in cmd or 'sudo' in cmd):
            env = {**os.environ, "ROOT_PASS": Config.ROOT_PASS}
        result = subprocess.run(cmd, shell=True, capture_output=True, text=True, timeout=timeout, env=env)
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

    def put(self, key, value):
        with self._lock:
            self._data[key] = value

    def get(self, key, default=None):
        with self._lock:
            return self._data.get(key, default)

    def items(self):
        with self._lock:
            return dict(self._data)

    def merge(self, data):
        with self._lock:
            self._data.update(data)

    def clear(self):
        with self._lock:
            self._data.clear()

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

You are working on a subtask delegated by the main agent. Work autonomously step by step. After each command, assess progress. Report when done.

A shared quantum context is available between all agents. Read from it with the /quantum command when you need shared information.
Use /remember <text> to store important findings in the long-term file-cabinet memory.
Use /recall <query> to search past memories from any agent.
You can be assigned a different provider than the main agent via --provider flag.
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
                resp = ask_ai(self._history, stream=False)
                if not resp or resp.startswith('['):
                    self.error = resp or "No response"
                    self.result = f"[SUBAGENT ERROR] {self.error}"
                    break
                resp = handle_ask_blocks(resp, self._history)
                commands = extract_blocks(resp, 'execute')
                if commands:
                    clean = clean_response(resp)
                    for c in commands:
                        c = c.strip()
                        result = run_cmd(c)
                        success = "error" not in result.lower()[:50] and "blocked" not in result.lower()
                        cmd_result(c, result, success)
                        msg = f"Executed: {c}\nResult:\n{result[:1500]}"
                        self._history.append({"role": "user", "content": f"{msg}\n\nCommand output above. Continue with task or give final answer."})
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
        self._run_loop()
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
            return f"[{self.id}] RUNNING  task: {self.task[:50]}"
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

When given a GOAL, work autonomously step by step. After each command,
assess progress toward the goal. Use ```ask``` only if truly stuck.

CROSS-PLATFORM RULES:
1. Detect the OS first: uname -s (Linux/Darwin/macOS/NetBSD/FreeBSD/OpenBSD/Windows)
2. Use the system's actual package manager: apt/apt-get (Debian/Ubuntu), dnf/yum (Fedora/RHEL), pacman (Arch), zypper (openSUSE), apk (Alpine), nix (NixOS), snap/flatpak (universal Linux), brew/port (macOS), pkgin/pkg_add/pkg (BSD), winget/choco/scoop (Windows). Prefer the OS-native manager over universal ones.
3. Use appropriate network command: ip/ss (Linux), ifconfig/netstat (macOS/BSD), Get-NetAdapter (Windows PowerShell)
4. For root access on Linux: echo "$ROOT_PASS" | su -c "command" or use sudo
5. For root access on BSD: su root -c "command" (password injected automatically)
6. For root access on macOS: sudo command (will prompt for password)
7. On Windows, use PowerShell or cmd; avoid Unix-only utilities

GENERAL RULES:
1. ALWAYS run commands to investigate - don't just suggest them
2. Verify fixes work by running check commands
3. Be concise and direct
4. Chain commands with && or ; when logical
5. When a goal is set, keep working until done or max steps reached
6. Report what you did and what remains after each step"""

def ask_ai(messages, stream=None, retry=2, base_delay=2):
    '''Resilient AI query with retry, backoff, and history trimming.'''
    # Filter empty messages
    clean_messages = []
    for m in messages:
        if m.get("content", "").strip():
            clean_messages.append(m)
        elif m.get("role") in ("system", "assistant"):
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
        try:
            req = urllib.request.Request(
                url,
                data=json.dumps(payload).encode(),
                headers=build_headers(),
            )
            with urllib.request.urlopen(req, timeout=600) as resp:
                if stream if stream is not None else Config.STREAM:
                    return stream_response(resp)
                data = json.loads(resp.read().decode())
                return data.get('choices', [{}])[0].get('message', {}).get('content', '')
        except urllib.error.HTTPError as e:
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
            last_error = f"[NETWORK ERROR] {e}"
            learn_error(str(e), "network")
            if attempt < retry:
                delay = base_delay * (2 ** attempt)
                viz.status(f"Network error, retrying in {delay}s...", "warning")
                time.sleep(delay)
                continue
            break
        except Exception as e:
            last_error = f"[ERROR] {e}"
            learn_error(str(e), "ask_ai exception")
            break
    
    return last_error

def stream_response(resp):
    full = ""
    t = T()
    reasoning_mode = False
    agent_prefix_printed = False
    
    for line in resp:
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
                with stdout_lock:
                    move_to_scroll_bottom()
                    if not agent_prefix_printed:
                        sys.stdout.write(f" {t['accent']}<{Config.AGENT_NAME}>:{RST} ")
                        agent_prefix_printed = True
                    sys.stdout.write(f"{t['dim']}{reasoning}{RST}")
                    sys.stdout.flush()
                reasoning_mode = True
            
            if content:
                with stdout_lock:
                    move_to_scroll_bottom()
                    if not agent_prefix_printed:
                        sys.stdout.write(f" {t['primary']}<{Config.AGENT_NAME}>:{RST} ")
                        agent_prefix_printed = True
                    if reasoning_mode:
                        sys.stdout.write(f"\n{t['primary']}")
                        reasoning_mode = False
                    sys.stdout.write(f"{t['primary']}{content}{RST}")
                    sys.stdout.flush()
                full += content
        except json.JSONDecodeError:
            continue

        inj = _interjection_poll()
        if inj is not None:
            _interjection_stop()
            with stdout_lock:
                sys.stdout.write(SHOW)
            return full
    
    _interjection_stop()
    with stdout_lock:
        sys.stdout.write(SHOW)
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

# ── Context Builder ──────────────────────────────────────────

def build_context():
    info = get_system_info()
    mem = memory_context()
    extra = ""
    if _PluginHooks._extra_context:
        extra = "\n" + "\n".join(_PluginHooks._extra_context) + "\n"
    return (
        f"System: {info.get('os', '')} {info.get('arch', '')}\n"
        f"CPU: {info.get('cpu', '')}\nRAM: {info.get('ram', '')}\n"
        f"Disk: {info.get('disk', '')}\nIP: {info.get('ip', '')}\n"
        f"Uptime: {info.get('uptime', '')}\nCWD: {os.getcwd()}\n"
        f"Memory:{mem}\n{extra}"
    )

# ── User Interaction (ask / interject) ──────────────────────

def ask_user(question):
    t = T()
    print(f"\n{t['warn']}+ QUESTION FROM AI:{RST}")
    box("AI NEEDS INPUT", question, "warn")
    try:
        answer = input(rl_prompt(f" {t['bright']}answer{RST} {t['primary']}>{RST} ")).strip()
    except (EOFError, KeyboardInterrupt):
        answer = ""
    return answer

def handle_ask_blocks(resp, history, goal_mode=False):
    t = T()
    questions = extract_blocks(resp, 'ask')
    if not questions:
        return resp
    
    if goal_mode:
        # In goal mode, don't ask questions - strip them and continue
        cleaned = clean_response(resp)
        if not cleaned:
            # Force the model to execute commands instead of asking
            cleaned = "Run commands. Do not ask questions."
        viz.status("Stripped question blocks in goal mode", "warning")
        return cleaned
    
    for q in questions:
        answer = ask_user(q.strip())
        history.append({"role": "assistant", "content": f"[User was asked]: {q.strip()}"})
        history.append({"role": "user", "content": f"[User answered]: {answer}"})
    cleaned = clean_response(resp)
    return cleaned

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
                resp = ask_ai(history)
                print()
            else:
                spin = SpinnerThread("thinking")
                spin.start()
                resp = ask_ai(history, stream=False)
        except KeyboardInterrupt:
            resp = None
        finally:
            if spin is not None:
                spin.stop()
        if resp and (resp.startswith('[HTTP ERROR 400]') or resp.startswith('[HTTP ERROR 413]')):
            if len(history) > 5:
                history = [history[0]] + history[:-4]
            viz.status("API error, trimming history and retrying...", "warning")
            resp = ask_ai(history, stream=False)
        if resp and (resp.startswith('[HTTP ERROR 400]') or resp.startswith('[HTTP ERROR 413]')):
            # Second failure - strip back to just system + goal, retry once more
            history = history[:2]
            viz.status("API error again, stripping history to system+goal...", "warning")
            resp = ask_ai(history, stream=False)
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

            for c in commands:
                c = c.strip()
                viz.tool_call("execute", c)
                result = run_cmd(c)
                success = "error" not in result.lower()[:50] and "blocked" not in result.lower()
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

    if not completed:
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
    'agentname', 'api', 'apikey', 'autosave', 'bash', 'cat', 'clear', 'collect', 'config', 'debug', 'delegate', 'delete', 'edit', 'exit', 'export', 'find', 'forget', 'git', 'goal', 'grep', 'help', 'history', 'key', 'load', 'loadcfg', 'log', 'ls', 'maxhistory', 'maxsteps', 'maxtokens', 'memories', 'memory', 'model', 'net', 'ports', 'procs', 'provider', 'providers', 'q', 'quantum', 'quit', 'recall', 'remember', 'resume', 'rootpass', 'sam', 'save', 'savecfg', 'session', 'sessions', 'skill-create', 'skill-delete', 'skill-list', 'skill-load', 'spawn', 'stream', 'subagent-model', 'subagents', 'sysinfo', 'temperature', 'theme', 'thinking', 'timeout', 'update', 'usage', 'plugins'
, 'memctx', 'memory'
}

CMD_HELP = """{bold}== Prism32 by MegaDyne Systems (MDS) =={reset}
 All commands require the / prefix.

 {bold}AI Interaction{reset}
   <anything>           Talk to AI - it runs commands automatically
   /goal <task>         Autonomous multi-step goal mode

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

 {bold}System{reset}
   /sysinfo             System information
   /procs               Top processes by CPU
   /net                 Network interfaces + routes
   /ports               Open listening ports
   /debug               Toggle debug logging
   /log                 Show debug log
   /memory              Show memory stats

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
   /theme               Cycle theme (21 built-in themes)
   /plugins             List loaded plugins
   /update [dir]        Git pull + reinstall from project directory
   /help                This help
   /quit                Exit

 {bold}Subagents{reset}
   /delegate <task>     Sync subagent (--provider <name> for different provider)
   /spawn <task>        Async subagent (--provider <name> for different provider)
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
   """


 

def cmd_sysinfo():
    display_system_info()

def cmd_procs():
    if Platform.LINUX:
        out = run_cmd("ps aux --sort=-%cpu | head -12")
    elif Platform.MACOS:
        out = run_cmd("ps aux -r | head -12")
    elif Platform.BSD:
        out = run_cmd("ps aux -r | head -12")
    else:
        out = run_cmd("ps aux | head -12")
    box("TOP PROCESSES", out, "primary")
    if Platform.LINUX:
        mem = run_cmd("free -h")
    elif Platform.MACOS:
        mem = run_cmd("vm_stat | head -10")
    elif Platform.BSD:
        mem = run_cmd("vmstat -s | head -10")
    else:
        mem = f"RAM: {Platform.get_ram()} MB"
    box("MEMORY", mem, "accent")

def cmd_net():
    if Platform.LINUX:
        out = run_cmd("ip -br addr 2>/dev/null")
        routes = run_cmd("ip route 2>/dev/null | head -5")
    elif Platform.MACOS or Platform.BSD:
        out = run_cmd("ifconfig -a 2>/dev/null | head -30")
        routes = run_cmd("netstat -rn -f inet 2>/dev/null | head -5")
    else:
        out = run_cmd("ifconfig 2>/dev/null | head -20")
        routes = ""
    box("INTERFACES", out, "primary")
    if routes:
        box("ROUTES", routes, "dim")

def cmd_ports():
    if Platform.LINUX:
        out = run_cmd("ss -tlnp 2>/dev/null | head -20")
        if not out.strip():
            out = run_cmd("netstat -tlnp 2>/dev/null | head -20")
    elif Platform.MACOS:
        out = run_cmd("lsof -iTCP -sTCP:LISTEN -P -n 2>/dev/null | head -20")
    elif Platform.BSD:
        out = run_cmd("sockstat -4 -l 2>/dev/null | head -20")
        if not out.strip():
            out = run_cmd("netstat -an -f inet 2>/dev/null | grep LISTEN | head -20")
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
    parser.add_argument("--turbo", action="store_true", help="Turbo mode: enable streaming and animated spinner (default)")
    parser.add_argument("--slow-cpu", action="store_true", help=argparse.SUPPRESS)
    parser.add_argument("--no-boot", action="store_true", help="Skip boot sequence")
    parser.add_argument("--temperature", type=float, help="AI temperature (0.0-1.0)")
    parser.add_argument("--goal", "-g", help="Run in goal mode and exit")
    parser.add_argument("--set-timeout", type=int, help="Set command timeout in seconds and exit")
    parser.add_argument("--update", help="Update prism32 from a URL or file path and exit")
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
    if args.set_timeout is not None:
        Config.CMD_TIMEOUT = max(1, args.set_timeout)
        Config.save_config()
        print(f"Command timeout set to {Config.CMD_TIMEOUT}s")
        return
    if args.update:
        _do_git_update(args.update)
        return

    t = T()

    print(HIDE + CLS)
    banner()

    load_plugins()
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
        draw_footer(build_status_bar(history=history))
        try:
            user_input = input().strip()
        except (EOFError, KeyboardInterrupt):
            print()
            reset_scroll_region()
            print(f"  {t['bright']}Shutting down...{RST}")
            break

        if not user_input:
            continue
        _PluginHooks.fire_message(user_input)
        # Clear interject recall on new input
        _LAST_INTERJECT = ""

        # Echo user message in scroll region
        move_to_scroll_bottom()
        print(f" {t['primary']}You:{RST} {user_input}")

        is_slash = user_input.startswith("/")
        parts = user_input.lstrip("/").split(None, 1)
        cmd = parts[0].lower()
        args_str = parts[1] if len(parts) > 1 else ""

        if not is_slash:
            pass
        elif cmd in ("quit", "exit", "q"):
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
        if registry.dispatch(cmd, args_str, history, cmd_log):
            learn_command(cmd, success=True, duration=0)
            _PluginHooks.fire_command(cmd, args_str, None)
            save_current_session(history, cmd_log)
            continue

        # ── Built-in commands ──
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
            mem = load_memory()
            stats = mem.get('command_stats', {})
            errors = mem.get('error_patterns', {})
            sess = mem.get('session_count', 0)
            lines = [f" Sessions:    {sess}",
                    f" Commands tracked: {len(stats)}",
                    f" Error patterns:   {len(errors)}",
                    "", " Top Commands:"]
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
            box("MEMORY", "\n".join(lines), "accent")
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
                print(f"  Subagent {sa.id} spawned asynchronously.")
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
                print(f"  Subagent {sid} still running. Check /subagents for status.")
                continue
            print(f"  {T()['bright']}Result from {sid}:{RST}")
            print(f"  {(sa.result or sa.error or '?')[:2000]}")
            print()
            # Add to history
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
                            result = run_cmd(c)
                            success = "error" not in result.lower()[:50] and "blocked" not in result.lower()
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
        history.append({"role": "user", "content": user_input})
        max_iter = 9999

        for iteration in range(max_iter):
            spin = None
            try:
                if Config.STREAM:
                    move_to_scroll_bottom()
                    _interjection_start()
                    resp = ask_ai(history)
                    print()
                else:
                    set_bottom_bar_spinner(history)
                    spin = SpinnerThread("thinking")
                    spin.start()
                    resp = ask_ai(history)
            except KeyboardInterrupt:
                resp = None
            finally:
                if spin is not None:
                    spin.stop()
                    # After spinner, cursor is on footer line; move to scroll region
                    move_to_scroll_bottom()
                    print()
                _interjection_stop()

            # Handle interjection (user typed while AI was streaming)
            if _INTERJECTION_RESULT is not None:
                inj = _INTERJECTION_RESULT
                _INTERJECTION_RESULT = None
                if resp:
                    history.append({"role": "assistant", "content": resp})
                history.append({"role": "user", "content": inj})
                move_to_scroll_bottom()
                print(f" {T()['primary']}You:{RST} {inj}")
                save_current_session(history, cmd_log)
                continue
            if not resp or resp.startswith('['):
                box("AI ERROR", resp or "No response", "err")
                break

            resp = handle_ask_blocks(resp, history)
            commands = extract_blocks(resp, 'execute')

            if commands:
                clean = clean_response(resp)
                if clean and iteration == 0 and not Config.STREAM:
                    box("AI ANALYSIS", clean, "accent")

                for c in commands:
                    c = c.strip()
                    viz.tool_call("execute", c)
                    result = run_cmd(c)
                    success = "error" not in result.lower()[:50] and "blocked" not in result.lower()
                    viz.tool_result(success, result[:100])
                    cmd_result(c, result, success)
                    cmd_log.append(("ai", c))

                    exec_msg = f"Executed: {c}\nResult:\n{result[:1500]}"
                    continuation = "Command output above. Continue with your task or give final answer."
                    if exec_msg.strip():
                        history.append({"role": "user", "content": f"{exec_msg}\n\n{continuation}"})
                    else:
                        history.append({"role": "user", "content": continuation})
            else:
                clean = clean_response(resp)
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

if __name__ == '__main__':
    main()