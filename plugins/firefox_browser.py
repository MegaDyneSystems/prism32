"""
Prism32 Firefox Browser Plugin — /fox and /firefox
==================================================

Real web browsing from inside the agent, driving the OPERATOR'S actual
Firefox session: same profile, same logins, same cookies — no re-auth.
Built directly on Firefox's built-in Marionette remote-control protocol
over plain TCP. Pure stdlib: socket + threading only. NO websockets, NO
asyncio, NO extension, NO event loops.

This is a clean rewrite of the quarantined _firefox_agent.py.disabled
(that plugin died of asyncio.get_event_loop() on Python 3.14 and of
returning strings nobody ever printed). Contract honored here:
every command handler PRINTS its result and returns None — Prism32's
dispatch_capture captures stdout; return values are discarded. Every
command body is wrapped so a plugin error prints 'firefox: <error>' and
NEVER kills the host REPL.

MARIONETTE PROTOCOL — verified empirically against Firefox 158.0.1 on
this machine (probed with a raw socket script, 2026-11-24), then
cross-checked against mozilla-central source (gecko-dev mirror):

Framing (both directions, packets.sys.mjs JSONPacket):
    <utf8_byte_length>:<utf-8 JSON bytes>
  - The prefix counts UTF-8 BYTES of the body (the server converts the
    JS string to UTF-8 first and takes the converted string's length;
    read-side converts bytes back to unicode). ASCII-only bodies have
    len(str) == len(bytes) — count bytes, not chars, to be correct for
    unicode page titles.
  - Immediately after connect the server sends the handshake (a bare
    JSON object, same framing):
    50:{"applicationType":"gecko","marionetteProtocol":3}

Packets (message.sys.mjs):
  - client -> server command:  [0, <msg_id:int>, "<CommandName>", <params obj>]
  - server -> client response: [1, <msg_id:int>, <error|null>, <value>]
  - error is null on success; on failure an object
    {"error": "<kind>", "message": "<human msg>", "stacktrace": "..."}.
  - A malformed packet gets a response with msg_id -1.

Response value shapes (observed on 158):
  - Most W3C commands wrap: {"value": <result>} — GetTitle,
    GetCurrentURL, GetElementText, ExecuteScript, FindElement,
    TakeScreenshot, Navigate, SwitchToWindow, SetTimeouts...
  - Raw (no wrapper): NewSession -> {"sessionId", "capabilities"};
    FindElements/GetWindowHandles/CloseWindow -> plain arrays.

Command names verified live on Firefox 158.0.1 (the pre-quantum-era
names SendKeysToElement / ClickElement / ClearElement / GetCurrentUrl /
GetScreenshot / Stop are ALL "unknown command" now — do not use them):
    WebDriver:NewSession            (required once per TCP connection)
    WebDriver:Navigate              {"url"} — blocks until page load
    WebDriver:GetCurrentURL         NOTE THE CAPITAL "URL"
    WebDriver:GetTitle
    WebDriver:ExecuteScript         {"script", "args"} -> {"value": js}
    WebDriver:FindElement/FindElements {"using": "css selector", "value": sel}
    WebDriver:ElementClick          {"id": "<bare element uuid>"}
    WebDriver:ElementSendKeys       {"id", "text"} — APPENDS to the
                                    field (ElementClear first!); PUA
                                    key codes (\ue007 Enter) work inline
    WebDriver:ElementClear          {"id"}
    WebDriver:GetElementText       {"id"}
    WebDriver:TakeScreenshot       {"id": null, "full", "hash", "scroll"}
                                    -> {"value": base64 PNG}
    WebDriver:PerformActions / ReleaseActions  {"actions": [...]}
    WebDriver:GetWindowHandles / GetWindowHandle
    WebDriver:SwitchToWindow        {"handle", "focus": true}
    WebDriver:CloseWindow           -> remaining handles (raw array);
                                    afterwards the current context is
                                    dead until you SwitchToWindow to a
                                    surviving handle
    WebDriver:Back / Forward / Refresh
    WebDriver:SetTimeouts           {"implicit": ms} (respected by
                                    FindElement)
    Marionette:SetContext           {"value": "content"} — param key is
                                    "value" NOT "context" (assert.string
                                    on cmd.parameters.value). Raw
                                    connections start in CHROME scope;
                                    set content scope right after
                                    NewSession. Page commands still fail
                                    honestly ("privileged scope") until
                                    the first Navigate swaps the startup
                                    window for a real content tab
                                    (verified on 158).

Element references: FindElement's value is the W3C dict
    {"element-6066-11e4-a52e-4f735466cecf": "<uuid>"}
and subsequent element commands take the BARE UUID as "id"
(driver.sys.mjs does WebElement.fromUUID(id) with assert.string).

Launching:  `firefox --marionette` enables the server on the port from
the marionette.port pref (default 2828). The `--marionette-port <n>`
CLI flag is IGNORED by Firefox 158 (verified: fell back to 2828 in
every position) — to use another port, write
    user_pref("marionette.port", <n>);
into the profile's user.js before launching (only ever done for
explicit throwaway profile PATHS here; the operator's default/named
profiles are never modified and therefore always use 2828).

Reconnect semantics (verified): each new TCP connection must run its
own WebDriver:NewSession; the browser survives a client disconnect, so
auto-reconnect re-attaches to the still-running browser.

Profile flags (from `firefox --help`, verified text):
    (no flag)          -> Firefox picks its DEFAULT profile: this is
                          what "/fox start default" uses, so the
                          operator's real logins/cookies apply.
    -P <name>          -> select profile by NAME from profiles.ini.
    --profile <path>   -> use profile at PATH (throwaway/test profiles).

ENABLE (one-time, permanent):
    `/fox enable` is the ONLY flow that ever closes Firefox — and it
    does so ONCE, gracefully (SIGTERM = clean shutdown; Firefox saves
    the session, and session restore brings the tabs back). Steps:
    (1) if a Marionette port is already live it just attaches
    ("already enabled"); (2) else, if a Firefox is running without
    Marionette it prints the honest one-time notice and waits for Enter
    (interactive stdin only — 'now' skips the wait for automation;
    non-tty contexts never kill anything, they print instructions);
    (3) SIGTERM Firefox, wait for a clean exit; (4) relaunch detached
    with --marionette (default profile — tabs return); (5) patch a
    user-level .desktop copy of the Firefox launcher so every FUTURE
    normal launch keeps Marionette (marker-guarded, idempotent; on
    macOS/Windows or odd setups it prints manual instructions); (6)
    persist {"enabled": true} in state.json and print status. No other
    command ever calls pkill/kill — /fox start never closes Firefox: if
    the everyday Firefox is running without control it says exactly one
    line ("run /fox enable"). SIGTERM is never escalated to SIGKILL: a
    Firefox that refuses to exit within ~20s is left alone with an
    honest message.
"""

import base64
import json
import os
import re
import signal
import socket
import subprocess
import sys
import threading
import time
from urllib.parse import quote_plus

# Prism32 plugin API (set by register()).
api = None

# ── Locations (all plugin files live under ~/.prism32/firefox/) ──
FOX_DIR = os.path.join(os.path.expanduser("~"), ".prism32", "firefox")
STATE_FILE = os.path.join(FOX_DIR, "state.json")

DEFAULT_HOST = "127.0.0.1"
DEFAULT_PORT = 2828
W3C_ELEM_KEY = "element-6066-11e4-a52e-4f735466cecf"

# How long /fox enable waits for a SIGTERMed Firefox to exit cleanly
# (never escalated to SIGKILL — an exit dialog gets an honest message).
TERM_WAIT_SEC = 20.0

# The honest one-time notice /fox enable prints before the ONE restart.
ENABLE_NOTICE = (
    "Enabling browser control requires ONE Firefox restart (session "
    "restore brings all your tabs back — nothing is lost). Save any "
    "unsaved work in Firefox, then press Enter (Ctrl-C to cancel).")

# Marker comment placed in the patched user-level .desktop — the guard
# that makes the patch idempotent (never double-append).
DESKTOP_MARKER = "# prism32-fox"

