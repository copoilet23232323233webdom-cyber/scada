import { useEffect, useState, useRef, useCallback } from 'react'
import { useParams, Link, useNavigate } from 'react-router-dom'
import { plantsAPI, gatewaysAPI, cardsAPI, alarmsAPI, scanAPI } from '../services/api'
import { useAuth } from '../context/AuthContext'
import { Plant, Gateway, Card, Alarm } from '../types'
import { 
  ArrowLeft, Wifi, Activity, AlertTriangle, CheckCircle, Clock, 
  RefreshCw, Cpu, X, Loader, Radio, FileText, Download, Settings
} from 'lucide-react'
import { reportAPI } from '../services/api'
import PlantVpnSettings from '../components/PlantVpnSettings'

export default function PlantDetail() {
  const { plantId } = useParams<{ plantId: string }>()
  const navigate = useNavigate()
  const [plant, setPlant] = useState<Plant | null>(null)
  const [gateways, setGateways] = useState<Gateway[]>([])
  const [alarms, setAlarms] = useState<Alarm[]>([])
  const [loading, setLoading] = useState(true)
  const [scanning, setScanning] = useState(false)
  const [scanMessage, setScanMessage] = useState('')
  const [selectedGateway, setSelectedGateway] = useState<Gateway | null>(null)
  const [gatewayCards, setGatewayCards] = useState<Card[]>([])
  const [loadingCards, setLoadingCards] = useState(false)
  const [vpnStatus, setVpnStatus] = useState<string>('')
  const [showReportModal, setShowReportModal] = useState(false)
  const [generatingReport, setGeneratingReport] = useState(false)
  const [editingGateway, setEditingGateway] = useState<Gateway | null>(null)
  const [createGatewayOpen, setCreateGatewayOpen] = useState(false)
  const [newGateway, setNewGateway] = useState({ ip: '', id_start: 1, id_end: 32 })
  const [editGateway, setEditGateway] = useState({ ip: '', id_start: 1, id_end: 32 })
  const [deleteGatewayId, setDeleteGatewayId] = useState<number | null>(null)
  const [gatewaySaving, setGatewaySaving] = useState(false)
  const wsRef = useRef<WebSocket | null>(null)
  const scanTimeoutRef = useRef<number | null>(null)
  // El WebSocket se abre antes de tener la planta cargada: sin esta ref el
  // handler capturaría plant=null y descartaría todos los eventos.
  const plantRef = useRef<Plant | null>(null)
  const [selectedCard, setSelectedCard] = useState<Card | null>(null)
  const [scanProgress, setScanProgress] = useState(0)
  const [scanStage, setScanStage] = useState('')
  useEffect(() => { plantRef.current = plant }, [plant])
  const [reportOpts, setReportOpts] = useState({
    incluir_alarmas: true,
    incluir_diag: false,
    incluir_voltaje: true,
    incluir_strings: false,
    umbral_strings: 30
  })
  const { user } = useAuth()
  const loadingData = useRef(false)
  const wsClosed = useRef(false)

  useEffect(() => {
    if (plantId) {
      loadData()
      connectWebSocket()
    }
    return () => {
      wsClosed.current = true
      if (wsRef.current) wsRef.current.close()
      if (scanTimeoutRef.current) clearTimeout(scanTimeoutRef.current)
    }
  }, [plantId])

  const loadData = useCallback(async () => {
    // Durante un escaneo llegan muchos eventos seguidos: una recarga a la vez.
    if (loadingData.current) return
    loadingData.current = true
    try {
      const [plantRes, gatewaysRes, alarmsRes] = await Promise.all([
        plantsAPI.getById(parseInt(plantId!)),
        gatewaysAPI.getByPlant(parseInt(plantId!)),
        alarmsAPI.getAll({ plant_id: plantId })
      ])
      
      setPlant(plantRes.data)
      setGateways(gatewaysRes.data)
      const alarmsData = alarmsRes.data
      setAlarms(Array.isArray(alarmsData) ? alarmsData : (alarmsData.alarms || []))
    } catch (error) {
      console.error('Error cargando datos:', error)
    } finally {
      loadingData.current = false
      setLoading(false)
    }
  }, [plantId])

  const connectWebSocket = () => {
    try {
      const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:'
      // Mismo origen que la app (el dev server hace de proxy hacia el backend).
      const wsHost = import.meta.env.VITE_WS_HOST || window.location.host
      const wsUrl = `${protocol}//${wsHost}/api/ws/status`
      const ws = new WebSocket(wsUrl)

      ws.onmessage = (event) => {
        try {
          const msg = JSON.parse(event.data)
          const plantName = msg.data?.plant_name
          const currentPlant = plantRef.current
          if (!currentPlant || !plantName || plantName !== currentPlant.name) return

          const data = msg.data
          if (msg.type === 'scan_progress') {
            setScanStage(data.stage)
            setScanProgress(data.percent)
            setScanMessage(data.message || '')
            if (data.stage === 'scanning' || data.stage === 'vpn' || data.stage === 'starting') {
              setScanning(true)
            }
            if (data.stage === 'complete' || data.stage === 'error') {
              setScanning(false)
              setVpnStatus('')
              loadData()
              if (data.stage === 'error') {
                window.setTimeout(() => { setScanProgress(0); setScanStage('') }, 5000)
              }
            }
            return
          }
          if (msg.type === 'scan_update') {
            setGateways(prev => {
              const next = prev.map(gw =>
                gw.ip === data.gateway_ip
                  ? { ...gw, status: data.status, total_cards: data.total_cards, active_cards: data.active_cards, failed_cards: data.failed_cards, response_time_ms: data.response_time_ms }
                  : gw
              )
              return next
            })
            return
          }
          if (data.status === 'connecting_vpn') {
            setVpnStatus('conectando')
          } else if (['green', 'yellow', 'red', 'unknown', 'error'].includes(data.status)) {
            setVpnStatus('')
            loadData()
          }
        } catch (e) {}
      }

      ws.onclose = () => {
        if (!wsClosed.current) setTimeout(connectWebSocket, 5000)
      }

      wsRef.current = ws
    } catch (e) {
      console.error('Error WebSocket:', e)
    }
  }

  const handleScan = async () => {
    if (!plant) return
    setScanning(true)
    setScanMessage('Iniciando escaneo...')
    setVpnStatus('iniciando')
    setScanProgress(5)
    setScanStage('starting')
    try {
      await scanAPI.scanPlant(plant.id)
      // Red de seguridad por si se pierde el WebSocket: el escaneo real de una
      // planta va muy por debajo de este límite.
      if (scanTimeoutRef.current) clearTimeout(scanTimeoutRef.current)
      scanTimeoutRef.current = window.setTimeout(() => {
        setScanning(false)
        setScanMessage('')
        setVpnStatus('')
        setScanProgress(0)
        setScanStage('')
        loadData()
      }, 120000)
    } catch (error) {
      console.error('Error:', error)
      setScanning(false)
      setScanMessage('Error al iniciar escaneo')
    }
  }

  const handleGatewayClick = async (gateway: Gateway) => {
    setSelectedGateway(gateway)
    setLoadingCards(true)
    try {
      const response = await cardsAPI.getByGateway(gateway.id)
      setGatewayCards(response.data)
    } catch (error) {
      console.error('Error cargando tarjetas:', error)
      setGatewayCards([])
    } finally {
      setLoadingCards(false)
    }
  }

  const handleGenerateReport = async (format: string) => {
    if (!plant) return
    setGeneratingReport(true)
    try {
      const response = format === 'csv' 
        ? await reportAPI.generateCsv(plant.id, reportOpts)
        : await reportAPI.generatePdf(plant.id, reportOpts)

      const url = window.URL.createObjectURL(new Blob([response.data]))
      const link = document.createElement('a')
      link.href = url
      const ext = format === 'csv' ? 'csv' : 'pdf'
      const timestamp = new Date().toISOString().replace(/[:.]/g, '').slice(0, 15)
      link.download = `${plant.name}_${timestamp}.${ext}`
      document.body.appendChild(link)
      link.click()
      document.body.removeChild(link)
      window.URL.revokeObjectURL(url)
      setShowReportModal(false)
    } catch (error) {
      console.error('Error generando reporte:', error)
    } finally {
      setGeneratingReport(false)
    }
  }

  const getStatusColor = (status: string) => {
    switch (status) {
      case 'green': return 'bg-green-100 text-green-800'
      case 'red': return 'bg-red-100 text-red-800'
      case 'yellow': return 'bg-yellow-100 text-yellow-800'
      case 'success': return 'bg-green-100 text-green-800'
      default: return 'bg-gray-100 text-gray-800'
    }
  }

  const getGatewayStatusIcon = (status: string) => {
    switch (status) {
      case 'green': return <CheckCircle className="h-5 w-5 text-green-600" />
      case 'red': return <AlertTriangle className="h-5 w-5 text-red-600" />
      case 'yellow': return <AlertTriangle className="h-5 w-5 text-yellow-600" />
      case 'success': return <CheckCircle className="h-5 w-5 text-green-600" />
      default: return <Activity className="h-5 w-5 text-gray-400" />
    }
  }

  const getCardStatusIcon = (card: Card) => {
    if (card.maintenance_mode) return <Cpu className="h-5 w-5 text-yellow-500" />
    if (card.disabled) return <X className="h-5 w-5 text-gray-400" />
    if (!card.communication_ok) return <AlertTriangle className="h-5 w-5 text-red-500" />
    if (card.sec_alarm || card.overvoltage_alarm) return <AlertTriangle className="h-5 w-5 text-yellow-500" />
    return <CheckCircle className="h-5 w-5 text-green-500" />
  }

  const getCardStatusText = (card: Card) => {
    if (card.maintenance_mode) return 'Mantenimiento'
    if (card.disabled) return 'Deshabilitada'
    if (!card.communication_ok) return 'Sin comunicación'
    const alarms = []
    if (card.sec_alarm) alarms.push('SEC abierto')
    if (card.overvoltage_alarm) alarms.push('Sobretensión')
    if (alarms.length > 0) return alarms.join(' + ')
    return 'OK'
  }

  const getPlantVpnStatusBadge = () => {
    if (!plant) return null
    const status = plant.vpn_status
    if (status === 'connected') return <span className="text-xs bg-green-100 text-green-700 px-2 py-0.5 rounded-full">VPN</span>
    if (status === 'demo') return <span className="text-xs bg-blue-100 text-blue-700 px-2 py-0.5 rounded-full">DEMO</span>
    if (status === 'error') return <span className="text-xs bg-red-100 text-red-700 px-2 py-0.5 rounded-full">VPN Error</span>
    return <span className="text-xs bg-gray-100 text-gray-500 px-2 py-0.5 rounded-full">Sin VPN</span>
  }

  const handleEditGateway = (gateway: Gateway, e: React.MouseEvent) => {
    e.stopPropagation()
    setEditingGateway(gateway)
    setEditGateway({ ip: gateway.ip, id_start: gateway.id_start, id_end: gateway.id_end })
  }

  const handleSaveGateway = async () => {
    if (!editingGateway) return
    setGatewaySaving(true)
    try {
      await gatewaysAPI.update(editingGateway.id, editGateway)
      setEditingGateway(null)
      loadData()
    } catch (error) {
      console.error('Error al actualizar gateway:', error)
    } finally {
      setGatewaySaving(false)
    }
  }

  const handleCreateGateway = async () => {
    if (!plant) return
    setGatewaySaving(true)
    try {
      await gatewaysAPI.create({ plant_id: plant.id, ...newGateway })
      setCreateGatewayOpen(false)
      setNewGateway({ ip: '', id_start: 1, id_end: 32 })
      loadData()
    } catch (error) {
      console.error('Error al crear gateway:', error)
    } finally {
      setGatewaySaving(false)
    }
  }

  const handleDeleteGateway = async () => {
    if (!deleteGatewayId) return
    try {
      await gatewaysAPI.delete(deleteGatewayId)
      setDeleteGatewayId(null)
      loadData()
    } catch (error) {
      console.error('Error al eliminar gateway:', error)
    }
  }

  if (loading) {
    return (
      <div className="flex items-center justify-center h-96">
        <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-blue-600"></div>
      </div>
    )
  }

  if (!plant) {
    return <div className="text-center py-12">Planta no encontrada</div>
  }

  const gatewaysOk = gateways.filter(g => g.status === 'green' || g.status === 'success').length
  const gatewayWarnings = gateways.filter(g => g.status === 'yellow').length

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div className="flex items-center space-x-4">
          <Link to="/" className="p-2 hover:bg-gray-100 rounded-lg transition-colors">
            <ArrowLeft className="h-6 w-6" />
          </Link>
          <div>
            <div className="flex items-center space-x-2">
              <h1 className="text-3xl font-bold text-gray-900">{plant.name}</h1>
              {getPlantVpnStatusBadge()}
            </div>
            <p className="text-gray-600 mt-1">
              Última actualización: {plant.last_scan ? new Date(plant.last_scan).toLocaleString('es-ES') : 'Nunca'}
              {vpnStatus && <span className="ml-2 text-xs text-blue-500">VPN: {vpnStatus}</span>}
            </p>
          </div>
        </div>
        <div className="flex items-center space-x-3">
          <button
            onClick={() => setShowReportModal(true)}
            className="flex items-center space-x-2 px-4 py-3 rounded-lg font-medium bg-purple-600 hover:bg-purple-700 text-white transition-all"
          >
            <FileText className="h-5 w-5" />
            <span>Reporte</span>
          </button>
          <button
            onClick={handleScan}
            disabled={scanning}
            className={`flex items-center space-x-2 px-6 py-3 rounded-lg font-medium transition-all ${
              scanning 
                ? 'bg-blue-400 cursor-not-allowed text-white' 
                : 'bg-blue-600 hover:bg-blue-700 text-white shadow-lg hover:shadow-xl'
            }`}
          >
            {scanning ? (
              <>
                <Loader className="h-5 w-5 animate-spin" />
                <span>{scanMessage || 'Escaneando...'}</span>
              </>
            ) : (
              <>
                <RefreshCw className="h-5 w-5" />
                <span>Escanear Ahora</span>
              </>
            )}
          </button>
        </div>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-5 gap-6">
        <div className="bg-white rounded-xl shadow-md p-6">
          <div className="flex items-center justify-between mb-2">
            <Wifi className="h-8 w-8 text-blue-600" />
            <span className="text-3xl font-bold text-gray-900">{gateways.length}</span>
          </div>
          <h3 className="text-sm font-medium text-gray-600">Gateways</h3>
        </div>
        <div className="bg-white rounded-xl shadow-md p-6">
          <div className="flex items-center justify-between mb-2">
            <Activity className="h-8 w-8 text-green-600" />
            <span className="text-3xl font-bold text-gray-900">{plant.total_cards}</span>
          </div>
          <h3 className="text-sm font-medium text-gray-600">Tarjetas</h3>
        </div>
        <div className="bg-white rounded-xl shadow-md p-6">
          <div className="flex items-center justify-between mb-2">
            <CheckCircle className="h-8 w-8 text-green-600" />
            <span className="text-3xl font-bold text-gray-900">{gatewaysOk}</span>
          </div>
          <h3 className="text-sm font-medium text-gray-600">Gateways OK</h3>
        </div>
        <div className="bg-white rounded-xl shadow-md p-6">
          <div className="flex items-center justify-between mb-2">
            <AlertTriangle className={`h-8 w-8 ${gatewayWarnings > 0 ? 'text-yellow-600' : 'text-gray-400'}`} />
            <span className="text-3xl font-bold text-gray-900">{gatewayWarnings}</span>
          </div>
          <h3 className="text-sm font-medium text-gray-600">Amarillos</h3>
        </div>
        <div className="bg-white rounded-xl shadow-md p-6">
          <div className="flex items-center justify-between mb-2">
            <AlertTriangle className={`h-8 w-8 ${plant.active_alarms > 0 ? 'text-red-600' : 'text-gray-400'}`} />
            <span className="text-3xl font-bold text-gray-900">{plant.active_alarms}</span>
          </div>
          <h3 className="text-sm font-medium text-gray-600">Alarmas</h3>
        </div>
      </div>

      {scanning && (
        <div className="bg-white border border-blue-200 rounded-xl shadow-sm p-4 space-y-2">
          <div className="flex items-center justify-between text-sm">
            <div className="flex items-center space-x-2 text-blue-700">
              <Loader className="h-4 w-4 animate-spin" />
              <span className="font-medium">{scanMessage || 'Escaneando...'}</span>
            </div>
            <span className="text-blue-500 font-mono text-xs">{scanProgress}%</span>
          </div>
          <div className="w-full bg-blue-100 rounded-full h-2">
            <div
              className="bg-blue-600 h-2 rounded-full transition-all duration-500 ease-out"
              style={{ width: `${scanProgress}%` }}
            />
          </div>
          <div className="flex items-center justify-between text-xs text-gray-400">
            <span>
              {scanStage === 'starting' && 'Preparando...'}
              {scanStage === 'vpn' && 'Conectando VPN...'}
              {scanStage === 'scanning' && 'Escaneando gateways...'}
              {scanStage === 'complete' && 'Completado'}
            </span>
            {scanStage === 'scanning' && <span>Escaneando en tiempo real...</span>}
          </div>
        </div>
      )}

      {user?.role === 'admin' && plant && <PlantVpnSettings plantId={plant.id} />}

      <div className="bg-white rounded-xl shadow-md">
        <div className="px-6 py-4 border-b border-gray-200 flex items-center justify-between">
          <h2 className="text-xl font-semibold text-gray-900">
            Gateways
            {scanning && (
              <span className="ml-2 text-sm text-blue-600">
                <Loader className="h-4 w-4 inline animate-spin mr-1" />
                Escaneando...
              </span>
            )}
          </h2>
          {user?.role === 'admin' && (
            <button
              onClick={() => setCreateGatewayOpen(true)}
              className="px-4 py-2 bg-blue-600 hover:bg-blue-700 text-white rounded-lg text-sm font-medium transition-colors"
            >
              + Añadir Gateway
            </button>
          )}
        </div>
        <div className="divide-y divide-gray-200">
          {gateways.map((gateway) => (
            <div 
              key={gateway.id} 
              className="px-6 py-4 hover:bg-gray-50 cursor-pointer transition-colors"
              onClick={() => handleGatewayClick(gateway)}
            >
              <div className="flex items-center justify-between">
                <div className="flex items-center space-x-3">
                  <div className={`p-2 rounded-lg ${getStatusColor(gateway.status)}`}>
                    {getGatewayStatusIcon(gateway.status)}
                  </div>
                  <div>
                    <h3 className="text-lg font-medium text-gray-900 hover:text-blue-600">
                      {gateway.ip}
                      <span className="ml-2 text-xs text-blue-500">(clic para ver tarjetas)</span>
                    </h3>
                    <p className="text-sm text-gray-500">
                      IDs: {gateway.id_start || 1}-{gateway.id_end || 32} | 
                      Respuesta: {gateway.response_time_ms ? `${gateway.response_time_ms.toFixed(0)}ms` : 'N/A'}
                    </p>
                  </div>
                </div>
                <div className="flex items-center space-x-4">
                  <div className="text-right">
                    <div className="text-sm text-gray-600">
                      <span className="font-medium text-green-600">{gateway.active_cards}</span> / {gateway.total_cards} tarjetas
                      {gateway.failed_cards > 0 && (
                        <span className="ml-2 text-red-600">({gateway.failed_cards} fallos)</span>
                      )}
                    </div>
                    <div className="text-xs text-gray-500 mt-1">
                      <span className={gateway.lora_ok ? 'text-green-600' : 'text-red-600'}>
                        LoRa: {gateway.lora_ok ? '✓' : '✗'}
                      </span>
                      {gateway.consecutive_errors > 0 && (
                        <span className="ml-2 text-red-600">Errores: {gateway.consecutive_errors}</span>
                      )}
                    </div>
                  </div>
                  {user?.role === 'admin' && (
                    <div className="flex items-center space-x-1">
                      <button
                        onClick={(e) => handleEditGateway(gateway, e)}
                        className="p-2 hover:bg-gray-200 rounded-lg text-gray-500 hover:text-blue-600 transition-colors"
                        title="Editar gateway"
                      >
                        <svg className="h-4 w-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
                          <path strokeLinecap="round" strokeLinejoin="round" d="M11 5H6a2 2 0 00-2 2v11a2 2 0 002 2h11a2 2 0 002-2v-5m-1.414-9.414a2 2 0 112.828 2.828L11.828 15H9v-2.828l8.586-8.586z" />
                        </svg>
                      </button>
                      <button
                        onClick={(e) => { e.stopPropagation(); setDeleteGatewayId(gateway.id) }}
                        className="p-2 hover:bg-gray-200 rounded-lg text-gray-500 hover:text-red-600 transition-colors"
                        title="Eliminar gateway"
                      >
                        <svg className="h-4 w-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
                          <path strokeLinecap="round" strokeLinejoin="round" d="M19 7l-.867 12.142A2 2 0 0116.138 21H7.862a2 2 0 01-1.995-1.858L5 7m5 4v6m4-6v6m1-10V4a1 1 0 00-1-1h-4a1 1 0 00-1 1v3M4 7h16" />
                        </svg>
                      </button>
                    </div>
                  )}
                </div>
              </div>
            </div>
          ))}
          {gateways.length === 0 && (
            <div className="px-6 py-8 text-center text-gray-500">
              <Wifi className="h-12 w-12 mx-auto mb-3 text-gray-300" />
              <p>No hay gateways configurados</p>
            </div>
          )}
        </div>
      </div>

      {selectedGateway && (
        <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50" onClick={() => setSelectedGateway(null)}>
          <div className="bg-white rounded-xl shadow-xl max-w-2xl w-full mx-4 max-h-[80vh] overflow-y-auto" onClick={(e) => e.stopPropagation()}>
            <div className="px-6 py-4 border-b border-gray-200 flex items-center justify-between sticky top-0 bg-white">
              <div>
                <h2 className="text-xl font-bold text-gray-900">
                  Gateway: {selectedGateway.ip}
                </h2>
                <p className="text-sm text-gray-500">
                  IDs Modbus: {selectedGateway.id_start || 1} - {selectedGateway.id_end || 32} |
                  Firmware: {selectedGateway.firmware || 'N/A'}
                </p>
              </div>
              <div className="flex items-center gap-2">
                <button
                  onClick={() => navigate(`/gateway/${selectedGateway.id}/control`)}
                  className="flex items-center gap-2 px-3 py-2 bg-blue-600 text-white rounded-lg text-sm hover:bg-blue-700"
                  title="Control avanzado"
                >
                  <Settings className="w-4 h-4" /> Control Avanzado
                </button>
                <button
                  onClick={() => setSelectedGateway(null)}
                  className="p-2 hover:bg-gray-100 rounded-lg"
                >
                  <X className="h-6 w-6" />
                </button>
              </div>
            </div>
            
            <div className="p-6">
              {loadingCards ? (
                <div className="flex items-center justify-center py-12">
                  <Loader className="h-8 w-8 animate-spin text-blue-600" />
                </div>
              ) : gatewayCards.length === 0 ? (
                <div className="text-center py-12 text-gray-500">
                  <Cpu className="h-12 w-12 mx-auto mb-3 text-gray-300" />
                  <p>No hay tarjetas disponibles para este gateway</p>
                  <p className="text-sm mt-1">Usa el botón "Escanear Ahora" para descubrir las tarjetas</p>
                </div>
              ) : (
                <div className="space-y-3">
                  <div className="flex items-center justify-between mb-4">
                    <h3 className="font-semibold text-gray-700">
                      Tarjetas ({gatewayCards.length})
                    </h3>
                    <span className="text-xs text-gray-500">
                      {gatewayCards.filter(c => c.communication_ok).length} activas / 
                      {gatewayCards.filter(c => c.sec_alarm || c.overvoltage_alarm).length} alarmas
                    </span>
                  </div>
                  {gatewayCards.map((card) => (
                    <div
                      key={card.id}
                      onClick={() => setSelectedCard(card)}
                      className="border border-gray-200 rounded-lg p-4 hover:bg-gray-50 hover:shadow-sm transition-all cursor-pointer"
                    >
                      <div className="flex items-center justify-between">
                        <div className="flex items-center space-x-3">
                          <div className="p-2 rounded-lg bg-gray-100">
                            {getCardStatusIcon(card)}
                          </div>
                          <div>
                            <h4 className="font-medium text-gray-900">
                              Tarjeta ID: {card.modbus_id}
                            </h4>
                            <p className="text-sm text-gray-500">
                              {getCardStatusText(card)}
                            </p>
                          </div>
                        </div>
                        <div className="text-right text-sm text-gray-600">
                          <div>
                            Voltaje: {card.voltage ? `${card.voltage}V` : 'N/A'}
                            {card.lora_ok !== undefined && (
                              <span className={`ml-2 text-xs ${card.lora_ok ? 'text-green-600' : 'text-red-600'}`}>
                                <Radio className="h-3 w-3 inline" /> LoRa: {card.lora_ok ? 'OK' : 'No'}
                              </span>
                            )}
                          </div>
                          <div className="text-xs text-gray-400 mt-1">
                            {card.last_contact ? new Date(card.last_contact).toLocaleString('es-ES') : 'Sin contacto'}
                            {card.response_time_ms && ` | ${card.response_time_ms.toFixed(0)}ms`}
                          </div>
                        </div>
                      </div>
                      {card.sec_alarm && (
                        <div className="mt-2 px-3 py-1 bg-yellow-50 text-yellow-700 text-sm rounded">
                          ⚠️ Alarma SEC activa
                        </div>
                      )}
                      {card.overvoltage_alarm && (
                        <div className="mt-2 px-3 py-1 bg-yellow-50 text-yellow-700 text-sm rounded">
                          ⚡ Alarma de sobretensión activa
                        </div>
                      )}
                      {!card.communication_ok && (
                        <div className="mt-2 px-3 py-1 bg-red-50 text-red-700 text-sm rounded">
                          🚫 Sin comunicación con esta tarjeta
                          {card.last_error_message && <span className="ml-2">({card.last_error_message})</span>}
                        </div>
                      )}
                      {card.maintenance_mode && (
                        <div className="mt-2 px-3 py-1 bg-yellow-50 text-yellow-700 text-sm rounded">
                          🔧 En mantenimiento
                        </div>
                      )}
                    </div>
                  ))}
                </div>
              )}
            </div>
          </div>
        </div>
      )}

      {alarms.length > 0 && (
        <div className="bg-white rounded-xl shadow-md">
          <div className="px-6 py-4 border-b border-gray-200">
            <h2 className="text-xl font-semibold text-gray-900">Alarmas ({alarms.length})</h2>
          </div>
          <div className="divide-y divide-gray-200">
            {alarms.slice(0, 10).map((alarm) => (
              <div key={alarm.id} className="px-6 py-4">
                <div className="flex items-start justify-between">
                  <div>
                    <h3 className="text-lg font-medium text-gray-900">{alarm.alarm_type}</h3>
                    <p className="text-sm text-gray-600 mt-1">{alarm.description || ''}</p>
                    {alarm.gateway_ip && (
                      <p className="text-xs text-gray-500 mt-1">Gateway: {alarm.gateway_ip}</p>
                    )}
                    {alarm.card_id && (
                      <p className="text-xs text-gray-500">Tarjeta ID: {alarm.card_id}</p>
                    )}
                  </div>
                  <div className="text-right">
                    <span className={`px-3 py-1 rounded-full text-xs font-medium ${
                      alarm.status === 'active' ? 'bg-red-100 text-red-800' : 'bg-green-100 text-green-800'
                    }`}>
                      {alarm.status}
                    </span>
                    <div className="flex items-center text-xs text-gray-500 mt-2">
                      <Clock className="h-3 w-3 mr-1" />
                      {new Date(alarm.created_at).toLocaleString('es-ES')}
                    </div>
                    {alarm.acknowledged_at && (
                      <div className="text-xs text-gray-400 mt-1">
                        Reconocida: {new Date(alarm.acknowledged_at).toLocaleString('es-ES')}
                      </div>
                    )}
                  </div>
                </div>
              </div>
            ))}
          </div>
        </div>
      )}

      {editingGateway && (
        <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50" onClick={() => setEditingGateway(null)}>
          <div className="bg-white rounded-xl shadow-xl max-w-md w-full mx-4 p-6" onClick={(e) => e.stopPropagation()}>
            <div className="flex items-center justify-between mb-6">
              <h2 className="text-xl font-bold text-gray-900">Editar Gateway</h2>
              <button onClick={() => setEditingGateway(null)} className="p-2 hover:bg-gray-100 rounded-lg">
                <X className="h-6 w-6" />
              </button>
            </div>
            <div className="space-y-4">
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">IP</label>
                <input
                  type="text"
                  value={editGateway.ip}
                  onChange={(e) => setEditGateway({ ...editGateway, ip: e.target.value })}
                  className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-blue-500"
                />
              </div>
              <div className="grid grid-cols-2 gap-4">
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-1">ID Inicio</label>
                  <input
                    type="number"
                    value={editGateway.id_start}
                    onChange={(e) => setEditGateway({ ...editGateway, id_start: parseInt(e.target.value) || 1 })}
                    className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-blue-500"
                  />
                </div>
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-1">ID Fin</label>
                  <input
                    type="number"
                    value={editGateway.id_end}
                    onChange={(e) => setEditGateway({ ...editGateway, id_end: parseInt(e.target.value) || 32 })}
                    className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-blue-500"
                  />
                </div>
              </div>
              <div className="flex space-x-3 pt-2">
                <button
                  onClick={() => setEditingGateway(null)}
                  className="flex-1 px-4 py-2 border border-gray-300 text-gray-700 rounded-lg hover:bg-gray-50 transition-colors"
                >
                  Cancelar
                </button>
                <button
                  onClick={handleSaveGateway}
                  disabled={gatewaySaving}
                  className="flex-1 px-4 py-2 bg-blue-600 hover:bg-blue-700 disabled:bg-blue-400 text-white rounded-lg font-medium transition-colors"
                >
                  {gatewaySaving ? 'Guardando...' : 'Guardar'}
                </button>
              </div>
            </div>
          </div>
        </div>
      )}

      {createGatewayOpen && (
        <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50" onClick={() => setCreateGatewayOpen(false)}>
          <div className="bg-white rounded-xl shadow-xl max-w-md w-full mx-4 p-6" onClick={(e) => e.stopPropagation()}>
            <div className="flex items-center justify-between mb-6">
              <h2 className="text-xl font-bold text-gray-900">Añadir Gateway</h2>
              <button onClick={() => setCreateGatewayOpen(false)} className="p-2 hover:bg-gray-100 rounded-lg">
                <X className="h-6 w-6" />
              </button>
            </div>
            <div className="space-y-4">
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">IP</label>
                <input
                  type="text"
                  value={newGateway.ip}
                  onChange={(e) => setNewGateway({ ...newGateway, ip: e.target.value })}
                  placeholder="192.168.1.100"
                  className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-blue-500"
                />
              </div>
              <div className="grid grid-cols-2 gap-4">
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-1">ID Inicio</label>
                  <input
                    type="number"
                    value={newGateway.id_start}
                    onChange={(e) => setNewGateway({ ...newGateway, id_start: parseInt(e.target.value) || 1 })}
                    className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-blue-500"
                  />
                </div>
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-1">ID Fin</label>
                  <input
                    type="number"
                    value={newGateway.id_end}
                    onChange={(e) => setNewGateway({ ...newGateway, id_end: parseInt(e.target.value) || 32 })}
                    className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-blue-500"
                  />
                </div>
              </div>
              <div className="flex space-x-3 pt-2">
                <button
                  onClick={() => setCreateGatewayOpen(false)}
                  className="flex-1 px-4 py-2 border border-gray-300 text-gray-700 rounded-lg hover:bg-gray-50 transition-colors"
                >
                  Cancelar
                </button>
                <button
                  onClick={handleCreateGateway}
                  disabled={gatewaySaving || !newGateway.ip}
                  className="flex-1 px-4 py-2 bg-blue-600 hover:bg-blue-700 disabled:bg-blue-400 text-white rounded-lg font-medium transition-colors"
                >
                  {gatewaySaving ? 'Creando...' : 'Crear Gateway'}
                </button>
              </div>
            </div>
          </div>
        </div>
      )}

      {deleteGatewayId && (
        <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50" onClick={() => setDeleteGatewayId(null)}>
          <div className="bg-white rounded-xl shadow-xl max-w-sm w-full mx-4 p-6" onClick={(e) => e.stopPropagation()}>
            <h2 className="text-lg font-bold text-gray-900 mb-4">Eliminar Gateway</h2>
            <p className="text-gray-600 mb-6">
              ¿Estás seguro de eliminar este gateway? Se eliminarán también todas sus tarjetas y alarmas asociadas.
            </p>
            <div className="flex space-x-3">
              <button
                onClick={() => setDeleteGatewayId(null)}
                className="flex-1 px-4 py-2 border border-gray-300 text-gray-700 rounded-lg hover:bg-gray-50 transition-colors"
              >
                Cancelar
              </button>
              <button
                onClick={handleDeleteGateway}
                className="flex-1 px-4 py-2 bg-red-600 hover:bg-red-700 text-white rounded-lg font-medium transition-colors"
              >
                Eliminar
              </button>
            </div>
          </div>
        </div>
      )}

      {showReportModal && (
        <div className="fixed inset-0 bg-black/50 z-50 flex items-center justify-center" onClick={() => setShowReportModal(false)}>
          <div className="bg-white rounded-2xl shadow-2xl w-full max-w-lg mx-4 p-6" onClick={(e) => e.stopPropagation()}>
            <div className="flex items-center justify-between mb-4">
              <h2 className="text-2xl font-bold text-gray-900">Generar Reporte</h2>
              <button onClick={() => setShowReportModal(false)} className="p-2 hover:bg-gray-100 rounded-lg">
                <X className="h-6 w-6" />
              </button>
            </div>

            <p className="text-gray-600 mb-5 text-sm">
              Se escanearán todos los gateways de <strong>{plant.name}</strong> en tiempo real
              y se generará un reporte con las opciones seleccionadas.
            </p>

            <div className="space-y-3 mb-6 p-4 bg-gray-50 rounded-xl">
              <h3 className="font-semibold text-gray-700 text-sm">Incluir en el reporte</h3>
              {[
                { key: 'incluir_alarmas', label: 'Alarmas (seccionador / sobretensión)' },
                { key: 'incluir_diag', label: 'Diagnóstico (LoRa, Memoria)' },
                { key: 'incluir_voltaje', label: 'Voltaje DC' },
                { key: 'incluir_strings', label: 'Corrientes de strings' },
              ].map(({ key, label }) => (
                <label key={key} className="flex items-center space-x-3 cursor-pointer group">
                  <input
                    type="checkbox"
                    checked={(reportOpts as any)[key]}
                    onChange={(e) => setReportOpts({ ...reportOpts, [key]: e.target.checked })}
                    className="w-4 h-4 text-blue-600 border-gray-300 rounded focus:ring-blue-500"
                  />
                  <span className="text-sm text-gray-700 group-hover:text-gray-900 select-none">{label}</span>
                </label>
              ))}
              {(reportOpts as any).incluir_strings && (
                <div className="flex items-center space-x-2 ml-7 mt-2">
                  <label className="text-xs text-gray-500">Umbral %:</label>
                  <input
                    type="number"
                    value={reportOpts.umbral_strings}
                    onChange={(e) => setReportOpts({ ...reportOpts, umbral_strings: Number(e.target.value) })}
                    className="w-20 px-2 py-1 border rounded text-sm text-center"
                    min={1}
                    max={100}
                  />
                </div>
              )}
            </div>

            {generatingReport && (
              <div className="mb-4 p-3 bg-blue-50 border border-blue-200 rounded-xl">
                <div className="flex items-center space-x-2 text-blue-700 text-sm mb-2">
                  <Loader className="h-4 w-4 animate-spin" />
                  <span>Escaneando y generando reporte...</span>
                </div>
                <div className="w-full bg-blue-100 rounded-full h-1.5">
                  <div className="bg-blue-600 h-1.5 rounded-full animate-pulse" style={{ width: '60%' }} />
                </div>
              </div>
            )}

            <div className="grid grid-cols-2 gap-3">
              <button
                onClick={() => handleGenerateReport('pdf')}
                disabled={generatingReport}
                className="flex items-center justify-center space-x-2 px-4 py-3 bg-purple-600 hover:bg-purple-700 disabled:bg-purple-400 text-white rounded-xl font-medium transition-all"
              >
                <FileText className="h-5 w-5" />
                <span>PDF</span>
              </button>
              <button
                onClick={() => handleGenerateReport('csv')}
                disabled={generatingReport}
                className="flex items-center justify-center space-x-2 px-4 py-3 bg-green-600 hover:bg-green-700 disabled:bg-green-400 text-white rounded-xl font-medium transition-all"
              >
                <Download className="h-5 w-5" />
                <span>CSV</span>
              </button>
            </div>
          </div>
        </div>
      )}

      {selectedCard && (
        <div className="fixed inset-0 bg-black/50 z-50 flex items-center justify-center" onClick={() => setSelectedCard(null)}>
          <div className="bg-white rounded-2xl shadow-2xl w-full max-w-md mx-4 p-6" onClick={e => e.stopPropagation()}>
            <div className="flex items-center justify-between mb-4">
              <h2 className="text-xl font-bold text-gray-900">Tarjeta #{selectedCard.modbus_id}</h2>
              <button onClick={() => setSelectedCard(null)} className="p-1.5 hover:bg-gray-100 rounded-lg">
                <X className="h-5 w-5" />
              </button>
            </div>
            <div className="space-y-4">
              <div className="grid grid-cols-2 gap-3">
                <div className="p-3 bg-gray-50 rounded-lg">
                  <p className="text-xs text-gray-500 mb-1">Estado</p>
                  <div className="flex items-center space-x-2">
                    {getCardStatusIcon(selectedCard)}
                    <span className="font-medium">{getCardStatusText(selectedCard)}</span>
                  </div>
                </div>
                <div className="p-3 bg-gray-50 rounded-lg">
                  <p className="text-xs text-gray-500 mb-1">Comunicación</p>
                  <span className={`font-medium ${selectedCard.communication_ok ? 'text-green-600' : 'text-red-600'}`}>
                    {selectedCard.communication_ok ? 'OK' : 'Falló'}
                  </span>
                </div>
                <div className="p-3 bg-gray-50 rounded-lg">
                  <p className="text-xs text-gray-500 mb-1">Voltaje</p>
                  <span className="font-medium text-gray-900">
                    {selectedCard.voltage ? `${selectedCard.voltage}V` : 'N/A'}
                  </span>
                </div>
                <div className="p-3 bg-gray-50 rounded-lg">
                  <p className="text-xs text-gray-500 mb-1">Tiempo Respuesta</p>
                  <span className="font-medium text-gray-900">
                    {selectedCard.response_time_ms ? `${selectedCard.response_time_ms.toFixed(0)}ms` : 'N/A'}
                  </span>
                </div>
                <div className="p-3 bg-gray-50 rounded-lg">
                  <p className="text-xs text-gray-500 mb-1">LoRa</p>
                  <span className={`font-medium ${selectedCard.lora_ok ? 'text-green-600' : 'text-red-600'}`}>
                    {selectedCard.lora_ok ? 'OK' : 'Falló'}
                  </span>
                </div>
                <div className="p-3 bg-gray-50 rounded-lg">
                  <p className="text-xs text-gray-500 mb-1">Errores consecutivos</p>
                  <span className="font-medium text-gray-900">{selectedCard.consecutive_errors}</span>
                </div>
              </div>

              <div className="border-t pt-4 space-y-2">
                <h3 className="font-semibold text-gray-700 mb-2">Alarmas</h3>
                <div className="grid grid-cols-2 gap-2">
                  <div className={`p-2 rounded-lg text-sm ${selectedCard.sec_alarm ? 'bg-yellow-50 text-yellow-800' : 'bg-gray-50 text-gray-400'}`}>
                    ⚠️ Seccionador: {selectedCard.sec_alarm ? 'Activa' : 'Inactiva'}
                  </div>
                  <div className={`p-2 rounded-lg text-sm ${selectedCard.overvoltage_alarm ? 'bg-yellow-50 text-yellow-800' : 'bg-gray-50 text-gray-400'}`}>
                    ⚡ Sobretensión: {selectedCard.overvoltage_alarm ? 'Activa' : 'Inactiva'}
                  </div>
                  <div className={`p-2 rounded-lg text-sm ${selectedCard.communication_alarm ? 'bg-red-50 text-red-800' : 'bg-gray-50 text-gray-400'}`}>
                    📡 Comms: {selectedCard.communication_alarm ? 'Activa' : 'Inactiva'}
                  </div>
                </div>
              </div>

              <div className="border-t pt-4">
                <div className="grid grid-cols-2 gap-3 text-sm">
                  <div>
                    <p className="text-xs text-gray-500">Mantenimiento</p>
                    <span className={`font-medium ${selectedCard.maintenance_mode ? 'text-yellow-600' : 'text-gray-600'}`}>
                      {selectedCard.maintenance_mode ? 'Activo' : 'Inactivo'}
                    </span>
                  </div>
                  <div>
                    <p className="text-xs text-gray-500">Deshabilitada</p>
                    <span className={`font-medium ${selectedCard.disabled ? 'text-red-600' : 'text-gray-600'}`}>
                      {selectedCard.disabled ? 'Sí' : 'No'}
                    </span>
                  </div>
                </div>
              </div>

              <div className="border-t pt-4 text-xs text-gray-400 space-y-1">
                <p>Último contacto: {selectedCard.last_contact ? new Date(selectedCard.last_contact).toLocaleString('es-ES') : 'Nunca'}</p>
                {selectedCard.last_error_message && (
                  <p className="text-red-500">Último error: {selectedCard.last_error_message}</p>
                )}
                <p>Creada: {new Date(selectedCard.created_at).toLocaleString('es-ES')}</p>
              </div>
            </div>
          </div>
        </div>
      )}
    </div>
  )
}
