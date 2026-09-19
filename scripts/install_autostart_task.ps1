# -*- coding: utf-8 -*-
# PowerShell Auto-Start Installer for Crypto Paper Dashboard Service
# Configures persistent execution across computer reboots via:
# 1. Windows CurrentUser Auto-Run Registry (HKCU:\Software\Microsoft\Windows\CurrentVersion\Run)
# 2. Windows Startup Folder Redundancy (shell:startup)

$ErrorActionPreference = "Stop"

Write-Host "==================================================================" -ForegroundColor Cyan
Write-Host " INSTALLING PERSISTENT AUTO-START FOR CRYPTO DASHBOARD SERVICE   " -ForegroundColor Cyan
Write-Host "==================================================================" -ForegroundColor Cyan

$TaskName = "CryptoPaperDashboard"
$VbsPath = "C:\Users\liuqi\crypto\scripts\run_background_hidden.vbs"
$BatPath = "C:\Users\liuqi\crypto\scripts\start_service.bat"

# Verify files exist
if (-not (Test-Path $VbsPath) -or -not (Test-Path $BatPath)) {
    Write-Error "Required script files not found at $VbsPath or $BatPath!"
    exit 1
}

# 1. Register in Windows CurrentUser Run Key
Write-Host "`n[1/3] Configuring Windows User Auto-Run Registry Key..." -ForegroundColor Yellow
$RunKey = "HKCU:\Software\Microsoft\Windows\CurrentVersion\Run"
$RunCmd = "wscript.exe `"$VbsPath`""
Set-ItemProperty -Path $RunKey -Name $TaskName -Value $RunCmd
Write-Host "  -> Registry auto-start configured successfully!" -ForegroundColor Green

# 2. Configure Dual-Redundancy Startup Folder
Write-Host "`n[2/3] Configuring secondary redundancy in Windows Startup Folder..." -ForegroundColor Yellow
$StartupFolder = [System.Environment]::GetFolderPath('Startup')
$StartupVbs = Join-Path $StartupFolder "StartCryptoDashboard.vbs"

$VbsContent = @"
' Windows Startup Redundancy for Crypto Dashboard
Set WshShell = CreateObject("WScript.Shell")
WshShell.CurrentDirectory = "C:\Users\liuqi\crypto"
WshShell.Run "cmd.exe /c ""C:\Users\liuqi\crypto\scripts\start_service.bat""", 0, False
Set WshShell = Nothing
"@

Set-Content -Path $StartupVbs -Value $VbsContent -Encoding UTF8
Write-Host "  -> Startup folder launcher created at: $StartupVbs" -ForegroundColor Green

# 3. Start the service now
Write-Host "`n[3/3] Launching background dashboard service..." -ForegroundColor Yellow
Start-Process -FilePath "wscript.exe" -ArgumentList "`"$VbsPath`""

# Wait for service initialization
Start-Sleep -Seconds 5

# Verify health
Write-Host "`n[HEALTH CHECK] Verifying service connectivity..." -ForegroundColor Cyan
$PortListening = $false
for ($i = 0; $i -lt 15; $i++) {
    $conn = Get-NetTCPConnection -LocalPort 8088 -State Listen -ErrorAction SilentlyContinue
    if ($conn) {
        $PortListening = $true
        break
    }
    Start-Sleep -Seconds 1
}

if ($PortListening) {
    Write-Host "  -> Port 8088 is ACTIVE and LISTENING!" -ForegroundColor Green
    try {
        $resp = Invoke-RestMethod -Uri "http://127.0.0.1:8088/api/status" -TimeoutSec 5
        Write-Host "  -> API Status Response: OK! Mode: $($resp.active_mode) | PnL: $($resp.capital.pnl_pct)%" -ForegroundColor Green
        Write-Host "  -> Public Tunnel URL:   $($resp.public_url)" -ForegroundColor Yellow
    } catch {
        Write-Host "  -> API connection warming up..." -ForegroundColor Yellow
    }
} else {
    Write-Host "  -> Port 8088 not detected yet. Check paper_logs\dashboard_service.log for details." -ForegroundColor Yellow
}

Write-Host "`n==================================================================" -ForegroundColor Cyan
Write-Host " AUTO-START INSTALLATION COMPLETE!                                " -ForegroundColor Cyan
Write-Host " Public URL : https://percolate-zipfile-corned.ngrok-free.dev    " -ForegroundColor Green
Write-Host " Local URL  : http://127.0.0.1:8088                               " -ForegroundColor Green
Write-Host " Status     : Configured to auto-start on every computer reboot.  " -ForegroundColor Green
Write-Host "==================================================================" -ForegroundColor Cyan
