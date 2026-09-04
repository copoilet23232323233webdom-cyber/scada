# 🏗️ ARQUITECTURA Y FLUJO DE WEBDOM MONITOR v2.0

## 1. ARQUITECTURA DE COMPONENTES

```
┌─────────────────────────────────────────────────────────────────────┐
│                                                                     │
│               WEBDOM MONITOR v2.0 - ARQUITECTURA                   │
│                      (Profesional SCADA)                           │
│                                                                     │
└─────────────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────────────┐
│                        FRONTEND LAYER                               │
├─────────────────────────────────────────────────────────────────────┤
│                                                                     │
│  React 18 + TypeScript + Vite                                      │
│  ├── http://localhost:5173                                         │
│  │                                                                 │
│  ├── 📱 Pages:                                                     │
│  │   ├── Login.tsx         (JWT Authentication)                    │
│  │   ├── Dashboard.tsx     (Vista de plantas, realtime WebSocket)  │
│  │   └── PlantDetail.tsx   (Gateways, Tarjetas, Alarmas)          │
│  │                                                                 │
│  ├── 🎨 Components:                                                │
│  │   └── Layout.tsx        (Menú lateral, header)                  │
│  │                                                                 │
│  └── 🔌 Services:                                                  │
│      └── api.ts            (Axios + JWT bearer token)              │
│                                                                     │
└─────────────────────────────────────────────────────────────────────┘
                           ↕ HTTP/WebSocket
┌─────────────────────────────────────────────────────────────────────┐
│                       API REST LAYER                                │
├─────────────────────────────────────────────────────────────────────┤
│                                                                     │
│  FastAPI (http://localhost:8000)                                   │
│  ├── /docs              (Swagger UI automático)                    │
│  ├── /health            (Estado del scheduler)                     │
│  │                                                                 │
│  └── /api/               (Endpoints REST)                          │
│      ├── /auth/          (Login, JWT)                             │
│      ├── /plants/        (CRUD plantas)                           │
│      ├── /gateways/      (CRUD gateways)                          │
│      ├── /cards/         (CRUD tarjetas)                          │
│      ├── /alarms/        (CRUD alarmas)                           │
│      ├── /users/         (Gestión usuarios)                       │
│      ├── /vpn/           (VPN manager)                            │
│      ├── /maintenance/   (Modo mantenimiento)                     │
│      └── /ws/            (WebSocket real-time)                    │
│                                                                     │
└─────────────────────────────────────────────────────────────────────┘
                           ↕ FastAPI depends
┌─────────────────────────────────────────────────────────────────────┐
│                    BUSINESS LOGIC LAYER                             │
├─────────────────────────────────────────────────────────────────────┤
│                                                                     │
│  ┌──────────────────────────────────────────────────────────────┐  │
│  │  SCHEDULER v2 (Background Task - Desacoplado)               │  │
│  ├──────────────────────────────────────────────────────────────┤  │
│  │  ├─ Ejecuta cada 5 minutos (configurable)                  │  │
│  │  ├─ Verifica recordatorios cada 1 hora                     │  │
│  │  ├─ Limpia datos cada 6 horas                              │  │
│  │  ├─ 24/7 funcionamiento                                     │  │
│  │  └─ INDEPENDIENTE del frontend                             │  │
│  └──────────────────────────────────────────────────────────────┘  │
│                           ↓                                         │
│  ┌──────────────────────────────────────────────────────────────┐  │
│  │  SCAN SERVICE v2 (Orquestación)                             │  │
│  ├──────────────────────────────────────────────────────────────┤  │
│  │  ├─ Detecta plantas en Plants/ (auto-discovery)           │  │
│  │  ├─ Parsea ips.txt y vpn.txt                              │  │
│  │  └─ Para cada planta:                                      │  │
│  │      └─ Conecta VPN → Escanea → Desconecta VPN            │  │
│  └──────────────────────────────────────────────────────────────┘  │
│                      ↓ (para cada Gateway)                         │
│  ┌──────────────────────────────────────────────────────────────┐  │
│  │  MODBUS SERVICE v2 (Protocolo TCP puro)                    │  │
│  ├──────────────────────────────────────────────────────────────┤  │
│  │  ├─ Descubre tarjetas automáticamente                      │  │
│  │  ├─ Lee registro 57624 (estado)                            │  │
│  │  ├─ Lee registro 57625 (voltaje)                           │  │
│  │  └─ Realiza 5 escaneos consecutivos                        │  │
│  │      └─ Consolida por mayoría (no falsas alarmas)         │  │
│  └──────────────────────────────────────────────────────────────┘  │
│                           ↓                                         │
│  ┌──────────────────────────────────────────────────────────────┐  │
│  │  VPN SERVICE v2 (Gestión de Conexiones)                    │  │
│  ├──────────────────────────────────────────────────────────────┤  │
│  │  ├─ FortiClient VPN (automático)                           │  │
│  │  ├─ OpenVPN (automático)                                   │  │
│  │  ├─ Auto-detecta tipo de VPN                              │  │
│  │  ├─ Valida conectividad antes de escanear                 │  │
│  │  └─ Garantiza: NUNCA 2 VPNs abiertas                       │  │
│  └──────────────────────────────────────────────────────────────┘  │
│                           ↓                                         │
│  ┌──────────────────────────────────────────────────────────────┐  │
│  │  ALARM DETECTOR v2 (Análisis Inteligente)                  │  │
│  ├──────────────────────────────────────────────────────────────┤  │
│  │  ├─ Analiza estado de Gateway                              │  │
│  │  ├─ Analiza estado de Tarjeta                              │  │
│  │  ├─ Genera alarmas automáticamente                         │  │
│  │  ├─ 3 estados: 🟢GREEN / 🟡YELLOW / 🔴RED                  │  │
│  │  └─ Envía email SOLO en alarma nueva (sin spam)            │  │
│  └──────────────────────────────────────────────────────────────┘  │
│                                                                     │
└─────────────────────────────────────────────────────────────────────┘
                           ↓ Guarda datos
┌─────────────────────────────────────────────────────────────────────┐
│                     DATABASE LAYER                                  │
├─────────────────────────────────────────────────────────────────────┤
│                                                                     │
│  SQLite (webdom_monitor.db)                                        │
│  ├── plants            (Plantas configuradas)                      │
│  ├── gateways          (Webdom Gateways)                          │
│  ├── cards             (Tarjetas I/O)                             │
│  ├── scans             (Histórico últimos 5 escaneos)             │
│  ├── alarms            (Alarmas activas/resueltas)                │
│  ├── users             (Usuarios + roles)                         │
│  └── [índices]         (Optimizados para búsquedas)               │
│                                                                     │
│  Características:                                                  │
│  ├─ ACID compliance                                               │
│  ├─ Índices para búsquedas rápidas                               │
│  ├─ Histórico limitado a 5 escaneos (sin bloat)                 │
│  └─ Limpieza automática de datos antiguos                        │
│                                                                     │
└─────────────────────────────────────────────────────────────────────┘
                           ↕ Lectura
┌─────────────────────────────────────────────────────────────────────┐
│                    EXTERNAL SYSTEMS                                 │
├─────────────────────────────────────────────────────────────────────┤
│                                                                     │
│  🔌 Webdom Gateways (Modbus TCP 502)                              │
│  ├─ 10.10.0.20, 10.10.0.21, 10.10.0.22, ...                     │
│  ├─ Modbus ID 1-32 (tarjetas por gateway)                        │
│  └─ Lectura cada 5 minutos (configurable)                        │
│                                                                     │
│  🔐 VPN (FortiClient/OpenVPN)                                     │
│  ├─ Conexión automática por planta                               │
│  ├─ Credenciales en vpn.txt (localizada)                         │
│  └─ Timeout automático                                           │
│                                                                     │
│  📧 Email Notificaciones (Gmail SMTP)                             │
│  ├─ Nueva alarma → EMAIL                                         │
│  ├─ Alarma activa >7 días → RECORDATORIO                         │
│  └─ Resolución → REGISTRO                                        │
│                                                                     │
└─────────────────────────────────────────────────────────────────────┘
```

