$ErrorActionPreference = "Continue"
$root = "C:\SCADA_MOHAMED"
$log = Join-Path $root "logs\backend.log"
New-Item -ItemType Directory -Force -Path (Split-Path $log) | Out-Null
$py = Join-Path $root "venv\Scripts\python.exe"
if (-not (Test-Path $py)) { $py = "C:\Users\mromero\AppData\Local\Programs\Python\Python311\python.exe" }
$existing = Get-NetTCPConnection -LocalPort 8000 -State Listen -ErrorAction SilentlyContinue | Select-Object -First 1
if ($existing) {
    Stop-Process -Id $existing.OwningProcess -Force -ErrorAction SilentlyContinue
    Start-Sleep -Seconds 2
}
Start-Process -FilePath $py -ArgumentList "run.py" -WorkingDirectory $root -WindowStyle Hidden -RedirectStandardOutput $log -RedirectStandardError "$log.err"
Start-Sleep -Seconds 2
Write-Output "Backend iniciado (puerto 8000). Log: $log"
