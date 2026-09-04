# Sistema VPN automático

El servicio VPN (`app/services/vpn_service_v2.py`) conecta la planta de forma
automática, comprueba que el túnel realmente alcanza los gateways y lo mantiene
vivo con un watchdog que reconecta solo.

## Cómo elige el cliente

El tipo declarado en `vpn.txt` decide qué clientes se prueban. Sólo se intentan
clientes que hablan el mismo protocolo y que están instalados en la máquina:

| `VPN_TYPE`             | Clientes probados, en orden                                                  |
|------------------------|------------------------------------------------------------------------------|
| `openvpn`              | OpenVPN                                                                       |
| `forticlient` (SSL)    | openfortivpn → FortiClient CLI → OpenConnect (`--protocol=fortinet`)          |
| `forticlient` + `SUBTYPE=ipsec` | VPN nativa de Windows (L2TP/IPsec y luego IKEv2)                     |
| `openconnect`          | OpenConnect → openfortivpn                                                    |
| `ssh`                  | Túnel SSH con port-forwarding al puerto Modbus                                |
| `demo`                 | Simulación (también si `DEMO_MODE=true`)                                      |

En Windows, si `VPN_TYPE=forticlient` y no hay ningún cliente SSL, el servicio
descarga un `openfortivpn` portable en `bin/`.

La conexión se reintenta `VPN_CONNECT_RETRIES` veces con backoff exponencial.

## Qué se considera "conectado"

Que el cliente diga que el túnel está arriba no basta: el servicio abre una
conexión TCP al puerto Modbus (`MODBUS_PORT`) de las IPs de gateway de la planta
y sólo da la conexión por buena cuando alguna responde. Los escaneos, los
informes y el control multi-gateway pasan esas IPs al conectar, así que ya no
hay esperas fijas de "estabilización de rutas".

## Watchdog y reconexión

Cada `VPN_HEALTH_INTERVAL_SECONDS` se vuelve a comprobar el túnel. Si deja de
responder, la VPN se cierra y se reconecta con la misma configuración; el
contador de reconexiones aparece en el diagnóstico.

## Configuración

`plants/<PLANTA>/vpn.txt`, un `clave=valor` por línea.

OpenVPN:

```
VPN_TYPE=openvpn
CONFIG=mtech.ovpn
USER=<usuario>
PASSWORD=<contraseña>
KEY_PASSWORD=<contraseña de la clave privada>
```

`CONFIG` admite una ruta absoluta de otra máquina (p. ej. la de Windows con la
que se configuró la planta): si no existe, se busca el mismo nombre de archivo
dentro de la carpeta de la planta.

FortiClient SSL:

```
VPN_TYPE=forticlient
HOST=vpn.empresa.com
PORT=10443
USER=<usuario>
PASSWORD=<contraseña>
# opcionales: REALM, TRUSTED_CERT, ALLOW_INSECURE=true
```

FortiClient IPsec (Windows):

```
VPN_TYPE=forticlient
SUBTYPE=ipsec
HOST=vpn.empresa.com
PSK=<clave precompartida>
USER=<usuario>
PASSWORD=<contraseña>
```

Túnel SSH:

```
VPN_TYPE=ssh
SSH_HOST=<host>
SSH_PORT=22
SSH_USER=<usuario>
SSH_PASSWORD=<contraseña>   # o SSH_KEY_PATH=<ruta a la clave>
```

Ajustes globales en `.env`:

```
VPN_CONNECT_TIMEOUT=45
VPN_VERIFY_TIMEOUT=20
VPN_CONNECT_RETRIES=3
VPN_AUTO_RECONNECT=true
VPN_HEALTH_INTERVAL_SECONDS=60
```

## Diagnóstico

- `GET /api/vpn/diagnostics`: clientes detectados, método en uso, uptime,
  gateways sondeados, resultado de la última comprobación y último error.
- `POST /api/vpn/health-check`: comprueba el túnel en el momento.
- `POST /api/vpn/reconnect?plant_name=...`: reconexión limpia.
- `GET /health`: incluye el mismo diagnóstico VPN.

La página de control multi-gateway muestra todo eso en la barra superior, con
botones de conectar, reconectar, desconectar y comprobar túnel.

## Credenciales

Los ficheros de credenciales que necesitan los clientes se generan en
`logs/vpn_credentials/` con permisos de sólo-usuario y se borran al desconectar.
Nunca se escriben dentro de `plants/`.
