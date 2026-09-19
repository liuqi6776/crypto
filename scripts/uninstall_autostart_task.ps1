# -*- coding: utf-8 -*-
# Uninstalls auto-start scheduled task and startup shortcut

$TaskName = "CryptoPaperDashboard"
Write-Host "Uninstalling auto-start for $TaskName..." -ForegroundColor Yellow

try {
    Unregister-ScheduledTask -TaskName $TaskName -Confirm:$false -ErrorAction SilentlyContinue
    Write-Host "Task Scheduler task removed." -ForegroundColor Green
} catch {}

$StartupFolder = [System.Environment]::GetFolderPath('Startup')
$StartupVbs = Join-Path $StartupFolder "StartCryptoDashboard.vbs"
if (Test-Path $StartupVbs) {
    Remove-Item $StartupVbs -Force
    Write-Host "Startup folder launcher removed." -ForegroundColor Green
}

Write-Host "Auto-start successfully uninstalled." -ForegroundColor Green
