import { useEffect, useState } from 'react'
import { AlertTriangle, CheckCircle, ChevronDown, ChevronRight, Loader, Save, Shield, Zap } from 'lucide-react'
import { plantsAPI } from '../services/api'

interface Props {
  plantId: number
}

const MASK = '********'

type Form = {
  type: string
  config_path: string
  username: string
  password: string
  key_password: string
  subtype: string
  vpn_name: string
  host: string
  port: number
  realm: string
  trusted_cert: string
  allow_insecure: boolean
  psk: string
  local_id: string
  remote_id: string
  ike_version: string
  ssh_host: string
  ssh_port: number
  ssh_username: string
  ssh_password: string
  ssh_key_path: string
}

const EMPTY: Form = {
  type: 'openvpn',
  config_path: '', username: '', password: '', key_password: '',
  subtype: 'ssl', vpn_name: '', host: '', port: 10443,
  realm: '', trusted_cert: '', allow_insecure: true,
  psk: '', local_id: '', remote_id: '', ike_version: 'v2',
  ssh_host: '', ssh_port: 22, ssh_username: '', ssh_password: '', ssh_key_path: ''
}

const input = 'w-full px-2 py-1.5 border rounded text-sm'
const label = 'block text-xs font-medium text-gray-600 mb-1'