---

## 2. FLUJO DE EJECUCIÓN (Ciclo de 5 minutos)

```
START
  │
  ├─► [SCHEDULER v2]
  │    └─► ¿Esperar 5 minutos?
  │        └─► Sí: Ejecutar ciclo
  │
  ├─► [AUTO-DISCOVERY]
  │    ├─► Buscar carpetas en Plants/
  │    ├─► Parsear ips.txt (IPs Gateways)
  │    ├─► Parsear vpn.txt (Config VPN)
  │    └─► Sincronizar con BD
  │
  ├─► [SCAN SERVICE]
  │    └─► Para cada Planta:
  │        │
  │        ├─► [VPN MANAGER]
  │        │    ├─► Leer vpn.txt
  │        │    ├─► Detectar tipo (FortiClient/OpenVPN)
  │        │    ├─► Conectar VPN
  │        │    └─► Esperar confirmación
  │        │
  │        ├─► [GATEWAY DISCOVERY]
  │        │    ├─► Para cada IP en ips.txt
  │        │    └─► TCP ping Modbus (puerto 502)
  │        │
  │        ├─► [MODBUS SCANNER] ✨ 5 ESCANEOS
  │        │    ├─► ESCANEO 1:
  │        │    │    ├─► Descubrir tarjetas activas
  │        │    │    ├─► Leer registros Modbus
  │        │    │    └─► Guardar resultados
  │        │    │
  │        │    ├─► ESCANEO 2: (idem)
  │        │    ├─► ESCANEO 3: (idem)
  │        │    ├─► ESCANEO 4: (idem)
  │        │    └─► ESCANEO 5: (idem)
  │        │
  │        ├─► [CONSOLIDAR RESULTADOS]
  │        │    ├─► Contar tarjetas en cada escaneo
  │        │    ├─► Si todos coinciden → USAR ESE RESULTADO
  │        │    └─► Si varían → USAR MÁS FRECUENTE
  │        │
  │        ├─► [GUARDAR EN BD]
  │        │    ├─► Actualizar tarjetas
  │        │    ├─► Guardar scan en histórico
  │        │    └─► Mantener solo últimos 5
  │        │
  │        ├─► [DETECTOR DE ALARMAS]
  │        │    ├─► Analizar estado Gateway
  │        │    ├─► Analizar estado Tarjeta
  │        │    ├─► Generar alarmas necesarias
  │        │    └─► Enviar emails (si es nueva)
  │        │
  │        └─► [VPN DISCONNECT]
  │            └─► Cerrar conexión VPN
  │
  ├─► [REMINDER CHECK] (Cada 1 hora)
  │    ├─► Buscar alarmas activas >7 días
  │    └─► Enviar recordatorios
  │
  ├─► [DATA CLEANUP] (Cada 6 horas)
  │    ├─► Eliminar scans >30 días
  │    └─► Eliminar alarmas resueltas >90 días
  │
  └─► ESPERAR 5 MINUTOS Y REPETIR
```

