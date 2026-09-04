[CmdletBinding()]
param([string]$FrpDirectory = "")

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

function Write-Check {
    param([bool]$Success, [string]$SuccessText, [string]$FailureText)
    if ($Success) {
        Write-Host "[通过] $SuccessText" -ForegroundColor Green
    }
    else {
        Write-Host "[失败] $FailureText" -ForegroundColor Red
    }
}

function Find-FrpDirectory {
    param([string]$PreferredDirectory)
    if ($PreferredDirectory) {
        $resolved = Resolve-Path -LiteralPath $PreferredDirectory -ErrorAction SilentlyContinue
        if ($resolved -and (Test-Path -LiteralPath (Join-Path $resolved.Path "frpc.exe"))) {
            return $resolved.Path
        }
        return $null
    }

    $desktopDir = [Environment]::GetFolderPath("Desktop")
    $userProfileDir = Split-Path -Parent $desktopDir
    foreach ($candidate in @($PSScriptRoot, (Join-Path $PSScriptRoot "frp"), $desktopDir, (Join-Path $userProfileDir "Downloads"))) {
        if (Test-Path -LiteralPath (Join-Path $candidate "frpc.exe")) { return $candidate }
        if (Test-Path -LiteralPath $candidate) {
            $found = Get-ChildItem -LiteralPath $candidate -Directory -Filter "frp_*_windows_amd64" -ErrorAction SilentlyContinue |
                Where-Object { Test-Path -LiteralPath (Join-Path $_.FullName "frpc.exe") } |
                Sort-Object LastWriteTime -Descending |
                Select-Object -First 1
            if ($found) { return $found.FullName }
        }
    }
    return $null
}

function Get-FrpSetting {
    param([string]$Content, [string]$Name)
    $pattern = '(?m)^\s*' + [regex]::Escape($Name) + '\s*=\s*(.+?)\s*$'
    $match = [regex]::Match($Content, $pattern)
    if (-not $match.Success) { return $null }
    return $match.Groups[1].Value.Trim().Trim('"').Trim("'")
}

function Test-TcpEndpoint {
    param([string]$Address, [int]$Port, [int]$TimeoutMilliseconds = 3000)
    $client = [Net.Sockets.TcpClient]::new()
    try {
        $connection = $client.ConnectAsync($Address, $Port)
        return $connection.Wait($TimeoutMilliseconds) -and $client.Connected
    }
    catch { return $false }
    finally { $client.Dispose() }
}

Write-Host ""
Write-Host "霓虹乱斗 FRP 联机自检" -ForegroundColor Cyan
Write-Host "=======================" -ForegroundColor Cyan

$frpDir = Find-FrpDirectory -PreferredDirectory $FrpDirectory
Write-Check ([bool]$frpDir) "已找到 FRP：$frpDir" "没有找到解压后的官方 FRP 文件夹"
if (-not $frpDir) { exit 1 }

$frpcPath = Join-Path $frpDir "frpc.exe"
$configPath = Join-Path $frpDir "frpc.toml"
$version = (& $frpcPath -v 2>&1 | Select-Object -First 1)
Write-Check ($LASTEXITCODE -eq 0) "frpc 版本：$version" "frpc.exe 无法运行"
Write-Check (Test-Path -LiteralPath $configPath) "已找到 frpc.toml" "FRP 文件夹中缺少 frpc.toml"
if (-not (Test-Path -LiteralPath $configPath)) { exit 1 }

& $frpcPath verify -c $configPath *> $null
Write-Check ($LASTEXITCODE -eq 0) "frpc.toml 语法正确" "frpc.toml 语法错误"
if ($LASTEXITCODE -ne 0) { exit 1 }

$config = Get-Content -LiteralPath $configPath -Raw
$serverAddress = Get-FrpSetting -Content $config -Name "serverAddr"
$serverPortText = Get-FrpSetting -Content $config -Name "serverPort"
$localPortText = Get-FrpSetting -Content $config -Name "localPort"
$remotePortText = Get-FrpSetting -Content $config -Name "remotePort"
$hasTokenMethod = $config -match '(?m)^\s*auth\.method\s*=\s*["'']token["'']\s*$'
$hasTokenValue = $config -match '(?m)^\s*auth\.token\s*=\s*["''].+["'']\s*$'
Write-Check ($hasTokenMethod -and $hasTokenValue) "已配置 token（内容已隐藏）" "没有正确配置 auth.method 和 auth.token"

$settingsOk = $serverAddress -and $serverPortText -and $localPortText -and $remotePortText
Write-Check ([bool]$settingsOk) "已读取服务器及端口配置" "配置缺少 serverAddr、serverPort、localPort 或 remotePort"
if (-not $settingsOk) { exit 1 }

$serverPort = [int]$serverPortText
$localPort = [int]$localPortText
$remotePort = [int]$remotePortText
Write-Host "      云服务器：$serverAddress`:$serverPort"
Write-Host "      游戏映射：127.0.0.1:$localPort -> $serverAddress`:$remotePort"

$localHealth = $null
try { $localHealth = Invoke-RestMethod -Uri "http://127.0.0.1:$localPort/health" -TimeoutSec 2 } catch {}
$localReady = $localHealth -and $localHealth.game -eq "neon-brawl"
Write-Check ([bool]$localReady) "本地游戏服务器正在运行" "本地游戏服务器未运行；请先启动 start_internet.bat"

$controlReady = Test-TcpEndpoint -Address $serverAddress -Port $serverPort
Write-Check $controlReady "云服务器 FRP 控制端口 $serverPort 可连接" "无法连接 $serverAddress`:$serverPort；请检查 frps、安全组和系统防火墙"

$frpcRunning = [bool](Get-Process -Name "frpc" -ErrorAction SilentlyContinue)
Write-Check $frpcRunning "本机 frpc 正在运行" "本机 frpc 未运行"

$publicReady = Test-TcpEndpoint -Address $serverAddress -Port $remotePort
Write-Check $publicReady "公网游戏端口 $remotePort 可连接" "公网端口 $remotePort 未开放；只有 frps、frpc 和游戏都运行后才会通过"

$endToEndReady = $false
if ($publicReady) {
    try {
        $publicHealth = Invoke-RestMethod -Uri "http://$serverAddress`:$remotePort/health" -TimeoutSec 4
        $endToEndReady = $publicHealth.game -eq "neon-brawl" -and $publicHealth.edition -eq "internet"
    }
    catch {}
}
Write-Check $endToEndReady "完整公网链路正常：http://$serverAddress`:$remotePort" "完整公网链路尚未建立"

Write-Host ""
if ($endToEndReady) {
    Write-Host "结论：互联网联机已经可用。" -ForegroundColor Green
    Write-Host "分享网址：http://$serverAddress`:$remotePort" -ForegroundColor Green
}
elseif (-not $controlReady) {
    Write-Host "结论：问题在云服务器端。请让服务器管理员启动 frps，并放行 TCP $serverPort。" -ForegroundColor Yellow
}
elseif (-not $localReady -or -not $frpcRunning) {
    Write-Host "结论：云服务器可达，但本地游戏或 frpc 尚未启动。请运行 start_internet.bat。" -ForegroundColor Yellow
}
else {
    Write-Host "结论：请检查云服务器 TCP $remotePort 的安全组和系统防火墙。" -ForegroundColor Yellow
}
