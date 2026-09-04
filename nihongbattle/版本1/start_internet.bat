@echo off
chcp 65001 >nul
title Neon Brawl - Open Source FRP
set "FRP_DIR=%USERPROFILE%\Desktop\frp_0.35.1_windows_amd64"
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0start_internet.ps1" -FrpDirectory "%FRP_DIR%" %*
echo.
echo FRP launcher stopped. Press any key to close.
pause >nul
