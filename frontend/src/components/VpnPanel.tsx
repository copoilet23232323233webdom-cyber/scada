import { useEffect, useRef, useState } from 'react'
import { vpnAPI } from '../services/api'
import { ShieldCheck, ShieldAlert, ShieldOff, RefreshCw, Plug, PlugZap, Loader, ChevronDown } from 'lucide-react'

interface VpnDiagnostics {
  platform: string
  connected: boolean
  plant: string | null
  method: string | null
  uptime_seconds: number
  auto_reconnect: boolean
  reconnect_count: number
  health_targets: string[]
  last_health_check: number | null
  last_health_ok: boolean | null
  last_error: string | null
  demo_mode: boolean
  available_methods: string[]
  clients: Record<string, string | boolean | null>
}

interface Props {
  plantName?: string
  canOperate?: boolean
  /** Conecta la VPN de la planta al entrar y la mantiene mientras se navega por ella. */
  autoConnect?: boolean
  onChange?: (diag: VpnDiagnostics) => void
}

const METHOD_LABELS: Record<string, string> = {
  openvpn: 'OpenVPN',
  openfortivpn: 'FortiClient SSL (openfortivpn)',
  forticlient_cli: 'FortiClient CLI',
  openconnect: 'OpenConnect',
  windows_vpn: 'VPN nativa de Windows',
  ssh: 'Túnel SSH',
  demo: 'DEMO'
}

function formatUptime(seconds: number): string {
  if (!seconds) return '—'
  const h = Math.floor(seconds / 3600)
  const m = Math.floor((seconds % 3600) / 60)
  const s = seconds % 60
  return h > 0 ? `${h}h ${m}m` : m > 0 ? `${m}m ${s}s` : `${s}s`
}

/**
 * Barra de estado de la VPN: conectar / reconectar / desconectar, salud del
 * túnel y diagnóstico de los clientes VPN detectados en el servidor.
 */