# Socket timeouts: attach attempts fail fast; command I/O allows for a
# slow page load (Marionette's pageLoadStrategy normal blocks Navigate
# until load, default session page-load timeout is 300 s — keep the
# socket timeout comfortably above it).
_CONNECT_TIMEOUT = 8
_CMD_TIMEOUT = 360

TEXT_CAP = 3000

# W3C private-use-area key codes (WebDriver spec key table) for /fox key.
PUA_KEYS = {
    "null": "\ue000", "cancel": "\ue001", "help": "\ue002",
    "backspace": "\ue003", "tab": "\ue004", "clear": "\ue005",
    "return": "\ue006", "enter": "\ue007", "shift": "\ue008",
    "control": "\ue009", "ctrl": "\ue009", "alt": "\ue00a",
    "pause": "\ue00b", "esc": "\ue00c", "escape": "\ue00c",
    "space": "\ue00d", "pageup": "\ue00e", "pagedown": "\ue00f",
    "end": "\ue010", "home": "\ue011", "left": "\ue012",
    "arrowleft": "\ue012", "up": "\ue013", "arrowup": "\ue013",
    "right": "\ue014", "arrowright": "\ue014", "down": "\ue015",
    "arrowdown": "\ue015", "insert": "\ue016", "delete": "\ue017",
}

SEARCH_ENGINES = {
    "ddg": "https://duckduckgo.com/?q={q}",
    "lite": "https://lite.duckduckgo.com/lite/?q={q}",
    "google": "https://www.google.com/search?q={q}",
    "startpage": "https://www.startpage.com/sp/search?query={q}",
    "marginalia": "https://old-search.marginalia.nu/search?query={q}",
    "mojeek": "https://www.mojeek.com/search?q={q}",
    "wiby": "https://wiby.com/?q={q}",
}


class MarionetteError(Exception):
    """Clean, printable failure (protocol or connection level)."""


# ── Marionette client (pure stdlib socket) ──────────────────────────

class _Marionette:
    """One TCP connection to a Marionette server. NOT thread-safe on
    its own — every use goes through the module lock in _call()."""

    def __init__(self, host, port):
        self.host = host
        self.port = port
        self.sock = socket.create_connection((host, port),
                                             timeout=_CONNECT_TIMEOUT)
        self.sock.settimeout(_CMD_TIMEOUT)
        self._next_id = 0
        self.session_id = None
        # Handshake first: a bare JSON object, length-prefixed.
        hello = self._recv_body()
        if "marionetteProtocol" not in str(hello):
            raise MarionetteError(f"not a Marionette server: {hello!r}")
        err, val = self.cmd("WebDriver:NewSession")
        if err:
            raise MarionetteError(f"NewSession failed: {err.get('message')}")
        if isinstance(val, dict):
            self.session_id = val.get("sessionId")
        # Raw Marionette connections start in CHROME scope; page
        # commands need content scope. NOTE: SetContext takes the
        # param under key "value" (driver.sys.mjs: const {value} =
        # cmd.parameters) — "context" is silently rejected. Best-effort
        # only: page commands still fail (honestly) until the first
        # Navigate replaces the privileged startup window.
        try:
            self.cmd("Marionette:SetContext", {"value": "content"})
        except (MarionetteError, OSError, EOFError):
            pass

    # -- framing ------------------------------------------------------

    def _recv_exact(self, n):
        buf = b""
        while len(buf) < n:
            try:
                chunk = self.sock.recv(n - len(buf))
            except socket.timeout:
                raise MarionetteError(
                    "timed out waiting for Firefox (page still loading?)")
            if not chunk:
                raise EOFError("marionette socket closed")
            buf += chunk
        return buf

    def _recv_body(self):
        """Read one frame: digits, ':', then that many UTF-8 bytes."""
        header = b""
        while not header.endswith(b":"):
            byte = self.sock.recv(1)
            if not byte:
                raise EOFError("marionette socket closed mid-header")
            if not (byte.isdigit() or (header and byte == b":")):
                raise MarionetteError(
                    f"bad frame header from Firefox: {header + byte!r}")
            header += byte
        return json.loads(self._recv_exact(int(header[:-1])).decode("utf-8"))

    def _send_frame(self, obj):
        body = json.dumps(obj, ensure_ascii=True).encode("utf-8")
        # Prefix counts UTF-8 BYTES (packets.sys.mjs ConvertFromUnicode).
        self.sock.sendall(str(len(body)).encode("ascii") + b":" + body)

    # -- protocol -----------------------------------------------------

    def cmd(self, name, params=None):
        """Send one command; return (error_dict_or_None, value_slot)."""
        self._next_id += 1
        self._send_frame([0, self._next_id, name, params or {}])
        pkt = self._recv_body()
        if not (isinstance(pkt, list) and len(pkt) >= 3 and pkt[0] == 1):
            raise MarionetteError(f"unexpected packet from Firefox: {pkt!r}")
        return pkt[2], (pkt[3] if len(pkt) > 3 else None)

    def close(self):
        try:
            self.sock.close()
        except OSError:
            pass


# ── Module state: one connection, one lock ──────────────────────────
# RLock: _fox_tabs/_fox_start hold it across several _call()s, and each
# _call() re-acquires it internally.

_LOCK = threading.RLock()
_CONN = None            # live _Marionette or None
_LAUNCH_PID = None


def _unwrap(val):
    """Most W3C commands reply {"value": X} (verified: the wrapper is
    always exactly one key). FindElements/GetWindowHandles/CloseWindow/
    NewSession return raw structures — those simply pass through."""
    if isinstance(val, dict) and set(val.keys()) == {"value"}:
        return val["value"]
    return val


def _read_state():
    try:
        with open(STATE_FILE, "r", encoding="utf-8") as fh:
            st = json.load(fh)
        if isinstance(st, dict):
            return st
    except (OSError, ValueError):
        pass
    return {}


def _dump_state(st):
    try:
        os.makedirs(FOX_DIR, exist_ok=True)
        with open(STATE_FILE, "w", encoding="utf-8") as fh:
            json.dump(st, fh)
    except OSError:
        pass  # state file is a convenience, never fatal


def _write_state(port, pid, profile=""):
    """Rewrite the volatile fields; PRESERVE other keys (e.g. the
    'enabled' flag persisted by /fox enable) across rewrites."""
    st = _read_state()
    st.update({"port": port, "pid": pid, "profile": profile,
               "started": time.strftime("%Y-%m-%d %H:%M:%S")})
    _dump_state(st)


def _update_state(**fields):
    """Merge fields into state.json (used for /fox enable's
    {"enabled": true} — keeps port/pid/profile/started intact)."""
    st = _read_state()
    st.update(fields)
    _dump_state(st)


def _pid_alive(pid):
    if not pid:
        return False
    try:
        os.kill(int(pid), 0)
        return True
    except (OSError, ValueError, TypeError):
        return False


# ── Running-Firefox detection + graceful close (ENABLE flow ONLY) ────
# No command other than /fox enable may ever signal Firefox; /fox start
# uses _firefox_running() purely to CHOOSE between attaching, launching,
# and printing one honest line — it never kills anything.

def _pgrep(args):
    """Run pgrep; return int pids ([] when pgrep is missing/fails —
    e.g. on Windows, where enable degrades to manual instructions)."""
    try:
        out = subprocess.run(["pgrep"] + args, capture_output=True,
                             text=True, timeout=10).stdout
    except (OSError, subprocess.SubprocessError):
        return []
    return [int(p) for p in out.split() if p.isdigit()]


def _proc_comm(pid):
    """Process name from /proc/<pid>/comm ('' if unreadable/non-Linux).
    Content processes have comms like 'Web Content'/'Socket Process';
    the browser MAIN process is 'firefox' — so a comm check keeps
    profile-scoped kills away from shells (or this REPL!) that merely
    mention a profile path on their command line."""
    try:
        with open(f"/proc/{pid}/comm", "r", encoding="utf-8",
                  errors="replace") as fh:
            return fh.read().strip()
    except OSError:
        return ""


def _firefox_running():
    """True if any Firefox main process is running (pgrep firefox —
    also covers firefox-esr/firefox-bin name variants)."""
    return bool(_pgrep(["firefox"]))


