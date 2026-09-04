param(
    [Parameter(Mandatory=$true)]
    [string]$ConfigFile,
    [string]$AuthFile,
    [string]$LogFile,
    [string]$OpenVpnPath = "C:\Program Files\OpenVPN\bin\openvpn.exe"
)

$ErrorActionPreference = "Stop"

if (-not (Test-Path $OpenVpnPath)) {
    $OpenVpnPath = "C:\Program Files (x86)\OpenVPN\bin\openvpn.exe"
}

if (-not (Test-Path $OpenVpnPath)) {
    Write-Error "OpenVPN no encontrado"
    exit 1
}

if (-not (Test-Path $ConfigFile)) {
    Write-Error "Archivo de configuracion no encontrado: $ConfigFile"
    exit 1
}

$logDir = Split-Path $LogFile -Parent
if (-not (Test-Path $logDir)) {
    New-Item -ItemType Directory -Path $logDir -Force | Out-Null
}

$arguments = @(
    "--config", "`"$ConfigFile`"",
    "--log", "`"$LogFile`"",
    "--verb", "3",
    "--route-nopull"
)

if ($AuthFile -and (Test-Path $AuthFile)) {
    $arguments += @("--auth-user-pass", "`"$AuthFile`"")
}

$logFileDir = Split-Path $LogFile -Parent
$process = Start-Process -FilePath $OpenVpnPath -ArgumentList $arguments -NoNewWindow -PassThru -WorkingDirectory $logFileDir

$process | Export-Clixml -Path "$env:TEMP\openvpn_process_$($process.Id).xml"

Write-Host "OpenVPN iniciado con PID: $($process.Id)"
exit 0
