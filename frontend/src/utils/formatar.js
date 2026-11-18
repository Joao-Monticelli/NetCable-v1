// Formatação compartilhada de métricas (bit/s, uptime, velocidade de porta).
import { t } from '../i18n'

export function formatarBps(bps) {
  if (bps == null) return '—'
  const unidades = ['b/s', 'kb/s', 'Mb/s', 'Gb/s', 'Tb/s']
  let v = bps, i = 0
  while (v >= 1000 && i < unidades.length - 1) { v /= 1000; i++ }
  return `${v >= 100 || i === 0 ? Math.round(v) : v.toFixed(1)} ${unidades[i]}`
}

export function formatarVelocidade(mbps) {
  if (!mbps) return ''
  return mbps >= 1000 ? `${mbps / 1000 >= 10 ? Math.round(mbps / 1000) : (mbps / 1000).toFixed(mbps % 1000 ? 1 : 0)}G` : `${mbps}M`
}

export function formatarUptime(segundos) {
  if (segundos == null) return '—'
  const d = Math.floor(segundos / 86400), h = Math.floor((segundos % 86400) / 3600), m = Math.floor((segundos % 3600) / 60)
  if (d) return t('{d}d {h}h', { d, h })
  if (h) return t('{h}h {m}min', { h, m })
  return t('{m}min', { m })
}

// Texto curto de uma porta para tooltips: "ge-0/0/1 (uplink) · up 1G · ↓10 Mb/s ↑2 Mb/s"
export function resumoPorta(link) {
  if (!link) return ''
  const [, up, entrada, saida, nome, alias, vel] = link
  const partes = [`${nome}${alias ? ` (${alias})` : ''}`, `${up ? t('link ativo') : t('sem link')}${vel && up ? ' ' + formatarVelocidade(vel) : ''}`]
  if (up && (entrada != null || saida != null)) partes.push(`↓${formatarBps(entrada)} ↑${formatarBps(saida)}`)
  return partes.join(' · ')
}
