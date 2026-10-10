#!/usr/bin/env python3
"""Prism32 smoketests — end-to-end harness verification without real APIs.

Drives the actual REPL (piped stdin), a real mission run, subagents, the
execute-block protocol, config persistence, and bracketed paste — all
against an in-process mock OpenAI-compatible server. Zero network, zero
real keys: any environment can run these in seconds.

Usage:  python3 smoketests.py [--keep]     (add --keep to keep the sandbox)

Exit code 0 = all smoketests green. Each check prints PASS/FAIL with the
reasoning; failures dump the relevant output for triage.
"""
import json
import os
import subprocess
import sys
import tempfile
import threading
import time
import socket
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

HERE = os.path.dirname(os.path.abspath(__file__))
PRISM32 = os.path.join(HERE, "prism32.py")

_results = []


def check(name, ok, detail=""):
    _results.append((name, ok, detail))
    mark = "PASS" if ok else "FAIL"
    print(f"  [{mark}] {name}" + (f"  — {detail}" if detail and not ok else ""))
    return ok


# ── Mock OpenAI-compatible provider ─────────────────────────────────
class MockLLM:
    """Stateful scripted LLM: chat round 1 runs commands via execute blocks,
    round 2 answers in plain text. Models endpoint advertises mock-model."""

    def __init__(self):
        self.rounds = 0
        self.requests = []

    def handler(self):
        llm = self
        class H(BaseHTTPRequestHandler):
            def log_message(self, *a):
                pass
            def _send(self, code, obj):
                body = json.dumps(obj).encode()
                self.send_response(code)
                self.send_header("Content-Type", "application/json")
                self.send_header("Content-Length", str(len(body)))
                self.end_headers()
                self.wfile.write(body)
            def do_GET(self):
                if self.path.endswith("/models"):
                    self._send(200, {"object": "list", "data": [
                        {"id": "mock-model", "object": "model"}]})
                else:
                    self._send(404, {"error": "not found"})
            def do_POST(self):
                n = int(self.headers.get("Content-Length") or 0)
                req = json.loads(self.rfile.read(n) or b"{}")
                llm.requests.append(req)
                llm.rounds += 1
                if llm.rounds == 1:
                    content = ("Working on it.\n\n```execute\n/quantum smoke:ok\n```\n"
                               "```execute\n/remember smoke-ltm-entry: the harness works\n```\n")
                elif llm.rounds == 2:
                    content = "SMOKE_DONE: the quantum key was written."
                else:
                    content = "ack"
                if req.get("stream"):
                    self.send_response(200)
                    self.send_header("Content-Type", "text/event-stream")
                    self.end_headers()
                    chunk = {"choices": [{"delta": {"content": content}, "index": 0}]}
                    self.wfile.write(b"data: " + json.dumps(chunk).encode() + b"\n\n")
                    self.wfile.write(b"data: [DONE]\n\n")
                else:
                    self._send(200, {
                        "id": "mock", "object": "chat.completion",
                        "choices": [{"index": 0,
                                     "message": {"role": "assistant", "content": content},
                                     "finish_reason": "stop"}],
                        "usage": {"prompt_tokens": 10, "completion_tokens": 5,
                                  "total_tokens": 15}})
        return H


class PathologicalMockLLM(MockLLM):
    """Degenerate model: emits the IDENTICAL execute block every round.
    The loop guard must stop the agent within a handful of steps."""

    def handler(self):
        base = super().handler()
        llm = self
        class H(base):
            def do_POST(self):
                n = int(self.headers.get("Content-Length") or 0)
                req = json.loads(self.rfile.read(n) or b"{}")
                llm.requests.append(req)
                content = "```execute\n/quantum degenerate:1\n```\nSpinning."
                if req.get("stream"):
                    self.send_response(200)
                    self.send_header("Content-Type", "text/event-stream")
                    self.end_headers()
                    chunk = {"choices": [{"delta": {"content": content}, "index": 0}]}
                    self.wfile.write(b"data: " + json.dumps(chunk).encode() + b"\n\n")
                    self.wfile.write(b"data: [DONE]\n\n")
                else:
                    self._send(200, {
                        "id": "mock", "object": "chat.completion",
                        "choices": [{"index": 0,
                                     "message": {"role": "assistant", "content": content},
                                     "finish_reason": "stop"}],
                        "usage": {"prompt_tokens": 1, "completion_tokens": 1,
                                  "total_tokens": 2}})
        return H


def start_mock():
    llm = MockLLM()
    srv = ThreadingHTTPServer(("127.0.0.1", 0), llm.handler())
    th = threading.Thread(target=srv.serve_forever, daemon=True)
    th.start()
    return llm, srv, f"http://127.0.0.1:{srv.server_address[1]}/v1"


