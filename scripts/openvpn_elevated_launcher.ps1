param(
    [Parameter(Mandatory=$true)]
    [string]$Action,
    [string]$ConfigFile,
    [string]$AuthFile,
    [string]$LogFile,
    [string]$PidFile
)

$OpenVpnExe = "C:\Program Files\OpenVPN\bin\openvpn.exe"
if (-not (Test-Path $OpenVpnExe)) {
    $OpenVpnExe = "C:\Program Files (x86)\OpenVPN\bin\openvpn.exe"
}

function Connect-VPN {
    $logDir = Split-Path $LogFile -Parent
    if (-not (Test-Path $logDir)) { New-Item -ItemType Directory -Path $logDir -Force | Out-Null }

    $args = @("--config", $ConfigFile, "--log", $LogFile, "--verb", "3", "--disable-dco", "--data-ciphers", "AES-256-GCM:AES-128-GCM:AES-128-CBC")

    if ($AuthFile -and (Test-Path $AuthFile)) {
        $args += @("--auth-user-pass", $AuthFile)
    }

    $workDir = Split-Path $ConfigFile -Parent
    $proc = Start-Process -FilePath $OpenVpnExe -ArgumentList $args -NoNewWindow -PassThru -WorkingDirectory $workDir -WindowStyle Hidden

    $proc.Id | Out-File -FilePath $PidFile -Force
    Write-Host "OpenVPN PID: $($proc.Id)"
    Start-Sleep -Seconds 3

    $timeout = 60
    $elapsed = 0
    while ($elapsed -lt $timeout) {
        Start-Sleep -Seconds 1
        $elapsed++
        $logContent = Get-Content -Path $LogFile -Tail 10 -ErrorAction SilentlyContinue
        foreach ($line in $logContent) {
            if ($line -match "Initialization Sequence Completed") {
                Write-Host "CONNECTED"
                exit 0
            }
        }
        $proc.Refresh()
        if ($proc.HasExited) {
            Write-Host "PROCESS_EXITED:$($proc.ExitCode)"
            exit $proc.ExitCode
        }
    }

    Write-Host "TIMEOUT"
    exit 2
}

function Disconnect-VPN {
    if (Test-Path $PidFile) {
        $pid = Get-Content $PidFile -Raw | ForEach-Object { $_.Trim() }
        if ($pid -and $pid -match '^\d+$') {
            $proc = Get-Process -Id $pid -ErrorAction SilentlyContinue
            if ($proc) { $proc.Kill() }
        }
        Remove-Item $PidFile -Force -ErrorAction SilentlyContinue
    }
    Get-Process -Name "openvpn" -ErrorAction SilentlyContinue | ForEach-Object { $_.Kill() }
    Write-Host "DISCONNECTED"
    exit 0
}

switch ($Action.ToLower()) {
    "connect" { Connect-VPN }
    "disconnect" { Disconnect-VPN }
    default { exit 1 }
}
