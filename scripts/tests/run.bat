@echo off
setlocal
for %%I in ("%~dp0\..\..") do set "PROJECT_ROOT=%%~fI"
cd /d "%PROJECT_ROOT%" || exit /b 1

where py >nul 2>&1
if not errorlevel 1 (
    py -3 -m unittest discover -s . -p "test_*.py" -v
) else (
    python -m unittest discover -s . -p "test_*.py" -v
)
