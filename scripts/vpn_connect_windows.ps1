param(
    [Parameter(Mandatory=$true)]
    [string]$Action,
    [string]$Name,
    [string]$ServerAddress,
    [string]$PresharedKey,
    [string]$Username,
    [string]$Password,
    [string]$TunnelType = "L2tp",
    [string[]]$Routes = @("192.168.0.0/16", "10.110.0.0/16")
)

$ErrorActionPreference = "Stop"

function Create-L2tpVpn {
    Write-Host "Creating L2TP/IPsec VPN: $Name -> $ServerAddress"

    # Escape single quotes in PSK for PowerShell
    $escapedPsk = $PresharedKey -replace "'", "''"

    $cmd = "Add-VpnConnection -Name '$Name' -ServerAddress '$ServerAddress' -TunnelType L2tp -L2tpPsk '$escapedPsk' -EncryptionLevel Required -AuthenticationMethod Pap,Chap,MsChapv2 -SplitTunneling -PassThru -Force"
    $result = Invoke-Expression $cmd
    if (-not $?) {
        Write-Error "Failed to create L2TP VPN: $($Error[0].Exception.Message)"
        return $false
    }
    return $true
}

function Create-Ikev2Vpn {
    Write-Host "Creating IKEv2 VPN: $Name -> $ServerAddress"

    $cmd = "Add-VpnConnection -Name '$Name' -ServerAddress '$ServerAddress' -TunnelType Ikev2 -EncryptionLevel Required -AuthenticationMethod MsChapv2 -SplitTunneling -PassThru -Force"
    $result = Invoke-Expression $cmd
    if (-not $?) {
        Write-Error "Failed to create IKEv2 VPN: $($Error[0].Exception.Message)"
        return $false
    }

    # Configure IKEv2 to accept any server certificate
    $rasPath = "$env:APPDATA\Microsoft\Network\Connections\Pbk\rasphone.pbk"
    if (Test-Path $rasPath) {
        $content = Get-Content $rasPath -Raw
        $pattern = "(?<=\[$Name\]\r?\n.*?)AuthenticateServer=([01])"
        if ($content -match $pattern) {
            $content = $content -replace $pattern, 'AuthenticateServer=0'
            Set-Content -Path $rasPath -Value $content -Force
        }
    }
    return $true
}

function Connect-Vpn {
    Write-Host "Connecting $Name..."

    $rasdialPath = "$env:SystemRoot\System32\rasdial.exe"
    
    # Construir comando rasdial correctamente
    if ($Username -and $Password) {
        $credArg = "$Username $Password"
        $psi = New-Object System.Diagnostics.ProcessStartInfo
        $psi.FileName = $rasdialPath
        $psi.Arguments = "$Name $credArg"
        $psi.UseShellExecute = $false
        $psi.RedirectStandardOutput = $true
        $psi.RedirectStandardError = $true
        $psi.CreateNoWindow = $true
        $p = [System.Diagnostics.Process]::Start($psi)
        $output = $p.StandardOutput.ReadToEnd()
        $err = $p.StandardError.ReadToEnd()
        $p.WaitForExit()
        $exitCode = $p.ExitCode
    } else {
        $psi = New-Object System.Diagnostics.ProcessStartInfo
        $psi.FileName = $rasdialPath
        $psi.Arguments = $Name
        $psi.UseShellExecute = $false
        $psi.RedirectStandardOutput = $true
        $psi.RedirectStandardError = $true
        $psi.CreateNoWindow = $true
        $p = [System.Diagnostics.Process]::Start($psi)
        $output = $p.StandardOutput.ReadToEnd()
        $err = $p.StandardError.ReadToEnd()
        $p.WaitForExit()
        $exitCode = $p.ExitCode
    }

    Write-Host $output
    if ($err) { Write-Host $err }
    
    # Verificar conexión real: exit code 0 = success, output debe contener "conectado" o "connected"
    $connected = ($exitCode -eq 0) -and ($output -match "conectado" -or $output -match "connected" -or $output -match "registrado")
    
    if ($connected) {
        Write-Host "VPN Connected: $Name"
        return $true
    } else {
        Write-Warning "Connection attempt result (exit=$exitCode): $output $err"
        # Si el exit code es 0 pero no vemos texto de conexión, asumimos conectado
        if ($exitCode -eq 0) {
            Write-Host "ExitCode=0, assuming connected: $Name"
            return $true
        }
        Write-Error "Connection failed (exit=$exitCode): $output $err"
        return $false
    }
}

