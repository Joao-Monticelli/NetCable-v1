import { useEffect, useState } from 'react'
import { Activity, CheckCircle2, Clock3, X, XCircle, BarChart3, List, LineChart, Table2, Download } from 'lucide-react'
import toast from 'react-hot-toast'
import { api } from '../../services/api'
import LatencyChart from '../LatencyChart'
import { t, useI18n, localeAtual } from '../../i18n'

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

const DIAS_SLA = [7, 30, 90]

function ExportarSla({ projectId }) {
  const [dias, setDias] = useState(30)
  const [baixando, setBaixando] = useState(false)
  const baixar = async () => {
    setBaixando(true)
    try { await api.baixarSlaCsv(projectId, dias) } catch (e) { toast.error(e.message) } finally { setBaixando(false) }
  }
  return (
    <div style={{ marginLeft: 'auto', display: 'flex', alignItems: 'center', gap: '6px' }} title={t('Relatório de SLA: disponibilidade, tempo fora do ar e quedas de cada equipamento, para abrir no Excel.')}>
      <select aria-label={t('Período do relatório de SLA')} value={dias} onChange={e => setDias(Number(e.target.value))} style={{ padding: '4px 6px', fontSize: '12px', borderRadius: '6px', border: '1px solid #334155', background: '#0f172a', color: 'white' }}>
        {DIAS_SLA.map(d => <option key={d} value={d}>{t('{n} dias', { n: d })}</option>)}
      </select>
      <button onClick={baixar} disabled={baixando} style={{ display: 'flex', alignItems: 'center', gap: '5px', padding: '4px 10px', fontSize: '12px', borderRadius: '6px', border: '1px solid #334155', background: '#0f172a', color: '#cbd5e1', cursor: 'pointer' }}>
        <Download size={13} /> {t('Exportar SLA (CSV)')}
      </button>
    </div>
  )
}

