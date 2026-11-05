import { useState } from 'react'
import { X, Plus, Server, Wifi, Shield, Monitor, Activity, CheckCircle, XCircle, Network } from 'lucide-react'
import { api } from '../../services/api' // IMPORTANDO A API
import { useLang, typeLabel } from '../../i18n.jsx'

export default function AddEquipmentModal({ onClose, onAdd }) {
  const { t } = useLang()
  const [nome, setNome] = useState('')
  const [ip, setIp] = useState('')
  const [tipo, setTipo] = useState('router')
  const [semIp, setSemIp] = useState(false)
  const [monitorMode, setMonitorMode] = useState('ip')
  const [snmpConfig, setSnmpConfig] = useState({ username: '', authProtocol: 'SHA', authPassword: '', privProtocol: 'AES', privPassword: '', port: 161 })
  const [neighbors, setNeighbors] = useState(null)
  const [isDiscovering, setIsDiscovering] = useState(false)

  const [tipos, setTipos] = useState([
    { value: 'router', icon: Wifi },
    { value: 'managed-switch', icon: Server },
    { value: 'unmanaged-switch', icon: Server },
    { value: 'firewall', icon: Shield },
    { value: 'server', icon: Server },
    { value: 'pc', icon: Monitor },
  ])
  const [novoTipo, setNovoTipo] = useState('')
  const [mostrarNovoTipo, setMostrarNovoTipo] = useState(false)

  const [isTesting, setIsTesting] = useState(false)
  const [testResult, setTestResult] = useState(null)
  const [pingTime, setPingTime] = useState(null)
  const [testMessage, setTestMessage] = useState('')

  const handleTestConnection = async () => {
    if (semIp) return
    if (!ip) { setTestResult('error'); return }
    
    setIsTesting(true)
    setTestResult(null)
    setPingTime(null)
    setTestMessage('')

    try {
      const data = monitorMode === 'snmpv3' ? await api.monitor(null, ip, monitorMode, snmpConfig) : await api.ping(ip)
      if (data.status === 'online') {
        setTestResult('success')
        setPingTime(data.tempo_ms)
      } else {
        setTestResult('error')
        setTestMessage(data.error || t('addEquipment.noResponse'))
      }
    } catch (error) {
      setTestResult('error')
      setTestMessage(error.message || t('addEquipment.testFail'))
    } finally {
      setIsTesting(false)
    }
  }

  const handleDiscovery = async () => {
    if (!ip || !snmpConfig.username) return
    setIsDiscovering(true)
    try {
      const data = await api.discoverNeighbors(ip, snmpConfig)
      setNeighbors(data.neighbors || [])
    } catch (error) {
      setNeighbors([])
    } finally {
      setIsDiscovering(false)
    }
  }

  const handleAdd = async () => {
    if (!nome) { alert(t('addEquipment.fillName')); return }
    if (!semIp && !ip) { alert(t('addEquipment.fillIp')); return }

    let finalStatus = 'offline'
    let finalPingTime = null

    if (semIp) {
      finalStatus = 'visual'
    } else {
      if (testResult !== 'success') {
        try {
            const data = monitorMode === 'snmpv3' ? await api.monitor(null, ip, monitorMode, snmpConfig) : await api.ping(ip)
          if (data.status === 'online') {
            finalStatus = 'online'
            finalPingTime = data.tempo_ms
          } else {
            if (!window.confirm(t('addEquipment.ipNoResponse'))) return
          }
        } catch (error) {
          if (!window.confirm(t('addEquipment.backendError'))) return
        }
      } else {
        finalStatus = 'online'
        finalPingTime = pingTime
      }
    }
    
    onAdd({ nome, ip: semIp ? t('misc.noIpLabel') : ip, tipo, status: finalStatus, pingTime: finalPingTime, monitorMode: semIp ? 'visual' : monitorMode, snmpConfig: monitorMode === 'snmpv3' ? snmpConfig : null })
  }

  const handleAddTipo = () => {
    if (novoTipo.trim() !== '') {
      setTipos([...tipos, { value: novoTipo, icon: Server }])
      setTipo(novoTipo)
      setNovoTipo('')
      setMostrarNovoTipo(false)
    }
  }

  return (
    <div style={{ position: 'absolute', top: 0, left: 0, width: '100%', height: '100%', backgroundColor: 'rgba(0,0,0,0.6)', display: 'flex', justifyContent: 'center', alignItems: 'center', zIndex: 1000 }}>
      <div style={{ backgroundColor: '#1e293b', padding: '25px', borderRadius: '12px', width: '480px', border: '1px solid #334155' }}>
        
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '20px' }}>
          <h2 style={{ fontSize: '20px' }}>{t('addEquipment.title')}</h2>
          <button onClick={onClose} style={{ background: 'transparent', border: 'none', color: '#94a3b8', cursor: 'pointer' }}><X size={20} /></button>
        </div>

        <div style={{ display: 'flex', flexDirection: 'column', gap: '15px' }}>
          <div>
            <label style={{ fontSize: '14px', color: '#94a3b8' }}>{t('addEquipment.monitorMethod')}</label>
            <select value={semIp ? 'visual' : monitorMode} onChange={(e) => setMonitorMode(e.target.value)} disabled={semIp} style={{ width: '100%', padding: '10px', marginTop: '5px', borderRadius: '6px', border: '1px solid #334155', backgroundColor: '#0f172a', color: 'white' }}>
              <option value="ip">{t('addEquipment.ipOption')}</option>
              <option value="snmpv3">{t('addEquipment.snmpOption')}</option>
            </select>
          </div>

          {monitorMode === 'snmpv3' && !semIp && <div style={{ padding: '12px', backgroundColor: '#0f172a', borderRadius: '6px', border: '1px solid #334155', display: 'grid', gap: '10px' }}>
            <label style={{ fontSize: '13px', color: '#94a3b8' }}>{t('addEquipment.snmpCreds')}</label>
            <input value={snmpConfig.username} onChange={(e) => setSnmpConfig({ ...snmpConfig, username: e.target.value })} placeholder={t('addEquipment.user')} style={{ padding: '9px', borderRadius: '6px', border: '1px solid #334155', backgroundColor: '#1e293b', color: 'white' }} />
            <div style={{ display: 'flex', gap: '8px' }}><select value={snmpConfig.authProtocol} onChange={(e) => setSnmpConfig({ ...snmpConfig, authProtocol: e.target.value })} style={{ flex: 1, padding: '9px', backgroundColor: '#1e293b', color: 'white', border: '1px solid #334155', borderRadius: '6px' }}><option>SHA</option><option>MD5</option></select><input type="password" value={snmpConfig.authPassword} onChange={(e) => setSnmpConfig({ ...snmpConfig, authPassword: e.target.value })} placeholder={t('addEquipment.authPass')} style={{ flex: 2, padding: '9px', borderRadius: '6px', border: '1px solid #334155', backgroundColor: '#1e293b', color: 'white' }} /></div>
            <div style={{ display: 'flex', gap: '8px' }}><select value={snmpConfig.privProtocol} onChange={(e) => setSnmpConfig({ ...snmpConfig, privProtocol: e.target.value })} style={{ flex: 1, padding: '9px', backgroundColor: '#1e293b', color: 'white', border: '1px solid #334155', borderRadius: '6px' }}><option>AES</option><option>DES</option><option>3DES</option></select><input type="password" value={snmpConfig.privPassword} onChange={(e) => setSnmpConfig({ ...snmpConfig, privPassword: e.target.value })} placeholder={t('addEquipment.privPass')} style={{ flex: 2, padding: '9px', borderRadius: '6px', border: '1px solid #334155', backgroundColor: '#1e293b', color: 'white' }} /></div>
            <input type="number" min="1" max="65535" value={snmpConfig.port} onChange={(e) => setSnmpConfig({ ...snmpConfig, port: Number(e.target.value) })} placeholder={t('addEquipment.snmpPort')} style={{ padding: '9px', borderRadius: '6px', border: '1px solid #334155', backgroundColor: '#1e293b', color: 'white' }} />
            <button onClick={handleDiscovery} disabled={isDiscovering || !ip || !snmpConfig.username} style={{ padding: '9px', backgroundColor: '#334155', color: 'white', border: 'none', borderRadius: '6px', cursor: isDiscovering ? 'wait' : 'pointer' }}>{isDiscovering ? t('addEquipment.discovering') : t('addEquipment.discover')}</button>
            {neighbors && <div style={{ fontSize: '12px', color: neighbors.length ? '#10b981' : '#f59e0b' }}>{neighbors.length ? t('addEquipment.neighborsFound', { n: neighbors.length, list: neighbors.map(item => item.name || item.port || t('addEquipment.unnamed')).join(', ') }) : t('addEquipment.noNeighbors')}</div>}
          </div>}

          <div>
            <label style={{ fontSize: '14px', color: '#94a3b8' }}>{t('addEquipment.name')}</label>
            <input type="text" value={nome} onChange={(e) => setNome(e.target.value)} placeholder={t('addEquipment.namePh')} style={{ width: '100%', padding: '10px', marginTop: '5px', borderRadius: '6px', border: '1px solid #334155', backgroundColor: '#0f172a', color: 'white' }} />
          </div>
          
          <div style={{ display: 'flex', alignItems: 'center', gap: '10px', marginTop: '5px' }}>
            <input type="checkbox" id="semIp" checked={semIp} onChange={(e) => setSemIp(e.target.checked)} style={{ width: '16px', height: '16px', cursor: 'pointer' }} />
            <label htmlFor="semIp" style={{ fontSize: '14px', color: '#94a3b8', cursor: 'pointer', display: 'flex', alignItems: 'center', gap: '5px' }}>
              <Network size={16} /> {t('addEquipment.noIp')}
            </label>
          </div>

          <div style={{ opacity: semIp ? 0.5 : 1, pointerEvents: semIp ? 'none' : 'auto' }}>
            <label style={{ fontSize: '14px', color: '#94a3b8' }}>{t('addEquipment.ipAddress')}</label>
            <div style={{ display: 'flex', gap: '10px', marginTop: '5px' }}>
              <input type="text" value={ip} onChange={(e) => setIp(e.target.value)} placeholder={semIp ? t('addEquipment.ipDisabled') : t('addEquipment.ipPh')} disabled={semIp} style={{ flex: 1, padding: '10px', borderRadius: '6px', border: '1px solid #334155', backgroundColor: '#0f172a', color: 'white' }} />
              <button onClick={handleTestConnection} disabled={isTesting || semIp} style={{ display: 'flex', alignItems: 'center', gap: '5px', padding: '0 15px', backgroundColor: isTesting ? '#475569' : '#334155', color: 'white', border: 'none', borderRadius: '6px', cursor: isTesting ? 'wait' : 'pointer' }}>
                {isTesting ? <Activity size={18} className="spin" /> : <Wifi size={18} />} {t('addEquipment.test')}
              </button>
            </div>
            {testResult === 'success' && (
              <div style={{ display: 'flex', alignItems: 'center', gap: '5px', color: '#10b981', fontSize: '13px', marginTop: '8px' }}>
                <CheckCircle size={16} /> {t('addEquipment.onlineIn', { ms: pingTime })}
              </div>
            )}
            {testResult === 'error' && (
              <div style={{ display: 'flex', alignItems: 'center', gap: '5px', color: '#ef4444', fontSize: '13px', marginTop: '8px' }}>
                <XCircle size={16} /> {testMessage || t('addEquipment.connFail')}
              </div>
            )}
          </div>

          <div>
            <label style={{ fontSize: '14px', color: '#94a3b8' }}>{t('equipment.type')}</label>
            <div style={{ display: 'flex', gap: '10px', marginTop: '5px' }}>
              <select value={tipo} onChange={(e) => setTipo(e.target.value)} style={{ flex: 1, padding: '10px', borderRadius: '6px', border: '1px solid #334155', backgroundColor: '#0f172a', color: 'white' }}>
                {tipos.map((item) => <option key={item.value} value={item.value}>{typeLabel(t, item.value)}</option>)}
              </select>
              <button onClick={() => setMostrarNovoTipo(!mostrarNovoTipo)} style={{ padding: '10px', backgroundColor: '#334155', color: 'white', border: 'none', borderRadius: '6px', cursor: 'pointer' }} title={t('addEquipment.newTypeTitle')}><Plus size={18} /></button>
            </div>
          </div>

          {mostrarNovoTipo && (
            <div style={{ display: 'flex', gap: '10px', marginTop: '5px' }}>
              <input type="text" value={novoTipo} onChange={(e) => setNovoTipo(e.target.value)} placeholder={t('addEquipment.newTypePh')} style={{ flex: 1, padding: '10px', borderRadius: '6px', border: '1px solid #3b82f6', backgroundColor: '#0f172a', color: 'white' }} />
              <button onClick={handleAddTipo} style={{ padding: '10px', backgroundColor: '#3b82f6', color: 'white', border: 'none', borderRadius: '6px', cursor: 'pointer' }}>{t('addEquipment.addType')}</button>
            </div>
          )}
        </div>

        <div style={{ display: 'flex', justifyContent: 'flex-end', marginTop: '30px', gap: '10px' }}>
          <button onClick={onClose} style={{ padding: '10px 20px', backgroundColor: 'transparent', color: '#94a3b8', border: '1px solid #334155', borderRadius: '6px', cursor: 'pointer' }}>{t('addEquipment.cancel')}</button>
          <button onClick={handleAdd} style={{ display: 'flex', alignItems: 'center', gap: '5px', padding: '10px 20px', backgroundColor: '#3b82f6', color: 'white', border: 'none', borderRadius: '6px', cursor: 'pointer' }}><Plus size={18} /> {t('addEquipment.add')}</button>
        </div>

      </div>
    </div>
  )
}
