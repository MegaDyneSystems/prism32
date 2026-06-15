# Prism32 Windows Install

This is the quick Windows install guide for Prism32.

## Files

- `prism32.py`: Prism32 main program.
- `install.ps1`: PowerShell installer.
- `Install-Prism32-Windows.cmd`: double-click installer launcher.
- `README.md`: full Prism32 operator guide.
- `README_WINDOWS.md`: this quick Windows install guide.
- `pyproject.toml`: package metadata.

## Requirements

- Windows 11, Windows 10, or older Windows where Python 3.7+ is installed.
- Practical oldest target: Windows 7/Vista-era systems with Python 3.7 available.
- No pip packages are required. Prism32 is stdlib-only.
- Network access is needed only when using a remote AI provider.

## Fast Install

1. Open this folder in File Explorer.
2. Double-click `Install-Prism32-Windows.cmd`.
3. If Windows asks, allow the script to run.
4. Open a new Command Prompt or PowerShell window.
5. Run:

```bat
prism32
```

## Manual PowerShell Install

Open PowerShell in this folder and run:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File .\install.ps1 -Yes
```

Then open a new terminal and run:

```bat
prism32 --setup-runtime
prism32
```

## Manual No-Install Run

If you only want to test Prism32 from this folder:

```bat
python prism32.py --setup-runtime
python prism32.py
```

If your system uses the Python launcher:

```bat
py -3 prism32.py --setup-runtime
py -3 prism32.py
```

## Where It Installs

The installer copies Prism32 to:

```text
%LOCALAPPDATA%\Programs\Prism32\prism32.py
%LOCALAPPDATA%\Programs\Prism32\prism32.cmd
```

It creates runtime files in:

```text
%USERPROFILE%\.prism32\config.json
%USERPROFILE%\.prism32\startup_memory.md
%USERPROFILE%\.prism32\harnesses.json
%USERPROFILE%\.prism32\evolve\
%USERPROFILE%\.prism32\plugins\
%USERPROFILE%\.prism32\sessions\
```

The installer also adds `%LOCALAPPDATA%\Programs\Prism32` to the user PATH. Open a new terminal after installing so Windows reloads PATH.

## API Setup

After launching Prism32, configure a provider:

```text
/provider
/provider key YOUR_API_KEY
```

You can also run locally against an OpenAI-compatible endpoint:

```bat
prism32 --api http://127.0.0.1:8080
```

## Startup Memory

Prism32 creates an editable startup memory file:

```text
%USERPROFILE%\.prism32\startup_memory.md
```

Inside Prism32:

```text
/memory show
/memory edit
/memory append remember this Windows machine has PowerShell 5 only
/memory refresh
/memory path
```

Use this file for hardware notes, software tips, terminal quirks, shell notes, and workflow preferences.

## Harness, Plugins, And Evolve

Prism32 can scan for external AI agent CLIs and expose them to its context:

```text
/harness scan
/harness
/harness delegate inspect this project
```

Prism32 can also enable self-repair and plugin-generation context:

```text
/evolve on
/evolve docs
/evolve tools
/evolve diff
/extend prompt
```

Plugins load from:

```text
%USERPROFILE%\.prism32\plugins\
```

## Troubleshooting

If `prism32` is not recognized:

```bat
%LOCALAPPDATA%\Programs\Prism32\prism32.cmd
```

Then open a new terminal. If needed, add this folder to PATH manually:

```text
%LOCALAPPDATA%\Programs\Prism32
```

If Python is missing:

- Windows 10/11: install current Python 3 from python.org.
- Windows 7: install Python 3.7.9, the last Python 3.7 Windows release commonly used for legacy systems.
- During install, enable `Add Python to PATH` or install the Python launcher.

If PowerShell script execution is blocked:

```powershell
Set-ExecutionPolicy -Scope Process Bypass
.\install.ps1 -Yes
```

If colors or the bottom bar look wrong on an old Windows console:

```bat
setx NO_COLOR 1
```

Then open a new terminal and run Prism32 again. Prism32 has a plain prompt fallback for old consoles.
