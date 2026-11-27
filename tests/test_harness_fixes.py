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


def test_wait_default_is_indefinite():
    # Live incident 2026-11-15: the 600s default made the model re-issue
    # /wait until the loop guard killed the turn. Default must now block
    # until cancel (no spontaneous timeout).
    _clear_subagents()
    _register(_FakeSA("sa_inf", done=False))
    results = {}

    def _w():
        results['r'] = _wait_for_work("sa_inf")

    th = threading.Thread(target=_w, daemon=True)
    th.start()
    try:
        time.sleep(0.8)
        assert th.is_alive(), "default /wait must NOT time out on its own"
        prism32.request_agent_cancel("test")
        th.join(3)
        assert not th.is_alive()
        assert "CANCELLED" in results.get('r', '')
    finally:
        prism32.clear_agent_cancel()
        _clear_subagents()


def test_wait_timeout_zero_is_indefinite():
    _clear_subagents()
    _register(_FakeSA("sa_inf2", done=False))
    results = {}

    def _w():
        results['r'] = _wait_for_work("sa_inf2 --timeout 0")

    th = threading.Thread(target=_w, daemon=True)
    th.start()
    try:
        time.sleep(0.8)
        assert th.is_alive(), "--timeout 0 must mean indefinite"
        prism32.request_agent_cancel("test")
        th.join(3)
        assert "CANCELLED" in results.get('r', '')
    finally:
        prism32.clear_agent_cancel()
        _clear_subagents()


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
        assert cap[0] == "sleep 300"
        assert "capped" in cap[1] and "/wait" in cap[1]
        # A 90s external-process wait is LEGIT work — must NOT be capped
        # (timers audit 2026-11: the old 30s cap cut service-restart waits).
        assert _maybe_cap_sleep("sleep 90") is None
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


# ── opencode (Zen) provider ──────────────────────────────────────

def test_opencode_provider_registered():
    from prism32 import PROVIDER_REGISTRY
    row = PROVIDER_REGISTRY.get("opencode")
    assert row is not None, "opencode provider missing from registry"
    assert row.get("api_base") == "https://opencode.ai/zen/v1"


# ── objective preservation (accuracy audit) ───────────────────────

def test_context_refresher_preserves_objective():
    prism32._ACTIVE_GOAL = ""
    hist = [{"role": "system", "content": "sys"}]
    hist.append({"role": "user", "content": "Fix the voice bridge on the Echo Show 5"})
    for i in range(40):
        hist.append({"role": "user", "content": f"Executed: cmd{i}\nResult:\nnoise {i}"})
    summary = prism32._build_context_refresher(hist, keep_count=10)
    assert "OBJECTIVE:" in summary
    assert "Fix the voice bridge" in summary, "original task must survive trims"


def test_context_refresher_recovers_objective_from_prior_summary():
    prism32._ACTIVE_GOAL = ""
    baked = ("[SESSION CONTEXT — prior conversation summarized]\n"
             "OBJECTIVE: Fix the voice bridge on the Echo Show 5\n"
             "[END SUMMARY — continue working.]")
    hist = [{"role": "system", "content": "sys"},
            {"role": "system", "content": baked}]
    for i in range(30):
        hist.append({"role": "user", "content": f"Executed: cmd{i}\nResult:\nn{i}"})
    summary = prism32._build_context_refresher(hist, keep_count=10)
    assert "Fix the voice bridge" in summary, "objective must survive repeated trims"


def test_max_history_slice_summarizes_not_deletes():
    prism32._ACTIVE_GOAL = ""
    cap = prism32.Config.MAX_HISTORY
    hist = [{"role": "system", "content": "sys"}]
    hist.append({"role": "user", "content": "Tune the wakeword engine"})
    for i in range(cap + 30):
        hist.append({"role": "user", "content": f"Executed: cmd{i}\nResult:\nr{i}"})
        hist.append({"role": "assistant", "content": f"ok {i}"})
    assert len(hist) > cap
    # replicate the end-of-turn cap logic's core: refresher must retain the task
    keep = cap - 1
    summary = prism32._build_context_refresher(hist, keep_count=keep)
    assert "Tune the wakeword engine" in summary


# ── compress_tool_turns predicate ────────────────────────────────

def test_compress_leaves_real_user_messages():
    long_paste = "Result: " + ("x" * 800)  # user pasted a log mentioning 'Result:'
    msgs = [{"role": "system", "content": "s"},
            {"role": "user", "content": long_paste}]
    out = prism32.compress_tool_turns(msgs, recent_keep=0)
    assert out[1]["content"] == long_paste, "real user text must never be collapsed"


