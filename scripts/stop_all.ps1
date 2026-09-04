# Detiene backend y frontend cerrando SOLO los procesos que escuchan sus puertos.
# No toca procesos de VPN: una conexion establecida sigue viva.
$ErrorActionPreference = "Continue"

$ports = @(
    @{ Name = "Backend";  Port = if ($env:WEBDOM_BACKEND_PORT)  { [int]$env:WEBDOM_BACKEND_PORT }  else { 8000 } },
    @{ Name = "Frontend"; Port = if ($env:WEBDOM_FRONTEND_PORT) { [int]$env:WEBDOM_FRONTEND_PORT } else { 5173 } }
)

foreach ($entry in $ports) {
    $conns = Get-NetTCPConnection -LocalPort $entry.Port -State Listen -ErrorAction SilentlyContinue
    if (-not $conns) {
        Write-Output "$($entry.Name): no habia nada escuchando en el puerto $($entry.Port)."
        continue
    }
    foreach ($procId in ($conns | Select-Object -ExpandProperty OwningProcess -Unique)) {
        Stop-Process -Id $procId -Force -ErrorAction SilentlyContinue
        Write-Output "$($entry.Name): proceso $procId detenido (puerto $($entry.Port))."
    }
}
