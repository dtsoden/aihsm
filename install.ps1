$ErrorActionPreference = "Stop"
Write-Host "Installing Claude-Secret-Harness..."

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

$skillDir = Join-Path $HOME ".claude\skills\secret-harness"
New-Item -ItemType Directory -Force -Path $skillDir | Out-Null
Copy-Item "skills\secret-harness\SKILL.md" (Join-Path $skillDir "SKILL.md") -Force

python -m secret_harness.installer install-hook
if ($LASTEXITCODE -ne 0) { Write-Error "Hook install failed. Aborting."; exit 1 }

if (-not (Get-Command vault -ErrorAction SilentlyContinue)) {
  $scripts = (& python -c "import sysconfig; print(sysconfig.get_path('scripts','nt_user'))").Trim()
  if ($scripts -and (Test-Path $scripts)) {
    $userPath = [Environment]::GetEnvironmentVariable('Path', 'User')
    if ($null -eq $userPath) { $userPath = '' }
    if (($userPath.Split(';') | Where-Object { $_ -ne '' }) -notcontains $scripts) {
      $newPath = if ($userPath -eq '') { $scripts } else { $userPath.TrimEnd(';') + ';' + $scripts }
      [Environment]::SetEnvironmentVariable('Path', $newPath, 'User')
      Write-Host "Added the Python user scripts directory to your PATH so 'vault' works."
    }
    if (($env:Path).Split(';') -notcontains $scripts) { $env:Path += ';' + $scripts }
    Write-Host "Open a NEW terminal for 'vault' to be available (this window will not see it yet)."
  } else {
    Write-Host "Note: could not locate the scripts directory. Run vault as:  python -m secret_harness.vault"
  }
}

Write-Host "Done. Store a secret with:  vault put my-key"
