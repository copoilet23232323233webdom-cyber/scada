@echo off
setlocal
title WEBDOM MONITOR

:: ============================================================
::  WEBDOM MONITOR - LANZADOR
::  Doble clic para iniciar backend + frontend.
::  Funciona desde cualquier carpeta: la raiz se deduce del .bat.
::  Logs en logs\backend.log y logs\frontend.log
:: ============================================================

set "ROOT=%~dp0"
if "%ROOT:~-1%"=="\" set "ROOT=%ROOT:~0,-1%"
cd /d "%ROOT%" || (
    echo [ERROR] No se pudo entrar en "%ROOT%".
    pause
    exit /b 1
)

:: --- Auto-elevacion a Administrador (necesaria para la VPN) ---
net session >nul 2>&1
if %errorlevel% neq 0 (
    echo Solicitando permisos de Administrador...
    powershell -NoProfile -Command "Start-Process -FilePath '%~f0' -Verb RunAs"
    exit /b 0
)

echo.
echo ========================================
echo   WEBDOM MONITOR
echo   Raiz: %ROOT%
echo ========================================
echo.

:: --- 1/4 Python ---
echo [1/4] Comprobando Python...
set "PY=%ROOT%\venv\Scripts\python.exe"
if not exist "%PY%" (
    echo       Entorno virtual no encontrado, creandolo...
    where py >nul 2>&1 && (py -3 -m venv "%ROOT%\venv") || (python -m venv "%ROOT%\venv")
)
if not exist "%PY%" (
    echo [ERROR] No se pudo crear el entorno virtual. Instala Python 3.10+ y reintenta.
    pause
    exit /b 1
)
echo       Ok

:: --- 2/4 Dependencias (solo si faltan o cambio requirements.txt) ---
echo [2/4] Comprobando dependencias Python...
set "STAMP=%ROOT%\venv\.requirements.stamp"
set "NEED_INSTALL=0"
"%PY%" -c "import fastapi, uvicorn, sqlalchemy" >nul 2>&1 || set "NEED_INSTALL=1"
if not exist "%STAMP%" set "NEED_INSTALL=1"
if "%NEED_INSTALL%"=="0" (
    for /f %%A in ('powershell -NoProfile -Command "if ((Get-Item '%ROOT%\requirements.txt').LastWriteTimeUtc -gt (Get-Item '%STAMP%').LastWriteTimeUtc) { 1 } else { 0 }"') do set "NEED_INSTALL=%%A"
)
if "%NEED_INSTALL%"=="1" (
    echo       Instalando/actualizando dependencias...
    "%PY%" -m pip install --disable-pip-version-check -q -r "%ROOT%\requirements.txt"
    if errorlevel 1 (
        echo [ERROR] Fallo la instalacion de dependencias. Revisa la conexion a internet.
        pause
        exit /b 1
    )
    echo ok> "%STAMP%"
) else (
    echo       Ya instaladas (se omite)
)

:: --- 3/4 Node/npm ---
echo [3/4] Comprobando frontend...
set "NO_FRONTEND=0"
where npm >nul 2>&1 || set "NO_FRONTEND=1"
if not exist "%ROOT%\frontend\package.json" set "NO_FRONTEND=1"
if "%NO_FRONTEND%"=="1" (
    echo       [AVISO] npm o frontend no disponibles: solo se inicia el backend.
) else (
    if not exist "%ROOT%\frontend\node_modules" (
        echo       Instalando dependencias del frontend ^(primera vez^)...
        pushd "%ROOT%\frontend"
        call npm install --no-fund --no-audit
        popd
    )
    echo       Ok
)

:: --- 4/4 Arranque ---
echo [4/4] Iniciando servicios...
powershell -NoProfile -ExecutionPolicy Bypass -File "%ROOT%\scripts\start_backend.ps1"
if errorlevel 1 (
    echo [ERROR] El backend no arranco. Revisa logs\backend.log
    pause
    exit /b 1
)

if "%NO_FRONTEND%"=="0" (
    powershell -NoProfile -ExecutionPolicy Bypass -File "%ROOT%\scripts\start_frontend.ps1"
    if errorlevel 1 (
        echo [AVISO] El frontend no arranco. Revisa logs\frontend.log
    )
)

echo.
echo ========================================
echo   Backend:  http://localhost:8000
echo   Docs:     http://localhost:8000/docs
if "%NO_FRONTEND%"=="0" echo   Frontend: http://localhost:5173
echo   Logs:     logs\backend.log  /  logs\frontend.log
echo ========================================
echo.

if "%NO_FRONTEND%"=="0" start "" http://localhost:5173

echo Pulse una tecla para DETENER backend y frontend y cerrar esta ventana.
pause >nul

echo Deteniendo servicios...
powershell -NoProfile -ExecutionPolicy Bypass -File "%ROOT%\scripts\stop_all.ps1"
endlocal
exit /b 0
