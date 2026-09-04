"""
Servicio VPN multiplataforma con conexión automática.

Soporta OpenVPN, FortiClient (SSL vía openfortivpn / IPsec vía VPN nativa de
Windows), OpenConnect y túneles SSH.  El servicio detecta qué clientes hay
instalados, prueba únicamente los métodos compatibles con el `vpn.txt` de la
planta, verifica que el túnel realmente alcanza los gateways y mantiene la
conexión viva con un watchdog que reconecta de forma automática.
"""
import asyncio
import logging
import os
import shutil
import socket
import stat
import subprocess
import threading
import time
import urllib.request
import zipfile
from typing import Dict, List, Optional, Tuple

from app.core.config import settings

logger = logging.getLogger(__name__)

IS_WINDOWS = os.name == 'nt'

BASE_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
LOGS_DIR = os.path.join(BASE_DIR, 'logs')
CREDS_DIR = os.path.join(LOGS_DIR, 'vpn_credentials')
VPN_PID_FILE = os.path.join(LOGS_DIR, 'vpn_pid.txt')
PLANTS_DIR = os.path.join(BASE_DIR, 'plants')


def resolve_plant_vpn_file(plant_path: Optional[str], plant_name: str) -> Optional[str]:
    """Localiza el vpn.txt de una planta.

    La ruta guardada en la base de datos puede venir de otra máquina (p. ej.
    `C:\\SCADA_MOHAMED\\plants\\ACAMPO`), así que se cae a `plants/<nombre>`
    dentro del proyecto.
    """
    candidates = []
    if plant_path:
        candidates.append(os.path.join(plant_path, 'vpn.txt'))
        basename = plant_path.replace('\\', '/').rstrip('/').rsplit('/', 1)[-1]
        if basename:
            candidates.append(os.path.join(PLANTS_DIR, basename, 'vpn.txt'))
    candidates.append(os.path.join(PLANTS_DIR, plant_name, 'vpn.txt'))

    for candidate in candidates:
        if os.path.isfile(candidate):
            return candidate
    return None

# Métodos que puede usar cada tipo de VPN declarado en vpn.txt, en orden de
# preferencia. El servicio filtra los que no están instalados en la máquina.
METHODS_BY_TYPE: Dict[str, List[str]] = {
    'openvpn': ['openvpn'],
    'forticlient': ['openfortivpn', 'forticlient_cli', 'openconnect', 'windows_vpn'],
    'openconnect': ['openconnect', 'openfortivpn'],
    'ssh': ['ssh'],
}


class VPNConfig:
    def __init__(self, vpn_file: str):
        self.vpn_file = vpn_file
        self.vpn_type: Optional[str] = None
        self.vpn_subtype: Optional[str] = None
        self.is_valid = False
        self.config_dict: Dict[str, str] = {}
        self._parse()

    def _parse(self):
        try:
            with open(self.vpn_file, 'r', encoding='utf-8-sig') as f:
                for line in f:
                    line = line.strip()
                    if not line or line.startswith('#'):
                        continue
                    if '=' in line:
                        key, val = line.split('=', 1)
                        self.config_dict[key.strip().upper()] = val.strip()

            vpn_type = self.config_dict.get('VPN_TYPE', '').lower()
            if vpn_type == 'forticlient':
                self.vpn_type = 'forticlient'
            elif vpn_type in ('openconnect', 'anyconnect', 'ssl'):
                self.vpn_type = 'openconnect'
            elif vpn_type == 'openvpn':
                self.vpn_type = 'openvpn'
            elif vpn_type == 'ssh':
                self.vpn_type = 'ssh'
            elif vpn_type == 'demo':
                self.vpn_type = 'demo'

            self.vpn_subtype = self.config_dict.get('SUBTYPE', 'ssl').lower()

            if self.vpn_type == 'forticlient':
                self.is_valid = 'HOST' in self.config_dict
            elif self.vpn_type == 'openconnect':
                self.is_valid = 'HOST' in self.config_dict and 'USER' in self.config_dict
            elif self.vpn_type == 'openvpn':
                self.is_valid = self.resolved_config_path() is not None
            elif self.vpn_type == 'ssh':
                self.is_valid = 'SSH_HOST' in self.config_dict
            elif self.vpn_type == 'demo':
                self.is_valid = True

            logger.info(f"VPN {vpn_type} parseado: valid={self.is_valid}")

        except Exception as e:
            logger.error(f"Error parseando VPN {self.vpn_file}: {e}")
            self.is_valid = False

    def get(self, key: str, default=None):
        return self.config_dict.get(key.upper(), default)

    def resolved_config_path(self) -> Optional[str]:
        """Ruta real del .ovpn.

        `CONFIG` suele venir con una ruta absoluta de la máquina donde se
        configuró la planta (p. ej. ``C:\\SCADA_MOHAMED\\plants\\ACAMPO\\mtech.ovpn``).
        Si esa ruta no existe se busca el fichero por su nombre dentro de la
        carpeta de la planta, y si tampoco está, cualquier .ovpn de la carpeta.
        """
        plant_dir = os.path.dirname(os.path.abspath(self.vpn_file))
        declared = self.get('CONFIG')

        if declared:
            if os.path.isfile(declared):
                return declared
            basename = declared.replace('\\', '/').rsplit('/', 1)[-1]
            candidate = os.path.join(plant_dir, basename)
            if os.path.isfile(candidate):
                return candidate

        try:
            ovpns = sorted(f for f in os.listdir(plant_dir) if f.lower().endswith('.ovpn'))
        except OSError:
            ovpns = []
        if ovpns:
            return os.path.join(plant_dir, ovpns[0])
        return None


