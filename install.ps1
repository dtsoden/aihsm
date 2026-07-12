$ErrorActionPreference = "Stop"
Write-Host "Installing aihsm..."

$python = Get-Command python -ErrorAction SilentlyContinue
if (-not $python) {
  Write-Error "Python 3 is required but was not found. Install Python 3 and re-run."
  exit 1
}

python -m pip install --user .
if ($LASTEXITCODE -ne 0) {
  Write-Error "pip install failed. If you saw an 'externally-managed-environment' error, install with pipx ('pipx install .') or inside a virtualenv instead. See the README Install section."
  exit 1
}

$skillDir = Join-Path $HOME ".claude\skills\aihsm"
New-Item -ItemType Directory -Force -Path $skillDir | Out-Null
Copy-Item "skills\aihsm\SKILL.md" (Join-Path $skillDir "SKILL.md") -Force

python -m aihsm.installer install-hook
if ($LASTEXITCODE -ne 0) { Write-Error "Hook install failed. Aborting."; exit 1 }

# Self-check: confirm the hook blocks a fake secret (runs entirely in Python so
# PowerShell quoting and error handling cannot interfere).
python -m aihsm.installer selfcheck

if (-not (Get-Command aihsm -ErrorAction SilentlyContinue)) {
  $scripts = (& python -c "import sysconfig; print(sysconfig.get_path('scripts','nt_user'))").Trim()
  if ($scripts -and (Test-Path $scripts)) {
    $userPath = [Environment]::GetEnvironmentVariable('Path', 'User')
    if ($null -eq $userPath) { $userPath = '' }
    if (($userPath.Split(';') | Where-Object { $_ -ne '' }) -notcontains $scripts) {
      $newPath = if ($userPath -eq '') { $scripts } else { $userPath.TrimEnd(';') + ';' + $scripts }
      [Environment]::SetEnvironmentVariable('Path', $newPath, 'User')
      Write-Host "Added the Python user scripts directory to your PATH so 'aihsm' works."
    }
    if (($env:Path).Split(';') -notcontains $scripts) { $env:Path += ';' + $scripts }
    Write-Host "Open a NEW terminal for 'aihsm' to be available (this window will not see it yet)."
  } else {
    Write-Host "Note: could not locate the scripts directory. Run aihsm as:  python -m aihsm.cli"
  }
}

Write-Host "Done. Store a secret with:  aihsm put my-key"
