# Prism32

Prism32 is a self-extending, self-repairing terminal AI super-agent. One Python file, stdlib-only. A real Jarvis. A DIY Palantir. It generates plugins for itself, delegates to subagents, absorbs external AI harnesses, synchronizes state through quantum context, persists everything it learns, and becomes more powerful every time you use it. There is no fixed feature ceiling.

Full manual: `README.md`.

## Fastest Start

```sh
git clone https://github.com/MegaDyneSystems/prism32.git && cd prism32 && bash install.sh && prism32
```

Most-used commands:

```text
/help                 command list
/provider list        providers
/provider key KEY     set API key
/model                browse/select model
/goal <task>          autonomous task mode
/bash <cmd>           run shell command
/memory edit          edit machine memory
/remember <text>      save long-term memory
/delegate <task>      sync subagent
/spawn <task>         async subagent
/extend <goal>        create/load a temporary AI-generated plugin
/extend prompt        print pasteable plugin-generation prompt
/evolve on            self-repair/plugin/tool-scan context
/quit                 exit
```

Press Escape to stop active AI work, API waits, foreground commands, or goal mode.

## One-Line Install

Unix, Linux, macOS, BSD:

```sh
git clone https://github.com/MegaDyneSystems/prism32.git && cd prism32 && bash install.sh
```

User-local non-root install:

```sh
git clone https://github.com/MegaDyneSystems/prism32.git && cd prism32 && bash install.sh -y
```

Run without installing:

```sh
git clone https://github.com/MegaDyneSystems/prism32.git && cd prism32 && python3 prism32.py --setup-runtime && python3 prism32.py
```

Windows PowerShell:

```powershell
git clone https://github.com/MegaDyneSystems/prism32.git; cd prism32; powershell -ExecutionPolicy Bypass -File .\install.ps1
```

Termux:

```sh
pkg update && pkg install python git && git clone https://github.com/MegaDyneSystems/prism32.git && cd prism32 && python prism32.py --setup-runtime && python prism32.py
```

## Why It Is Different

Prism32 is a self-extending, self-repairing, multi-agent command system. It is not a chat window — it is a real Jarvis, a DIY Palantir that grows more powerful every time you use it.

The agent bootstraps itself: auto-detects OS and CPU, scans local tools, absorbs external AI harnesses, generates plugins on the fly for missing capabilities, delegates to subagents running different models, synchronizes state through quantum context, and persists everything it learns into memory files that survive restarts. It can do all of this autonomously from inside execute blocks mid-task without operator approval.

- **Self-evolution without guardrails.** The agent inspects its own source, diffs against a baseline, generates plugins to fix gaps, syntax-checks them, loads them immediately, and uses the new commands in the same session. It can git-pull and reinstall itself.
- **Hot-swappable plugins the agent creates for itself.** `/extend temp add a command that ingests MQTT from this Zigbee network` — the model generates a stdlib Python plugin, Prism32 validates and loads it, and the agent calls the new command in its next execute block. No restart. No pip. No human.
- **Quantum context as a shared brain.** Subagents drop results into a thread-safe key-value store. The main agent reads them without polling. Every agent sees every other agent's findings. System prompts rebuild mid-task with the latest state.
- **Model mixing for cost and speed.** Talk to a strong model. Subagents run on cheap fast ones. Thousands of tokens of infrastructure scanning happen on a free-tier model while your main session stays on the expensive reasoning model. `/delegate scan this subnet --provider groq` costs almost nothing.
- **Harness absorption.** Prism32 detects every other AI CLI on the machine and can coordinate them as tools. It becomes the commander over every AI agent installed on the system.
- **The peripheral surface is the entire Linux device tree.** GPIO, I2C, SPI, serial, CAN, SDR, cameras, Zigbee sticks, Z-Wave, Bluetooth, motor controllers, relays. If Linux has a /dev node for it, the agent can script against it. Combine with on-the-fly plugin generation for universal hardware control that learns new protocols mid-session.
- **Platform reach means deploy anywhere.** Same binary runs on a Raspberry Pi in a robot, a Steam Deck, a jailbroken Kindle, a Tesla MCU, a DEC AlphaStation, a Synology NAS, a $15 OpenWrt travel router, an SGI Octane, and an AWS Graviton instance. Auto-detects architecture, package manager, and shell.
- **Cost scales to zero.** Local Ollama/llama.cpp models run entirely offline. Switch to cloud models only when needed. You control cost-per-task by choosing which model does which job.
- **Theoretically unbounded.** Because the agent writes and loads plugins, spawns subagents, absorbs external harnesses, evolves its own context, and persists everything it learns, there is no fixed feature ceiling. Every task expands the agent's capability surface. The operator describes goals. The agent builds the path.

No pip dependencies. No Node.js. No browser. No database. One Python file.

## Quick Examples

```text
prism32> inspect this git repo, run the tests, and summarize what failed
```

```text
/goal audit this server for disk pressure, top CPU users, open ports, and failed services; report only
```

```text
/delegate summarize the last 20 commits and identify risky changes
```

```text
/spawn scan this repository for TODO comments and group them by subsystem
/subagents
/collect <id>
```

```text
/memory append This NetBSD host uses /usr/pkg/bin/python3.12 and pkgin.
/remember The release command is python -m pytest && git tag vX.Y.Z
/recall release command
```

```text
/evolve on
/evolve diff
```

```text
/extend temp add a command that summarizes pytest output and highlights failures
/extend prompt
```

## Supported Systems

