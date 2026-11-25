import { useEffect, useState } from 'react'
import { useParams } from 'react-router-dom'
import { CheckCircle2, AlertTriangle, XCircle, Wrench, Loader2, CalendarClock, Network } from 'lucide-react'
import { api } from '../services/api'
import { t, useI18n, SeletorIdioma, localeAtual } from '../i18n'

// Status palette (good / warning / serious / critical) - always paired with an icon or a label.
const COR = { bom: '#0ca30c', aviso: '#fab219', serio: '#ec835a', critico: '#d03b3b', semDados: '#334155', manutencao: '#38bdf8' }
const FAIXAS = [[99.5, COR.bom], [98, COR.aviso], [90, COR.serio], [0, COR.critico]]
const corDoDia = (pct) => pct == null ? COR.semDados : FAIXAS.find(([min]) => pct >= min)[1]
const fmtPct = (v) => v == null ? '—' : `${v.toLocaleString(localeAtual(), { maximumFractionDigits: v >= 99.9 && v < 100 ? 2 : 1 })}%`
const DIAS_SEMANA = ['Seg', 'Ter', 'Qua', 'Qui', 'Sex', 'Sáb', 'Dom']

const GERAL = {
  operacional: { cor: COR.bom, icone: CheckCircle2, texto: 'Todos os sistemas operacionais' },
  parcial: { cor: COR.serio, icone: AlertTriangle, texto: 'Alguns serviços com problema' },
  fora: { cor: COR.critico, icone: XCircle, texto: 'Serviços fora do ar' },
  manutencao: { cor: COR.manutencao, icone: Wrench, texto: 'Manutenção em andamento' },
}
const STATUS = {
  online: { cor: COR.bom, icone: CheckCircle2, texto: 'Operacional' },
  offline: { cor: COR.critico, icone: XCircle, texto: 'Fora do ar' },
  manutencao: { cor: COR.manutencao, icone: Wrench, texto: 'Em manutenção' },
}

function useLargura() {
  const [w, setW] = useState(window.innerWidth)
  useEffect(() => { const f = () => setW(window.innerWidth); window.addEventListener('resize', f); return () => window.removeEventListener('resize', f) }, [])
  return w
}

// One bar per day; hover/focus shows the day and its availability below the strip.
function FaixaDias({ dias, nome }) {
  const [foco, setFoco] = useState(null)
  const dataTexto = (d) => new Date(`${d.data}T12:00:00`).toLocaleDateString(localeAtual(), { day: '2-digit', month: 'short' })
  return (
    <div>
      <div role="list" aria-label={t('Disponibilidade diária de {nome}', { nome })} style={{ display: 'flex', gap: '2px', height: '30px', alignItems: 'stretch' }}
        onMouseLeave={() => setFoco(null)}>
        {dias.map((d, i) => (
          <div key={d.data} role="listitem" tabIndex={0} onMouseEnter={() => setFoco(i)} onFocus={() => setFoco(i)} onBlur={() => setFoco(null)}
            aria-label={`${dataTexto(d)}: ${d.pct == null ? t('sem dados') : fmtPct(d.pct)}`}
            style={{ flex: 1, minWidth: '2px', borderRadius: '4px', background: corDoDia(d.pct), opacity: foco === null || foco === i ? 1 : 0.55,
              outline: foco === i ? '2px solid #e2e8f0' : 'none', outlineOffset: '1px', cursor: 'default' }} />
        ))}
      </div>
      <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: '11px', color: '#64748b', marginTop: '5px', minHeight: '15px' }}>
        {foco === null ? <>
          <span>{t('{n} dias atrás', { n: dias.length })}</span><span>{t('Hoje')}</span>
        </> : (
          <span style={{ color: '#cbd5e1' }}>
            {dataTexto(dias[foco])} · {dias[foco].pct == null ? t('sem dados de monitoramento') : t('{pct} disponível', { pct: fmtPct(dias[foco].pct) })}
          </span>
        )}
      </div>
    </div>
  )
}