function Disponibilidade({ projectId, onVerLatencia }) {
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
      <div style={{ display: 'flex', gap: '6px', marginBottom: '12px', flexWrap: 'wrap', alignItems: 'center' }}>
        {PERIODOS.map(p => (
          <button key={p.horas} onClick={() => setHoras(p.horas)} style={{ padding: '4px 10px', fontSize: '12px', borderRadius: '12px', border: '1px solid #334155', cursor: 'pointer', background: horas === p.horas ? '#3b82f6' : 'transparent', color: 'white' }}>{t(p.rotulo)}</button>
        ))}
        <ExportarSla projectId={projectId} />
      </div>
      {dados === null ? <div style={{ color: '#94a3b8' }}>{t('Calculando...')}</div> : dados.length === 0 ? <div style={{ color: '#94a3b8' }}>{t('Nenhum equipamento monitorado neste mapa (salve o projeto para começar).')}</div> : (
        <div style={{ maxHeight: '50vh', overflow: 'auto' }}>
          <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: '13px' }}>
            <thead><tr style={{ color: '#94a3b8', textAlign: 'left' }}><th style={th}>{t('Equipamento')}</th><th style={th}>{t('Disponibilidade')}</th><th style={th}>{t('Quedas')}</th><th style={th}>{t('Latência média')}</th></tr></thead>
            <tbody>{[...dados].sort((a, b) => (a.uptime_pct ?? 101) - (b.uptime_pct ?? 101)).map(item => (
              <tr key={item.equipamento_id} onClick={() => onVerLatencia(item.equipamento_id)} title={t('Ver gráfico de latência')} style={{ borderTop: '1px solid #334155', cursor: 'pointer' }}>
                <td style={td}><div style={{ fontWeight: 'bold' }}>{item.nome}</div><div style={{ color: '#64748b', fontSize: '11px' }}>{item.ip}</div></td>
                <td style={{ ...td, minWidth: '170px' }}>
                  {item.uptime_pct == null ? <span style={{ color: '#64748b' }}>{t('sem dados ainda')}</span> : (
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


function percentil(valores, p) {
  if (!valores.length) return null
  const ord = [...valores].sort((a, b) => a - b)
  return ord[Math.min(ord.length - 1, Math.ceil((p / 100) * ord.length) - 1)]
}

function Latencia({ projectId, equipamentoInicial }) {
  const [equipamentos, setEquipamentos] = useState([])
  const [selecionado, setSelecionado] = useState(equipamentoInicial || '')
  const [horas, setHoras] = useState(24)
  const [dados, setDados] = useState(null)
  const [verTabela, setVerTabela] = useState(false)

  useEffect(() => {
    api.disponibilidadeProjeto(projectId, 24).then(r => {
      setEquipamentos(r.equipamentos)
      if (!equipamentoInicial && r.equipamentos.length) setSelecionado(r.equipamentos[0].equipamento_id)
    }).catch(e => toast.error(e.message))
  }, [projectId])

  useEffect(() => {
    if (!selecionado) return
    setDados(null)
    api.latenciaEquipamento(projectId, selecionado, horas).then(setDados).catch(e => { toast.error(e.message); setDados({ pontos: [] }) })
  }, [projectId, selecionado, horas])

  const valores = (dados?.pontos || []).filter(p => p.status === 'online' && p.ms != null).map(p => p.ms)
  const media = valores.length ? valores.reduce((a, b) => a + b, 0) / valores.length : null
  const fmt = (v) => v == null ? '—' : `${Math.round(v * 10) / 10} ms`
  const stats = [[t('Média'), media], [t('Mínima'), valores.length ? Math.min(...valores) : null], ['p95', percentil(valores, 95)], [t('Máxima'), valores.length ? Math.max(...valores) : null]]

  if (!equipamentos.length) return <div style={{ color: '#94a3b8' }}>{t('Nenhum equipamento monitorado neste mapa.')}</div>
  return (
    <>
      <div style={{ display: 'flex', gap: '8px', alignItems: 'center', marginBottom: '12px', flexWrap: 'wrap' }}>
        <select value={selecionado} onChange={e => setSelecionado(e.target.value)} style={{ padding: '6px 8px', borderRadius: '6px', border: '1px solid #334155', background: '#0f172a', color: 'white', fontSize: '13px' }}>
          {equipamentos.map(e => <option key={e.equipamento_id} value={e.equipamento_id}>{e.nome} ({e.ip})</option>)}
        </select>
        {PERIODOS.map(p => (
          <button key={p.horas} onClick={() => setHoras(p.horas)} style={{ padding: '4px 10px', fontSize: '12px', borderRadius: '12px', border: '1px solid #334155', cursor: 'pointer', background: horas === p.horas ? '#3b82f6' : 'transparent', color: 'white' }}>{t(p.rotulo)}</button>
        ))}
        <button onClick={() => setVerTabela(v => !v)} title={t('Alternar entre gráfico e tabela')} style={{ marginLeft: 'auto', display: 'flex', alignItems: 'center', gap: '5px', padding: '4px 10px', fontSize: '12px', borderRadius: '6px', border: '1px solid #334155', background: 'transparent', color: '#cbd5e1', cursor: 'pointer' }}>
          {verTabela ? <><LineChart size={13} /> {t('Gráfico')}</> : <><Table2 size={13} /> {t('Tabela')}</>}
        </button>
      </div>

      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(4, 1fr)', gap: '8px', marginBottom: '12px' }}>
        {stats.map(([rotulo, valor]) => (
          <div key={rotulo} style={{ background: '#0f172a', border: '1px solid #334155', borderRadius: '6px', padding: '8px 10px' }}>
            <div style={{ fontSize: '11px', color: '#94a3b8' }}>{rotulo}</div>
            <div style={{ fontSize: '17px', fontWeight: 'bold', color: 'white' }}>{fmt(valor)}</div>
          </div>
        ))}
      </div>

      <div style={{ fontSize: '13px', color: '#cbd5e1', marginBottom: '4px' }}>{t('Latência')}{dados?.nome ? ` — ${dados.nome}` : ''} (ms)</div>
      {dados === null ? <div style={{ color: '#94a3b8', height: 220 }}>{t('Carregando...')}</div>
        : dados.pontos.length === 0 ? <div style={{ color: '#94a3b8', padding: '30px 0' }}>{t('Ainda não há medições neste período.')}</div>
        : verTabela ? (
          <div style={{ maxHeight: '260px', overflow: 'auto' }}>
            <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: '12px' }}>
              <thead><tr style={{ color: '#94a3b8', textAlign: 'left' }}><th style={th}>{t('Horário')}</th><th style={th}>{t('Status')}</th><th style={th}>{t('Latência')}</th></tr></thead>
              <tbody>{[...dados.pontos].reverse().map((p, i) => (
                <tr key={i} style={{ borderTop: '1px solid #334155' }}>
                  <td style={{ ...td, color: '#94a3b8' }}>{new Date(p.t).toLocaleString(localeAtual())}</td>
                  <td style={{ ...td, color: p.status === 'online' ? '#10b981' : '#ef4444' }}>{t(p.status)}</td>
                  <td style={td}>{fmt(p.ms)}</td>
                </tr>
              ))}</tbody>
            </table>
          </div>
        ) : <LatencyChart pontos={dados.pontos} horas={horas} />}
      <div style={{ fontSize: '11px', color: '#64748b', marginTop: '6px' }}>{t('Um ponto é registrado a cada mudança de status e a cada 5 minutos.')}</div>
    </>
  )
}

function Eventos({ projectId }) {
  const [history, setHistory] = useState([])
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    api.historicoProjeto(projectId, 200)
      .then(setHistory)
      .catch(error => toast.error(error.message || t('Não foi possível carregar o histórico.')))
      .finally(() => setLoading(false))
  }, [projectId])

  if (loading) return <div style={{ color: '#94a3b8' }}>{t('Carregando histórico...')}</div>
  if (history.length === 0) return <div style={{ color: '#94a3b8' }}>{t('Ainda não há verificações registradas.')}</div>
  return (
    <div style={{ maxHeight: '55vh', overflow: 'auto' }}>
      <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: '13px' }}>
        <thead><tr style={{ color: '#94a3b8', textAlign: 'left' }}><th style={th}>{t('Equipamento')}</th><th style={th}>{t('Status')}</th><th style={th}>{t('Tempo')}</th><th style={th}>{t('Horário')}</th></tr></thead>
        <tbody>{history.map((item, index) => <tr key={`${item.equipamento_id}-${item.criado_em}-${index}`} style={{ borderTop: '1px solid #334155' }}>
          <td style={td}>{item.equipamento_nome || item.equipamento_id}</td>
          <td style={{ ...td, color: item.status === 'online' ? '#10b981' : '#ef4444' }}><span style={{ display: 'flex', alignItems: 'center', gap: '5px' }}>{item.status === 'online' ? <CheckCircle2 size={14} /> : <XCircle size={14} />} {t(item.status)}</span></td>
          <td style={{ ...td, color: '#94a3b8' }}>{item.tempo_ms == null ? '—' : `${item.tempo_ms} ms`}</td>
          <td style={{ ...td, color: '#94a3b8' }}><span style={{ display: 'flex', alignItems: 'center', gap: '4px' }}><Clock3 size={13} /> {new Date(item.criado_em).toLocaleString(localeAtual())}</span></td>
        </tr>)}</tbody>
      </table>
    </div>
  )
}