def _firefox_pids_for_cmdline(pattern):
    """Firefox MAIN-process pids whose command line contains `pattern`
    (a --profile PATH or a '-P name'). pgrep -f happily matches shells
    and even this REPL's own command line when they mention the path —
    so keep only pids whose comm starts with 'firefox', never our own
    pid/parent. The '--' guard matters: a '-P name' pattern would
    otherwise be eaten as pgrep OPTIONS (procps -P = parent-pid!)."""
    me, parent = os.getpid(), os.getppid()
    pids = []
    for pid in _pgrep(["-f", "--", pattern]):
        if pid in (me, parent):
            continue
        if _proc_comm(pid).startswith("firefox"):
            pids.append(pid)
    return pids


def _pid_gone(pid):
    """True when pid no longer exists OR is a zombie (a dead child we
    haven't reaped would otherwise make the exit-poll hang)."""
    try:
        os.kill(pid, 0)
    except OSError:
        return True
    try:
        with open(f"/proc/{pid}/stat", "rb") as fh:
            stat = fh.read()
        tail = stat[stat.rindex(b")") + 2:]
        return tail.startswith(b"Z")
    except (OSError, ValueError):
        return False


def _graceful_close_firefox(pattern=None):
    """SIGTERM Firefox and wait for a CLEAN exit (up to TERM_WAIT_SEC;
    never SIGKILL — Firefox saves the session on SIGTERM, which is what
    makes the enable restart tab-safe). pattern=None -> every Firefox
    instance via `pkill -TERM firefox` (the default-profile enable);
    a pattern (profile path / '-P name') -> only instances whose
    command line matches it, so throwaway profiles never touch the
    operator's everyday browser. Returns True if all exited in time."""
    if pattern is None:
        try:
            subprocess.run(["pkill", "-TERM", "firefox"], timeout=10)
        except (OSError, subprocess.SubprocessError) as exc:
            print(f"firefox: could not signal Firefox: {exc}")
            return False
        time.sleep(0.3)
    else:
        for pid in _firefox_pids_for_cmdline(pattern):
            try:
                os.kill(pid, signal.SIGTERM)
            except OSError:
                pass
        time.sleep(0.3)
    deadline = time.time() + TERM_WAIT_SEC
    while time.time() < deadline:
        if pattern is None:
            alive = [p for p in _pgrep(["firefox"]) if not _pid_gone(p)]
        else:
            alive = [p for p in _firefox_pids_for_cmdline(pattern)
                     if not _pid_gone(p)]
        if not alive:
            return True
        for pid in alive:
            try:
                os.waitpid(pid, os.WNOHANG)   # reap if it's OUR child
            except (ChildProcessError, OSError):
                pass
        time.sleep(0.5)
    return False


def _default_port():
    """Port preference: explicit env override > last state file > 2828."""
    env = os.environ.get("PRISM32_FOX_PORT", "").strip()
    if env.isdigit():
        return int(env)
    st = _read_state()
    port = st.get("port")
    if isinstance(port, int) and 0 < port < 65536:
        return port
    return DEFAULT_PORT


def _connect(host=DEFAULT_HOST, port=None):
    """(Re)establish the Marionette connection + session. Raises
    MarionetteError if the browser is not listening."""
    global _CONN
    try:
        _CONN = _Marionette(host, port or _default_port())
    except MarionetteError:
        raise
    except (OSError, socket.timeout) as exc:
        _CONN = None
        raise MarionetteError(
            f"cannot connect to Firefox Marionette at {host}:{port or _default_port()} "
            f"({exc}) — run /fox start")
    return _CONN


def _close_conn():
    global _CONN
    if _CONN is not None:
        try:
            _CONN.close()
        except Exception:
            pass
    _CONN = None


def _call(name, params=None, retry=True):
    """Send a command under the module lock with one auto-reconnect on
    socket errors. Returns the UNWRAPPED result value; raises
    MarionetteError on protocol-level errors."""
    global _CONN
    with _LOCK:
        for attempt in (1, 2):
            if _CONN is None:
                _connect()
            try:
                err, raw = _CONN.cmd(name, params)
            except (OSError, EOFError, MarionetteError) as exc:
                _close_conn()
                if retry and attempt == 1:
                    continue   # auto-reconnect ONCE, then give up
                if isinstance(exc, MarionetteError):
                    raise
                raise MarionetteError(f"connection to Firefox lost: {exc}")
            if err:
                raise MarionetteError(
                    f"{err.get('error', 'error')}: {err.get('message', '')}")
            return _unwrap(raw)
    raise MarionetteError("unreachable")


def _connected():
    return _CONN is not None


def _require_conn():
    if not _connected():
        raise MarionetteError("not connected — run /fox start")


# ── Small helpers used by command bodies ────────────────────────────

def _js(script, args=None):
    """Synchronous JS; returns the plain JS result value."""
    return _call("WebDriver:ExecuteScript",
                 {"script": script, "args": args or []})


def _norm_url(url):
    u = url.strip()
    if re.match(r"^[a-zA-Z][a-zA-Z0-9+.\-]*://", u) or u.startswith("about:"):
        return u
    return "https://" + u


def _page_title():
    return _call("WebDriver:GetTitle")


def _page_url():
    return _call("WebDriver:GetCurrentURL")   # capital URL on 158


def _find_uuid(selector, wait_sec=8.0):
    """Poll until a CSS selector exists, then return the element's bare
    uuid (what element commands expect as 'id')."""
    deadline = time.time() + max(0.0, wait_sec)
    last = None
    while True:
        last = _js("return document.querySelector(arguments[0]) !== null;",
                   [selector])
        if last:
            ref = _call("WebDriver:FindElement",
                        {"using": "css selector", "value": selector})
            if isinstance(ref, dict) and W3C_ELEM_KEY in ref:
                return ref[W3C_ELEM_KEY]
            raise MarionetteError(f"unexpected element reference: {ref!r}")
        if time.time() >= deadline:
            break
        time.sleep(0.25)
    raise MarionetteError(f"no element matches '{selector}'")


def _trim(text, limit=160):
    text = (text or "").strip().replace("\n", " / ")
    return text if len(text) <= limit else text[:limit - 1] + "…"


# ── Shared attach/launch plumbing (start + enable) ───────────────────

def _attach_candidates(port=None):
    """Ports to try attaching to (explicit > env > state file > 2828)."""
    if port is not None:
        return [port]
    candidates = []
    env = os.environ.get("PRISM32_FOX_PORT", "").strip()
    if env.isdigit():
        candidates.append(int(env))
    st_port = _read_state().get("port")
    if isinstance(st_port, int) and st_port not in candidates:
        candidates.append(st_port)
    if DEFAULT_PORT not in candidates:
        candidates.append(DEFAULT_PORT)
    return candidates


def _try_attach(candidates):
    """Attach to the first live Marionette port among `candidates`.
    Sets _CONN/_LAUNCH_PID on success; leaves everything clean on
    failure. Returns the port or None."""
    global _CONN, _LAUNCH_PID
    for cand in candidates:
        try:
            with _LOCK:
                _close_conn()
                _CONN = _Marionette(DEFAULT_HOST, cand)
            _LAUNCH_PID = _read_state().get("pid")
            return cand
        except (MarionetteError, OSError, EOFError):
            _close_conn()
    return None


def _firefox_binary():
    return "/usr/bin/firefox" if os.path.exists("/usr/bin/firefox") else "firefox"


def _spawn_firefox(argv):
    """Detach-launch Firefox (new session: it survives the REPL)."""
    try:
        return subprocess.Popen(
            argv, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
            stdin=subprocess.DEVNULL, start_new_session=True)
    except OSError as exc:
        print(f"firefox: failed to launch Firefox: {exc}")
        return None


def _wait_attach(port, timeout=25.0, proc=None):
    """Poll until Marionette answers on `port`; sets _CONN. Returns
    True/False. Gives up early if the launcher process itself died
    (e.g. 'Firefox is already running' delegation exits instantly)."""
    global _CONN
    deadline = time.time() + timeout
    while time.time() < deadline:
        try:
            with _LOCK:
                _close_conn()
                _CONN = _Marionette(DEFAULT_HOST, port)
            return True
        except (MarionetteError, OSError, EOFError):
            _close_conn()
            if proc is not None and proc.poll() is not None:
                return False
            time.sleep(0.5)
    return False