export default function VpnPanel({ plantName, canOperate = false, autoConnect = false, onChange }: Props) {
  const [diag, setDiag] = useState<VpnDiagnostics | null>(null)
  const [busy, setBusy] = useState<string | null>(null)
  const [expanded, setExpanded] = useState(false)
  const [message, setMessage] = useState<string | null>(null)
  const autoTried = useRef<string | null>(null)

  const refresh = async (): Promise<VpnDiagnostics | null> => {
    try {
      const res = await vpnAPI.getDiagnostics()
      setDiag(res.data)
      onChange?.(res.data)
      return res.data
    } catch {
      /* la barra es informativa: un fallo puntual no debe romper la página */
      return null
    }
  }

  useEffect(() => {
    refresh()
    const timer = setInterval(refresh, 15000)
    return () => clearInterval(timer)
  }, [])

  const act = async (action: 'connect' | 'reconnect' | 'disconnect' | 'health') => {
    setBusy(action)
    setMessage(null)
    try {
      if (action === 'health') {
        const res = await vpnAPI.healthCheck()
        setMessage(res.data.healthy ? 'Túnel operativo: los gateways responden' : 'El túnel no alcanza los gateways')
      } else if (action === 'disconnect') {
        await vpnAPI.disconnect()
      } else if (plantName) {
        const res = action === 'connect'
          ? await vpnAPI.connect(plantName)
          : await vpnAPI.reconnect(plantName)
        setMessage(res.data.success
          ? `VPN conectada via ${METHOD_LABELS[res.data.method] || res.data.method}`
          : res.data.error || 'No se pudo conectar la VPN')
      }
    } catch (e: any) {
      setMessage(e?.response?.data?.detail || 'Error operando la VPN')
    } finally {
      setBusy(null)
      refresh()
    }
  }

  // Al entrar en una planta la VPN se levanta sola y se mantiene: el usuario
  // no debería tener que pulsar "Conectar" para leer sus gateways.
  useEffect(() => {
    if (!autoConnect || !canOperate || !plantName || autoTried.current === plantName) return
    autoTried.current = plantName
    void (async () => {
      const current = await refresh()
      if (current?.connected && current.plant === plantName) return
      await act('connect')
    })()
  }, [autoConnect, canOperate, plantName])

  const healthy = diag?.connected && diag?.last_health_ok !== false
  const Icon = !diag?.connected ? ShieldOff : healthy ? ShieldCheck : ShieldAlert
  const tone = !diag?.connected
    ? 'bg-gray-100 text-gray-600 border-gray-200'
    : healthy
      ? 'bg-emerald-50 text-emerald-700 border-emerald-200'
      : 'bg-amber-50 text-amber-700 border-amber-200'

  return (
    <div className={`rounded-xl border ${tone.split(' ')[2]} bg-white shadow-sm`}>
      <div className="flex items-center gap-3 flex-wrap px-4 py-3">
        <span className={`flex items-center gap-2 px-3 py-1.5 rounded-lg border text-sm font-medium ${tone}`}>
          {busy === 'connect' || busy === 'reconnect'
            ? <Loader className="w-4 h-4 animate-spin" />
            : <Icon className="w-4 h-4" />}
          {busy === 'connect' || busy === 'reconnect'
            ? `Conectando VPN${plantName ? ` de ${plantName}` : ''}...`
            : !diag?.connected
              ? 'VPN desconectada'
              : `VPN ${diag.plant || ''} · ${METHOD_LABELS[diag.method || ''] || diag.method}`}
        </span>

        {diag?.connected && (
          <span className="text-xs text-gray-500">
            uptime {formatUptime(diag.uptime_seconds)}
            {diag.reconnect_count > 0 && ` · ${diag.reconnect_count} reconexiones automáticas`}
          </span>
        )}
        {diag?.auto_reconnect && (
          <span className="text-xs px-2 py-0.5 rounded-full bg-blue-50 text-blue-600 border border-blue-100">
            watchdog activo
          </span>
        )}
        {diag?.demo_mode && (
          <span className="text-xs px-2 py-0.5 rounded-full bg-purple-50 text-purple-600 border border-purple-100">
            DEMO
          </span>
        )}

        <div className="ml-auto flex items-center gap-2">
          <button
            onClick={() => act('health')}
            disabled={busy !== null}
            className="flex items-center gap-1.5 px-3 py-1.5 text-xs border rounded-lg hover:bg-gray-50 disabled:opacity-50"
          >
            {busy === 'health' ? <Loader className="w-3.5 h-3.5 animate-spin" /> : <RefreshCw className="w-3.5 h-3.5" />}
            Comprobar túnel
          </button>
          {canOperate && plantName && (
            <>
              <button
                onClick={() => act(diag?.connected ? 'reconnect' : 'connect')}
                disabled={busy !== null}
                className="flex items-center gap-1.5 px-3 py-1.5 text-xs bg-blue-600 text-white rounded-lg hover:bg-blue-700 disabled:opacity-50"
              >
                {busy === 'connect' || busy === 'reconnect'
                  ? <Loader className="w-3.5 h-3.5 animate-spin" />
                  : <PlugZap className="w-3.5 h-3.5" />}
                {diag?.connected ? 'Reconectar' : 'Conectar'}
              </button>
              {diag?.connected && (
                <button
                  onClick={() => act('disconnect')}
                  disabled={busy !== null}
                  className="flex items-center gap-1.5 px-3 py-1.5 text-xs border rounded-lg text-red-600 hover:bg-red-50 disabled:opacity-50"
                >
                  <Plug className="w-3.5 h-3.5" /> Desconectar
                </button>
              )}
            </>
          )}
          <button
            onClick={() => setExpanded(v => !v)}
            className="p-1.5 rounded-lg hover:bg-gray-100"
            title="Diagnóstico VPN"
          >
            <ChevronDown className={`w-4 h-4 text-gray-500 transition ${expanded ? 'rotate-180' : ''}`} />
          </button>
        </div>
      </div>

      {(message || diag?.last_error) && (
        <div className="px-4 pb-3 text-xs text-gray-600">
          {message || `Último error: ${diag?.last_error}`}
        </div>
      )}

      {expanded && diag && (
        <div className="border-t px-4 py-3 grid grid-cols-1 md:grid-cols-3 gap-4 text-xs">
          <div>
            <div className="text-gray-400 uppercase tracking-wide mb-1">Servidor</div>
            <div className="text-gray-700">Plataforma: {diag.platform}</div>
            <div className="text-gray-700">
              Métodos: {diag.available_methods.map(m => METHOD_LABELS[m] || m).join(', ') || '—'}
            </div>
          </div>
          <div>
            <div className="text-gray-400 uppercase tracking-wide mb-1">Clientes detectados</div>
            {Object.entries(diag.clients).map(([name, path]) => (
              <div key={name} className={path ? 'text-emerald-700' : 'text-gray-400'}>
                {METHOD_LABELS[name] || name}: {path ? (typeof path === 'string' ? path : 'disponible') : 'no instalado'}
              </div>
            ))}
          </div>
          <div>
            <div className="text-gray-400 uppercase tracking-wide mb-1">Salud del túnel</div>
            <div className="text-gray-700">
              Gateways sondeados: {diag.health_targets.length ? diag.health_targets.join(', ') : '—'}
            </div>
            <div className="text-gray-700">
              Última comprobación: {diag.last_health_check
                ? new Date(diag.last_health_check * 1000).toLocaleTimeString()
                : '—'} ({diag.last_health_ok === null ? 'sin datos' : diag.last_health_ok ? 'ok' : 'fallo'})
            </div>
          </div>
        </div>
      )}
    </div>
  )
}
