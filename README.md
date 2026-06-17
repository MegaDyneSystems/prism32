# Prism32 v6.7

Prism32 is a self-extending, self-repairing, self-evolving terminal AI super-agent from MegaDyne Systems. One Python file, stdlib-only. A real Jarvis. It auto-detects its platform, absorbs external AI harnesses, generates plugins on the fly for missing capabilities, delegates to subagents running different models, synchronizes state through quantum context, persists everything it learns, and becomes more powerful every time you use it. There is no fixed feature ceiling — every task expands what the agent can do. it can turn any PC or low end hardware SBC or laptop etc into a robotic assistant that can control external peripherals and can also run on robots and IOT devices with shell and python on bare metal

It is designed for modern PC's and older machines: no Node.js, no browser runtime, no pip dependencies, and no local database server. Runtime state lives in small files under `~/.prism32/`.

This README is the full operator guide. A shorter GitHub front-page summary is in `README-GITHUB.md`.

## Cheat Sheet: Fastest Path

Install and start on Unix/Linux/macOS/BSD:

```sh
git clone https://github.com/MegaDyneSystems/prism32.git && cd prism32 && bash install.sh && prism32
```

No-root install:

```sh
git clone https://github.com/MegaDyneSystems/prism32.git && cd prism32 && bash install.sh -y && ~/.local/bin/prism32
```

Run directly without install:

```sh
git clone https://github.com/MegaDyneSystems/prism32.git && cd prism32 && python3 prism32.py --setup-runtime && python3 prism32.py
```

Most-used first commands inside Prism32:

```text
/help                 Show all commands
/provider list        Show providers
/provider openrouter  Switch provider
/provider key KEY     Set API key
/model                Browse/select models
/config               Show active config
/goal <task>          Autonomous multi-step mode
/bash <cmd>           Run a shell command manually
/memory edit          Edit machine notes injected into context
/remember <text>      Store long-term memory
/delegate <task>      Run a subagent now
/spawn <task>         Start a background subagent
/extend <goal>        Generate/load a temporary plugin for a missing capability
/extend prompt        Print the plugin-generation prompt
/evolve on            Enable self-repair/plugin/tool-scan context
/quit                 Exit
```

Practical starter prompts:

```text
inspect this machine, identify OS/architecture/package manager, and save useful notes to startup memory
```

```text
inspect this git repo, run the tests, and summarize what failed without changing files
```

```text
/goal audit this server for disk pressure, failed services, open ports, and risky logs; report only
```

Stop anything that is taking too long:

```text
Press Escape.
```

## Quick Start

Unix, Linux, macOS, and BSD:

```sh
git clone https://github.com/MegaDyneSystems/prism32.git
cd prism32
bash install.sh
prism32
```

Non-root user-local install:

```sh
git clone https://github.com/MegaDyneSystems/prism32.git && cd prism32 && bash install.sh -y
```

Run without installing:

```sh
git clone https://github.com/MegaDyneSystems/prism32.git
cd prism32
python3 prism32.py --setup-runtime
python3 prism32.py
```

Windows PowerShell:

```powershell
git clone https://github.com/MegaDyneSystems/prism32.git
cd prism32
powershell -ExecutionPolicy Bypass -File .\install.ps1
prism32
```

Android Termux:

```sh
pkg update
pkg install python git
git clone https://github.com/MegaDyneSystems/prism32.git
cd prism32
python prism32.py --setup-runtime
python prism32.py
```

Direct local model example:

```sh
python3 prism32.py --api http://127.0.0.1:8080 --model local-model
```

NVIDIA Jetson, DGX, or CUDA-backed local model example:

```sh
python3 prism32.py --api http://127.0.0.1:8080 --model local-cuda-model
```

OpenRouter example:

```sh
python3 prism32.py --api https://openrouter.ai/api/v1 --api-key sk-or-v1-... --model deepseek/deepseek-v4-flash
```

Inside Prism32, use `/help` for the live command list.

## What Prism32 Does

Prism32 combines several systems in one terminal harness:

- Interactive chat with OpenAI-compatible model APIs.
- Active task mode: the AI can emit shell commands in fenced `execute` blocks; Prism32 runs them, captures output, and asks the AI what to do next.
- Autonomous goal mode with `/goal <task>` for multi-step tasks up to a configurable step limit.
- Synchronous and asynchronous subagents with `/delegate`, `/spawn`, `/subagents`, and `/collect`.
- Plugin loading from `~/.prism32/plugins/*.py` for custom slash commands, providers, themes, context injection, timers, and HTTP helpers.
- Self-extension with `/extend`: Prism32 can ask the configured model to generate a stdlib-only plugin, syntax-check it, write it, load it, and use the new command immediately.
- Memory and evolution files that let the system remember machine quirks, recurring fixes, tools, baselines, user rules, and long-term notes.
- Promptshard files for structured job assignments and subagent deployment.
- Harness absorption: Prism32 can detect external AI CLIs such as OpenCode, Codex CLI, Claude Code, Aider, Gemini CLI, Goose, and Cursor Agent, then include their availability in context.
- Terminal interjection while streaming: type while the AI is responding, press Enter, and your message interrupts the model.
- Bare Escape cancellation: press Escape to stop active AI streaming, non-streaming API waits, foreground shell commands, and goal-mode work.

## The Emergent Agent

Prism32 isn't chatbot. It is a self-extending, self-repairing, multi-agent command system that becomes more capable the longer it runs.

