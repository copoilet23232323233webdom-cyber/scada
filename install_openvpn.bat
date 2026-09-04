@echo off
REM WEBDOM MONITOR - Instalador OpenVPN para Windows
REM Este script descarga e instala OpenVPN automáticamente

setlocal enabledelayedexpansion

echo.
echo ========================================
echo  WEBDOM MONITOR - Instalador OpenVPN
echo ========================================
echo.

REM Verificar si ya está instalado
if exist "C:\Program Files\OpenVPN\bin\openvpn.exe" (
    echo.
    echo [OK] OpenVPN ya esta instalado
    echo Ubicacion: C:\Program Files\OpenVPN\bin\openvpn.exe
    echo.
    pause
    exit /b 0
)

if exist "C:\Program Files (x86)\OpenVPN\bin\openvpn.exe" (
    echo.
    echo [OK] OpenVPN ya esta instalado
    echo Ubicacion: C:\Program Files (x86)\OpenVPN\bin\openvpn.exe
    echo.
    pause
    exit /b 0
)

REM Intentar instalar con chocolatey
echo [1/3] Verificando Chocolatey...
where choco >nul 2>&1
if %ERRORLEVEL% EQU 0 (
    echo [2/3] Chocolatey encontrado. Instalando OpenVPN...
    choco install openvpn -y
    if %ERRORLEVEL% EQU 0 (
        echo.
        echo [OK] OpenVPN instalado exitosamente con Chocolatey
        echo.
        pause
        exit /b 0
    )
)

REM Si no está chocolatey, intentar manual
echo [2/3] Descargando OpenVPN...
powershell -Command "(New-Object System.Net.ServicePointManager).SecurityProtocol = [System.Net.ServicePointManager]::SecurityProtocol -bor 3072; (New-Object System.Net.WebClient).DownloadFile('https://swupdate.openvpn.org/community/releases/OpenVPN-2.6.8-I601-amd64.msi', '%TEMP%\OpenVPN-installer.msi')"

if exist "%TEMP%\OpenVPN-installer.msi" (
    echo [3/3] Instalando OpenVPN...
    msiexec /i "%TEMP%\OpenVPN-installer.msi" /qb
    
    echo.
    echo [OK] OpenVPN instalado exitosamente
    echo Reinicia tu terminal y ejecuta: .\start.ps1
    echo.
    pause
    exit /b 0
) else (
    echo.
    echo [ERROR] No se pudo descargar OpenVPN
    echo.
    echo Instalacion manual:
    echo 1. Visita: https://openvpn.net/download-open-vpn/
    echo 2. Descarga OpenVPN 2.6.x o superior
    echo 3. Ejecuta el instalador
    echo 4. Reinicia tu terminal
    echo 5. Ejecuta: .\start.ps1
    echo.
    pause
    exit /b 1
)
