param([int]$Port = 8083)
$root = Split-Path -Parent $PSScriptRoot
$env:APP_EDITION = 'offline'; $env:HOST = '127.0.0.1'; $env:PORT = "$Port"
Push-Location "$root/backend"
try { python -m app.main } finally { Pop-Location }
