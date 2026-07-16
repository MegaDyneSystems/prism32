$ErrorActionPreference = 'Stop'

$toolsDir   = Split-Path -Parent $MyInvocation.MyCommand.Definition
$targetFile = Join-Path $toolsDir 'prism32.py'
$cmdFile    = Join-Path $toolsDir 'prism32.cmd'

# --- Check for Python 3.7+ ---
$pythonCmd = Get-Command 'python' -ErrorAction SilentlyContinue
if (-not $pythonCmd) {
    $pythonCmd = Get-Command 'python3' -ErrorAction SilentlyContinue
}

if (-not $pythonCmd) {
    throw @"
Python 3.7 or later is required to run Prism32, but it was not found in PATH.
Please install Python from https://python.org and re-run this installation.
"@
}

# Verify version (3.7+ required)
try {
    $verStr = & $pythonCmd.Source --version 2>&1
    if ($verStr -match '(\d+)\.(\d+)') {
        $major = [int]$matches[1]
        $minor = [int]$matches[2]
        if ($major -lt 3 -or ($major -eq 3 -and $minor -lt 7)) {
            throw "Python $major.$minor found, but Python 3.7+ is required."
        }
    }
} catch {
    Write-Warning "Could not verify Python version. Ensure Python 3.7+ is installed."
}

# --- Download prism32.py (commit-pinned) ---
$url = 'https://raw.githubusercontent.com/MegaDyneSystems/prism32/2152bb1c78ee31a106cab6c46be613186ebfd583/prism32.py'

$packageArgs = @{
    packageName  = $env:ChocolateyPackageName
    fileFullPath = $targetFile
    url          = $url
}

Get-ChocolateyWebFile @packageArgs

# --- Create .cmd wrapper ---
$wrapper = @'
@echo off
python "%~dp0\prism32.py" %*
'@

$wrapper | Out-File -FilePath $cmdFile -Encoding Ascii

# --- Register shim ---
Install-BinFile -Name 'prism32' -Path $cmdFile