export default function HistoryModal({ projectId, onClose }) {
  useI18n()
  const [aba, setAba] = useState('disponibilidade')
  const [equipamentoLatencia, setEquipamentoLatencia] = useState(null)
  const verLatencia = (id) => { setEquipamentoLatencia(id); setAba('latencia') }

  return (
    <div style={{ position: 'absolute', inset: 0, backgroundColor: 'rgba(0,0,0,0.65)', display: 'flex', justifyContent: 'center', alignItems: 'center', zIndex: 1100 }}>
      <div style={{ backgroundColor: '#1e293b', padding: '25px', borderRadius: '12px', width: 'min(780px, 94vw)', maxHeight: '90vh', overflow: 'auto', border: '1px solid #334155', color: 'white' }}>
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '16px' }}>
          <h2 style={{ display: 'flex', alignItems: 'center', gap: '8px', fontSize: '20px' }}><Activity size={20} color="#3b82f6" /> {t('Histórico de disponibilidade')}</h2>
          <button onClick={onClose} style={{ background: 'transparent', border: 0, color: '#94a3b8', cursor: 'pointer' }}><X size={20} /></button>
        </div>
        <div style={{ display: 'flex', gap: '8px', marginBottom: '16px' }}>
          <Aba ativa={aba === 'disponibilidade'} onClick={() => setAba('disponibilidade')} icon={BarChart3}>{t('Disponibilidade')}</Aba>
          <Aba ativa={aba === 'latencia'} onClick={() => setAba('latencia')} icon={LineChart}>{t('Latência')}</Aba>
          <Aba ativa={aba === 'eventos'} onClick={() => setAba('eventos')} icon={List}>{t('Eventos')}</Aba>
        </div>
        {projectId === 'novo'
          ? <div style={{ color: '#94a3b8' }}>{t('Salve o projeto para começar a registrar o histórico.')}</div>
          : aba === 'disponibilidade' ? <Disponibilidade projectId={projectId} onVerLatencia={verLatencia} />
          : aba === 'latencia' ? <Latencia key={equipamentoLatencia || 'auto'} projectId={projectId} equipamentoInicial={equipamentoLatencia} />
          : <Eventos projectId={projectId} />}
      </div>
    </div>
  )
}