export default function PlantVpnSettings({ plantId }: Props) {
  const [form, setForm] = useState<Form>(EMPTY)
  const [ovpnFiles, setOvpnFiles] = useState<string[]>([])
  const [upload, setUpload] = useState<{ name: string; data: string } | null>(null)
  const [configured, setConfigured] = useState(false)
  const [loading, setLoading] = useState(true)
  const [busy, setBusy] = useState(false)
  const [msg, setMsg] = useState<{ kind: 'ok' | 'err'; text: string } | null>(null)
  // Oculto por defecto: la configuración VPN no debe quedar a la vista.
  const [open, setOpen] = useState(() => localStorage.getItem('vpnPanelOpen') === '1')

  const toggle = () => {
    setOpen(prev => {
      localStorage.setItem('vpnPanelOpen', prev ? '0' : '1')
      return !prev
    })
  }

  const set = (patch: Partial<Form>) => setForm(prev => ({ ...prev, ...patch }))

  const load = async () => {
    setLoading(true)
    try {
      const { data } = await plantsAPI.getVpn(plantId)
      const cfg = data.config || {}
      setConfigured(!!data.configured)
      setOvpnFiles(data.ovpn_files || [])
      setForm({
        ...EMPTY,
        type: (cfg.VPN_TYPE || 'openvpn').toLowerCase(),
        config_path: cfg.CONFIG || '',
        username: cfg.USER || '',
        password: cfg.PASSWORD || '',
        key_password: cfg.KEY_PASSWORD || '',
        subtype: (cfg.SUBTYPE || 'ssl').toLowerCase(),
        vpn_name: cfg.VPN_NAME || '',
        host: cfg.HOST || '',
        port: Number(cfg.PORT || 10443),
        realm: cfg.REALM || '',
        trusted_cert: cfg.TRUSTED_CERT || '',
        allow_insecure: (cfg.ALLOW_INSECURE || 'true') !== 'false',
        psk: cfg.PSK || '',
        local_id: cfg.LOCAL_ID || '',
        remote_id: cfg.REMOTE_ID || '',
        ike_version: cfg.IKE_VERSION || 'v2',
        ssh_host: cfg.SSH_HOST || '',
        ssh_port: Number(cfg.SSH_PORT || 22),
        ssh_username: cfg.SSH_USER || '',
        ssh_password: cfg.SSH_PASSWORD || '',
        ssh_key_path: cfg.SSH_KEY_PATH || ''
      })
    } catch {
      setMsg({ kind: 'err', text: 'No se pudo leer la configuración VPN de la planta' })
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => { if (open) load() }, [plantId, open])

  const pickFile = async (file: File) => {
    const text = await file.text()
    setUpload({ name: file.name, data: btoa(unescape(encodeURIComponent(text))) })
  }

  const save = async () => {
    setBusy(true); setMsg(null)
    try {
      const body: any = { ...form }
      if (upload) {
        body.config_filename = upload.name
        body.config_file = upload.data
      }
      await plantsAPI.saveVpn(plantId, body)
      setUpload(null)
      setMsg({ kind: 'ok', text: 'Configuración VPN guardada' })
      load()
    } catch (e: any) {
      setMsg({ kind: 'err', text: e?.response?.data?.detail || 'No se pudo guardar' })
    } finally {
      setBusy(false)
    }
  }

  const test = async () => {
    setBusy(true); setMsg(null)
    try {
      const { data } = await plantsAPI.testVpn(plantId)
      setMsg(data.success
        ? { kind: 'ok', text: `Conectada por ${data.method}. Gateways alcanzables.` }
        : { kind: 'err', text: data.error || 'No se pudo conectar la VPN' })
    } catch (e: any) {
      setMsg({ kind: 'err', text: e?.response?.data?.detail || 'No se pudo probar la VPN' })
    } finally {
      setBusy(false)
    }
  }

  return (
    <div className="bg-white rounded-lg shadow p-4 space-y-3">
      <div className="flex items-center justify-between">
        <button onClick={toggle} className="flex items-center font-semibold text-gray-900 hover:text-blue-700">
          {open ? <ChevronDown className="h-4 w-4 mr-1" /> : <ChevronRight className="h-4 w-4 mr-1" />}
          <Shield className="h-4 w-4 mr-2 text-blue-600" /> Configuración VPN de la planta
        </button>
        <div className="flex items-center gap-2">
          {open && (
            <span className={`text-xs px-2 py-0.5 rounded-full ${configured ? 'bg-green-100 text-green-700' : 'bg-yellow-100 text-yellow-700'}`}>
              {configured ? 'vpn.txt configurado' : 'sin vpn.txt'}
            </span>
          )}
          <button onClick={toggle} className="text-xs text-blue-600 hover:underline">
            {open ? 'Ocultar' : 'Mostrar'}
          </button>
        </div>
      </div>

      {!open && (
        <p className="text-xs text-gray-500">Configuración oculta. Pulsa "Mostrar" para editarla.</p>
      )}

      {open && loading && (
        <div className="flex items-center text-gray-500 text-sm">
          <Loader className="h-4 w-4 animate-spin mr-2" /> Cargando configuración VPN...
        </div>
      )}

      {open && !loading && (
      <>
      <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
        <div>
          <label className={label}>Tipo de VPN</label>
          <select value={form.type} onChange={e => set({ type: e.target.value })} className={input}>
            <option value="openvpn">OpenVPN</option>
            <option value="forticlient">FortiClient</option>
            <option value="ssh">Túnel SSH</option>
          </select>
        </div>

        {form.type === 'openvpn' && (
          <>
            <div>
              <label className={label}>Archivo .ovpn</label>
              <input type="text" value={form.config_path} onChange={e => set({ config_path: e.target.value })}
                className={input} placeholder="mtech.ovpn" list="ovpn-files" />
              <datalist id="ovpn-files">
                {ovpnFiles.map(f => <option key={f} value={f} />)}
              </datalist>
            </div>
            <div>
              <label className={label}>Subir .ovpn</label>
              <input type="file" accept=".ovpn,.conf" className="w-full text-sm"
                onChange={e => { const f = e.target.files?.[0]; if (f) pickFile(f) }} />
              {upload && <p className="mt-1 text-xs text-gray-500">Se guardará {upload.name}</p>}
            </div>
            <div>
              <label className={label}>Usuario</label>
              <input type="text" value={form.username} onChange={e => set({ username: e.target.value })} className={input} />
            </div>
            <div>
              <label className={label}>Contraseña</label>
              <input type="password" value={form.password} onChange={e => set({ password: e.target.value })}
                className={input} placeholder={form.password === MASK ? 'Sin cambios' : ''} />
            </div>
            <div>
              <label className={label}>Contraseña de la clave privada</label>
              <input type="password" value={form.key_password} onChange={e => set({ key_password: e.target.value })} className={input} />
            </div>
          </>
        )}

        {form.type === 'forticlient' && (
          <>
            <div>
              <label className={label}>Modo</label>
              <select value={form.subtype} onChange={e => set({ subtype: e.target.value })} className={input}>
                <option value="ssl">SSL VPN</option>
                <option value="ipsec">IPsec</option>
              </select>
            </div>
            <div>
              <label className={label}>Host</label>
              <input type="text" value={form.host} onChange={e => set({ host: e.target.value })} className={input} placeholder="vpn.empresa.com" />
            </div>
            <div>
              <label className={label}>Puerto</label>
              <input type="number" value={form.port} onChange={e => set({ port: Number(e.target.value) })} className={input} />
            </div>
            <div>
              <label className={label}>Usuario</label>
              <input type="text" value={form.username} onChange={e => set({ username: e.target.value })} className={input} />
            </div>
            <div>
              <label className={label}>Contraseña</label>
              <input type="password" value={form.password} onChange={e => set({ password: e.target.value })} className={input} />
            </div>
            {form.subtype === 'ssl' ? (
              <>
                <div>
                  <label className={label}>Realm</label>
                  <input type="text" value={form.realm} onChange={e => set({ realm: e.target.value })} className={input} />
                </div>
                <div>
                  <label className={label}>Certificado de confianza</label>
                  <input type="text" value={form.trusted_cert} onChange={e => set({ trusted_cert: e.target.value })} className={input} />
                </div>
                <label className="flex items-center text-sm text-gray-700">
                  <input type="checkbox" checked={form.allow_insecure} className="mr-2"
                    onChange={e => set({ allow_insecure: e.target.checked })} />
                  Aceptar certificado no verificado
                </label>
              </>
            ) : (
              <>
                <div>
                  <label className={label}>PSK</label>
                  <input type="password" value={form.psk} onChange={e => set({ psk: e.target.value })} className={input} />
                </div>
                <div>
                  <label className={label}>Nombre de la conexión (Windows)</label>
                  <input type="text" value={form.vpn_name} onChange={e => set({ vpn_name: e.target.value })} className={input} />
                </div>
                <div>
                  <label className={label}>Versión IKE</label>
                  <select value={form.ike_version} onChange={e => set({ ike_version: e.target.value })} className={input}>
                    <option value="v1">IKEv1</option>
                    <option value="v2">IKEv2</option>
                  </select>
                </div>
              </>
            )}
          </>
        )}

        {form.type === 'ssh' && (
          <>
            <div>
              <label className={label}>Host</label>
              <input type="text" value={form.ssh_host} onChange={e => set({ ssh_host: e.target.value })} className={input} />
            </div>
            <div>
              <label className={label}>Puerto</label>
              <input type="number" value={form.ssh_port} onChange={e => set({ ssh_port: Number(e.target.value) })} className={input} />
            </div>
            <div>
              <label className={label}>Usuario</label>
              <input type="text" value={form.ssh_username} onChange={e => set({ ssh_username: e.target.value })} className={input} />
            </div>
            <div>
              <label className={label}>Contraseña</label>
              <input type="password" value={form.ssh_password} onChange={e => set({ ssh_password: e.target.value })} className={input} />
            </div>
            <div>
              <label className={label}>Ruta de la clave</label>
              <input type="text" value={form.ssh_key_path} onChange={e => set({ ssh_key_path: e.target.value })} className={input} />
            </div>
          </>
        )}
      </div>

      {msg && (
        <div className={`flex items-start text-sm rounded p-2 ${msg.kind === 'ok' ? 'bg-green-50 text-green-700' : 'bg-red-50 text-red-700'}`}>
          {msg.kind === 'ok'
            ? <CheckCircle className="h-4 w-4 mr-2 mt-0.5 shrink-0" />
            : <AlertTriangle className="h-4 w-4 mr-2 mt-0.5 shrink-0" />}
          <span>{msg.text}</span>
        </div>
      )}

      <div className="flex items-center gap-2">
        <button onClick={save} disabled={busy}
          className="flex items-center px-3 py-1.5 bg-blue-600 text-white rounded text-sm hover:bg-blue-700 disabled:opacity-50">
          <Save className="h-4 w-4 mr-1" /> Guardar
        </button>
        <button onClick={test} disabled={busy || !configured}
          className="flex items-center px-3 py-1.5 border rounded text-sm hover:bg-gray-50 disabled:opacity-50">
          <Zap className="h-4 w-4 mr-1" /> Probar conexión
        </button>
        <span className="text-xs text-gray-500">
          Las contraseñas guardadas se muestran como {MASK}; déjalas así para no cambiarlas.
        </span>
      </div>
      </>
      )}
    </div>
  )
}
