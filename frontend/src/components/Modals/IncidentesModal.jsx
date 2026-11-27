import { useEffect, useState } from 'react'
import { X, Megaphone, Loader2, Plus, Send, Trash2, CheckCircle2 } from 'lucide-react'
import toast from 'react-hot-toast'
import { api } from '../../services/api'
import { t, useI18n, localeAtual } from '../../i18n'
import { ESTADOS_INCIDENTE, IMPACTOS } from '../../utils/incidentes'


const rotulo = { fontSize: '13px', color: '#94a3b8', display: 'grid', gap: '4px' }
const campo = { width: '100%', padding: '8px', borderRadius: '6px', border: '1px solid #334155', backgroundColor: '#0f172a', color: 'white', boxSizing: 'border-box', fontFamily: 'inherit', fontSize: '13px' }
const botao = (cor) => ({ display: 'inline-flex', alignItems: 'center', gap: '6px', padding: '8px 12px', border: 0, borderRadius: '6px', background: cor, color: 'white', cursor: 'pointer', fontSize: '13px' })
const quando = (iso) => iso ? new Date(iso).toLocaleString(localeAtual(), { dateStyle: 'short', timeStyle: 'short' }) : ''

// Devices that can be listed as affected (only the ones shown on the status page appear there).
const listaEquipamentos = (nodes) => nodes
  .filter(n => n.type !== 'rack' && n.data?.tipo !== 'Atalho de mapa' && n.data?.ip && n.data.ip !== 'Sem IP')
  .map(n => ({ id: n.id, nome: n.data.label, publico: n.data.statusPublico !== false }))
  .sort((a, b) => a.nome.localeCompare(b.nome))

function NovoIncidente({ projectId, equipamentos, onCriado, onCancelar }) {
  const [dados, setDados] = useState({ titulo: '', mensagem: '', impacto: 'parcial', estado: 'investigando', afetados: [] })
  const [enviando, setEnviando] = useState(false)
  const set = (k) => (e) => setDados({ ...dados, [k]: e.target.value })
  const alternar = (id) => setDados({ ...dados, afetados: dados.afetados.includes(id) ? dados.afetados.filter(x => x !== id) : [...dados.afetados, id] })
  const enviar = async (e) => {
    e.preventDefault()
    setEnviando(true)
    try { onCriado(await api.criarIncidente(projectId, dados)); toast.success(t('Incidente publicado na página de status.')) }
    catch (err) { toast.error(err.message) } finally { setEnviando(false) }
  }
  return (
    <form onSubmit={enviar} style={{ display: 'grid', gap: '10px', padding: '14px', background: '#0f172a', borderRadius: '8px', border: '1px solid #334155' }}>
      <label style={rotulo}>{t('Título')}<input required maxLength={120} aria-label={t('Título do incidente')} value={dados.titulo} onChange={set('titulo')} placeholder={t('ex.: Lentidão no acesso à internet')} style={campo} /></label>
      <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '8px' }}>
        <label style={rotulo}>{t('Impacto')}
          <select aria-label={t('Impacto')} value={dados.impacto} onChange={set('impacto')} style={campo}>
            {Object.entries(IMPACTOS).map(([k, v]) => <option key={k} value={k}>{t(v.texto)}</option>)}
          </select>
        </label>
        <label style={rotulo}>{t('Situação')}
          <select aria-label={t('Situação')} value={dados.estado} onChange={set('estado')} style={campo}>
            {Object.entries(ESTADOS_INCIDENTE).filter(([k]) => k !== 'resolvido').map(([k, v]) => <option key={k} value={k}>{t(v)}</option>)}
          </select>
        </label>
      </div>
      <label style={rotulo}>{t('O que está acontecendo')}<textarea required maxLength={2000} rows={3} aria-label={t('Mensagem do incidente')} value={dados.mensagem} onChange={set('mensagem')}
        placeholder={t('ex.: O link principal está instável. Estamos falando com a operadora.')} style={{ ...campo, resize: 'vertical' }} /></label>
      {equipamentos.length > 0 && (
        <fieldset style={{ border: '1px solid #334155', borderRadius: '6px', padding: '8px 10px', margin: 0 }}>
          <legend style={{ fontSize: '12px', color: '#94a3b8', padding: '0 4px' }}>{t('Serviços afetados (opcional)')}</legend>
          <div style={{ display: 'flex', flexWrap: 'wrap', gap: '4px 12px', maxHeight: '110px', overflow: 'auto' }}>
            {equipamentos.map(e => (
              <label key={e.id} style={{ fontSize: '12px', color: e.publico ? '#e2e8f0' : '#64748b', display: 'flex', alignItems: 'center', gap: '4px' }} title={e.publico ? '' : t('Não aparece na página de status')}>
                <input type="checkbox" checked={dados.afetados.includes(e.id)} onChange={() => alternar(e.id)} /> {e.nome}
              </label>
            ))}
          </div>
        </fieldset>
      )}
      <div style={{ display: 'flex', gap: '8px', justifyContent: 'flex-end' }}>
        <button type="button" onClick={onCancelar} style={botao('#334155')}>{t('Cancelar')}</button>
        <button type="submit" disabled={enviando} style={botao('#d97706')}>{enviando ? <Loader2 size={14} className="spin" /> : <Megaphone size={14} />} {t('Publicar incidente')}</button>
      </div>
    </form>
  )
}

