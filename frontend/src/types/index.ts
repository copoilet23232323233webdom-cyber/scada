export interface Plant {
  id: number
  name: string
  path: string
  status: string
  vpn_status: string
  response_time_ms: number | null
  maintenance_mode: boolean
  last_scan: string | null
  last_vpn_connection: string | null
  client_id: string | null
  created_at: string
  updated_at: string
  gateways_count: number
  total_cards: number
  active_alarms: number
}

export interface Gateway {
  id: number
  plant_id: number
  ip: string
  firmware: string | null
  id_start: number
  id_end: number
  status: string
  response_time_ms: number | null
  lora_ok: boolean
  total_cards: number
  active_cards: number
  failed_cards: number
  consecutive_errors: number
  maintenance_mode: boolean
  last_scan: string | null
  last_error: string | null
  created_at: string
  updated_at: string
}

export interface Card {
  id: number
  gateway_id: number
  modbus_id: number
  status: string
  communication_ok: boolean
  sec_alarm: boolean
  overvoltage_alarm: boolean
  lora_ok: boolean
  communication_alarm: boolean
  maintenance_mode: boolean
  disabled: boolean
  voltage: number | null
  response_time_ms: number | null
  last_contact: string | null
  consecutive_errors: number
  last_error_message: string | null
  created_at: string
  updated_at: string
}

export interface Alarm {
  id: number
  plant_id: number
  gateway_id: number | null
  card_id: number | null
  gateway_ip: string | null
  alarm_type: string
  description: string | null
  status: string
  severity: string
  acknowledged_at: string | null
  email_sent: boolean
  last_reminder: string | null
  reminder_count: number
  created_at: string
  resolved_at: string | null
  active_duration_minutes: number
  observations: string | null
}

export interface User {
  id: number
  username: string
  email: string
  full_name: string | null
  role: string
  assigned_plants: string | null
  is_active: boolean
}

export interface AuthResponse {
  access_token: string
  token_type: string
  user_id: number
  username: string
  role: string
}

// ---- Gateway control (multiGW) ----

export interface GwStatus {
  gw_status: number
  lora_updating: number
  cbt_modified: boolean
  cbconf_modified: boolean
  lst_modified: boolean
  sntp_status: number
  mac: string
  slave_id: number
}

export interface GwSysConfig {
  mode_index: number
  mode: string
  data_log_interval: number
  zone_time: number
  dst_saving: boolean
  n_lora_fail: number
  threshold: number
  gain: number
}

export interface CommSett {
  slave_id: number
  timeout: number
  baudrate: number
  char_len: number
  parity: number
  stop_bit: number
  id_ovr: boolean
}

export interface CbItem {
  id: number
  mac: string
  key: string
  lo_conf: {
    raw_bits: number
    pream_length: number
    fixed_pk_length: number
    frq: number
  }
  comm_conf: CommSett[]
  lat: number
  lon: number
  configured: boolean
  updated: boolean
  cmd_ok: boolean
  datetime_ok: boolean
  analog_in: { k: number; offset: number; n_mean: number }
  sys_conf: {
    config: number
    data_log_interval: number
    device_type: string
  }
}

export interface LoraConfDict {
  raw_bits: number
  pream_length: number
  fixed_pk_length: number
  frq: number
  lora_id: number
  low_data_rate_opt: boolean
  crc_dis: boolean
  explicit_en: boolean
  fix_pkln_en: boolean
  bandwidth: number
  coding_rate: number
  sfactor: number
  tx_pwr: number
}

export interface AnalogChannel {
  channel: number
  k: number
  offset: number
  n_mean: number
}

export interface ChannelMapItem {
  toroide: number
  channel: number
}

export interface LoraScanResult {
  ok: boolean
  id: number
  mac: string
  pkt_snr: number
  pkt_rssi: number
  rssi: number
}

