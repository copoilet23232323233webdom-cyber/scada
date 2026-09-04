@echo off
title WEBDOM MONITOR v2.1
cd /d C:\SCADA_MOHAMED

:: ============================================================
::  WEBDOM MONITOR v2.1 - LANZADOR COMPLETO
::  Doble clic para iniciar todo el proyecto
::  Usa scripts PowerShell robustos (funcionan con doble clic
::  y en sesiones no interactivas), con logs en logs\*.log
:: ============================================================

:: --- Auto-elevacion a Administrador (UAC) ---
net session >nul 2>&1
if %errorLevel% neq 0 (
    echo Solicitando permisos de Administrador...
    powershell -Command "Start-Process '%~f0' -Verb RunAs"
    exit /b
)

echo.
echo ========================================
echo   WEBDOM MONITOR v2.1
echo   Backend + Frontend
echo   Modo estable (sin auto-reload)
echo ========================================
echo.

:: --- Verificar entorno virtual ---
if not exist "venv\Scripts\python.exe" (
    echo [ERROR] Entorno virtual no encontrado.
    echo Ejecuta: python -m venv venv
    pause
    exit /b 1
)

echo [1/4] Verificando dependencias Python...
venv\Scripts\python.exe -m pip install -q -r requirements.txt 2>nul
echo       Ok
echo.

:: --- Matar procesos OpenVPN previos (libera adaptador TAP) ---
echo [2/4] Limpiando procesos OpenVPN previos...
taskkill /IM openvpn.exe /F >nul 2>&1
timeout /t 1 /nobreak >nul
echo       Ok
echo.

:: --- Verificar Node.js para el frontend ---
echo [3/4] Verificando frontend...
set NO_FRONTEND=0
where npm >nul 2>&1
if %errorLevel% neq 0 (
    echo       [AVISO] npm no encontrado. Solo se iniciara el backend.
    set NO_FRONTEND=1
)
echo       Ok
echo.

:: --- Mostrar informacion ---
echo ========================================
echo   Backend:  http://localhost:8000
echo   Docs:     http://localhost:8000/docs
echo   Frontend: http://localhost:5173
echo   Usuario:  admin
echo   Password: admin123
echo ========================================
echo.

:: --- Iniciar Backend y Frontend (procesos reales via PowerShell) ---
echo [4/4] Iniciando Backend y Frontend...
echo.
powershell -NoProfile -ExecutionPolicy Bypass -File "C:\SCADA_MOHAMED\scripts\start_backend.ps1"

if "%NO_FRONTEND%"=="0" (
    powershell -NoProfile -ExecutionPolicy Bypass -File "C:\SCADA_MOHAMED\scripts\start_frontend.ps1"
)

echo.
echo ========================================
echo   Backend y Frontend iniciados.
echo   Backend:  http://localhost:8000
echo   Docs:     http://localhost:8000/docs
echo   Frontend: http://localhost:5173
echo   Logs:     logs\backend.log  /  logs\frontend.log
echo ========================================
echo.

:: --- Mantener abierta la ventana lanzadora hasta Ctrl+C ---
echo Pulse Ctrl+C para cerrar esta ventana.
echo Para detener la app cierre los procesos en los logs o reinicie Windows.
echo.
:loop
timeout /t 3600 /nobreak >nul
goto loop
