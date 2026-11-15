"""Harness fixes from the 2026-11 session forensics
(auto_20261101_125932: 13.6h of `sleep N; /subagents` poll loops,
1000-step subagents, results lost to /collect-pop + 300s GC, empty
auto_*.json session files, LOOP GUARD that never fired).

Every test here pins one failure mode observed in that session.
"""
import os
import sys
import threading
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import prism32
from prism32 import (
    _try_plugin_cmd,
    _split_plugin_block,
    _RepeatGuard,
    _cap_result_for_model,
    _purge_nudge_marks,
    _maybe_cap_sleep,
    _notify_subagent_done,
    _drain_agent_events,
    _wait_for_work,
    BackgroundJob,
    _pending_work_running,
    _list_pending_work,
    save_current_session,
    Config,
    _CMD_RESULT_CAP,
)


class _FakeSA:
    """Minimal stand-in for SubAgent."""

    def __init__(self, sid="sa_t", task="test task", done=False, result=None, error=None):
        self.id = sid
        self.task = task
        self.done = done
        self.result = result
        self.error = error
        self._step = 4
        self.max_steps = 200
        self._thread = None
        self._sync_run = False

    def status_str(self):
        if not self.done:
            return f"[{self.id}] RUNNING step {self._step}/{self.max_steps}"
        return f"[{self.id}] DONE result: {(self.result or '?')[:40]}"


def _register(sa):
    with prism32._subagent_lock:
        prism32._SUBAGENTS[sa.id] = sa


def _clear_subagents():
    with prism32._subagent_lock:
        prism32._SUBAGENTS.clear()


def _clear_events():
    with prism32._agent_events_lock:
        prism32._AGENT_EVENT_LOG.clear()
    prism32._MAIN_EVENT_CURSOR[0] = 0
    prism32._AGENT_EVENT_SEQ = 0


# ── /wait ────────────────────────────────────────────────────────

def test_wait_with_no_work():
    _clear_subagents()
    with prism32._bg_lock:
        prism32._BG_JOBS.clear()
    r = _wait_for_work("")
    assert "No subagents or background jobs" in r


def test_wait_returns_immediately_for_done_subagent():
    _clear_subagents()
    _register(_FakeSA("sa_done", done=True, result="all finished"))
    try:
        r = _wait_for_work("sa_done")
        assert "finished" in r and "all finished" in r
    finally:
        _clear_subagents()


def test_wait_blocks_until_subagent_finishes():
    _clear_subagents()
    sa = _FakeSA("sa_slow", done=False)
    _register(sa)

    def _finish():
        time.sleep(0.3)
        sa.done = True
        sa.result = "late result"

    threading.Thread(target=_finish, daemon=True).start()
    try:
        t0 = time.time()
        r = _wait_for_work("sa_slow --timeout 10")
        assert time.time() - t0 >= 0.25, "returned before subagent finished"
        assert "late result" in r
    finally:
        _clear_subagents()


def test_wait_timeout_reports_running():
    _clear_subagents()
    _register(_FakeSA("sa_stuck", done=False))
    try:
        t0 = time.time()
        r = _wait_for_work("sa_stuck --timeout 1")
        assert time.time() - t0 < 5
        assert "TIMEOUT" in r and "sa_stuck" in r and "/wait" in r
    finally:
        _clear_subagents()


def test_wait_routes_from_execute_blocks():
    _clear_subagents()
    assert _try_plugin_cmd("/wait") is not None


# ── compound command splitting ───────────────────────────────────

def test_split_compound_poll_pattern():
    assert _split_plugin_block("sleep 480; /subagents") == ["sleep 480", "/subagents"]


def test_split_compound_with_git_and_remember():
    got = _split_plugin_block('git add -A; git commit -m "x"; /remember "done"')
    assert got == ['git add -A', 'git commit -m "x"', '/remember "done"']


def test_split_respects_quoted_semicolons():
    got = _split_plugin_block('echo "a;b"; /subagents')
    assert got == ['echo "a;b"', '/subagents']


def test_split_refuses_shell_control_structures():
    # A for-loop body split on `;` would be a syntax error — must not split
    got = _split_plugin_block("for i in 1 2; do echo $i; done; /subagents")
    assert len(got) == 1 and got[0].startswith("for i in")


def test_split_plain_shell_untouched():
    assert _split_plugin_block("echo a; echo b") == ["echo a; echo b"]


def test_split_whitespace_only_block():
    assert _split_plugin_block("   \n  ") == []


def test_multiline_all_slash_blocks_still_split():
    got = _split_plugin_block("/quantum k:v\n/remember hello")
    assert got == ["/quantum k:v", "/remember hello"]


