import { useEffect, useMemo, useRef, useState } from 'react'
import { X, Radar, Loader2, Plus, Square } from 'lucide-react'
import toast from 'react-hot-toast'
import { api } from '../../services/api'
import { TIPOS } from '../rack/rackUtils'
import { t, useI18n } from '../../i18n'

const campo = { padding: '9px', borderRadius: '6px', border: '1px solid #334155', backgroundColor: '#0f172a', color: 'white' }
const botao = { display: 'flex', alignItems: 'center', gap: '6px', padding: '9px 14px', border: 0, borderRadius: '6px', cursor: 'pointer', color: 'white' }
const NOMES_PORTA = { 22: 'SSH', 53: 'DNS', 80: 'HTTP', 139: 'SMB', 443: 'HTTPS', 445: 'SMB', 554: 'RTSP', 3389: 'RDP', 5000: 'DSM', 5001: 'DSM', 8006: 'Proxmox', 8080: 'HTTP', 9100: 'Print' }

// Sugere a faixa pela rede mais comum entre os IPs já no mapa (ex.: 192.168.1.0/24).
function faixaSugerida(nodes) {
  const contagem = new Map()
  for (const n of nodes) {
    const m = /^(\d+\.\d+\.\d+)\.\d+$/.exec(n.data?.ip || '')
    if (m) contagem.set(m[1], (contagem.get(m[1]) || 0) + 1)
  }
  const [melhor] = [...contagem.entries()].sort((a, b) => b[1] - a[1])
  return melhor ? `${melhor[0]}.0/24` : '192.168.1.0/24'
}

