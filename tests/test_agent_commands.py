"""Every command the SYSTEM_PROMPT advertises for execute blocks must
actually route in _try_plugin_cmd.

The subagent audit (v7.2) found /remember /recall /memories /forget
advertised to agents but falling through to the shell — the prompt was
lying to the agent. This test verifies each canonical agent command
routes (returns a usage/answer string instead of None) AND is mentioned
in SYSTEM_PROMPT, so a new advertised-but-dead command — or a routed
but unadvertised one — fails here before it can confuse an agent
(or poison RL training).
"""
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import prism32
from prism32 import SYSTEM_PROMPT, _try_plugin_cmd

# Canonical agent-usable commands inside execute blocks. Keep in sync
# with SYSTEM_PROMPT's "Commands you can use inside execute blocks" list.
AGENT_COMMANDS = [
    "quantum", "board", "delegate", "spawn", "collect", "subagents",
    "remember", "recall", "memories", "forget",
    "auto", "skill-list", "skill-load", "shard",
    "harness", "evolve", "extend", "memory", "json",
]


def test_advertised_commands_route_in_execute_blocks():
    dead = [c for c in AGENT_COMMANDS
            if _try_plugin_cmd(f"/{c}") is None]
    assert not dead, f"advertised to agents but fall through to the shell: {dead}"


def test_every_agent_command_is_advertised_in_prompt():
    missing = [c for c in AGENT_COMMANDS
               if f"/{c}" not in SYSTEM_PROMPT]
    assert not missing, f"routed for agents but never advertised in prompt: {missing}"


def test_ltm_commands_full_round_trip_from_execute_blocks():
    # /remember → /memories → /recall → /forget, all via the agent router
    r = _try_plugin_cmd("/remember smoke-ltm-entry: the kettle is blue --tag smoke")
    assert r and "Remembered" in r
    m = re.search(r"mem_(\d+)", r)
    assert m, f"no memory id in {r!r}"
    mid = m.group(1)

    listing = _try_plugin_cmd("/memories")
    assert listing and "smoke-ltm-entry" in listing

    hit = _try_plugin_cmd("/recall kettle")
    assert hit and "kettle is blue" in hit

    d = _try_plugin_cmd(f"/forget {mid}")
    assert d and "Deleted" in d
    d2 = _try_plugin_cmd(f"/forget {mid}")
    assert "not found" in d2


def test_board_attribution_from_router():
    from prism32 import Mission, mission_board_read, _mission_ws_expire
    prism32._ACTIVE_MISSION = None
    m = Mission("attribution test")
    prism32._ACTIVE_MISSION = m
    try:
        _try_plugin_cmd("/board hello from the router", who="shard_sa_9")
        content = mission_board_read()
        assert "shard_sa_9" in content and "hello from the router" in content
    finally:
        prism32._ACTIVE_MISSION = None
        _mission_ws_expire(m)
