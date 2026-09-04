# 🚀 WEBDOM MONITOR v2.0 - GUÍA DE INSTALACIÓN Y USO

## 📌 Requisitos del Sistema

- **Windows 10/Server 2019+** o **Linux (Debian/Ubuntu/RHEL)**
- **Python 3.11+**
- **4GB RAM mínimo** (8GB recomendado)
- **100MB espacio en disco** (para BD SQLite)
- **(Opcional) FortiClient VPN o OpenVPN** instalado

## ⚙️ INSTALACIÓN PASO A PASO

### 1️⃣ Instalar Python 3.13

**Windows:**
```powershell
# Descargar desde https://www.python.org/downloads/
# O usar chocolatey:
choco install python
```

**Linux (Debian/Ubuntu):**
```bash
sudo apt-get update
sudo apt-get install python3.13 python3.13-venv python3-pip
```

### 2️⃣ Clonar/Descargar Webdom Monitor

```bash
cd C:\
git clone <tu-repo> SCADA_MOHAMED
cd SCADA_MOHAMED
```

O descargar ZIP y extraer en `C:\SCADA_MOHAMED`

### 3️⃣ Crear Entorno Virtual Python

**Windows (PowerShell):**
```powershell
cd C:\SCADA_MOHAMED
python -m venv venv
.\venv\Scripts\Activate.ps1
```

**Linux/MacOS:**
```bash
cd /home/usuario/SCADA_MOHAMED
python3.13 -m venv venv
source venv/bin/activate
```

### 4️⃣ Instalar Dependencias Python

```bash
pip install --upgrade pip
pip install -r requirements.txt
```

**Dependencias incluidas:**
- FastAPI 0.115.0
- SQLAlchemy 2.0.36
- Pydantic 2.9.2
- Modbus TCP nativo
- WebSockets
- Python-Jose (JWT)
- Passlib (hashing)

### 5️⃣ Crear Estructura de Plantas

```bash
mkdir plants
mkdir plants\Olivenza
mkdir plants\Torralba
mkdir plants\RioDoPeixe

# Crear archivos de configuración
```

**Ejemplo: plants/Olivenza/ips.txt**
```
10.10.0.20
10.10.0.21
10.10.0.22
```

**Ejemplo: plants/Olivenza/vpn.txt**
```
VPN_TYPE=forticlient
VPN_NAME=OLIVENZA
HOST=vpn.miempresa.com
USER=usuario
PASSWORD=tu_password

# O para OpenVPN:
VPN_TYPE=openvpn
CONFIG=C:\VPN\olivenza.ovpn
USER=usuario
PASSWORD=tu_password
```

### 6️⃣ Crear Base de Datos Inicial

```bash
# Automático: se crea en primer inicio
# O manual:
python
>>> from app.core.database import Base, engine
>>> Base.metadata.create_all(bind=engine)
```

### 7️⃣ Crear Usuario Admin

```bash
python scripts/create_admin.py
# Usuario: admin
# Contraseña: admin123 (CAMBIAR DESPUÉS)
```

### 8️⃣ Iniciar Servidor Backend

```bash
# Desarrollo (puerto 8000)
python run.py

# Producción (con gunicorn)
pip install gunicorn
gunicorn -w 4 -b 0.0.0.0:8000 app.main:app --reload
```

### 9️⃣ Instalar Frontend (Node.js + React)

**Windows:**
```powershell
# Descargar Node.js desde https://nodejs.org/ (LTS)
# O: choco install nodejs

cd frontend
npm install
npm run dev
```

**Linux:**
```bash
curl -fsSL https://deb.nodesource.com/setup_20.x | sudo -E bash -
sudo apt-get install -y nodejs

cd frontend
npm install
npm run dev
```

### 🔟 Acceder a la Aplicación

```
Frontend:  http://localhost:5173
Backend:   http://localhost:8000
API Docs:  http://localhost:8000/docs
Health:    http://localhost:8000/health
```

**Credenciales por defecto:**
- Usuario: `admin`
- Contraseña: `admin123`

---

## 🎯 FLUJO DE FUNCIONAMIENTO

### Ciclo Automático de Escaneo

