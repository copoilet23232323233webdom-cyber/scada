@echo off
REM Script intermedio para ejecutar vpn_connect_windows.ps1 con privilegios de administrador
REM Este .bat se ejecuta con Start-Process -Verb RunAs
REM Guarda la salida a un archivo temporal para que Python pueda leerla

set OUTPUT_FILE=%TEMP%\vpn_output_%RANDOM%.txt
set ERROR_FILE=%TEMP%\vpn_error_%RANDOM%.txt

echo [BAT] Iniciando script VPN elevado... > "%OUTPUT_FILE%"
echo [BAT] Argumentos: %* >> "%OUTPUT_FILE%"

REM Ejecutar PowerShell con los argumentos recibidos
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0vpn_connect_windows.ps1" %* >> "%OUTPUT_FILE%" 2>> "%ERROR_FILE%"

REM Capturar el exit code
set EXIT_CODE=%ERRORLEVEL%
echo EXIT_CODE=%EXIT_CODE% >> "%OUTPUT_FILE%"

REM Verificar si hay STATUS:CONNECTED en la salida
findstr /C:"STATUS:CONNECTED" "%OUTPUT_FILE%" > nul
if %ERRORLEVEL%==0 (
    echo STATUS_DETECTED=YES >> "%OUTPUT_FILE%"
) else (
    echo STATUS_DETECTED=NO >> "%OUTPUT_FILE%"
)

REM Mostrar la salida por stdout para que Python la capture
type "%OUTPUT_FILE%"

REM Limpiar archivos temporales (opcional, los dejamos para debug)
del "%ERROR_FILE%" 2>nul

exit /b %EXIT_CODE%