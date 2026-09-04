# Arranca el frontend (Vite) y verifica que sirve antes de salir.
$ErrorActionPreference = "Stop"

$root = Split-Path -Parent $PSScriptRoot
$front = Join-Path $root "frontend"
$port = if ($env:WEBDOM_FRONTEND_PORT) { [int]$env:WEBDOM_FRONTEND_PORT } else { 5173 }
$log = Join-Path $root "logs\frontend.log"
New-Item -ItemType Directory -Force -Path (Split-Path $log) | Out-Null

if (-not (Test-Path (Join-Path $front "package.json"))) {
    Write-Error "No se encontro frontend\package.json en $front"
    exit 1
}
$npm = (Get-Command npm.cmd -ErrorAction SilentlyContinue)
if (-not $npm) { $npm = (Get-Command npm -ErrorAction SilentlyContinue) }
if (-not $npm) {
    Write-Error "npm no esta instalado o no esta en el PATH. Instala Node.js LTS."
    exit 1
}

if (-not (Test-Path (Join-Path $front "node_modules"))) {
    Write-Output "Instalando dependencias del frontend (primera vez)..."
    & $npm.Source install --no-fund --no-audit --prefix $front
}

$existing = Get-NetTCPConnection -LocalPort $port -State Listen -ErrorAction SilentlyContinue | Select-Object -First 1
if ($existing) {
    Write-Output "Cerrando proceso anterior en el puerto $port (PID $($existing.OwningProcess))..."
    Stop-Process -Id $existing.OwningProcess -Force -ErrorAction SilentlyContinue
    Start-Sleep -Seconds 2
}

if (Test-Path $log) { Move-Item $log "$log.old" -Force -ErrorAction SilentlyContinue }

$proc = Start-Process -FilePath $npm.Source -ArgumentList "run","dev" -WorkingDirectory $front `
    -WindowStyle Hidden -RedirectStandardOutput $log -RedirectStandardError "$log.err" -PassThru

$deadline = (Get-Date).AddSeconds(90)
$ready = $false
while ((Get-Date) -lt $deadline) {
    if ($proc.HasExited) { break }
    try {
        $r = Invoke-WebRequest -Uri "http://127.0.0.1:$port/" -UseBasicParsing -TimeoutSec 3
        if ($r.StatusCode -ge 200) { $ready = $true; break }
    } catch { Start-Sleep -Milliseconds 700 }
}

if (-not $ready) {
    Write-Output "El frontend NO respondio en el puerto $port. Ultimas lineas del log:"
    if (Test-Path "$log.err") { Get-Content "$log.err" -Tail 20 }
    if (Test-Path $log) { Get-Content $log -Tail 20 }
    exit 1
}

Write-Output "Frontend listo en http://localhost:$port (PID $($proc.Id)). Log: $log"
exit 0