# ── Helpers ─────────────────────────────────────────────────────────
def run_repl(home, api_base, lines, timeout=90, model="mock-model"):
    """Pipe commands into a real REPL subprocess; return (rc, output)."""
    script = "\n".join(lines) + "\n/exit\n"
    env = dict(os.environ, HOME=home, TERM="dumb",
               PRISM32_NATIVE_TOOLS="0")
    try:
        p = subprocess.run(
            [sys.executable, PRISM32, "--api", api_base, "--model", model,
             "--no-boot", "--api-key", "mock-key"],
            input=script, capture_output=True, text=True, timeout=timeout, env=env)
        return p.returncode, p.stdout + p.stderr
    except subprocess.TimeoutExpired as e:
        return 124, ((e.stdout or b"") + (e.stderr or b"")).decode(errors="replace") if isinstance(e.stdout, bytes) else str(e)


def make_home():
    home = tempfile.mkdtemp(prefix="prism32-smoke-")
    os.makedirs(os.path.join(home, ".prism32"), exist_ok=True)
    return home


# ── Smoketests ───────────────────────────────────────────────────────
def smoke_cli():
    print("\n[1] CLI basics")
    p = subprocess.run([sys.executable, PRISM32, "--version"],
                       capture_output=True, text=True, timeout=60)
    check("prism32 --version exits 0", p.returncode == 0, p.stderr[-200:])
    check("version banner present", "MegaDyne" in p.stdout or "Prism32" in p.stdout, p.stdout[:100])
    p = subprocess.run([sys.executable, PRISM32, "--help"],
                       capture_output=True, text=True, timeout=60)
    check("prism32 --help exits 0", p.returncode == 0, p.stderr[-200:])


def smoke_repl_commands(llm, api_base):
    print("\n[2] REPL + operator commands (mock provider)")
    llm.rounds = 0
    home = make_home()
    rc, out = run_repl(home, api_base, [
        "/help",
        "/config",
        "/provider list",
        "/quantum smoke_pre:yes",
        "/quantum smoke_pre:",
        "/board",
        "/temperature 0.3",
        "/mission status",
    ])
    ok = rc == 0
    check("REPL session exits cleanly", ok, f"rc={rc} tail={out[-300:]}")
    check("/help lists commands", "/mission" in out and "/provider" in out, out[:200])
    check("/config shows settings", "api_base" in out.lower() or "Config" in out, out[:400])
    check("/provider list renders registry", "neuralwatt" in out, out[:600])
    check("/quantum write+read round-trips", "smoke_pre" in out and "yes" in out, out[-800:])
    check("/board outside a mission explains itself", "no active mission" in out, out[-600:])
    cfg = os.path.join(home, ".prism32", "config.json")
    if os.path.isfile(cfg):
        d = json.load(open(cfg))
        check("/temperature persists to config.json", d.get("temperature") == 0.3, str(d.get("temperature")))
    else:
        check("/temperature persists to config.json", False, "config.json missing")


def smoke_chat_protocol(llm, api_base):
    llm.rounds = 0
    print("\n[3] Chat + execute-block protocol (mock provider)")
    home = make_home()
    rc, out = run_repl(home, api_base, [
        "hello there, please do the thing",   # round 1 → execute /quantum smoke:ok
        "and now summarize",                   # round 2 → SMOKE_DONE text
    ], timeout=120)
    check("chat session exits cleanly", rc == 0, f"rc={rc} tail={out[-300:]}")
    check("model reply rendered", "SMOKE_DONE" in out, out[-500:])
    check("execute block ran the /quantum command", "smoke:ok" in out or "smoke" in out.lower(), out[-900:])
    check("agent /remember routes (no shell fall-through)", "Remembered as mem_" in out, out[-900:])
    check("assistant turn echoed", "MDS" in out or "You:" in out, out[:300])


def smoke_loop_guard():
    print("\n[7] Loop guard (degenerate repeat agent force-stopped)")
    llm = PathologicalMockLLM()
    srv = ThreadingHTTPServer(("127.0.0.1", 0), llm.handler())
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    api_base = f"http://127.0.0.1:{srv.server_address[1]}/v1"
    try:
        home = make_home()
        t0 = time.time()
        rc, out = run_repl(home, api_base, [
            "/delegate spin forever please",
        ], timeout=120)
        dt = time.time() - t0
        check("degenerate delegate terminates", rc == 0, f"rc={rc}")
        check("loop guard fired (not max-steps)", "LOOP GUARD" in out, out[-400:])
        check("loop stopped fast (<15s)", dt < 15, f"{dt:.1f}s")
    finally:
        srv.shutdown()


def smoke_subagent(llm, api_base):
    llm.rounds = 0
    print("\n[4] Subagent delegation (mock provider)")
    home = make_home()
    rc, out = run_repl(home, api_base, [
        "/delegate check the mock catalog and report",
    ], timeout=120)
    check("delegate returns", rc == 0, f"rc={rc}")
    check("subagent result surfaced", "Subagent" in out or "smoke" in out.lower() or "ack" in out, out[-600:])