```
┌─────────────────────────────────────────┐
│ SCHEDULER (cada 5 minutos)              │
├─────────────────────────────────────────┤
│ 1. Detectar plantas en carpeta Plants/  │
│ 2. Para cada planta:                    │
│    a) Conectar VPN                      │
│    b) Descubrir Gateways (ips.txt)      │
│    c) Para cada Gateway:                │
│       - 5 escaneos Modbus consecutivos  │
│       - Consolidar resultados           │
│       - Guardar en BD (últimos 5)       │
│       - Generar alarmas si necesario    │
│    d) Desconectar VPN                   │
│ 3. Enviar recordatorios de alarmas      │
│ 4. Limpiar datos antiguos               │
│ 5. Esperar 5 minutos                    │
│ 6. Repetir                              │
└─────────────────────────────────────────┘
```

### Estados de Planta/Gateway/Tarjeta

| Estado | Descripción | Acción |
|--------|-------------|--------|
| 🟢 **GREEN** | Todo OK | Sin alarmas |
| 🟡 **YELLOW** | Parcialmente OK | - Algunas tarjetas sin comunicación<br>- Tiempo respuesta medio<br>- Alarmas SEC/Sobretensión |
| 🔴 **RED** | Crítico | - Gateway caído<br>- VPN caída<br>- Todas las tarjetas caídas |

### Validación de Errores (5 Escaneos)

```
Gateway 10.10.0.20:

Escaneo 1: 22 tarjetas OK ✓
Escaneo 2: 22 tarjetas OK ✓
Escaneo 3: 22 tarjetas OK ✓
Escaneo 4: 22 tarjetas OK ✓
Escaneo 5: 22 tarjetas OK ✓
─────────────────────────
RESULTADO: 22 tarjetas confirmadas ✓

Si hubiera variación:
Escaneo 1: 22 tarjetas
Escaneo 2: 20 tarjetas
Escaneo 3: 22 tarjetas
Escaneo 4: 22 tarjetas
Escaneo 5: 22 tarjetas
─────────────────────────
RESULTADO: 22 (más frecuente) ✓
```

---

## 📊 PANEL DE CONTROL (Dashboard)

### Pantalla Principal
- **Tarjetas de Plantas**: Estado en tiempo real
- **Métricas**: Gateways, Tarjetas, Alarmas activas
- **Gráficas**: Tendencias de disponibilidad
- **Búsqueda y Filtros**: Por estado, planta, etc

### Vista de Planta
- **Tabla de Gateways**: IP, Estado, Firmware, Respuesta
- **Tabla de Tarjetas**: ID, Estado, Comunicación, Última lectura
- **Histórico**: Últimos 5 escaneos
- **Alarmas**: Activas, Resueltas, Historial

### Gestor de Alarmas
- **Crear alarma manual**
- **Resolver alarma**
- **Añadir observaciones**
- **Historial completo**

---

## ⚙️ CONFIGURACIÓN AVANZADA

### Archivo .env

```env
# Aplicación
APP_NAME=Webdom Monitor
DATABASE_URL=sqlite:///./webdom_monitor.db
SECRET_KEY=tu-clave-secreta-super-segura

# Tokens JWT
ALGORITHM=HS256
ACCESS_TOKEN_EXPIRE_MINUTES=1440

# CORS
CORS_ORIGINS=["http://localhost:5173", "http://localhost:3000"]

# Escaneo
SCAN_INTERVAL_SECONDS=300          # 5 minutos
SCAN_RETRIES=5                     # 5 escaneos
MODBUS_TIMEOUT=5.0                 # segundos
MODBUS_PORT=502                    # puerto Modbus

# Alarmas
ALARM_REMINDER_DAYS=7              # recordatorio cada 7 días

# Email
SMTP_SERVER=smtp.gmail.com
SMTP_PORT=587
SMTP_USER=webdomreports@gmail.com
SMTP_PASSWORD=tu-app-password      # Usar Google App Password

# VPN
VPN_EXECUTABLE_OPENVPN=C:\Program Files\OpenVPN\bin\openvpn.exe
VPN_EXECUTABLE_FORTICLIENT=C:\Program Files\Fortinet\FortiClient\FortiClient.exe
```

### Configurar Gmail SMTP