def test_compress_collapses_executed_messages():
    tool_msg = {"role": "user", "content": "Executed: cat big.log\nResult:\n" + "\n".join(f"line{i}" for i in range(60))}
    filler = {"role": "assistant", "content": "ok"}
    msgs = [{"role": "system", "content": "s"}, tool_msg, filler]
    out = prism32.compress_tool_turns(msgs, recent_keep=1)
    assert len(out[1]["content"]) < len(tool_msg["content"])
    assert "trimmed" in out[1]["content"]


# ── false-failure detection ─────────────────────────────────────

def test_cmd_succeeded_zero_errors_is_success():
    assert prism32._cmd_succeeded("PASS: 42 tests\n0 errors, 0 failures") is True
    assert prism32._cmd_succeeded("no issues found in 3 files") is True


def test_cmd_succeeded_real_failures():
    assert prism32._cmd_succeeded("Traceback: ValueError\n1 failed") is False
    assert prism32._cmd_succeeded("make: *** [all] Error 1") is False


# ── event-log completion priority ────────────────────────────────

def test_drain_events_completions_outrank_pulses():
    _clear_events()
    # More than 8 completions: the window must keep the OLDEST undelivered
    # completion reachable (cursor goes back to it), never skip past it.
    for i in range(10):
        prism32._publish_agent_event("subagent", True, f"sa_done{i}", "task", "result")
    for i in range(5):
        prism32._publish_agent_event("pulse", True, f"sa_p{i}", "step", "")
    try:
        evs, nxt = _drain_agent_events(0)
        kinds = [e["kind"] for e in evs]
        assert len(evs) <= 8
        assert all(k == "subagent" for k in kinds), "backlog: completions outrank pulses"
        ids = [e["id"] for e in evs]
        assert ids == [f"sa_done{i}" for i in range(8)], "FIFO: oldest completions deliver first"
        # second drain delivers the remaining 2
        evs2, nxt2 = _drain_agent_events(nxt)
        ids2 = [e["id"] for e in evs2 if e["kind"] == "subagent"]
        assert ids2 == ["sa_done8", "sa_done9"], "every completion must eventually deliver"
    finally:
        _clear_events()


# ── quantum bookkeeping filter ───────────────────────────────────

def test_quantum_bookkeeping_keys_filtered():
    assert prism32._is_quantum_bookkeeping("subagent_sa_1_spawned") is True
    assert prism32._is_quantum_bookkeeping("subagent_sa_1_status") is True
    assert prism32._is_quantum_bookkeeping("subagent_sa_1_task") is True
    assert prism32._is_quantum_bookkeeping("bg_bg_0_cmd") is True
    assert prism32._is_quantum_bookkeeping("subagent_sa_1_result") is False
    assert prism32._is_quantum_bookkeeping("my_shared_finding") is False


# ── interruptor relaxation (timers audit) ─────────────────────────

def test_repeat_guard_changing_output_is_progress():
    g = _RepeatGuard()
    for i in range(10):
        g.note("adb shell getprop sys.boot_completed")
        g.observe("adb shell getprop sys.boot_completed", f"output-{i}")
        assert g.count == 1, "changing output must reset the count"


def test_repeat_guard_identical_output_climbs():
    g = _RepeatGuard()
    for i in range(5):
        rc = g.note("cat /tmp/lock")
        g.observe("cat /tmp/lock", "same-output")
    assert rc == 5, "identical command + identical output must still trip"


def test_bg_job_timeout_floor():
    job = BackgroundJob("echo long-build")
    assert job.timeout >= 1800, "bg jobs are the long ones — 30min floor"


def test_bg_timeout_override():
    job = BackgroundJob("echo x", timeout=42)
    assert job.timeout == 42


def test_mission_budget_config():
    assert prism32.Config.MISSION_MAX_STEPS >= 1
    old = prism32.Config.MISSION_MAX_STEPS
    prism32.Config.MISSION_MAX_STEPS = 60
    assert prism32.Config.MISSION_MAX_STEPS == 60
    prism32.Config.MISSION_MAX_STEPS = old


def _run_cmd_threaded(cmd, timeout):
    """Run run_cmd from a non-main thread so it takes the Popen+select path
    (the main-thread/no-tty path is a plain subprocess.run fallback)."""
    box = {}

    def _w():
        box['r'] = prism32.run_cmd(cmd, timeout=timeout)

    th = threading.Thread(target=_w, daemon=True)
    th.start()
    th.join(20)
    return box.get('r', '')