// Public status page of a map (/status/:token): no login, no IPs, refreshes every minute.
export default function StatusPage() {
  useI18n()
  const { token } = useParams()
  const [dados, setDados] = useState(null)
  const [erro, setErro] = useState(null)
  const largura = useLargura()
  const nDias = largura < 560 ? 30 : largura < 860 ? 60 : 90

  useEffect(() => {
    let ativo = true
    const carregar = () => api.paginaStatus(token)
      .then(d => { if (ativo) { setDados(d); setErro(null); document.title = `${d.titulo} · ${t('Status')}` } })
      .catch(e => { if (ativo) setErro(e.message) })
    carregar()
    const id = setInterval(carregar, 60000)
    return () => { ativo = false; clearInterval(id) }
  }, [token])

  const pagina = { minHeight: '100vh', background: '#0f172a', color: '#e2e8f0', padding: '32px 16px', boxSizing: 'border-box' }
  const coluna = { maxWidth: '860px', margin: '0 auto' }
  if (erro && !dados) return <div style={pagina}><div style={{ ...coluna, textAlign: 'center', color: '#94a3b8', paddingTop: '80px' }}><XCircle size={40} color={COR.critico} style={{ margin: '0 auto 12px' }} />{erro}</div></div>
  if (!dados) return <div style={pagina}><div style={{ ...coluna, textAlign: 'center', paddingTop: '80px' }}><Loader2 className="spin" /></div></div>

  const geral = GERAL[dados.geral] || GERAL.operacional
  const IconeGeral = geral.icone
  const quando = (iso) => new Date(iso).toLocaleString(localeAtual(), { dateStyle: 'short', timeStyle: 'short' })

  return (
    <div style={pagina}>
      <div style={coluna}>
        <header style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', gap: '12px', marginBottom: '22px' }}>
          <h1 style={{ fontSize: '24px', margin: 0 }}>{dados.titulo}</h1>
          <SeletorIdioma compacto />
        </header>

        <div role="status" style={{ display: 'flex', alignItems: 'center', gap: '12px', padding: '16px 18px', borderRadius: '10px', background: '#1e293b', border: `1px solid ${geral.cor}`, marginBottom: '22px' }}>
          <IconeGeral size={26} color={geral.cor} />
          <div style={{ fontSize: '18px', fontWeight: 'bold' }}>{t(geral.texto)}</div>
        </div>

        {dados.manutencoes.length > 0 && (
          <section style={{ marginBottom: '22px' }}>
            <h2 style={{ fontSize: '15px', color: '#94a3b8', margin: '0 0 8px' }}>{t('Manutenções')}</h2>
            {dados.manutencoes.map((m, i) => (
              <div key={i} style={{ display: 'flex', gap: '10px', padding: '10px 14px', background: '#1e293b', borderRadius: '8px', border: '1px solid #334155', marginBottom: '6px', fontSize: '14px' }}>
                {m.ativa ? <Wrench size={17} color={COR.manutencao} /> : <CalendarClock size={17} color="#94a3b8" />}
                <div>
                  <div style={{ fontWeight: 'bold' }}>{m.alvo || t('Todos os serviços')}{m.motivo ? ` — ${m.motivo}` : ''}</div>
                  <div style={{ color: '#94a3b8', fontSize: '13px' }}>
                    {m.ativa ? t('Em andamento até {hora}', { hora: quando(m.ate) })
                      : m.recorrencia ? t('Toda semana ({dias}) às {hora}; próxima: {proxima}', { dias: m.recorrencia.dias.map(d => t(DIAS_SEMANA[d])).join(', '), hora: m.recorrencia.hora, proxima: quando(m.inicio) })
                      : t('Programada: {inicio} → {fim}', { inicio: quando(m.inicio), fim: quando(m.ate) })}
                  </div>
                </div>
              </div>
            ))}
          </section>
        )}

        <section style={{ background: '#1e293b', border: '1px solid #334155', borderRadius: '10px', overflow: 'hidden' }}>
          {dados.servicos.length === 0 && <div style={{ padding: '18px', color: '#94a3b8' }}>{t('Nenhum serviço publicado nesta página.')}</div>}
          {dados.servicos.map((s, i) => {
            const st = STATUS[s.status] || STATUS.offline
            const Icone = st.icone
            return (
              <div key={s.nome + i} style={{ padding: '16px 18px', borderTop: i ? '1px solid #334155' : 0 }}>
                <div style={{ display: 'flex', alignItems: 'center', gap: '10px', marginBottom: '10px', flexWrap: 'wrap' }}>
                  <span style={{ fontWeight: 'bold', fontSize: '15px' }}>{s.nome}</span>
                  <span style={{ display: 'inline-flex', alignItems: 'center', gap: '4px', fontSize: '13px', color: '#cbd5e1' }}><Icone size={15} color={st.cor} /> {t(st.texto)}</span>
                  <span style={{ marginLeft: 'auto', fontSize: '13px', color: '#94a3b8' }}>
                    {t('{pct} em {n} dias', { pct: fmtPct(nDias >= 90 ? s.uptime['90d'] : s.uptime['30d']), n: nDias >= 90 ? 90 : 30 })}
                  </span>
                </div>
                <FaixaDias dias={s.dias.slice(-nDias)} nome={s.nome} />
              </div>
            )
          })}
        </section>

        <div style={{ display: 'flex', gap: '14px', flexWrap: 'wrap', alignItems: 'center', fontSize: '12px', color: '#94a3b8', margin: '14px 2px 0' }} aria-label={t('Legenda')}>
          {FAIXAS.map(([min, cor], i) => [cor, i === 0 ? `≥ ${fmtPct(min)}` : i === FAIXAS.length - 1 ? `< ${fmtPct(FAIXAS[i - 1][0])}` : `${fmtPct(min)} – ${fmtPct(FAIXAS[i - 1][0])}`]).map(([cor, rotuloF]) => (
            <span key={rotuloF} style={{ display: 'inline-flex', alignItems: 'center', gap: '5px' }}><span style={{ width: 10, height: 10, borderRadius: 3, background: cor }} />{rotuloF}</span>
          ))}
          <span style={{ display: 'inline-flex', alignItems: 'center', gap: '5px' }}><span style={{ width: 10, height: 10, borderRadius: 3, background: COR.semDados }} />{t('sem dados')}</span>
        </div>

        <footer style={{ marginTop: '26px', display: 'flex', justifyContent: 'space-between', flexWrap: 'wrap', gap: '8px', fontSize: '12px', color: '#64748b' }}>
          <span>{t('Atualizado em {hora} · atualiza sozinho a cada minuto', { hora: quando(dados.atualizado_em) })}</span>
          <span style={{ display: 'inline-flex', alignItems: 'center', gap: '5px' }}><Network size={13} /> NetCable</span>
        </footer>
      </div>
    </div>
  )
}
