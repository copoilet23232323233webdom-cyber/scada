import axios from 'axios'

/** Peticiones normales: si el backend no responde en 20s, se corta y se avisa
 *  en vez de dejar la pantalla cargando para siempre. */
const DEFAULT_TIMEOUT = 20000
/** Operaciones que hablan con la planta por VPN/Modbus (o generan informes). */
const LONG_TIMEOUT = 90000

const api = axios.create({
  baseURL: '/api',
  timeout: DEFAULT_TIMEOUT,
  headers: {
    'Content-Type': 'application/json'
  }
})

const long = { timeout: LONG_TIMEOUT }

api.interceptors.request.use((config) => {
  const token = localStorage.getItem('access_token')
  if (token) {
    config.headers.Authorization = `Bearer ${token}`
  }
  return config
})

api.interceptors.response.use(
  (response) => response,
  (error) => {
    if (error.code === 'ECONNABORTED') {
      error.message = 'El servidor tardó demasiado en responder. Inténtalo de nuevo.'
    }
    if (error.response?.status === 401) {
      localStorage.removeItem('access_token')
      localStorage.removeItem('user')
      window.location.href = '/login'
    }
    return Promise.reject(error)
  }
)

export const authAPI = {
  login: (username: string, password: string) =>
    api.post('/auth/login', { username, password })
}

export const plantsAPI = {
  getAll: () => api.get('/plants/'),
  getById: (id: number) => api.get(`/plants/${id}`),
  create: (data: any) => api.post('/plants/', data),
  update: (id: number, data: any) => api.put(`/plants/${id}`, data),
  delete: (id: number) => api.delete(`/plants/${id}`),
  getVpn: (id: number) => api.get(`/plants/${id}/vpn`),
  saveVpn: (id: number, data: any) => api.put(`/plants/${id}/vpn`, data),
  testVpn: (id: number) => api.post(`/plants/${id}/vpn/test`, null, long)
}

export const gatewaysAPI = {
  getByPlant: (plantId: number) => api.get(`/gateways/plant/${plantId}`),
  getById: (id: number) => api.get(`/gateways/${id}`),
  create: (data: any) => api.post('/gateways/', data),
  update: (id: number, data: any) => api.patch(`/gateways/${id}`, data),
  delete: (id: number) => api.delete(`/gateways/${id}`)
}

export const cardsAPI = {
  getByGateway: (gatewayId: number) => api.get(`/cards/gateway/${gatewayId}`),
  update: (id: number, data: any) => api.patch(`/cards/${id}`, data)
}

export const alarmsAPI = {
  getAll: (params?: any) => api.get('/alarms/', { params }),
  getById: (id: number) => api.get(`/alarms/${id}`),
  resolve: (id: number) => api.post(`/alarms/${id}/resolve`)
}

export const vpnAPI = {
  getStatus: () => api.get('/vpn/status'),
  getDiagnostics: () => api.get('/vpn/diagnostics'),
  healthCheck: () => api.post('/vpn/health-check', null, long),
  connect: (plantName: string) => api.post('/vpn/connect', null, { params: { plant_name: plantName }, ...long }),
  reconnect: (plantName: string) => api.post('/vpn/reconnect', null, { params: { plant_name: plantName }, ...long }),
  disconnect: () => api.post('/vpn/disconnect', null, long)
}

export const scanAPI = {
  // Puede quedarse esperando a que termine el escaneo anterior.
  scanPlant: (plantId: number) => api.post(`/scan/plant/${plantId}`, null, long),
  scanAll: () => api.post('/scan/all'),
  scanStop: () => api.post('/scan/stop'),
  getStatus: () => api.get('/scan/status')
}

export const healthAPI = {
  getStatus: () => api.get('/health')
}

export const reportAPI = {
  generatePdf: (plantId: number, params?: any) => 
    api.get(`/report/plant/${plantId}`, { 
      params: { format: 'pdf', ...params },
      responseType: 'blob',
      ...long
    }),
  generateCsv: (plantId: number, params?: any) =>
    api.get(`/report/plant/${plantId}`, { 
      params: { format: 'csv', ...params },
      responseType: 'blob',
      ...long
    })
}

export const usersAPI = {
  getAll: () => api.get('/users/'),
  create: (data: any) => api.post('/users/', data),
  update: (id: number, data: any) => api.patch(`/users/${id}`, data),
  delete: (id: number) => api.delete(`/users/${id}`)
}

// Todo lo que va contra el gateway pasa por la VPN: timeout amplio.
export const gwControlAPI = {
  overview: (id: number) => api.get(`/gateways/${id}/overview`, long),
  status: (id: number) => api.get(`/gateways/${id}/status`, long),
  firmware: (id: number) => api.get(`/gateways/${id}/firmware`, long),
  sysConfig: (id: number) => api.get(`/gateways/${id}/sys-config`, long),
  setMode: (id: number, mode: number) => api.post(`/gateways/${id}/mode`, { mode }, long),
  saveNvm: (id: number) => api.post(`/gateways/${id}/save-nvm`, null, long),
  reset: (id: number) => api.post(`/gateways/${id}/reset`, null, long),
  command: (id: number, value: number) => api.post(`/gateways/${id}/command`, { value }, long),
  cbTable: (id: number) => api.get(`/gateways/${id}/cb-table`, long),

  slaveLora: (id: number, cbId: number) => api.get(`/gateways/${id}/slaves/${cbId}/lora`, long),
  slaveAnalogBottom: (id: number, cbId: number) => api.get(`/gateways/${id}/slaves/${cbId}/analog-bottom`, long),
  slaveAnalogTop: (id: number, cbId: number) => api.get(`/gateways/${id}/slaves/${cbId}/analog-top`, long),
  slaveChannelMap: (id: number, cbId: number) => api.get(`/gateways/${id}/slaves/${cbId}/channel-map`, long),

  writeSlaveLora: (id: number, cbId: number, data: any) => api.post(`/gateways/${id}/slaves/${cbId}/lora`, data, long),
  writeSlaveAnalogBottom: (id: number, cbId: number, channels: any[]) => api.post(`/gateways/${id}/slaves/${cbId}/analog-bottom`, channels, long),
  writeSlaveAnalogTop: (id: number, cbId: number, channels: any[]) => api.post(`/gateways/${id}/slaves/${cbId}/analog-top`, channels, long),
  writeSlaveChannelMap: (id: number, cbId: number, channels: number[]) => api.post(`/gateways/${id}/slaves/${cbId}/channel-map`, { channels }, long),
  slaveCommand: (id: number, cbId: number, cmd: number) => api.post(`/gateways/${id}/slaves/${cbId}/command`, { cmd, typ: 3, save_nvm: true }, long),
  slaveZero: (id: number, cbId: number) => api.post(`/gateways/${id}/slaves/${cbId}/zero`, null, long),
  loraScan: (id: number) => api.post(`/gateways/${id}/lora-scan`, {}, long),

  dir: (id: number, directory: string) => api.get(`/gateways/${id}/files/${directory}`, long),
  download: (id: number, directory: string, filename: string) =>
    api.get(`/gateways/${id}/files/${directory}/${filename}`, long),
  upload: (id: number, directory: string, filename: string, data: string) =>
    api.post(`/gateways/${id}/files/${directory}/${filename}`, { data }, long)
}

export default api
