@echo off
rem ============================================================================
rem Service Terminator: Stops Crypto Dashboard & ngrok tunnel
rem ============================================================================
echo [SHUTDOWN] Stopping Crypto Dashboard Service on port 8088...

for /f "tokens=5" %%a in ('netstat -aon ^| findstr ":8088" ^| findstr "LISTENING"') do (
    echo Terminating Dashboard process PID %%a...
    taskkill /F /PID %%a
)

echo Terminating ngrok tunnels...
taskkill /F /IM ngrok.exe >nul 2>&1

echo [OK] Service stopped successfully.
