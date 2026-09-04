"""
Constantes de direcciones Modbus (MBaddr) replicadas del programa multi_gw_control
(C#) para control remoto de gateways Webdom via Modbus TCP.
Documentación de referencia: MBaddr.cs del proyecto multiGW.
"""

# ------------------------------------------------------------------
# Registros del gateway
# ------------------------------------------------------------------
REG_RAW = 0x0000
ANALOG = 0x0100
SAVE_GW_CONFIG = 0x2000
REG_LORA = 0x1200
REG_VERSION = 0x1F00
READ_ID = 0x4400
COMM_CONF = 0x4100
ANALOG_CONF = 0x4200
LORA_CONFIG = 0x4300
REG_CFG_DATE_TIME = 0x4500
REG_CFG_COMMON = 0x4600
REG_SD = 0x4700
REG_LORA_PACKET_CFG = 0x4B00
REG_CFG_SYS = 0x4C00
REG_CFG_ANEM = 0x4D00
CMD = 0x4F00
LORA_UPDATING = 0x0300
STADISTICS = 0x0600

# Valores de comandos que se escriben en CMD (0x4F00)
CMD_SAVE_CONFIG_NVM = 0x00F0
CMD_ZERO = 0x00E0
CMD_ENCRYPT = 0x00D0
CMD_SYNC = 0x00D1
CMD_RESET = 0x00E1
CMD_CLEAR_LOG = 0x00E3
CMD_SET_MODE = 0x00E4
CMD_GO_POS = 0x00E5
CMD_GO_POS_IDX = 0x00E6
CMD_STOP = 0x00E7
CMD_RESET_ALARM = 0x00E8

# ------------------------------------------------------------------
# Comunicacion slave/puente LoRa (GW <-> slave)
# ------------------------------------------------------------------
SLV_ID_MAC = 0x7000
SLV_DATE_REQ = 0x7100
SLV_DATA_REG = 0x7200
SLV_LORA_CONFIG = 0x7300
SLV_COMM_CONFIG = 0x7400
SLV_LORA_KEY = 0x7500
SLV_LORA_UPDATING = 0x7600
SLV_REG_LORA = 0x7700
SLV_REG_CFG_DATE_TIME = 0x7800
SLV_REG_HOLDING = 0x7900
SLV_REG_CFG_MUX_CHANNELS = 0x7A00
SLV_REG_CFG_ANALOGIN = 0x7B00
SLV_REG_CFG_ANALOGIN_TOP = 0x7C00

# Triggers de actualizacion del slave (escritura de 1 registro [0])
SLV_UPDATE = 0x7F00
SLV_UPDATE_CFG_LORA = 0x7F00
SLV_UPDATE_COMM_CFG = 0x7F01
SLV_UPDATE_LORA_KEY = 0x7F02
SLV_UPDATE_REG_LORA = 0x7F03
SLV_UPDATE_REG_CFG_DATE_TIME = 0x7F04
SLV_UPDATE_REG_HOLDING = 0x7F05
SLV_UPDATE_REG_CFG_MUX_CHANNELS = 0x7F06
SLV_UPDATE_SYS_CFG = 0x7F07
SLV_UPDATE_REG_CFG_ANALOG_IN = 0x7F42
SLV_UPDATE_REG_CFG_ANALOG_IN_SLV = 0x7F4E

SLV_CMD = 0xD000

# ------------------------------------------------------------------
# Gestion de archivos
# ------------------------------------------------------------------
SEND_PATH_FILE = 0x2100
OPEN_FILE = 0x2200
READ_FILE_BLOCK = 0x2300
CLOSE_FILE = 0x2400
ERASE_FILE = 0x2500
OPEN_LOG_DIR = 0x2600
OPEN_DATA_DIR = 0x2700
READ_DIR = 0x2800
OPEN_CBTB_DIR = 0x2900
OPEN_STDS_DIR = 0x2A00
OPEN_FILE_TO_WRITE = 0x2B00
WRITE_FILE_BLOCK = 0x2C00
CLOSE_FILE_TO_WRITE = 0x2D00