# ── RepeatGuard normalization ────────────────────────────────────

def test_repeat_guard_catches_numeric_variants():
    g = _RepeatGuard()
    c1 = g.note("sleep 480; /subagents")
    c2 = g.note("sleep 540; /subagents")
    c3 = g.note("sleep 300 ; /subagents")
    assert (c1, c2, c3) == (1, 2, 3), "varying digits must not dodge the guard"


def test_repeat_guard_resets_on_new_command():
    g = _RepeatGuard()
    g.note("sleep 480; /subagents")
    g.note("sleep 540; /subagents")
    assert g.note("echo hello") == 1


# ── sleep cap ────────────────────────────────────────────────────

def test_sleep_capped_while_subagents_run():
    _clear_subagents()
    _register(_FakeSA("sa_run", done=False))
    try:
        cap = _maybe_cap_sleep("sleep 480")
        assert cap is not None
        assert cap[0] == "sleep 30"
        assert "capped" in cap[1] and "/wait" in cap[1]
    finally:
        _clear_subagents()


def test_short_sleep_not_capped():
    _clear_subagents()
    _register(_FakeSA("sa_run2", done=False))
    try:
        assert _maybe_cap_sleep("sleep 20") is None
    finally:
        _clear_subagents()


def test_sleep_not_capped_without_running_subagents():
    _clear_subagents()
    assert _maybe_cap_sleep("sleep 480") is None


def test_compound_sleep_not_matched_by_cap():
    # Only bare sleeps are capped; compounds are split first anyway
    _clear_subagents()
    _register(_FakeSA("sa_run3", done=False))
    try:
        assert _maybe_cap_sleep("sleep 480; /subagents") is None
    finally:
        _clear_subagents()


# ── result visibility ────────────────────────────────────────────

def test_cap_result_keeps_tail():
    body = "x" * 3000
    result = "HEAD-START\n" + body + "\nFINAL-STATUS: OK rc=0"
    capped = _cap_result_for_model(result)
    assert len(capped) <= _CMD_RESULT_CAP + 60
    assert "HEAD-START" in capped
    assert "FINAL-STATUS: OK rc=0" in capped, "tail (exit status) must be visible"
    assert "middle truncated" in capped


def test_cap_result_short_passthrough():
    assert _cap_result_for_model("short") == "short"


# ── subagent result persistence + events ─────────────────────────

def test_notify_publishes_quantum_and_events():
    _clear_subagents()
    _clear_events()
    prism32._quantum.clear()
    sa = _FakeSA("sa_pub", done=True, result="the answer is 42")
    _notify_subagent_done(sa)
    try:
        assert prism32._quantum.get("subagent_sa_pub_result") == "the answer is 42"
        assert prism32._quantum.get("subagent_sa_pub_status") == "done"
        evs, nxt = _drain_agent_events(0)
        assert len(evs) == 1 and evs[0]["id"] == "sa_pub"
        assert evs[0]["kind"] == "subagent"
        assert evs[0]["result"] == "the answer is 42"
        # cursor advances: second drain sees nothing new
        evs2, _ = _drain_agent_events(nxt)
        assert evs2 == []
    finally:
        prism32._quantum.clear()
        _clear_events()


def test_sync_subagents_do_not_queue_events():
    _clear_events()
    prism32._quantum.clear()
    sa = _FakeSA("sa_sync", done=True, result="direct")
    sa._sync_run = True
    _notify_subagent_done(sa)
    try:
        evs, _ = _drain_agent_events(0)
        assert evs == [], "sync /delegate returns its result directly"
        assert prism32._quantum.get("subagent_sa_sync_result") == "direct"
    finally:
        prism32._quantum.clear()
        _clear_events()


def test_drain_per_consumer_cursors():
    _clear_events()
    prism32._quantum.clear()
    _notify_subagent_done(_FakeSA("sa_a", done=True, result="a"))
    _notify_subagent_done(_FakeSA("sa_b", done=True, result="b"))
    try:
        evs1, cur1 = _drain_agent_events(0)
        evs2, cur2 = _drain_agent_events(0)
        assert [e["id"] for e in evs1] == ["sa_a", "sa_b"]
        assert [e["id"] for e in evs2] == ["sa_a", "sa_b"], \
            "concurrent consumers must each see the events"
        assert cur1 == cur2
    finally:
        prism32._quantum.clear()
        _clear_events()


