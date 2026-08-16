$ErrorActionPreference = "Stop"
$exe = Join-Path $PSScriptRoot "dist\FileForge.exe"

if (!(Test-Path $exe)) {
    Write-Host "EXE not found: $exe" -ForegroundColor Red
    exit 1
}

Write-Host "SHA-256:" -ForegroundColor Cyan
Get-FileHash $exe -Algorithm SHA256 | Format-List

Write-Host "`nWindows Defender:" -ForegroundColor Cyan
if (Get-Command Start-MpScan -ErrorAction SilentlyContinue) {
    Start-MpScan -ScanPath $exe -ScanType CustomScan
    Write-Host "Scan command completed. Review Windows Security for results." -ForegroundColor Green
} else {
    Write-Host "Start-MpScan is unavailable in this PowerShell session." -ForegroundColor Yellow
    Write-Host "Use Windows Security -> Virus & threat protection -> Scan options -> Custom scan."
}

Write-Host "`nThe EXE is unsigned. A trusted code-signing certificate is needed for a publisher signature." -ForegroundColor Yellow
