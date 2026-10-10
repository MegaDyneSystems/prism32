"""Tests for the mission workspace: shared info board + goals file.

The mission-scoped files (board.md, goals.md) must:
- be created when a mission starts
- accept appends from any agent (thread-safe)
- have their tail injected into every shard's context
- mirror the live step tree in goals.md
- expire (directory deleted) the instant the mission completes
- answer /board from execute blocks (append / read / clear / no-mission)
"""
import os
import sys
import threading

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import prism32
from prism32 import (
    Config,
    Mission,
    MissionTodo,
    _ACTIVE_MISSION,
    _mission_ws_expire,
    _mission_ws_init,
    _mission_ws_sync,
    mission_board_append,
    mission_board_path,
    mission_board_read,
    mission_goals_path,
    _try_plugin_cmd,
)


def _fresh_mission(goal="test goal"):
    prism32._ACTIVE_MISSION = None
    m = Mission(goal)
    prism32._ACTIVE_MISSION = m
    return m


def test_mission_creates_workspace_files():
    m = _fresh_mission("check the disk")
    assert os.path.isfile(mission_board_path(m.id))
    assert os.path.isfile(mission_goals_path(m.id))
    with open(mission_goals_path(m.id)) as f:
        assert "check the disk" in f.read()
    prism32._ACTIVE_MISSION = None
    _mission_ws_expire(m)


def test_board_append_and_read():
    m = _fresh_mission()
    r = mission_board_append("ports 22 and 80 open", who="shard1")
    assert r.startswith("Board: noted")
    content = mission_board_read()
    assert "ports 22 and 80 open" in content
    assert "shard1" in content
    prism32._ACTIVE_MISSION = None
    _mission_ws_expire(m)


def test_board_concurrent_appends_all_land():
    m = _fresh_mission()
    errs = []
    def worker(i):
        try:
            mission_board_append(f"finding {i}", who=f"shard{i}")
        except Exception as e:  # pragma: no cover
            errs.append(e)
    threads = [threading.Thread(target=worker, args=(i,)) for i in range(8)]
    for th in threads: th.start()
    for th in threads: th.join()
    assert not errs
    content = mission_board_read()
    for i in range(8):
        assert f"finding {i}" in content
    prism32._ACTIVE_MISSION = None
    _mission_ws_expire(m)


def test_board_requires_active_mission():
    prism32._ACTIVE_MISSION = None
    assert "no active mission" in mission_board_append("x")
    assert "no active mission" in mission_board_read()


def test_board_routed_from_execute_blocks():
    m = _fresh_mission()
    # append via the execute-block command router
    out = _try_plugin_cmd("/board service nginx is running")
    assert out and out.startswith("Board: noted")
    # read back
    out = _try_plugin_cmd("/board")
    assert "service nginx is running" in out
    # clear
    out = _try_plugin_cmd("/board clear")
    assert out == "Board: cleared."
    assert "(board cleared)" in _try_plugin_cmd("/board")
    # no mission → informative, not an error
    prism32._ACTIVE_MISSION = None
    assert "no active mission" in _try_plugin_cmd("/board")
    assert "no active mission" in _try_plugin_cmd("/board whatever")


def test_goals_file_mirrors_step_states():
    m = _fresh_mission("audit the prompt")
    t1 = m.add_todo("step one")
    t2 = m.add_todo("step two")
    _mission_ws_sync(m)
    with open(mission_goals_path(m.id)) as f:
        txt = f.read()
    assert "[ ] step one" in txt and "[ ] step two" in txt
    m.todos[t1].state = "done"
    m.todos[t2].state = "running"
    _mission_ws_sync(m)
    with open(mission_goals_path(m.id)) as f:
        txt = f.read()
    assert "[x] step one" in txt and "[~] step two" in txt
    prism32._ACTIVE_MISSION = None
    _mission_ws_expire(m)


def test_render_context_includes_board():
    m = _fresh_mission("boarded mission")
    t1 = m.add_todo("do the thing")
    mission_board_append("the answer is 42", who="shard0")
    ctx = m.render_context(m.todos[t1])
    assert "the answer is 42" in ctx
    assert "/board" in ctx          # instructions on how to post
    prism32._ACTIVE_MISSION = None
    _mission_ws_expire(m)


def test_render_context_empty_board_is_quiet():
    m = _fresh_mission("quiet mission")
    t1 = m.add_todo("solo step")
    ctx = m.render_context(m.todos[t1])
    assert "SHARED INFO BOARD" not in ctx   # header-only board → no noise
    assert "/board" in ctx                   # but usage hint stays
    prism32._ACTIVE_MISSION = None
    _mission_ws_expire(m)


def test_workspace_expires_on_completion():
    m = _fresh_mission("expiring mission")
    mission_board_append("ephemeral", who="x")
    d = os.path.dirname(mission_board_path(m.id))
    assert os.path.isdir(d)
    m.state = "complete"
    _mission_ws_expire(m)
    assert not os.path.exists(d)


def test_orphan_cleanup_wipes_stale_dirs():
    import shutil
    m = _fresh_mission("orphaned run")   # simulates a crashed mission
    d = os.path.dirname(mission_board_path(m.id))
    assert os.path.isdir(d)
    prism32._ACTIVE_MISSION = None       # process "died"
    prism32._mission_ws_cleanup_orphans()
    assert not os.path.isdir(d)