def test_collect_no_longer_pops():
    _clear_subagents()
    _register(_FakeSA("sa_keep", done=True, result="kept result"))
    try:
        r1 = _try_plugin_cmd("/collect sa_keep")
        assert "kept result" in r1
        with prism32._subagent_lock:
            assert "sa_keep" in prism32._SUBAGENTS, "record must persist"
        r2 = _try_plugin_cmd("/collect sa_keep")
        assert "kept result" in r2, "re-collect must still work"
    finally:
        _clear_subagents()


def test_collect_running_mentions_wait():
    _clear_subagents()
    _register(_FakeSA("sa_busy", done=False))
    try:
        r = _try_plugin_cmd("/collect sa_busy")
        assert "still running" in r and "/wait" in r
    finally:
        _clear_subagents()


def test_collect_unknown_falls_back_to_quantum():
    _clear_subagents()
    prism32._quantum.clear()
    prism32._quantum.put("subagent_sa_gone_result", "cached result")
    try:
        r = _try_plugin_cmd("/collect sa_gone")
        assert "cached result" in r
    finally:
        prism32._quantum.clear()


def test_spawn_return_mentions_wait(monkeypatch):
    class _StubSA:
        def __init__(self, task, model=None, max_steps=None, provider=None):
            self.task, self.id, self.max_steps = task, "sa_stub", max_steps

        def run_async(self, quiet=False):
            pass

    monkeypatch.setattr(prism32, "SubAgent", _StubSA)
    r = _try_plugin_cmd("/spawn test the swarm")
    assert "/wait" in r and "sa_stub" in r


# ── subagent step budget ─────────────────────────────────────────

def test_subagent_default_steps_from_config():
    sa = prism32.SubAgent("budget check")
    assert sa.max_steps == Config.SUBAGENT_MAX_STEPS
    assert sa.max_steps <= 1000, "default must not be the runaway 1000"


def test_subagent_explicit_steps_honored():
    sa = prism32.SubAgent("explicit", max_steps=7)
    assert sa.max_steps == 7


# ── empty session guard ──────────────────────────────────────────

def test_save_current_session_skips_empty_history(tmp_path, monkeypatch):
    monkeypatch.setattr(Config, "SESSION_DIR", str(tmp_path))
    prism32._CURRENT_SESSION_ID = None
    sys_only = [{"role": "system", "content": "You are Prism32."}]
    save_current_session(sys_only, [])
    assert prism32._CURRENT_SESSION_ID is None, "no id minted for empty session"
    assert os.listdir(str(tmp_path)) == []

    hist = sys_only + [{"role": "user", "content": "do the thing"}]
    save_current_session(hist, [])
    files = os.listdir(str(tmp_path))
    assert len(files) == 1 and files[0].startswith("auto_")


def test_save_current_session_skips_after_clear(tmp_path, monkeypatch):
    monkeypatch.setattr(Config, "SESSION_DIR", str(tmp_path))
    prism32._CURRENT_SESSION_ID = None
    save_current_session([{"role": "user", "content": "hi"}], [])
    assert len(os.listdir(str(tmp_path))) == 1
    # /clear equivalent: system-only history + fresh id
    prism32._CURRENT_SESSION_ID = None
    save_current_session([{"role": "system", "content": "reset"}], [])
    assert len(os.listdir(str(tmp_path))) == 1, "no new empty session file"


# ── nudge-mark purge by identity ─────────────────────────────────

def test_purge_nudge_marks_identity():
    keep_before = {"role": "user", "content": "before"}
    a1 = {"role": "assistant", "content": "I will do the thing"}
    n1 = {"role": "user", "content": "STOP ANNOUNCING"}
    keep_mid = {"role": "user", "content": "Executed: ls\nResult:\nfiles"}
    a2 = {"role": "assistant", "content": "announcement 2"}
    n2 = {"role": "user", "content": "PROTOCOL RESET"}
    keep_after = {"role": "assistant", "content": "final answer"}
    history = [keep_before, a1, n1, keep_mid, a2, n2, keep_after]
    _purge_nudge_marks(history, [a1, n1, a2, n2])
    assert history == [keep_before, keep_mid, keep_after]


def test_purge_nudge_marks_tolerates_trimmed_history():
    m1 = {"role": "assistant", "content": "gone already"}
    history = [{"role": "system", "content": "sys"}]
    _purge_nudge_marks(history, [m1])  # must not raise


# ── quantum display truncation ───────────────────────────────────

def test_quantum_str_not_starved():
    prism32._quantum.clear()
    try:
        long_value = "z" * 3000
        prism32._quantum.put("subagent_sa_1_result", long_value)
        rendered = str(prism32._quantum)
        assert "z" * 1500 in rendered
        assert "z" * 1501 not in rendered
    finally:
        prism32._quantum.clear()


# ── hints ─────────────────────────────────────────────────────────

