import { useEffect, useState } from 'react'
import { X, Boxes, Plus, Pencil, Trash2, Save, Loader2 } from 'lucide-react'
import toast from 'react-hot-toast'
import { api } from '../../services/api'
import { TIPOS, TIPOS_PASSIVOS, alturaPadrao, portasDoEquipamento } from '../rack/rackUtils'
import { FrentePreview } from '../rack/RackNodes'
import '../rack/rack.css'

const VAZIO = { nome: '', fabricante: '', tipo: 'Switch Gerenciável', altura_u: 1, portas_rj45: 24, portas_sfp: 4, prefixo_porta: '' }
const campo = { width: '100%', padding: '8px', marginTop: '4px', borderRadius: '6px', border: '1px solid #334155', backgroundColor: '#0f172a', color: 'white', fontSize: '13px', boxSizing: 'border-box' }
const rotulo = { fontSize: '12px', color: '#94a3b8' }
const botao = { display: 'inline-flex', alignItems: 'center', gap: '5px', padding: '7px 12px', border: 0, borderRadius: '6px', cursor: 'pointer', color: 'white', fontSize: '13px' }

// Biblioteca de modelos da equipe: o usuário define tipo, altura e portas reais
// do equipamento (ex.: Grandstream GWN7003 = firewall 1U com 4 RJ45 + 2 SFP).
export default function ModelosModal({ onClose, onChange, podeEditar = true }) {
  const [modelos, setModelos] = useState(null)
  const [form, setForm] = useState(null) // null = lista; objeto = criando/editando
  const [salvando, setSalvando] = useState(false)

  const carregar = () => api.listarModelos().then(lista => { setModelos(lista); onChange?.(lista) }).catch(e => { toast.error(e.message); setModelos([]) })
  useEffect(() => { carregar() }, [])

  const set = (k, numero = false) => (e) => setForm({ ...form, [k]: numero ? Number(e.target.value) : e.target.value })
  const escolherTipo = (e) => {
    const tipo = e.target.value
    // Sugere as portas padrão do tipo ao trocar (o usuário ajusta depois).
    const altura = alturaPadrao(tipo)
    const padrao = portasDoEquipamento({ tipo, alturaU: altura }, null)
    setForm({ ...form, tipo, altura_u: altura, portas_rj45: padrao.rj45, portas_sfp: padrao.sfp })
  }

  const salvar = async (e) => {
    e.preventDefault()
    setSalvando(true)
    try {
      if (form.id) await api.atualizarModelo(form.id, form)
      else await api.criarModelo(form)
      toast.success(`Modelo "${form.nome}" salvo.`)
      setForm(null)
      carregar()
    } catch (err) { toast.error(err.message) } finally { setSalvando(false) }
  }

  const excluir = async (m) => {
    if (!window.confirm(`Excluir o modelo "${m.nome}"?`)) return
    try { await api.excluirModelo(m.id); toast.success('Modelo excluído.'); carregar() } catch (err) { toast.error(err.message, { duration: 6000 }) }
  }

  const resumoPortas = (m) => [m.portas_rj45 && `${m.portas_rj45}× RJ45`, m.portas_sfp && `${m.portas_sfp}× SFP`].filter(Boolean).join(' + ') || 'sem portas'

  return (
    <div style={{ position: 'fixed', inset: 0, backgroundColor: 'rgba(0,0,0,0.65)', display: 'flex', justifyContent: 'center', alignItems: 'center', zIndex: 1100 }}>
      <div style={{ backgroundColor: '#1e293b', padding: '25px', borderRadius: '12px', width: 'min(760px, 94vw)', maxHeight: '90vh', overflowY: 'auto', border: '1px solid #334155', color: 'white' }}>
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '6px' }}>
          <h2 style={{ display: 'flex', alignItems: 'center', gap: '8px', fontSize: '20px' }}><Boxes size={20} color="#3b82f6" /> Modelos de equipamento</h2>
          <button onClick={onClose} style={{ background: 'transparent', border: 0, color: '#94a3b8', cursor: 'pointer' }}><X size={20} /></button>
        </div>
        <p style={{ color: '#94a3b8', fontSize: '13px', marginBottom: '16px' }}>
          Cadastre os equipamentos reais da sua rede (portas, altura em U). Ao adicionar um equipamento, escolha o modelo e a frente no rack é desenhada com exatamente essas portas.
        </p>

        {form ? (
          <form onSubmit={salvar} style={{ display: 'grid', gap: '12px' }}>
            <div style={{ display: 'grid', gridTemplateColumns: '2fr 1fr', gap: '10px' }}>
              <label style={rotulo}>Nome do modelo<input required value={form.nome} onChange={set('nome')} placeholder="Ex: Grandstream GWN7003" style={campo} /></label>
              <label style={rotulo}>Fabricante<input value={form.fabricante || ''} onChange={set('fabricante')} placeholder="Ex: Grandstream" style={campo} /></label>
            </div>
            <div style={{ display: 'grid', gridTemplateColumns: '1.6fr 0.8fr 0.8fr 0.8fr 1fr', gap: '10px' }}>
              <label style={rotulo}>Tipo
                <select aria-label="Tipo do modelo" value={form.tipo} onChange={escolherTipo} style={campo}>
                  {TIPOS.map(t => <option key={t} value={t}>{t}</option>)}
                </select>
              </label>
              <label style={rotulo}>Altura
                <select aria-label="Altura do modelo" value={form.altura_u} onChange={set('altura_u', true)} style={campo}>
                  {[1, 2, 3, 4, 5, 6, 8].map(a => <option key={a} value={a}>{a}U</option>)}
                </select>
              </label>
              <label style={rotulo}>Portas RJ45<input aria-label="Portas RJ45" type="number" min="0" max={48 * form.altura_u} value={form.portas_rj45} onChange={set('portas_rj45', true)} style={campo} /></label>
              <label style={rotulo}>Portas SFP<input aria-label="Portas SFP" type="number" min="0" max="8" value={form.portas_sfp} onChange={set('portas_sfp', true)} style={campo} /></label>
              <label style={rotulo}>Nome das portas<input aria-label="Prefixo das portas" value={form.prefixo_porta} onChange={set('prefixo_porta')} placeholder="ex: eth, Gi1/0/" maxLength={12} style={campo} /></label>
            </div>
            <span style={{ fontSize: '11px', color: '#64748b', marginTop: '-6px' }}>
              Nome das portas: com "eth" as portas viram eth1, eth2…; vazio fica "Porta 1, Porta 2…". As SFP são SFP1, SFP2…
            </span>

            <div style={{ background: '#0b1120', border: '1px solid #334155', borderRadius: '8px', padding: '14px', display: 'flex', flexDirection: 'column', alignItems: 'center', gap: '8px' }}>
              <span style={{ fontSize: '11px', color: '#64748b', alignSelf: 'flex-start' }}>Prévia no rack</span>
              <FrentePreview modelo={form} data={{
                label: form.nome || 'Novo modelo', tipo: form.tipo, alturaU: form.altura_u,
                ip: TIPOS_PASSIVOS.includes(form.tipo) ? 'Sem IP' : '192.168.0.1',
                status: TIPOS_PASSIVOS.includes(form.tipo) ? 'visual' : 'online', pingTime: 1.2,
              }} />
            </div>

            <div style={{ display: 'flex', justifyContent: 'flex-end', gap: '8px' }}>
              <button type="button" onClick={() => setForm(null)} style={{ ...botao, background: 'transparent', border: '1px solid #334155', color: '#94a3b8' }}>Cancelar</button>
              <button type="submit" disabled={salvando} style={{ ...botao, background: '#3b82f6' }}>{salvando ? <Loader2 size={14} className="spin" /> : <Save size={14} />} Salvar modelo</button>
            </div>
          </form>
        ) : (
          <>
            {podeEditar && <button onClick={() => setForm({ ...VAZIO })} style={{ ...botao, background: '#10b981', marginBottom: '14px' }}><Plus size={15} /> Novo modelo</button>}
            {modelos === null ? <div style={{ color: '#94a3b8' }}><Loader2 size={16} className="spin" /> Carregando...</div>
              : modelos.length === 0 ? <div style={{ color: '#94a3b8', fontSize: '14px' }}>Nenhum modelo cadastrado ainda.</div>
              : (
                <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: '13px' }}>
                  <thead><tr style={{ color: '#94a3b8', textAlign: 'left' }}>
                    <th style={{ padding: '6px', fontWeight: 'normal' }}>Modelo</th><th style={{ padding: '6px', fontWeight: 'normal' }}>Tipo</th>
                    <th style={{ padding: '6px', fontWeight: 'normal' }}>Altura</th><th style={{ padding: '6px', fontWeight: 'normal' }}>Portas</th><th></th>
                  </tr></thead>
                  <tbody>{modelos.map(m => (
                    <tr key={m.id} style={{ borderTop: '1px solid #334155' }}>
                      <td style={{ padding: '6px' }}><b>{m.nome}</b>{m.fabricante && <div style={{ color: '#64748b', fontSize: '11px' }}>{m.fabricante}</div>}</td>
                      <td style={{ padding: '6px', color: '#cbd5e1' }}>{m.tipo}</td>
                      <td style={{ padding: '6px', color: '#cbd5e1' }}>{m.altura_u}U</td>
                      <td style={{ padding: '6px', color: '#cbd5e1' }}>{resumoPortas(m)}{m.prefixo_porta && <span style={{ color: '#64748b' }}> ({m.prefixo_porta}1…)</span>}</td>
                      <td style={{ padding: '6px', textAlign: 'right', whiteSpace: 'nowrap' }}>
                        {podeEditar && <>
                          <button onClick={() => setForm({ ...m, fabricante: m.fabricante || '' })} title="Editar" style={{ ...botao, background: '#334155', padding: '6px 8px', marginRight: '6px' }}><Pencil size={13} /></button>
                          <button onClick={() => excluir(m)} title="Excluir" style={{ ...botao, background: '#ef4444', padding: '6px 8px' }}><Trash2 size={13} /></button>
                        </>}
                      </td>
                    </tr>
                  ))}</tbody>
                </table>
              )}
          </>
        )}
      </div>
    </div>
  )
}
