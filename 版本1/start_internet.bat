@echo off
@title Neon Brawl - Internet Multiplayer
@call "%SystemRoot%\System32\WindowsPowerShell\v1.0\powershell.exe" -NoProfile -ExecutionPolicy Bypass -File "%~dp0start_internet.ps1" %*
@echo.
@echo Internet multiplayer stopped. Press any key to close.
@pause >nul
