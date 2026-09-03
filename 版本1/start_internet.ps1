[CmdletBinding()]
param(
    [ValidateRange(1024, 65535)]
    [int]$Port = 8080
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"
$ProgressPreference = "SilentlyContinue"

$projectDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$toolsDir = Join-Path $projectDir ".tools"
$runtimeDir = Join-Path $projectDir ".runtime"
$serverProcess = $null
$tunnelProcess = $null
$ownsServer = $false
$expectedProtocol = 9
$instanceLock = [Threading.Mutex]::new($false, "Local\NeonBrawlInternet$Port")
$lockTaken = $false

function Get-GameHealth {
    param([int]$GamePort)
    try {
        return Invoke-RestMethod -Uri "http://127.0.0.1:$GamePort/health" -TimeoutSec 2
    }
    catch {
        return $null
    }
}

function Test-GameServer {
    param([int]$GamePort)
    $result = Get-GameHealth -GamePort $GamePort
    return $result -and $result.game -eq "neon-brawl" -and $result.protocol -eq $expectedProtocol
}

function Get-Cloudflared {
    $installed = Get-Command cloudflared -ErrorAction SilentlyContinue
    if ($installed) {
        return $installed.Source
    }

    New-Item -ItemType Directory -Force -Path $toolsDir | Out-Null
    $executable = Join-Path $toolsDir "cloudflared.exe"
    if (Test-Path -LiteralPath $executable) {
        return $executable
    }

    $architecture = [Runtime.InteropServices.RuntimeInformation]::OSArchitecture.ToString()
    if ($architecture -eq "Arm64") {
        $asset = "cloudflared-windows-arm64.exe"
    }
    elseif ($architecture -eq "X64") {
        $asset = "cloudflared-windows-amd64.exe"
    }
    else {
        throw "暂不支持此 Windows 架构：$architecture"
    }

    $download = "https://github.com/cloudflare/cloudflared/releases/latest/download/$asset"
    $partial = "$executable.download"
    Write-Host "首次运行，正在下载公网隧道组件……" -ForegroundColor Cyan
    Invoke-WebRequest -Uri $download -OutFile $partial -UseBasicParsing
    Move-Item -LiteralPath $partial -Destination $executable -Force
    return $executable
}

try {
    try { $lockTaken = $instanceLock.WaitOne(0) } catch [Threading.AbandonedMutexException] { $lockTaken = $true }
    if (-not $lockTaken) {
        throw "端口 $Port 的互联网版启动器已经运行，请使用现有窗口或选择其他端口。"
    }
    New-Item -ItemType Directory -Force -Path $runtimeDir | Out-Null

    $existingHealth = Get-GameHealth -GamePort $Port
    if ($existingHealth -and $existingHealth.game -eq "neon-brawl" -and $existingHealth.protocol -ne $expectedProtocol) {
        $listener = Get-NetTCPConnection -State Listen -LocalPort $Port -ErrorAction SilentlyContinue | Select-Object -First 1
        if (-not $listener) { throw "检测到旧版游戏服务器，但无法确定对应进程，请关闭旧服务器窗口后重试。" }
        Write-Host "检测到协议 $($existingHealth.protocol) 的旧游戏服务器，正在自动升级……" -ForegroundColor Yellow
        Stop-Process -Id $listener.OwningProcess -Force -ErrorAction Stop
        Start-Sleep -Milliseconds 500
        if (Get-NetTCPConnection -State Listen -LocalPort $Port -ErrorAction SilentlyContinue) {
            throw "旧游戏服务器无法自动关闭，请关闭旧窗口后重试。"
        }
    }

    if (-not (Test-GameServer -GamePort $Port)) {
        $python = Get-Command python -ErrorAction SilentlyContinue
        if (-not $python) {
            throw "没有找到 Python。请先安装 Python 3，然后重新运行本脚本。"
        }

        & $python.Source -c "import aiohttp" 2>$null
        if ($LASTEXITCODE -ne 0) {
            Write-Host "正在安装游戏服务器依赖……" -ForegroundColor Cyan
            & $python.Source -m pip install -r (Join-Path $projectDir "requirements.txt")
            if ($LASTEXITCODE -ne 0) {
                throw "依赖安装失败。"
            }
        }

        $oldPort = $env:PORT
        $env:PORT = "$Port"
        try {
            $serverProcess = Start-Process -FilePath $python.Source `
                -ArgumentList @("-u", "server.py") `
                -WorkingDirectory $projectDir `
                -WindowStyle Hidden `
                -RedirectStandardOutput (Join-Path $runtimeDir "server-$Port-out.log") `
                -RedirectStandardError (Join-Path $runtimeDir "server-$Port-error.log") `
                -PassThru
            $ownsServer = $true
        }
        finally {
            $env:PORT = $oldPort
        }

        $deadline = (Get-Date).AddSeconds(20)
        while ((Get-Date) -lt $deadline -and -not (Test-GameServer -GamePort $Port)) {
            if ($serverProcess.HasExited) {
                $details = Get-Content -LiteralPath (Join-Path $runtimeDir "server-$Port-error.log") -Raw -ErrorAction SilentlyContinue
                throw "游戏服务器启动失败。`n$details"
            }
            Start-Sleep -Milliseconds 300
        }
        if (-not (Test-GameServer -GamePort $Port)) {
            throw "游戏服务器启动超时，请检查端口 $Port 是否被其他程序占用。"
        }
    }
    else {
        Write-Host "检测到游戏服务器已经在端口 $Port 运行。" -ForegroundColor Green
    }

    $cloudflared = Get-Cloudflared
    $tunnelOut = Join-Path $runtimeDir "tunnel-$Port-out.log"
    $tunnelError = Join-Path $runtimeDir "tunnel-$Port-error.log"
    $tunnelProcess = Start-Process -FilePath $cloudflared `
        -ArgumentList @("tunnel", "--no-autoupdate", "--protocol", "auto", "--url", "http://127.0.0.1:$Port") `
        -WorkingDirectory $projectDir `
        -WindowStyle Hidden `
        -RedirectStandardOutput $tunnelOut `
        -RedirectStandardError $tunnelError `
        -PassThru

    Write-Host "正在建立互联网连接……" -ForegroundColor Cyan
    $publicUrl = $null
    $deadline = (Get-Date).AddSeconds(45)
    while ((Get-Date) -lt $deadline -and -not $publicUrl) {
        if ($tunnelProcess.HasExited) {
            $details = Get-Content -LiteralPath $tunnelError -Raw -ErrorAction SilentlyContinue
            throw "公网隧道启动失败。`n$details"
        }
        $logs = Get-Content -LiteralPath $tunnelError -Raw -ErrorAction SilentlyContinue
        if ($logs -match "https://[a-z0-9-]+\.trycloudflare\.com") {
            $publicUrl = $Matches[0]
            break
        }
        Start-Sleep -Milliseconds 500
    }

    if (-not $publicUrl) {
        throw "等待公网网址超时。请检查网络后重试。"
    }

    Write-Host ""
    Write-Host "互联网联机已经开启！" -ForegroundColor Green
    Write-Host "分享网址：$publicUrl" -ForegroundColor Yellow
    Write-Host "电脑和手机打开这个网址，再输入相同房间号即可联机。"
    Write-Host "请保持本窗口开启；按 Ctrl+C 可停止公网联机。"
    Write-Host ""

    while (-not $tunnelProcess.HasExited) {
        Start-Sleep -Seconds 1
    }
}
finally {
    if ($tunnelProcess -and -not $tunnelProcess.HasExited) {
        Stop-Process -Id $tunnelProcess.Id -ErrorAction SilentlyContinue
    }
    if ($ownsServer -and $serverProcess -and -not $serverProcess.HasExited) {
        Stop-Process -Id $serverProcess.Id -ErrorAction SilentlyContinue
    }
    if ($lockTaken) {
        try { $instanceLock.ReleaseMutex() } catch {}
    }
    $instanceLock.Dispose()
}
