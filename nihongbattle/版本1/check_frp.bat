@echo off
chcp 65001 >nul
title Neon Brawl - FRP Check
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0check_frp.ps1"
echo.
echo FRP check finished. Press any key to close.
pause >nul
