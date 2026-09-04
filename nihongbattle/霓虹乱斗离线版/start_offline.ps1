[CmdletBinding()]
param(
    [ValidateRange(1024, 65535)]
    [int]$Port = 8083,
    [switch]$NoBrowser
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"
$projectDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$runtimeDir = Join-Path $projectDir ".runtime"
$serverProcess = $null
$expectedProtocol = 11

$python = Get-Command python -ErrorAction SilentlyContinue
if (-not $python) {
    throw "没有找到 Python，请先安装 Python 3。"
}

$previousErrorActionPreference = $ErrorActionPreference
$dependencyReady = $false
try {
    # 新电脑第一次运行时，模块不存在会向 stderr 写入信息；这里将它作为检测结果处理，不能让 PowerShell 提前退出。
    $ErrorActionPreference = "Continue"
    & $python.Source -c "import aiohttp" *> $null
    $dependencyReady = $LASTEXITCODE -eq 0
    if (-not $dependencyReady) {
        Write-Host "首次运行，正在安装游戏依赖，请稍候……" -ForegroundColor Cyan
        & $python.Source -m pip install --disable-pip-version-check -r (Join-Path $projectDir "requirements.txt")
        $dependencyReady = $LASTEXITCODE -eq 0
    }
}
finally {
    $ErrorActionPreference = $previousErrorActionPreference
}
if (-not $dependencyReady) {
    throw "游戏依赖安装失败。请确认电脑可以访问互联网，然后重新双击启动文件。"
}

try {
    $inUse = Get-NetTCPConnection -State Listen -LocalPort $Port -ErrorAction SilentlyContinue
    if ($inUse) {
        try {
            $health = Invoke-RestMethod -Uri "http://127.0.0.1:$Port/health" -TimeoutSec 2
        }
        catch {
            throw "端口 $Port 已被其他程序占用，请关闭对应程序后重试。"
        }
        if ($health.game -eq "neon-brawl" -and $health.edition -eq "offline" -and $health.protocol -eq $expectedProtocol) {
            Write-Host "离线版已经在运行，不需要重复启动。" -ForegroundColor Green
            Write-Host "这台电脑打开：http://localhost:$Port" -ForegroundColor Yellow
            exit 0
        }
        elseif ($health.game -eq "neon-brawl" -and $health.edition -eq "offline") {
            $oldProcessId = ($inUse | Select-Object -First 1).OwningProcess
            Write-Host "检测到协议 $($health.protocol) 的旧离线服务器，正在自动升级……" -ForegroundColor Yellow
            Stop-Process -Id $oldProcessId -Force -ErrorAction Stop
            Start-Sleep -Milliseconds 500
            if (Get-NetTCPConnection -State Listen -LocalPort $Port -ErrorAction SilentlyContinue) {
                throw "旧离线服务器无法自动关闭，请关闭旧窗口后重试。"
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
            throw "离线服务器启动失败。`n$details"
        }
        try { $health = Invoke-RestMethod -Uri "http://127.0.0.1:$Port/health" -TimeoutSec 2 } catch {}
        if (-not $health) { Start-Sleep -Milliseconds 300 }
    }
    if (-not $health) { throw "离线服务器启动超时。" }
    if ($health.edition -ne "offline" -or $health.protocol -ne $expectedProtocol) {
        throw "启动到了错误的游戏版本，请关闭占用端口 $Port 的程序后重试。"
    }

    Write-Host ""
    Write-Host "霓虹乱斗离线版已经启动" -ForegroundColor Green
    Write-Host "这台电脑打开：http://localhost:$Port" -ForegroundColor Yellow
    Write-Host "此版本只允许本机访问，不会开放局域网或互联网连接。"
    Write-Host "可以在同一台电脑打开多个浏览器窗口，并输入相同房间号。"
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