Core requirement: Python 3.7+ and a usable shell.

Primary targets:

- Linux
- macOS
- FreeBSD, NetBSD, OpenBSD
- WSL/WSL2
- Android Termux
- Windows with `install.ps1` and reduced terminal interjection support

NVIDIA targets:

- Grace CPU / Grace Hopper: ARM64/aarch64 Linux with Python 3.7+.
- Jetson Nano/Xavier/Orin, Jetson Linux, L4T, JetPack: Linux/ARM64 with Python 3.7+.
- DGX OS: Ubuntu-based Linux.
- NGC/CUDA/AI Enterprise containers: supported when Python, shell tools, and API network access are present.
- DRIVE OS: best effort; Linux side is most practical, QNX side depends on Python availability.
- CUDA is used through a local model server or OpenAI-compatible gateway, not directly by Prism32.

3D printer and smart home targets:

- OctoPrint, Klipper (Mainsail/Fluidd), PrusaLink: Raspberry Pi Linux/ARM with Python 3.7+.
- Home Assistant OS/Supervised/Core: Linux with Python 3.7+.
- OpenHAB, Domoticz, Homebridge: Linux hosts with Python 3.7+ installed.
- Marlin, Duet, ESPHome, Tasmota: MCU/appliance devices. Point Prism32 at the companion Linux host on the same network.

Devices you can control with Prism32 on a companion Linux host:

- Robot vacuums: Roomba, Roborock, Dreame, Ecovacs (via Home Assistant, Valetudo, or REST).
- Zigbee/Z-Wave: lights, switches, sensors, locks, thermostats (via Zigbee2MQTT, Z-Wave JS).
- IP cameras, smart speakers, garage controllers, irrigation, energy monitors.
- Shelly, Sonoff, Tasmota devices over HTTP/MQTT.
- Prism32 runs on the coordinator host, or directly on any device with Python 3.7+, a shell, and network access. Use it to write automations, debug MQTT, query device APIs, and script multi-device routines. Use /extend for device-specific plugins.

Real hardware it has been used on: Steam Deck, PS3/PS4, Nintendo Switch, Anbernic and Retroid handhelds, Raspberry Pi 1-5 and Zero, BeagleBone, Orange Pi, Milk-V and VisionFive RISC-V boards, OpenWrt travel routers, MikroTik, GL.iNet, Synology and QNAP NAS, Android phones via Termux, PinePhone, reMarkable, Tesla MCU, Comma.ai Openpilot, DJI drones, ArduPilot, NVIDIA Shield, Kodi boxes, jailbroken Kindle and Kobo, SGI/SPARC/DEC/HP/IBM legacy Unix workstations, Antminer control boards, LinuxCNC, digital signage, and thin clients.

Best-effort targets include containers, ChromeOS/Crostini, Proxmox, TrueNAS, pfSense, OPNsense, OpenWrt/BusyBox, NAS appliances, Solaris/SunOS/illumos, AIX, HP-UX, IRIX, Tru64, Haiku, QNX, MINIX, Cygwin/MSYS2, IBM z/OS, IBM i PASE, and OpenVMS where compatible Python exists.

Architecture labels include x86/x64, ARM, RISC-V, LoongArch, PowerPC/POWER, MIPS, SPARC, S/390x/IBM Z, Alpha, PA-RISC, Itanium, Elbrus, VAX, and SGI MIPS.

CI checks Ubuntu and macOS syntax on Python 3.9 through 3.13. Unit tests run on Ubuntu for Python 3.9 through 3.13. The project environment has also syntax-checked deployed copies on NetBSD 10.1 and macOS 10.13, with NetBSD PTY smoke tests used for terminal behavior.

## Low-End Hardware

Prism32 stays light because it is a single Python process and a small script. It does not load a web UI, package tree, or vector database. The main cost is usually the model API, local model inference, shell commands, package installs, or network scans.

For slow CPUs or fragile terminals:

```sh
prism32 --slow-cpu
```

Inside Prism32:

```text
/stream off
/memctx 512
```

## Plugin Example

Create `~/.prism32/plugins/hello.py`:

```python
USAGE_CONTEXT = """Hello plugin available:
- /hello [name]: print a greeting for testing plugin loading.
"""

def cmd_hello(args_str, history, cmd_log):
    print("Hello, " + (args_str.strip() or "operator"))

def register(api):
    api.registry.register("hello", cmd_hello, description="Say hello")

def on_boot(api):
    api.inject_context(USAGE_CONTEXT)
```

Restart Prism32:

```text
/hello Ada
```

Use `/extend prompt` to print a longer pasteable plugin cheat sheet for another AI chatbot. Plugins should define a `USAGE_CONTEXT` string and inject it from `on_boot(api)` so Prism32 agents know the plugin's commands/options without guessing.

## Important Commands

```text
/help                 command list
/provider list        provider list
/provider key KEY     set API key
/model                browse/select model
/goal <task>          autonomous task mode
/bash <cmd>           run shell command
/memory edit          edit machine memory
/remember <text>      save long-term memory
/delegate <task>      sync subagent
/spawn <task>         async subagent
/harness scan         detect external AI CLIs
/extend <goal>        generate/load temporary plugin
/evolve on            enable self-documentation context
/evolve diff          compare current file to baseline
/quit                 exit
```

All commands require `/`. Bare text goes to the AI.

## Safety

Prism32 can run shell commands. Review risky actions, use read-only audit prompts on servers, and press Escape to stop active work.
