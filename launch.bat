@echo off
setlocal
cd /d "%~dp0"

if exist "dist\EntropyAI\EntropyAI.exe" (
    start "" "dist\EntropyAI\EntropyAI.exe" %*
) else (
    python run_entropy.py %*
)
