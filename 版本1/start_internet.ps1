[CmdletBinding()]
param(
    [ValidateRange(1024, 65535)]
    [int]$Port = 8080,
    [string]$FrpDirectory = "",
    [switch]$NoBrowser
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"
$ProgressPreference = "SilentlyContinue"

$projectDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$runtimeDir = Join-Path $projectDir ".runtime"
$serverStdout = Join-Path $runtimeDir "server-$Port-out.log"
$serverProcess = $null
$frpcProcess = $null
$ownsServer = $false
$ownsFrpc = $false
$expectedProtocol = 16
$expectedBuild = 72
$instanceLock = [Threading.Mutex]::new($false, "Local\NeonBrawlFrp$Port")
$lockTaken = $false

function Find-FrpDirectory {
    param([string]$PreferredDirectory)

    if ($PreferredDirectory) {
        $resolved = Resolve-Path -LiteralPath $PreferredDirectory -ErrorAction SilentlyContinue
        if ($resolved -and (Test-Path -LiteralPath (Join-Path $resolved.Path "frpc.exe"))) {
            return $resolved.Path
        }
        throw "指定的 FRP 目录无效或缺少 frpc.exe：$PreferredDirectory"
    }

    $desktopDir = [Environment]::GetFolderPath("Desktop")
    $userProfileDir = Split-Path -Parent $desktopDir
    $candidates = @(
        (Join-Path $projectDir "frp")
        $desktopDir
        (Join-Path $userProfileDir "Downloads")
    )
    foreach ($candidate in $candidates) {
        if (Test-Path -LiteralPath (Join-Path $candidate "frpc.exe")) {
            return $candidate
        }
        if (Test-Path -LiteralPath $candidate) {
            $found = Get-ChildItem -LiteralPath $candidate -Directory -Filter "frp_*_windows_amd64" -ErrorAction SilentlyContinue |
                Where-Object { Test-Path -LiteralPath (Join-Path $_.FullName "frpc.exe") } |
                Sort-Object LastWriteTime -Descending |
                Select-Object -First 1
            if ($found) { return $found.FullName }
        }
    }
    throw "没有找到官方 frpc.exe。请保留解压后的 frp_*_windows_amd64 文件夹，或使用 -FrpDirectory 指定其路径。"
}

function Get-FrpSetting {
    param(
        [string]$Content,
        [string]$Name
    )
    $pattern = '(?m)^\s*' + [regex]::Escape($Name) + '\s*=\s*(.+?)\s*$'
    $match = [regex]::Match($Content, $pattern)
    if (-not $match.Success) { return $null }
    return $match.Groups[1].Value.Trim().Trim('"').Trim("'")
}

function Test-TcpEndpoint {
    param(
        [string]$Address,
        [int]$EndpointPort,
        [int]$TimeoutMilliseconds = 3000
    )
    $client = [Net.Sockets.TcpClient]::new()
    try {
        $connection = $client.ConnectAsync($Address, $EndpointPort)
        return $connection.Wait($TimeoutMilliseconds) -and $client.Connected
    }
    catch { return $false }
    finally { $client.Dispose() }
}

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
    $hasBuild = $result -and ($result.PSObject.Properties.Name -contains "build")
    return $result -and $result.game -eq "neon-brawl" -and $result.edition -eq "internet" -and $result.protocol -eq $expectedProtocol -and $hasBuild -and $result.build -eq $expectedBuild
}

function Install-GameDependencies {
    param([string]$PythonPath)
    $previousErrorActionPreference = $ErrorActionPreference
    $ready = $false
    try {
        $ErrorActionPreference = "Continue"
        & $PythonPath -c "import aiohttp" *> $null
        $ready = $LASTEXITCODE -eq 0
        if (-not $ready) {
            Write-Host "首次运行，正在安装游戏服务器依赖，请稍候……" -ForegroundColor Cyan
            & $PythonPath -m pip install --disable-pip-version-check -r (Join-Path $projectDir "requirements.txt")
            $ready = $LASTEXITCODE -eq 0
        }
    }
    finally {
        $ErrorActionPreference = $previousErrorActionPreference
    }
    if (-not $ready) {
        throw "游戏依赖安装失败。请确认电脑可以访问互联网，然后重新运行。"
    }
}

