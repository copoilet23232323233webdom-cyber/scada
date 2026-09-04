import { useEffect, useState, useRef } from 'react'
import { Link } from 'react-router-dom'
import { plantsAPI, scanAPI } from '../services/api'
import { useAuth } from '../context/AuthContext'
import { Plant } from '../types'
import { Activity, AlertTriangle, CheckCircle, Wifi, Zap, Search, Filter, RefreshCw, Loader, Plus, X, Trash2, Edit3, Shield, Play, Square } from 'lucide-react'

export default function Dashboard() {
  const { user } = useAuth()
  const [plants, setPlants] = useState<Plant[]>([])
  const [filteredPlants, setFilteredPlants] = useState<Plant[]>([])
  const [loading, setLoading] = useState(true)
  const [searchTerm, setSearchTerm] = useState('')
  const [statusFilter, setStatusFilter] = useState('all')
  const [wsConnected, setWsConnected] = useState(false)
  const [scanningAll, setScanningAll] = useState(false)
  const [autoLoop, setAutoLoop] = useState(false)
  const [scanningPlantId, setScanningPlantId] = useState<number | null>(null)
  const [refreshing, setRefreshing] = useState(false)
  // Progreso en vivo por nombre de planta (lo emite el backend vía WebSocket).
  const [scanProgress, setScanProgress] = useState<Record<string, { percent: number; stage: string; message: string }>>({})
  const wsRef = useRef<WebSocket | null>(null)
  const pingIntervalRef = useRef<number | null>(null)

  useEffect(() => {
    loadPlants()
    const interval = setInterval(loadPlants, 30000)
    connectWebSocket()
    loadScanStatus()
    const statusInterval = setInterval(loadScanStatus, 15000)
    
    return () => {
      clearInterval(interval)
      clearInterval(statusInterval)
      if (wsRef.current) wsRef.current.close()
      if (pingIntervalRef.current) clearInterval(pingIntervalRef.current)
    }
  }, [])

  useEffect(() => {
    let result = plants
    if (searchTerm) {
      result = result.filter(p => 
        p.name.toLowerCase().includes(searchTerm.toLowerCase())
      )
    }
    if (statusFilter !== 'all') {
      result = result.filter(p => p.status === statusFilter)
    }
    setFilteredPlants(result)
  }, [plants, searchTerm, statusFilter])

  const connectWebSocket = () => {
    try {
      const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:'
      // Mismo origen que la app (el dev server hace de proxy hacia el backend).
      const wsHost = import.meta.env.VITE_WS_HOST || window.location.host
      const wsUrl = `${protocol}//${wsHost}/api/ws/status`
      const ws = new WebSocket(wsUrl)
      
      ws.onopen = () => {
        setWsConnected(true)
        pingIntervalRef.current = window.setInterval(() => {
          if (ws.readyState === WebSocket.OPEN) {
            ws.send(JSON.stringify({ type: 'ping' }))
          }
        }, 30000)
      }
      
      ws.onmessage = (event) => {
        try {
          const msg = JSON.parse(event.data)
          if (msg.type === 'scan_progress') {
            const { plant_name, percent, stage, message } = msg.data
            setScanProgress(prev => ({ ...prev, [plant_name]: { percent, stage, message } }))
            if (stage === 'complete' || stage === 'error') {
              setScanningPlantId(null)
              loadPlants()
              window.setTimeout(() => {
                setScanProgress(prev => {
                  const next = { ...prev }
                  delete next[plant_name]
                  return next
                })
              }, 4000)
            }
            return
          }
          if (msg.type === 'scan_update' || msg.type === 'plant_status' || msg.type === 'scheduler_status') {
            loadPlants()
          }
        } catch (e) {}
      }
      
      ws.onclose = () => {
        setWsConnected(false)
        if (pingIntervalRef.current) clearInterval(pingIntervalRef.current)
        setTimeout(connectWebSocket, 5000)
      }
      
      ws.onerror = () => { ws.close() }
      wsRef.current = ws
    } catch (e) {
      console.error('Error WebSocket:', e)
    }
  }

  const loadPlants = async (isRefresh = false) => {
    if (isRefresh) setRefreshing(true)
    try {
      const response = await plantsAPI.getAll()
      setPlants(response.data)
    } catch (error) {
      console.error('Error cargando plantas:', error)
    } finally {
      setLoading(false)
      if (isRefresh) setRefreshing(false)
    }
  }

  const loadScanStatus = async () => {
    try {
      const response = await scanAPI.getStatus()
      const data = response.data
      setAutoLoop(Boolean(data.auto_loop))
    } catch (error) {
      console.debug('No se pudo leer estado de escaneo:', error)
    }
  }

  const handleStartAuto = async () => {
    setScanningAll(true)
    try {
      await scanAPI.scanAll()
      setAutoLoop(true)
    } catch (error) {
      console.error('Error iniciando modo AUTO:', error)
    } finally {
      setScanningAll(false)
    }
  }

  const handleStopAuto = async () => {
    setScanningAll(true)
    try {
      await scanAPI.scanStop()
      setAutoLoop(false)
    } catch (error) {
      console.error('Error deteniendo modo AUTO:', error)
    } finally {
      setScanningAll(false)
    }
  }

  const handleScanOne = async (plantId: number) => {
    // Escanear solo esta planta: detiene cualquier bucle auto para "olvidarse del resto"
    if (autoLoop) {
      try { await scanAPI.scanStop() } catch {}
      setAutoLoop(false)
    }
    setScanningPlantId(plantId)
    try {
      await scanAPI.scanPlant(plantId)
      // Red de seguridad: normalmente lo limpia el evento de progreso final.
      setTimeout(() => setScanningPlantId(null), 120000)
    } catch (error) {
      console.error('Error escaneando planta:', error)
      setScanningPlantId(null)
    }
  }

  const [showCreateModal, setShowCreateModal] = useState(false)
  const [newPlant, setNewPlant] = useState({ name: '', client_id: '' })
  const [newGateways, setNewGateways] = useState<{ ip: string; id_start: number; id_end: number }[]>([])
  const [creating, setCreating] = useState(false)
  const [createError, setCreateError] = useState('')
  const [editPlant, setEditPlant] = useState<Plant | null>(null)
  const [deleteConfirm, setDeleteConfirm] = useState<Plant | null>(null)
  const [vpnEnabled, setVpnEnabled] = useState(false)
  const [vpnType, setVpnType] = useState('openvpn')
  const [vpnConfig, setVpnConfig] = useState({
    config_path: '', username: '', password: '', key_password: '',
    vpn_name: '', host: '', port: 10443,
    subtype: 'ssl', psk: '', private_key: '', local_id: '', remote_id: '', ike_version: 'v2',
    phase1_proposal: 'AES256-SHA512', phase1_dh_group: '14',
    phase2_proposal: 'AES256-SHA512', phase2_dh_group: '14',
    realm: '', trusted_cert: '', allow_insecure: true,
    ssh_host: '', ssh_port: 22, ssh_username: '', ssh_password: '', ssh_key_path: ''
  })
  const [ovpnFile, setOvpnFile] = useState<{ name: string; data: string } | null>(null)

  const readOvpnFile = async (file: File) => {
    const text = await file.text()
    setOvpnFile({ name: file.name, data: btoa(unescape(encodeURIComponent(text))) })
  }

  const handleCreatePlant = async () => {
    if (!newPlant.name.trim()) { setCreateError('Nombre requerido'); return }
    setCreating(true); setCreateError('')
    try {
      const body: any = { name: newPlant.name, client_id: newPlant.client_id || null, gateways: newGateways }
      if (vpnEnabled) {
        body.vpn = { type: vpnType }
        if (vpnType === 'openvpn') {
          if (vpnConfig.config_path) body.vpn.config_path = vpnConfig.config_path
          if (ovpnFile) {
            body.vpn.config_filename = ovpnFile.name
            body.vpn.config_file = ovpnFile.data
          }
          if (vpnConfig.username) body.vpn.username = vpnConfig.username
          if (vpnConfig.password) body.vpn.password = vpnConfig.password
          if (vpnConfig.key_password) body.vpn.key_password = vpnConfig.key_password
        } else if (vpnType === 'forticlient') {
          body.vpn.subtype = vpnConfig.subtype
          if (vpnConfig.vpn_name) body.vpn.vpn_name = vpnConfig.vpn_name
          if (vpnConfig.host) body.vpn.host = vpnConfig.host
          body.vpn.port = vpnConfig.port
          if (vpnConfig.username) body.vpn.username = vpnConfig.username
          if (vpnConfig.password) body.vpn.password = vpnConfig.password
          if (vpnConfig.subtype === 'ssl') {
            if (vpnConfig.realm) body.vpn.realm = vpnConfig.realm
            if (vpnConfig.trusted_cert) body.vpn.trusted_cert = vpnConfig.trusted_cert
            body.vpn.allow_insecure = vpnConfig.allow_insecure
          } else if (vpnConfig.subtype === 'ipsec') {
            if (vpnConfig.psk) body.vpn.psk = vpnConfig.psk
            if (vpnConfig.private_key) body.vpn.private_key = vpnConfig.private_key
            if (vpnConfig.local_id) body.vpn.local_id = vpnConfig.local_id
            if (vpnConfig.remote_id) body.vpn.remote_id = vpnConfig.remote_id
            body.vpn.ike_version = vpnConfig.ike_version
            body.vpn.phase1_proposal = vpnConfig.phase1_proposal
            body.vpn.phase1_dh_group = vpnConfig.phase1_dh_group
            body.vpn.phase2_proposal = vpnConfig.phase2_proposal
            body.vpn.phase2_dh_group = vpnConfig.phase2_dh_group
          }
        } else if (vpnType === 'ssh') {
          if (vpnConfig.ssh_host) body.vpn.ssh_host = vpnConfig.ssh_host
          body.vpn.ssh_port = vpnConfig.ssh_port
          if (vpnConfig.ssh_username) body.vpn.ssh_username = vpnConfig.ssh_username
          if (vpnConfig.ssh_password) body.vpn.ssh_password = vpnConfig.ssh_password
          if (vpnConfig.ssh_key_path) body.vpn.ssh_key_path = vpnConfig.ssh_key_path
        }
      }
      await plantsAPI.create(body)
      setShowCreateModal(false)
      setNewPlant({ name: '', client_id: '' })
      setNewGateways([])
      setVpnEnabled(false)
      setVpnType('openvpn')
      setOvpnFile(null)
      setVpnConfig({
        config_path: '', username: '', password: '', key_password: '',
        vpn_name: '', host: '', port: 10443,
        subtype: 'ssl', psk: '', private_key: '', local_id: '', remote_id: '', ike_version: 'v2',
        realm: '', trusted_cert: '', allow_insecure: true,
        phase1_proposal: 'AES256-SHA512', phase1_dh_group: '14',
        phase2_proposal: 'AES256-SHA512', phase2_dh_group: '14',
        ssh_host: '', ssh_port: 22, ssh_username: '', ssh_password: '', ssh_key_path: ''
      })
      loadPlants()
    } catch (err: any) {
      setCreateError(err.response?.data?.detail || 'Error al crear planta')
    } finally {
      setCreating(false)
    }
  }

  const handleUpdatePlant = async () => {
    if (!editPlant || !editPlant.name.trim()) return
    setCreating(true); setCreateError('')
    try {
      await plantsAPI.update(editPlant.id, { name: editPlant.name, client_id: editPlant.client_id })
      setEditPlant(null)
      loadPlants()
    } catch (err: any) {
      setCreateError(err.response?.data?.detail || 'Error al actualizar')
    } finally {
      setCreating(false)
    }
  }

  const handleDeletePlant = async () => {
    if (!deleteConfirm) return
    try {
      await plantsAPI.delete(deleteConfirm.id)
      setDeleteConfirm(null)
      loadPlants()
    } catch (err: any) {
      console.error('Error eliminando:', err)
    }
  }

  const getStatusColor = (status: string) => {
    switch (status) {
      case 'green': return 'bg-green-100 text-green-800 border-green-200'
      case 'red': return 'bg-red-100 text-red-800 border-red-200'
      case 'yellow': return 'bg-yellow-100 text-yellow-800 border-yellow-200'
      case 'scanning': return 'bg-blue-100 text-blue-800 border-blue-200'
      case 'unknown': return 'bg-gray-100 text-gray-800 border-gray-200'
      default: return 'bg-yellow-100 text-yellow-800 border-yellow-200'
    }
  }

  const getStatusIcon = (status: string) => {
    switch (status) {
      case 'green': return <CheckCircle className="h-5 w-5 text-green-600" />
      case 'red': return <AlertTriangle className="h-5 w-5 text-red-600" />
      case 'yellow': return <AlertTriangle className="h-5 w-5 text-yellow-600" />
      case 'scanning': return <Loader className="h-5 w-5 text-blue-600 animate-spin" />
      case 'unknown': return <Activity className="h-5 w-5 text-gray-600" />
      default: return <Activity className="h-5 w-5 text-gray-600" />
    }
  }

  if (loading) {
    return (
      <div className="flex items-center justify-center h-96">
        <div className="text-center">
          <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-blue-600 mx-auto"></div>
          <p className="mt-4 text-gray-600">Cargando plantas...</p>
        </div>
      </div>
    )
  }

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <h1 className="text-3xl font-bold text-gray-900">Dashboard</h1>
        <div className="flex items-center space-x-3">
          <span className={`flex items-center space-x-1 text-sm ${wsConnected ? 'text-green-600' : 'text-red-600'}`}>
            <span className={`h-2 w-2 rounded-full ${wsConnected ? 'bg-green-600' : 'bg-red-600'}`}></span>
            <span>{wsConnected ? 'Tiempo real' : 'Desconectado'}</span>
          </span>
          {autoLoop ? (
            <button
              onClick={handleStopAuto}
              disabled={scanningAll}
              className={`flex items-center space-x-2 px-4 py-2 rounded-lg font-medium transition-colors text-white ${
                scanningAll ? 'bg-red-400 cursor-not-allowed' : 'bg-red-600 hover:bg-red-700'
              }`}
            >
              <Square className="h-4 w-4" />
              <span>Parar AUTO</span>
            </button>
          ) : (
            <button
              onClick={handleStartAuto}
              disabled={scanningAll}
              className={`flex items-center space-x-2 px-4 py-2 rounded-lg font-medium transition-colors ${
                scanningAll
                  ? 'bg-blue-400 cursor-not-allowed text-white'
                  : 'bg-blue-600 hover:bg-blue-700 text-white'
              }`}
            >
              {scanningAll ? (
                <><Loader className="h-4 w-4 animate-spin" /><span>Iniciando...</span></>
              ) : (
                <><Play className="h-4 w-4" /><span>Iniciar AUTO</span></>
              )}
            </button>
          )}
          <button
            onClick={() => loadPlants(true)}
            disabled={refreshing}
            className={`flex items-center space-x-2 px-4 py-2 rounded-lg font-medium transition-colors ${
              refreshing
                ? 'bg-blue-400 cursor-not-allowed text-white'
                : 'bg-gray-600 hover:bg-gray-700 text-white'
            }`}
          >
            {refreshing ? (
              <><Loader className="h-4 w-4 animate-spin" /><span>Actualizando...</span></>
            ) : (
              <><RefreshCw className="h-4 w-4" /><span>Actualizar</span></>
            )}
          </button>
          {user?.role === 'admin' && (
          <button
            onClick={() => setShowCreateModal(true)}
            className="flex items-center space-x-2 px-4 py-2 bg-green-600 text-white rounded-lg hover:bg-green-700 transition-colors"
          >
            <Plus className="h-4 w-4" />
            <span>Nueva Planta</span>
          </button>
          )}
        </div>
      </div>

      <div className="flex flex-col sm:flex-row gap-4">
        <div className="relative flex-1">
          <Search className="absolute left-3 top-1/2 transform -translate-y-1/2 h-5 w-5 text-gray-400" />
          <input
            type="text"
            placeholder="Buscar planta..."
            value={searchTerm}
            onChange={(e) => setSearchTerm(e.target.value)}
            className="w-full pl-10 pr-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent"
          />
        </div>
        <div className="flex items-center space-x-2">
          <Filter className="h-5 w-5 text-gray-400" />
          <select
            value={statusFilter}
            onChange={(e) => setStatusFilter(e.target.value)}
            className="px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500"
          >
            <option value="all">Todos los estados</option>
            <option value="green">Verde</option>
            <option value="yellow">Amarillo</option>
            <option value="red">Rojo</option>
            <option value="scanning">Escaneando</option>
            <option value="unknown">Desconocido</option>
          </select>
        </div>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
        {filteredPlants.map((plant) => (
          <div key={plant.id} className="bg-white rounded-xl shadow-md hover:shadow-lg transition-shadow border border-gray-200 p-6 relative group">
            {user?.role === 'admin' && (
            <div className="absolute top-2 right-2 flex items-center space-x-1 opacity-0 group-hover:opacity-100 transition-opacity">
              <button
                onClick={(e) => { e.preventDefault(); handleScanOne(plant.id) }}
                disabled={scanningPlantId === plant.id || autoLoop}
                className={`p-1.5 hover:bg-blue-100 rounded ${autoLoop ? 'text-gray-400 cursor-not-allowed' : 'text-blue-600'}`}
                title={autoLoop ? 'Detén el AUTO para escanear solo esta' : 'Escanear solo esta planta'}
              >
                {scanningPlantId === plant.id
                  ? <Loader className="h-4 w-4 animate-spin text-blue-600" />
                  : <Play className="h-4 w-4" />}
              </button>
              <button onClick={() => setEditPlant(plant)} className="p-1.5 hover:bg-blue-100 rounded text-blue-600" title="Editar">
                <Edit3 className="h-4 w-4" />
              </button>
              <button onClick={() => setDeleteConfirm(plant)} className="p-1.5 hover:bg-red-100 rounded text-red-500" title="Eliminar">
                <Trash2 className="h-4 w-4" />
              </button>
            </div>
            )}
            <Link to={`/plant/${plant.id}`}>
            <div className="flex items-start justify-between mb-4">
              <div>
                <div className="flex items-center space-x-2">
                  <h3 className="text-xl font-semibold text-gray-900">{plant.name}</h3>
                  {plant.vpn_status === 'demo' && (
                    <span className="text-xs bg-blue-100 text-blue-600 px-1.5 py-0.5 rounded">DEMO</span>
                  )}
                </div>
                <p className="text-sm text-gray-500 mt-1">
                  Ultima actualizacion: {plant.last_scan ? new Date(plant.last_scan).toLocaleString('es-ES') : 'Nunca'}
                </p>
              </div>
              <div className={`px-3 py-1 rounded-full border ${getStatusColor(plant.status)} flex items-center space-x-1`}>
                {getStatusIcon(plant.status)}
                <span className="text-xs font-medium capitalize">{plant.status === 'unknown' ? '?' : plant.status}</span>
              </div>
            </div>

            {scanProgress[plant.name] && (
              <div className="mt-3 space-y-1">
                <div className="flex items-center justify-between text-xs text-blue-700">
                  <span className="truncate pr-2">{scanProgress[plant.name].message}</span>
                  <span className="font-mono">{scanProgress[plant.name].percent}%</span>
                </div>
                <div className="w-full bg-blue-100 rounded-full h-1.5">
                  <div
                    className={`h-1.5 rounded-full transition-all duration-300 ${scanProgress[plant.name].stage === 'error' ? 'bg-red-500' : 'bg-blue-600'}`}
                    style={{ width: `${scanProgress[plant.name].percent}%` }}
                  />
                </div>
              </div>
            )}

            <div className="grid grid-cols-3 gap-4 mt-4">
              <div className="text-center">
                <div className="flex items-center justify-center mb-1">
                  <Wifi className="h-5 w-5 text-blue-600" />
                </div>
                <div className="text-2xl font-bold text-gray-900">{plant.gateways_count}</div>
                <div className="text-xs text-gray-500">Gateways</div>
              </div>
              
              <div className="text-center">
                <div className="flex items-center justify-center mb-1">
                  <Zap className="h-5 w-5 text-green-600" />
                </div>
                <div className="text-2xl font-bold text-gray-900">{plant.total_cards}</div>
                <div className="text-xs text-gray-500">Tarjetas</div>
              </div>
              
              <div className="text-center">
                <div className="flex items-center justify-center mb-1">
                  <AlertTriangle className={`h-5 w-5 ${plant.active_alarms > 0 ? 'text-red-600' : 'text-gray-400'}`} />
                </div>
                <div className="text-2xl font-bold text-gray-900">{plant.active_alarms}</div>
                <div className="text-xs text-gray-500">Alarmas</div>
              </div>
            </div>
          </Link>
          </div>
        ))}
      </div>

      {filteredPlants.length === 0 && plants.length > 0 && (
        <div className="text-center py-12 bg-white rounded-xl shadow-md">
          <Search className="h-16 w-16 text-gray-400 mx-auto mb-4" />
          <h3 className="text-xl font-medium text-gray-900 mb-2">Sin resultados</h3>
          <p className="text-gray-600">No se encontraron plantas con los filtros seleccionados</p>
        </div>
      )}

      {plants.length === 0 && (
        <div className="text-center py-12 bg-white rounded-xl shadow-md">
          <Activity className="h-16 w-16 text-gray-400 mx-auto mb-4" />
          <h3 className="text-xl font-medium text-gray-900 mb-2">No hay plantas configuradas</h3>
          <p className="text-gray-600">Crea la primera planta con el boton "Nueva Planta"</p>
        </div>
      )}

      {showCreateModal && (
        <div className="fixed inset-0 bg-black/50 z-50 flex items-center justify-center" onClick={() => setShowCreateModal(false)}>
          <div className="bg-white rounded-2xl shadow-2xl w-full max-w-lg mx-4 p-6 max-h-[90vh] overflow-y-auto" onClick={e => e.stopPropagation()}>
            <div className="flex items-center justify-between mb-6">
              <h2 className="text-xl font-bold text-gray-900">Nueva Planta</h2>
              <button onClick={() => setShowCreateModal(false)} className="p-1 hover:bg-gray-100 rounded">
                <X className="h-5 w-5" />
              </button>
            </div>
            
            {createError && (
              <div className="mb-4 p-3 bg-red-50 border border-red-200 rounded-lg text-red-700 text-sm">{createError}</div>
            )}

            <div className="space-y-4">
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">Nombre *</label>
                <input type="text" value={newPlant.name} onChange={e => setNewPlant({...newPlant, name: e.target.value})}
                  className="w-full px-3 py-2 border rounded-lg focus:ring-2 focus:ring-blue-500" placeholder="ACAMPO" />
              </div>
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">Client ID</label>
                <input type="text" value={newPlant.client_id} onChange={e => setNewPlant({...newPlant, client_id: e.target.value})}
                  className="w-full px-3 py-2 border rounded-lg focus:ring-2 focus:ring-blue-500" placeholder="Opcional" />
              </div>

              <div>
                <div className="flex items-center justify-between mb-1">
                  <label className="block text-sm font-medium text-gray-700">Gateways</label>
                  <button onClick={() => setNewGateways([...newGateways, { ip: '', id_start: 1, id_end: 32 }])}
                    className="text-sm text-blue-600 hover:text-blue-800 flex items-center space-x-1">
                    <Plus className="h-3 w-3" /><span>Añadir</span>
                  </button>
                </div>
                <div className="space-y-2 max-h-48 overflow-y-auto">
                  {newGateways.map((gw, i) => (
                    <div key={i} className="flex items-center space-x-2 p-2 bg-gray-50 rounded-lg">
                      <input type="text" value={gw.ip} onChange={e => {
                        const g = [...newGateways]; g[i] = {...g[i], ip: e.target.value}; setNewGateways(g)
                      }} className="flex-1 px-2 py-1.5 border rounded text-sm" placeholder="10.110.1.21" />
                      <input type="number" value={gw.id_start} onChange={e => {
                        const g = [...newGateways]; g[i] = {...g[i], id_start: Number(e.target.value)}; setNewGateways(g)
                      }} className="w-16 px-2 py-1.5 border rounded text-sm text-center" min={1} max={255} />
                      <span className="text-xs text-gray-400">-</span>
                      <input type="number" value={gw.id_end} onChange={e => {
                        const g = [...newGateways]; g[i] = {...g[i], id_end: Number(e.target.value)}; setNewGateways(g)
                      }} className="w-16 px-2 py-1.5 border rounded text-sm text-center" min={1} max={255} />
                      <button onClick={() => setNewGateways(newGateways.filter((_, j) => j !== i))}
                        className="p-1 hover:bg-red-100 rounded text-red-500">
                        <Trash2 className="h-4 w-4" />
                      </button>
                    </div>
                  ))}
                </div>
              </div>
            </div>

              <div className="border-t pt-4">
                <div className="flex items-center justify-between mb-3">
                  <div className="flex items-center space-x-2">
                    <Shield className="h-4 w-4 text-gray-500" />
                    <label className="text-sm font-medium text-gray-700">VPN / Tunel</label>
                  </div>
                  <label className="relative inline-flex items-center cursor-pointer">
                    <input type="checkbox" className="sr-only peer" checked={vpnEnabled} onChange={e => setVpnEnabled(e.target.checked)} />
                    <div className="w-9 h-5 bg-gray-200 peer-focus:outline-none rounded-full peer peer-checked:after:translate-x-full after:content-[''] after:absolute after:top-[2px] after:left-[2px] after:bg-white after:border-gray-300 after:border after:rounded-full after:h-4 after:w-4 after:transition-all peer-checked:bg-blue-600"></div>
                  </label>
                </div>

                {vpnEnabled && (
                  <div className="space-y-3 p-3 bg-gray-50 rounded-lg">
                    <div>
                      <label className="block text-xs font-medium text-gray-600 mb-1">Tipo</label>
                      <select value={vpnType} onChange={e => setVpnType(e.target.value)}
                        className="w-full px-2 py-1.5 border rounded text-sm">
                        <option value="openvpn">OpenVPN</option>
                        <option value="forticlient">FortiClient</option>
                        <option value="ssh">SSH Tunnel</option>
                      </select>
                    </div>

                    {vpnType === 'openvpn' && (
                      <>
                        <div>
                          <label className="block text-xs font-medium text-gray-600 mb-1">Subir archivo .ovpn</label>
                          <input type="file" accept=".ovpn,.conf"
                            onChange={e => { const f = e.target.files?.[0]; if (f) readOvpnFile(f) }}
                            className="w-full text-sm" />
                          <p className="mt-1 text-xs text-gray-500">
                            {ovpnFile
                              ? `Se guardara ${ovpnFile.name} en la carpeta de la planta`
                              : 'Se copia al servidor; si no lo subes, indica abajo el nombre del .ovpn ya existente.'}
                          </p>
                        </div>
                        <div>
                          <label className="block text-xs font-medium text-gray-600 mb-1">Archivo .ovpn (nombre o ruta en servidor)</label>
                          <input type="text" value={vpnConfig.config_path}
                            onChange={e => setVpnConfig({...vpnConfig, config_path: e.target.value})}
                            className="w-full px-2 py-1.5 border rounded text-sm" placeholder="openvpn.ovpn (default)" />
                        </div>
                        <div>
                          <label className="block text-xs font-medium text-gray-600 mb-1">Usuario</label>
                          <input type="text" value={vpnConfig.username}
                            onChange={e => setVpnConfig({...vpnConfig, username: e.target.value})}
                            className="w-full px-2 py-1.5 border rounded text-sm" placeholder="Opcional" />
                        </div>
                        <div>
                          <label className="block text-xs font-medium text-gray-600 mb-1">Contraseña</label>
                          <input type="password" value={vpnConfig.password}
                            onChange={e => setVpnConfig({...vpnConfig, password: e.target.value})}
                            className="w-full px-2 py-1.5 border rounded text-sm" placeholder="Opcional" />
                        </div>
                        <div>
                          <label className="block text-xs font-medium text-gray-600 mb-1">Key Password</label>
                          <input type="password" value={vpnConfig.key_password}
                            onChange={e => setVpnConfig({...vpnConfig, key_password: e.target.value})}
                            className="w-full px-2 py-1.5 border rounded text-sm" placeholder="Opcional" />
                        </div>
                      </>
                    )}

                    {vpnType === 'forticlient' && (
                      <>
                        <div>
                          <label className="block text-xs font-medium text-gray-600 mb-1">Tipo de conexión</label>
                          <select value={vpnConfig.subtype}
                            onChange={e => setVpnConfig({...vpnConfig, subtype: e.target.value})}
                            className="w-full px-2 py-1.5 border rounded text-sm"
                          >
                            <option value="ssl">SSL VPN</option>
                            <option value="ipsec">IPSec</option>
                          </select>
                        </div>
                        <div>
                          <label className="block text-xs font-medium text-gray-600 mb-1">Nombre del portal / conexión</label>
                          <input type="text" value={vpnConfig.vpn_name}
                            onChange={e => setVpnConfig({...vpnConfig, vpn_name: e.target.value})}
                            className="w-full px-2 py-1.5 border rounded text-sm" placeholder="ej: Oficina-VPN" />
                        </div>
                        <div>
                          <label className="block text-xs font-medium text-gray-600 mb-1">Servidor FortiGate (host)</label>
                          <input type="text" value={vpnConfig.host}
                            onChange={e => setVpnConfig({...vpnConfig, host: e.target.value})}
                            className="w-full px-2 py-1.5 border rounded text-sm" placeholder="ej: vpn.miempresa.com" />
                        </div>
                        {vpnConfig.subtype === 'ssl' && (
                          <>
                            <div>
                              <label className="block text-xs font-medium text-gray-600 mb-1">Puerto SSL</label>
                              <input type="number" value={vpnConfig.port}
                                onChange={e => setVpnConfig({...vpnConfig, port: Number(e.target.value)})}
                                className="w-full px-2 py-1.5 border rounded text-sm" />
                            </div>
                            <div>
                              <label className="block text-xs font-medium text-gray-600 mb-1">Usuario</label>
                              <input type="text" value={vpnConfig.username}
                                onChange={e => setVpnConfig({...vpnConfig, username: e.target.value})}
                                className="w-full px-2 py-1.5 border rounded text-sm" placeholder="Usuario VPN" />
                            </div>
                            <div>
                              <label className="block text-xs font-medium text-gray-600 mb-1">Contraseña</label>
                              <input type="password" value={vpnConfig.password}
                                onChange={e => setVpnConfig({...vpnConfig, password: e.target.value})}
                                className="w-full px-2 py-1.5 border rounded text-sm" placeholder="Contraseña VPN" />
                            </div>
                          </>
                        )}
                        {vpnConfig.subtype === 'ipsec' && (
                          <>
                            <div>
                              <label className="block text-xs font-medium text-gray-600 mb-1">Usuario</label>
                              <input type="text" value={vpnConfig.username}
                                onChange={e => setVpnConfig({...vpnConfig, username: e.target.value})}
                                className="w-full px-2 py-1.5 border rounded text-sm" placeholder="Usuario VPN (opcional)" />
                            </div>
                            <div>
                              <label className="block text-xs font-medium text-gray-600 mb-1">Contraseña compartida (PSK)</label>
                              <input type="password" value={vpnConfig.psk}
                                onChange={e => setVpnConfig({...vpnConfig, psk: e.target.value})}
                                className="w-full px-2 py-1.5 border rounded text-sm" placeholder="Clave pre-compartida" />
                            </div>
                            <div>
                              <label className="block text-xs font-medium text-gray-600 mb-1">Contraseña privada</label>
                              <input type="password" value={vpnConfig.private_key}
                                onChange={e => setVpnConfig({...vpnConfig, private_key: e.target.value})}
                                className="w-full px-2 py-1.5 border rounded text-sm" placeholder="Clave privada (opcional)" />
                            </div>
                          </>
                        )}

                        <details className="text-xs">
                          <summary className="text-blue-600 cursor-pointer hover:text-blue-800 select-none font-medium">
                            Ajustes avanzados
                          </summary>
                          <div className="mt-3 space-y-3 pl-2 border-l-2 border-blue-100">
                            {vpnConfig.subtype === 'ssl' && (
                              <>
                                <div>
                                  <label className="block text-xs font-medium text-gray-600 mb-1">Realm (dominio de autenticación)</label>
                                  <input type="text" value={vpnConfig.realm}
                                    onChange={e => setVpnConfig({...vpnConfig, realm: e.target.value})}
                                    className="w-full px-2 py-1 border rounded text-sm" placeholder="Opcional" />
                                </div>
                                <div>
                                  <label className="block text-xs font-medium text-gray-600 mb-1">Certificado de confianza (ruta)</label>
                                  <input type="text" value={vpnConfig.trusted_cert}
                                    onChange={e => setVpnConfig({...vpnConfig, trusted_cert: e.target.value})}
                                    className="w-full px-2 py-1 border rounded text-sm" placeholder="Opcional" />
                                </div>
                                <label className="flex items-center space-x-2 cursor-pointer">
                                  <input type="checkbox" checked={vpnConfig.allow_insecure}
                                    onChange={e => setVpnConfig({...vpnConfig, allow_insecure: e.target.checked})}
                                    className="w-3.5 h-3.5 text-blue-600 rounded" />
                                  <span className="text-gray-600">Permitir certificado no válido</span>
                                </label>
                              </>
                            )}
                            {vpnConfig.subtype === 'ipsec' && (
                              <>
                                <div className="border-b border-blue-100 pb-2 mb-2">
                                  <span className="text-blue-600 font-semibold">Fase 1 (IKE)</span>
                                </div>
                                <div className="grid grid-cols-2 gap-2">
                                  <div>
                                    <label className="block text-xs font-medium text-gray-600 mb-1">ID Local</label>
                                    <input type="text" value={vpnConfig.local_id}
                                      onChange={e => setVpnConfig({...vpnConfig, local_id: e.target.value})}
                                      className="w-full px-2 py-1 border rounded text-sm" placeholder="Opcional" />
                                  </div>
                                  <div>
                                    <label className="block text-xs font-medium text-gray-600 mb-1">ID Remoto</label>
                                    <input type="text" value={vpnConfig.remote_id}
                                      onChange={e => setVpnConfig({...vpnConfig, remote_id: e.target.value})}
                                      className="w-full px-2 py-1 border rounded text-sm" placeholder="Opcional" />
                                  </div>
                                </div>
                                <div>
                                  <label className="block text-xs font-medium text-gray-600 mb-1">Versión IKE</label>
                                  <select value={vpnConfig.ike_version}
                                    onChange={e => setVpnConfig({...vpnConfig, ike_version: e.target.value})}
                                    className="w-full px-2 py-1 border rounded text-sm"
                                  >
                                    <option value="v2">IKEv2</option>
                                    <option value="v1">IKEv1</option>
                                  </select>
                                </div>
                                <div className="grid grid-cols-2 gap-2">
                                  <div>
                                    <label className="block text-xs font-medium text-gray-600 mb-1">Propuesta IKE Fase 1</label>
                                    <select value={vpnConfig.phase1_proposal}
                                      onChange={e => setVpnConfig({...vpnConfig, phase1_proposal: e.target.value})}
                                      className="w-full px-2 py-1 border rounded text-sm"
                                    >
                                      <option value="AES256-SHA512">AES256-SHA512</option>
                                      <option value="AES256-SHA256">AES256-SHA256</option>
                                      <option value="AES128-SHA256">AES128-SHA256</option>
                                      <option value="AES128-SHA1">AES128-SHA1</option>
                                      <option value="3DES-SHA1">3DES-SHA1</option>
                                    </select>
                                  </div>
                                  <div>
                                    <label className="block text-xs font-medium text-gray-600 mb-1">DH Group Fase 1</label>
                                    <select value={vpnConfig.phase1_dh_group}
                                      onChange={e => setVpnConfig({...vpnConfig, phase1_dh_group: e.target.value})}
                                      className="w-full px-2 py-1 border rounded text-sm"
                                    >
                                      <option value="14">Group 14 (2048-bit)</option>
                                      <option value="5">Group 5 (1536-bit)</option>
                                      <option value="2">Group 2 (1024-bit)</option>
                                      <option value="19">Group 19 (ECP 256-bit)</option>
                                      <option value="20">Group 20 (ECP 384-bit)</option>
                                      <option value="21">Group 21 (ECP 521-bit)</option>
                                    </select>
                                  </div>
                                </div>
                                <div className="border-b border-blue-100 pb-2 mb-2">
                                  <span className="text-blue-600 font-semibold">Fase 2 (IPsec)</span>
                                </div>
                                <div className="grid grid-cols-2 gap-2">
                                  <div>
                                    <label className="block text-xs font-medium text-gray-600 mb-1">Propuesta Fase 2</label>
                                    <select value={vpnConfig.phase2_proposal}
                                      onChange={e => setVpnConfig({...vpnConfig, phase2_proposal: e.target.value})}
                                      className="w-full px-2 py-1 border rounded text-sm"
                                    >
                                      <option value="AES256-SHA512">AES256-SHA512</option>
                                      <option value="AES256-SHA256">AES256-SHA256</option>
                                      <option value="AES128-SHA256">AES128-SHA256</option>
                                      <option value="AES128-SHA1">AES128-SHA1</option>
                                      <option value="3DES-SHA1">3DES-SHA1</option>
                                    </select>
                                  </div>
                                  <div>
                                    <label className="block text-xs font-medium text-gray-600 mb-1">DH Group Fase 2</label>
                                    <select value={vpnConfig.phase2_dh_group}
                                      onChange={e => setVpnConfig({...vpnConfig, phase2_dh_group: e.target.value})}
                                      className="w-full px-2 py-1 border rounded text-sm"
                                    >
                                      <option value="14">Group 14 (2048-bit)</option>
                                      <option value="5">Group 5 (1536-bit)</option>
                                      <option value="2">Group 2 (1024-bit)</option>
                                      <option value="19">Group 19 (ECP 256-bit)</option>
                                      <option value="20">Group 20 (ECP 384-bit)</option>
                                      <option value="21">Group 21 (ECP 521-bit)</option>
                                    </select>
                                  </div>
                                </div>
                              </>
                            )}
                          </div>
                        </details>
                      </>
                    )}

                    {vpnType === 'ssh' && (
                      <>
                        <div>
                          <label className="block text-xs font-medium text-gray-600 mb-1">Host SSH</label>
                          <input type="text" value={vpnConfig.ssh_host}
                            onChange={e => setVpnConfig({...vpnConfig, ssh_host: e.target.value})}
                            className="w-full px-2 py-1.5 border rounded text-sm" placeholder="ej: 10.0.0.1" />
                        </div>
                        <div className="grid grid-cols-3 gap-2">
                          <div className="col-span-1">
                            <label className="block text-xs font-medium text-gray-600 mb-1">Puerto</label>
                            <input type="number" value={vpnConfig.ssh_port}
                              onChange={e => setVpnConfig({...vpnConfig, ssh_port: Number(e.target.value)})}
                              className="w-full px-2 py-1.5 border rounded text-sm" />
                          </div>
                          <div className="col-span-2">
                            <label className="block text-xs font-medium text-gray-600 mb-1">Usuario SSH</label>
                            <input type="text" value={vpnConfig.ssh_username}
                              onChange={e => setVpnConfig({...vpnConfig, ssh_username: e.target.value})}
                              className="w-full px-2 py-1.5 border rounded text-sm" placeholder="Opcional" />
                          </div>
                        </div>
                        <div>
                          <label className="block text-xs font-medium text-gray-600 mb-1">Contraseña SSH</label>
                          <input type="password" value={vpnConfig.ssh_password}
                            onChange={e => setVpnConfig({...vpnConfig, ssh_password: e.target.value})}
                            className="w-full px-2 py-1.5 border rounded text-sm" placeholder="Opcional" />
                        </div>
                        <div>
                          <label className="block text-xs font-medium text-gray-600 mb-1">Ruta clave privada (servidor)</label>
                          <input type="text" value={vpnConfig.ssh_key_path}
                            onChange={e => setVpnConfig({...vpnConfig, ssh_key_path: e.target.value})}
                            className="w-full px-2 py-1.5 border rounded text-sm" placeholder="Opcional" />
                        </div>
                      </>
                    )}
                  </div>
                )}
              </div>

            <div className="flex justify-end space-x-3 mt-6 pt-4 border-t">
              <button onClick={() => setShowCreateModal(false)}
                className="px-4 py-2 border rounded-lg hover:bg-gray-50 text-gray-700">Cancelar</button>
              <button onClick={handleCreatePlant} disabled={creating}
                className={`px-6 py-2 rounded-lg text-white font-medium ${creating ? 'bg-green-400' : 'bg-green-600 hover:bg-green-700'}`}>
                {creating ? 'Creando...' : 'Crear Planta'}
              </button>
            </div>
          </div>
        </div>
      )}

      {editPlant && (
        <div className="fixed inset-0 bg-black/50 z-50 flex items-center justify-center" onClick={() => setEditPlant(null)}>
          <div className="bg-white rounded-2xl shadow-2xl w-full max-w-md mx-4 p-6" onClick={e => e.stopPropagation()}>
            <div className="flex items-center justify-between mb-6">
              <h2 className="text-xl font-bold text-gray-900">Editar Planta</h2>
              <button onClick={() => setEditPlant(null)} className="p-1 hover:bg-gray-100 rounded"><X className="h-5 w-5" /></button>
            </div>
            {createError && (
              <div className="mb-4 p-3 bg-red-50 border border-red-200 rounded-lg text-red-700 text-sm">{createError}</div>
            )}
            <div className="space-y-4">
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">Nombre</label>
                <input type="text" value={editPlant.name} onChange={e => setEditPlant({...editPlant, name: e.target.value})}
                  className="w-full px-3 py-2 border rounded-lg focus:ring-2 focus:ring-blue-500" />
              </div>
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">Client ID</label>
                <input type="text" value={editPlant.client_id || ''} onChange={e => setEditPlant({...editPlant, client_id: e.target.value})}
                  className="w-full px-3 py-2 border rounded-lg focus:ring-2 focus:ring-blue-500" />
              </div>
            </div>
            <div className="flex justify-end space-x-3 mt-6 pt-4 border-t">
              <button onClick={() => setEditPlant(null)}
                className="px-4 py-2 border rounded-lg hover:bg-gray-50 text-gray-700">Cancelar</button>
              <button onClick={handleUpdatePlant} disabled={creating}
                className={`px-6 py-2 rounded-lg text-white font-medium ${creating ? 'bg-blue-400' : 'bg-blue-600 hover:bg-blue-700'}`}>
                {creating ? 'Guardando...' : 'Guardar'}
              </button>
            </div>
          </div>
        </div>
      )}

      {deleteConfirm && (
        <div className="fixed inset-0 bg-black/50 z-50 flex items-center justify-center" onClick={() => setDeleteConfirm(null)}>
          <div className="bg-white rounded-2xl shadow-2xl w-full max-w-sm mx-4 p-6" onClick={e => e.stopPropagation()}>
            <div className="text-center mb-6">
              <AlertTriangle className="h-12 w-12 text-red-500 mx-auto mb-3" />
              <h2 className="text-xl font-bold text-gray-900">Eliminar Planta</h2>
              <p className="text-gray-600 mt-2">Se eliminara <strong>{deleteConfirm.name}</strong> y todos sus gateways y datos. Esta accion no se puede deshacer.</p>
            </div>
            <div className="flex justify-center space-x-3">
              <button onClick={() => setDeleteConfirm(null)}
                className="px-4 py-2 border rounded-lg hover:bg-gray-50 text-gray-700">Cancelar</button>
              <button onClick={handleDeletePlant}
                className="px-6 py-2 rounded-lg text-white font-medium bg-red-600 hover:bg-red-700">Eliminar</button>
            </div>
          </div>
        </div>
      )}
    </div>
  )
}
