@echo off
chcp 65001 >nul
title 霓虹乱斗 - 互联网联机
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0start_internet.ps1"
echo.
echo 公网联机已经停止，按任意键关闭窗口。
pause >nul