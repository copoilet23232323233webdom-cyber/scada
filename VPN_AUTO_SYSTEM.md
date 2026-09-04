# VPN SISTEMA AUTOMÁTICO v2.1

## 🎯 Características Principales

El nuevo sistema VPN **automáticamente detecta y utiliza** cualquier cliente VPN disponible:

### ✅ Orden de Prioridad Automática:
1. **OpenVPN** (si está instalado)
2. **FortiClient** (si OpenVPN no funciona)
3. **DEMO MODE** (si ninguno funciona - para pruebas)

### 🔄 Fallback Automático:
Si un método falla, intenta automáticamente el siguiente sin intervención manual.

---

## 🚀 Opciones de Inicio

### Opción 1: Modo Normal (Intenta OpenVPN/FortiClient)

```powershell
.\start.ps1
```

Esto:
- ✅ Intenta conectar OpenVPN
- ✅ Si falla, intenta FortiClient  
- ✅ Si ambos fallan, activa DEMO MODE automáticamente
- ✅ Muestra en logs qué método está usando

---

### Opción 2: Modo DEMO (Sin VPN Real)

```powershell
.\start_demo.ps1
```

Esto:
- ✅ Simula conexión VPN exitosa
- ✅ Genera datos de prueba
- ✅ NO necesita OpenVPN/FortiClient instalado
- ✅ Perfecto para desarrollo y demostración

---

### Opción 3: Modo DEMO desde Terminal

```powershell
$env:DEMO_MODE="true"
python run.py
```

---

## 📦 Instalar OpenVPN (Opcional)

Si quieres usar OpenVPN real:

```powershell
# Opción A: Con Chocolatey
choco install openvpn -y

# Opción B: Script automático (Windows)
.\install_openvpn.bat

# Opción C: Descarga manual
# https://openvpn.net/download-open-vpn/
```

---

## ⚙️ Configuración VPN

### Archivo: `plants/ACAMPO/vpn.txt`

**Para OpenVPN:**
```
VPN_TYPE=openvpn
CONFIG=C:\SCADA_MOHAMED\plants\ACAMPO\mtech.ovpn
USER=mtech
PASSWORD=78BnGj1Cki82
KEY_PASSWORD=acampofw
```

**Para FortiClient:**
```
VPN_TYPE=forticlient
VPN_NAME=Mi_VPN
HOST=vpn.miempresa.com
USER=usuario
PASSWORD=contraseña
```

**Para DEMO Mode:**
```
VPN_TYPE=demo
DEMO_MODE=true
```

---

## 📊 Ver Qué VPN Se Está Usando

Abre el archivo de logs mientras el servidor corre:

```powershell
Get-Content logs\webdom_monitor.log -Tail 30 -Wait
```

Busca mensajes como:
```
OpenVPN disponible: True/False
FortiClient disponible: True/False
Modo DEMO: True/False
Métodos VPN disponibles: [openvpn, forticlient, demo]
Intento 1/3: openvpn
✓ ACAMPO conectado exitosamente via openvpn
```

---

## 🧪 Flujo de Conexión

```
┌─────────────────────────────────────┐
│  Iniciar Servidor (start.ps1)       │
└────────────┬────────────────────────┘
             │
             ▼
┌─────────────────────────────────────┐
│  ¿OpenVPN instalado?                │
└────────┬────────────────────┬───────┘
         │ SÍ                 │ NO
         ▼                    ▼
    ┌─────────────┐   ┌──────────────────┐
    │ Conectar    │   │ ¿FortiClient     │
    │ OpenVPN     │   │ instalado?       │
    └──┬────┬─────┘   └──┬──────┬────────┘
       │    │            │      │ NO
      ✓ │    │✗           │ SÍ   │
       │    │            ▼      ▼
       │    └────┬──►Conectar  DEMO
       │         │ FortiClient  MODE
       │         │             (✓)
       │         ▼
       │      ┌─────────┐
       │      │ ✓ ó ✗   │
       │      └─────────┘
       │         │✗
       └────┬────┘
            │
            ▼
     ┌─────────────────┐
     │  DEMO MODE      │
     │  (Simulado)     │
     └─────────────────┘
```

---

## 🔍 Diagnóstico

**¿Por qué está usando DEMO MODE?**

1. Abre `logs/webdom_monitor.log`
2. Busca `VPN SERVICE INITIALIZED`
3. Verifica:
   - `OpenVPN disponible: False` → Instala OpenVPN
   - `FortiClient disponible: False` → Instala FortiClient
   - `Modo DEMO: True` → Está en modo de pruebas

**¿OpenVPN está instalado pero no funciona?**

```powershell
# Verifica la instalación
Test-Path "C:\Program Files\OpenVPN\bin\openvpn.exe"

# Mira los logs de OpenVPN
Get-Content "plants/ACAMPO/openvpn_ACAMPO.log" -Tail 50
```

---

## 💡 Recomendaciones

| Situación | Solución |
|-----------|----------|
| **Desarrollo/Demo** | `.\start_demo.ps1` |
| **Testing Local** | Instala OpenVPN + usa vpn.txt real |
| **Producción** | Instala OpenVPN + configura credenciales seguras |
| **Sin Acceso VPN** | Usa DEMO MODE indefinidamente |

---

## ✨ Ventajas del Nuevo Sistema

✅ **Automático:** Detecta qué está disponible  
✅ **Resiliente:** Fallback automático a otros métodos  
✅ **Sin Frustración:** DEMO MODE como última opción  
✅ **Logs Claros:** Ves exactamente qué está pasando  
✅ **Flexible:** Cambia `vpn.txt` y reinicia  

---

**¡Listo para usar!** 🚀
