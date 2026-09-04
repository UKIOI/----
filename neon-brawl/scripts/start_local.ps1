param([int]$Port = 8080)
$root = Split-Path -Parent $PSScriptRoot
$env:APP_EDITION = 'local'; $env:PORT = "$Port"
Push-Location "$root/backend"
try { python -m app.main } finally { Pop-Location }
