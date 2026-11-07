import { useEffect, useState } from 'react'
import { Activity, CheckCircle2, Clock3, X, XCircle } from 'lucide-react'
import toast from 'react-hot-toast'
import { api } from '../../services/api'

export default function HistoryModal({ projectId, onClose }) {
  const [history, setHistory] = useState([])
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    api.historicoProjeto(projectId)
      .then(setHistory)
      .catch(error => toast.error(error.message || 'Não foi possível carregar o histórico.'))
      .finally(() => setLoading(false))
  }, [projectId])

  return (
    <div style={{ position: 'absolute', inset: 0, backgroundColor: 'rgba(0,0,0,0.65)', display: 'flex', justifyContent: 'center', alignItems: 'center', zIndex: 1100 }}>
      <div style={{ backgroundColor: '#1e293b', padding: '25px', borderRadius: '12px', width: 'min(680px, 92vw)', maxHeight: '80vh', border: '1px solid #334155', color: 'white' }}>
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '18px' }}>
          <h2 style={{ display: 'flex', alignItems: 'center', gap: '8px', fontSize: '20px' }}><Activity size={20} color="#3b82f6" /> Histórico de disponibilidade</h2>
          <button onClick={onClose} style={{ background: 'transparent', border: 0, color: '#94a3b8', cursor: 'pointer' }}><X size={20} /></button>
        </div>
        {loading ? <div style={{ color: '#94a3b8' }}>Carregando histórico...</div> : history.length === 0 ? <div style={{ color: '#94a3b8' }}>Ainda não há verificações registradas.</div> : (
          <div style={{ maxHeight: '55vh', overflow: 'auto' }}>
            <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: '13px' }}>
              <thead><tr style={{ color: '#94a3b8', textAlign: 'left' }}><th style={{ padding: '8px' }}>Equipamento</th><th style={{ padding: '8px' }}>Status</th><th style={{ padding: '8px' }}>Tempo</th><th style={{ padding: '8px' }}>Horário</th></tr></thead>
              <tbody>{history.map((item, index) => <tr key={`${item.equipamento_id}-${item.criado_em}-${index}`} style={{ borderTop: '1px solid #334155' }}>
                <td style={{ padding: '8px' }}>{item.equipamento_id}</td>
                <td style={{ padding: '8px', color: item.status === 'online' ? '#10b981' : '#ef4444', display: 'flex', alignItems: 'center', gap: '5px' }}>{item.status === 'online' ? <CheckCircle2 size={14} /> : <XCircle size={14} />} {item.status}</td>
                <td style={{ padding: '8px', color: '#94a3b8' }}>{item.tempo_ms == null ? '—' : `${item.tempo_ms} ms`}</td>
                <td style={{ padding: '8px', color: '#94a3b8' }}><span style={{ display: 'flex', alignItems: 'center', gap: '4px' }}><Clock3 size={13} /> {new Date(item.criado_em).toLocaleString()}</span></td>
              </tr>)}</tbody>
            </table>
          </div>
        )}
      </div>
    </div>
  )
}