def test_run_cmd_idle_based_timeout_lets_streamers_live():
    # Streams every 0.3s for ~1.8s total with a 1s timeout: the old
    # total-wall deadline killed it at 1s; the idle deadline must let it
    # finish (timers audit 2026-11 — long builds were dying mid-work).
    out = _run_cmd_threaded("for i in 1 2 3 4 5 6; do echo tick$i; sleep 0.3; done", 1)
    assert "tick6" in out, f"streaming command must not be killed by idle timeout: {out[:80]!r}"


def test_run_cmd_silent_command_still_dies():
    t0 = time.time()
    out = _run_cmd_threaded("sleep 8", 1)
    assert time.time() - t0 < 5, "a silent command must still be killed at the idle deadline"
    assert "[TIMEOUT]" in out and "silent" in out, out[:120]


# ── provider registry merge (UX audit critical fix) ────────────────

def test_provider_key_on_builtin_keeps_base_and_model():
    """Regression (UX audit 2026-11-24, verified broken): a key-only
    update on a built-in provider used to clobber the registry's
    api_base/model to '' — the documented '/provider key <builtin> <key>'
    then '/model' path dead-ended fresh installs."""
    from prism32 import PROVIDER_REGISTRY, Config
    old = prism32.Config.CONFIG_FILE
    import tempfile as _tf, os as _os
    prism32.Config.CONFIG_FILE = _os.path.join(_tf.mkdtemp(), "config.json")
    try:
        base_before = PROVIDER_REGISTRY["neuralwatt"].get("api_base")
        model_before = PROVIDER_REGISTRY["neuralwatt"].get("model")
        assert base_before, "neuralwatt built-in must have a base"
        Config.set_provider_entry("neuralwatt", api_key="sk-merge-test")
        reg = PROVIDER_REGISTRY["neuralwatt"]
        assert reg.get("api_base") == base_before, \
            f"key-only update must not clobber base (got {reg.get('api_base')!r})"
        assert reg.get("model") == model_before, \
            f"key-only update must not clobber model (got {reg.get('model')!r})"
        assert reg.get("default_key") == "sk-merge-test"
    finally:
        prism32.Config.CONFIG_FILE = old


# ── user-prompt preservation ─────────────────────────────────────

def test_user_requests_survive_summarization():
    prism32._ACTIVE_GOAL = ""
    hist = [{"role": "system", "content": "sys"},
            {"role": "user", "content": "Design the quantum dot spidroin"},
            {"role": "assistant", "content": "on it"}]
    for i in range(30):
        hist.append({"role": "user", "content": f"Executed: cmd{i}\nResult:\nr{i}"})
    hist.append({"role": "user", "content": "also make it beat kevlar in tensile tests"})
    for i in range(10):
        hist.append({"role": "user", "content": f"Executed: tail{i}\nResult:\nt{i}"})
    summary = prism32._build_context_refresher(hist, keep_count=8)
    assert "USER REQUESTS" in summary
    assert "quantum dot spidroin" in summary
    assert "beat kevlar" in summary, "later user prompts must survive too"


# ── auto-compact threshold ───────────────────────────────────────

def test_auto_compact_fires_on_pct_of_window(monkeypatch):
    """Owner spec 2026-11-24: compact at 80% of the model's ACTUAL context."""
    monkeypatch.setattr(prism32.Config, "resolve_context_window", lambda: 20000)
    prism32.Config.AUTO_COMPACT_PCT = 80
    prism32.Config.AUTO_COMPACT_TOKENS = 0
    hist = [{"role": "system", "content": "s"}]
    for i in range(120):
        hist.append({"role": "user", "content": f"Executed: c{i}\nResult:\n" + "x" * 400})
        hist.append({"role": "assistant", "content": "ok " * 50})
    total = sum(prism32._msg_tokens(m) for m in hist)
    assert total >= 16000, f"test history must be over 80% of the window (got {total})"
    compacted = prism32._auto_compact_if_expensive(hist)
    assert compacted is True
    assert sum(prism32._msg_tokens(m) for m in hist) < total


def test_auto_compact_fires_on_threshold():
    old_threshold = prism32.Config.AUTO_COMPACT_TOKENS
    prism32.Config.AUTO_COMPACT_TOKENS = 4000  # tiny for the test
    try:
        hist = [{"role": "system", "content": "s"}]
        for i in range(80):
            hist.append({"role": "user", "content": f"Executed: c{i}\nResult:\n" + "x" * 400})
            hist.append({"role": "assistant", "content": "ok " * 50})
        before_tokens = sum(prism32._msg_tokens(m) for m in hist)
        assert before_tokens > 4000
        compacted = prism32._auto_compact_if_expensive(hist)
        after_tokens = sum(prism32._msg_tokens(m) for m in hist)
        assert compacted is True
        assert after_tokens < before_tokens
    finally:
        prism32.Config.AUTO_COMPACT_TOKENS = old_threshold