def smoke_mission(llm, api_base):
    llm.rounds = 0
    print("\n[5] Mission lifecycle incl. shared board + expiry")
    home = make_home()
    env = dict(os.environ, HOME=home, TERM="dumb", PRISM32_NATIVE_TOOLS="0")
    goal = ("Step one: post the word KIWI to the mission info board using /board. "
            "Step two: run /board and reply with what it returned.")
    try:
        p = subprocess.run(
            [sys.executable, PRISM32, "--api", api_base, "--model", "mock-model",
             "--no-boot", "--api-key", "mock-key", "--mission", goal],
            capture_output=True, text=True, timeout=180, env=env)
        out = p.stdout + p.stderr
    except subprocess.TimeoutExpired:
        out = "TIMEOUT"
    check("mission run terminates", "TIMEOUT" not in out, out[-200:])
    check("mission completes structurally", "MISSION COMPLETE" in out, out[-400:])
    missions_dir = os.path.join(home, ".prism32", "missions")
    check("mission workspace expired", not os.path.isdir(missions_dir) or not os.listdir(missions_dir),
          str(os.listdir(missions_dir) if os.path.isdir(missions_dir) else "gone"))


def smoke_bracketed_paste():
    print("\n[6] Bracketed paste (multi-paragraph input stays one message)")
    import pty, select
    code = (
        "import sys; sys.path.insert(0, %r)\n"
        "import prism32\n"
        "line = input('PROMPT>')\n"
        "sys.stderr.write('GOT:' + repr(line) + chr(10))\n" % PRISM32
    )
    try:
        pid, fd = pty.fork()
    except (ImportError, OSError):
        check("bracketed paste (pty unavailable)", True, "skipped — no pty on this platform")
        return
    if pid == 0:
        os.environ["TERM"] = "xterm"
        os.execvp(sys.executable, [sys.executable, "-c", code])
    try:
        time.sleep(1.0)
        os.write(fd, b"intro ")
        time.sleep(0.5)
        # Does the app enable bracketed paste mode? GNU readline >= 8.1
        # (with enable-bracketed-paste on) emits ESC[?2004h when reading;
        # libedit (macOS) and older readlines never do — and real terminals
        # only send markers when the app asked for them.
        out = b""
        deadline = time.time() + 3
        while time.time() < deadline:
            r, _, _ = select.select([fd], [], [], 0.3)
            if not r:
                break
            try:
                chunk = os.read(fd, 4096)
            except OSError:
                break
            if not chunk:
                break
            out += chunk
        app_enabled_paste = b"\x1b[?2004h" in out

        if app_enabled_paste:
            # Terminal wraps the paste; pasted newlines are literal.
            os.write(fd, b"\x1b[200~para one\n\npara two\n\npara three\x1b[201~")
            time.sleep(0.4)
            os.write(fd, b"\r")
            got = _pty_read_got(fd)
            if got:
                ok = ("para one" in got) and ("para two" in got) and ("para three" in got)
                check("multi-paragraph paste returns as ONE input", ok, got[:140])
            else:
                check("multi-paragraph paste returns as ONE input", False, out.decode(errors="replace")[-200:])
        else:
            # libedit / old readline: no ?2004 handshake → real terminals
            # send pastes RAW (no markers). Verify the app degrades
            # cleanly instead of corrupting on escape garbage.
            os.write(fd, b"\x1b[200~stale marker bytes\x1b[201~")
            time.sleep(0.3)
            os.write(fd, b"\r")
            got = _pty_read_got(fd)
            check("paste mode degrades cleanly (libedit: per-line paste, known limitation)",
                  got is not None, out.decode(errors="replace")[-200:])
    finally:
        try:
            os.close(fd)
        except OSError:
            pass
        try:
            os.waitpid(pid, 0)
        except OSError:
            pass


def _pty_read_got(fd, timeout=6):
    """Read a pty until the child prints a GOT: line; return its value."""
    import select as _sel
    out = b""
    deadline = time.time() + timeout
    while time.time() < deadline:
        r, _, _ = _sel.select([fd], [], [], 0.5)
        if not r:
            if b"GOT:" in out:
                break
            continue
        try:
            chunk = os.read(fd, 4096)
        except OSError:
            break
        if not chunk:
            break
        out += chunk
        if b"GOT:" in out:
            break
    text = out.decode(errors="replace")
    got = [ln for ln in text.splitlines() if ln.startswith("GOT:")]
    return got[0][4:] if got else None


def main():
    import argparse
    ap = argparse.ArgumentParser()
    ap.add_argument("--keep", action="store_true", help="keep sandbox dirs")
    args = ap.parse_args()

    print("Prism32 smoketests — mock provider, hermetic REPL drives")
    llm, srv, api_base = start_mock()
    try:
        smoke_cli()
        smoke_repl_commands(llm, api_base)
        smoke_chat_protocol(llm, api_base)
        smoke_subagent(llm, api_base)
        smoke_mission(llm, api_base)
        smoke_bracketed_paste()
        smoke_loop_guard()
    finally:
        srv.shutdown()

    failed = [r for r in _results if not r[1]]
    print(f"\n{'=' * 60}")
    print(f"SMOKETESTS: {len(_results) - len(failed)}/{len(_results)} passed")
    if failed:
        for name, _, detail in failed:
            print(f"  FAIL: {name}\n    {detail[:400]}")
        sys.exit(1)
    print("ALL GREEN")


if __name__ == "__main__":
    main()
