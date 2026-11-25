import { useEffect, useState } from 'react'
import { X, CalendarClock, Trash2, Loader2, Plus, Repeat } from 'lucide-react'
import toast from 'react-hot-toast'
import { api } from '../../services/api'
import { t, useI18n, localeAtual } from '../../i18n'

// Monday = 0 ... Sunday = 6 (same as the API)
const DIAS = ['Seg', 'Ter', 'Qua', 'Qui', 'Sex', 'Sáb', 'Dom']
const campo = { padding: '7px 8px', borderRadius: '6px', border: '1px solid #334155', background: '#0f172a', color: 'white', fontSize: '13px', boxSizing: 'border-box' }
const rotulo = { display: 'grid', gap: '4px', fontSize: '12px', color: '#94a3b8' }
const botao = (cor) => ({ display: 'inline-flex', alignItems: 'center', gap: '5px', padding: '7px 12px', border: 0, borderRadius: '6px', background: cor, color: 'white', cursor: 'pointer', fontSize: '13px' })

const paraInputLocal = (data) => {
  const d = new Date(data.getTime() - data.getTimezoneOffset() * 60000)
  return d.toISOString().slice(0, 16)
}
const quando = (iso) => iso ? new Date(iso).toLocaleString(localeAtual(), { dateStyle: 'short', timeStyle: 'short' }) : ''
const duracaoTexto = (min) => min % 60 ? `${Math.floor(min / 60) ? `${Math.floor(min / 60)} h ` : ''}${min % 60} min` : `${min / 60} h`

