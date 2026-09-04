$ErrorActionPreference = "Continue"
$root = "C:\SCADA_MOHAMED"
$front = Join-Path $root "frontend"
$log = Join-Path $root "logs\frontend.log"
New-Item -ItemType Directory -Force -Path (Split-Path $log) | Out-Null
$existing = Get-NetTCPConnection -LocalPort 5173 -State Listen -ErrorAction SilentlyContinue | Select-Object -First 1
if ($existing) {
    Stop-Process -Id $existing.OwningProcess -Force -ErrorAction SilentlyContinue
    Start-Sleep -Seconds 2
}
Start-Process -FilePath "npm.cmd" -ArgumentList "run","dev" -WorkingDirectory $front -WindowStyle Hidden -RedirectStandardOutput $log -RedirectStandardError "$log.err"
Start-Sleep -Seconds 2
Write-Output "Frontend iniciado (puerto 5173). Log: $log"
