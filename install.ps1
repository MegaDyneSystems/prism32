param(
    [switch]$Yes
)

$ErrorActionPreference = "Stop"

function Info($msg) { Write-Host "  $msg" }
function Ok($msg) { Write-Host "  * $msg" }
function Warn($msg) { Write-Host "  ! $msg" }

$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$Source = Join-Path $ScriptDir "prism32.py"
$HomeDir = [Environment]::GetFolderPath("UserProfile")
$Runtime = Join-Path $HomeDir ".prism32"
$InstallDir = Join-Path ([Environment]::GetFolderPath("LocalApplicationData")) "Programs\Prism32"
$Target = Join-Path $InstallDir "prism32.py"
$CmdShim = Join-Path $InstallDir "prism32.cmd"

Write-Host ""
Write-Host "  Prism32 Windows Installer v6.7"
Write-Host ""

if (!(Test-Path $Source)) {
    throw "prism32.py not found next to install.ps1"
}

$Python = $null
$PythonArgs = @()
foreach ($candidate in @("py", "python3", "python")) {
    $cmd = Get-Command $candidate -ErrorAction SilentlyContinue
    if ($cmd) {
        try {
            if ($candidate -eq "py") {
                & $candidate -3 -c "import sys; raise SystemExit(0 if sys.version_info >= (3,7) else 1)" | Out-Null
                $Python = $candidate
                $PythonArgs = @("-3")
            } else {
                & $candidate -c "import sys; raise SystemExit(0 if sys.version_info >= (3,7) else 1)" | Out-Null
                $Python = $candidate
                $PythonArgs = @()
            }
            break
        } catch {
            $Python = $null
            $PythonArgs = @()
        }
    }
}

if (!$Python) {
    throw "Python 3.7+ not found. Install Python 3.7+ and rerun this script. Windows 7/Vista-era systems need a compatible Python 3.7 install."
}

New-Item -ItemType Directory -Force -Path $InstallDir | Out-Null
New-Item -ItemType Directory -Force -Path $Runtime | Out-Null
New-Item -ItemType Directory -Force -Path (Join-Path $Runtime "plugins") | Out-Null
New-Item -ItemType Directory -Force -Path (Join-Path $Runtime "skills") | Out-Null
New-Item -ItemType Directory -Force -Path (Join-Path $Runtime "sessions") | Out-Null
New-Item -ItemType Directory -Force -Path (Join-Path $Runtime "evolve") | Out-Null

Copy-Item -Force $Source $Target
Ok "Installed $Target"

$pyLine = if ($Python -eq "py") { "py -3" } else { $Python }
Set-Content -Path $CmdShim -Encoding ASCII -Value "@echo off`r`n$pyLine `"$Target`" %*`r`n"
Ok "Command shim $CmdShim"

try {
    & $Python @PythonArgs $Target --setup-runtime | Out-Null
    Ok "Runtime memory/harness/evolve setup complete"
} catch {
    Warn "Runtime setup skipped; run prism32 --setup-runtime later"
}

$PathUser = [Environment]::GetEnvironmentVariable("Path", "User")
if ($PathUser -notlike "*$InstallDir*") {
    [Environment]::SetEnvironmentVariable("Path", ($PathUser.TrimEnd(';') + ";" + $InstallDir), "User")
    Warn "Added Prism32 to user PATH. Open a new terminal before running prism32."
}

Write-Host ""
Info "Run: prism32"
Info "Startup memory: $(Join-Path $Runtime 'startup_memory.md')"
Info "Harness scan: $(Join-Path $Runtime 'harnesses.json')"
Info "Evolve docs: $(Join-Path $Runtime 'evolve\evolve.md')"
Write-Host ""
