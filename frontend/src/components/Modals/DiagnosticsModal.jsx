import { useEffect, useState } from 'react'
import { Activity, CheckCircle2, X, XCircle, Loader2 } from 'lucide-react'
import { api } from '../../services/api'

export default function DiagnosticsModal({ onClose }) {
  const [data, setData] = useState(null)
  const [error, setError] = useState('')
  const [loading, setLoading] = useState(true)

  const load = async () => {
    setLoading(true)
    setError('')
    try { setData(await api.health()) } catch (err) { setError(err.message) } finally { setLoading(false) }
  }

  useEffect(() => { load() }, [])
  const Status = ({ ok, children }) => <div style={{ display: 'flex', alignItems: 'center', gap: '8px', color: ok ? '#10b981' : '#ef4444' }}>{ok ? <CheckCircle2 size={17} /> : <XCircle size={17} />}{children}</div>

  return <div style={{ position: 'absolute', inset: 0, backgroundColor: 'rgba(0,0,0,0.6)', display: 'flex', justifyContent: 'center', alignItems: 'center', zIndex: 1100 }}>
    <div style={{ backgroundColor: '#1e293b', padding: '25px', borderRadius: '12px', width: '440px', border: '1px solid #334155' }}>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '20px' }}>
        <h2 style={{ display: 'flex', alignItems: 'center', gap: '8px', fontSize: '20px' }}><Activity size={20} color="#3b82f6" /> Diagnóstico do NetCable</h2>
        <button onClick={onClose} style={{ background: 'transparent', border: 'none', color: '#94a3b8', cursor: 'pointer' }}><X size={20} /></button>
      </div>
      {loading && <div style={{ color: '#94a3b8', display: 'flex', gap: '8px', alignItems: 'center' }}><Loader2 className="spin" size={18} /> Verificando instalação...</div>}
      {error && <div style={{ color: '#ef4444', background: '#351b25', padding: '12px', borderRadius: '6px' }}>{error}</div>}
      {data && <div style={{ display: 'grid', gap: '12px', fontSize: '14px' }}>
        <Status ok={data.api === 'online'}>API: {data.api}</Status>
        <Status ok={data.database?.connected}>Banco de dados: {data.database?.connected ? 'conectado' : data.database?.error}</Status>
        <Status ok={data.snmp?.installed}>PySNMP: {data.snmp?.status}{data.snmp?.detail ? ` — ${data.snmp.detail}` : ''}</Status>
        <div style={{ color: '#94a3b8', fontSize: '12px', wordBreak: 'break-all' }}>Banco: {data.database_path}</div>
      </div>}
      <button onClick={load} disabled={loading} style={{ marginTop: '22px', width: '100%', padding: '10px', background: '#334155', color: 'white', border: 0, borderRadius: '6px', cursor: loading ? 'wait' : 'pointer' }}>Verificar novamente</button>
    </div>
  </div>
}