Each capability feeds the others. The agent bootstraps itself: it detects the OS and CPU it is running on, scans for local tools, absorbs external AI harnesses into its context, generates plugins on the fly for missing capabilities, delegates sub-tasks to subagents running different models, synchronizes state through quantum context, and records everything it learns into persistent memory files that survive restarts. None of this requires operator approval. The agent can decide to create a plugin, spawn a subagent, enable evolve mode, or absorb a harness entirely on its own, from inside an execute block, mid-task.

The combination creates real emergent power:

**Self-evolution without guardrails.** The agent can inspect its own source code against a baseline, diff it, generate a plugin to fix a gap, syntax-check the plugin, load it immediately, and use the new command in the same session. It can also git-pull and reinstall itself. The boundaries of what it can do expand at runtime.

**Hot-swappable plugins the agent creates for itself.** `/extend temp add a command that ingests MQTT telemetry from this Zigbee network` — the model generates a stdlib Python plugin, Prism32 validates and loads it, and the agent calls the new command in its next execute block. No restart. No pip. No human needed. Temporary plugins disappear when Prism32 exits; permanent ones load on every boot, can automate long tool call chains with a temporary plugin

**Quantum context as a shared brain.** Every main agent, subagent, and async spawned agent reads and writes to the same thread-safe key-value store. A subagent scanning open ports drops its findings into quantum context, and the main agent picks them up without polling. Subagents running different providers see each other's results. The system prompt is rebuilt mid-task to include the latest quantum state.

**Model mixing for cost and speed.** You talk to a strong model. Subagents run on cheap fast ones. Thousands of tokens of infrastructure scanning happen on a free-tier model while your main session stays on the expensive reasoning model for analysis. `/delegate scan every host on this subnet --provider groq` costs almost nothing. No other terminal agent harness lets you mix providers and models per-task with zero configuration changes.

**Harness absorption.** Prism32 detects OpenCode, Codex CLI, Claude Code, Aider, Gemini CLI, Goose, Cursor Agent, and other AI CLIs on the system. It injects their capabilities into its context. It can then delegate a task to a super-subagent seeded with those tools. Prism32 becomes a coordinator over every AI agent CLI installed on the machine.

**The peripheral surface is the entire Linux device tree.** USB serial adapters, GPIO pins, I2C sensors, SPI displays, CAN buses, SDR dongles, cameras, microphones, speakers, relays, motor controllers, 3D printer serial ports, Zigbee coordinators, Z-Wave sticks, Bluetooth adapters, WiFi interfaces, and anything with a /dev node. If Linux can talk to it, the agent can script against it. Combine that with on-the-fly plugin generation and you have a universal hardware controller that learns new protocols mid-session.

**Platform reach means deployment everywhere.** The same Prism32 binary runs on a Raspberry Pi inside a robot, an old laptop in a garage, a Steam Deck, a jailbroken Kindle, a Tesla MCU, a DEC AlphaStation, a Synology NAS, a $15 OpenWrt travel router, an SGI Octane, and an AWS Graviton instance, a bluetooth speaker. It auto-detects the architecture, the package manager, and the shell, then adjusts every command it runs. Install once, deploy anywhere.

**Cost scales down to zero.** Local llama.cpp or Ollama models run entirely offline on the same machine. No API costs. No cloud dependency. Use `/provider local` for private work, switch to OpenRouter for hard reasoning, and let subagents run on Groq's free tier for bulk scanning. You control the cost-per-task by choosing which model does which job.

**The system is theoretically unbounded.** Because the agent can write and load plugins, spawn subagents, absorb external harnesses, evolve its own context, and persist everything it learns, there is no fixed feature ceiling. Every task expands the agent's capability surface. The operator does not configure features — they describe goals, and the agent builds the path.

**Emergent capabilities on weird hardware.** When you put an agent that can write and load its own plugins onto a device that was never designed to host an AI, the result is not a chatbot on a Pi — it is a hardware-native intelligence that reshapes what the device can do. A $15 OpenWrt travel router with a USB Zigbee stick becomes a self-healing smart-home coordinator that generates MQTT plugins for whatever devices join the network. A jailbroken Kindle on a bookshelf becomes an AI reading companion that fetches, summarizes, and cross-references your library. A Tesla MCU or Comma.ai Openpilot device diagnoses CAN bus traffic, scripts custom dashboards, and hot-loads driving-data plugins mid-route. A Raspberry Pi inside a 3D printer enclosure learns G-code patterns, generates print-monitoring plugins, and self-corrects without cloud dependency. A DEC AlphaStation from 1994 or an SGI Octane from 1997 running a local model is a literal time capsule with a modern AI brain. A Linux-based oscilloscope or logic analyzer gets an operator that understands signal analysis. An Antminer control board running Prism32 can monitor hashrate, adjust pools, and rebuild firmware configs. The pattern is the same everywhere: install, describe the goal, and the agent extends itself to meet the hardware.

Prism32 is a Jarvis that lives in your terminal, runs on your hardware, costs what you choose to spend, and grows more powerful every time you use it.

## Requirements

- Python 3.7 or newer.
- A terminal or console.
- A shell for command execution.
- Network access to your AI model API unless you use a local server.
- No pip packages are required for the core program.

Optional tools make Prism32 more capable:

- `git` for updates, repo inspection, and code tasks.
- `bash` for the Unix installer and richer shell automation.
- Local model servers such as llama.cpp or Ollama.
- External AI harnesses such as OpenCode, Codex CLI, Claude Code, Aider, Gemini CLI, Goose, or Cursor Agent.

## Supported Systems

Prism32 is a pure-stdlib Python program, so the real portability rule is simple: if Python 3.7+ can run and the system has a usable shell, Prism32 should start. Some features depend on terminal support, process control, SSL certificates, and local command availability.