# ── Command bodies (each PRINTS its result, returns None) ──────────

def _fox_start(rest):
    """Attach to a running Marionette port, else launch Firefox with
    --marionette and attach to that. NEVER closes Firefox: if the
    everyday Firefox is running without control, say the one honest
    line and stop."""
    global _CONN, _LAUNCH_PID
    tokens = rest.split()
    profile = None
    port = None
    gui = None
    i = 0
    while i < len(tokens):
        tok = tokens[i]
        if tok.startswith("port="):
            if not tok[5:].isdigit():
                print(f"firefox: bad port '{tok[5:]}'")
                return
            port = int(tok[5:])
        elif tok in ("headless", "gui", "visible"):
            gui = tok in ("gui", "visible")
        else:
            if profile is not None:
                print(f"firefox: unexpected extra argument '{tok}' "
                      f"(usage: /fox start [default|<profile>] [port=N])")
                return
            profile = tok
        i += 1

    cand = _try_attach(_attach_candidates(port))
    if cand is not None:
        _write_state(cand, _LAUNCH_PID,
                     profile if profile else _read_state().get("profile", ""))
        print(f"firefox: attached to running Firefox on port {cand}")
        _print_status_body()
        _print_real_session_hint()
        return

    # Nothing to attach to.
    is_default = profile in (None, "default")
    is_path = (profile is not None and not is_default
               and os.path.isdir(profile))

    if port is not None and not is_path:
        print("firefox: a custom port (port=N) can only be used with an "
              "explicit profile PATH (we won't write prefs into your real "
              "profile). Run /fox start <profile-path> port=N, or omit "
              "port= to use 2828.")
        return

    # The everyday Firefox is already running WITHOUT control: never
    # launch into it, never close it — just the one honest line.
    if is_default and _firefox_running():
        print("firefox: Firefox is running without control enabled — run "
              "`/fox enable` (one-time; tabs are restored)")
        return

    if is_path:
        # Only explicit throwaway paths may pick a port (we write the
        # marionette.port pref into that profile's user.js — the CLI
        # --marionette-port flag is ignored by Firefox 158, verified).
        launch_port = port if port is not None else (
            _attach_candidates()[0] if _attach_candidates() else DEFAULT_PORT)
    else:
        # 'default' / named profiles: never modified, so their port is
        # always the pref default (2828). An env-var port only helps
        # the ATTACH step above, never the launch.
        launch_port = DEFAULT_PORT

    ff = _firefox_binary()
    argv = [ff, "--marionette"]

    if is_default:
        # No profile flag at all: Firefox opens its own DEFAULT profile,
        # so the operator's logins/cookies apply (see firefox --help:
        # -P selects by name, --profile takes a path; omitting both
        # uses the default profile).
        pass
    elif is_path:
        argv += ["--profile", profile]
        if launch_port != DEFAULT_PORT:
            _write_port_pref(profile, launch_port)
        if gui is None:
            gui = False            # throwaway/test profiles: headless by default
    else:
        argv += ["-P", profile]    # named profile
        if gui is None:
            gui = True            # it's a real profile — show the window

    if gui is False:
        argv += ["--headless"]

    proc = _spawn_firefox(argv)
    if proc is None:
        return

    print(f"firefox: launching: {' '.join(argv[1:])} "
          f"(pid {proc.pid}); waiting for port {launch_port}...")
    attached = _wait_attach(launch_port, proc=proc)

    if not attached:
        _close_conn()
        if is_default:
            hint = ("run /fox enable (one-time) — it restarts Firefox "
                    "once, with your tabs restored, and never again.")
        else:
            hint = ("a Firefox with that profile may already be running "
                    "without control — close it yourself, or run "
                    "/fox enable <profile-path>.")
        print(f"firefox: could not reach Marionette on port {launch_port} "
              f"after 25s. {hint}")
        return

    _LAUNCH_PID = proc.pid
    _write_state(launch_port, proc.pid,
                 profile if profile else "default")
    print(f"firefox: Firefox launched and attached on port {launch_port} "
          f"(pid {proc.pid})")
    _print_status_body()
    _print_real_session_hint()


def _write_port_pref(profile_path, port):
    """Set marionette.port via the profile's user.js — ONLY for explicit
    throwaway profile paths (never for the operator's real profile).
    The --marionette-port CLI flag is ignored by Firefox 158 (verified),
    so this pref is the only way to pick a non-default port."""
    try:
        os.makedirs(profile_path, exist_ok=True)
        userjs = os.path.join(profile_path, "user.js")
        line = f'user_pref("marionette.port", {int(port)});\n'
        existing = ""
        if os.path.exists(userjs):
            with open(userjs, "r", encoding="utf-8") as fh:
                existing = fh.read()
        if f'marionette.port", {int(port)}' not in existing:
            with open(userjs, "a", encoding="utf-8") as fh:
                fh.write(line)
    except OSError as exc:
        print(f"firefox: could not write marionette.port pref into "
              f"{profile_path}: {exc}")


# ── Desktop-entry patch (make --marionette PERMANENT, one-time) ──────
# Copy the system firefox .desktop into the user applications dir
# (same filename => overrides the system entry) with ` --marionette`
# added to every Exec line. Guarded by the DESKTOP_MARKER comment so a
# second run never double-appends; refuses to touch a user file it did
# not create; prints manual instructions on macOS/Windows or when no
# .desktop exists.

_DESKTOP_NAMES = (
    "firefox.desktop", "org.mozilla.firefox.desktop",
    "firefox-esr.desktop", "org.mozilla.firefox_esr.desktop",
    "mozilla-firefox.desktop", "firefox snap.desktop",
)


def _desktop_data_dirs():
    """System application dirs to search (honors XDG_DATA_DIRS so this
    is testable with a staged dummy tree)."""
    dirs = []
    xdd = os.environ.get("XDG_DATA_DIRS", "")
    for d in (xdd.split(os.pathsep) if xdd else []):
        if d:
            dirs.append(os.path.join(d, "applications"))
    for d in ("/usr/local/share/applications", "/usr/share/applications"):
        if d not in dirs:
            dirs.append(d)
    return dirs


def _user_applications_dir():
    """Where the patched override goes (honors XDG_DATA_HOME)."""
    xdh = os.environ.get("XDG_DATA_HOME", "").strip()
    base = xdh if xdh else os.path.join(os.path.expanduser("~"),
                                        ".local", "share")
    return os.path.join(base, "applications")


def _find_system_desktop():
    """Locate the system firefox .desktop; None if there isn't one."""
    for d in _desktop_data_dirs():
        for name in _DESKTOP_NAMES:
            path = os.path.join(d, name)
            if os.path.isfile(path):
                return path
    # Fallback: any .desktop in a system dir whose Exec runs firefox.
    for d in _desktop_data_dirs():
        try:
            names = sorted(os.listdir(d))
        except OSError:
            continue
        for name in names:
            if not name.endswith(".desktop"):
                continue
            path = os.path.join(d, name)
            try:
                with open(path, "r", encoding="utf-8",
                          errors="replace") as fh:
                    text = fh.read(200000)
            except OSError:
                continue
            if re.search(r"^Exec=\S*firefox\b", text, re.M):
                return path
    return None


def _marionette_exec(line):
    """One 'Exec=...' line with ` --marionette` inserted at the right
    position: right after the executable — or, for wrappers, after the
    real target:  env VAR=V /snap/bin/firefox  ->  after that firefox;
    flatpak run --flags org.mozilla.firefox  ->  after the app id (a
    flag before the id would go to flatpak itself). Already-flagged
    lines and non-Exec lines pass through unchanged."""
    if not line.startswith("Exec=") or "--marionette" in line:
        return line
    tokens = line[len("Exec="):].split()
    if not tokens:
        return line
    i = 0
    if os.path.basename(tokens[0]) == "env":     # env VAR=VAL <cmd> ...
        i = 1
        while i < len(tokens) and "=" in tokens[i]:
            i += 1
    if i < len(tokens) and os.path.basename(tokens[i]) in ("flatpak",
                                                           "snap"):
        i += 1
        while i < len(tokens) and (tokens[i] == "run"
                                   or tokens[i].startswith("-")):
            i += 1
        i += 1                                  # after the app id
    else:
        i += 1                                  # after the executable
    tokens.insert(min(i, len(tokens)), "--marionette")
    return "Exec=" + " ".join(tokens)


