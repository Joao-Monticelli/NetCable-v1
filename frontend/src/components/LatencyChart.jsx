import { useEffect, useMemo, useRef, useState } from 'react'
import { XCircle } from 'lucide-react'
import { t, useI18n, localeAtual } from '../i18n'

// Gráfico de linha (SVG puro) da latência de UM equipamento.
// Série única: sem caixa de legenda (o título nomeia a série). Faixas vermelhas
// suaves marcam os períodos offline, com rótulo "Offline" abaixo do gráfico e no
// tooltip, para não depender só da cor.
const COR_LINHA = '#3b82f6'      // validada contra a superfície #1e293b
const COR_OFFLINE = '#ef4444'
const TEXTO = '#94a3b8'
const GRADE = '#334155'
const ALTURA = 220
const MARGEM = { top: 12, right: 16, bottom: 26, left: 52 }

function topoBonito(max) {
  if (!max || max <= 0) return 10
  const passo = Math.pow(10, Math.floor(Math.log10(max)))
  for (const m of [1, 2, 2.5, 5, 10]) if (m * passo >= max) return m * passo
  return 10 * passo
}

const fmtMs = (v) => (v >= 100 ? Math.round(v) : Math.round(v * 10) / 10) + ' ms'

export default function LatencyChart({ pontos, horas }) {
  useI18n()
  const caixaRef = useRef(null)
  const [largura, setLargura] = useState(640)
  const [hover, setHover] = useState(null)

  useEffect(() => {
    const el = caixaRef.current
    if (!el) return
    const ro = new ResizeObserver(([e]) => setLargura(Math.max(320, Math.floor(e.contentRect.width))))
    ro.observe(el)
    return () => ro.disconnect()
  }, [])

  const dados = useMemo(() => pontos.map(p => ({ ...p, t: new Date(p.t) })), [pontos])
  const agora = useMemo(() => new Date(), [pontos])
  const inicio = useMemo(() => new Date(agora.getTime() - horas * 3600 * 1000), [agora, horas])

  const valores = dados.filter(p => p.status === 'online' && p.ms != null).map(p => p.ms)
  const yMax = topoBonito(Math.max(...valores, 1) * 1.1)
  const w = largura - MARGEM.left - MARGEM.right
  const h = ALTURA - MARGEM.top - MARGEM.bottom
  const x = (tm) => MARGEM.left + ((tm - inicio) / (agora - inicio)) * w
  const y = (v) => MARGEM.top + h - (v / yMax) * h

  // Linha quebrada nos períodos offline / sem medição.
  const caminho = useMemo(() => {
    let d = '', aberto = false
    for (const p of dados) {
      if (p.status === 'online' && p.ms != null) { d += `${aberto ? 'L' : 'M'}${x(p.t).toFixed(1)},${y(p.ms).toFixed(1)}`; aberto = true }
      else aberto = false
    }
    return d
  }, [dados, largura, yMax])

  const faixasOffline = useMemo(() => {
    const faixas = []
    dados.forEach((p, i) => {
      if (p.status !== 'offline') return
      const fim = i + 1 < dados.length ? dados[i + 1].t : agora
      const ultima = faixas[faixas.length - 1]
      if (ultima && ultima.fim.getTime() === p.t.getTime()) ultima.fim = fim
      else faixas.push({ inicio: p.t, fim })
    })
    return faixas
  }, [dados, agora])

  const ticksY = [0, 0.25, 0.5, 0.75, 1].map(f => f * yMax)
  const ticksX = Array.from({ length: 5 }, (_, i) => new Date(inicio.getTime() + (i / 4) * (agora - inicio)))
  const fmtX = (d) => horas <= 24 ? d.toLocaleTimeString(localeAtual(), { hour: '2-digit', minute: '2-digit' }) : d.toLocaleDateString(localeAtual(), { day: '2-digit', month: '2-digit' })

  const aoMover = (e) => {
    if (!dados.length) return
    const ret = e.currentTarget.getBoundingClientRect()
    const px = e.clientX - ret.left
    let melhor = null, dist = Infinity
    for (const p of dados) { const d = Math.abs(x(p.t) - px); if (d < dist) { dist = d; melhor = p } }
    setHover(melhor)
  }

  return (
    <div ref={caixaRef} style={{ position: 'relative', width: '100%' }}>
      <svg width={largura} height={ALTURA} role="img" aria-label={t('Gráfico de latência ao longo do tempo')} style={{ display: 'block' }}>
        {ticksY.map(v => (
          <g key={v}>
            <line x1={MARGEM.left} x2={MARGEM.left + w} y1={y(v)} y2={y(v)} stroke={GRADE} strokeWidth="1" strokeDasharray={v === 0 ? '' : '2 4'} />
            <text x={MARGEM.left - 8} y={y(v) + 4} textAnchor="end" fontSize="11" fill={TEXTO}>{v === 0 ? '0' : fmtMs(v)}</text>
          </g>
        ))}
        {ticksX.map((d, i) => (
          <text key={i} x={x(d)} y={ALTURA - 6} textAnchor={i === 0 ? 'start' : i === 4 ? 'end' : 'middle'} fontSize="11" fill={TEXTO}>{fmtX(d)}</text>
        ))}
        {faixasOffline.map((f, i) => (
          <rect key={i} x={x(f.inicio)} y={MARGEM.top} width={Math.max(2, x(f.fim) - x(f.inicio))} height={h} fill={COR_OFFLINE} opacity="0.18" />
        ))}
        <path d={caminho} fill="none" stroke={COR_LINHA} strokeWidth="2" strokeLinejoin="round" strokeLinecap="round" />
        {/* Medições isoladas (sem vizinha online) não formam linha: marca com um ponto. */}
        {dados.map((p, i) => {
          const valido = (q) => q && q.status === 'online' && q.ms != null
          if (!valido(p) || valido(dados[i - 1]) || valido(dados[i + 1])) return null
          return <circle key={i} cx={x(p.t)} cy={y(p.ms)} r="4" fill={COR_LINHA} />
        })}
        {hover && (
          <g pointerEvents="none">
            <line x1={x(hover.t)} x2={x(hover.t)} y1={MARGEM.top} y2={MARGEM.top + h} stroke={TEXTO} strokeWidth="1" />
            {hover.status === 'online' && hover.ms != null && (
              <circle cx={x(hover.t)} cy={y(hover.ms)} r="4.5" fill={COR_LINHA} stroke="#1e293b" strokeWidth="2" />
            )}
          </g>
        )}
        {/* Área de captura maior que a linha, para o crosshair */}
        <rect x={MARGEM.left} y={MARGEM.top} width={w} height={h} fill="transparent" onPointerMove={aoMover} onPointerLeave={() => setHover(null)} style={{ cursor: 'crosshair' }} />
      </svg>

      {hover && (
        <div style={{ position: 'absolute', top: 8, left: Math.min(Math.max(x(hover.t) + 12, 0), largura - 170), width: 160, pointerEvents: 'none', background: '#0f172a', border: '1px solid #334155', borderRadius: '6px', padding: '8px 10px', fontSize: '12px', boxShadow: '0 4px 10px rgba(0,0,0,0.4)' }}>
          {hover.status === 'online' && hover.ms != null
            ? <div style={{ display: 'flex', alignItems: 'center', gap: '6px' }}><span style={{ width: 12, height: 2, background: COR_LINHA, display: 'inline-block' }} /><b style={{ color: 'white', fontSize: '14px' }}>{fmtMs(hover.ms)}</b></div>
            : <div style={{ display: 'flex', alignItems: 'center', gap: '6px', color: 'white', fontWeight: 'bold' }}><XCircle size={14} color={COR_OFFLINE} /> {hover.status === 'offline' ? t('Offline') : t('Sem medição')}</div>}
          <div style={{ color: TEXTO, marginTop: '3px' }}>{hover.t.toLocaleString(localeAtual())}</div>
        </div>
      )}

      {faixasOffline.length > 0 && (
        <div style={{ display: 'flex', alignItems: 'center', gap: '6px', fontSize: '12px', color: TEXTO, marginTop: '4px' }}>
          <span style={{ width: 14, height: 10, background: COR_OFFLINE, opacity: 0.35, display: 'inline-block', borderRadius: 2 }} /> {t('Offline')}
        </div>
      )}
    </div>
  )
}
