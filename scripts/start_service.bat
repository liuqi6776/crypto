@echo off
rem ============================================================================
rem Auto-Start Launcher: Crypto Structural Trend & 3x Leverage Dashboard Service
rem ============================================================================
cd /d "C:\Users\liuqi\crypto"

if not exist "paper_logs" (
    mkdir "paper_logs"
)

echo ======================================================== >> "paper_logs\dashboard_service.log"
echo [SERVICE BOOT] Starting Crypto Dashboard Service at %DATE% %TIME% >> "paper_logs\dashboard_service.log"

rem Check if port 8088 is already in use, kill previous instance if hung
for /f "tokens=5" %%a in ('netstat -aon ^| findstr ":8088" ^| findstr "LISTENING"') do (
    echo [SERVICE CLEANUP] Terminating previous process PID %%a on port 8088 >> "paper_logs\dashboard_service.log"
    taskkill /F /PID %%a >nul 2>&1
)

"C:\Users\liuqi\anaconda3\python.exe" -m server.main --port 8088 --interval 900 >> "paper_logs\dashboard_service.log" 2>&1