def test_shell_wrap_hint_mentions_wait():
    hinted = prism32._shell_wrap_hint("/bin/sh: /subagents: No such file or directory",
                                      "sh -c '/subagents'")
    assert "/wait" in hinted


def test_hint_not_added_on_success():
    out = prism32._shell_wrap_hint("all good", "echo hi")
    assert out == "all good"


# ── swarm pause (Ctrl+P) ─────────────────────────────────────────

def test_pause_gate_blocks_until_resumed():
    prism32.request_agent_pause()
    assert prism32.agent_pause_requested()
    done = threading.Event()

    def _gate():
        prism32._pause_gate()
        done.set()

    th = threading.Thread(target=_gate, daemon=True)
    th.start()
    time.sleep(0.4)
    assert not done.is_set(), "gate must hold while paused"
    prism32.clear_agent_pause()
    done.wait(3)
    assert done.is_set(), "gate must release on resume"


def test_pause_gate_noop_when_not_paused():
    prism32.clear_agent_pause()
    t0 = time.time()
    prism32._pause_gate()
    assert time.time() - t0 < 0.2


def test_cancel_beats_pause():
    prism32.request_agent_pause()
    prism32.request_agent_cancel("test")
    try:
        t0 = time.time()
        prism32._pause_gate()
        assert time.time() - t0 < 1.0, "cancel must break the pause hold"
    finally:
        prism32.clear_agent_pause()
        prism32.clear_agent_cancel()


def test_toggle_agent_pause():
    prism32.clear_agent_pause()
    assert prism32.toggle_agent_pause() is True
    assert prism32.agent_pause_requested()
    assert prism32.toggle_agent_pause() is False
    assert not prism32.agent_pause_requested()


# ── /compact ──────────────────────────────────────────────────────

def test_compact_history_shrinks(monkeypatch):
    monkeypatch.setattr(prism32.Config, "resolve_context_window", lambda: 20000)
    big = "x" * 1200
    history = [{"role": "system", "content": "sys prompt " * 100}]
    for i in range(80):
        history.append({"role": "user", "content": f"Executed: cmd{i} arg\nResult:\n{big}"})
        history.append({"role": "assistant", "content": f"ok {i}"})
    before_tokens = sum(prism32._msg_tokens(m) for m in history)
    before, after = prism32.compact_history(history)
    after_tokens = sum(prism32._msg_tokens(m) for m in history)
    assert after < before, f"context pct must drop ({before} -> {after})"
    assert after_tokens < before_tokens
    assert history[0].get("role") == "system"


# ── /interject (steering) ────────────────────────────────────────

def test_interject_delivers_to_running_subagent():
    _clear_subagents()
    sa = prism32.SubAgent("steering target")
    sa._history = [{"role": "system", "content": "s"},
                   {"role": "user", "content": "Task: do things"}]
    _register(sa)
    try:
        r = _try_plugin_cmd(f"/interject {sa.id} the path is /opt/lib")
        assert "delivered" in r
        msgs = [m for m in sa._history if m.get("role") == "user" and "[STEER" in m.get("content", "")]
        assert msgs and "/opt/lib" in msgs[-1]["content"]
    finally:
        _clear_subagents()


def test_interject_rejects_finished_subagent():
    _clear_subagents()
    _register(_FakeSA("sa_fin", done=True, result="done already"))
    try:
        r = _try_plugin_cmd("/interject sa_fin keep going")
        assert "already finished" in r and "/collect" in r
    finally:
        _clear_subagents()


def test_interject_usage():
    assert "Usage" in _try_plugin_cmd("/interject")


# ── progress pulses ───────────────────────────────────────────────

def test_progress_pulse_published():
    _clear_events()
    sa = prism32.SubAgent("pulse test")
    sa._step = 50
    sa._last_cmd_snippet = "make -j8"
    sa._emit_pulse()
    try:
        evs, _ = _drain_agent_events(0)
        match = [e for e in evs if e["id"] == sa.id]
        assert match and match[0]["kind"] == "pulse"
        assert "50/200" in match[0]["subject"] and "make -j8" in match[0]["subject"]
    finally:
        _clear_events()


def test_pulse_rendering_is_compact():
    ev = {"kind": "pulse", "ok": True, "id": "sa_1", "subject": "step 50/200", "result": ""}
    rendered = prism32._format_agent_events([ev])
    assert "SUBAGENT PROGRESS" in rendered and "collect" not in rendered


# ── concurrency cap ──────────────────────────────────────────────

