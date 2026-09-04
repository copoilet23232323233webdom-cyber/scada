# Arranca el backend (FastAPI/uvicorn) y verifica que responde antes de salir.
# Sale con codigo != 0 si el backend no llega a escuchar en el puerto.
$ErrorActionPreference = "Stop"

$root = Split-Path -Parent $PSScriptRoot
$port = if ($env:WEBDOM_BACKEND_PORT) { [int]$env:WEBDOM_BACKEND_PORT } else { 8000 }
$log = Join-Path $root "logs\backend.log"
New-Item -ItemType Directory -Force -Path (Split-Path $log) | Out-Null

$py = Join-Path $root "venv\Scripts\python.exe"
if (-not (Test-Path $py)) {
    $py = (Get-Command python -ErrorAction SilentlyContinue).Source
}
if (-not $py) {
    Write-Error "No se encontro Python (ni venv\Scripts\python.exe ni python en PATH)."
    exit 1
}

# Liberar el puerto si quedo un backend anterior colgado.
$existing = Get-NetTCPConnection -LocalPort $port -State Listen -ErrorAction SilentlyContinue | Select-Object -First 1
if ($existing) {
    Write-Output "Cerrando proceso anterior en el puerto $port (PID $($existing.OwningProcess))..."
    Stop-Process -Id $existing.OwningProcess -Force -ErrorAction SilentlyContinue
    Start-Sleep -Seconds 2
}

if (Test-Path $log) { Move-Item $log "$log.old" -Force -ErrorAction SilentlyContinue }

$proc = Start-Process -FilePath $py -ArgumentList "run.py" -WorkingDirectory $root `
    -WindowStyle Hidden -RedirectStandardOutput $log -RedirectStandardError "$log.err" -PassThru

# Esperar a que el backend conteste de verdad (hasta 60s).
$deadline = (Get-Date).AddSeconds(60)
$ready = $false
while ((Get-Date) -lt $deadline) {
    if ($proc.HasExited) { break }
    try {
        $r = Invoke-WebRequest -Uri "http://127.0.0.1:$port/docs" -UseBasicParsing -TimeoutSec 3
        if ($r.StatusCode -ge 200) { $ready = $true; break }
    } catch { Start-Sleep -Milliseconds 700 }
}

if (-not $ready) {
    Write-Output "El backend NO respondio en el puerto $port. Ultimas lineas del log:"
    if (Test-Path "$log.err") { Get-Content "$log.err" -Tail 20 }
    if (Test-Path $log) { Get-Content $log -Tail 20 }
    exit 1
}

Write-Output "Backend listo en http://localhost:$port (PID $($proc.Id)). Log: $log"
exit 0