---

## 3. EJEMPLO REAL: ESCANEO DE 1 PLANTA

### Paso 1: DESCUBRIMIENTO (10 segundos)

```
Plants/
└── Olivenza/
    ├── ips.txt
    │   10.10.0.20  ← Gateway 1
    │   10.10.0.21  ← Gateway 2
    │   10.10.0.22  ← Gateway 3
    └── vpn.txt
        VPN_TYPE=forticlient
        VPN_NAME=OLIVENZA
        USER=admin
        PASSWORD=xxx

App detecta: 3 Gateways para Olivenza ✓
```

### Paso 2: CONECTAR VPN (15-30 segundos)

```
┌────────────────────────────────────────┐
│  VPN SERVICE                           │
├────────────────────────────────────────┤
│ 1. Parsear vpn.txt                    │
│    └─ Detecta: FortiClient VPN        │
│                                        │
│ 2. Buscar executable                  │
│    └─ Encontrado: C:\Program Files... │
│                                        │
│ 3. Conectar                           │
│    └─ Ejecutar FortiClient CLI        │
│                                        │
│ 4. Validar conexión (30 intentos)     │
│    └─ TCP socket a vpn.miempresa.com │
│                                        │
│ 5. Resultado: ✓ VPN CONECTADO         │
└────────────────────────────────────────┘
```

### Paso 3: ESCANEAR GATEWAYS (2-5 minutos)