export default function DescobertaModal({ nodes = [], onClose, onAdicionar }) {
  useI18n()
  const [faixa, setFaixa] = useState(() => faixaSugerida(nodes))
  const [job, setJob] = useState(null)
  const [escolhas, setEscolhas] = useState({}) // ip -> { marcado, nome, tipo }
  const timer = useRef(null)
  const ipsNoMapa = useMemo(() => new Set(nodes.map(n => n.data?.ip).filter(Boolean)), [nodes])
  const rodando = job?.status === 'rodando'

  useEffect(() => () => clearTimeout(timer.current), [])

  const acompanhar = (id) => {
    timer.current = setTimeout(async () => {
      try {
        const j = await api.statusDescoberta(id)
        setJob(j)
        if (j.status === 'rodando') acompanhar(id)
        else prepararEscolhas(j)
      } catch (err) { toast.error(err.message) }
    }, 700)
  }

  const prepararEscolhas = (j) => {
    const novas = {}
    for (const r of j.resultados) {
      const jaExiste = ipsNoMapa.has(r.ip) || r.no_mapa.length > 0
      novas[r.ip] = { marcado: !jaExiste, nome: r.nome ? r.nome.split('.')[0] : r.ip, tipo: r.tipo_sugerido }
    }
    setEscolhas(novas)
  }

  const varrer = async (e) => {
    e?.preventDefault()
    clearTimeout(timer.current)
    setEscolhas({})
    try {
      const j = await api.iniciarDescoberta(faixa)
      setJob(j)
      acompanhar(j.id)
    } catch (err) { toast.error(err.message, { duration: 7000 }) }
  }

  const parar = async () => { try { setJob(await api.cancelarDescoberta(job.id)) } catch (err) { toast.error(err.message) } }

  const marcados = job ? job.resultados.filter(r => escolhas[r.ip]?.marcado) : []
  const adicionar = () => {
    onAdicionar(marcados.map(r => ({
      nome: escolhas[r.ip].nome || r.ip, ip: r.ip, tipo: escolhas[r.ip].tipo, status: 'offline', monitorMode: 'ip', notificar: true,
    })))
  }
  const alterar = (ip, k, v) => setEscolhas(s => ({ ...s, [ip]: { ...s[ip], [k]: v } }))
  const marcarTodos = (v) => setEscolhas(s => Object.fromEntries(Object.entries(s).map(([ip, e]) => [ip, { ...e, marcado: v }])))
  const progresso = job ? Math.round((job.verificados / Math.max(1, job.total)) * 100) : 0

  return (
    <div style={{ position: 'fixed', inset: 0, backgroundColor: 'rgba(0,0,0,0.65)', display: 'flex', justifyContent: 'center', alignItems: 'center', zIndex: 1100 }}>
      <div role="dialog" aria-label={t('Descobrir equipamentos na rede')} style={{ backgroundColor: '#1e293b', padding: '25px', borderRadius: '12px', width: 'min(820px, 96vw)', maxHeight: '92vh', display: 'flex', flexDirection: 'column', border: '1px solid #334155', color: 'white' }}>
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '6px' }}>
          <h2 style={{ display: 'flex', alignItems: 'center', gap: '8px', fontSize: '20px' }}><Radar size={20} color="#22d3ee" /> {t('Descobrir equipamentos na rede')}</h2>
          <button onClick={onClose} aria-label={t('Fechar')} style={{ background: 'transparent', border: 0, color: '#94a3b8', cursor: 'pointer' }}><X size={20} /></button>
        </div>
        <p style={{ color: '#94a3b8', fontSize: '13px', marginBottom: '12px', lineHeight: 1.45 }}>
          {t('O servidor do NetCable testa cada endereço da faixa (ping e portas comuns) e lista quem respondeu. Escolha o que entra no mapa.')}
        </p>
        <form onSubmit={varrer} style={{ display: 'flex', gap: '8px', marginBottom: '12px' }}>
          <input aria-label={t('Faixa de IPs')} value={faixa} onChange={e => setFaixa(e.target.value)} placeholder="192.168.1.0/24" style={{ ...campo, flex: 1, fontFamily: 'monospace' }} disabled={rodando} />
          {rodando
            ? <button type="button" onClick={parar} style={{ ...botao, background: '#7f1d1d' }}><Square size={15} /> {t('Parar')}</button>
            : <button type="submit" style={{ ...botao, background: '#0891b2' }}><Radar size={15} /> {t('Varrer')}</button>}
        </form>

        {job && (
          <div style={{ marginBottom: '10px' }}>
            <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: '12px', color: '#94a3b8', marginBottom: '4px' }}>
              <span>{rodando
                ? (job.fase === 'vivos' ? t('Procurando equipamentos… {v} de {n}', { v: job.verificados, n: job.total }) : t('Coletando detalhes dos que responderam…'))
                : job.status === 'erro' ? t('Falha na varredura: {erro}', { erro: job.erro }) : t('{n} equipamento(s) encontrado(s) em {s} s', { n: job.resultados.length, s: job.duracao_s })}</span>
              {rodando && <Loader2 size={14} className="spin" />}
            </div>
            <div style={{ height: 6, background: '#0f172a', borderRadius: 3, overflow: 'hidden' }}>
              <div style={{ width: `${rodando && job.fase !== 'vivos' ? 100 : progresso}%`, height: '100%', background: '#22d3ee', transition: 'width .3s' }} />
            </div>
          </div>
        )}

        {job && !rodando && job.resultados.length > 0 && <>
          <div style={{ overflow: 'auto', flex: 1, border: '1px solid #334155', borderRadius: '8px' }}>
            <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: '13px' }}>
              <thead style={{ position: 'sticky', top: 0, background: '#0f172a', color: '#94a3b8', textAlign: 'left' }}>
                <tr>
                  <th style={{ padding: '8px' }}><input type="checkbox" aria-label={t('Marcar todos')} checked={marcados.length === job.resultados.length} onChange={e => marcarTodos(e.target.checked)} /></th>
                  <th style={{ padding: '8px' }}>{t('IP')}</th><th style={{ padding: '8px' }}>{t('Nome')}</th><th style={{ padding: '8px' }}>{t('Tipo')}</th><th style={{ padding: '8px' }}>{t('Portas abertas')}</th>
                </tr>
              </thead>
              <tbody>
                {job.resultados.map(r => {
                  const e = escolhas[r.ip] || {}
                  const jaExiste = ipsNoMapa.has(r.ip) || r.no_mapa.length > 0
                  return (
                    <tr key={r.ip} style={{ borderTop: '1px solid #1e293b', opacity: e.marcado ? 1 : 0.6 }}>
                      <td style={{ padding: '6px 8px' }}><input type="checkbox" aria-label={r.ip} checked={!!e.marcado} onChange={ev => alterar(r.ip, 'marcado', ev.target.checked)} /></td>
                      <td style={{ padding: '6px 8px', fontFamily: 'monospace', whiteSpace: 'nowrap' }}>
                        {r.ip}
                        {jaExiste && <div style={{ fontSize: '11px', color: '#f59e0b', fontFamily: 'inherit' }}>{ipsNoMapa.has(r.ip) ? t('já está neste mapa') : t('já está em: {mapas}', { mapas: r.no_mapa.join(', ') })}</div>}
                        {r.mac && <div style={{ fontSize: '11px', color: '#64748b' }}>{r.mac}</div>}
                      </td>
                      <td style={{ padding: '6px 8px' }}><input aria-label={t('Nome')} value={e.nome || ''} onChange={ev => alterar(r.ip, 'nome', ev.target.value)} style={{ ...campo, padding: '6px', width: '100%' }} /></td>
                      <td style={{ padding: '6px 8px' }}>
                        <select aria-label={t('Tipo')} value={e.tipo || 'Servidor'} onChange={ev => alterar(r.ip, 'tipo', ev.target.value)} style={{ ...campo, padding: '6px' }}>
                          {[...new Set([...TIPOS.filter(tp => tp !== 'Patch Panel' && tp !== 'Organizador de Cabos'), e.tipo].filter(Boolean))].map(tp => <option key={tp} value={tp}>{t(tp)}</option>)}
                        </select>
                      </td>
                      <td style={{ padding: '6px 8px', color: '#94a3b8' }}>
                        <div style={{ display: 'flex', flexWrap: 'wrap', gap: '4px' }}>
                          {r.portas.length ? r.portas.map(p => <span key={p} title={String(p)} style={{ fontSize: '11px', padding: '1px 6px', borderRadius: 8, background: '#334155', color: '#e2e8f0' }}>{NOMES_PORTA[p] || p}</span>) : <span style={{ fontSize: '11px' }}>{t('só ping')}</span>}
                        </div>
                      </td>
                    </tr>
                  )
                })}
              </tbody>
            </table>
          </div>
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginTop: '12px' }}>
            <span style={{ fontSize: '12px', color: '#64748b' }}>{t('Dica: depois de adicionar, ligue os cabos e use "calcular uplinks" para ter alertas por dependência.')}</span>
            <button onClick={adicionar} disabled={!marcados.length} style={{ ...botao, background: marcados.length ? '#3b82f6' : '#475569', cursor: marcados.length ? 'pointer' : 'not-allowed' }}>
              <Plus size={15} /> {t('Adicionar {n} ao mapa', { n: marcados.length })}
            </button>
          </div>
        </>}
        {job && !rodando && job.status !== 'erro' && job.resultados.length === 0 && (
          <div style={{ color: '#94a3b8', fontSize: '13px' }}>{t('Nenhum equipamento respondeu nesta faixa. Confira se o NetCable está na mesma rede (no Docker, a rede do container precisa alcançar a LAN).')}</div>
        )}
      </div>
    </div>
  )
}