The repository has automated CI syntax checks on Ubuntu and macOS using Python 3.9, 3.10, 3.11, 3.12, and 3.13. Unit tests run on Ubuntu across the same Python versions. Deployed copies have also been syntax-checked on NetBSD 10.1 and macOS 10.13 in the development environment; NetBSD PTY smoke tests have been used for terminal behavior.

Primary targets:

- All Linux distributions with Python 3.7+.
- macOS with Python 3.7+.
- FreeBSD, NetBSD, and OpenBSD with Python 3.7+.
- WSL and WSL2.
- Android through Termux.
- Windows with Python 3.7+ through `install.ps1`, with reduced terminal interjection support.

NVIDIA platform notes:

- NVIDIA Grace CPU and Grace Hopper systems work as ARM64/aarch64 Linux systems when Python 3.7+ is installed
- NVIDIA Jetson Nano, Xavier, Orin, Jetson Linux, L4T, and JetPack systems should work as Linux/ARM64 targets when Python 3.7+ and shell tools are available.
- NVIDIA NGC, CUDA, and AI Enterprise containers will work when the container includes Python 3.7+, a shell, and network access to a model endpoint
- NVIDIA DRIVE OS is best effort: the Linux side should work if Python and a shell are available; QNX-side use depends on having a compatible Python runtime.
- Prism32 does not require or call CUDA directly. For GPU acceleration of tasks, have your MDS AI agent create custom Cuda plugins

3D printer and maker systems:

- OctoPrint (Raspberry Pi Linux with Python 3) should work as a standard Linux/ARM target.
- Klipper with Mainsail or Fluidd (Raspberry Pi Linux with Python 3) should work.
- PrusaLink / Prusa Connect (Raspberry Pi Linux with Python) should work.
- Repetier-Server (Linux with Python) should work.
- Marlin, RepRapFirmware, and Duet are MCU firmwares and cannot run Prism32 directly. Point Prism32 at the companion Raspberry Pi or host machine connected to the printer.
- Use /memory append to save G-code paths, printer serial ports, material profiles, and slicing workflows for faster AI-assisted print management.

Smart home and IoT hub systems:

- Home Assistant OS, Home Assistant Supervised, and Home Assistant Core (Linux with Python 3) should work.
- OpenHAB (Linux, requires Python 3.7+ installed alongside) should work.
- Domoticz (Linux with Python available) should work.
- Homebridge (Linux, requires Python 3.7+ installed alongside) should work.
- Hubitat, SmartThings, and ESPHome are appliance/MCU systems. Point Prism32 at a companion Linux host on the same network.
- Raspberry Pi OS and Raspbian are already covered as standard Linux targets.
- Use startup memory to record MQTT brokers, Zigbee2MQTT paths, API tokens, device lists, and automation names so the agent can help debug, script, and monitor.

Robot vacuums, IoT devices, and automation hardware:

- iRobot Roomba, Roborock, Dreame, Ecovacs, and other Wi-Fi vacuums are typically controlled through Home Assistant, Valetudo, or REST APIs. Prism32 can run on the same Linux host that manages these devices.
- Zigbee and Z-Wave hardware (lights, switches, sensors, locks, thermostats, blinds) managed through Zigbee2MQTT, Z-Wave JS, or deCONZ.
- IP cameras (RTSP/ONVIF), smart speakers, smart displays, garage door controllers, irrigation systems, and energy monitors.
- Shelly, Sonoff, and Tasmota-flashed devices accessible over HTTP/MQTT.
- Many IoT devices and robot vacuums use lightweight MCU firmware without Python or a shell. If a device runs embedded Linux with Python 3.7+, a shell, and network access, Prism32 can run directly on it. Check your device specs.
- Use /extend to create plugins for specific device APIs. Use startup memory and /remember to store device names, IPs, MQTT topics, and common automation patterns.

Real-world devices and hardware people can target with Prism32:

Game consoles and handhelds: Steam Deck, PS3/PS4 (Linux), Nintendo Switch (L4T), Anbernic RG series, Retroid Pocket, AYN Odin, GPD Win, Aya Neo, Miyoo Mini (OnionOS).

Single-board computers: Raspberry Pi 1 through 5 and Zero, BeagleBone, Orange Pi, Banana Pi, Pine64, ODROID, Asus Tinker Board, LattePanda, Milk-V, VisionFive, Sipeed Lichee RV.

Routers and network gear: OpenWrt devices (Linksys, TP-Link, GL.iNet travel routers), MikroTik RouterBOARD, Ubiquiti EdgeRouter and UniFi, Turris Omnia, pfSense/OPNsense appliances.

NAS and server appliances: Synology, QNAP, TrueNAS, Unraid, WD My Cloud, Asustor, TerraMaster, Proxmox VE hosts.

Phones and tablets: Android phones and tablets via Termux, PinePhone, Librem 5, Fairphone, iPad and iPhone via iSH, Onyx Boox e-ink Android tablets, reMarkable tablet.

Automotive: Tesla MCU and infotainment, Comma.ai Openpilot devices, Automotive Grade Linux head units.

TV and streaming: NVIDIA Shield, Fire TV and Cube, Chromecast with Google TV, Kodi boxes running LibreELEC or OSMC.

Drones and robotics: DJI companion computers, ArduPilot and PX4 companion boards, ROS robots, Boston Dynamics Spot payload computers, Unitree robots.

Retro and legacy workstations: SGI Indy/Octane/O2 (IRIX/MIPS), Sun Ultra and Blade (Solaris/SPARC), DEC AlphaStation (Tru64/Alpha), HP 9000 (HP-UX/PA-RISC), IBM RS/6000 (AIX/POWER), Apple PowerPC Macs (Linux/PPC), Amiga with PPC accelerator.

