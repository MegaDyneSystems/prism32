# Prism32

Prism32 is a tiny but powerful terminal AI agent. It is one Python file, stdlib-only, and built for real terminals, old machines, servers, BSD boxes, macOS, Linux, Termux, Windows, containers, and weird Unix systems where a browser-based AI tool is too heavy.

Full manual: `README.md`.

## Fastest Start

```sh
git clone https://github.com/megadyne/prism32.git && cd prism32 && bash install.sh && prism32
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
git clone https://github.com/megadyne/prism32.git && cd prism32 && bash install.sh
```

User-local non-root install:

```sh
git clone https://github.com/megadyne/prism32.git && cd prism32 && bash install.sh -y
```

Run without installing:

```sh
git clone https://github.com/megadyne/prism32.git && cd prism32 && python3 prism32.py --setup-runtime && python3 prism32.py
```

Windows PowerShell:

```powershell
git clone https://github.com/megadyne/prism32.git; cd prism32; powershell -ExecutionPolicy Bypass -File .\install.ps1
```

Termux:

```sh
pkg update && pkg install python git && git clone https://github.com/megadyne/prism32.git && cd prism32 && python prism32.py --setup-runtime && python prism32.py
```

## Why It Is Different

- No pip dependencies, no Node.js, no browser runtime, no database.
- Talks to OpenAI-compatible APIs: local llama.cpp, Ollama, OpenAI, Groq, Together, OpenRouter, custom gateways, and compatible proxies.
- Runs shell commands from AI `execute` blocks and feeds results back until the task is done.
- `/goal <task>` runs autonomous multi-step work with a configurable step limit.
- `/delegate` and `/spawn` create subagents for synchronous or async work.
- Plugins in `~/.prism32/plugins/*.py` can add slash commands, providers, themes, context, timers, and HTTP helpers.
- `/extend <goal>` can ask the configured model to generate, syntax-check, write, load, and immediately use a task-specific plugin.
- Memory files keep machine notes, long-term notes, custom rules, tool scans, sessions, and evolve baselines.
- Harness absorption detects external AI CLIs such as OpenCode, Codex CLI, Claude Code, Aider, Gemini CLI, Goose, and Cursor Agent.
- Press Escape to stop streaming, API waits, foreground commands, and goal mode.

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