function Incidente({ projectId, inc, podeEditar, onAlterado, onExcluido }) {
  const [estado, setEstado] = useState(inc.estado === 'resolvido' ? 'resolvido' : inc.estado)
  const [mensagem, setMensagem] = useState('')
  const [enviando, setEnviando] = useState(false)
  const impacto = IMPACTOS[inc.impacto] || IMPACTOS.parcial
  const resolvido = inc.estado === 'resolvido'
  const atualizar = async (e) => {
    e.preventDefault()
    setEnviando(true)
    try { onAlterado(await api.atualizarIncidente(projectId, inc.id, { estado, mensagem })); setMensagem(''); toast.success(t('Atualização publicada.')) }
    catch (err) { toast.error(err.message) } finally { setEnviando(false) }
  }
  const excluir = async () => {
    if (!window.confirm(t('Excluir este incidente? Ele some da página de status (use só para algo publicado por engano).'))) return
    try { await api.excluirIncidente(projectId, inc.id); onExcluido(inc.id) } catch (err) { toast.error(err.message) }
  }
  return (
    <div style={{ padding: '12px 14px', background: '#0f172a', borderRadius: '8px', border: '1px solid #334155', borderLeft: `4px solid ${resolvido ? '#475569' : impacto.cor}`, display: 'grid', gap: '8px' }}>
      <div style={{ display: 'flex', alignItems: 'center', gap: '8px', flexWrap: 'wrap' }}>
        {resolvido && <CheckCircle2 size={15} color="#0ca30c" />}
        <strong style={{ fontSize: '14px' }}>{inc.titulo}</strong>
        <span style={{ fontSize: '12px', color: '#94a3b8' }}>{t(ESTADOS_INCIDENTE[inc.estado])} · {t(impacto.texto)}</span>
        {podeEditar && <button onClick={excluir} title={t('Excluir')} aria-label={t('Excluir incidente')} style={{ marginLeft: 'auto', background: 'transparent', border: 0, color: '#64748b', cursor: 'pointer' }}><Trash2 size={14} /></button>}
      </div>
      {inc.afetados.length > 0 && <div style={{ fontSize: '12px', color: '#94a3b8' }}>{t('Afetados: {lista}', { lista: inc.afetados.join(', ') })}</div>}
      <ol style={{ listStyle: 'none', margin: 0, padding: 0, display: 'grid', gap: '6px' }}>
        {inc.atualizacoes.map((a, i) => (
          <li key={i} style={{ fontSize: '13px', lineHeight: 1.45 }}>
            <span style={{ color: '#cbd5e1', fontWeight: 'bold' }}>{t(ESTADOS_INCIDENTE[a.estado])}</span>
            <span style={{ color: '#64748b' }}> · {quando(a.criado_em)}{a.usuario ? ` · ${a.usuario}` : ''}</span>
            <div style={{ color: '#e2e8f0', whiteSpace: 'pre-wrap' }}>{a.mensagem}</div>
          </li>
        ))}
      </ol>
      {podeEditar && (
        <form onSubmit={atualizar} style={{ display: 'grid', gridTemplateColumns: 'minmax(130px, 1fr) 3fr auto', gap: '6px', alignItems: 'start' }}>
          <select aria-label={t('Nova situação')} value={estado} onChange={e => setEstado(e.target.value)} style={campo}>
            {Object.entries(ESTADOS_INCIDENTE).map(([k, v]) => <option key={k} value={k}>{t(v)}</option>)}
          </select>
          <input required maxLength={2000} aria-label={t('Atualização do incidente')} value={mensagem} onChange={e => setMensagem(e.target.value)}
            placeholder={estado === 'resolvido' ? t('ex.: Link normalizado; seguimos acompanhando.') : t('O que mudou?')} style={campo} />
          <button type="submit" disabled={enviando} title={t('Publicar atualização')} aria-label={t('Publicar atualização')} style={botao('#334155')}>{enviando ? <Loader2 size={14} className="spin" /> : <Send size={14} />}</button>
        </form>
      )}
    </div>
  )
}

