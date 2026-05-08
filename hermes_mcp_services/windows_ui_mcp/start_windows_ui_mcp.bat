@echo off
setlocal
cd /d D:\open-source\UFO\hermes_mcp_services\windows_ui_mcp

set ZONUI3B_SERVICE_URL=http://localhost:8100

REM Use dedicated venv for MCP (do NOT pollute ZonUI-3B venv)
set VENV_DIR=D:\open-source\UFO\hermes_mcp_services\windows_ui_mcp\.venv

if not exist "%VENV_DIR%\Scripts\python.exe" (
    echo Creating dedicated venv...
    REM Find system Python
    if exist "C:\Python314\python.exe" (
        C:\Python314\python.exe -m venv "%VENV_DIR%"
    ) else (
        python -m venv "%VENV_DIR%"
    )
    if errorlevel 1 (
        echo ERROR: Failed to create venv
        pause
        exit /b 1
    )
)

set PYTHON=%VENV_DIR%\Scripts\python.exe
echo Using: %PYTHON%
echo ZONUI3B_SERVICE_URL=%ZONUI3B_SERVICE_URL%

REM Install deps if missing
%PYTHON% -c "import fastmcp" 2>nul
if errorlevel 1 (
    echo Installing dependencies...
    %PYTHON% -m pip install -r requirements.txt
    if errorlevel 1 (
        echo ERROR: pip install failed
        pause
        exit /b 1
    )
)

echo Starting Windows UI MCP Server on port 8031...
%PYTHON% server.py --port 8031 --host localhost
pause