class VPNServiceV2:
    def __init__(self):
        self.current_vpn_process = None
        self.current_vpn_config: Optional[VPNConfig] = None
        self.current_plant_name: Optional[str] = None
        self.current_method: Optional[str] = None
        self.temp_files: List[str] = []
        self.vpn_connected = False
        self.connection_start_time: Optional[float] = None
        self.ssh_client = None
        self.ssh_transport = None
        self.ssh_forward_ports: Dict[str, int] = {}
        self.ssh_forward_threads: List[threading.Thread] = []
        self._vpn_connection_name: Optional[str] = None

        # Estado de la conexión activa (permite reutilizarla y reconectarla)
        self._connected_plant: Optional[str] = None
        self._connected_vpn_file: Optional[str] = None
        self._connected_routes: Optional[List[str]] = None
        self._health_targets: List[str] = []

        self.last_error: Optional[str] = None
        self.last_health_check: Optional[float] = None
        self.last_health_ok: Optional[bool] = None
        self.reconnect_count = 0

        # Serializa las operaciones VPN: varias peticiones simultáneas peleando
        # por el mismo adaptador se matan entre sí.
        self._vpn_lock = asyncio.Lock()
        # Se incrementa en cada cambio de conexión para que el watchdog descarte
        # los sondeos que empezaron con una conexión anterior.
        self._connection_generation = 0
        self._monitor_task: Optional[asyncio.Task] = None

        self.openvpn_exe = self._find_openvpn()
        self.openfortivpn_exe = self._find_openfortivpn()
        self.openconnect_exe = self._find_openconnect()
        self.forticlient_exe = self._find_forticlient()
        self.windows_vpn_available = self._check_windows_vpn_available()

        self.demo_mode = settings.DEMO_MODE
        self.available_vpn_methods = self._detect_available_methods()

        logger.info("=== VPN SERVICE INITIALIZED ===")
        logger.info(f"Plataforma: {'Windows' if IS_WINDOWS else 'POSIX'}")
        logger.info(f"OpenVPN: {self.openvpn_exe or 'NO ENCONTRADO'}")
        logger.info(f"OpenFortiVPN: {self.openfortivpn_exe or 'NO ENCONTRADO'}")
        logger.info(f"OpenConnect: {self.openconnect_exe or 'NO ENCONTRADO'}")
        logger.info(f"FortiClient CLI: {self.forticlient_exe or 'NO ENCONTRADO'}")
        logger.info(f"Windows VPN: {'DISPONIBLE' if self.windows_vpn_available else 'NO DISPONIBLE'}")
        logger.info(f"DEMO mode: {self.demo_mode}")
        logger.info(f"Métodos disponibles: {self.available_vpn_methods}")

    # ------------------------------------------------------------------
    # Detección de clientes VPN
    # ------------------------------------------------------------------

    def _detect_available_methods(self) -> List[str]:
        methods = []
        if self.openvpn_exe:
            methods.append('openvpn')
        if self.openfortivpn_exe:
            methods.append('openfortivpn')
        if self.openconnect_exe:
            methods.append('openconnect')
        if self.forticlient_exe:
            methods.append('forticlient_cli')
        if self.windows_vpn_available:
            methods.append('windows_vpn')
        methods.append('ssh')  # paramiko siempre disponible
        if self.demo_mode:
            methods.append('demo')
        return methods

    def _check_windows_vpn_available(self) -> bool:
        if not IS_WINDOWS:
            return False
        try:
            result = subprocess.run(
                ['powershell', '-NoProfile', '-Command',
                 'Get-Command Add-VpnConnection -ErrorAction SilentlyContinue'],
                capture_output=True, text=True, timeout=10
            )
            return result.returncode == 0
        except Exception:
            return False

    @staticmethod
    def _first_existing(paths: List[Optional[str]]) -> Optional[str]:
        for path in paths:
            if path and os.path.isfile(path):
                return path
        return None

    def _find_openvpn(self) -> Optional[str]:
        candidates: List[Optional[str]] = [settings.VPN_EXECUTABLE_OPENVPN, shutil.which('openvpn')]
        if IS_WINDOWS:
            candidates += [
                r'C:\Program Files\OpenVPN\bin\openvpn.exe',
                r'C:\Program Files (x86)\OpenVPN\bin\openvpn.exe',
                shutil.which('openvpn.exe'),
            ]
        else:
            candidates += ['/usr/sbin/openvpn', '/usr/bin/openvpn', '/usr/local/sbin/openvpn']
        found = self._first_existing(candidates)
        if found:
            logger.info(f"OpenVPN encontrado: {found}")
        return found

    def _find_openfortivpn(self) -> Optional[str]:
        candidates: List[Optional[str]] = [
            shutil.which('openfortivpn'),
            os.path.join(BASE_DIR, 'bin', 'openfortivpn.exe' if IS_WINDOWS else 'openfortivpn'),
        ]
        if not IS_WINDOWS:
            candidates += ['/usr/bin/openfortivpn', '/usr/local/bin/openfortivpn']
        found = self._first_existing(candidates)
        if found:
            logger.info(f"OpenFortiVPN encontrado: {found}")
        return found

    def _find_openconnect(self) -> Optional[str]:
        candidates: List[Optional[str]] = [shutil.which('openconnect')]
        if IS_WINDOWS:
            candidates += [
                r'C:\Program Files\OpenConnect\openconnect.exe',
                r'C:\Program Files (x86)\OpenConnect\openconnect.exe',
            ]
        else:
            candidates += ['/usr/sbin/openconnect', '/usr/bin/openconnect']
        found = self._first_existing(candidates)
        if found:
            logger.info(f"OpenConnect encontrado: {found}")
        return found

    def _find_forticlient(self) -> Optional[str]:
        """CLI de FortiClient (FortiSSLVPNclient.exe) para conexión desatendida."""
        if not IS_WINDOWS:
            return None
        declared = settings.VPN_EXECUTABLE_FORTICLIENT
        candidates = [
            os.path.join(os.path.dirname(declared), 'FortiSSLVPNclient.exe') if declared else None,
            r'C:\Program Files\Fortinet\FortiClient\FortiSSLVPNclient.exe',
            r'C:\Program Files (x86)\Fortinet\FortiClient\FortiSSLVPNclient.exe',
        ]
        found = self._first_existing(candidates)
        if found:
            logger.info(f"FortiClient CLI encontrado: {found}")
        return found

    # ------------------------------------------------------------------
    # Utilidades
    # ------------------------------------------------------------------

    def parse_vpn_config(self, vpn_file: str) -> VPNConfig:
        return VPNConfig(vpn_file)

    def _write_secret_file(self, name: str, content: str) -> str:
        """Escribe credenciales fuera de la carpeta de la planta y con permisos
        restringidos, y las registra para borrarlas al desconectar."""
        os.makedirs(CREDS_DIR, exist_ok=True)
        path = os.path.join(CREDS_DIR, name)
        with open(path, 'w', encoding='utf-8') as f:
            f.write(content)
        try:
            os.chmod(path, stat.S_IRUSR | stat.S_IWUSR)
        except OSError:
            pass
        self.temp_files.append(path)
        return path

    def _cleanup_temp_files(self):
        for f in self.temp_files:
            try:
                if os.path.exists(f):
                    os.remove(f)
            except OSError:
                pass
        self.temp_files = []

    async def check_ip_connectivity(self, test_ip: str, timeout: float = 3.0) -> Tuple[bool, float]:
        """Comprueba el puerto Modbus del gateway sin bloquear el event loop."""
        start = time.time()
        try:
            fut = asyncio.open_connection(test_ip, settings.MODBUS_PORT)
            reader, writer = await asyncio.wait_for(fut, timeout=timeout)
            writer.close()
            try:
                await writer.wait_closed()
            except Exception:
                pass
            return True, (time.time() - start) * 1000
        except Exception:
            return False, (time.time() - start) * 1000

    async def verify_tunnel(self, targets: Optional[List[str]] = None,
                            timeout: float = 20.0) -> bool:
        """El túnel se considera operativo cuando responde al menos un gateway."""
        if self.current_method == 'demo':
            return self.vpn_connected
        if self.current_method == 'ssh':
            # Los gateways sólo son alcanzables a través de los forwards locales,
            # no por su IP real, así que se comprueba el transporte SSH.
            return bool(self.ssh_transport and self.ssh_transport.is_active())

        targets = targets or self._health_targets
        if not targets:
            # Sin objetivos que sondear sólo podemos fiarnos del proceso cliente.
            return self._client_process_alive()

        deadline = time.time() + timeout
        while True:
            results = await asyncio.gather(
                *[self.check_ip_connectivity(ip) for ip in targets]
            )
            for ip, (ok, ms) in zip(targets, results):
                if ok:
                    logger.info(f"Túnel verificado: {ip}:{settings.MODBUS_PORT} responde ({ms:.0f} ms)")
                    return True
            if time.time() >= deadline:
                return False
            await asyncio.sleep(1)

    def _client_process_alive(self) -> bool:
        proc = self.current_vpn_process
        if proc is None:
            return self.ssh_transport is not None and self.ssh_transport.is_active()
        poll = getattr(proc, 'poll', None)
        if poll is not None:
            return poll() is None
        return proc.returncode is None

    def _mark_connected(self, plant_name: str, method: str, config: VPNConfig):
        self.vpn_connected = True
        self.connection_start_time = time.time()
        self.current_plant_name = plant_name
        self.current_method = method
        self.current_vpn_config = config
        self.last_error = None

    # ------------------------------------------------------------------
    # OpenVPN
    # ------------------------------------------------------------------

    def _kill_previous_openvpn(self, routes: Optional[List[str]] = None):
        """Libera el adaptador de túnel y las rutas que dejó una sesión previa.

        En Windows una IP o ruta huérfana en un TAP anterior hace que OpenVPN
        aborte con 'Initialization Sequence Completed With Errors'.
        """
        if IS_WINDOWS:
            try:
                subprocess.run(['taskkill', '/F', '/IM', 'openvpn.exe'],
                               capture_output=True, text=True, timeout=10)
            except Exception as e:
                logger.debug(f"No se pudieron matar procesos OpenVPN previos: {e}")
            for prefix in (routes or []):
                try:
                    subprocess.run(
                        ['powershell', '-NoProfile', '-Command',
                         f"Get-NetRoute -DestinationPrefix '{prefix}' -ErrorAction SilentlyContinue | "
                         "Remove-NetRoute -Confirm:$false -ErrorAction SilentlyContinue"],
                        capture_output=True, text=True, timeout=10
                    )
                except Exception as e:
                    logger.debug(f"No se pudo limpiar la ruta {prefix}: {e}")
        else:
            try:
                subprocess.run(['pkill', '-f', 'openvpn --config'],
                               capture_output=True, text=True, timeout=10)
            except Exception as e:
                logger.debug(f"No se pudieron matar procesos OpenVPN previos: {e}")
        time.sleep(1)

    async def connect_openvpn(self, config: VPNConfig, plant_name: str,
                              routes: Optional[List[str]] = None) -> bool:
        if not self.openvpn_exe:
            logger.warning("OpenVPN no está instalado")
            return False

        config_file = config.resolved_config_path()
        if not config_file:
            logger.error(f"No se encontró ningún .ovpn para {plant_name}")
            return False

        user = config.get('USER')
        password = config.get('PASSWORD')
        key_password = config.get('KEY_PASSWORD')

        self._kill_previous_openvpn(routes)

        base_dir = os.path.dirname(config_file)
        self.cleanup_old_logs(base_dir, plant_name)
        log_file = os.path.join(base_dir, f'openvpn_{plant_name}_{int(time.time())}.log')

        cmd = [self.openvpn_exe, '--config', config_file]
        if IS_WINDOWS:
            # tap-windows6 + netsh: wintun exige privilegios SYSTEM y el DHCP de
            # Windows deja la interfaz sin IP en esta instalación.
            cmd += ['--windows-driver', 'tap-windows6', '--ip-win32', 'netsh']
        cmd += ['--route-metric', '1', '--verb', '3', '--log', log_file]
        # El .ovpn de planta negocia AES-128-CBC, que DCO no admite.
        cmd += ['--data-ciphers', 'AES-256-GCM:AES-128-GCM:AES-128-CBC']

        if user and password:
            auth_file = self._write_secret_file(f'auth_{plant_name}.txt', f'{user}\n{password}\n')
            cmd += ['--auth-user-pass', auth_file]
        if key_password:
            askpass_file = self._write_secret_file(f'keypass_{plant_name}.txt', f'{key_password}\n')
            cmd += ['--askpass', askpass_file]

        logger.info(f"Conectando OpenVPN para {plant_name}: {config_file}")
        try:
            self.current_vpn_process = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                cwd=base_dir,
                text=True,
                encoding='utf-8',
                errors='replace',
                creationflags=subprocess.CREATE_NO_WINDOW if IS_WINDOWS else 0,
            )
        except Exception as e:
            self.last_error = f"No se pudo iniciar OpenVPN: {e}"
            logger.warning(self.last_error)
            return False

        logger.info(f"OpenVPN PID: {self.current_vpn_process.pid}")

        initialized = await self._await_openvpn_init(log_file, timeout=settings.VPN_CONNECT_TIMEOUT)
        if not initialized:
            logger.warning("OpenVPN no reportó 'Initialization Sequence Completed'")

        # La señal del log no garantiza que las rutas estén puestas: la prueba
        # real es alcanzar un gateway.
        if await self.verify_tunnel(timeout=settings.VPN_VERIFY_TIMEOUT):
            self._mark_connected(plant_name, 'openvpn', config)
            logger.info(f"OpenVPN operativo para {plant_name}")
            return True

        if initialized and not self._health_targets:
            self._mark_connected(plant_name, 'openvpn', config)
            return True

        self.last_error = f"OpenVPN no alcanzó los gateways de {plant_name} (ver {log_file})"
        logger.error(self.last_error)
        self._terminate_process()
        return False

    async def _await_openvpn_init(self, log_file: str, timeout: float) -> bool:
        start = time.time()
        while time.time() - start < timeout:
            try:
                if os.path.exists(log_file):
                    with open(log_file, 'r', encoding='utf-8', errors='replace') as f:
                        if 'Initialization Sequence Completed' in f.read():
                            logger.info("OpenVPN inicializado")
                            return True
            except OSError:
                pass
            proc = self.current_vpn_process
            if proc is not None and proc.poll() is not None:
                # En Windows el CLI termina tras delegar en el servicio
                # interactivo, así que salir no implica fallo.
                logger.info(f"Proceso OpenVPN terminó (exit={proc.returncode})")
                return False
            await asyncio.sleep(1)
        return False

    def _terminate_process(self):
        proc = self.current_vpn_process
        if proc is None:
            return
        try:
            proc.terminate()
        except Exception:
            pass
        self.current_vpn_process = None

    # ------------------------------------------------------------------
    # FortiClient / SSL VPN
    # ------------------------------------------------------------------

    async def _ensure_openfortivpn(self) -> Optional[str]:
        if self.openfortivpn_exe:
            return self.openfortivpn_exe
        if not IS_WINDOWS:
            return None
        # Binario portable para Windows: evita depender de una instalación previa.
        url = ("https://github.com/adrienverge/openfortivpn/releases/download/v1.22.0/"
               "openfortivpn-win64.zip")
        download_dir = os.path.join(BASE_DIR, 'bin')
        os.makedirs(download_dir, exist_ok=True)
        zip_path = os.path.join(download_dir, 'openfortivpn-win64.zip')
        try:
            logger.info(f"Descargando openfortivpn desde {url}...")
            await asyncio.to_thread(urllib.request.urlretrieve, url, zip_path)
            exe_path = os.path.join(download_dir, 'openfortivpn.exe')
            with zipfile.ZipFile(zip_path, 'r') as zf:
                # Se extrae sólo el ejecutable y por su basename: un zip remoto
                # con rutas absolutas o '..' no debe escribir fuera de bin/.
                member = next(
                    (m for m in zf.namelist()
                     if os.path.basename(m).lower() == 'openfortivpn.exe'),
                    None
                )
                if member:
                    with zf.open(member) as src, open(exe_path, 'wb') as dst:
                        shutil.copyfileobj(src, dst)
            if os.path.isfile(exe_path):
                self.openfortivpn_exe = exe_path
                logger.info(f"openfortivpn descargado: {exe_path}")
                return exe_path
        except Exception as e:
            logger.warning(f"No se pudo obtener openfortivpn: {e}")
        finally:
            if os.path.exists(zip_path):
                try:
                    os.remove(zip_path)
                except OSError:
                    pass
        return None

    async def _connect_ssl_openfortivpn(self, config: VPNConfig, plant_name: str) -> bool:
        host = config.get('HOST')
        port = int(config.get('PORT', '10443'))
        user = config.get('USER')
        password = config.get('PASSWORD')

        if not host or not user:
            logger.error("HOST y USER son obligatorios para SSL VPN")
            return False

        exe = await self._ensure_openfortivpn()
        if not exe:
            logger.warning("openfortivpn no disponible")
            return False

        logger.info(f"Conectando SSL VPN (openfortivpn): {host}:{port}")
        args = [exe, f'{host}:{port}', '--username', user, '--pppd-log',
                os.path.join(LOGS_DIR, f'ofvpn_{plant_name}.log')]
        if password:
            args.append('--password-on-stdin')
        if config.get('REALM'):
            args += ['--realm', config.get('REALM')]
        if config.get('TRUSTED_CERT'):
            args += ['--trusted-cert', config.get('TRUSTED_CERT')]
        if str(config.get('ALLOW_INSECURE', '')).lower() in ('1', 'true', 'yes'):
            args.append('--insecure-ssl')

        try:
            proc = await asyncio.create_subprocess_exec(
                *args,
                stdin=asyncio.subprocess.PIPE,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.STDOUT,
            )
        except Exception as e:
            self.last_error = f"No se pudo iniciar openfortivpn: {e}"
            logger.warning(self.last_error)
            return False

        if password and proc.stdin:
            proc.stdin.write(f"{password}\n".encode())
            await proc.stdin.drain()

        tunnel_up = await self._await_tunnel_line(
            proc, ('tunnel is up', 'tunnel is up and running', 'connected'),
            timeout=settings.VPN_CONNECT_TIMEOUT, tag='openfortivpn'
        )
        self.current_vpn_process = proc

        if tunnel_up and await self.verify_tunnel(timeout=settings.VPN_VERIFY_TIMEOUT):
            self._mark_connected(plant_name, 'openfortivpn', config)
            return True
        if tunnel_up and not self._health_targets:
            self._mark_connected(plant_name, 'openfortivpn', config)
            return True

        self.last_error = f"openfortivpn no estableció el túnel para {plant_name}"
        logger.warning(self.last_error)
        await self._kill_async_process(proc)
        self.current_vpn_process = None
        return False

    async def _connect_forticlient_cli(self, config: VPNConfig, plant_name: str) -> bool:
        """Conexión desatendida con el CLI que instala FortiClient en Windows."""
        if not self.forticlient_exe:
            return False
        host = config.get('HOST')
        port = config.get('PORT', '10443')
        user = config.get('USER')
        password = config.get('PASSWORD')
        if not host or not user:
            return False

        logger.info(f"Conectando FortiClient CLI: {host}:{port}")
        args = [self.forticlient_exe, 'connect', '-h', f'{host}:{port}', '-u', f'{user}:{password or ""}']
        if str(config.get('ALLOW_INSECURE', '')).lower() in ('1', 'true', 'yes'):
            args.append('-i')
        try:
            proc = await asyncio.create_subprocess_exec(
                *args, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.STDOUT
            )
        except Exception as e:
            logger.warning(f"No se pudo iniciar FortiClient CLI: {e}")
            return False

        self.current_vpn_process = proc
        if await self.verify_tunnel(timeout=settings.VPN_CONNECT_TIMEOUT):
            self._mark_connected(plant_name, 'forticlient_cli', config)
            return True

        await self._kill_async_process(proc)
        self.current_vpn_process = None
        return False

    async def _await_tunnel_line(self, proc, needles: Tuple[str, ...],
                                 timeout: float, tag: str) -> bool:
        deadline = time.time() + timeout
        while time.time() < deadline:
            try:
                line = await asyncio.wait_for(proc.stdout.readline(), timeout=5)
            except asyncio.TimeoutError:
                if proc.returncode is not None:
                    return False
                continue
            if not line:
                return False
            decoded = line.decode('utf-8', errors='replace').strip()
            if decoded:
                logger.info(f"[{tag}] {decoded}")
            low = decoded.lower()
            if any(n in low for n in needles):
                return True
            if 'authentication failed' in low or 'permission denied' in low:
                self.last_error = decoded
                return False
        return False

    @staticmethod
    async def _kill_async_process(proc):
        if proc is None or proc.returncode is not None:
            return
        try:
            proc.terminate()
            await asyncio.wait_for(proc.wait(), timeout=5)
        except Exception:
            try:
                proc.kill()
            except Exception:
                pass

    async def _connect_ipsec_windows(self, config: VPNConfig, plant_name: str,
                                     routes: Optional[List[str]] = None) -> bool:
        """VPN IPsec usando el cliente nativo de Windows (L2TP/IPsec, luego IKEv2)."""
        if not self.windows_vpn_available:
            return False

        vpn_name = config.get('VPN_NAME', plant_name)
        host = config.get('HOST')
        if not host:
            return False

        script_path = os.path.join(BASE_DIR, 'scripts', 'vpn_connect_windows.ps1')
        if not os.path.isfile(script_path):
            logger.error(f"Script no encontrado: {script_path}")
            return False

        psk = config.get('PSK')
        user = config.get('USER')
        password = config.get('PRIVATE_KEY') or config.get('PASSWORD')

        async def run_script(tunnel_type: str) -> bool:
            ps_args = [
                'powershell', '-NoProfile', '-ExecutionPolicy', 'Bypass',
                '-File', script_path,
                '-Action', 'connect_and_cleanup',
                '-Name', vpn_name,
                '-ServerAddress', host,
                '-TunnelType', tunnel_type,
            ]
            if psk:
                ps_args += ['-PresharedKey', psk]
            if user:
                ps_args += ['-Username', user]
            if password:
                ps_args += ['-Password', password]
            for r in (routes or []):
                ps_args += ['-Routes', r]
            try:
                result = await asyncio.to_thread(
                    subprocess.run, ps_args, capture_output=True, text=True, timeout=90
                )
            except Exception as e:
                logger.warning(f"Error ejecutando script VPN ({tunnel_type}): {e}")
                return False
            output = (result.stdout or '') + (result.stderr or '')
            for line in output.splitlines():
                if line.strip():
                    logger.info(f"  [{tunnel_type}] {line.strip()}")
            return 'STATUS:CONNECTED' in output

        for tunnel_type in ('L2tp', 'Ikev2'):
            logger.info(f"Intentando VPN nativa de Windows ({tunnel_type})...")
            if await run_script(tunnel_type):
                self._vpn_connection_name = vpn_name
                self._mark_connected(plant_name, 'windows_vpn', config)
                if await self.verify_tunnel(timeout=settings.VPN_VERIFY_TIMEOUT):
                    return True
                logger.warning(f"{tunnel_type} conectó pero no alcanza los gateways")
                self.vpn_connected = False

        return False

    # ------------------------------------------------------------------
    # OpenConnect
    # ------------------------------------------------------------------

    async def connect_openconnect(self, config: VPNConfig, plant_name: str,
                                  routes: Optional[List[str]] = None) -> bool:
        if not self.openconnect_exe:
            return False

        host = config.get('HOST')
        port = int(config.get('PORT', '10443'))
        user = config.get('USER') or config.get('VPN_NAME')
        password = config.get('PASSWORD') or config.get('PRIVATE_KEY')
        # FortiGate habla su propio dialecto SSL, no AnyConnect.
        default_proto = 'fortinet' if config.vpn_type == 'forticlient' else 'anyconnect'
        protocol = config.get('PROTOCOL', default_proto).lower()

        if not host or not user:
            logger.error("HOST y USER son obligatorios para OpenConnect")
            return False

        args = [self.openconnect_exe, '--non-inter', '--user', user,
                f'--protocol={protocol}']
        if password:
            args.append('--passwd-on-stdin')
        if str(config.get('ALLOW_INSECURE', '')).lower() in ('1', 'true', 'yes'):
            args.append('--no-cert-check')
        args.append(f'{host}:{port}')

        logger.info(f"Conectando OpenConnect: {host}:{port} (proto={protocol})")
        try:
            proc = await asyncio.create_subprocess_exec(
                *args,
                stdin=asyncio.subprocess.PIPE,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.STDOUT,
            )
        except Exception as e:
            logger.warning(f"No se pudo iniciar openconnect: {e}")
            return False

        if password and proc.stdin:
            proc.stdin.write(f"{password}\n".encode())
            await proc.stdin.drain()

        tunnel_up = await self._await_tunnel_line(
            proc, ('connected', 'established', 'tunnel is up'),
            timeout=settings.VPN_CONNECT_TIMEOUT, tag='openconnect'
        )
        self.current_vpn_process = proc

        if tunnel_up and await self.verify_tunnel(timeout=settings.VPN_VERIFY_TIMEOUT):
            self._mark_connected(plant_name, 'openconnect', config)
            return True
        if tunnel_up and not self._health_targets:
            self._mark_connected(plant_name, 'openconnect', config)
            return True

        await self._kill_async_process(proc)
        self.current_vpn_process = None
        return False

    # ------------------------------------------------------------------
    # Túnel SSH
    # ------------------------------------------------------------------

    async def connect_ssh(self, config: VPNConfig, plant_name: str,
                          gateways: Optional[List[str]] = None) -> bool:
        host = config.get('SSH_HOST')
        port = int(config.get('SSH_PORT', '22'))
        username = config.get('SSH_USER')
        password = config.get('SSH_PASSWORD')
        key_path = config.get('SSH_KEY_PATH')

        if not host or not username:
            logger.error("SSH_HOST y SSH_USER son obligatorios")
            return False

        logger.info(f"Conectando túnel SSH a {username}@{host}:{port}")
        import paramiko

        ssh = paramiko.SSHClient()
        ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
        connect_kwargs = {
            'hostname': host, 'port': port, 'username': username,
            'timeout': 15, 'allow_agent': False, 'look_for_keys': False,
        }
        if password:
            connect_kwargs['password'] = password
        if key_path and os.path.exists(key_path):
            connect_kwargs['key_filename'] = key_path

        try:
            await asyncio.to_thread(lambda: ssh.connect(**connect_kwargs))
        except Exception as e:
            self.last_error = f"Error conectando SSH: {e}"
            logger.error(self.last_error)
            return False

        transport = ssh.get_transport()
        if not transport or not transport.is_active():
            logger.error("Transporte SSH no activo")
            ssh.close()
            return False

        self.ssh_forward_threads = []
        self.ssh_forward_ports = {}
        self.ssh_client = ssh
        self.ssh_transport = transport
        self.vpn_connected = True  # los forwarders lo consultan para seguir vivos

        for i, gw_ip in enumerate(gateways or self._health_targets):
            local_port = 15000 + i
            self._start_ssh_forward(transport, local_port, gw_ip, settings.MODBUS_PORT)
            self.ssh_forward_ports[gw_ip] = local_port
            logger.info(f"Forward SSH: localhost:{local_port} -> {gw_ip}:{settings.MODBUS_PORT}")

        self._mark_connected(plant_name, 'ssh', config)
        logger.info(f"Túnel SSH establecido para {plant_name}")
        return True

    def _start_ssh_forward(self, transport, local_port: int, remote_host: str, remote_port: int):
        server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        server.bind(('127.0.0.1', local_port))
        server.listen(10)

        def handler():
            while self.vpn_connected:
                try:
                    client = server.accept()[0]
                    client.settimeout(30)
                    channel = transport.open_channel('direct-tcpip', (remote_host, remote_port), ('', 0))
                    if channel is None:
                        client.close()
                        continue
                    channel.settimeout(30)
                    self._pipe_two_ways(client, channel)
                except (socket.timeout, OSError):
                    continue
                except Exception as e:
                    if self.vpn_connected:
                        logger.debug(f"Forward error: {e}")
                    break
            server.close()

        thread = threading.Thread(target=handler, daemon=True)
        thread.start()
        self.ssh_forward_threads.append(thread)

    def _pipe_two_ways(self, sock1, sock2):
        def pipe(src, dst):
            try:
                while self.vpn_connected:
                    data = src.recv(4096)
                    if not data:
                        break
                    dst.send(data)
            except Exception:
                pass
            finally:
                for s in (src, dst):
                    try:
                        s.close()
                    except Exception:
                        pass

        for args in ((sock1, sock2), (sock2, sock1)):
            threading.Thread(target=pipe, args=args, daemon=True).start()

    def get_ssh_forward_port(self, gateway_ip: str) -> Optional[int]:
        return self.ssh_forward_ports.get(gateway_ip)

    def open_ssh_channel(self, target_host: str, target_port: int = 502):
        if not self.ssh_transport or not self.ssh_transport.is_active():
            logger.error("SSH no conectado")
            return None
        try:
            return self.ssh_transport.open_channel('direct-tcpip', (target_host, target_port), ('', 0))
        except Exception as e:
            logger.error(f"Error abriendo canal SSH a {target_host}:{target_port}: {e}")
            return None

    # ------------------------------------------------------------------
    # Orquestación
    # ------------------------------------------------------------------

    def _methods_for(self, config: VPNConfig) -> List[str]:
        """Métodos compatibles con el tipo declarado y disponibles en la máquina.

        Sólo se prueban clientes que hablan el mismo protocolo: lanzar
        openconnect contra un servidor OpenVPN clásico nunca funciona y añade
        un minuto de espera a cada escaneo.
        """
        preferred = METHODS_BY_TYPE.get(config.vpn_type or '', [])
        if config.vpn_type == 'forticlient':
            # IPsec sólo lo habla la VPN nativa de Windows; SSL nunca debe caer en ella.
            preferred = (['windows_vpn'] if config.vpn_subtype == 'ipsec'
                         else ['openfortivpn', 'forticlient_cli', 'openconnect'])

        methods = [m for m in preferred if m in self.available_vpn_methods]
        # En Windows openfortivpn se descarga bajo demanda, así que sigue siendo
        # candidato aunque todavía no esté instalado.
        if IS_WINDOWS and 'openfortivpn' in preferred and 'openfortivpn' not in methods:
            methods.insert(0, 'openfortivpn')
        if self.demo_mode or config.vpn_type == 'demo':
            methods.append('demo')
        return methods

    async def _dispatch(self, method: str, config: VPNConfig, plant_name: str,
                        routes: Optional[List[str]]) -> bool:
        if method == 'openvpn':
            return await self.connect_openvpn(config, plant_name, routes)
        if method == 'openfortivpn':
            return await self._connect_ssl_openfortivpn(config, plant_name)
        if method == 'forticlient_cli':
            return await self._connect_forticlient_cli(config, plant_name)
        if method == 'openconnect':
            return await self.connect_openconnect(config, plant_name, routes)
        if method == 'windows_vpn':
            return await self._connect_ipsec_windows(config, plant_name, routes)
        if method == 'ssh':
            return await self.connect_ssh(config, plant_name)
        if method == 'demo':
            return await self.connect_demo(plant_name, config)
        return False

    def _recently_verified(self, plant_name: str, vpn_file: str) -> bool:
        return bool(
            self.vpn_connected
            and self._connected_plant == plant_name
            and self._connected_vpn_file == vpn_file
            and self.last_health_ok
            and self.last_health_check
            and time.time() - self.last_health_check < settings.VPN_REUSE_GRACE_SECONDS
        )

    async def connect_vpn(self, vpn_file: str, plant_name: str,
                          routes: Optional[List[str]] = None,
                          targets: Optional[List[str]] = None) -> bool:
        """Conecta (o reutiliza) la VPN de una planta.

        `routes` son las subredes a enrutar y `targets` las IPs de gateway que
        se usan para comprobar que el túnel está realmente operativo.

        Si el túnel de esa misma planta se comprobó hace poco se devuelve al
        instante, sin tomar el cerrojo ni sondear de nuevo: el watchdog ya
        vigila la conexión, así que operaciones encadenadas no pagan latencia.
        """
        if self._recently_verified(plant_name, vpn_file):
            if targets:
                self._health_targets = list(targets)
            return True

        async with self._vpn_lock:
            return await self._connect_locked(vpn_file, plant_name, routes, targets)

    async def _connect_locked(self, vpn_file: str, plant_name: str,
                              routes: Optional[List[str]],
                              targets: Optional[List[str]]) -> bool:
        if targets:
            self._health_targets = list(targets)

        if (self.vpn_connected and self._connected_plant == plant_name
                and self._connected_vpn_file == vpn_file):
            if await self.verify_tunnel(timeout=5):
                logger.info(f"Reutilizando VPN ya conectada para {plant_name}")
                self.last_health_ok = True
                self.last_health_check = time.time()
                return True
            logger.warning(f"La VPN de {plant_name} ya no responde: reconectando")
            await self._disconnect_locked(keep=True)

        if self.vpn_connected and self._connected_plant != plant_name:
            logger.info(f"Cambiando VPN: {self._connected_plant} -> {plant_name}")
            await self._disconnect_locked()

        config = self.parse_vpn_config(vpn_file)
        if not config.is_valid:
            self.last_error = f"Configuración VPN inválida: {vpn_file}"
            logger.error(self.last_error)
            if self.demo_mode:
                return await self.connect_demo(plant_name, config)
            return False

        methods = self._methods_for(config)
        if not methods:
            self.last_error = (
                f"No hay ningún cliente instalado para una VPN de tipo "
                f"'{config.vpn_type}'. Instale el cliente correspondiente."
            )
            logger.error(self.last_error)
            return False

        logger.info(f"Conectando VPN {plant_name} (tipo: {config.vpn_type}, métodos: {methods})")

        for attempt in range(1, settings.VPN_CONNECT_RETRIES + 1):
            for method in methods:
                logger.info(f"Intento {attempt}/{settings.VPN_CONNECT_RETRIES} con '{method}'")
                try:
                    success = await self._dispatch(method, config, plant_name, routes)
                except Exception as e:
                    logger.warning(f"Error en método {method}: {e}", exc_info=True)
                    success = False

                if success:
                    self._connected_plant = plant_name
                    self._connection_generation += 1
                    self._connected_vpn_file = vpn_file
                    self._connected_routes = routes
                    self.last_health_ok = True
                    self.last_health_check = time.time()
                    logger.info(f"{plant_name} conectado via {method}")
                    self._ensure_monitor()
                    return True

            if attempt < settings.VPN_CONNECT_RETRIES:
                backoff = min(2 ** attempt, 30)
                logger.info(f"Reintentando conexión de {plant_name} en {backoff}s...")
                await asyncio.sleep(backoff)

        self.last_error = self.last_error or f"No se pudo conectar la VPN de {plant_name}"
        logger.error(self.last_error)
        self._connected_plant = None
        self._connected_vpn_file = None
        return False

    async def connect_demo(self, plant_name: str, config: Optional[VPNConfig] = None) -> bool:
        logger.info(f"DEMO: {plant_name} conectado (simulado)")
        self._mark_connected(plant_name, 'demo', config)
        return True

    async def disconnect_vpn(self, keep: bool = False) -> bool:
        async with self._vpn_lock:
            return await self._disconnect_locked(keep=keep)

    async def _disconnect_locked(self, keep: bool = False) -> bool:
        try:
            self._connection_generation += 1
            if not keep:
                self._connected_plant = None
                self._connected_vpn_file = None
                self._connected_routes = None
                self._health_targets = []

            self.vpn_connected = False  # detiene los hilos de forwarding SSH
            self.ssh_forward_ports.clear()
            for attr in ('ssh_transport', 'ssh_client'):
                obj = getattr(self, attr)
                if obj is not None:
                    try:
                        obj.close()
                    except Exception:
                        pass
                    setattr(self, attr, None)

            proc = self.current_vpn_process
            if proc is not None:
                if hasattr(proc, 'poll'):
                    try:
                        proc.terminate()
                        await asyncio.to_thread(proc.wait, 5)
                    except Exception:
                        try:
                            proc.kill()
                        except Exception:
                            pass
                else:
                    await self._kill_async_process(proc)
                self.current_vpn_process = None

            if IS_WINDOWS:
                await self._disconnect_windows_leftovers()
            else:
                for pattern in ('openvpn --config', 'openfortivpn', 'openconnect'):
                    try:
                        subprocess.run(['pkill', '-f', pattern],
                                       capture_output=True, timeout=5)
                    except Exception:
                        pass

            if os.path.exists(VPN_PID_FILE):
                try:
                    os.remove(VPN_PID_FILE)
                except OSError:
                    pass

            self.current_vpn_config = None
            self.current_method = None
            self.connection_start_time = None
            self._cleanup_temp_files()
            logger.info("VPN desconectada")
            return True

        except Exception as e:
            logger.error(f"Error desconectando VPN: {e}")
            return False

    async def _disconnect_windows_leftovers(self):
        if self._vpn_connection_name:
            script_path = os.path.join(BASE_DIR, 'scripts', 'vpn_connect_windows.ps1')
            try:
                if os.path.isfile(script_path):
                    await asyncio.to_thread(
                        subprocess.run,
                        ['powershell', '-NoProfile', '-ExecutionPolicy', 'Bypass',
                         '-File', script_path, '-Action', 'remove',
                         '-Name', self._vpn_connection_name],
                        capture_output=True, timeout=20
                    )
                else:
                    rasdial = os.path.join(os.environ.get('SystemRoot', r'C:\Windows'),
                                           'System32', 'rasdial.exe')
                    await asyncio.to_thread(
                        subprocess.run, [rasdial, self._vpn_connection_name, '/disconnect'],
                        capture_output=True, timeout=15
                    )
                logger.info(f"Windows VPN desconectada: {self._vpn_connection_name}")
            except Exception as e:
                logger.debug(f"Error desconectando Windows VPN: {e}")
            self._vpn_connection_name = None

        for proc_name in ('openvpn.exe', 'openfortivpn.exe', 'openconnect.exe'):
            try:
                await asyncio.to_thread(
                    subprocess.run, ['taskkill', '/F', '/IM', proc_name],
                    capture_output=True, timeout=10
                )
            except Exception:
                pass

    # ------------------------------------------------------------------
    # Watchdog de salud y reconexión automática
    # ------------------------------------------------------------------

    def _ensure_monitor(self):
        if not settings.VPN_AUTO_RECONNECT:
            return
        if self._monitor_task and not self._monitor_task.done():
            return
        self._monitor_task = asyncio.create_task(self._monitor_loop())

    async def start_monitor(self):
        self._ensure_monitor()

    async def stop_monitor(self):
        if self._monitor_task:
            self._monitor_task.cancel()
            try:
                await self._monitor_task
            except (asyncio.CancelledError, Exception):
                pass
            self._monitor_task = None

    async def _monitor_loop(self):
        logger.info(f"Watchdog VPN activo (cada {settings.VPN_HEALTH_INTERVAL_SECONDS}s)")
        while True:
            try:
                await asyncio.sleep(settings.VPN_HEALTH_INTERVAL_SECONDS)
                if not self._connected_plant or self._vpn_lock.locked():
                    continue
                generation = self._connection_generation
                plant, vpn_file = self._connected_plant, self._connected_vpn_file
                routes, targets = self._connected_routes, list(self._health_targets)
                healthy = await self.verify_tunnel(timeout=8)
                if generation != self._connection_generation:
                    # La conexión cambió mientras se sondeaba: el resultado ya no aplica.
                    continue
                self.last_health_check = time.time()
                self.last_health_ok = healthy
                if healthy:
                    continue
                logger.warning(f"VPN de {plant} caída: reconectando automáticamente")
                await self.disconnect_vpn(keep=True)
                if vpn_file and await self.connect_vpn(vpn_file, plant, routes, targets):
                    self.reconnect_count += 1
                    logger.info(f"VPN de {plant} restablecida (reconexión #{self.reconnect_count})")
                else:
                    logger.error(f"No se pudo restablecer la VPN de {plant}")
            except asyncio.CancelledError:
                raise
            except Exception as e:
                logger.error(f"Error en watchdog VPN: {e}")

    # ------------------------------------------------------------------
    # Estado
    # ------------------------------------------------------------------

    def cleanup_old_logs(self, base_dir: str, plant_name: str, keep: int = 2):
        try:
            logs = sorted(
                (os.path.join(base_dir, f) for f in os.listdir(base_dir)
                 if f.startswith(f'openvpn_{plant_name}_') and f.endswith('.log')),
                key=os.path.getctime
            )
            for old_log in logs[:-keep]:
                try:
                    os.remove(old_log)
                except OSError:
                    pass
        except OSError:
            pass

    def is_vpn_connected(self) -> bool:
        return self.vpn_connected

    def connected_plant(self) -> Optional[str]:
        return self._connected_plant

    def is_connected_to(self, plant_name: str) -> bool:
        return self.vpn_connected and self._connected_plant == plant_name

    def get_connection_uptime(self) -> int:
        if self.connection_start_time:
            return int(time.time() - self.connection_start_time)
        return 0

    def get_diagnostics(self) -> dict:
        return {
            'platform': 'windows' if IS_WINDOWS else 'posix',
            'connected': self.vpn_connected,
            'plant': self._connected_plant,
            'method': self.current_method,
            'uptime_seconds': self.get_connection_uptime(),
            'auto_reconnect': settings.VPN_AUTO_RECONNECT,
            'reconnect_count': self.reconnect_count,
            'health_targets': self._health_targets,
            'last_health_check': self.last_health_check,
            'last_health_ok': self.last_health_ok,
            'last_error': self.last_error,
            'demo_mode': self.demo_mode,
            'available_methods': self.available_vpn_methods,
            'clients': {
                'openvpn': self.openvpn_exe,
                'openfortivpn': self.openfortivpn_exe,
                'openconnect': self.openconnect_exe,
                'forticlient_cli': self.forticlient_exe,
                'windows_vpn': self.windows_vpn_available,
            },
        }


vpn_service = VPNServiceV2()