def test_subagent_slot_acquire_release():
    monkey_val = prism32.Config.MAX_CONCURRENT_SUBAGENTS
    prism32.Config.MAX_CONCURRENT_SUBAGENTS = 1
    prism32._SUBAGENT_SEMAPHORE = None
    try:
        assert prism32._acquire_subagent_slot() is True
        # Slot exhausted: with an immediate cancel, acquisition gives up fast
        t0 = time.time()
        assert prism32._acquire_subagent_slot(cancel_check=lambda: True) is False
        assert time.time() - t0 < 2
        prism32._release_subagent_slot()
        # Freed slot is acquirable again
        assert prism32._acquire_subagent_slot() is True
        prism32._release_subagent_slot()
    finally:
        prism32.Config.MAX_CONCURRENT_SUBAGENTS = monkey_val
        prism32._SUBAGENT_SEMAPHORE = None


def test_status_str_shows_queued(monkeypatch):
    sa = prism32.SubAgent("queued test")
    sa._slot_pending = True
    assert "QUEUED" in sa.status_str()


# ── background jobs (/bg) ────────────────────────────────────────

def _clear_bg_jobs():
    with prism32._bg_lock:
        prism32._BG_JOBS.clear()


def test_bg_job_runs_and_pushes_result():
    _clear_events()
    _clear_bg_jobs()
    prism32._quantum.clear()
    job = BackgroundJob("echo bg-hello-world")
    job.start()
    try:
        deadline = time.time() + 15
        while not job.done and time.time() < deadline:
            time.sleep(0.05)
        assert job.done, "bg job did not finish"
        assert "bg-hello-world" in (job.result or "")
        # quantum publication
        assert "bg-hello-world" in prism32._quantum.get(f"bg_{job.id}_result")
        # event publication
        evs, _ = _drain_agent_events(0)
        match = [e for e in evs if e["id"] == job.id]
        assert match and match[0]["kind"] == "bg" and match[0]["ok"]
        assert "bg-hello-world" in match[0]["result"]
    finally:
        prism32._quantum.clear()
        _clear_events()
        _clear_bg_jobs()


def test_bg_failure_publishes_error_event():
    _clear_events()
    _clear_bg_jobs()
    prism32._quantum.clear()
    job = BackgroundJob("exit 3")
    job.start()
    try:
        deadline = time.time() + 15
        while not job.done and time.time() < deadline:
            time.sleep(0.05)
        assert job.done
        evs, _ = _drain_agent_events(0)
        match = [e for e in evs if e["id"] == job.id]
        assert match, "failure must still notify"
    finally:
        prism32._quantum.clear()
        _clear_events()
        _clear_bg_jobs()


def test_bg_routes_from_execute_blocks():
    _clear_bg_jobs()
    r = _try_plugin_cmd("/bg")
    assert r is not None and "No background jobs" in r


def test_bg_start_message_mentions_notification():
    _clear_bg_jobs()
    r = _try_plugin_cmd("/bg echo hi")
    assert "NOTIFIED" in r and "/wait" in r
    # clean up the started job quickly
    deadline = time.time() + 15
    with prism32._bg_lock:
        job = list(prism32._BG_JOBS.values())[-1]
    while not job.done and time.time() < deadline:
        time.sleep(0.05)
    _clear_bg_jobs()


def test_collect_bg_job_result():
    _clear_bg_jobs()
    job = BackgroundJob("echo collect-me")
    job.start()
    try:
        deadline = time.time() + 15
        while not job.done and time.time() < deadline:
            time.sleep(0.05)
        r = _try_plugin_cmd(f"/collect {job.id}")
        assert "collect-me" in r
    finally:
        _clear_bg_jobs()


def test_wait_includes_bg_jobs():
    _clear_bg_jobs()
    _clear_subagents()
    job = BackgroundJob("sleep 30")
    job.start()
    try:
        t0 = time.time()
        r = _wait_for_work(f"{job.id} --timeout 1")
        assert time.time() - t0 < 5
        assert "TIMEOUT" in r and job.id in r
    finally:
        # don't leave the 30s sleep running
        job.timeout = 0.1
        _clear_bg_jobs()
        _clear_subagents()


def test_pending_work_running_covers_both_kinds():
    _clear_subagents()
    _clear_bg_jobs()
    assert not _pending_work_running()
    _register(_FakeSA("sa_pw", done=False))
    assert _pending_work_running()
    _clear_subagents()
    job = BackgroundJob("sleep 30")
    job.start()
    try:
        assert _pending_work_running()
        assert job.id in _list_pending_work()
    finally:
        job.timeout = 0.1
        _clear_bg_jobs()
        _clear_subagents()


def test_compound_bg_command_splits():
    assert _split_plugin_block("echo start; /bg make -j8") == \
        ["echo start", "/bg make -j8"]