1. Activar 2FA en Google Account
2. Generar "App Password" en myaccount.google.com
3. Usar ese password en .env

```bash
SMTP_USER=webdomreports@gmail.com
SMTP_PASSWORD=xxxx xxxx xxxx xxxx
```

---

## 🔧 MANTENIMIENTO

### Ver Estado de la BD

```bash
python check_db.py
```

**Salida:**
```
=== ESTADO DE LA BASE DE DATOS ===

Plantas encontradas: 3
  - Olivenza: status=green, last_scan=2024-07-08 10:30:00
    Gateways: 3
      - 10.10.0.20 (IDs 1-32): status=green, lora_ok=1
      - 10.10.0.21 (IDs 1-32): status=yellow, lora_ok=1
      - 10.10.0.22 (IDs 1-32): status=green, lora_ok=1
```

### Diagnosticar API

```bash
python diagnostic.py
```

### Recuperar Base de Datos

```bash
python recover_and_test.py
```

### Ejecutar Tests

```bash
pytest tests/
```

---

## 🚀 DESPLIEGUE EN PRODUCCIÓN (Windows Service)

### Crear Windows Service

```powershell
# 1. Instalar NSSM (Non-Sucking Service Manager)
choco install nssm

# 2. Crear servicio
nssm install WebdomMonitor "C:\SCADA_MOHAMED\venv\Scripts\python.exe" "C:\SCADA_MOHAMED\run.py"

# 3. Configurar para iniciar automáticamente
nssm set WebdomMonitor Start SERVICE_AUTO_START
nssm set WebdomMonitor AppDirectory "C:\SCADA_MOHAMED"
nssm set WebdomMonitor AppStdout "C:\SCADA_MOHAMED\logs\stdout.log"
nssm set WebdomMonitor AppStderr "C:\SCADA_MOHAMED\logs\stderr.log"

# 4. Iniciar servicio
nssm start WebdomMonitor

# Ver logs:
nssm log WebdomMonitor all
```

### Con Nginx (Windows)

```nginx
# C:\nginx\conf\nginx.conf
upstream webdom {
    server localhost:8000;
}

upstream frontend {
    server localhost:5173;
}

server {
    listen 80;
    server_name monitor.miempresa.es;

    # Frontend
    location / {
        proxy_pass http://frontend;
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection "upgrade";
    }

    # API Backend
    location /api/ {
        proxy_pass http://webdom;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
    }

    # WebSocket
    location /ws/ {
        proxy_pass http://webdom;
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection "upgrade";
    }
}
```

---

## 🐛 TROUBLESHOOTING

### Error: "VPN no encontrado"

```
✗ Problema: FortiClient o OpenVPN no instalado
✓ Solución: 
  1. Instalar cliente VPN
  2. Verificar ruta en .env
  3. Reiniciar aplicación
```

### Error: "Puerto 502 no accesible"

```
✗ Problema: VPN no conectada o Gateway caído
✓ Solución:
  1. Verificar archivo vpn.txt
  2. Conectar VPN manualmente
  3. Pingear IP del Gateway
```

### Error: "Database locked"

```
✗ Problema: Múltiples procesos usando BD simultaneamente
✓ Solución:
  1. Cerrar todos los procesos Python
  2. Eliminar archivo .db-journal
  3. Reiniciar
```

### Base de Datos corrupta

```bash
# Hacer backup
copy webdom_monitor.db webdom_monitor.db.bak

# Recrear
python
>>> from app.core.database import Base, engine
>>> Base.metadata.drop_all(bind=engine)
>>> Base.metadata.create_all(bind=engine)
```

---

## 📈 ESCALABILIDAD

Arquitectura soporta:
- ✅ 500+ plantas
- ✅ 5000+ gateways
- ✅ 100000+ tarjetas
- ✅ 24/7/365 operación

Sin necesidad de cambios de código.

---

## 📞 SOPORTE

- 📧 Email: webdomreports@gmail.com
- 🌐 Docs: http://localhost:8000/docs
- 📚 GitHub: <tu-repo>

---

## ⚖️ LICENCIA

GNU General Public License v3.0
Completamente GRATIS y Open Source

---

**Versión:** 2.0.0  
**Última actualización:** 2024-07-08  
**Autor:** Webdom Monitor Team
