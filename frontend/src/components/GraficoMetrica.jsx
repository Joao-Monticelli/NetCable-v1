import { useEffect, useMemo, useRef, useState } from 'react'
import { t, useI18n, localeAtual } from '../i18n'

// Gráfico de linhas (SVG) para métricas ao longo do tempo: um eixo só, até 2 séries.
// Cores da paleta categórica validada para a superfície escura #1e293b (azul, laranja),
// legenda + rótulo direto no fim de cada linha, linha de limite tracejada e tooltip com cruz.
export const CORES_SERIES = ['#3987e5', '#d95926']
const TEXTO = '#94a3b8'
const GRADE = '#334155'
const ALTURA = 170
const MARGEM = { top: 10, right: 70, bottom: 24, left: 56 }

function topoBonito(max) {
  if (!max || max <= 0) return 10
  const passo = Math.pow(10, Math.floor(Math.log10(max)))
  for (const m of [1, 2, 2.5, 5, 10]) if (m * passo >= max) return m * passo
  return 10 * passo
}

export default function GraficoMetrica({ titulo, series, horas, formatar, yMax: yMaxFixo, limite, intervaloS = 60 }) {
  useI18n()
  const caixaRef = useRef(null)
  const [largura, setLargura] = useState(640)
  const [hover, setHover] = useState(null)
  const [tabela, setTabela] = useState(false)

  useEffect(() => {
    const el = caixaRef.current
    if (!el) return
    const ro = new ResizeObserver(([e]) => setLargura(Math.max(320, Math.floor(e.contentRect.width))))
    ro.observe(el)
    return () => ro.disconnect()
  }, [])

  const dados = useMemo(() => series.map(s => ({ ...s, pontos: s.pontos.filter(p => p.v != null).map(p => ({ t: new Date(p.t), v: p.v })) })), [series])
  const agora = useMemo(() => new Date(), [series])
  const inicio = useMemo(() => new Date(agora.getTime() - horas * 3600 * 1000), [agora, horas])
  const todos = dados.flatMap(s => s.pontos.map(p => p.v))
  const temDados = todos.length > 0
  const yMax = yMaxFixo || topoBonito(Math.max(...todos, limite?.valor || 0, 1) * 1.1)
  const w = largura - MARGEM.left - MARGEM.right
  const h = ALTURA - MARGEM.top - MARGEM.bottom
  const x = (tm) => MARGEM.left + ((tm - inicio) / (agora - inicio)) * w
  const y = (v) => MARGEM.top + h - (Math.min(v, yMax) / yMax) * h
  const lacuna = Math.max(3 * intervaloS * 1000, 5 * 60 * 1000) // sem coleta por mais que isso: quebra a linha

  const caminhos = dados.map(s => {
    let d = '', anterior = null
    for (const p of s.pontos) {
      const quebra = !anterior || p.t - anterior > lacuna
      d += `${quebra ? 'M' : 'L'}${x(p.t).toFixed(1)},${y(p.v).toFixed(1)}`
      anterior = p.t
    }
    return d
  })

  // Pontos isolados (sem vizinho próximo) ou séries curtas ganham marcador: uma linha de 1 ponto não aparece.
  const marcadores = dados.map(s => s.pontos.filter((p, i, arr) => arr.length <= 40 ||
    ((!arr[i - 1] || p.t - arr[i - 1].t > lacuna) && (!arr[i + 1] || arr[i + 1].t - p.t > lacuna))))

  const marcas = [0, 0.25, 0.5, 0.75, 1].map(f => f * yMax)
  const horasEixo = useMemo(() => {
    const passos = horas <= 24 ? 6 : horas <= 168 ? 7 : 6
    return Array.from({ length: passos + 1 }, (_, i) => new Date(inicio.getTime() + (i * (agora - inicio)) / passos))
  }, [inicio, agora, horas])
  const fmtHora = (d) => horas <= 24 ? d.toLocaleTimeString(localeAtual(), { hour: '2-digit', minute: '2-digit' }) : d.toLocaleDateString(localeAtual(), { day: '2-digit', month: '2-digit' })

  const aoMover = (e) => {
    const r = e.currentTarget.getBoundingClientRect()
    const px = e.clientX - r.left
    if (px < MARGEM.left || px > MARGEM.left + w) { setHover(null); return }
    const tm = inicio.getTime() + ((px - MARGEM.left) / w) * (agora - inicio)
    const valores = dados.map(s => {
      let melhor = null
      for (const p of s.pontos) if (!melhor || Math.abs(p.t - tm) < Math.abs(melhor.t - tm)) melhor = p
      return melhor && Math.abs(melhor.t - tm) <= lacuna ? melhor : null
    })
    const ref = valores.find(Boolean)
    setHover(ref ? { px: x(ref.t), t: ref.t, valores } : null)
  }

  const linhasTabela = useMemo(() => {
    const porTempo = new Map()
    dados.forEach((s, i) => s.pontos.forEach(p => {
      const k = p.t.getTime()
      if (!porTempo.has(k)) porTempo.set(k, { t: p.t, v: [] })
      porTempo.get(k).v[i] = p.v
    }))
    return [...porTempo.values()].sort((a, b) => b.t - a.t).slice(0, 60)
  }, [dados])

  return (
    <div ref={caixaRef} style={{ marginBottom: '14px' }}>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '4px', gap: '10px' }}>
        <span style={{ fontSize: '13px', fontWeight: 'bold', color: '#e2e8f0' }}>{titulo}</span>
        <span style={{ display: 'flex', alignItems: 'center', gap: '12px', fontSize: '12px', color: TEXTO }}>
          {series.length > 1 && series.map((s, i) => (
            <span key={s.nome} style={{ display: 'flex', alignItems: 'center', gap: '5px' }}>
              <i style={{ width: 12, height: 3, borderRadius: 2, background: CORES_SERIES[i], display: 'inline-block' }} /> {s.nome}
            </span>
          ))}
          <button type="button" onClick={() => setTabela(v => !v)} style={{ background: 'transparent', border: '1px solid #334155', color: TEXTO, borderRadius: 4, padding: '1px 6px', cursor: 'pointer', fontSize: '11px' }}>
            {tabela ? t('Gráfico') : t('Tabela')}
          </button>
        </span>
      </div>
      {!temDados ? (
        <div style={{ fontSize: '12px', color: '#64748b', padding: '18px 0' }}>{t('Ainda sem dados neste período.')}</div>
      ) : tabela ? (
        <div style={{ maxHeight: ALTURA, overflow: 'auto', fontSize: '12px' }}>
          <table style={{ width: '100%', borderCollapse: 'collapse' }}>
            <thead><tr style={{ color: TEXTO, textAlign: 'left' }}><th style={{ padding: '3px 6px' }}>{t('Horário')}</th>{series.map(s => <th key={s.nome} style={{ padding: '3px 6px' }}>{s.nome}</th>)}</tr></thead>
            <tbody>{linhasTabela.map(l => (
              <tr key={l.t.getTime()} style={{ borderTop: '1px solid #1e293b', color: '#e2e8f0' }}>
                <td style={{ padding: '3px 6px', color: TEXTO }}>{l.t.toLocaleString(localeAtual())}</td>
                {series.map((s, i) => <td key={s.nome} style={{ padding: '3px 6px' }}>{l.v[i] != null ? formatar(l.v[i]) : '—'}</td>)}
              </tr>
            ))}</tbody>
          </table>
        </div>
      ) : (
        <div style={{ position: 'relative' }}>
          <svg role="img" aria-label={titulo} width={largura} height={ALTURA} onMouseMove={aoMover} onMouseLeave={() => setHover(null)} style={{ display: 'block' }}>
            {marcas.map(v => (
              <g key={v}>
                <line x1={MARGEM.left} x2={MARGEM.left + w} y1={y(v)} y2={y(v)} stroke={GRADE} strokeWidth={1} />
                <text x={MARGEM.left - 6} y={y(v) + 4} textAnchor="end" fontSize="10" fill={TEXTO}>{formatar(v)}</text>
              </g>
            ))}
            {horasEixo.map((d, i) => (
              <text key={i} x={x(d)} y={ALTURA - 6} textAnchor={i === 0 ? 'start' : i === horasEixo.length - 1 ? 'end' : 'middle'} fontSize="10" fill={TEXTO}>{fmtHora(d)}</text>
            ))}
            {limite?.valor > 0 && limite.valor <= yMax && (
              <g>
                <line x1={MARGEM.left} x2={MARGEM.left + w} y1={y(limite.valor)} y2={y(limite.valor)} stroke="#cbd5e1" strokeWidth={1} strokeDasharray="4 4" />
                <text x={MARGEM.left + w + 4} y={y(limite.valor) + 4} fontSize="10" fill="#cbd5e1">{limite.rotulo}</text>
              </g>
            )}
            {caminhos.map((d, i) => <path key={i} d={d} fill="none" stroke={CORES_SERIES[i]} strokeWidth={2} strokeLinejoin="round" strokeLinecap="round" />)}
            {marcadores.map((pts, i) => pts.map(p => <circle key={`${i}-${p.t.getTime()}`} cx={x(p.t)} cy={y(p.v)} r={4} fill={CORES_SERIES[i]} stroke="#1e293b" strokeWidth={2} />))}
            {series.length > 1 && dados.map((s, i) => {
              const ultimo = s.pontos[s.pontos.length - 1]
              return ultimo ? <text key={s.nome} x={x(ultimo.t) + 6} y={y(ultimo.v) + 4} fontSize="10" fill="#e2e8f0">{s.nome}</text> : null
            })}
            {hover && <line x1={hover.px} x2={hover.px} y1={MARGEM.top} y2={MARGEM.top + h} stroke="#64748b" strokeWidth={1} />}
            {hover && hover.valores.map((p, i) => p && <circle key={i} cx={x(p.t)} cy={y(p.v)} r={4} fill={CORES_SERIES[i]} stroke="#1e293b" strokeWidth={2} />)}
          </svg>
          {hover && (
            <div style={{ position: 'absolute', top: 4, left: Math.min(hover.px + 10, largura - 170), pointerEvents: 'none', background: '#0f172a', border: '1px solid #334155', borderRadius: 6, padding: '6px 8px', fontSize: '12px', color: '#e2e8f0', minWidth: 140 }}>
              <div style={{ color: TEXTO, marginBottom: 3 }}>{hover.t.toLocaleString(localeAtual())}</div>
              {hover.valores.map((p, i) => p && (
                <div key={i} style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
                  <i style={{ width: 8, height: 8, borderRadius: 4, background: CORES_SERIES[i], display: 'inline-block' }} />
                  {series[i].nome}: <b>{formatar(p.v)}</b>
                </div>
              ))}
            </div>
          )}
        </div>
      )}
    </div>
  )
}
