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
Write-Host "  Prism32 Windows Installer v7.4.0"
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
                # Native exit codes do NOT throw in Windows PowerShell —
                # without this check the MS-Store python stub was accepted.
                if ($LASTEXITCODE -ne 0) { $Python = $null; continue }
                $Python = $candidate
                $PythonArgs = @("-3")
            } else {
                & $candidate -c "import sys; raise SystemExit(0 if sys.version_info >= (3,7) else 1)" | Out-Null
                if ($LASTEXITCODE -ne 0) { $Python = $null; continue }
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
    if ($LASTEXITCODE -ne 0) { Warn "Runtime setup failed; run prism32 --setup-runtime later" }
    else { Ok "Runtime memory/harness/evolve setup complete" }
} catch {
    Warn "Runtime setup skipped; run prism32 --setup-runtime later"
}

# ── Scan for remote llama.cpp instances on the local network ──
$ConfigFile = Join-Path $Runtime "config.json"
if (-not (Test-Path $ConfigFile)) {
    Write-Host ""
    Info "Scanning network for remote llama.cpp instances..."
    $ScanResult = try {
        & $Python -c @'
import socket, urllib.request, json, concurrent.futures, sys

def probe(ip, port):
    try:
        url = "http://{0}:{1}/v1/models".format(ip, port)
        req = urllib.request.Request(url, headers={"User-Agent": "Prism32-Installer"})
        with urllib.request.urlopen(req, timeout=2) as r:
            data = json.loads(r.read().decode("utf-8", errors="replace"))
            models = [m.get("id", "") for m in data.get("data", [])]
            return {"ip": ip, "port": port, "models": models[:8]}
    except Exception:
        return None

# Get local subnet via socket
subnet = None
try:
    h = socket.gethostname()
    ip = socket.gethostbyname(h)
    octets = ip.split(".")
    if len(octets) == 4 and not ip.startswith("127."):
        subnet = ".".join(octets[:3])
except Exception:
    pass

if not subnet:
    print("[]")
    sys.exit(0)

PORTS = [8080, 8000, 8081, 5000, 11434]
ips = ["{0}.{1}".format(subnet, i) for i in list(range(1, 31)) + list(range(100, 121))]
found = []

with concurrent.futures.ThreadPoolExecutor(max_workers=50) as ex:
    futures = {ex.submit(probe, ip, p): (ip, p) for ip in ips for p in PORTS}
    for f in concurrent.futures.as_completed(futures, timeout=10):
        try:
            r = f.result(timeout=2)
            if r:
                found.append(r)
        except Exception:
            pass

seen = set()
unique = []
for r in found:
    key = "{0}:{1}".format(r["ip"], r["port"])
    if key not in seen:
        seen.add(key)
        unique.append(r)
print(json.dumps(unique))
'@ 2>$null
    } catch { "[]" }

    $ScanCount = try { ($ScanResult | ConvertFrom-Json).Count } catch { 0 }
    if ($ScanCount -gt 0) {
        Ok "Found $ScanCount remote llama.cpp instance(s)"
        $ScanResult | ConvertFrom-Json | ForEach-Object {
            $url = "http://$($_.ip):$($_.port)"
            $model = if ($_.models.Count -gt 0) { $_.models[0] } else { "default" }
            Write-Host "  [$($url)]  model: $model"
        }

        # Build config with scanned providers
        $Providers = @{}
        $FirstUrl = ""
        $FirstModel = "default"
        $i = 1
        $ScanResult | ConvertFrom-Json | ForEach-Object {
            $key = "llama_remote_$i"
            $url = "http://$($_.ip):$($_.port)"
            $model = if ($_.models.Count -gt 0) { $_.models[0] } else { "default" }
            $Providers[$key] = @{ api_base = $url; model = $model; api_key = "" }
            if ($i -eq 1) { $FirstUrl = $url; $FirstModel = $model }
            $i++
        }

        $Config = @{
            theme = "phosphor"
            provider = "llama_remote_1"
            model = $FirstModel
            api_base = $FirstUrl
            api_key = ""
            max_history = 2000
            max_response_tokens = 8192
            cmd_timeout = 600
            goal_max_steps = 1000
            stream = $false
            max_memory_ctx = 1024
            subagent_model = ""
            verify_ssl = $true
            agent_name = "MDS"
            providers = $Providers
        }
        $Config | ConvertTo-Json -Depth 5 | Set-Content -Path $ConfigFile
        Ok "Config created (provider: llama_remote_1 @ $FirstUrl)"
    } else {
        Warn "No remote llama.cpp instances found on local network"
        Warn "No AI provider configured — run 'prism32' then /setup to configure one"
    }
}

$PathUser = [Environment]::GetEnvironmentVariable("Path", "User")
if (-not $PathUser) { $PathUser = "" }   # fresh profiles return $null — TrimEnd on it crashed the script
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
