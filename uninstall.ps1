$ErrorActionPreference = "Continue"
Write-Host "Removing Claude-Secret-Harness..."
python -m secret_harness.installer uninstall-hook
Remove-Item -Recurse -Force (Join-Path $HOME ".claude\skills\secret-harness") -ErrorAction SilentlyContinue
python -m pip uninstall -y claude-secret-harness
Write-Host "Hook and skill removed. Your stored secrets remain in the OS vault."
