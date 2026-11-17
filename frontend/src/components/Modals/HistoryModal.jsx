import { useEffect, useState } from 'react'
import { Activity, CheckCircle2, Clock3, X, XCircle, BarChart3, List } from 'lucide-react'
import toast from 'react-hot-toast'
import { api } from '../../services/api'

const PERIODOS = [{ horas: 24, rotulo: '24 h' }, { horas: 24 * 7, rotulo: '7 dias' }, { horas: 24 * 30, rotulo: '30 dias' }]

const corUptime = (pct) => pct == null ? '#64748b' : pct >= 99 ? '#10b981' : pct >= 95 ? '#f59e0b' : '#ef4444'

const th = { padding: '8px', fontWeight: 'normal' }
const td = { padding: '8px' }

function Aba({ ativa, onClick, icon: Icon, children }) {
  return (
    <button onClick={onClick} style={{ display: 'flex', alignItems: 'center', gap: '6px', padding: '8px 14px', background: ativa ? '#334155' : 'transparent', color: ativa ? 'white' : '#94a3b8', border: '1px solid #334155', borderRadius: '6px', cursor: 'pointer', fontSize: '13px' }}>
      <Icon size={15} /> {children}
    </button>
  )
}

function Disponibilidade({ projectId }) {
  const [horas, setHoras] = useState(24)
  const [dados, setDados] = useState(null)

  useEffect(() => {
    setDados(null)
    api.disponibilidadeProjeto(projectId, horas)
      .then(r => setDados(r.equipamentos))
      .catch(error => { toast.error(error.message); setDados([]) })
  }, [projectId, horas])

  return (
    <>
      <div style={{ display: 'flex', gap: '6px', marginBottom: '12px' }}>
        {PERIODOS.map(p => (
          <button key={p.horas} onClick={() => setHoras(p.horas)} style={{ padding: '4px 10px', fontSize: '12px', borderRadius: '12px', border: '1px solid #334155', cursor: 'pointer', background: horas === p.horas ? '#3b82f6' : 'transparent', color: 'white' }}>{p.rotulo}</button>
        ))}
      </div>
      {dados === null ? <div style={{ color: '#94a3b8' }}>Calculando...</div> : dados.length === 0 ? <div style={{ color: '#94a3b8' }}>Nenhum equipamento monitorado neste mapa (salve o projeto para começar).</div> : (
        <div style={{ maxHeight: '50vh', overflow: 'auto' }}>
          <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: '13px' }}>
            <thead><tr style={{ color: '#94a3b8', textAlign: 'left' }}><th style={th}>Equipamento</th><th style={th}>Disponibilidade</th><th style={th}>Quedas</th><th style={th}>Latência média</th></tr></thead>
            <tbody>{[...dados].sort((a, b) => (a.uptime_pct ?? 101) - (b.uptime_pct ?? 101)).map(item => (
              <tr key={item.equipamento_id} style={{ borderTop: '1px solid #334155' }}>
                <td style={td}><div style={{ fontWeight: 'bold' }}>{item.nome}</div><div style={{ color: '#64748b', fontSize: '11px' }}>{item.ip}</div></td>
                <td style={{ ...td, minWidth: '170px' }}>
                  {item.uptime_pct == null ? <span style={{ color: '#64748b' }}>sem dados ainda</span> : (
                    <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                      <div style={{ flex: 1, height: '8px', background: '#0f172a', borderRadius: '4px', overflow: 'hidden' }}>
                        <div style={{ width: `${item.uptime_pct}%`, height: '100%', background: corUptime(item.uptime_pct) }} />
                      </div>
                      <span style={{ color: corUptime(item.uptime_pct), fontWeight: 'bold', minWidth: '58px', textAlign: 'right' }}>{item.uptime_pct.toFixed(2)}%</span>
                    </div>
                  )}
                </td>
                <td style={{ ...td, color: item.quedas ? '#ef4444' : '#94a3b8' }}>{item.quedas}</td>
                <td style={{ ...td, color: '#94a3b8' }}>{item.latencia_media_ms == null ? '—' : `${item.latencia_media_ms} ms`}</td>
              </tr>
            ))}</tbody>
          </table>
        </div>
      )}
    </>
  )
}

function Eventos({ projectId }) {
  const [history, setHistory] = useState([])
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    api.historicoProjeto(projectId, 200)
      .then(setHistory)
      .catch(error => toast.error(error.message || 'Não foi possível carregar o histórico.'))
      .finally(() => setLoading(false))
  }, [projectId])

  if (loading) return <div style={{ color: '#94a3b8' }}>Carregando histórico...</div>
  if (history.length === 0) return <div style={{ color: '#94a3b8' }}>Ainda não há verificações registradas.</div>
  return (
    <div style={{ maxHeight: '55vh', overflow: 'auto' }}>
      <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: '13px' }}>
        <thead><tr style={{ color: '#94a3b8', textAlign: 'left' }}><th style={th}>Equipamento</th><th style={th}>Status</th><th style={th}>Tempo</th><th style={th}>Horário</th></tr></thead>
        <tbody>{history.map((item, index) => <tr key={`${item.equipamento_id}-${item.criado_em}-${index}`} style={{ borderTop: '1px solid #334155' }}>
          <td style={td}>{item.equipamento_nome || item.equipamento_id}</td>
          <td style={{ ...td, color: item.status === 'online' ? '#10b981' : '#ef4444' }}><span style={{ display: 'flex', alignItems: 'center', gap: '5px' }}>{item.status === 'online' ? <CheckCircle2 size={14} /> : <XCircle size={14} />} {item.status}</span></td>
          <td style={{ ...td, color: '#94a3b8' }}>{item.tempo_ms == null ? '—' : `${item.tempo_ms} ms`}</td>
          <td style={{ ...td, color: '#94a3b8' }}><span style={{ display: 'flex', alignItems: 'center', gap: '4px' }}><Clock3 size={13} /> {new Date(item.criado_em).toLocaleString()}</span></td>
        </tr>)}</tbody>
      </table>
    </div>
  )
}

export default function HistoryModal({ projectId, onClose }) {
  const [aba, setAba] = useState('disponibilidade')

  return (
    <div style={{ position: 'absolute', inset: 0, backgroundColor: 'rgba(0,0,0,0.65)', display: 'flex', justifyContent: 'center', alignItems: 'center', zIndex: 1100 }}>
      <div style={{ backgroundColor: '#1e293b', padding: '25px', borderRadius: '12px', width: 'min(720px, 92vw)', maxHeight: '85vh', border: '1px solid #334155', color: 'white' }}>
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '16px' }}>
          <h2 style={{ display: 'flex', alignItems: 'center', gap: '8px', fontSize: '20px' }}><Activity size={20} color="#3b82f6" /> Histórico de disponibilidade</h2>
          <button onClick={onClose} style={{ background: 'transparent', border: 0, color: '#94a3b8', cursor: 'pointer' }}><X size={20} /></button>
        </div>
        <div style={{ display: 'flex', gap: '8px', marginBottom: '16px' }}>
          <Aba ativa={aba === 'disponibilidade'} onClick={() => setAba('disponibilidade')} icon={BarChart3}>Disponibilidade</Aba>
          <Aba ativa={aba === 'eventos'} onClick={() => setAba('eventos')} icon={List}>Eventos</Aba>
        </div>
        {projectId === 'novo'
          ? <div style={{ color: '#94a3b8' }}>Salve o projeto para começar a registrar o histórico.</div>
          : aba === 'disponibilidade' ? <Disponibilidade projectId={projectId} /> : <Eventos projectId={projectId} />}
      </div>
    </div>
  )
}
