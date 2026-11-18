import { useEffect, useRef, useState } from 'react'
import { X, Loader2, Cpu, MemoryStick, Thermometer, Clock, Gauge } from 'lucide-react'
import { api } from '../../services/api'
import GraficoMetrica from '../GraficoMetrica'
import { formatarBps, formatarUptime, formatarVelocidade } from '../../utils/formatar'
import { t, useI18n, localeAtual } from '../../i18n'

const PERIODOS = [[1, '1 h'], [24, '24 h'], [168, '7 dias']]

function Cartao({ icone, rotulo, valor, alerta }) {
  return (
    <div style={{ flex: 1, minWidth: 120, padding: '10px 12px', background: '#0f172a', border: `1px solid ${alerta ? '#b45309' : '#334155'}`, borderRadius: 8 }}>
      <div style={{ display: 'flex', alignItems: 'center', gap: 6, fontSize: '12px', color: '#94a3b8' }}>{icone} {rotulo}</div>
      <div style={{ fontSize: '20px', fontWeight: 'bold', marginTop: 4, color: '#f1f5f9' }}>
        {valor}{alerta && <span style={{ fontSize: '11px', color: '#fbbf24', marginLeft: 6, fontWeight: 'normal' }}>⚠ {t('acima do limite')}</span>}
      </div>
    </div>
  )
}

const pct = (v) => v == null ? '—' : `${Math.round(v)}%`
const graus = (v) => v == null ? '—' : `${Math.round(v * 10) / 10} °C`