// Maintenance calendar of a map: windows scheduled for later and weekly windows (e.g. every Sunday 02:00 for 2 h).
export default function AgendaManutencaoModal({ projectId, equipamentos = [], onClose, onMudou }) {
  useI18n()
  const [lista, setLista] = useState(null)
  const [tipo, setTipo] = useState('uma')
  const [alvo, setAlvo] = useState('')
  const amanha = new Date(Date.now() + 86400000); amanha.setHours(22, 0, 0, 0)
  const [inicio, setInicio] = useState(paraInputLocal(amanha))
  const [fim, setFim] = useState(paraInputLocal(new Date(amanha.getTime() + 2 * 3600000)))
  const [dias, setDias] = useState([6])
  const [hora, setHora] = useState('02:00')
  const [horas, setHoras] = useState(2)
  const [motivo, setMotivo] = useState('')
  const [salvando, setSalvando] = useState(false)

  const nomeDe = (id) => id ? (equipamentos.find(e => e.id === id)?.label || id) : t('Mapa inteiro')
  const carregar = () => api.listarManutencoes(projectId).then(setLista).catch(err => { toast.error(err.message); setLista([]) })
  useEffect(() => { carregar() }, [projectId]) // eslint-disable-line react-hooks/exhaustive-deps

  const salvar = async (e) => {
    e.preventDefault()
    const dados = { equipamento_id: alvo || null, motivo: motivo.trim() || null }
    if (tipo === 'uma') {
      Object.assign(dados, { inicio: new Date(inicio).toISOString(), ate: new Date(fim).toISOString() })
    } else {
      if (!dias.length) { toast.error(t('Escolha pelo menos um dia da semana.')); return }
      dados.recorrencia = { dias, hora, minutos: Math.round(Number(horas) * 60) }
    }
    setSalvando(true)
    try {
      await api.iniciarManutencao(projectId, dados)
      toast.success(t('Manutenção agendada.'))
      setMotivo('')
      carregar(); onMudou?.()
    } catch (err) { toast.error(err.message, { duration: 7000 }) } finally { setSalvando(false) }
  }

  const remover = async (m) => {
    if (!window.confirm(t('Remover esta manutenção da agenda?'))) return
    try { await api.removerManutencao(projectId, m.id); carregar(); onMudou?.() } catch (err) { toast.error(err.message) }
  }

  const descricao = (m) => {
    if (m.recorrencia) {
      const d = m.recorrencia.dias.map(i => t(DIAS[i])).join(', ')
      return t('Toda semana ({dias}) às {hora}, por {duracao}', { dias: d, hora: m.recorrencia.hora, duracao: duracaoTexto(m.recorrencia.minutos) })
    }
    return m.inicio ? `${quando(m.inicio)} → ${quando(m.ate)}` : t('Agora, até {hora}', { hora: quando(m.ate) })
  }

  return (
    <div style={{ position: 'fixed', inset: 0, backgroundColor: 'rgba(0,0,0,0.65)', display: 'flex', justifyContent: 'center', alignItems: 'center', zIndex: 1100 }}>
      <div role="dialog" aria-label={t('Agenda de manutenção')} style={{ backgroundColor: '#1e293b', padding: '22px', borderRadius: '12px', width: 'min(620px, 95vw)', maxHeight: '90vh', overflowY: 'auto', overflowX: 'hidden', border: '1px solid #334155', color: 'white', boxSizing: 'border-box' }}>
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '6px' }}>
          <h2 style={{ display: 'flex', alignItems: 'center', gap: '8px', fontSize: '19px' }}><CalendarClock size={20} color="#38bdf8" /> {t('Agenda de manutenção')}</h2>
          <button onClick={onClose} aria-label={t('Fechar')} style={{ background: 'transparent', border: 0, color: '#94a3b8', cursor: 'pointer' }}><X size={20} /></button>
        </div>
        <p style={{ fontSize: '12px', color: '#64748b', marginBottom: '14px' }}>
          {t('Durante a manutenção os alertas ficam em silêncio; o monitoramento e o histórico continuam. Horários semanais seguem o fuso do sistema.')}
        </p>

        <div style={{ display: 'grid', gap: '6px', marginBottom: '16px' }}>
          {lista === null ? <span style={{ color: '#94a3b8', fontSize: '13px' }}><Loader2 size={14} className="spin" /> {t('Carregando...')}</span>
            : lista.length === 0 ? <span style={{ color: '#94a3b8', fontSize: '13px' }}>{t('Nenhuma manutenção agendada.')}</span>
            : lista.map(m => (
              <div key={m.id} style={{ display: 'flex', alignItems: 'center', gap: '10px', padding: '8px 10px', background: '#0f172a', border: `1px solid ${m.ativa ? '#0369a1' : '#334155'}`, borderRadius: '6px', fontSize: '13px' }}>
                {m.recorrencia ? <Repeat size={15} color="#a78bfa" /> : <CalendarClock size={15} color="#38bdf8" />}
                <div style={{ flex: 1, minWidth: 0 }}>
                  <div style={{ fontWeight: 'bold' }}>{nomeDe(m.equipamento_id)}{m.ativa && <span style={{ color: '#38bdf8', fontWeight: 'normal' }}> · {t('ativa até {hora}', { hora: quando(m.ativa_ate) })}</span>}</div>
                  <div style={{ color: '#94a3b8' }}>{descricao(m)}{m.motivo ? ` — ${m.motivo}` : ''}</div>
                  {!m.ativa && m.proxima && m.recorrencia && <div style={{ color: '#64748b', fontSize: '12px' }}>{t('Próxima: {hora}', { hora: quando(m.proxima) })}</div>}
                </div>
                <button onClick={() => remover(m)} title={t('Remover')} aria-label={t('Remover')} style={{ ...botao('#334155'), padding: '6px 8px' }}><Trash2 size={14} /></button>
              </div>
            ))}
        </div>

        <form onSubmit={salvar} style={{ display: 'grid', gap: '10px', padding: '14px', background: '#0f172a', border: '1px solid #334155', borderRadius: '8px' }}>
          <div style={{ display: 'flex', gap: '6px' }}>
            {[['uma', t('Uma vez')], ['semanal', t('Toda semana')]].map(([v, r]) => (
              <button key={v} type="button" aria-pressed={tipo === v} onClick={() => setTipo(v)} style={botao(tipo === v ? '#0369a1' : '#334155')}>{r}</button>
            ))}
          </div>
          <label style={rotulo}>{t('O que silenciar')}
            <select value={alvo} onChange={e => setAlvo(e.target.value)} style={campo}>
              <option value="">{t('Mapa inteiro')}</option>
              {equipamentos.map(e => <option key={e.id} value={e.id}>{e.label}</option>)}
            </select>
          </label>
          {tipo === 'uma' ? (
            <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '10px' }}>
              <label style={rotulo}>{t('Início')}<input type="datetime-local" required value={inicio} onChange={e => setInicio(e.target.value)} style={campo} /></label>
              <label style={rotulo}>{t('Fim')}<input type="datetime-local" required value={fim} onChange={e => setFim(e.target.value)} style={campo} /></label>
            </div>
          ) : (
            <>
              <div style={{ display: 'flex', gap: '4px', flexWrap: 'wrap' }} role="group" aria-label={t('Dias da semana')}>
                {DIAS.map((d, i) => (
                  <button key={d} type="button" aria-pressed={dias.includes(i)} onClick={() => setDias(ds => ds.includes(i) ? ds.filter(x => x !== i) : [...ds, i].sort())}
                    style={{ ...botao(dias.includes(i) ? '#7c3aed' : '#334155'), padding: '6px 10px' }}>{t(d)}</button>
                ))}
              </div>
              <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '10px' }}>
                <label style={rotulo}>{t('Começa às')}<input type="time" required value={hora} onChange={e => setHora(e.target.value)} style={campo} /></label>
                <label style={rotulo}>{t('Duração (horas)')}<input type="number" required min={0.25} max={24} step={0.25} value={horas} onChange={e => setHoras(e.target.value)} style={campo} /></label>
              </div>
            </>
          )}
          <label style={rotulo}>{t('Motivo (opcional)')}<input value={motivo} maxLength={200} onChange={e => setMotivo(e.target.value)} placeholder={t('ex.: atualização de firmware')} style={campo} /></label>
          <div style={{ display: 'flex', justifyContent: 'flex-end' }}>
            <button type="submit" disabled={salvando} style={botao('#0369a1')}>{salvando ? <Loader2 size={14} className="spin" /> : <Plus size={14} />} {t('Agendar')}</button>
          </div>
        </form>
      </div>
    </div>
  )
}