def _print_manual_launcher_instructions():
    """What we print where the .desktop patch can't apply (macOS,
    Windows, unusual Linux setups): honest, actionable, undo-free."""
    plat = sys.platform
    if plat.startswith("win") or plat == "cygwin":
        print("firefox: no automatic launcher patch on Windows — one-time")
        print("  manual step: right-click your Firefox shortcut ->")
        print("  Properties -> Target field, append:  --marionette")
        print('  e.g.  "C:\\Program Files\\Mozilla Firefox\\firefox.exe"'
              " --marionette")
    elif plat == "darwin":
        print("firefox: no automatic launcher patch on macOS — one-time")
        print("  manual step: launch Firefox with control enabled via")
        print("      open -a Firefox --args --marionette")
        print("  (save that as a small .command file / Dock item to make")
        print("  it permanent; undo = launch normally again)")
    else:
        print("firefox: no firefox .desktop found — one-time manual step:")
        print("  add ` --marionette` to your Firefox launcher command so")
        print("  future starts have control enabled. Undo: remove it.")


def _patch_desktop_entry():
    """The permanence step of /fox enable. PRINTS what happened (or the
    manual instructions); never raises; idempotent via DESKTOP_MARKER."""
    if not sys.platform.startswith("linux"):
        _print_manual_launcher_instructions()
        return
    src = _find_system_desktop()
    if src is None:
        _print_manual_launcher_instructions()
        return
    dest = os.path.join(_user_applications_dir(), os.path.basename(src))
    if os.path.exists(dest):
        try:
            with open(dest, "r", encoding="utf-8", errors="replace") as fh:
                current = fh.read()
        except OSError as exc:
            print(f"firefox: could not check existing launcher: {exc}")
            return
        if DESKTOP_MARKER in current:
            print(f"firefox: launcher already patched — nothing to do "
                  f"({dest})")
            print("  undo: delete that file (the system launcher takes "
                  "over again)")
        else:
            print(f"firefox: {dest} already exists and was NOT created by "
                  "/fox enable — leaving it alone.")
            print("  to make control permanent, add ` --marionette` to its "
                  "Exec line(s) yourself.")
        return
    try:
        with open(src, "r", encoding="utf-8", errors="replace") as fh:
            text = fh.read()
    except OSError as exc:
        print(f"firefox: could not read {src}: {exc}")
        return
    out_lines = [_marionette_exec(ln) for ln in text.splitlines()]
    patched = sum(1 for a, b in zip(text.splitlines(), out_lines)
                  if a != b)
    new_text = "\n".join(out_lines) + (
        f"\n{DESKTOP_MARKER}: --marionette added by /fox enable "
        "(delete this file to undo)\n")
    try:
        os.makedirs(os.path.dirname(dest), exist_ok=True)
        with open(dest, "w", encoding="utf-8") as fh:
            fh.write(new_text)
    except OSError as exc:
        print(f"firefox: could not write {dest}: {exc}")
        return
    print(f"firefox: launcher patched (permanent): {dest}")
    print(f"  (copied from {src}; added --marionette to {patched} "
          "Exec line(s))")
    print("  undo: delete that file — the system launcher takes over "
          "again; or remove the flag from its Exec lines.")


def _print_real_session_hint():
    """Post-attach/launch tip. After /fox enable the state file says so
    and this stays silent — the tip only nudges the ONE-TIME enable."""
    if _read_state().get("enabled"):
        return
    print("  tip: /fox enable (one-time) makes your normal Firefox launcher")
    print("  start with control enabled — your tabs and logins stay put.")


def _fox_enable(rest):
    """/fox enable — the ONE-TIME permanent enable. The ONLY flow that
    ever closes Firefox, and it does it exactly once, gracefully. For
    the default profile it drives the operator's EVERYDAY Firefox (all
    logins, all tabs); a --profile PATH (or '-P name') scopes the
    restart to that profile's instances, so throwaway profiles never
    touch the everyday browser."""
    global _LAUNCH_PID
    tokens = rest.split()
    profile = None
    port = None
    gui = None
    now = False
    i = 0
    while i < len(tokens):
        tok = tokens[i]
        if tok == "now":
            now = True               # skip the Enter confirmation (automation)
        elif tok.startswith("port="):
            if not tok[5:].isdigit():
                print(f"firefox: bad port '{tok[5:]}'")
                return
            port = int(tok[5:])
        elif tok in ("headless", "gui", "visible"):
            gui = tok in ("gui", "visible")
        else:
            if profile is not None:
                print(f"firefox: unexpected extra argument '{tok}' "
                      "(usage: /fox enable [now] "
                      "[default|<profile-path>] [port=N])")
                return
            profile = tok
        i += 1

    is_default = profile in (None, "default")
    is_path = (profile is not None and not is_default
               and os.path.isdir(profile))

    if port is not None and not is_path:
        print("firefox: a custom port (port=N) can only be used with an "
              "explicit profile PATH (we won't write prefs into your real "
              "profile). Run /fox enable <profile-path> port=N, or omit "
              "port= to use 2828.")
        return

    # (a) A Marionette port is already live: already enabled — attach,
    # keep it permanent (idempotent patch), persist, done.
    cand = _try_attach(_attach_candidates(port))
    if cand is not None:
        label = profile if is_path else (
            _read_state().get("profile") or "default")
        _write_state(cand, _read_state().get("pid"), label)
        _update_state(enabled=True)
        print(f"firefox: already enabled — attached to running Firefox "
              f"on port {cand}")
        _print_status_body()
        _patch_desktop_entry()
        return

    # (b) Firefox running WITHOUT control? Scope the check to the
    # profile we were asked about (default = any firefox process).
    if is_path:
        pattern = profile
        running = bool(_firefox_pids_for_cmdline(pattern))
    elif profile is not None:
        pattern = f"-P {profile}"
        running = bool(_firefox_pids_for_cmdline(pattern))
    else:
        pattern = None
        running = _firefox_running()

    if running and not now:
        if not sys.stdin.isatty():
            # Non-interactive context: NEVER kill anything. Instruct.
            print(f"firefox: {ENABLE_NOTICE}")
            print("  (stdin is not interactive, so Firefox was NOT "
                  "closed — re-run /fox enable in your terminal to "
                  "confirm the one-time restart, or use '/fox enable "
                  "now' to skip the confirmation)")
            return
        print(f"firefox: {ENABLE_NOTICE}")
        try:
            input()
        except KeyboardInterrupt:
            print("firefox: cancelled — Firefox was NOT closed")
            return
        except (EOFError, OSError) as exc:
            print(f"firefox: could not read confirmation ({exc!r}) — "
                  "Firefox was NOT closed; retry /fox enable")
            return

    # (c) Graceful close — SIGTERM, wait for a CLEAN exit (session
    # saved; never SIGKILL, never from any other command).
    if running:
        print("firefox: closing Firefox gracefully (SIGTERM — session "
              "saved, tabs come back on the relaunch)...")
        if not _graceful_close_firefox(pattern):
            print(f"firefox: Firefox did not finish exiting within "
                  f"{int(TERM_WAIT_SEC)}s (a save dialog?). Nothing was "
                  "relaunched — close it and run /fox enable again.")
            return

    # (d) Relaunch detached WITH control (default profile: the visible
    # everyday browser; explicit path: headless unless asked otherwise).
    argv = [_firefox_binary(), "--marionette",
            "--marionette-allow-origins", "*"]
    if is_default:
        label = "default"
        gui = True
    elif is_path:
        argv += ["--profile", profile]
        label = profile
        if port is not None and port != DEFAULT_PORT:
            _write_port_pref(profile, port)
        if gui is None:
            gui = False               # throwaway/test profiles: headless
    else:
        argv += ["-P", profile]       # named profile
        label = profile
        if gui is None:
            gui = True                # a real profile — show the window
    if gui is False:
        argv += ["--headless"]

    if is_path:
        launch_port = port if port is not None else (
            _attach_candidates()[0] if _attach_candidates()
            else DEFAULT_PORT)
    else:
        launch_port = DEFAULT_PORT

    proc = _spawn_firefox(argv)
    if proc is None:
        return
    verb = ("relaunched" if running else "launched")
    print(f"firefox: {verb} with control enabled: "
          f"{' '.join(argv[1:])} (pid {proc.pid}); waiting for port "
          f"{launch_port}...")
    attached = _wait_attach(launch_port, proc=proc)

    # (f) Persist the enable the moment control is verified live.
    if attached:
        _LAUNCH_PID = proc.pid
        _write_state(launch_port, proc.pid, label)
        _update_state(enabled=True)

    # (e) Make it PERMANENT for future normal launches (idempotent;
    # prints what was patched or the manual instructions).
    _patch_desktop_entry()

    if attached:
        print(f"firefox: enabled — attached to Firefox on port "
              f"{launch_port} (pid {proc.pid}); enabled for good: future "
              "normal launches have control too")
        _print_status_body()
    else:
        _close_conn()
        print(f"firefox: Firefox {verb}, but Marionette on port "
              f"{launch_port} did not answer within 25s. The launcher is "
              "patched, so its next start has control — attach later "
              "with /fox start.")