export default function MetricasModal({ projectId, node, onClose }) {
  useI18n()
  const [horas, setHoras] = useState(24)
  const [dados, setDados] = useState(null)
  const [erro, setErro] = useState(null)
  const ajustouPeriodo = useRef(false)

  useEffect(() => {
    let ativo = true
    const carregar = () => api.metricasEquipamento(projectId, node.id, horas)
      .then(d => {
        if (!ativo) return
        setDados(d); setErro(null)
        // Histórico ainda curto (equipamento recém-configurado): começa mostrando a última hora.
        if (!ajustouPeriodo.current) {
          ajustouPeriodo.current = true
          const primeiro = d.historico?.[0]?.t
          if (horas === 24 && primeiro && Date.now() - new Date(primeiro).getTime() < 3600 * 1000) setHoras(1)
        }
      })
      .catch(e => { if (ativo) setErro(e.message) })
    carregar()
    const timer = setInterval(carregar, 30000)
    return () => { ativo = false; clearInterval(timer) }
  }, [projectId, node.id, horas])

  const atual = dados?.atual
  const limites = dados?.limites || {}
  const serie = (campo) => (dados?.historico || []).map(p => ({ t: p.t, v: p[campo] }))
  const portas = (atual?.interfaces || []).filter(i => i.fisica || i.up)

  return (
    <div style={{ position: 'fixed', inset: 0, backgroundColor: 'rgba(0,0,0,0.65)', display: 'flex', justifyContent: 'center', alignItems: 'center', zIndex: 1100 }}>
      <div role="dialog" aria-label={t('Métricas SNMP')} style={{ backgroundColor: '#1e293b', padding: '22px', borderRadius: '12px', width: 'min(860px, 96vw)', maxHeight: '94vh', overflow: 'auto', border: '1px solid #334155', color: 'white' }}>
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '4px' }}>
          <h2 style={{ display: 'flex', alignItems: 'center', gap: '8px', fontSize: '19px' }}><Gauge size={20} color="#3987e5" /> {node.data.label} <span style={{ fontSize: '13px', color: '#94a3b8', fontWeight: 'normal' }}>{node.data.ip}</span></h2>
          <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
            {PERIODOS.map(([h, r]) => (
              <button key={h} onClick={() => setHoras(h)} aria-pressed={horas === h} style={{ padding: '4px 10px', borderRadius: 12, border: '1px solid #334155', background: horas === h ? '#3987e5' : 'transparent', color: 'white', cursor: 'pointer', fontSize: '12px' }}>{r}</button>
            ))}
            <button onClick={onClose} aria-label={t('Fechar')} style={{ background: 'transparent', border: 0, color: '#94a3b8', cursor: 'pointer' }}><X size={20} /></button>
          </div>
        </div>
        {atual?.descricao && <p style={{ color: '#64748b', fontSize: '12px', marginBottom: '10px' }}>{atual.descricao}</p>}

        {erro ? <div style={{ color: '#ef4444', fontSize: '13px' }}>{erro}</div>
          : !dados ? <div style={{ color: '#94a3b8' }}><Loader2 size={16} className="spin" /> {t('Carregando...')}</div>
          : !dados.snmp ? <div style={{ color: '#94a3b8', fontSize: '13px' }}>{t('Métricas disponíveis para equipamentos monitorados por SNMPv3. Mude o método de monitoramento deste equipamento para SNMPv3.')}</div>
          : <>
            {!atual && <div style={{ color: '#94a3b8', fontSize: '13px', marginBottom: 10 }}>{t('Aguardando a primeira coleta (a cada {s} s, com o equipamento online).', { s: dados.intervalo_s })}</div>}
            <div style={{ display: 'flex', gap: 10, flexWrap: 'wrap', marginBottom: 14 }}>
              <Cartao icone={<Cpu size={14} />} rotulo={t('CPU')} valor={pct(atual?.cpu_pct)} alerta={limites.cpu > 0 && atual?.cpu_pct >= limites.cpu} />
              <Cartao icone={<MemoryStick size={14} />} rotulo={t('Memória')} valor={pct(atual?.memoria_pct)} />
              <Cartao icone={<Thermometer size={14} />} rotulo={t('Temperatura')} valor={graus(atual?.temperatura_c)} alerta={limites.temperatura > 0 && atual?.temperatura_c >= limites.temperatura} />
              <Cartao icone={<Clock size={14} />} rotulo={t('Ligado há')} valor={formatarUptime(atual?.uptime_s)} />
            </div>

            <GraficoMetrica titulo={t('Temperatura (°C)')} horas={horas} intervaloS={dados.intervalo_s} formatar={v => `${Math.round(v)} °C`}
              series={[{ nome: t('Temperatura'), pontos: serie('temp') }]}
              limite={limites.temperatura > 0 ? { valor: limites.temperatura, rotulo: t('limite') } : null} />
            <GraficoMetrica titulo={t('CPU e memória (%)')} horas={horas} intervaloS={dados.intervalo_s} formatar={v => `${Math.round(v)}%`} yMax={100}
              series={[{ nome: t('CPU'), pontos: serie('cpu') }, { nome: t('Memória'), pontos: serie('mem') }]}
              limite={limites.cpu > 0 ? { valor: limites.cpu, rotulo: t('limite CPU') } : null} />
            <GraficoMetrica titulo={t('Tráfego total das portas')} horas={horas} intervaloS={dados.intervalo_s} formatar={formatarBps}
              series={[{ nome: t('Entrada'), pontos: serie('in') }, { nome: t('Saída'), pontos: serie('out') }]} />

            {portas.length > 0 && <>
              <div style={{ fontSize: '13px', fontWeight: 'bold', margin: '6px 0' }}>{t('Portas')} <span style={{ color: '#64748b', fontWeight: 'normal', fontSize: '12px' }}>{t('coletado às {hora}', { hora: new Date(atual.coletado_em).toLocaleTimeString(localeAtual()) })}</span></div>
              <div style={{ border: '1px solid #334155', borderRadius: 8, overflow: 'auto', maxHeight: 280 }}>
                <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: '12px' }}>
                  <thead style={{ position: 'sticky', top: 0, background: '#0f172a', color: '#94a3b8', textAlign: 'left' }}>
                    <tr>{[t('Porta'), t('Descrição'), t('Status'), t('Velocidade'), t('Entrada'), t('Saída'), t('Erros')].map(c => <th key={c} style={{ padding: '6px 8px' }}>{c}</th>)}</tr>
                  </thead>
                  <tbody>
                    {portas.map(p => (
                      <tr key={p.indice} style={{ borderTop: '1px solid #1e293b' }}>
                        <td style={{ padding: '5px 8px', fontFamily: 'monospace' }}>{p.ordem ? <span style={{ color: '#64748b' }}>{p.ordem}. </span> : null}{p.nome}</td>
                        <td style={{ padding: '5px 8px', color: '#94a3b8' }}>{p.alias || '—'}</td>
                        <td style={{ padding: '5px 8px' }}><span style={{ display: 'inline-flex', alignItems: 'center', gap: 5 }}><i style={{ width: 8, height: 8, borderRadius: 4, background: p.up ? '#22c55e' : '#475569', display: 'inline-block' }} />{p.up ? t('ativo') : t('sem link')}</span></td>
                        <td style={{ padding: '5px 8px' }}>{p.up ? formatarVelocidade(p.velocidade_mbps) : '—'}</td>
                        <td style={{ padding: '5px 8px' }}>{formatarBps(p.in_bps)}</td>
                        <td style={{ padding: '5px 8px' }}>{formatarBps(p.out_bps)}</td>
                        <td style={{ padding: '5px 8px', color: p.erros ? '#fbbf24' : '#64748b' }}>{p.erros || 0}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </>}
          </>}
      </div>
    </div>
  )
}
