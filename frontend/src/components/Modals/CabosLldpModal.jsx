import { useEffect, useMemo, useState } from 'react'
import { X, Cable, Loader2, AlertTriangle, CheckCircle2, Plus } from 'lucide-react'
import { api } from '../../services/api'
import { t, useI18n } from '../../i18n'
import { portasDoEquipamento, listarPortas, ehPorta } from '../rack/rackUtils'

const botao = (cor) => ({ display: 'inline-flex', alignItems: 'center', gap: '6px', padding: '8px 12px', border: 0, borderRadius: '6px', background: cor, color: 'white', cursor: 'pointer', fontSize: '13px' })
const normal = (s) => (s || '').toLowerCase().replace(/\s+/g, '')
const PARECE_SFP = /sfp|^xe|^te|tengig|xgig|10g|25g|40g/i

// Port drawn on the map that matches an LLDP/CDP port name ("ge-0/0/3", "GigabitEthernet1/0/3", "port3", "SFP1").
export function portaDoMapa(node, modelos, nome) {
  if (!node || node.type !== 'rackDevice' || !nome) return null
  const portas = listarPortas(portasDoEquipamento(node.data, modelos.get(node.data.modeloId)))
  const exata = portas.find(p => normal(p.nome) === normal(nome))
  if (exata) return exata.id
  const numero = /(\d+)\D*$/.exec(nome)?.[1]
  if (!numero) return null
  const id = `${PARECE_SFP.test(nome.trim()) ? 's' : 'p'}:${Number(numero)}`
  return portas.some(p => p.id === id) ? id : null
}