def _print_status_body():
    if not _connected():
        return
    try:
        url = _page_url()
        title = _page_title()
        pid = _LAUNCH_PID or _read_state().get("pid")
        print(f"  pid:   {pid if pid else '?'}")
        print(f"  url:   {url}")
        print(f"  title: {title}")
    except MarionetteError as exc:
        if "privileged scope" in str(exc):
            # Fresh browser: the startup window is privileged; page
            # info appears after the first /fox open.
            print("  pid:   "
                  f"{_LAUNCH_PID or _read_state().get('pid') or '?'}")
            print("  page:  (fresh window — no content page yet; "
                  "run /fox open <url>)")
        else:
            print(f"  (page info unavailable: {exc})")


def _fox_status(rest):
    st = _read_state()
    if _connected():
        print(f"firefox: connected to {_CONN.host}:{_CONN.port}")
        _print_status_body()
    else:
        port = st.get("port")
        pid = st.get("pid")
        print("firefox: not connected — run /fox start")
        if port:
            alive = "running" if _pid_alive(pid) else "not running"
            print(f"  (state file: port {port}, pid {pid or '?'} — {alive})")
    if st.get("enabled"):
        print("  enabled: launcher starts Firefox with control "
              "(/fox enable was run)")


def _fox_open(rest):
    _require_conn()
    if not rest.strip():
        print("firefox: usage: /fox open <url>")
        return
    url = _norm_url(rest)
    _call("WebDriver:Navigate", {"url": url})
    time.sleep(0.3)   # let settle-onload JS run
    print(f"firefox: opened {_page_url()}")
    print(f"  title: {_page_title()}")


def _fox_back(rest):
    _require_conn()
    _call("WebDriver:Back", {})
    print(f"firefox: back — {_page_url()}")
    print(f"  title: {_page_title()}")


def _fox_forward(rest):
    _require_conn()
    _call("WebDriver:Forward", {})
    print(f"firefox: forward — {_page_url()}")
    print(f"  title: {_page_title()}")


def _fox_reload(rest):
    _require_conn()
    _call("WebDriver:Refresh", {})
    print(f"firefox: reloaded — {_page_url()}")
    print(f"  title: {_page_title()}")


def _fox_stopload(rest):
    """No WebDriver:Stop exists on 158 (verified) — window.stop() is the
    honest equivalent."""
    _require_conn()
    _js("window.stop(); return true;")
    print("firefox: stop requested (window.stop())")


def _fox_title(rest):
    _require_conn()
    print(_page_title())


def _fox_url(rest):
    _require_conn()
    print(_page_url())


def _fox_text(rest):
    _require_conn()
    sel = rest.strip()
    if sel:
        body = _js(
            "var el = document.querySelector(arguments[0]); "
            "return el ? el.innerText : null;", [sel])
        if body is None:
            print(f"firefox: no element matches '{sel}'")
            return
    else:
        body = _js("return (document.body && document.body.innerText) || "
                   "(document.documentElement && document.documentElement.innerText) || '';")
    if len(body) > TEXT_CAP:
        print(body[:TEXT_CAP])
        print(f"[... {len(body)} chars total — call with a narrower "
              f"selector for more, e.g. /fox text main, or /fox read N]")
    else:
        print(body if body.strip() else "(no visible text)")


def _fox_read(rest):
    _require_conn()
    cap = TEXT_CAP
    if rest.strip():
        try:
            cap = max(200, min(60000, int(rest.strip())))
        except ValueError:
            print("firefox: max_chars must be a number — usage: "
                  "/fox read [max_chars]")
            return
    body = _js("return (document.body && document.body.innerText) || "
               "(document.documentElement && document.documentElement.innerText) || '';")
    if not body.strip():
        print("(no visible text on this page)")
        return
    if len(body) <= cap:
        print(body)
        return
    # Smart cap: head-biased head+tail window (leads usually carry the
    # content, feet often hold the conclusion; the middle is boilerplate).
    head = body[:int(cap * 0.7)]
    tail = body[-int(cap * 0.3):]
    skipped = len(body) - len(head) - len(tail)
    print(head)
    print(f"\n[... {skipped} middle chars skipped — /fox read {min(60000, len(body))} "
          f"for the whole page, or /fox find <css> to narrow ...]\n")
    print(tail)
    print(f"\n[page text: {len(body)} chars total, showing ~{cap}]")


def _fox_find(rest):
    _require_conn()
    tokens = rest.split(None, 1)
    if not tokens:
        print("firefox: usage: /fox find <css> [text|count|href|value]")
        return
    sel = tokens[0]
    mode = tokens[1].strip().lower() if len(tokens) > 1 else "text"
    if mode not in ("text", "count", "href", "value"):
        print(f"firefox: unknown mode '{mode}' (use text|count|href|value)")
        return
    result = _js(
        "var els = document.querySelectorAll(arguments[0]);"
        "var mode = arguments[1];"
        "var out = [];"
        "for (var i = 0; i < els.length && i < 5; i++) {"
        "  var e = els[i];"
        "  if (mode == 'href') out.push(e.href || '');"
        "  else if (mode == 'value') out.push(e.value || '');"
        "  else out.push(e.textContent || '');"
        "}"
        "return [els.length, out];", [sel, mode])
    count, sample = result if isinstance(result, list) else (0, [])
    print(f"firefox: {count} match{'es' if count != 1 else ''} for '{sel}'")
    for idx, item in enumerate(sample, 1):
        print(f"  {idx}. {_trim(str(item))}")
    if count > len(sample):
        print(f"  [... {count - len(sample)} more — /fox find with a "
              f"narrower selector]")


def _fox_click(rest):
    _require_conn()
    tokens = rest.split(None, 1)
    if not tokens:
        print("firefox: usage: /fox click <css> [n]  (n is 1-based)")
        return
    sel = tokens[0]
    n = 1
    if len(tokens) > 1 and tokens[1].strip():
        try:
            n = int(tokens[1].strip())
        except ValueError:
            print(f"firefox: n must be a number, got '{tokens[1].strip()}'")
            return
    # Waits for it to exist first (spec): poll up to 10s.
    deadline = time.time() + 10.0
    while True:
        exists = _js(
            "return document.querySelector(arguments[0]) !== null;", [sel])
        if exists:
            break
        if time.time() >= deadline:
            print(f"firefox: no element matches '{sel}' after 10s")
            return
        time.sleep(0.25)
    refs = _call("WebDriver:FindElements",
                 {"using": "css selector", "value": sel})
    refs = refs if isinstance(refs, list) else []
    if len(refs) < n or n < 1:
        print(f"firefox: only {len(refs)} element(s) match '{sel}' — "
              f"cannot click match {n}")
        return
    uuid = refs[n - 1].get(W3C_ELEM_KEY) if isinstance(refs[n - 1], dict) else None
    if not uuid:
        print(f"firefox: unexpected element reference {refs[n-1]!r}")
        return
    _call("WebDriver:ElementClick", {"id": uuid})
    time.sleep(0.4)   # let a navigation or handler settle
    print(f"firefox: clicked '{sel}' (match {n} of {len(refs)})")
    print(f"  now at: {_page_title()}")
    print(f"  url:    {_page_url()}")


