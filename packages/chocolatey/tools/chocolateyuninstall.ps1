$ErrorActionPreference = 'Stop'

$toolsDir  = Split-Path -Parent $MyInvocation.MyCommand.Definition

# Remove the shim so the command no longer exists on PATH
Uninstall-BinFile -Name 'prism32'

# Clean up downloaded/generated files in the package tools directory
Remove-Item (Join-Path $toolsDir 'prism32.py')  -ErrorAction SilentlyContinue
Remove-Item (Join-Path $toolsDir 'prism32.cmd') -ErrorAction SilentlyContinue
