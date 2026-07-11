$ErrorActionPreference = "Continue"
Write-Host "Removing aihsm..."
python -m aihsm.installer uninstall-hook
Remove-Item -Recurse -Force (Join-Path $HOME ".claude\skills\aihsm") -ErrorAction SilentlyContinue
python -m pip uninstall -y aihsm
Write-Host "Hook and skill removed. Your stored secrets remain in the OS vault."