def _fox_type(rest):
    _require_conn()
    tokens = rest.split(None, 1)
    if not tokens:
        print("firefox: usage: /fox type <css> <text...>")
        return
    sel = tokens[0]
    text = tokens[1] if len(tokens) > 1 else ""
    uuid = _find_uuid(sel, wait_sec=8.0)
    # ElementSendKeys APPENDS (verified on 158) — clear first.
    _call("WebDriver:ElementClear", {"id": uuid})
    try:
        _call("WebDriver:ElementSendKeys", {"id": uuid, "text": text})
    except MarionetteError:
        # Native keys can be refused on odd widgets; fall back to a JS
        # value set + input/change events (keeps frameworks happy).
        _js(
            "var el = document.querySelector(arguments[0]);"
            "var proto = el instanceof HTMLTextAreaElement"
            "  ? HTMLTextAreaElement.prototype : HTMLInputElement.prototype;"
            "var d = Object.getOwnPropertyDescriptor(proto, 'value');"
            "if (d && d.set) d.set.call(el, arguments[1]);"
            "else el.value = arguments[1];"
            "el.dispatchEvent(new Event('input', {bubbles: true}));"
            "el.dispatchEvent(new Event('change', {bubbles: true}));"
            "return true;", [sel, text])
    value = _js("var el = document.querySelector(arguments[0]); "
                "return el ? (el.value !== undefined ? el.value : "
                "el.textContent) : null;", [sel])
    print(f"firefox: typed into '{sel}' — value now: {_trim(str(value), 300)}")


def _fox_key(rest):
    _require_conn()
    name = rest.strip()
    if not name:
        print("firefox: usage: /fox key <Enter|Tab|Esc|Backspace|Space|"
              "ArrowDown|...|single char>")
        return
    key = PUA_KEYS.get(name.lower(), name if len(name) == 1 else None)
    if key is None:
        print(f"firefox: unknown key '{name}' — known: "
              f"{', '.join(sorted(PUA_KEYS))}")
        return
    _call("WebDriver:PerformActions", {"actions": [
        {"type": "key", "id": "fox-kbd", "actions": [
            {"type": "keyDown", "value": key},
            {"type": "keyUp", "value": key},
        ]}]})
    _call("WebDriver:ReleaseActions", {})
    print(f"firefox: sent key {name!r} to the page")


def _fox_scroll(rest):
    _require_conn()
    tokens = rest.split()
    where = tokens[0].lower() if tokens else "down"
    amount = 600
    if len(tokens) > 1:
        try:
            amount = int(tokens[1])
        except ValueError:
            print(f"firefox: bad amount '{tokens[1]}'")
            return
    if where not in ("down", "up", "top", "bottom", "px"):
        print("firefox: usage: /fox scroll <down|up|top|bottom|px> [n]")
        return
    result = _js(
        "var dir = arguments[0], amt = arguments[1];"
        "var h = Math.max(document.body ? document.body.scrollHeight : 0,"
        "                document.documentElement.scrollHeight);"
        "var y;"
        "if (dir == 'top') y = 0;"
        "else if (dir == 'bottom') y = h;"
        "else if (dir == 'down') y = window.scrollY + amt;"
        "else if (dir == 'up') y = window.scrollY - amt;"
        "else y = amt;"
        "window.scrollTo(0, Math.max(0, Math.min(y, h)));"
        "return [window.scrollY, h];", [where, amount])
    y, h = result if isinstance(result, list) else (None, None)
    print(f"firefox: scrolled to y={y} (page height {h})")


def _fox_js(rest):
    _require_conn()
    script = rest.strip()
    if not script:
        print("firefox: usage: /fox js <script>")
        return
    value = _call("WebDriver:ExecuteScript", {"script": script, "args": []})
    try:
        printed = json.dumps(value, ensure_ascii=False, indent=None,
                             default=str)
    except (TypeError, ValueError):
        printed = str(value)
    print(printed if printed.strip() else "(no result)")


def _fox_shot(rest):
    _require_conn()
    tokens = rest.split()
    name = None
    view = False
    for tok in tokens:
        if tok.lower() in ("view", "viewport"):
            view = True
        elif name is None:
            name = tok
    if name is None or not re.fullmatch(r"[A-Za-z0-9_\-]+", name or ""):
        name = "shot_" + time.strftime("%Y%m%d_%H%M%S")
    b64 = _call("WebDriver:TakeScreenshot",
                {"id": None, "full": not view, "hash": False, "scroll": True})
    try:
        raw = base64.b64decode(b64)
        if not raw.startswith(b"\x89PNG"):
            raise ValueError("not a PNG payload")
        os.makedirs(FOX_DIR, exist_ok=True)
        path = os.path.join(FOX_DIR, f"{name}.png")
        with open(path, "wb") as fh:
            fh.write(raw)
        print(f"firefox: screenshot saved: {path} ({len(raw)} bytes)")
    except (OSError, ValueError, TypeError) as exc:
        print(f"firefox: screenshot failed: {exc}")


def _fox_tabs(rest):
    _require_conn()
    with _LOCK:
        handles = _call("WebDriver:GetWindowHandles")
        try:
            current = _call("WebDriver:GetWindowHandle")
        except MarionetteError:
            current = None
        rows = []
        for idx, handle in enumerate(handles, 1):
            try:
                _call("WebDriver:SwitchToWindow", {"handle": handle,
                                                   "focus": True})
                title = _page_title()
                url = _page_url()
            except MarionetteError as exc:
                title, url = f"(unreadable: {exc})", ""
            rows.append((idx, handle, title, url))
        if current:
            try:
                _call("WebDriver:SwitchToWindow", {"handle": current,
                                                   "focus": True})
            except MarionetteError:
                pass
    print(f"firefox: {len(rows)} tab(s)")
    for idx, handle, title, url in rows:
        mark = "*" if handle == current else " "
        print(f" {mark} {idx}. {_trim(title, 80)}")
        print(f"      {url}")


def _fox_tab(rest):
    _require_conn()
    arg = rest.strip()
    if not arg.isdigit():
        print("firefox: usage: /fox tab <n>  (1-based; see /fox tabs)")
        return
    n = int(arg)
    handles = _call("WebDriver:GetWindowHandles")
    if not (1 <= n <= len(handles)):
        print(f"firefox: there are {len(handles)} tab(s) — no tab {n}")
        return
    _call("WebDriver:SwitchToWindow", {"handle": handles[n - 1],
                                       "focus": True})
    print(f"firefox: switched to tab {n}: {_page_title()}")
    print(f"  url: {_page_url()}")


def _fox_closetab(rest):
    _require_conn()
    arg = rest.strip()
    if not arg.isdigit():
        print("firefox: usage: /fox closetab <n>  (1-based; see /fox tabs)")
        return
    n = int(arg)
    handles = _call("WebDriver:GetWindowHandles")
    if not (1 <= n <= len(handles)):
        print(f"firefox: there are {len(handles)} tab(s) — no tab {n}")
        return
    target = handles[n - 1]
    _call("WebDriver:SwitchToWindow", {"handle": target, "focus": True})
    remaining = _call("WebDriver:CloseWindow")
    remaining = remaining if isinstance(remaining, list) else []
    print(f"firefox: closed tab {n} — {len(remaining)} tab(s) left")
    if not remaining:
        print("  (that was the last window — Firefox may have quit; "
              "commands will say if it's gone)")
        return
    survivor = handles[n - 2] if n >= 2 else remaining[0]
    if survivor not in remaining:
        survivor = remaining[0]
    _call("WebDriver:SwitchToWindow", {"handle": survivor, "focus": True})
    print(f"  now on: {_page_title()}")
    print(f"  url:    {_page_url()}")


def _fox_wait(rest):
    _require_conn()
    tokens = rest.split()
    if not tokens:
        print("firefox: usage: /fox wait <css> [timeout_sec]")
        return
    sel = tokens[0]
    timeout = 10.0
    if len(tokens) > 1:
        try:
            timeout = max(0.0, float(tokens[1]))
        except ValueError:
            print(f"firefox: bad timeout '{tokens[1]}'")
            return
    start = time.time()
    while True:
        found = _js("return document.querySelector(arguments[0]) !== null;",
                    [sel])
        if found:
            print(f"firefox: '{sel}' appeared after "
                  f"{time.time() - start:.1f}s")
            return
        if time.time() - start >= timeout:
            print(f"firefox: '{sel}' NOT found within {timeout:.0f}s")
            return
        time.sleep(0.3)