```
GATEWAY 1: 10.10.0.20
├─ ESCANEO 1:
│  ├─ Descubrir tarjetas (IDs 1-32)
│  │  └─ Encontradas: 22 tarjetas
│  ├─ Leer registro 57624 (estado)
│  │  └─ Bit 5 = 1 (LoRa OK)
│  └─ Resultado: 22 OK ✓
│
├─ ESCANEO 2: → 22 OK ✓
├─ ESCANEO 3: → 22 OK ✓
├─ ESCANEO 4: → 22 OK ✓
└─ ESCANEO 5: → 22 OK ✓

CONSOLIDACIÓN:
├─ Todos coinciden: 22 tarjetas
├─ Confianza: 100%
└─ Resultado FINAL: 22 tarjetas ✓

GATEWAY 2: 10.10.0.21 → [IGUAL PROCESO]
GATEWAY 3: 10.10.0.22 → [IGUAL PROCESO]
```

### Paso 4: GENERAR ALARMAS (Instantáneo)

```
┌──────────────────────────────────────────┐
│  ALARM DETECTOR                          │
├──────────────────────────────────────────┤
│                                          │
│ ANÁLISIS GATEWAY 1 (10.10.0.20):        │
│ ├─ Total tarjetas: 22                   │
│ ├─ Sin comunicación: 0                  │
│ ├─ Respuesta: 450ms                     │
│ └─ ESTADO: 🟢 GREEN (OK)                │
│                                          │
│ ANÁLISIS GATEWAY 2 (10.10.0.21):        │
│ ├─ Total tarjetas: 22                   │
│ ├─ Sin comunicación: 4 (18%)            │
│ ├─ Respuesta: 620ms                     │
│ └─ ESTADO: 🟡 YELLOW                    │
│    └─ Generar alarma: "COMMUNICATION"   │
│                                          │
│ ANÁLISIS GATEWAY 3 (10.10.0.22):        │
│ ├─ No responde (timeout)                │
│ ├─ Tarjetas: 0                          │
│ └─ ESTADO: 🔴 RED                       │
│    └─ Generar alarma: "GATEWAY_DOWN"    │
│                                          │
└──────────────────────────────────────────┘

ALARMAS GENERADAS:
├─ Alarma 1: COMMUNICATION (Gateway 2)
│  └─ EMAIL ENVIADO: webdomreports@gmail.com
│
└─ Alarma 2: GATEWAY_DOWN (Gateway 3)
   └─ EMAIL ENVIADO: webdomreports@gmail.com
```

### Paso 5: GUARDAR EN BD (Instantáneo)

```
DATABASE
├─ plants
│  └─ Olivenza
│     ├─ status = YELLOW (1 rojo + 1 amarillo)
│     ├─ last_scan = 2024-07-08 10:30:00
│     └─ active_alarms = 2
│
├─ gateways
│  ├─ 10.10.0.20
│  │  ├─ status = GREEN
│  │  ├─ total_cards = 22
│  │  └─ response_time_ms = 450
│  │
│  ├─ 10.10.0.21
│  │  ├─ status = YELLOW
│  │  ├─ total_cards = 22
│  │  ├─ failed_cards = 4
│  │  └─ response_time_ms = 620
│  │
│  └─ 10.10.0.22
│     ├─ status = RED
│     ├─ total_cards = 0
│     └─ last_error = "No responde"
│
├─ scans
│  └─ Último scan de cada Gateway (límite 5)
│
└─ alarms
   ├─ Alarma COMMUNICATION (Active)
   └─ Alarma GATEWAY_DOWN (Active)
```

### Paso 6: DESCONECTAR VPN (5 segundos)

```
VPN SERVICE
├─ Terminar proceso FortiClient
├─ Limpiar archivos temporales
└─ Marcar: VPN_STATUS = disconnected
```

---

## 4. CICLOS SECUNDARIOS

### Cada 1 Hora: RECORDATORIOS DE ALARMAS

```
ALARMA: "COMMUNICATION" (desde hace 8 días)
├─ last_reminder = 2024-07-01
├─ ¿Hoy - last_reminder > 7 días?
│  └─ SÍ: 8 días > 7 días
├─ ENVIAR EMAIL: "Recordatorio Alarma Activa"
├─ Actualizar: last_reminder = 2024-07-08
└─ reminder_count = 8
```

### Cada 6 Horas: LIMPIEZA DE DATOS

