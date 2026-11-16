# Prism32 v7.3.0
The Easiest agent to use, You never have to learn how to use prism32
Prism32 is a self-extending, self-repairing, self-evolving hivemind program with a AI super-agent from MegaDyne Systems. One Python file, stdlib-only. A real Jarvis. It auto-detects its platform, absorbs external AI harnesses, generates plugins on the fly for missing capabilities, delegates to subagents running different models, synchronizes state through quantum context, persists everything it learns, and becomes more powerful every time you use it. There is no fixed feature ceiling — every task expands what the agent can do. it can turn any PC or low end hardware SBC or laptop etc into a robotic assistant that can control external peripherals and can also run on robots and IOT devices with shell and python on bare metal. Prism32 is the first polymorphic AI assistant and coding harness
Prism32 uses MegadyneSystem's Tesseract hivemind technology to maximize intelligence and efficiency removing bloated A2A communication and addressing the issues with multi agent systems
 
It is designed for modern PC's and older machines: no Node.js, no browser runtime, no pip dependencies, and no local database server. Runtime state lives in small files under `~/.prism32/`.

This README is the full operator guide. The GitHub front page shows the same document.

## Install And Start

Recommended — the one-click install works everywhere (macOS, Linux, BSD/unix, Android/Termux, ChromeOS, NAS, any POSIX box with `curl` or `wget`). It auto-detects the platform, installs Python 3 + git if missing, and sets everything up:

```sh
curl -fsSL https://raw.githubusercontent.com/MegaDyneSystems/prism32/main/bootstrap.sh | sh
```

or, if `curl` is not available:

```sh
wget -qO- https://raw.githubusercontent.com/MegaDyneSystems/prism32/main/bootstrap.sh | sh
```

Then start with `prism32`. For updates, run the same command again — it updates an existing clone in place.