def _fox_search(rest):
    _require_conn()
    tokens = rest.split(None, 1)
    if len(tokens) < 2:
        print("firefox: usage: /fox search <engine> <query> — engines: "
              + ", ".join(sorted(SEARCH_ENGINES)))
        return
    engine = tokens[0].lower()
    query = tokens[1].strip()
    if engine not in SEARCH_ENGINES:
        print(f"firefox: unknown engine '{engine}' — use one of: "
              + ", ".join(sorted(SEARCH_ENGINES)))
        return
    url = SEARCH_ENGINES[engine].replace("{q}", quote_plus(query))
    _call("WebDriver:Navigate", {"url": url})
    time.sleep(0.5)
    print(f"firefox: searched {engine} for '{query}'")
    print(f"  title: {_page_title()}")
    snippet = _js("return (document.body && document.body.innerText) || '';")
    snippet = (snippet or "").strip()
    if snippet:
        print(f"  first text: {_trim(snippet, 400)}")


def _fox_disconnect(rest):
    """'stop' serves two spec'd meanings: bare '/fox stop' closes the
    connection (browser keeps running — verified: the Marionette server
    accepts a fresh connection later); '/fox stop load' stops the page
    load (the nav-group 'stop')."""
    global _LAUNCH_PID
    if rest.strip().lower() in ("load", "loading"):
        _fox_stopload("")
        return
    with _LOCK:
        port = _CONN.port if _CONN else None
        _close_conn()
    print(f"firefox: connection closed"
          + (f" (Firefox still running on port {port})" if port else "")
          + " — /fox start reattaches anytime")


def _fox_help(rest):
    print(_USAGE)


_USAGE = """firefox browser commands (/fox or /firefox):
  enable [now] [default|<profile-path>] [port=N]
                              ONE-TIME permanent enable. If Firefox is
                              already controllable: 'already enabled' +
                              attach. If Firefox is running without
                              control: asks (Enter) for ONE graceful
                              restart — session restore brings your
                              tabs back — then relaunches it with
                              --marionette and patches your launcher
                              (.desktop) so every future start has
                              control. 'now' skips the Enter wait
                              (automation). Non-interactive contexts
                              never close Firefox. No other /fox command
                              ever closes Firefox. Undo: delete the
                              patched launcher file (path is printed).
  start [default|<profile-path>] [port=N] [gui|headless]
                              attach to a running Marionette port, else
                              launch Firefox with --marionette. 'default'
                              or no argument = your real default profile
                              (logins/cookies apply). If Firefox is
                              already running WITHOUT control it just
                              says to run /fox enable once. A profile
                              PATH is headless by default and may set
                              port=N (via user.js).
  status                      honest connection report (url/title/pid)
  open <url>                  navigate; waits for load; prints url+title
  back | forward | reload | stop load
  url | title                 current page URL / title
  text [css]                  page (or element) innerText, ~3000 char cap
  read [max_chars]            page text with a smart head+tail cap
  find <css> [text|count|href|value]
                              count + first matches
  click <css> [n]             click nth match (1-based); waits for it
  type <css> <text...>        clear the field, then type
  key <Enter|Tab|Esc|...>     send one key to the page
  scroll <down|up|top|bottom|px> [amount]
  js <script>                 sync JS; prints the returned value
  shot [name] [view]          screenshot -> ~/.prism32/firefox/<name>.png
  tabs                        list tabs (titles + current tab marked)
  tab <n>                     switch to tab n (1-based)
  closetab <n>                close tab n, land on a neighbour
  wait <css> [timeout_sec]    poll for a selector
  search <engine> <query>     engines: ddg, lite, google, startpage,
                              marginalia, mojeek, wiby
  stop                        close the connection (browser keeps running)
  stopload                    stop the current page load (window.stop)"""


# ── Dispatch ─────────────────────────────────────────────────────────

_SUBCOMMANDS = {
    "start": _fox_start,
    "enable": _fox_enable,
    "status": _fox_status,
    "open": _fox_open,
    "nav": _fox_open,          # friendly alias
    "navigate": _fox_open,
    "back": _fox_back,
    "forward": _fox_forward,
    "reload": _fox_reload,
    "refresh": _fox_reload,
    "stop": _fox_disconnect,
    "stopload": _fox_stopload,
    "title": _fox_title,
    "url": _fox_url,
    "text": _fox_text,
    "read": _fox_read,
    "find": _fox_find,
    "click": _fox_click,
    "type": _fox_type,
    "key": _fox_key,
    "scroll": _fox_scroll,
    "js": _fox_js,
    "shot": _fox_shot,
    "screenshot": _fox_shot,
    "tabs": _fox_tabs,
    "tab": _fox_tab,
    "closetab": _fox_closetab,
    "wait": _fox_wait,
    "search": _fox_search,
    "help": _fox_help,
}

def cmd_fox(args_str, history, cmd_log):
    """Handler the Prism32 loader calls: (args_str, history, cmd_log).
    PRINTS its result and returns None (dispatch_capture collects
    stdout — returned strings would be invisible). Any failure prints
    'firefox: <error>' and never propagates into the host REPL."""
    try:
        rest = (args_str or "").strip()
        if not rest or rest.lower() in ("help", "?"):
            _fox_help("")
            return
        tokens = rest.split(None, 1)
        sub = tokens[0].lower()
        sub_rest = tokens[1] if len(tokens) > 1 else ""
        handler = _SUBCOMMANDS.get(sub)
        if handler is None:
            print(f"firefox: unknown subcommand '{sub}' — try /fox help")
            return
        handler(sub_rest)
    except KeyboardInterrupt:
        raise   # let the host handle interrupt keys as it always does
    except SystemExit:
        raise
    except Exception as exc:
        print(f"firefox: {exc}")


# ── Registration ─────────────────────────────────────────────────────

ADVERTISEMENT = (
    "[firefox_browser] /fox — remote-control the operator's REAL Firefox "
    "over Marionette (their profile's logins/cookies apply — no "
    "re-authentication needed; works for posts, paperwork, research, any "
    "search engine). Run /fox status first: it reports the honest "
    "connection state. ONE-TIME setup: /fox enable attaches if possible, "
    "else restarts Firefox ONCE (gracefully — session restore brings "
    "every tab back) and patches the launcher so future normal launches "
    "are controllable; after that /fox start just attaches, and NO "
    "command ever closes tabs or Firefox outside that one enable "
    "restart. /fox start [default|<profile-path>] attaches or launches. "
    "Commands: /fox open <url>, /fox back|forward|reload|stop, "
    "/fox url, /fox title, /fox text [css], /fox read [max_chars], "
    "/fox find <css> [text|count|href|value], /fox click <css> [n] "
    "(1-based), /fox type <css> <text>, /fox key <Enter|Tab|Esc>, "
    "/fox scroll <down|up|top|bottom|px>, /fox js <script>, "
    "/fox shot [name], /fox tabs, /fox tab <n>, /fox closetab <n>, "
    "/fox wait <css> [sec], /fox search <ddg|lite|google|startpage|"
    "marginalia|mojeek|wiby> <query>, /fox stop. Output is printed by the "
    "handler; failures print 'firefox: <error>' and never break the "
    "session. Screenshots land in ~/.prism32/firefox/."
)


def register(plugin_api):
    global api
    api = plugin_api
    try:
        os.makedirs(FOX_DIR, exist_ok=True)
    except OSError:
        pass
    api.registry.register(
        "fox", cmd_fox,
        aliases=["firefox"],
        description="Drive the operator's real Firefox via Marionette "
                    "(logins/cookies apply): open, click, type, read, "
                    "search, screenshots",
        category="Web Automation",
    )
    # Always advertise (the commands self-explain their state and /fox
    # status is honest about connectivity) — the quarantined plugin's
    # sin was advertising a feature that hard-crashed; these commands
    # degrade to a printed error message instead.
    api.inject_context(ADVERTISEMENT)
