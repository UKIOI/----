[CmdletBinding()]
param(
    [ValidateRange(1024, 65535)]
    [int]$Port = 8081,
    [switch]$NoBrowser
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"
$projectDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$runtimeDir = Join-Path $projectDir ".runtime"
$serverProcess = $null
$expectedProtocol = 10

function Get-LanAddress {
    try {
        $configuration = Get-NetIPConfiguration -ErrorAction Stop |
            Where-Object { $_.IPv4DefaultGateway -and $_.NetAdapter.Status -eq "Up" } |
            Select-Object -First 1
        if ($configuration -and $configuration.IPv4Address) {
            return $configuration.IPv4Address.IPAddress
        }
    }
    catch {}

    return [System.Net.Dns]::GetHostAddresses($env:COMPUTERNAME) |
        Where-Object { $_.AddressFamily -eq [System.Net.Sockets.AddressFamily]::InterNetwork -and -not $_.IPAddressToString.StartsWith("127.") } |
        Select-Object -First 1 -ExpandProperty IPAddressToString
}

$python = Get-Command python -ErrorAction SilentlyContinue
if (-not $python) {
    throw "没有找到 Python，请先安装 Python 3。"
}

& $python.Source -c "import aiohttp" 2>$null
if ($LASTEXITCODE -ne 0) {
    Write-Host "正在安装游戏依赖……" -ForegroundColor Cyan
    & $python.Source -m pip install -r (Join-Path $projectDir "requirements.txt")
    if ($LASTEXITCODE -ne 0) { throw "依赖安装失败。" }
}

$lanAddress = Get-LanAddress

try {
    $inUse = Get-NetTCPConnection -State Listen -LocalPort $Port -ErrorAction SilentlyContinue
    if ($inUse) {
        try {
            $health = Invoke-RestMethod -Uri "http://127.0.0.1:$Port/health" -TimeoutSec 2
        }
        catch {
            throw "端口 $Port 已被其他程序占用，请关闭对应程序后重试。"
        }
        if ($health.game -eq "neon-brawl" -and $health.edition -eq "local" -and $health.protocol -eq $expectedProtocol) {
            Write-Host "本地版已经在运行，不需要重复启动。" -ForegroundColor Green
            Write-Host "这台电脑打开：http://localhost:$Port" -ForegroundColor Yellow
            if ($lanAddress) { Write-Host "同一 Wi-Fi 玩家打开：http://${lanAddress}:$Port" -ForegroundColor Yellow }
            exit 0
        }
        elseif ($health.game -eq "neon-brawl" -and $health.edition -eq "local") {
            $oldProcessId = ($inUse | Select-Object -First 1).OwningProcess
            Write-Host "检测到协议 $($health.protocol) 的旧本地服务器，正在自动升级……" -ForegroundColor Yellow
            Stop-Process -Id $oldProcessId -Force -ErrorAction Stop
            Start-Sleep -Milliseconds 500
            if (Get-NetTCPConnection -State Listen -LocalPort $Port -ErrorAction SilentlyContinue) {
                throw "旧本地服务器无法自动关闭，请关闭旧窗口后重试。"
            }
        }
        else {
            throw "端口 $Port 已被其他程序占用，请关闭对应程序后重试。"
        }
    }

    New-Item -ItemType Directory -Force -Path $runtimeDir | Out-Null
    $oldPort = $env:PORT
    $env:PORT = "$Port"
    try {
        $serverProcess = Start-Process -FilePath $python.Source `
            -ArgumentList @("-u", "server.py") `
            -WorkingDirectory $projectDir `
            -WindowStyle Hidden `
            -RedirectStandardOutput (Join-Path $runtimeDir "server-out.log") `
            -RedirectStandardError (Join-Path $runtimeDir "server-error.log") `
            -PassThru
    }
    finally {
        $env:PORT = $oldPort
    }

    $deadline = (Get-Date).AddSeconds(20)
    $health = $null
    while ((Get-Date) -lt $deadline -and -not $health) {
        if ($serverProcess.HasExited) {
            $details = Get-Content -LiteralPath (Join-Path $runtimeDir "server-error.log") -Raw -ErrorAction SilentlyContinue
            throw "本地服务器启动失败。`n$details"
        }
        try { $health = Invoke-RestMethod -Uri "http://127.0.0.1:$Port/health" -TimeoutSec 2 } catch {}
        if (-not $health) { Start-Sleep -Milliseconds 300 }
    }
    if (-not $health) { throw "本地服务器启动超时。" }

    Write-Host ""
    Write-Host "本地版服务器已经启动" -ForegroundColor Green
    Write-Host "这台电脑打开：http://localhost:$Port" -ForegroundColor Yellow
    if ($lanAddress) {
        Write-Host "同一 Wi-Fi 玩家打开：http://${lanAddress}:$Port" -ForegroundColor Yellow
    }
    else {
        Write-Host "未能自动识别局域网 IP，请在终端运行 ipconfig 查看 IPv4 地址。" -ForegroundColor Yellow
    }
    Write-Host "所有玩家输入相同房间号即可联机。"
    Write-Host "如果 Windows 防火墙询问，请勾选“专用网络”并允许访问。"
    Write-Host "游戏期间请保持本窗口开启，按 Ctrl+C 停止。"
    Write-Host ""

    if (-not $NoBrowser) { Start-Process "http://localhost:$Port" }
    while (-not $serverProcess.HasExited) {
        Start-Sleep -Seconds 1
    }
}
finally {
    if ($serverProcess -and -not $serverProcess.HasExited) {
        Stop-Process -Id $serverProcess.Id -ErrorAction SilentlyContinue
    }
}