**Termux (Android):** install [Termux from F-Droid](https://f-droid.org/en/packages/com.termux/), then `pkg install curl && curl -fsSL https://raw.githubusercontent.com/MegaDyneSystems/prism32/main/termux-install.sh | sh`

Package managers also work if you prefer them:

| Manager | Platform | Install Command |
|---------|----------|-----------------|
| **Homebrew** | macOS, Linux | `brew tap MegaDyneSystems/prism32 && brew install prism32` |
| **Scoop** | Windows | `scoop bucket add prism32 https://github.com/MegaDyneSystems/scoop-prism32 && scoop install prism32` |
| **pip** | Any (Python 3.7+) | `pip install prism32` |
| **npm / npx / bunx** | Any (Node.js 14+) | `npx @megadynesystems/prism32` |

All package managers install the same `prism32` command. After installation, run `prism32 --version` to verify, then `prism32 --setup-runtime` to initialize your config.

**pip / PyPI:** https://pypi.org/project/prism32/  
**Homebrew Tap:** https://github.com/MegaDyneSystems/homebrew-prism32  
**Scoop Bucket:** https://github.com/MegaDyneSystems/scoop-prism32  
**npm Registry:** https://www.npmjs.com/package/@megadynesystems/prism32

### From Source (Git clone)

Install and start on Unix/Linux/macOS/BSD/Android Termux:

```sh
git clone https://github.com/MegaDyneSystems/prism32.git && cd prism32 && bash install.sh && prism32
```

No-root install:

```sh
git clone https://github.com/MegaDyneSystems/prism32.git && cd prism32 && bash install.sh -y && ~/.local/bin/prism32
```

> On a NAS (Synology DSM) the user home may not exist — use the [NAS install](#nas-synology--qnap--wd-my-cloud) instead; the installer then auto-reroutes to the persistent volume home.

Run directly without install:

```sh
git clone https://github.com/MegaDyneSystems/prism32.git
cd prism32
python3 prism32.py --setup-runtime
python3 prism32.py
```

Windows (PowerShell or Scoop):

```powershell
# Option A: Scoop (recommended)
scoop bucket add prism32 https://github.com/MegaDyneSystems/scoop-prism32
scoop install prism32

# Option B: PowerShell installer
git clone https://github.com/MegaDyneSystems/prism32.git
cd prism32
powershell -ExecutionPolicy Bypass -File .\install.ps1
prism32
```

Direct local model example:

```sh
python3 prism32.py --api http://127.0.0.1:8080 --model local-model
```

NVIDIA Jetson, DGX, or CUDA-backed local models use the same local-server form (`--api http://127.0.0.1:8080 --model local-cuda-model`). OpenRouter example:

```sh
python3 prism32.py --api https://openrouter.ai/api/v1 --api-key sk-or-v1-... --model deepseek/deepseek-v4-flash
```

### OpenWrt Routers

Pure POSIX sh installer (busybox ash compatible):

```sh
wget -O /tmp/install.sh https://raw.githubusercontent.com/MegaDyneSystems/prism32/main/openwrt-install.sh
sh /tmp/install.sh                # interactive
sh /tmp/install.sh -y            # auto mode
sh /tmp/install.sh /mnt/usb      # install to USB drive (low-flash routers)
```

The OpenWrt installer:

- Auto-detects `opkg` (OpenWrt <24) or `apk` (OpenWrt >=24)
- Bootstraps HTTPS support (`libustream-mbedtls` + `ca-bundle`)
- Installs `python3-light` + `python3-openssl` (minimal footprint)
- Low-flash detection: suggests USB install below 8 MB free
- Low-RAM detection: skips `py_compile` syntax check on devices <64 MB to avoid OOM during install
- Downloads `prism32.py` from GitHub if not present locally
- Router-tuned config: lower `max_history` (500), `max_response_tokens` (4096), `stream: false`
- Creates `/etc/profile.d/prism32.sh` for USB PATH setup
- Works on 4 MB+ flash (with USB), 24 MB+ RAM

### ChromeOS (Crostini)

ChromeOS supports Linux apps via the Crostini container (built into ChromeOS 69+) — no Developer Mode or Crouton needed. In the Terminal app (Crostini):

```sh
curl -fsSL https://raw.githubusercontent.com/MegaDyneSystems/prism32/main/bootstrap.sh | sh
```

This auto-detects ChromeOS/Crostini as Linux, installs Python 3 + git if needed, clones the repo, and runs the installer. Or install manually: `sudo apt-get install -y python3 git`, then clone and `bash install.sh` (or run `python3 prism32.py` directly from the clone).

ChromeOS notes:

- **Crostini** is recommended over Crouton/Developer Mode — it's sandboxed, stable, and supported on all Chromebooks from 2019 onward.
- Prism32 runs at full speed in the Crostini container (a real Linux environment with `apt`, `python3`, `git`, etc.).
- Shared filesystem: files in the Crostini container's home directory are accessible from the ChromeOS Files app under "Linux files"; clipboard sharing works.
- From the restricted Crosh shell (Ctrl+Alt+T) — no Python, no package manager — bootstrap into the container:
  `vmc start termina` then `vmc container termina -- penguin -- sh -c "curl -fsSL https://raw.githubusercontent.com/MegaDyneSystems/prism32/main/bootstrap.sh | sh"`. If Crostini isn't enabled yet, the bootstrap script prints how to enable it (Settings → Linux development environment → Turn on). With Developer Mode, type `shell` in Crosh for a root bash shell, then run the bootstrap command.

### Android / Termux

One-command install for Android phones, tablets, Chromecast with Google TV, Android TV, Wear OS watches, Fire TV (sideloaded Termux), and any device that can run Termux:

```sh
# 1. Install Termux from F-Droid (Google Play version is deprecated)
# 2. In Termux, run:
pkg install curl && curl -fsSL https://raw.githubusercontent.com/MegaDyneSystems/prism32/main/termux-install.sh | sh
```

This installs Python 3 + git via `pkg`, clones Prism32, creates a `prism32` command in `$PREFIX/bin` (no root needed), and preserves existing config on updates. Then start with `prism32`. To use a cloud provider, pass `--api`/`--api-key` for the session or persist the pick with `/model` and `/provider key <name> <key>` inside the app (no `--provider` CLI flag exists).

### Universal Bootstrap (Any Platform)

A single command that auto-detects the platform and installs everything:

```sh
curl -fsSL https://raw.githubusercontent.com/MegaDyneSystems/prism32/main/bootstrap.sh | sh
# or:
wget -qO- https://raw.githubusercontent.com/MegaDyneSystems/prism32/main/bootstrap.sh | sh
```

| Platform | Package Manager | Install Path |
|----------|-----------------|-------------|
| Termux/Android | `pkg` | `~/prism32` + `install.sh -y` |
| OpenWrt | `opkg` or `apk` | `~/prism32` + `openwrt-install.sh -y` |
| macOS | `brew` (auto-installs if needed) | `~/prism32` + `install.sh -y` + SSL fix |
| Linux (Debian/Ubuntu) | `apt-get` | `~/prism32` + `install.sh -y` |
| Linux (Fedora/RHEL) | `dnf` | `~/prism32` + `install.sh -y` |
| Linux (Arch/Manjaro) | `pacman` | `~/prism32` + `install.sh -y` |
| Linux (Alpine) | `apk` | `~/prism32` + `install.sh -y` |
| Linux (Gentoo) | `emerge` | `~/prism32` + `install.sh -y` |
| Linux (Void) | `xbps-install` | `~/prism32` + `install.sh -y` |
| BSD (FreeBSD/NetBSD/OpenBSD) | `pkg`/`pkgin`/`pkg_add` | `~/prism32` + `install.sh -y` |
| Synology/QNAP/WD NAS | N/A (no package manager) | Direct download via `curl`/`wget` (no git needed) |
| Unknown | N/A | Direct download of `prism32.py` via `wget`/`curl`/`python3` |

If Python 3 is not installed, the bootstrap script installs it via the system's package manager automatically. If no recognized package manager exists (e.g. Synology DSM, QNAP QTS), it falls back to downloading `prism32.py` + `install.sh` directly via `curl`/`wget`/`python3 urllib` — no git required. If `$HOME` doesn't exist (common on Synology NAS), it probes persistent locations (`/volume1/prism32` on Synology) and only then falls back to `/tmp` as HOME.

### NAS (Synology / QNAP / WD My Cloud)

Most NAS devices ship with Python 3 and `curl`/`wget` but no `git` and no package manager. The universal bootstrap handles this automatically — via SSH (Synology DSM has curl preinstalled; use `wget -qO- ... | sh` if curl is unavailable). If GitHub CDN is cached, pipe the script directly from your local machine:

```sh
cat bootstrap.sh | ssh user@nas "cat > /tmp/bootstrap.sh && HOME=/tmp sh /tmp/bootstrap.sh"
```

Tested on Synology DS414 (Marvell Armada XP, ARMv7l, 2GB RAM, Python 3.8.12, DSM 7.1.1 — the v7.2 full battery passed there: 165 pytest + 24 smoketests, GNU readline 8.0 with working bracketed paste). The installer:

- Detects missing git and falls back to direct download of `prism32.py` + `install.sh`
- Detects a broken `$HOME` (DSM's `/var/services/homes/<user>` dangles when the user home service is off) and reroutes the runtime dir to the **persistent** `/volume1/homes/<user>/.prism32` — never volatile `/tmp`, which DSM mounts noexec and wipes on reboot
- Installs the wrapper to `/volume1/homes/<user>/.local/bin/prism32` (persistent + exec-capable)
- Persists PATH by appending a guarded export to `.profile`/`.bashrc` (and the volume home's `.profile`) — a fresh interactive SSH login finds `prism32`
- Writes neutral local-provider defaults in `-y` auto mode — configure the real endpoint with `/provider` on first run
- Verifies the wrapper it actually wrote and warns if a stale prism32 elsewhere in PATH shadows it
- No root required (installs to user-local paths)

DSM notes:

- Best fix for a missing home: **Control Panel → User & Group → Advanced → Enable user home service**, or run with `HOME=/volume1/homes/<user>`. `/volume1/homes/<user>` exists and is user-writable even when the homes symlink dangles.
- `/tmp` is tmpfs, **noexec**, and wiped on reboot — nothing lives there.
- `scp` to DSM needs `-O` (SFTP subsystem is disabled by default): `scp -O file user@nas:/path`.
- Non-interactive SSH (`ssh nas 'prism32 --version'`) sources no dotfiles on DSM — run from an interactive shell, or use the full wrapper path.
- No pip on DSM, but the app is stdlib-only (no dependencies). For development, `python3 -m venv` works (ensurepip is bundled).
- To connect to a cloud provider (NAS likely has no local LLM), pass `--api`/`--api-key` for the session, then persist with `/model` and `/provider key <name> <key>` inside the app.

After install, run with `prism32` (after PATH refresh) or `python3 /volume1/homes/<user>/.prism32/prism32.py` explicitly.

QNAP QTS: same procedure as Synology. QNAP NAS devices also ship with Python 3 and `curl`; the bootstrap script auto-detects QNAP via `/etc/config/uLinux.conf` or `/etc/qnap_config`.

WD My Cloud: busybox Linux with Python 3 available via optware; the bootstrap script detects WD via `/etc/NAS_CFG` and uses direct download.

### Portable: Floppy / USB / CD

The project includes tooling to build a FAT12 floppy disk image that bundles Prism32 with your configuration, API keys, plugins, and memory:

```sh
python3 make_floppy.py            # build 1.44MB image with your config
sh floppy-install.sh              # write to removable device
```

See [Floppy And Removable Media](#floppy-and-removable-media) below for image contents and usage.

## First Commands

Most-used first commands inside Prism32:

```text
/help                 Show all commands
/provider             Interactive provider manager (switch/edit/test by number)
/provider add         Add a provider (template wizard with live detection)
/provider key <name> <key>
                       Set a provider's API key (persisted)
/model                Browse every provider's models; assign main/subagent
/cost                 Show session token usage and cost
/config               Show active config
/mission <goal>       Autonomous orchestrated mission mode
/bash <cmd>           Run a shell command manually
/memory edit          Edit machine notes injected into context
/remember <text>      Store long-term memory
/delegate <task>       Run a subagent now
/spawn <task>         Start a background subagent
/extend <goal>        Generate/load a temporary plugin for a missing capability
/quit                 Exit
```

Practical starter prompts:

```text
inspect this machine, identify OS/architecture/package manager, and save useful notes to startup memory
inspect this git repo, run the tests, and summarize what failed without changing files
/mission audit this server for disk pressure, failed services, open ports, and risky logs; report only
```

Stop anything that is taking too long: press Escape.

## What Prism32 Does

Prism32 combines several systems in one terminal harness:

- Interactive chat with OpenAI-compatible model APIs.
- Active task mode: the AI can emit shell commands in fenced `execute` blocks; Prism32 runs them, captures output, and asks the AI what to do next.
- Autonomous mission mode with `/mission <goal>`: a planner decomposes the goal into 3-6 steps that run as parallel subagent shards until the mission is structurally complete.
- Synchronous and asynchronous subagents with `/delegate`, `/spawn`, `/subagents`, `/collect`, and `/wait`; background shell jobs with `/bg`. Completion is event-driven — finished subagents and jobs push their results into the conversation automatically, so nothing needs to be polled.
- Plugin loading from `~/.prism32/plugins/*.py` for custom slash commands, providers, themes, context injection, timers, and HTTP helpers.
- Self-extension with `/extend`: Prism32 can ask the configured model to generate a stdlib-only plugin, syntax-check it, write it, load it, and use the new command immediately.
- Memory and evolution files that let the system remember machine quirks, recurring fixes, tools, baselines, user rules, and long-term notes.
- Promptshard files for structured job assignments and subagent deployment.
- Harness absorption: Prism32 can detect external AI CLIs such as OpenCode, Codex CLI, Claude Code, KimiCode, Aider, Gemini CLI, Goose, Pi AI CLI, Hermes Agent, and Cursor Agent, then include their availability in context.
- Terminal interjection while streaming: type while the AI is responding, press Enter, and your message interrupts the model.
- Bare Escape cancellation: press Escape to stop active AI streaming, non-streaming API waits, foreground shell commands, and goal-mode work.
- Low-RAM mode: auto-detects <64MB systems, skips heavy startup paths, and caps output to stay usable on 27MB OpenWrt routers.
- Prompt caching: Anthropic native cache_control, OpenAI automatic cached_tokens billing, and DeepSeek prompt_cache_hit_tokens — toggle with `/prompt_caching on|off`.
- Cheaper inference: non-destructive compression of older verbose tool results (~85% token reduction), condensed system prompt, and per-provider `cheap_model` suggestions in `/model`.
- Provider URL protection: custom `api_base` survives provider switches; set with `/set api_base <url>` or `reset` to revert. Per-provider bases are fixed with `/provider api <name> <url>`.

## The Emergent Agent

Prism32 isn't chatbot. It is a self-extending, self-repairing, multi-agent command system that becomes more capable the longer it runs.

Each capability feeds the others. The agent bootstraps itself: it detects the OS and CPU it is running on, scans for local tools, absorbs external AI harnesses into its context, generates plugins on the fly for missing capabilities, delegates sub-tasks to subagents running different models, synchronizes state through quantum context, and records everything it learns into persistent memory files that survive restarts. None of this requires operator approval. The agent can decide to create a plugin, spawn a subagent, enable evolve mode, or absorb a harness entirely on its own, from inside an execute block, mid-task.

The combination creates real emergent power:

**Self-evolution without guardrails.** The agent can inspect its own source code against a baseline, diff it, generate a plugin to fix a gap, syntax-check the plugin, load it immediately, and use the new command in the same session. It can also git-pull and reinstall itself. The boundaries of what it can do expand at runtime.

**Hot-swappable plugins the agent creates for itself.** `/extend temp add a command that ingests MQTT telemetry from this Zigbee network` — the model generates a stdlib Python plugin, Prism32 validates and loads it, and the agent calls the new command in its next execute block. No restart. No pip. No human needed. Temporary plugins disappear when Prism32 exits; permanent ones load on every boot, can automate long tool call chains with a temporary plugin

**Quantum context as a shared brain.** Every main agent, subagent, and async spawned agent reads and writes to the same thread-safe key-value store. A subagent scanning open ports drops its findings into quantum context, and the main agent picks them up without polling. Subagents running different providers see each other's results. The system prompt is rebuilt mid-task to include the latest quantum state.

**Model mixing for cost and speed.** You talk to a strong model. Subagents run on cheap fast ones. Thousands of tokens of infrastructure scanning happen on a free-tier model while your main session stays on the expensive reasoning model for analysis. `/delegate scan every host on this subnet --provider groq` costs almost nothing. No other terminal agent harness lets you mix providers and models per-task with zero configuration changes.

**Harness absorption.** Prism32 detects OpenCode, Codex CLI, Claude Code, KimiCode, Aider, Gemini CLI, Goose, Pi AI CLI, Hermes Agent, Cursor Agent, and other AI CLIs on the system. It injects their capabilities into its context. It can then delegate a task to a super-subagent seeded with those tools. Prism32 becomes a coordinator over every AI agent CLI installed on the machine.

**The peripheral surface is the entire Linux device tree.** USB serial adapters, GPIO pins, I2C sensors, SPI displays, CAN buses, SDR dongles, cameras, microphones, speakers, relays, motor controllers, 3D printer serial ports, Zigbee coordinators, Z-Wave sticks, Bluetooth adapters, WiFi interfaces, and anything with a /dev node. If Linux can talk to it, the agent can script against it. Combine that with on-the-fly plugin generation and you have a universal hardware controller that learns new protocols mid-session.

**Platform reach means deployment everywhere.** The same Prism32 binary runs on a Raspberry Pi inside a robot, an old laptop in a garage, a Steam Deck, a jailbroken Kindle, a Tesla MCU, a DEC AlphaStation, a Synology NAS, a $15 OpenWrt travel router, an SGI Octane, and an AWS Graviton instance, a bluetooth speaker. It auto-detects the architecture, the package manager, and the shell, then adjusts every command it runs. Install once, deploy anywhere.

**Cost scales down to zero.** Local llama.cpp or Ollama models run entirely offline on the same machine. No API costs. No cloud dependency. Pick a local model from `/model` for private work, a cloud model for hard reasoning, and let subagents run on Groq's free tier for bulk scanning. You control the cost-per-task by choosing which model does which job.

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
- External AI harnesses such as OpenCode, Codex CLI, Claude Code, KimiCode, Aider, Gemini CLI, Goose, Pi AI CLI, Hermes Agent, or Cursor Agent.

## Supported Systems

Prism32 is a pure-stdlib Python program, so the real portability rule is simple: if Python 3.7+ can run and the system has a usable shell, Prism32 should start. Some features depend on terminal support, process control, SSL certificates, and local command availability.

The repository has automated CI syntax checks and unit tests on Ubuntu (Python 3.9, 3.10, 3.11, 3.12, and 3.13, plus a 3.7 compile check). Deployed copies have also been syntax-checked on NetBSD 10.1 and macOS 10.13 in the development environment; NetBSD PTY smoke tests have been used for terminal behavior. The v7.0 compat pass was verified end-to-end on real hardware: Synology DSM 7.1.1 (ARMv7, Python 3.8, nonexistent user home), NetBSD 10.1 i386, and Fire TV / Termux (Android 5.1.1, Python 3.8).

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

TV and streaming: NVIDIA Shield, Fire TV Stick and Cube, Chromecast with Google TV, Kodi boxes running LibreELEC or OSMC.

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
- AIX, HP-UX, IRIX, Tru64/Digital UNIX (requires a compatible Python 3.7+ build; on IRIX/Tru64, use Linux or NetBSD ports for MIPS/Alpha hardware).
- Haiku, QNX Neutrino, MINIX.
- Cygwin, MSYS2, and MinGW.
- DragonFly BSD.
- IBM z/OS (USS), IBM i PASE, and OpenVMS where a compatible Python runtime exists.

Important platform limits:

- Windows 11 22H2+: uses PowerShell `Get-CimInstance` for system info (replaces deprecated `wmic`).
- Windows does not support Escape-cancel of foreground commands or streaming interjection. Use Ctrl-C to interrupt.
- Old terminals without ANSI/VT support may use simpler prompts and fewer visual effects.
- Appliance and embedded systems may have read-only filesystems, missing compilers, missing SSL certificates, restricted package managers, or non-GNU shell tools. Use `install.sh -y` for user-local installs on read-only systems.
- On AIX, HP-UX, QNX, and MINIX: `install.sh` requires bash. Install it first, or run `python3 prism32.py --setup-runtime && python3 prism32.py` directly.
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

- The main program is a single `prism32.py` file of about 600 KB in this working copy.
- The core uses only Python standard-library modules.
- There is no browser, Electron shell, Node.js dependency tree, local vector database, or background service required.
- Live streaming of AI responses is on by default (`Config.STREAM = True`) — tokens (and reasoning, dimmed) render as they arrive and flow into terminal scrollback. Turn it off with `/stream off` (persisted) or `--slow-cpu` on fragile/slow terminals.
- Runtime memory files are small JSON/Markdown files and are consolidated automatically, for example top 30 command stats and top 15 error patterns in `memory.json`.
- Large constants (themes, help text, harness candidates, tool scan groups, subagent prompts, memory cache) are lazy-loaded on first access, reducing import-time memory usage.

### Embedded and Ultra-Low-RAM Devices

Prism32 runs on devices with as little as 27 MB RAM (OpenWrt routers). On devices with <64MB RAM, low-RAM mode activates automatically at startup via `/proc/meminfo` detection:

- Only 3 base themes are loaded; extended themes and plugins are skipped.
- `startup_memory.md` and `soul.md` reads are deferred.
- Command output cap drops from 1500 to 500 chars; subagent result cap drops from 2000 to 800 chars.
- `MAX_CONTEXT_TOKENS` defaults to 4000.
- The banner shows `(low-RAM mode)` and the full POST sequence is skipped.

Tested on an OpenWrt TL-WR1043ND (27MB RAM, MIPS 24Kc, Python 3.7.13).

On extremely memory-constrained systems where CPython's parser cannot compile the source in RAM, cross-compile a `.pyc` locally for the target Python version and copy only the bytecode — no on-device compilation, no OOM risk:

```sh
# On a machine with matching Python version (e.g. 3.7):
python3.7 -m py_compile prism32.py

# Copy only the .pyc to the embedded device:
scp prism32.pyc root@router:/root/
ssh root@router 'python3 /root/prism32.pyc'
```

GitHub Releases include pre-built `.pyc` artifacts for Python 3.7 through 3.13 — download the one matching your device's Python version. The `.pyc` is architecture-agnostic (runs on x86, ARM, MIPS, RISC-V) but Python-version-specific.

Verified on:
- **OpenWrt router** (Atheros AR9132 MIPS, 27 MB RAM) — runs via `.pyc` in low-RAM mode, detects `OpenWrt on tl-wr1043nd`
- **Amazon Fire TV Stick** (MT8127 ARMv7, 874 MB RAM) — runs via `.py` directly, detects `Amazon Fire TV (AFTT)`
- **Amazon Kindle Fire tablet** (MT8186 ARM64, 2.8 GB RAM) — runs via `.py`, detects `Android/Termux on Amazon Kindle (KFTUWI)`

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

## Command-Line Flags

All flags are optional. `--model`, `--api`, and `--api-key` are **session-only overrides** — they apply for the current session and are never persisted to `config.json` (persist providers/models/keys with `/provider ...`, `/model ...`, or `/set ...` inside the app instead). On exit, Prism32 prints a warning if a session-only `--api-key` or other CLI override was never saved, so a working key is not silently lost to the next session:

| Flag | Effect |
| --- | --- |
| `--model, -m <name>` | Override model name for this session |
| `--api, -a <url>` | Override API base URL for this session |
| `--api-key, -k <key>` | Set API key for this session |
| `--theme, -t <name>` | Start with a specific theme (session-only) |
| `--turbo` | Force-enable live streaming (already the default) for this session |
| `--slow-cpu` | Non-streaming mode, save-on-interaction (old machines) |
| `--no-boot` | Skip the boot sequence |
| `--temperature <0.0-2.0>` | AI temperature (session-only) |
| `--goal, --mission, -g <task>` | Run a mission headless and exit on completion |
| `--set-timeout <sec>` | Set command timeout and exit |
| `--update <url|path>` | Update prism32 from a URL or file path and exit |
| `--resume-session <id>` | Resume a saved session id (used by hot update to keep the conversation) |
| `--setup-runtime` | Refresh startup memory, harness scan, evolve baseline, exit |
| `--harness-scan` | Scan for external AI harness CLIs and exit |
| `--evolve-setup` | Create evolve docs/baseline/tool scan and exit |
| `--version, -V` | Show version and exit |

Additional operator commands not listed elsewhere: `/agentname <name>`, `/autosave <sec>`, `/aitimeout <sec>`, `/rootpass <pwd>`, `/verify-ssl [on|off]`, `/maxhistory <n>`, `/maxtokens <n>`, `/compact`, `/wait`, `/bg`, `/interject`, `/board`. Extra environment variables: `PRISM32_VERIFY_SSL=0` (disable TLS verification), `PRISM32_DEVICE=<name>` (manual device label), plus `PRISM32_ARCH` and `NO_COLOR`.

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

During streaming responses, you can type at any time. The footer changes to `interject▶`. Press Enter to send your interjection as the next message after the AI finishes its current response.

Useful controls:

- Escape: **the only key that cancels** agent work. This covers streaming, non-streaming API waits, foreground commands, in-flight mission shards/subagents, and a blocking `/wait`. Escape is detected through a unified `select()` that polls stdin and stdout simultaneously, so there is no blind spot during tool execution. Typed interjections do NOT cancel — they are queued for after the current response completes.
- Ctrl+P: pause/resume the whole swarm between steps, non-destructively (running commands finish, processes untouched, no progress lost). While paused, typed messages reach the captain agent on its next model call. `/pause` and `/unpause` are the scriptable equivalents.
- Up/Down while interjecting: cycle previous interjections.
- Left/Right, Home, End: edit the interjection buffer.
- Delete (forward): delete the character after the cursor.
- Ctrl-A: move cursor to beginning (Home).
- Ctrl-E: move cursor to end.
- Ctrl-D: forward delete.
- Ctrl-K: kill to end of line.
- Ctrl-U: kill to beginning of line.
- Ctrl-W: delete word backward.
- Ctrl-C: cancel agent work or interrupt.
- Ctrl-L: clear/redraw.

Arrow keys are handled as escape sequences, so normal arrow-key editing does not trigger bare-Escape cancellation. Double-Escape also cancels.

## What The Installers Do

`install.sh` performs a Unix/macOS/BSD-style install:

- Validates `prism32.py` syntax (skipped on low-RAM devices <64 MB to avoid OOM).
- Detects total system RAM and warns if below 64 MB with embedded deployment instructions.
- Generates `.pyc` bytecode after install for faster startup (on capable systems).
- Creates a wrapper command named `prism32` in `${PREFIX:-/usr/local}/bin` when writable.
- Falls back to `~/.local/bin/prism32` during `-y` user-local installs without root.
- Creates `~/.prism32/`, `sessions`, `plugins`, `skills`, and `evolve` directories.
- Copies `prism32.py` to `~/.prism32/prism32.py` (works after removable media is ejected).
- Copies bundled default plugins (e.g. `web_scraper.py`) to `~/.prism32/plugins/`.
- Prompts for provider, endpoint, model, and API key when running interactively.
- Tests model API reachability when possible.
- Runs `prism32.py --setup-runtime` to create startup memory, harness scan, and evolve baseline files.

`install.ps1` performs a Windows user-local install:

- Copies `prism32.py` to `%LOCALAPPDATA%\Programs\Prism32`.
- Creates `prism32.cmd`.
- Creates runtime directories under `%USERPROFILE%\.prism32`.
- Runs `--setup-runtime` when possible.
- Adds the install directory to the user PATH.

`bootstrap.sh` is the universal auto-detecting installer (see the platform table under [Universal Bootstrap](#universal-bootstrap-any-platform)). It detects Termux/Android, OpenWrt, macOS, Linux and BSD package managers, and unknown platforms; installs Python 3 + git if missing; clones the repo (`--depth 1`) and runs the appropriate installer; updates existing clones with `git pull`; and falls back to direct `wget`/`curl` download of `prism32.py` for unknown platforms.

`termux-install.sh` installs `python3` and `git` via `pkg`, clones the repo, preserves existing config, and creates the `prism32` command in `$PREFIX/bin` (no root needed).

## First Run Setup

Recommended first commands:

```text
/provider             Interactive manager: pick by number → switch/edit/test
/provider add         Template wizard: preset → name → key → live test → model
/model                Browse every provider's models; assign main/subagent
/config               Show active config
/memory path
/help
```

Provider management examples:

```text
/provider add myserver http://192.168.1.50:8080/v1
/provider add openrouter https://openrouter.ai/api/v1
/provider key openrouter sk-or-v1-...
/provider api llamacpp-remote http://192.168.1.60:8080/v1
/provider test openrouter
/provider rm myserver
/provider list
```

- `add <name> <base> [model]` registers a provider; with no arguments it runs an interactive wizard (base → key → live reachability/auth test → model pick).
- `key <name> <key>` stores a per-provider key under `providers.<name>.api_key` (a bare `/provider key <key>` still sets the main key).
- `api <name> <url>` fixes that provider's base URL.
- `test [name]` runs a 3-step diagnostic: reachability → auth → model-in-catalog, with the exact fix command for each failure.
- Switching models and providers happens in `/model` — it lists every provider's models and assigns the right base+key per pick.

Model selection — browse every configured provider's catalog in one list, then assign a pick to the main agent or the subagent slot (mixing providers is fine):

```text
/model                     Full multi-provider browser
/model qwen                Same browser with search pre-filled
/set model <name>          Exact quick-set for the main model
```

Track session cost:

```text
/cost                 Show input/output tokens and dollar cost for this session
```

Prism32 captures token usage from both streaming and non-streaming API responses. Cost is calculated using real per-model pricing fetched from the provider's API at startup where available, with hardcoded prices for 29 common models (OpenAI, Anthropic, Groq, Together, Neuralwatt, OpenRouter) as fallback. Local models show $0.0000. The running cost is shown live in the status bar as `$X.XXXX` (alongside live subagent and background-job counts, `SA:n`/`BG:n`).

**Prompt caching** reduces repeated token costs:

- Anthropic native API: `cache_control` markers on the system prompt + oldest user message (ephemeral cache).
- OpenAI automatic caching: parses `cached_tokens` and bills at 0.5x.
- DeepSeek caching: parses `prompt_cache_hit_tokens` and bills at 0.1x.
- Toggle with `/prompt_caching on|off`. Only money saved is shown in `/cost`; no misleading cache hit token counts.

**Cheaper inference** tools:

- `compress_tool_turns()`: non-destructive compression of older verbose tool results, keeping the most recent 6 turns verbatim. Saves ~85% tokens on long sessions.
- System prompt is condensed (~190 tokens saved per request).
- `/set subagent_model` routes subagents to a cheaper model; `/set subagent_provider` routes them to a different provider entirely.
- `CONTEXT_RECENT_FLOOR` and `CONTEXT_COMPRESS_KEEP` are configurable.
- The `/model` browser shows each provider's `cheap_model` field with cost-saving suggestions.

## Built-In Providers

The built-in provider registry contains:

- `local`: `http://127.0.0.1:8080` (local llama.cpp server).
- `ollama`: `http://localhost:11434/v1`.
- `openai`: `https://api.openai.com/v1`.
- `anthropic`: `https://api.anthropic.com/v1`.
- `groq`: `https://api.groq.com/openai/v1`.
- `together`: `https://api.together.xyz/v1`.
- `openrouter`: `https://openrouter.ai/api/v1`.
- `neuralwatt`: `https://api.neuralwatt.com/v1`.
- `deepseek`: `https://api.deepseek.com/v1`.
- `llamacpp-remote`: no default host — configure its address with `/provider api llamacpp-remote http://<host>:8080/v1`.
- `custom`: operator-specified.

Add your own with `/provider add <name> <base> [model]` or the `/provider add` wizard; remove with `/provider rm <name>`. Per-provider keys persist under `providers.<name>.api_key` in `config.json` and win for their own provider; model/provider selection happens in `/model`.

Prism32 sends OpenAI-style `/chat/completions` requests (protocol is routed by each request's base URL, so mixing providers in one session is safe). Providers work best when they expose an OpenAI-compatible API surface. For providers with native non-OpenAI APIs, use a compatible proxy or gateway.

## Common Commands

All commands require the `/` prefix. Bare text is sent to the AI.

Not all commands are available to both the operator and the model. Commands that manage the session, config, providers, models, and system state (`/config`, `/savecfg`, `/provider`, `/model`, `/theme`, `/stream`, `/help`, `/quit`, `/clear`, `/save`, `/load`, `/resume`, `/sessions`, `/skill-create`, `/auto delete|pause|resume|show`, `/shard reset`, `/memory edit`, `/plugins`, `/usage`, and similar session/config commands) are operator-side only. The model cannot issue them from `execute` blocks. (`/delegate`, `/spawn`, `/subagents`, `/collect`, `/wait`, `/bg`, `/bgs`, `/board`, `/remember`, `/recall`, `/memories`, `/forget`, `/json`, `/quantum`, and plugin commands are exceptions — they work for both the operator and from execute blocks.)

Core:

```text
/help                 Show command reference
/version              Show version, Python, platform, runtime dir
/quit                 Exit
/clear                Clear current conversation history
/config               Show current configuration
/savecfg              Save configuration
/loadcfg              Reload configuration
/model                Browse all providers' models; assign main/subagent
/provider add|rm|api|key|test|list
                      Manage the provider registry
```

AI and task execution:

```text
/mission <goal>       Start an orchestrated autonomous mission
/mission status       Show mission todo tree and running shards
/mission pause        Pause mission dispatch (running shards finish)
/mission resume       Resume a paused mission
/mission interject <note>
                      Add a team note delivered to future shards
/mission board        Show the active mission's shared board
/mission wait         Block until the active mission completes
/stream on|off        Toggle streamed responses
/temperature <0-2>    Set model temperature
/thinking off|low|medium|high
                      Set reasoning effort (saves to config)
/timeout <seconds>    Set shell command timeout
/aitimeout <seconds>  Set AI request wait timeout (default 3600s; flex models need more)
/maxsteps <n>         Set mission per-step budget (default 1000; each shard capped at 25)
/maxsteps sub <n>     Set subagent step budget for /spawn and /delegate (default 200)
/cost                 Show session token usage and dollar cost
/usage                Show API usage/cost (OpenRouter)
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
/json <file> [--key path] [--compact]
                      Read JSON files with smart summaries
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

Subagents, background jobs, and shared context:

```text
/delegate <task>      Run a synchronous subagent
/spawn <task>         Start an asynchronous subagent
/wait [id] [--timeout s]
                      Block until subagents/bg jobs finish (default: indefinite)
/interject <id> <msg> Steer a running subagent mid-task (no restart)
/bg <cmd>             Run a long shell command in the background
/bg                   List background jobs
/bgs                  List background jobs (alias)
/subagents            List running/completed subagents
/collect <id>         Show a completed subagent's or job's result (records stay for re-reads)
/pause | /unpause    Freeze/resume the whole swarm between steps (Ctrl+P too)
/board <text>         Post to the active mission's shared board (bare /board reads it)
/subagent-model       Pick or show default subagent model
/sam <model>          Alias for subagent-model
/quantum              Show shared session context
/quantum key:value    Set a shared context value
/quantum key:         Read a shared context value
/quantum key          Read a shared context value (no colon)
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

## Block Architecture

Prism32 uses **block architecture** instead of traditional tool-calling. The model writes commands in fenced markdown code blocks, and Prism32 parses, executes, and feeds results back — all through plain chat messages. No `tools` parameter, no JSON schemas, no `tool_calls` array.

### How It Works

The model communicates through three block types:

```text
```execute
ls -la && grep "error" /var/log/syslog
```

This is a command block. Prism32 executes it via the shell and
feeds the output back as the next user message. The model sees
the result and continues working.

```ask
Which interface should I configure?
```

This is a question block. Prism32 pauses, shows the question to
the operator, and feeds the answer back. Mission shards and
subagents are told to work autonomously and finish with a
plain-text result instead of asking.

```execute
df -h
```
```execute
free -m
```
```execute
uname -a
```

Multiple execute blocks in one response are executed sequentially.
Each result is appended to history as a separate user message, so
the model sees all prior results when deciding the next step.
```

### The Execution Loop

```text
1. Model response → Prism32 extracts execute blocks
2. For each block:
   a. Check if it's a plugin command (/quantum, /extend, /skill-load, etc.)
   b. If not, execute as shell command via run_cmd()
   c. Capture output (results fed back to the model are capped — 1500 chars normal, 500 on low-RAM devices)
   d. Feed result back: "Executed: <cmd>\nResult:\n<output>\nContinue..."
3. Model sees all results and decides next action
4. Repeat until model gives final answer with no execute blocks
```

### Commands Available Inside Execute Blocks

The model can use any shell command plus these Prism32-native commands:

| Command | Purpose |
|---------|---------|
| Any shell command | Full bash/POSIX access (the normal path) |
| `/quantum <key>:<value>` | Read/write shared agent context |
| `/board <text>` | Read/append the active mission's shared board |
| `/delegate <task>` | Run a synchronous subagent |
| `/spawn <task>` | Start an async subagent |
| `/subagents` | List subagents |
| `/wait [id] [--timeout s]` | Block until subagents/background jobs finish |
| `/interject <id> <msg>` | Steer a running subagent mid-task |
| `/bg <cmd>` / `/bgs` | Start/list background shell jobs |
| `/pause` / `/unpause` (Ctrl+P) | Non-destructive swarm pause/resume |
| `/compact` | Manually compact the session context now |
| `/collect <id>` | Show a completed subagent's or job's result |
| `/remember`, `/recall`, `/memories`, `/forget` | Long-term memory |
| `/auto create|list|run` | Create, list, or run automations |
| `/skill-list`, `/skill-load <name>` | List/inject skills |
| `/shard show|deploy|set|secrets|complete` | Promptshard management |
| `/harness scan\|context\|path\|delegate` | Harness detection and super-subagent delegation |
| `/evolve on\|tools\|diff\|docs\|context` | Evolve mode |
| `/extend temp\|permanent <goal>` | Generate and load a plugin |
| `/json <file>` | Smart JSON reads |
| `/memory path` | Show memory file paths |
| Any plugin command | Auto-discovered and advertised in context |

Both `/delegate` and `/spawn` accept a trailing `--provider <name>` to run that subagent on a different configured provider. Operator-only commands (`/provider`, `/config`, `/model`, `/theme`, `/save`, `/load`, `/update`, etc.) cannot be used from execute blocks — `/update` in particular must be run by you at the prompt, or via the `--update` flag before starting an agent session.

### Tool Call Healing

Models that use native tool-calling formats (GLM-5's `<|tool_calls_section_begin|>`, Qwen's function-call JSON, bare `{"command": "..."}`) are automatically healed:

1. `heal_response()` detects non-standard formats
2. Converts them to proper `execute` blocks
3. Strips all leftover markup tags from the displayed text
4. Shows a "Tool call format healed" status
5. Appends a reminder: "Use ```execute blocks for commands"

This means Prism32 works with any model — even ones that try to use their native tool-calling format — without configuration.

### Why Block Architecture Is Superior

**Provider-agnostic.** No `tools` parameter in the API request. Works with any OpenAI-compatible endpoint: local llama.cpp, GLM, Qwen, Groq, OpenRouter, Neuralwatt, Anthropic. Zero provider-specific tool schema configuration.

**Self-healing.** Traditional tool-calling breaks if the model emits malformed JSON or uses the wrong envelope. Prism32's healing layer converts any tool-call format to execute blocks automatically. The agent keeps working.

**Multiple commands per turn.** Many APIs limit tool calls to one per message. Execute blocks have no limit — the model can chain `df -h`, `free -m`, and `uname -a` in one response, each executed sequentially with results fed back.

**Mixed prose and commands.** The model writes analysis, commands, and questions in one message. Execute/ask blocks are hidden from the displayed output during streaming, so the user only sees the model's reasoning.

**Cancellable mid-execution.** `run_cmd()` polls for user input every 50ms. Press Escape to kill the running process tree (`SIGTERM`/`SIGKILL` via process groups). Type text to interject a new instruction that becomes the next user message.

**Extensible without schemas.** Adding a new capability is a plugin registration (`registry.register(...)`) or `/extend temp <goal>`. The new command is auto-advertised in the system prompt's context block. No JSON schema, no `tools` array, no provider configuration.

**Full shell access.** One execute block surface gives the model the entire POSIX/Windows shell — pipes, redirects, variables, loops. Traditional tools require a separate function for each operation.

**Cross-agent shared state.** The `/quantum` shared context lets the main agent and subagents exchange key-value data through execute blocks. No provider-managed tool state.

**Token-efficient.** No JSON tool schemas sent on every request. The system prompt is the only recurring token cost. Available commands are dynamically listed in context.

**Lower cognitive load for the model.** The model writes commands the same way it writes prose — fenced code blocks. No structured JSON, no tool IDs, no role management. Just write what you want to run.

## Context Management

Prism32 uses an intelligent multi-level context compression system inspired by promptshard architecture. When context fills up, the agent doesn't lose track — it keeps working like nothing happened.

### How It Works

When context reaches 75% of the model's window, Prism32 automatically:

1. **Reserves 8K+ tokens for recent messages** (or 30% of the window, whichever is larger) — the agent always has enough recent context to continue seamlessly
2. **Builds an intelligent summary** of the dropped messages:
   - **OBJECTIVE**: the active goal (never lost across trims)
   - **DISCOVERIES**: key facts extracted from command results — IP addresses, file paths, error messages, package versions
   - **ERRORS**: recurring problems encountered
   - **LAST ANALYSIS**: compressed key points from the last assistant response
3. **Injects the summary** as a system message between the system prompt and recent messages
4. **Compresses old command results** in kept messages — verbose output replaced with key facts only (e.g. `Executed: ip addr\nResults: inet 192.168.1.100; ERROR: wlan0 down`)

### Key Fact Extraction

The summarization engine scores every line by information density:

| Pattern | Score |
|---------|-------|
| IP addresses (192.168.x.x) | 3 points |
| File paths (/etc/nginx/conf) | 3 points |
| Errors/failures/denied | 3 points |
| Package commands (apt/pip/brew) | 2 points |
| Version numbers (v1.2.3) | 2 points |

Only the top N most information-dense lines are kept. Lines <5 or >200 chars are skipped.

### Session Intelligence

Prism32 tracks session state across trims:

- **Objective**: set by `/mission`, survives all context trims
- **Discoveries**: accumulated key facts from command results
- **Errors**: recurring problems tracked across the session
- **Trim count**: how many times context was compressed

This state is cleared on `/clear` and when the active mission ends.

### Recent Message Floor

The system guarantees at least **8K tokens** of recent messages in normal trimming (4K on very small models, or 50% of the context window, whichever is larger). This means:

- The agent always sees its last few commands and results in full
- The agent always sees the last user instruction
- The agent always sees its last analysis
- The summary fills in what happened before

The result: the agent keeps going when its context fills up and doesn't lose track of what it was doing.

## Mission Mode Examples

Mission mode is for goals where you want Prism32 to plan the work, dispatch parallel workers, and keep going until the goal is structurally complete.

```text
/mission find what llama.cpp command runs qwen 3.6 at the fastest tokens per second on this system
```

```text
/mission inspect this git repository, run the tests, comb through the code for bugs
```

```text
/mission audit this server for disk pressure, failed services, open ports, and risky logs; report only
```

When you start a mission:

1. **Clarify** — if the goal is ambiguous, the planner asks the operator 1-3 short questions before decomposing (skipped in headless mode; press Enter to accept the goal as-is).
2. **Plan** — the planner decomposes the goal into 3-6 short imperative steps (with a heuristic fallback split).
3. **Dispatch** — every ready step (parent chain done) runs as a PARALLEL subagent shard: siblings run concurrently, children wait for their parents.
4. **Complete structurally** — the mission ends when all leaf steps are done or failed. A failed step requeues once, then its leaf is marked failed and the mission continues.

Every shard receives the mission context: the goal, the last 10 completed step results, and team notes — so shards build on each other instead of redoing work. Shards and the operator can also share scratch state through the mission board: post with `/board <text>` (or `/mission board` to read it); entries expire when the mission completes. The REPL stays live while the mission runs — `/mission` returns instantly.

On completion you get a summary box (per-step results, failures marked) and the full result lands in quantum context as `mission_<id>_result` for the main agent and cross-agent handoff. `/maxsteps <n>` sets the per-step (per-todo) shard step budget — each shard is additionally capped at 25 steps. `/goal` still works as an alias for `/mission`.

Run a mission headless (plans, runs, exits on completion):

```sh
prism32 --mission "audit this server and write a report to /tmp/audit.md"
# --goal is an alias for --mission
```

## Subagents

Subagents are independent task runners with their own mini history. They use the same model as the main agent by default, or the subagent slot (`Config.SUBAGENT_MODEL` + `Config.SUBAGENT_PROVIDER`) if set — so subagents can deliberately run on a different, cheaper provider than the main agent. Change at runtime with `/set subagent_model <model>` and `/set subagent_provider <name>`, or pick both slots from `/model`. Each subagent run gets a TCP pre-flight check on its provider base and fails fast with an actionable fix command if the endpoint is down. Subagents are capped at `SUBAGENT_MAX_STEPS` steps (default 200; change with `/maxsteps sub <n>`).

Run synchronously:

```text
/delegate summarize the last 20 commits and identify risky changes
```

Run asynchronously:

```text
/spawn scan this repository for TODO comments and group them by subsystem
```

Use another configured provider (works for both `/delegate` and `/spawn`):

```text
/delegate write a release checklist --provider openrouter
/spawn inspect package manager options --provider ollama
```

**Completion is event-driven — do not poll.** When a subagent or background job finishes, its result is pushed into the conversation automatically as a completion notice (and into quantum context as `subagent_<id>_result` / `bg_<id>_result`). The status bar shows live counts (`SA:n` for subagents, `BG:n` for background jobs). If you must block, use:

```text
/wait                 Block until ALL subagents and bg jobs finish (no timeout)
/wait <id>            Block until one specific subagent or job finishes
/wait --timeout 60    Bound the wait; default is no timeout; Escape cancels
```

Long shell commands (builds, deploys, transfers) can run detached with `/bg <command>` — the result is pushed to the agent when it finishes. `/bg` bare (or `/bgs`) lists background jobs. While subagents are running, any `sleep` command the model tries to run is capped at 30 seconds with an explanatory note — the wait primitives replace sleep-polling.

`/collect <id>` shows a completed subagent's or job's result and appends it to the conversation. Collecting does not destroy the record — results stay available for re-reads (and in quantum context) and are reaped by a 1h garbage collector. `/subagents` lists status without touching records.

**Steer, don't kill.** If a subagent is going the wrong way, `/interject <id> <message>` delivers a steering message into its conversation on its next step — no cancellation, no restart, no lost progress:

```text
/interject sa_3 the config file is at /etc/opt/app.conf, not /usr/local/etc
```

Subagents emit a progress heartbeat into the shared event stream every 25 steps, so the main agent (and sibling agents) see step counts and last commands instead of silence. Parallel spawns beyond `max_concurrent_subagents` (default 6, config key `max_concurrent_subagents`) queue for a free run slot instead of thrashing provider rate limits.

**Pausing the swarm.** Ctrl+P during AI activity (or `/pause` and `/unpause` anytime) freezes the whole swarm between steps, non-destructively: running commands and processes finish untouched, no new agent steps start, nothing is cancelled or lost. While paused the interjection reader stays live — type a message to talk to the captain agent, or use `/interject` to steer a subagent, then Ctrl+P (or `/unpause`) to continue exactly where everything left off. The status bar shows `PAUSED` while held.

Subagent results are stored into the in-memory quantum context and important results may also be stored in long-term memory.

## Quantum Context

Quantum context is a purely in-memory thread-safe key-value store shared by the main session and all subagents. It is used to share short facts, task results, and handoff data. Nothing is written to disk.

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
/mission create a temporary plugin to connect to my outdoor webcam and send me a telegram message when my important package arrives today from USPS
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

Plugin commands can be called as normal slash commands. They can also be used from AI `execute` blocks in the default active task loop, the subagent loop, and mission shards.

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

Detected tools may include OpenCode, Codex CLI, Claude Code, KimiCode, Aider, Gemini CLI, Goose, Pi AI CLI, Hermes Agent, Cursor Agent, and related commands. Prism32 does not bundle or authenticate those tools. It only detects what exists locally and adds that information to the AI context.

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
- `ai_timeout`: AI request wait timeout in seconds (default 3600).
- `goal_max_steps`: per-step (per-todo) shard step budget for missions (see `/maxsteps`).
- `subagent_max_steps`: step budget for `/spawn` and `/delegate` subagents (default 200; see `/maxsteps sub`).
- `max_memory_ctx`: character limit for injected memory context.
- `subagent_model`: optional model override for subagents.
- `subagent_provider`: optional provider override for subagents (empty = main provider).
- `agent_name`: display name shown before assistant responses.

Use `/config`, `/savecfg`, and `/loadcfg` rather than editing JSON while Prism32 is running.

Set or reset a custom API base URL without it being clobbered by provider switches:

```text
/set api_base <url>      # persist a custom endpoint
/set api_base reset      # revert to the provider's default
/provider api <name> <url>   # fix one provider's own base
```

The `custom_api_base` flag is saved in config across sessions.

## Themes

Prism32 registers 34 themes, including phosphor, amber, cyan, vapor, nord, solarized, neon, retro, ice, ocean, sunset, forest, plasma, clear, glass, ghost, smoke, paper, ink, daylight, slate, synthcity, outrun, laserdisc, vapordark, chromecrt, sgi, dec, monoamber, iris, hpterm, ember, cyber, and cyberspace.

Cycle themes:

```text
/theme
```

Set a core theme at startup:

```sh
prism32 --theme amber
```

For old terminals, prefer the 16-color compatible themes such as `sgi`, `dec`, `monoamber`, `iris`, and `hpterm` through runtime theme cycling or configuration.

The default visual style uses half-block borders (`▛▀▜` / `▙▄▟`), `|` status-bar separators, `▶` prompt arrows, and `✓`/`✗` success markers on tool output. Step headers use thin `─` lines, and content boxes expand to the terminal width (capped at 78 chars).

## Floppy And Removable Media

The project includes tooling to build a FAT12 floppy disk image that bundles Prism32 with your configuration, API keys, plugins, and memory:

```sh
python3 make_floppy.py                    # build image to /tmp/prism32_floppy.img
python3 make_floppy.py --write            # build + write to detected removable device
python3 make_floppy.py --write /dev/sdc   # write to specific device
sh floppy-install.sh                      # auto-detect and write
```

The floppy image includes:
- `prism32.py`, `install.sh`, `README.md`, `LICENSE`, `pyproject.toml`
- Your `config.json` (with API keys, model, provider — copied automatically)
- Your `memory.json`, `startup_memory.md`, `soul.md`, `harnesses.json`, `promptshard.md`
- Your plugins (e.g. `web_scraper.py`)

Insert the media on any machine with Python 3.7+, mount it, and run:

```sh
mount /dev/sdX /mnt/floppy
cd /mnt/floppy && sh AUTORUN.SH
```

The installer copies `prism32.py` to `~/.prism32/` locally, so the media can be ejected after install. Your configuration, plugins, and memory are all preserved. Total image size: ~470 KB, fits easily on 1.44 MB floppy with ~68% free.

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
- Limit mission steps with `/maxsteps` on expensive models so expensive models don't drain your bank account looping on a simple task

## Troubleshooting

API connection failed:

```text
/provider test
/provider list
/provider api <name> https://your-provider/v1
/provider key <name> YOUR_KEY
/model
```

`/provider test <name>` runs the full 3-step diagnostic (reachability → auth → model-in-catalog) and prints the exact fix command for whatever fails.

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

"Process killed" or OOM on an embedded device (router, IoT):

The single-file `prism32.py` is ~600 KB. On devices with less than ~64 MB RAM, CPython's parser may not have enough memory to compile it. Use a pre-compiled `.pyc` instead (see "Embedded and Ultra-Low-RAM Devices" above), or compile on a host with the same Python version and copy the `.pyc` to the device.

Cost tracking shows wrong amount:

Prism32 fetches real per-model pricing from the provider's API at startup (for providers that expose it, like Neuralwatt and OpenRouter). If the model is not in the provider's model list, hardcoded prices from `_MODEL_PRICING` are used. If those are also missing, a heuristic estimate is used. To verify pricing for the current model, run `/config` and check the model name.

"Low RAM detected" warning during install:

This is expected on embedded devices (<64 MB RAM). The installer skips `py_compile` syntax checking to avoid OOM during installation. Compile a `.pyc` on a host with more RAM and copy it to the device.

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

GitHub Releases automatically include pre-compiled `.pyc` bytecode artifacts for Python 3.7 through 3.13, for deployment on embedded devices that cannot compile the source in RAM.

Deployed and tested on:
- Amazon Fire TV Stick (AFTT, ARMv7, 874 MB RAM, Python 3.8)
- Amazon Kindle Fire tablet (KFTUWI, ARM64, 2.8 GB RAM, Python 3.13)
- OpenWrt router (TL-WR1043ND, MIPS , 27 MB RAM, Python 3.7 via `.pyc`)
- Arch Linux desktop (x86_64, Python 3.14)
- Ubuntu desktop (x86_64)
- Raspberry pi 3b+ pi os
- Android phone Termux ARM64
- Compaq Pentium III 800Mhz Unix NetBSD 10.1 x86 512mb ram
- 2012 Imac MacOS high Sierra 
- Windows 11 powershell HP notebook (x86 n100)
- Pentium M 2005 durabook 2GB DDR2
- Synology Nas DS414 ARM64 1GB ram

## Developer Notes
This is a solo developer project so it's just me funded by donations and the free hardware I find, Dono's are appreciated as I am trying to get a new ISP or internet as my current one is run by crooks with broken unreliable service and bandwidth not enough for my devices
buymeacoffee.com/sebastianflynn

## License

See the repository license. Project metadata currently declares APACHE 2.0