function Add-VpnRoutes {
    Write-Host "Adding VPN routes for subnets: $($Routes -join ', ')"
    
    # 1. Guardar rutas en el perfil VPN para persistencia (no requiere admin)
    foreach ($route in $Routes) {
        try {
            Add-VpnConnectionRoute -ConnectionName $Name -DestinationPrefix $route -PassThru -ErrorAction SilentlyContinue | Out-Null
            Write-Host "  Route $route saved to VPN profile"
        } catch {
            Write-Warning "  Could not save route $route to profile: $_"
        }
    }
    
    Start-Sleep 1
    
    # 2. Forzar rutas activas con netsh (funciona sin admin en interfaces existentes)
    Write-Host "  Forcing active routes via netsh..."
    
    # Obtener el índice de la interfaz VPN
    $vpnIfIndex = (Get-NetAdapter | Where-Object { $_.Name -like "*$Name*" -or $_.InterfaceDescription -like "*WAN Miniport (L2TP)*" -or $_.InterfaceDescription -like "*WAN Miniport (IKEv2)*" -or $_.InterfaceDescription -like "*VPN*" } | Select-Object -First 1).ifIndex
    
    if (-not $vpnIfIndex) {
        # Buscar por cualquier interfaz que no sea la red local y tenga gateway
        $vpnIfIndex = (Get-NetAdapter | Where-Object { $_.Status -eq "Up" -and $_.InterfaceDescription -notlike "*Virtual*" -and $_.InterfaceDescription -notlike "*Bluetooth*" -and $_.InterfaceDescription -like "*Miniport*" } | Select-Object -First 1).ifIndex
    }
    
    if ($vpnIfIndex) {
        Write-Host "  VPN Interface Index: $vpnIfIndex"
        foreach ($route in $Routes) {
            Write-Host "  netsh interface ipv4 add route $route if=$vpnIfIndex"
            $result = netsh interface ipv4 add route $route if=$vpnIfIndex
            Write-Host "    Result: $result"
        }
    } else {
        Write-Warning "  Could not find VPN interface index. Trying route add with 0.0.0.0 gateway..."
        foreach ($route in $Routes) {
            $parts = $route -split '/'
            $network = $parts[0]
            $maskLen = [int]$parts[1]
            $maskVal = ([Math]::Pow(2, $maskLen) - 1) * [Math]::Pow(2, 32 - $maskLen)
            $maskBytes = [BitConverter]::GetBytes([UInt32]$maskVal)
            $mask = "$($maskBytes[3]).$($maskBytes[2]).$($maskBytes[1]).$($maskBytes[0])"
            
            # route add sin gateway específico (debug)
            Write-Host "  route add $network mask $mask 0.0.0.0"
            route add $network mask $mask 0.0.0.0 > $null 2>&1
        }
    }
    
    # 3. Verificar rutas activas
    Start-Sleep 2
    Write-Host "  Verifying active routes:"
    foreach ($route in $Routes) {
        $parts = $route -split '/'
        $network = $parts[0]
        $routePrint = route print -4 | Select-String $network
        if ($routePrint) {
            Write-Host "    ROUTE OK: $route"
        } else {
            Write-Warning "    ROUTE NOT FOUND: $route"
        }
    }
}

function Disconnect-Vpn {
    Write-Host "Disconnecting $Name..."
    $rasdialPath = "$env:SystemRoot\System32\rasdial.exe"
    $proc = Start-Process -FilePath $rasdialPath -ArgumentList @($Name, '/disconnect') -NoNewWindow -PassThru -Wait
    Write-Host "Disconnected: $Name"
}

function Remove-Vpn {
    Write-Host "Removing VPN profile: $Name..."
    $cmd = "Remove-VpnConnection -Name '$Name' -Force -PassThru -ErrorAction SilentlyContinue"
    Invoke-Expression $cmd | Out-Null
    Write-Host "Removed: $Name"
}

# Main
try {
    switch ($Action.ToLower()) {
        "connect" {
            if ($TunnelType -eq "Ikev2") {
                $created = Create-Ikev2Vpn
            } else {
                $created = Create-L2tpVpn
            }
            if (-not $created) { exit 1 }

            $connected = Connect-Vpn
            if (-not $connected) { exit 2 }
            Add-VpnRoutes
            Write-Host "STATUS:CONNECTED"
        }
        "disconnect" {
            Disconnect-Vpn
            Write-Host "STATUS:DISCONNECTED"
        }
        "remove" {
            Remove-Vpn
        }
        "connect_and_cleanup" {
            # Primero eliminar la conexión existente para evitar errores de duplicado
            Write-Host "Cleaning up existing VPN profile: $Name"
            Remove-Vpn

            if ($TunnelType -eq "Ikev2") {
                $created = Create-Ikev2Vpn
            } else {
                $created = Create-L2tpVpn
            }
            if (-not $created) { exit 1 }

            $connected = Connect-Vpn
            if (-not $connected) { exit 2 }
            Add-VpnRoutes
            Write-Host "STATUS:CONNECTED"
        }
        default {
            Write-Error "Unknown action: $Action"
            exit 3
        }
    }
} catch {
    Write-Error "Error: $_"
    exit 4
}