```
CLEANUP PROCESS
├─ Encontrar: scans creados hace >30 días
│  └─ ELIMINAR (mantener solo últimos 5)
│
├─ Encontrar: alarmas resueltas hace >90 días
│  └─ ELIMINAR (archivo completado)
│
└─ Resultado: BD optimizada, sin bloat
```

---

## 5. ESTADOS Y TRANSICIONES

### Estados de Planta

```
                   ┌─────────────┐
                   │   UNKNOWN   │
                   └──────┬──────┘
                          │
                    Primer escaneo
                          │
            ┌─────────────┴─────────────┐
            │                           │
        ┌───▼───┐                   ┌──▼───┐
        │ GREEN │◄────────────────┐ │ RED  │
        └───┬───┘                 │ └──▲───┘
            │                     │    │
    Todos gateways OK         Error   Recovery
            │                     │    │
            └──────────────┬──────┘    │
                       ┌──▼──┐        │
                       │YELL │────────┘
                       └─────┘
                    Problemas
                    parciales
```

### Estados de Gateway

```
┌──────────┐
│ UNKNOWN  │
└────┬─────┘
     │
     ├─► 🟢 GREEN  (0 errores, respuesta <500ms)
     ├─► 🟡 YELLOW (parcial o respuesta 500-2000ms)
     └─► 🔴 RED    (no responde o >75% tarjetas caídas)
```

### Estados de Tarjeta

```
┌──────────┐
│ UNKNOWN  │
└────┬─────┘
     │
     ├─► 🟢 GREEN      (comunica OK)
     ├─► 🟡 YELLOW     (alarma SEC/Sobretensión)
     ├─► 🔴 RED        (no comunica)
     ├─► 🔧 MAINTENANCE (en mantenimiento, sin alarmas)
     └─► ⚫ DISABLED    (deshabilitada)
```

---

## 6. EJEMPLO DE FLUJO COMPLETO

### Timeline de Ejecución

```
10:00:00  Scheduler dispara
10:00:05  Auto-discovery: detecta 3 plantas
10:00:10  Olivenza: Conectar VPN (FortiClient)
10:00:30  Olivenza: VPN conectado ✓
10:00:35  Olivenza: Descubrir 3 Gateways
10:00:45  Olivenza: 5 escaneos de Gateway 1
10:01:15  Olivenza: 5 escaneos de Gateway 2
10:01:45  Olivenza: 5 escaneos de Gateway 3
10:02:00  Olivenza: Generar 2 alarmas
10:02:05  Olivenza: Guardar en BD
10:02:10  Olivenza: Desconectar VPN
10:02:15  Olivenza: COMPLETO ✓

10:02:20  Torralba: Conectar VPN (OpenVPN)
10:02:40  Torralba: VPN conectado ✓
10:02:45  Torralba: [Similar proceso...]
10:03:45  Torralba: COMPLETO ✓

10:03:50  RioDoPeixe: Conectar VPN
10:04:00  RioDoPeixe: [Similar proceso...]
10:05:00  RioDoPeixe: COMPLETO ✓

10:05:05  Ciclo COMPLETADO
          Dormir hasta 10:05:00 del siguiente ciclo
```

---

## 7. DESACOPLAMIENTO: LA VENTAJA CRÍTICA

### Escenario 1: Sin Desacoplamiento (v1.0)

```
10:00:00  Frontend hace request → Backend inicia escaneo
10:00:30  Usuario reinicia frontend (cierra navegador)
10:00:31  ❌ Escaneo se interrumpe
10:00:32  Base de datos inconsistente
10:05:00  Siguiente escaneo NO ocurre
RESULTADO: ❌ PÉRDIDA DE DATOS, NO CONFIABLE
```

### Escenario 2: Con Desacoplamiento (v2.0)

```
10:00:00  Scheduler (proceso independiente) inicia escaneo
10:00:30  Usuario reinicia frontend (cierra navegador)
10:00:31  Frontend cierra pero...
10:00:32  ✅ Backend SIGUE ESCANEANDO
10:00:32  ✅ BD se actualiza normalmente
10:05:00  ✅ Siguiente escaneo ocurre automáticamente
RESULTADO: ✅ FUNCIONA SIEMPRE, 24/7 CONFIABLE
```

---

**La clave es: El escaneo NO depende del frontend. Es un proceso autónomo.**

**Versión:** 2.0.0  
**Última actualización:** 2024-07-08