// Asks the SNMPv3 switches of the map who is plugged into each port (LLDP/CDP) and offers the cables.
export default function CabosLldpModal({ projectId, nodes, edges, modelos = [], onAplicar, onClose }) {
  useI18n()
  const [resultado, setResultado] = useState(null)
  const [erro, setErro] = useState(null)
  const [marcados, setMarcados] = useState(new Set())
  const [novos, setNovos] = useState(new Set())
  const mapaModelos = useMemo(() => new Map(modelos.map(m => [m.id, m])), [modelos])
  const porId = useMemo(() => new Map(nodes.map(n => [n.id, n])), [nodes])

  useEffect(() => {
    api.descobrirCabos(projectId).then(r => {
      setResultado(r)
      setMarcados(new Set(r.sugestoes.map((s, i) => [s, i]).filter(([s]) => !ligados(s) && porId.has(s.origem_id) && porId.has(s.destino_id)).map(([, i]) => i)))
    }).catch(e => setErro(e.message))
  }, [projectId]) // eslint-disable-line react-hooks/exhaustive-deps

  // With the cables on the screen now (they may not be saved yet).
  function ligados(s) {
    return edges.some(e => (e.source === s.origem_id && e.target === s.destino_id) || (e.source === s.destino_id && e.target === s.origem_id))
  }
  const alternar = (conjunto, setConjunto, i) => setConjunto(new Set(conjunto.has(i) ? [...conjunto].filter(x => x !== i) : [...conjunto, i]))

  const aplicar = () => {
    const ocupadas = new Set(edges.flatMap(e => [ehPorta(e.sourceHandle) && `${e.source}|${e.sourceHandle}`, ehPorta(e.targetHandle) && `${e.target}|${e.targetHandle}`]).filter(Boolean))
    const cabos = []
    resultado.sugestoes.forEach((s, i) => {
      if (!marcados.has(i)) return
      const escolher = (id, nome, lado) => {
        const porta = portaDoMapa(porId.get(id), mapaModelos, nome)
        if (porta && !ocupadas.has(`${id}|${porta}`)) { ocupadas.add(`${id}|${porta}`); return [porta, true] }
        return [lado, false]
      }
      const [sourceHandle, origemNaPorta] = escolher(s.origem_id, s.porta_origem, 'right')
      const [targetHandle, destinoNaPorta] = escolher(s.destino_id, s.porta_destino, 'left')
      const rotulo = origemNaPorta && destinoNaPorta ? null : [s.porta_origem, s.porta_destino].filter(Boolean).join(' ↔ ') || null
      cabos.push({ id: `lldp_${Date.now()}_${i}`, source: s.origem_id, target: s.destino_id, label: rotulo, source_handle: sourceHandle, target_handle: targetHandle })
    })
    const equipamentos = resultado.fora_do_mapa.filter((_, i) => novos.has(i)).map(f => ({
      nome: f.nome || t('Vizinho de {nome}', { nome: f.visto_por }), ip: f.ip || 'Sem IP', tipo: f.plataforma ? 'Vizinho de rede' : 'PC',
      status: f.ip ? 'offline' : 'visual', monitorMode: f.ip ? 'ip' : 'visual',
    }))
    onAplicar(cabos, equipamentos)
  }

  const sugestoes = resultado?.sugestoes || []
  const total = marcados.size + novos.size
  const comErro = (resultado?.consultados || []).filter(c => c.erro)

  return (
    <div style={{ position: 'fixed', inset: 0, backgroundColor: 'rgba(0,0,0,0.65)', display: 'flex', justifyContent: 'center', alignItems: 'center', zIndex: 1100 }}>
      <div role="dialog" aria-label={t('Descobrir cabos (LLDP/CDP)')} style={{ backgroundColor: '#1e293b', padding: '22px', borderRadius: '12px', width: 'min(680px, 94vw)', maxHeight: '90vh', overflow: 'auto', border: '1px solid #334155', color: 'white', boxSizing: 'border-box' }}>
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '6px' }}>
          <h2 style={{ display: 'flex', alignItems: 'center', gap: '8px', fontSize: '19px' }}><Cable size={20} color="#38bdf8" /> {t('Descobrir cabos (LLDP/CDP)')}</h2>
          <button onClick={onClose} aria-label={t('Fechar')} style={{ background: 'transparent', border: 0, color: '#94a3b8', cursor: 'pointer' }}><X size={20} /></button>
        </div>
        <p style={{ fontSize: '13px', color: '#94a3b8', lineHeight: 1.5, marginBottom: '14px' }}>
          {t('Pergunta a cada equipamento do mapa monitorado por SNMPv3 quem está ligado em cada porta (LLDP e CDP) e sugere os cabos. Usa os equipamentos e credenciais salvos.')}
        </p>
        {erro ? <div role="alert" style={{ color: '#fca5a5', fontSize: '13px', display: 'flex', gap: '8px' }}><AlertTriangle size={16} /> {erro}</div>
          : !resultado ? <div style={{ color: '#94a3b8', fontSize: '13px', display: 'flex', alignItems: 'center', gap: '8px' }}><Loader2 size={16} className="spin" /> {t('Consultando os switches...')}</div> : (
          <div style={{ display: 'grid', gap: '14px' }}>
            <div style={{ fontSize: '12px', color: '#94a3b8' }}>
              {t('{n} equipamento(s) consultado(s); {v} vizinho(s) encontrados.', { n: resultado.consultados.length, v: resultado.consultados.reduce((s, c) => s + c.vizinhos, 0) })}
              {comErro.map(c => <div key={c.id} style={{ color: '#fca5a5', marginTop: '4px' }}><AlertTriangle size={12} /> {c.nome}: {c.erro}</div>)}
            </div>

            <section>
              <h3 style={{ fontSize: '14px', margin: '0 0 6px' }}>{t('Cabos encontrados')}</h3>
              {sugestoes.length === 0 ? <div style={{ fontSize: '13px', color: '#64748b' }}>{t('Nenhum cabo entre equipamentos deste mapa. Confira se o LLDP/CDP está ligado nos equipamentos.')}</div> : (
                <div style={{ display: 'grid', gap: '4px' }}>
                  {sugestoes.map((s, i) => {
                    const ja = ligados(s)
                    const ausente = !porId.has(s.origem_id) || !porId.has(s.destino_id)
                    return (
                      <label key={i} style={{ display: 'flex', alignItems: 'center', gap: '8px', padding: '8px 10px', background: '#0f172a', borderRadius: '6px', fontSize: '13px', opacity: ja || ausente ? 0.6 : 1 }}>
                        <input type="checkbox" disabled={ausente} checked={marcados.has(i)} onChange={() => alternar(marcados, setMarcados, i)} />
                        <span style={{ flex: 1 }}>
                          <strong>{s.origem}</strong>{s.porta_origem && <span style={{ color: '#94a3b8' }}> ({s.porta_origem})</span>}
                          {' ↔ '}
                          <strong>{s.destino}</strong>{s.porta_destino && <span style={{ color: '#94a3b8' }}> ({s.porta_destino})</span>}
                        </span>
                        <span style={{ fontSize: '11px', color: '#64748b' }}>{s.protocolo}</span>
                        {ja && <span style={{ fontSize: '11px', color: '#0ca30c', display: 'inline-flex', alignItems: 'center', gap: '3px' }}><CheckCircle2 size={12} /> {t('já ligado')}</span>}
                      </label>
                    )
                  })}
                </div>
              )}
            </section>

            {resultado.fora_do_mapa.length > 0 && (
              <section>
                <h3 style={{ fontSize: '14px', margin: '0 0 6px' }}>{t('Vizinhos que não estão no mapa')}</h3>
                <div style={{ display: 'grid', gap: '4px' }}>
                  {resultado.fora_do_mapa.map((f, i) => (
                    <label key={i} style={{ display: 'flex', alignItems: 'center', gap: '8px', padding: '8px 10px', background: '#0f172a', borderRadius: '6px', fontSize: '13px' }}>
                      <input type="checkbox" checked={novos.has(i)} onChange={() => alternar(novos, setNovos, i)} aria-label={t('Adicionar {nome} ao mapa', { nome: f.nome || '?' })} />
                      <span style={{ flex: 1 }}>
                        <strong>{f.nome || t('sem nome')}</strong>{f.ip && <span style={{ color: '#94a3b8' }}> · {f.ip}</span>}
                        {f.plataforma && <span style={{ color: '#64748b' }}> · {f.plataforma}</span>}
                        <div style={{ fontSize: '11px', color: '#64748b' }}>{t('Visto por {quem} na porta {porta}', { quem: f.visto_por, porta: f.porta_local || '?' })}</div>
                      </span>
                      <span style={{ fontSize: '11px', color: '#64748b' }}>{f.protocolo}</span>
                    </label>
                  ))}
                </div>
                <div style={{ fontSize: '11px', color: '#64748b', marginTop: '6px' }}>{t('Depois de salvar o mapa, rode de novo para ligar os cabos dos equipamentos adicionados.')}</div>
              </section>
            )}

            <div style={{ display: 'flex', justifyContent: 'flex-end', gap: '8px' }}>
              <button onClick={onClose} style={botao('#334155')}>{t('Cancelar')}</button>
              <button onClick={aplicar} disabled={!total} style={{ ...botao(total ? '#0284c7' : '#334155'), cursor: total ? 'pointer' : 'not-allowed' }}><Plus size={14} /> {t('Adicionar ao mapa ({n})', { n: total })}</button>
            </div>
          </div>
        )}
      </div>
    </div>
  )
}