# ------------------------------------------------------------------
# Tabla CB (Combiner Box)
# ------------------------------------------------------------------
N_ITEMS_CB_TABLE = 0x5000
READ_ITEM_CB_TABLE = 0x5100
WRITE_CB_TABLE_BEGIN = 0x5200
WRITE_CB_TABLE_ITEM = 0x5300
WRITE_CB_TABLE_FINISH = 0x5400
WRITE_CB_TABLE_KEY = 0x5500
WRITE_CB_TABLE_LORA_CFG = 0x5600
CB_TABLE_MODIFIED = 0x5700

# Tabla CBCONF
CBCONF_TABLE_MODIFIED = 0x5800
N_ITEMS_CBCONF_TABLE = 0x5900
READ_ITEM_CBCONF_TABLE = 0x5A00
CBCONF_BEGIN_TO_CONFIGURE = 0x5B00
CBCONF_BEGIN_TO_GET_KEYS = 0x5C00
CBCONF_BEGIN_TO_UPDATE = 0x5D00
CBCONF_BEGIN_TO_SEND_CMD = 0x5E00
CBCONF_BEGIN_TO_SEND_DATETIME = 0x5F00

# ------------------------------------------------------------------
# Escaneo LoRa
# ------------------------------------------------------------------
N_ITEMS_SCANLORA_TABLE = 0x6000
READ_ITEM_SCANLORA_TABLE = 0x6100
SCANLORA_BEGIN = 0x6200
SCANLORA_TABLE_MODIFIED = 0x6300
SCAN_LORA_IDX = 0x6400
GW_STATUS = 0x6500
GW_DATA_TO_FE = 0x6600

# ------------------------------------------------------------------
# Tracker (referencia, no usado en la UI principal)
# ------------------------------------------------------------------
TRK_UPDATE = 0x6F00
TRK_UPDATE_REG_HLD = 0x6F00
TRK_UPDATE_REG_LORA = 0x6F02
TRK_UPDATE_REG_WINDS = 0x6F05
TRK_UPDATE_REG_DOUT = 0x6F06
TRK_UPDATE_REG_DATALOG = 0x6F10
TRK_UPDATE_REG_LDATALOG = 0x6F11
TRK_UPDATE_REG_DL_NPENDREG = 0x6F12
TRK_UPDATE_REG_CFG_RAW = 0x6F40
TRK_UPDATE_REG_CFG_COM = 0x6F41
TRK_UPDATE_REG_CFG_TILTS = 0x6F42
TRK_UPDATE_REG_CFG_LORA = 0x6F43
TRK_UPDATE_REG_CFG_CHIPID = 0x6F44
TRK_UPDATE_REG_CFG_DATETIME = 0x6F45
TRK_UPDATE_REG_CFG_SUNPOS = 0x6F46
TRK_UPDATE_REG_CFG_TRACKER = 0x6F47
TRK_UPDATE_REG_CFG_DRIVER = 0x6F48
TRK_UPDATE_REG_CFG_CHARGER = 0x6F49
TRK_UPDATE_REG_CFG_DINPUTS = 0x6F4A
TRK_UPDATE_REG_CFGDOUTPUTS = 0x6F4B
TRK_UPDATE_REG_CFG_SYSCFG = 0x6F4C
TRK_UPDATE_REG_CFG_LOGNREGISTERS = 0x6F4D
TRK_UPDATE_REG_CFG_RDLOG = 0x6F4E

TRK_REG_HLD = 0x8000
TRK_REG_LORA = 0x8200
TRK_REG_WINDS = 0x8500
TRK_REG_DOUT = 0x8600
TRK_REG_DATALOG = 0x9000
TRK_REG_LDATALOG = 0x9100
TRK_REG_DL_NPENDREG = 0x9200

# ------------------------------------------------------------------
# Codificacion de estados
# ------------------------------------------------------------------

# lora_updating (bits 0-3 de GW_DATA_TO_FE[0])
LORA_UPDATING_OK = 0
LORA_UPDATING_WAITING = 1
LORA_UPDATING_TIMEOUT = 2
LORA_UPDATING_CHECKSUM = 3
LORA_UPDATING_MODBUS = 4


def lora_updating_to_text(code: int) -> str:
    mapping = {
        0: "OK",
        1: "waiting",
        2: "timeout",
        3: "Error checksum",
        4: "Error Modbus",
    }
    return mapping.get(code, "")
