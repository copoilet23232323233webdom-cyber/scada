import axios from 'axios'

const api = axios.create({
  baseURL: '/api',
  headers: {
    'Content-Type': 'application/json'
  }
})

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
  delete: (id: number) => api.delete(`/plants/${id}`)
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
  connect: (plantName: string) => api.post('/vpn/connect', null, { params: { plant_name: plantName } }),
  disconnect: () => api.post('/vpn/disconnect')
}

export const scanAPI = {
  scanPlant: (plantId: number) => api.post(`/scan/plant/${plantId}`),
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
      responseType: 'blob' 
    }),
  generateCsv: (plantId: number, params?: any) =>
    api.get(`/report/plant/${plantId}`, { 
      params: { format: 'csv', ...params },
      responseType: 'blob' 
    })
}

export const usersAPI = {
  getAll: () => api.get('/users/'),
  create: (data: any) => api.post('/users/', data),
  update: (id: number, data: any) => api.patch(`/users/${id}`, data),
  delete: (id: number) => api.delete(`/users/${id}`)
}

export const gwControlAPI = {
  status: (id: number) => api.get(`/gateways/${id}/status`),
  firmware: (id: number) => api.get(`/gateways/${id}/firmware`),
  sysConfig: (id: number) => api.get(`/gateways/${id}/sys-config`),
  setMode: (id: number, mode: number) => api.post(`/gateways/${id}/mode`, { mode }),
  saveNvm: (id: number) => api.post(`/gateways/${id}/save-nvm`),
  reset: (id: number) => api.post(`/gateways/${id}/reset`),
  command: (id: number, value: number) => api.post(`/gateways/${id}/command`, { value }),
  cbTable: (id: number) => api.get(`/gateways/${id}/cb-table`),

  slaveLora: (id: number, cbId: number) => api.get(`/gateways/${id}/slaves/${cbId}/lora`),
  slaveAnalogBottom: (id: number, cbId: number) => api.get(`/gateways/${id}/slaves/${cbId}/analog-bottom`),
  slaveAnalogTop: (id: number, cbId: number) => api.get(`/gateways/${id}/slaves/${cbId}/analog-top`),
  slaveChannelMap: (id: number, cbId: number) => api.get(`/gateways/${id}/slaves/${cbId}/channel-map`),

  writeSlaveLora: (id: number, cbId: number, data: any) => api.post(`/gateways/${id}/slaves/${cbId}/lora`, data),
  writeSlaveAnalogBottom: (id: number, cbId: number, channels: any[]) => api.post(`/gateways/${id}/slaves/${cbId}/analog-bottom`, channels),
  writeSlaveAnalogTop: (id: number, cbId: number, channels: any[]) => api.post(`/gateways/${id}/slaves/${cbId}/analog-top`, channels),
  writeSlaveChannelMap: (id: number, cbId: number, channels: number[]) => api.post(`/gateways/${id}/slaves/${cbId}/channel-map`, { channels }),
  slaveCommand: (id: number, cbId: number, cmd: number) => api.post(`/gateways/${id}/slaves/${cbId}/command`, { cmd, typ: 3, save_nvm: true }),
  slaveZero: (id: number, cbId: number) => api.post(`/gateways/${id}/slaves/${cbId}/zero`),
  loraScan: (id: number) => api.post(`/gateways/${id}/lora-scan`, {}),

  dir: (id: number, directory: string) => api.get(`/gateways/${id}/files/${directory}`),
  download: (id: number, directory: string, filename: string) =>
    api.get(`/gateways/${id}/files/${directory}/${filename}`),
  upload: (id: number, directory: string, filename: string, data: string) =>
    api.post(`/gateways/${id}/files/${directory}/${filename}`, { data })
}

export default api
