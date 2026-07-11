$ErrorActionPreference = "Stop"
Write-Host "Installing Claude-Secret-Harness..."

$python = Get-Command python -ErrorAction SilentlyContinue
if (-not $python) {
  Write-Error "Python 3 is required but was not found. Install Python 3 and re-run."
  exit 1
}

python -m pip install --user .
if ($LASTEXITCODE -ne 0) { Write-Error "pip install failed. Aborting."; exit 1 }

$skillDir = Join-Path $HOME ".claude\skills\secret-harness"
New-Item -ItemType Directory -Force -Path $skillDir | Out-Null
Copy-Item "skills\secret-harness\SKILL.md" (Join-Path $skillDir "SKILL.md") -Force

python -m secret_harness.installer install-hook
if ($LASTEXITCODE -ne 0) { Write-Error "Hook install failed. Aborting."; exit 1 }

Write-Host "Done. Store a secret with:  vault put my-key"