Other favorites: jailbroken Kindle and Kobo e-readers, AsteroidOS smartwatches, Antminer and Whatsminer control boards, GPU mining rigs, Linux-based oscilloscopes and logic analyzers, LinuxCNC controllers, digital signage players, kiosk systems, thin clients, Google Coral dev boards.

Best-effort targets and environment classes:

- ChromeOS/Crostini
- Docker, Podman, Kubernetes pods, LXC, and CI runners.
- Proxmox VE, TrueNAS, FreeNAS, pfSense, OPNsense, Unraid, OpenMediaVault, and NAS appliance shells.
- OpenWrt, BusyBox, Entware, Yocto, and Buildroot style embedded Linux.
- SteamOS, Fedora CoreOS, Silverblue, Kinoite, rpm-ostree systems, Clear Linux, Photon OS, NixOS, Guix System, and Wolfi/Chainguard images.
- Solaris, SunOS, illumos, OpenIndiana, OmniOS, and SmartOS.
- AIX, HP-UX, IRIX, Tru64/Digital UNIX.
- Haiku, QNX Neutrino, MINIX.
- Cygwin, MSYS2, and MinGW.
- IBM z/OS, IBM i PASE, and OpenVMS where a compatible Python runtime exists.

Important platform limits:

- Windows does not support the same stdin polling path used for Unix streaming interjection.
- Old terminals without ANSI/VT support may use simpler prompts and fewer visual effects.
- Appliance and embedded systems may have read-only filesystems, missing compilers, missing SSL certificates, restricted package managers, or non-GNU shell tools.
- Prompt the AI to prefer POSIX `sh` commands on unknown Unix systems and avoid GNU-only flags unless verified.

## Supported Architectures

Prism32 uses Python's runtime architecture plus an internal label map for old and unusual machines. The code recognizes these architecture families:

- x86 and x86_64: `i386`, `i486`, `i586`, `i686`, `x86_64`, `amd64`, `AMD64`, Solaris `i86pc`.
- ARM: `arm`, ARMv5TE, ARMv6, ARMv7, ARMv8, ARM hard-float, ARM soft-float, `aarch64`, `arm64`.
- RISC-V: `riscv`, `riscv32`, `riscv64`.
- LoongArch: `loongarch64`, `loong64`.
- PowerPC and POWER: `ppc`, `ppc64`, `ppc64le`, `powerpc`, `powerpc64`, `powerpcspe`, `power`, `rs6000`, `pmac`.
- MIPS: `mips`, `mipsel`, `mips64`, `mips64el`, MIPS32r2/r6, MIPS64r6, SGI `IP*` labels.
- SPARC: `sparc`, `sparc64`, `sparcv9`, `sun4*`.
- IBM mainframe: `s390`, `s390x`, `zarch`, IBM Z.
- Legacy and workstation families: Alpha, PA-RISC, Itanium, Elbrus, VAX.

Use `/arch` to inspect the detected label. Use `PRISM32_ARCH=<label>` or `/arch set <label>` if a rare machine needs a custom display name.

## Performance On Low-End Hardware

Prism32's local overhead is intentionally small:

- The main program is a single `prism32.py` file of about 304 KB in this working copy.
- The core uses only Python standard-library modules.
- There is no browser, Electron shell, Node.js dependency tree, local vector database, or background service required.
- Default live streaming is off in the Python runtime (`Config.STREAM = False`), which avoids token-by-token redraw work on slow terminals.
- Runtime memory files are small JSON/Markdown files and are consolidated automatically, for example top 30 command stats and top 15 error patterns in `memory.json`.

The slow parts are outside Prism32: the model provider latency, local model inference speed, shell commands, package installs, compilers, network scans, or disk IO. On old hardware, Prism32 still stays usable because it is just a task coordinator.

For very very slow CPUs (sub pentium 1) or fragile terminals:

```sh
prism32 --slow-cpu
```

`--slow-cpu` forces non-streaming mode and save-on-interaction behavior. You can also keep startup context small with:

```text
/memctx 512
```

Use `/stream off` if you enabled streaming in the current session.

## How The Agent Loop Works

The main architecture is simple and inspectable:

1. Prism32 starts, loads config from `~/.prism32/config.json`, loads plugins, refreshes memory/profile context, and scans for external harnesses.
2. It builds the AI system context from the core prompt plus memory, startup notes, soul rules, skills, plugin context, harness scan, and evolve docs when enabled.
3. User input is read from the terminal footer.
4. If the input starts with `/`, Prism32 treats it as a slash command.
5. If the input is normal text, Prism32 sends it to the configured model API.
6. If the AI returns `ask` blocks, Prism32 pauses for operator input.
7. If the AI returns `execute` blocks, Prism32 runs those shell commands and captures stdout, stderr, and exit code.
8. The command output is fed back to the AI as context.
9. The loop repeats until the AI produces a normal answer with no more execute blocks, the task is cancelled, or the step limit is reached.

The important pattern is that Prism32 is not just a chat window. It is a feedback harness: plan, execute, observe, continue.

Example active task:

```text
prism32> inspect this git repo, run the tests, and summarize what failed
```

The model can answer with:

````markdown
```execute
git status --short
python -m pytest
```
````

Prism32 runs those commands, captures the results, and asks the model to continue from the evidence.

## Escape, Interjection, And Control

During streaming responses, you can type at any time. The footer changes to `INTERJECT>`. Press Enter to interrupt the AI and send your interjection as the next message.

Useful controls:

- Escape: stop current agent work. This covers streaming, non-streaming API waits, foreground commands, and goal mode.
- Up/Down while interjecting: cycle previous interjections.
- Left/Right, Home, End: edit the interjection buffer.
- Ctrl-C: terminate or interrupt the current terminal operation.

Arrow keys are handled as escape sequences, so normal arrow-key editing does not trigger bare-Escape cancellation.

## Installers

`install.sh` performs a Unix/macOS/BSD-style install:

- Validates `prism32.py` syntax.
- Creates a wrapper command named `prism32` in `${PREFIX:-/usr/local}/bin` when writable.
- Falls back to `~/.local/bin/prism32` during `-y` user-local installs without root.
- Creates `~/.prism32/`, `sessions`, `plugins`, `skills`, and `evolve` directories.
- Prompts for provider, endpoint, model, and API key when running interactively.
- Tests model API reachability when possible.
- Runs `prism32.py --setup-runtime` to create startup memory, harness scan, and evolve baseline files.

`install.ps1` performs a Windows user-local install:

- Copies `prism32.py` to `%LOCALAPPDATA%\Programs\Prism32`.
- Creates `prism32.cmd`.
- Creates runtime directories under `%USERPROFILE%\.prism32`.
- Runs `--setup-runtime` when possible.
- Adds the install directory to the user PATH.

## First Run Setup

Recommended first commands:

```text
/provider list
/provider openrouter
/provider key sk-or-v1-...
/model
/config
/memory path
/help
```

Provider examples:

```text
/provider local
/provider ollama
/provider openai
/provider groq
/provider together
/provider openrouter
/provider custom
```

Set a custom endpoint:

```text
/provider api http://127.0.0.1:8080
/model deepseek-v4-flash
/savecfg
```

Browse/select models for the current provider:

```text
/model
```

## Built-In Providers

The built-in provider registry contains:

- `local`: `http://127.0.0.1:8080`.
- `ollama`: `http://localhost:11434/v1`.
- `openai`: `https://api.openai.com/v1`.
- `anthropic`: `https://api.anthropic.com/v1`.
- `groq`: `https://api.groq.com/openai/v1`.
- `together`: `https://api.together.xyz/v1`.
- `openrouter`: `https://openrouter.ai/api/v1`.
- `custom`: operator-specified.

Prism32 sends OpenAI-style `/chat/completions` requests. Providers work best when they expose an OpenAI-compatible API surface. For providers with native non-OpenAI APIs, use a compatible proxy or gateway.

## Common Commands

All commands require the `/` prefix. Bare text is sent to the AI.

Not all commands are available to both the operator and the model. Commands that manage the session, config, providers, models, and system state (`/config`, `/savecfg`, `/provider`, `/model`, `/theme`, `/stream`, `/help`, `/quit`, `/clear`, `/save`, `/load`, `/resume`, `/sessions`, `/delegate`, `/spawn`, `/subagents`, `/skill-create`, `/auto delete|pause|resume|show`, `/shard reset`, `/memory edit`, `/plugins`, `/usage`, and similar session/config commands) are operator-side only. The model cannot issue them from `execute` blocks.

From `execute` blocks, the model can use shell commands (the normal path), plugin-registered commands, `/quantum`, `/auto` (create/list/run automations), `/skill-list`, `/skill-load`, `/shard` (show/deploy/set/secrets/complete), `/harness scan|context|path`, `/evolve on|tools|diff|docs|context`, `/extend`, `/update`, and `/memory path`.

Core:

```text
/help                 Show command reference
/quit                 Exit
/clear                Clear current conversation history
/config               Show current configuration
/savecfg              Save configuration
/loadcfg              Reload configuration
```

AI and task execution:

```text
/goal <task>          Run autonomous multi-step goal mode
/stream on|off        Toggle streamed responses
/temperature <0-2>    Set model temperature
/thinking off|low|medium|high
/timeout <seconds>    Set shell command timeout
/maxsteps <n>         Set goal-mode step limit
/extend <goal>        AI-generate/load a temporary plugin
/extend permanent <g> AI-generate/load a persistent plugin
/extend prompt        Print the pasteable plugin prompt
```

Manual tools:

```text
/bash <cmd>           Run a shell command
/edit <file> <text>   Append text to a file
/cat <file>           Show file contents
/ls [path]            List files
/find <pattern>       Find files by name
/grep <pat> <file>    Search file content
/git                  Show git status and diff summary
/image <path> [text]  Send an image file or URL to a vision-capable model
```

System tools:

```text
/sysinfo              Show OS, CPU, RAM, disk, IP, package manager
/arch                 Show architecture label
/arch set <label>     Persist a custom architecture label
/procs                Show top processes
/net                  Show network interfaces and routes
/ports                Show listening ports
```

Sessions:

```text
/save [title]         Save current session
/resume               Browse saved sessions with previews
/sessions             List sessions
/load <id>            Load a session
/session <id>         Show session details
/delete <id>          Delete a session
/export [file]        Export current session
/history              Show recent conversation history
```

Memory and context:

```text
/memory               Show memory stats and help
/memory show          Show startup memory Markdown
/memory edit          Edit startup memory in $EDITOR or notepad
/memory append <txt>  Add a startup memory note
/memctx <chars>       Set memory context character limit; 0 disables
/soul show            Show persistent custom rules
/soul append <text>   Add persistent custom rules
/remember <text>      Store long-term memory
/recall <query>       Search long-term memory
/forget <id>          Delete a long-term memory
/memories             List recent long-term memories
```

Subagents and shared context:

```text
/delegate <task>      Run a synchronous subagent
/spawn <task>         Start an asynchronous subagent
/subagents            List running/completed subagents
/collect <id>         Collect async subagent result
/subagent-model       Pick or show default subagent model
/sam <model>          Alias for subagent-model
/quantum              Show shared session context
/quantum key:value    Set a shared context value
/quantum key:         Read a shared context value
```

Automation, skills, promptshards, and evolution:

```text
/auto <text>          Create a scheduled or one-shot automation
/auto list            List automations
/auto run <id>        Run an automation immediately
/skill-create         Create a reusable skill file
/skill-list           List skills
/skill-load <name>    Inject a skill into context
/skill-delete <name>  Delete a skill
/shard show           Show promptshard.md
/shard deploy         Spawn a subagent from promptshard.md
/shard set k:v        Update a promptshard field
/shard secrets        Manage promptshard secrets vault
/harness scan         Detect external AI harness CLIs
/evolve on            Enable evolve context
/evolve docs          Show generated evolve docs
/evolve diff          Diff current prism32.py against the baseline
/update [dir]         Git pull and reinstall from a local Prism32 repo
```

## Goal Mode Examples

Goal mode is for tasks where you want Prism32 to keep working step by step in a loop

```text
/goal find what llama.cpp command runs qwen 3.6 at the fastest tokens per second on this system
```

```text
/goal inspect this git repository, run the tests, comb through the code for bugs
```

```text
/goal on this NetBSD machine
```

Goal mode stops when the AI says `GOAL COMPLETE`, reaches `/maxsteps`, fails, or you press Escape.

## Advanced Task Examples

Prism32 is useful for tasks that need conversation plus terminal feedback:

- Legacy system onboarding: detect OS, architecture, package manager, shell quirks, RAM, disk, network tools, and record the facts in `startup_memory.md`.
- Codebase repair: inspect a repo, run tests, apply a minimal patch, rerun tests, and summarize the diff.
- Multi-provider research: use a fast cheap model for subagents while the main session uses a stronger model.
- Local/remote model routing: use Ollama or llama.cpp locally for private work, then switch to OpenRouter/Groq/OpenAI when needed.
- Plugin creation: ask Prism32 to write a plugin into `~/.prism32/plugins/`, restart, and use the new slash command.
- External harness coordination: scan installed AI CLIs with `/harness scan`, then let Prism32 choose when to delegate to one.
- Scheduled tasks: create natural-language automations that run while Prism32 is open, such as periodic reports or checks.
- Promptshard handoff: write a structured assignment into `promptshard.md`, then `/shard deploy` to spawn a specialized subagent.
- Self-maintenance: enable `/evolve on`, inspect tool scans, compare against the baseline with `/evolve diff`, and apply reviewed code changes.

## Subagents

Subagents are independent task runners with their own mini history. They use the same model as the main agent by default, or `Config.SUBAGENT_MODEL` if set.

Run synchronously:

```text
/delegate summarize the last 20 commits and identify risky changes
```

Run asynchronously:

```text
/spawn scan this repository for TODO comments and group them by subsystem
/subagents
/collect <id>
```

Use another configured provider:

```text
/delegate write a release checklist --provider openrouter
/spawn inspect package manager options --provider ollama
```

Subagent results are stored into the in-memory quantum context and important results may also be stored in long-term memory.

## Quantum Context

Quantum context is a thread-safe in-memory key-value store for the current Prism32 process. It is used by the main session and subagents to share short facts, task results, and handoff data.

```text
/quantum target:https://example.com
/quantum target:
/quantum
```

Current limits:

- Quantum context is session memory, not durable storage.
- For durable information, use `/remember`, `/memory append`, `/soul append`, or a project file.

## Promptshard

`~/.prism32/promptshard.md` is a structured assignment file. It can describe an objective, agent role, desired capabilities, tools, prompt text, requested secrets, and status.

Example:

```markdown
# PROMPTSHARD: repo-audit
## OBJECTIVE: Audit this repo and produce a risk report
## AGENT: specialist
## MODEL_CAPABILITIES: chat,code,fast
## TOOLS: bash,git,python3
## PROMPT: |-
  Inspect the repository. Do not modify files. Return findings with file paths.
## SECRETS_REQUESTED:
## STATUS: active
```

Commands:

```text
/shard show
/shard set objective:Audit the installer
/shard secrets
/shard deploy
/shard complete
/shard reset
```

`/shard deploy` spawns a subagent from the current shard. It is a lightweight handoff system, not a distributed cluster manager.

## Memory System

Prism32 memory is file-based and inspectable:

- `~/.prism32/memory.json`: command usage stats, error patterns, system profile, session count, and preferences. It is auto-consolidated to avoid unbounded growth.
- `~/.prism32/startup_memory.md`: human-editable machine notes injected into context. This is the best place for hardware quirks, shell differences, package manager notes, and recurring fixes.
- `~/.prism32/soul.md`: persistent custom instructions and operator rules.
- `~/.prism32/longterm/`: long-term memory files created with `/remember`, searched with `/recall`, and capped by the runtime.
- `~/.prism32/sessions/`: saved conversations.
- `~/.prism32/harnesses.json`: detected external AI harness tools.

Examples:

```text
/memory append This NetBSD host uses /usr/pkg/bin/python3.12 and pkgin.
/remember The build command for this repo is python -m pytest --tag build
/recall build command
/soul append Never change network settings unless explicitly asked.
```

This memory system gives Prism32 continuity across sessions without hiding data in a database. You can open and edit the files directly.

## Evolve Mode And Self-Editability

Evolve mode creates local documentation and baselines that help Prism32 reason about its own installation:

- `~/.prism32/evolve/evolve.md`: generated notes about self-repair, plugin creation, runtime files, and safe modification practices.
- `~/.prism32/evolve/tools.json`: scan of local shells, Python, git, build tools, network tools, package managers, service managers, containers, and platform-specific utilities.
- `~/.prism32/evolve/baseline/prism32.py`: baseline copy for diff comparison.
- `~/.prism32/evolve/baseline/config.default.json`: default config snapshot.
- `~/.prism32/evolve/tmp_plugins/`: temporary plugin workspace.

Commands:

```text
/evolve on
/evolve status
/evolve docs
/evolve context
/evolve tools
/evolve diff
/evolve baseline
/evolve plugin temp my_tool
/evolve plugin permanent my_tool
```

What self-editable means in Prism32:

- The whole application is one readable Python file.
- The AI can inspect files, run tests, and execute shell commands when you ask it to.
- `/extend <goal>` lets Prism32 generate, validate, write, load, and immediately use a task-specific plugin.
- `/evolve diff` shows how the current `prism32.py` differs from the saved baseline.
- `/evolve plugin ...` creates plugin templates instead of requiring core edits for every new feature.
- `/update [dir]` performs `git pull` plus reinstall from a local git checkout that contains `install.sh`.

What it does not mean:

- Prism32 does not silently rewrite itself.
- Prism32 does not guarantee that AI-generated patches are correct.
- `/edit` only appends text to a file; broader edits are done through shell commands or external editor tools.
- Review diffs before trusting self-modification work.

Safe self-edit workflow:

```text
create a plugin that shows me a visually stunning view of what the subagents running my website are doing and how many visisters are using the site
create a C compiler plugin so we can check cyntax of C code
/goal create a temporary plugin to connect to my outdoor webcam and send me a telegram message when my important package arrives today from USPS
/evolve on
/extend temp add a command that parses this project's test output and highlights failures 
/extend prompt
inspect prism32.py and propose a minimal fix for the bug I describe; do not edit core code yet
/evolve diff
now apply the smallest safe patch and run python -m pytest
/git
```

## Plugin System

Plugins are Python files in `~/.prism32/plugins/`. Files ending in `.py` are loaded at startup unless their filename starts with `_`.

Fast plugin creation paths:

```text
/extend <goal>              Generate, syntax-check, write, and load a temporary plugin
/extend permanent <goal>    Generate and load a persistent startup plugin
/extend load <path>         Load an existing plugin file immediately
/extend prompt              Print the pasteable plugin-generation prompt
```

Prism32 prefers plugin self-extension over editing `prism32.py` for new task-specific capabilities. A plugin can add a command, inject context, call simple HTTP APIs, add provider presets, add themes, schedule callbacks, parse local files, or wrap repeatable workflows draw new interfaces over or custom TUI's for specific modes and commands. Core self-rewrites should be reserved for critical bug fixes and changes that cannot be solved as plugins.

Each plugin may define `register(api)`. The `api` object provides:

- `api.registry`: register slash commands.
- `api.register_provider(name, **config)`: add a provider.
- `api.register_theme(name, **colors)`: add a theme.
- `api.config`: access runtime config.
- `api.memory`: access loaded memory data.
- `api.history`: access current session history.
- `api.inject_context(text)`: inject text into AI system context.
- `api.schedule(interval_sec, callback)`: run timer callbacks.
- `api.http_get(url, headers=None, timeout=10)`: stdlib HTTP GET.
- `api.http_post(url, data=None, headers=None, timeout=10)`: stdlib HTTP POST.
- `api.log(text)`: print a plugin diagnostic.
- `api.plugins`: loaded plugin modules.

Plugin hooks currently useful in normal operation:

- `on_boot(api)`: called after startup initialization.
- `on_message(api, text)`: called for operator input.
- `on_command(api, name, args, result)`: called for slash command names; `result` is currently passed as `None`.
- `on_tick(api)`: called by a background tick thread roughly every 5 seconds when registered.

Best practice: every plugin should define its own usage context. Add a `USAGE_CONTEXT` string that lists the commands, options, and when the agent should use them, then inject it with `on_boot(api): api.inject_context(USAGE_CONTEXT)`. That makes the agent aware of plugin capabilities instead of only seeing command names.

Plugin commands can be called as normal slash commands. They can also be used from AI `execute` blocks in the default active task loop and subagent loop. Goal mode focuses on shell commands and does not route every plugin command path the same way.

Minimal plugin:

```python
# ~/.prism32/plugins/hello.py

USAGE_CONTEXT = """Hello plugin available:
- /hello [name]: print a greeting for testing plugin loading.
"""

def cmd_hello(args_str, history, cmd_log):
    name = args_str.strip() or "operator"
    print(f"Hello, {name}.")

def register(api):
    api.registry.register(
        "hello",
        cmd_hello,
        description="Say hello from a plugin",
    )

def on_boot(api):
    api.inject_context(USAGE_CONTEXT)
```

Restart Prism32, then run:

```text
/hello Ada
```

Plugin example with context injection:

```python
# ~/.prism32/plugins/context_note.py

def on_message(api, text):
    if "release checklist" in text.lower():
        api.inject_context("Operator often wants tests, changelog, tag, and deploy notes for releases.")

def register(api):
    api.log("context_note active")
```

The repository also includes `plugins/web_scraper.py` as a sample plugin. To use it, copy it into `~/.prism32/plugins/` and restart Prism32.

## Plugin Cheat Sheet For Any AI Chatbot

Paste this into another AI chatbot when you want it to create a Prism32 extension on the fly:

```text
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

USAGE_CONTEXT = """Plugin available:
- /my-command <args>: what it does, its options, and when agents should use it.
"""

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

Now create a Prism32 plugin for this goal: <describe goal here>
```

## Skills

Skills are reusable JSON workflow/context files under `~/.prism32/skills/`.

```text
/skill-create
/skill-list
/skill-load release-checklist
/skill-delete release-checklist
```

Use skills when you want repeatable operating procedures without writing Python plugins.

## Automation

Automations are scheduled or one-shot tasks stored under `~/.prism32/automations/`. They are checked by a background thread while Prism32 is running.

```text
/auto check disk usage every hour
/auto write a project status summary in 3 days
/auto list
/auto show <id>
/auto pause <id>
/auto resume <id>
/auto run <id>
/auto delete <id>
```

Automations are not installed as OS services. They run only while Prism32 is open.

## Harness Absorption

Prism32 scans for external AI command-line harnesses and records them in `~/.prism32/harnesses.json`.

```text
/harness scan
/harness
/harness context
/harness delegate compare this repo against the README
/harness path
```

Detected tools may include OpenCode, Codex CLI, Claude Code, KimiCode, Aider, Gemini CLI, Goose, Cursor Agent, and related commands. Prism32 does not bundle or authenticate those tools. It only detects what exists locally and adds that information to the AI context.

## Why Prism32 Can Do More Than A Plain Chat CLI

Many terminal chat tools stop at sending prompts and printing responses. Prism32 combines multiple harness layers:

- A command-execution feedback loop with structured `ask` and `execute` blocks.
- Can turn any computer into a personal robot assistant with natural language
- Can run on IOT devices and robots with low end compute on bare metal and can expand their capabilities by writing custom plugins for it's niche hardware and OS'
- Persistent startup memory, long-term memory, and custom soul rules.
- Runtime plugin loading without pip packages.
- Subagents that can run synchronously or asynchronously.
- A shared in-memory quantum context for agent handoffs.
- Promptshard files for structured assignments.
- Evolve files for self-documentation, tool scans, baselines, plugin templates, and diffs.
- External harness detection so Prism32 can reason about other installed AI CLIs.
- Cross-platform command guidance injected into startup memory.
- Escape cancellation for long waits and runaway foreground commands.

The result is a small terminal program that can operate like a conversation, a shell assistant, a task runner, a plugin host, and a multi-agent coordinator.

## Configuration

Main config file:

```text
~/.prism32/config.json
```

Important settings:

- `api_base`: model API base URL.
- `model`: active model ID.
- `api_key`: provider API key when needed.
- `provider`: active provider name.
- `theme`: active theme.
- `temperature`: model temperature.
- `max_history`: maximum message history count.
- `max_response_tokens`: response token limit sent to the API.
- `cmd_timeout`: shell command timeout in seconds.
- `goal_max_steps`: maximum goal-mode steps.
- `max_memory_ctx`: character limit for injected memory context.
- `subagent_model`: optional model override for subagents.
- `agent_name`: display name shown before assistant responses.

Use `/config`, `/savecfg`, and `/loadcfg` rather than editing JSON while Prism32 is running.

## Themes

Prism32 registers 31 themes, including phosphor, amber, cyan, vapor, nord, solarized, neon, retro, ice, ocean, sunset, forest, plasma, clear, glass, ghost, smoke, paper, ink, daylight, slate, synthcity, outrun, laserdisc, vapordark, chromecrt, sgi, dec, monoamber, iris, and hpterm.

Cycle themes:

```text
/theme
```

Set a core theme at startup:

```sh
prism32 --theme amber
```

For old terminals, prefer the 16-color compatible themes such as `sgi`, `dec`, `monoamber`, `iris`, and `hpterm` through runtime theme cycling or configuration.

## Floppy And Removable Media

The project includes tooling to build a FAT12 floppy image:

```sh
python3 make_floppy.py
sh floppy-install.sh /tmp/opencode/prism32_floppy.img
```

This is useful for removable media, virtual floppy images, and legacy bootstrapping. The core app is small enough to fit comfortably on a 1.44 MB image, but the target machine still needs Python 3.7+.

## Safety Notes

Prism32 can execute shell commands. Treat it like a powerful operator sitting at your terminal.

- Read commands before allowing high-risk work.
- Create specific or custom rules for your codebase with prisms self editability easily
- Use read-only audit prompts when inspecting servers.
- Do not paste secrets into prompts unless necessary.
- Keep API keys in config or environment variables with normal local filesystem protections.
- Review diffs before trusting AI-generated code changes.
- Use Escape to stop active work if the agent is going in the wrong direction.
- Use `/timeout <seconds>` to limit foreground command duration.
- Limit /goal steps on expensive models so expensivie models don't drain your bank account looping on a simple task

## Troubleshooting

API connection failed:

```text
/provider list
/provider api https://your-provider/v1
/provider key YOUR_KEY
/model
```

Terminal rendering is broken:

```sh
NO_COLOR=1 python3 prism32.py --no-boot
```

Streaming is messy on a slow terminal:

```text
/stream off
```

Need to refresh runtime files:

```sh
python3 prism32.py --setup-runtime
```

Need to inspect logs:

```text
/debug
/log
```

Need to stop a runaway command or model wait:

```text
Press Escape.
```

## Development

Run syntax check:

```sh
python3 -m py_compile prism32.py
```

Run tests:

```sh
python3 -m pytest
```

Project metadata declares Python `>=3.7`. CI currently checks syntax on Ubuntu and macOS for Python 3.9 through 3.13 and runs unit tests on Ubuntu for Python 3.9 through 3.13.

## License

See the repository license. Project metadata currently declares MIT.