try {
    try { $lockTaken = $instanceLock.WaitOne(0) } catch [Threading.AbandonedMutexException] { $lockTaken = $true }
    if (-not $lockTaken) {
        throw "端口 $Port 的 FRP 联机启动器已经运行，请使用现有窗口。"
    }
    New-Item -ItemType Directory -Force -Path $runtimeDir | Out-Null

    $resolvedFrpDirectory = Find-FrpDirectory -PreferredDirectory $FrpDirectory
    $frpcPath = Join-Path $resolvedFrpDirectory "frpc.exe"
    $tomlConfig = Join-Path $resolvedFrpDirectory "frpc.toml"
    $iniConfig = Join-Path $resolvedFrpDirectory "frpc.ini"
    if (Test-Path -LiteralPath $tomlConfig) {
        $frpcConfig = $tomlConfig
        & $frpcPath verify -c $frpcConfig *> $null
        if ($LASTEXITCODE -ne 0) { throw "frpc.toml 配置校验失败，请检查：$frpcConfig" }
    }
    elseif (Test-Path -LiteralPath $iniConfig) {
        $frpcConfig = $iniConfig
    }
    else {
        throw "FRP 目录中缺少 frpc.toml 或 frpc.ini：$resolvedFrpDirectory"
    }

    $frpcConfigText = Get-Content -LiteralPath $frpcConfig -Raw
    if ([IO.Path]::GetExtension($frpcConfig) -eq ".ini") {
        $frpServerAddress = Get-FrpSetting -Content $frpcConfigText -Name "server_addr"
        $frpServerPortText = Get-FrpSetting -Content $frpcConfigText -Name "server_port"
        $frpLocalPortText = Get-FrpSetting -Content $frpcConfigText -Name "local_port"
        $frpRemotePortText = Get-FrpSetting -Content $frpcConfigText -Name "remote_port"
    }
    else {
        $frpServerAddress = Get-FrpSetting -Content $frpcConfigText -Name "serverAddr"
        $frpServerPortText = Get-FrpSetting -Content $frpcConfigText -Name "serverPort"
        $frpLocalPortText = Get-FrpSetting -Content $frpcConfigText -Name "localPort"
        $frpRemotePortText = Get-FrpSetting -Content $frpcConfigText -Name "remotePort"
    }
    if (-not $frpServerAddress -or -not $frpServerPortText -or -not $frpLocalPortText -or -not $frpRemotePortText) {
        throw "FRP 配置缺少服务端地址、服务端端口、本地端口或公网端口。"
    }
    $frpServerPort = [int]$frpServerPortText
    $frpLocalPort = [int]$frpLocalPortText
    $frpRemotePort = [int]$frpRemotePortText
    if ($frpLocalPort -ne $Port) {
        throw "端口不一致：游戏使用 $Port，但 FRP 配置的本地端口是 $frpLocalPort。请把两者改成相同值。"
    }
    if (-not (Test-TcpEndpoint -Address $frpServerAddress -EndpointPort $frpServerPort)) {
        throw "无法连接 FRP 服务端 $frpServerAddress`:$frpServerPort。请先在云服务器启动 frps，并在安全组和系统防火墙放行 TCP $frpServerPort。"
    }

    $existingHealth = Get-GameHealth -GamePort $Port
    if ($existingHealth -and $existingHealth.game -eq "neon-brawl" -and $existingHealth.edition -ne "internet") {
        throw "端口 $Port 正由其他霓虹乱斗版本使用，请改用其他端口，例如：.\start_internet.ps1 -Port 8082"
    }
    $existingHasBuild = $existingHealth -and ($existingHealth.PSObject.Properties.Name -contains "build")
    $serverOutdated = $existingHealth -and $existingHealth.game -eq "neon-brawl" -and $existingHealth.edition -eq "internet" -and (
        $existingHealth.protocol -ne $expectedProtocol -or -not $existingHasBuild -or $existingHealth.build -ne $expectedBuild
    )
    if ($serverOutdated) {
        $listener = Get-NetTCPConnection -State Listen -LocalPort $Port -ErrorAction SilentlyContinue | Select-Object -First 1
        if (-not $listener) { throw "检测到旧版游戏服务器，请关闭旧服务器窗口后重试。" }
        $currentBuild = if ($existingHasBuild) { $existingHealth.build } else { "未知" }
        Write-Host "检测到旧游戏服务器（构建 $currentBuild），正在自动升级到构建 $expectedBuild……" -ForegroundColor Yellow
        Stop-Process -Id $listener.OwningProcess -Force -ErrorAction Stop
        Start-Sleep -Milliseconds 500
    }

    if (-not (Test-GameServer -GamePort $Port)) {
        $python = Get-Command python -ErrorAction SilentlyContinue
        if (-not $python) { throw "没有找到 Python，请先安装 Python 3。" }
        Install-GameDependencies -PythonPath $python.Source

        $oldPort = $env:PORT
        $env:PORT = "$Port"
        try {
            $serverProcess = Start-Process -FilePath $python.Source `
                -ArgumentList @("-u", "server.py") `
                -WorkingDirectory $projectDir `
                -WindowStyle Hidden `
                -RedirectStandardOutput $serverStdout `
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
        if (-not (Test-GameServer -GamePort $Port)) { throw "游戏服务器启动超时。" }
    }

    $stamp = Get-Date -Format "yyyyMMdd-HHmmss"
    $frpcStdout = Join-Path $runtimeDir "frpc-$stamp-out.log"
    $frpcStderr = Join-Path $runtimeDir "frpc-$stamp-error.log"
    $frpcProcess = Start-Process -FilePath $frpcPath `
        -ArgumentList @("-c", $frpcConfig) `
        -WorkingDirectory $resolvedFrpDirectory `
        -WindowStyle Hidden `
        -RedirectStandardOutput $frpcStdout `
        -RedirectStandardError $frpcStderr `
        -PassThru
    $ownsFrpc = $true

    $frpcDeadline = (Get-Date).AddSeconds(15)
    $frpcReady = $false
    while ((Get-Date) -lt $frpcDeadline -and -not $frpcProcess.HasExited) {
        $frpcLog = ((Get-Content -LiteralPath $frpcStdout -Raw -ErrorAction SilentlyContinue) + "`n" +
            (Get-Content -LiteralPath $frpcStderr -Raw -ErrorAction SilentlyContinue))
        if ($frpcLog -match "start proxy success") { $frpcReady = $true; break }
        Start-Sleep -Milliseconds 250
    }
    if (-not $frpcReady) {
        $frpcLog = ((Get-Content -LiteralPath $frpcStdout -Raw -ErrorAction SilentlyContinue) + "`n" +
            (Get-Content -LiteralPath $frpcStderr -Raw -ErrorAction SilentlyContinue)).Trim()
        if (-not $frpcLog) { $frpcLog = "frpc 没有返回详细日志。" }
        throw "FRP 隧道启动失败。`n$frpcLog"
    }

    $shareUrl = "http://$frpServerAddress`:$frpRemotePort"
    Write-Host ""
    Write-Host "霓虹乱斗互联网版与开源 FRP 均已启动" -ForegroundColor Green
    Write-Host "分享网址：$shareUrl" -ForegroundColor Green
    Write-Host "FRP 客户端：$frpcPath"
    Write-Host "FRP 配置：$frpcConfig"
    Write-Host "本机测试地址：http://localhost:$Port"
    Write-Host "保持此窗口运行；按 Ctrl+C 会同时停止游戏服务器和 frpc。"
    Write-Host "房间人数变化会实时显示在此窗口。" -ForegroundColor Cyan
    Write-Host "Cloudflare 备用入口：start_cloudflare.bat"
    Write-Host ""

    if (-not $NoBrowser) { Start-Process "http://localhost:$Port" }
    $lastRoomStatus = ""
    while ((Test-GameServer -GamePort $Port) -and -not $frpcProcess.HasExited) {
        $latestRoomStatus = Get-Content -LiteralPath $serverStdout -Tail 40 -ErrorAction SilentlyContinue |
            Where-Object { $_.StartsWith("[房间人数]") } | Select-Object -Last 1
        if ($latestRoomStatus -and $latestRoomStatus -ne $lastRoomStatus) {
            Write-Host $latestRoomStatus -ForegroundColor Cyan
            $lastRoomStatus = $latestRoomStatus
        }
        Start-Sleep -Seconds 1
    }
    if ($frpcProcess.HasExited) {
        $frpcLog = ((Get-Content -LiteralPath $frpcStdout -Raw -ErrorAction SilentlyContinue) + "`n" +
            (Get-Content -LiteralPath $frpcStderr -Raw -ErrorAction SilentlyContinue)).Trim()
        throw "frpc 意外停止。`n$frpcLog"
    }
}
catch {
    Write-Host ""
    Write-Host $_.Exception.Message -ForegroundColor Red
    $global:LASTEXITCODE = 1
}
finally {
    if ($ownsFrpc -and $frpcProcess -and -not $frpcProcess.HasExited) {
        Stop-Process -Id $frpcProcess.Id -ErrorAction SilentlyContinue
    }
    if ($ownsServer -and $serverProcess -and -not $serverProcess.HasExited) {
        Stop-Process -Id $serverProcess.Id -ErrorAction SilentlyContinue
    }
    if ($lockTaken) {
        try { $instanceLock.ReleaseMutex() } catch {}
    }
    $instanceLock.Dispose()
}