def test_auto_compact_off_when_below_threshold():
    old_threshold = prism32.Config.AUTO_COMPACT_TOKENS
    prism32.Config.AUTO_COMPACT_TOKENS = 1_000_000
    try:
        hist = [{"role": "system", "content": "s"},
                {"role": "user", "content": "hi"}]
        assert prism32._auto_compact_if_expensive(hist) is False
    finally:
        prism32.Config.AUTO_COMPACT_TOKENS = old_threshold


# ── opencode zen go-plan routing ─────────────────────────────────

def test_headers_include_opencode_session():
    from prism32 import build_headers
    h = build_headers(api_key="k", api_base="https://opencode.ai/zen/v1")
    assert "x-opencode-session" in h, "zen requests need the session routing header"
    h2 = build_headers(api_key="k", api_base="https://api.neuralwatt.com/v1")
    assert "x-opencode-session" not in h2


def test_friendly_402_hints_go_namespace():
    body = ('{"error":{"type":"invalid_request_error","message":"Insufficient balance. '
            'This request is pay-as-you-go, billed to OpenCode Models credits. Top up '
            'at https://opencode.ai/console/org_X/billing?credits=1. OpenCode Go covers '
            'only requests to the OpenCode Go provider."}}')
    msg = prism32._friendly_402(body, "https://opencode.ai/zen/v1")
    assert "402" in msg
    assert "opencode-go/" in msg, "must point at the Go-covered model namespace"
    assert "https://opencode.ai/console/org_X/billing?credits=1" in msg, "URL kept whole"
    assert "Invalid credential" not in msg


# ── redundant-command cleanup (efficiency pass) ──────────────────

def test_bgs_removed_from_agent_names():
    from prism32 import _AGENT_CMD_NAMES
    assert 'bgs' not in _AGENT_CMD_NAMES, "/bgs was removed as redundant with bare /bg"
    assert 'bg' in _AGENT_CMD_NAMES


def test_set_model_delegates_to_apply_selection():
    """Class G fix: /set model must wire the full provider context
    (base+key+model), not just Config.MODEL — the old code set only
    Config.MODEL and left provider/base/key on the old vendor."""
    # Source-level contract: the /set model branch must call
    # _apply_model_selection (the same wiring /model and /provider use share).
    import inspect
    src = inspect.getsource(prism32)
    # Find the /set model dispatch block
    idx = src.find("elif set_key == 'model':")
    assert idx != -1, "/set model handler must exist"
    block = src[idx:idx+600]
    assert "_apply_model_selection" in block, \
        "/set model must delegate to _apply_model_selection (wires base+key)"


def test_system_prompt_execute_table_is_deduplicated():
    """Class A: the execute-block table must not restate the prose
    sections (it was 1,286 chars of duplication re-billed per request)."""
    from prism32 import SYSTEM_PROMPT
    # The deduplicated table keeps only the unique rows
    assert "Commands you can use inside execute blocks" in SYSTEM_PROMPT
    # The old duplicated rows must be gone (covered by prose sections)
    assert "- /quantum <key>:<value>, /quantum <key>:, /quantum (shared agent context)." not in SYSTEM_PROMPT
    assert "- /delegate <task> [--provider <name>] (synchronous subagent)." not in SYSTEM_PROMPT
    # But the unique rows survive
    assert "/json <file>" in SYSTEM_PROMPT
    assert "/memory path" in SYSTEM_PROMPT


def test_subagent_prompt_has_json_and_board():
    """I-9: subagent prompt must cover /json and /board (dispatcher handles
    both; the prompt omitted them)."""
    prompt = prism32._get_subagent_system_prompt()
    assert "/json <file>" in prompt
    assert "/board" in prompt
    # Quantum tutorial survived (the fenced examples are kept)
    assert "/quantum <key>:<value>" in prompt


# ── result cap disclosure ─────────────────────────────────────────

def test_cap_result_discloses_skipped_volume():
    result = "HEAD\n" + "x" * 3000 + "\nTAIL"
    capped = prism32._cap_result_for_model(result)
    assert "HEAD" in capped and "TAIL" in capped
    import re as _re
    m = _re.search(r'\[... (\d+) chars in the middle truncated', capped)
    assert m and int(m.group(1)) > 1000, "marker must disclose the skipped size"


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