// Incidents of the map, shown on its public status page ("Investigating", "Monitoring", "Resolved").
export default function IncidentesModal({ projectId, nodes = [], podeEditar, onClose }) {
  useI18n()
  const [lista, setLista] = useState(null)
  const [criando, setCriando] = useState(false)
  useEffect(() => { api.listarIncidentes(projectId).then(setLista).catch(e => { toast.error(e.message); setLista([]) }) }, [projectId])
  const substituir = (inc) => setLista(l => [inc, ...l.filter(x => x.id !== inc.id)].sort((a, b) => b.criado_em.localeCompare(a.criado_em)))
  const abertos = (lista || []).filter(i => i.estado !== 'resolvido')
  const resolvidos = (lista || []).filter(i => i.estado === 'resolvido')

  return (
    <div style={{ position: 'fixed', inset: 0, backgroundColor: 'rgba(0,0,0,0.65)', display: 'flex', justifyContent: 'center', alignItems: 'center', zIndex: 1150 }}>
      <div role="dialog" aria-label={t('Incidentes')} style={{ backgroundColor: '#1e293b', padding: '22px', borderRadius: '12px', width: 'min(640px, 94vw)', maxHeight: '90vh', overflow: 'auto', border: '1px solid #334155', color: 'white', boxSizing: 'border-box' }}>
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '6px' }}>
          <h2 style={{ display: 'flex', alignItems: 'center', gap: '8px', fontSize: '19px' }}><Megaphone size={20} color="#f59e0b" /> {t('Incidentes')}</h2>
          <button onClick={onClose} aria-label={t('Fechar')} style={{ background: 'transparent', border: 0, color: '#94a3b8', cursor: 'pointer' }}><X size={20} /></button>
        </div>
        <p style={{ fontSize: '13px', color: '#94a3b8', lineHeight: 1.5, marginBottom: '14px' }}>
          {t('Avise na página de status o que está acontecendo e como está a solução. Incidentes resolvidos continuam visíveis por 7 dias.')}
        </p>
        {lista === null ? <Loader2 size={18} className="spin" /> : (
          <div style={{ display: 'grid', gap: '10px' }}>
            {podeEditar && (criando
              ? <NovoIncidente projectId={projectId} equipamentos={listaEquipamentos(nodes)} onCancelar={() => setCriando(false)} onCriado={(inc) => { substituir(inc); setCriando(false) }} />
              : <button onClick={() => setCriando(true)} style={{ ...botao('#d97706'), justifySelf: 'start' }}><Plus size={14} /> {t('Novo incidente')}</button>)}
            {abertos.length === 0 && !criando && <div style={{ fontSize: '13px', color: '#64748b' }}>{t('Nenhum incidente em aberto.')}</div>}
            {abertos.map(inc => <Incidente key={inc.id} projectId={projectId} inc={inc} podeEditar={podeEditar} onAlterado={substituir} onExcluido={(id) => setLista(l => l.filter(x => x.id !== id))} />)}
            {resolvidos.length > 0 && <h3 style={{ fontSize: '13px', color: '#94a3b8', margin: '8px 0 0' }}>{t('Resolvidos')}</h3>}
            {resolvidos.map(inc => <Incidente key={inc.id} projectId={projectId} inc={inc} podeEditar={podeEditar} onAlterado={substituir} onExcluido={(id) => setLista(l => l.filter(x => x.id !== id))} />)}
          </div>
        )}
      </div>
    </div>
  )
}
