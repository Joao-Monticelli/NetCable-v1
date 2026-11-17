import { useState } from 'react'
import { X, Trash2, Save, ArrowRightLeft, Cable } from 'lucide-react'
import { portasDoEquipamento, listarPortas, ehPorta } from '../rack/rackUtils'

const seletor = { width: '100%', padding: '8px', marginTop: '5px', borderRadius: '4px', border: '1px solid #334155', backgroundColor: '#1e293b', color: 'white' }

// Portas disponíveis num nó (só equipamentos montados em rack têm portas desenhadas).
function portasDoNo(node, modelos) {
  if (node?.type !== 'rackDevice') return []
  return listarPortas(portasDoEquipamento(node.data, modelos.get(node.data.modeloId)))
}

export default function EdgeModal({ edge, onClose, onUpdate, onDelete, nodes, edges = [], modelos = new Map() }) {
  const [label, setLabel] = useState(edge.label || '')
  const [source, setSource] = useState(edge.source)
  const [target, setTarget] = useState(edge.target)
  const [sourceHandle, setSourceHandle] = useState(edge.sourceHandle || 'right')
  const [targetHandle, setTargetHandle] = useState(edge.targetHandle || 'left')

  const noOrigem = nodes.find(n => n.id === source)
  const noDestino = nodes.find(n => n.id === target)
  const portasOrigem = portasDoNo(noOrigem, modelos)
  const portasDestino = portasDoNo(noDestino, modelos)

  // Portas já usadas por outros cabos (não pode ligar dois cabos na mesma porta).
  const usadas = (nodeId) => new Set(edges.filter(e => e.id !== edge.id).flatMap(e => [
    e.source === nodeId ? e.sourceHandle : null, e.target === nodeId ? e.targetHandle : null,
  ]).filter(ehPorta))
  const usadasOrigem = usadas(source)
  const usadasDestino = usadas(target)

  const trocarOrigem = (id) => { setSource(id); setSourceHandle('right') }
  const trocarDestino = (id) => { setTarget(id); setTargetHandle('left') }

  const SeletorPorta = ({ portas, valor, onChange, ocupadas, lado, rotulo }) => portas.length === 0 ? null : (
    <label style={{ fontSize: '12px', color: '#94a3b8', display: 'block', marginTop: '8px' }}>{rotulo}
      <select aria-label={rotulo} value={ehPorta(valor) ? valor : ''} onChange={(e) => onChange(e.target.value || lado)} style={seletor}>
        <option value="">Lateral do equipamento (sem porta)</option>
        {portas.map(p => <option key={p.id} value={p.id} disabled={ocupadas.has(p.id)}>{p.nome}{ocupadas.has(p.id) ? ' (em uso)' : ''}</option>)}
      </select>
    </label>
  )

  return (
    <div style={{ position: 'absolute', inset: 0, backgroundColor: 'rgba(0,0,0,0.6)', display: 'flex', justifyContent: 'center', alignItems: 'center', zIndex: 1000 }}>
      <div style={{ backgroundColor: '#1e293b', padding: '25px', borderRadius: '12px', width: '480px', border: '1px solid #334155' }}>
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '20px' }}>
          <h2 style={{ fontSize: '20px', display: 'flex', alignItems: 'center', gap: '8px' }}><Cable size={20} color="#3b82f6" /> Editar Conexão</h2>
          <button onClick={onClose} style={{ background: 'transparent', border: 'none', color: '#94a3b8', cursor: 'pointer' }}><X size={20} /></button>
        </div>

        <div style={{ display: 'flex', flexDirection: 'column', gap: '15px' }}>
          <div>
            <label style={{ fontSize: '14px', color: '#94a3b8' }}>Rótulo da Conexão (Opcional)</label>
            <input type="text" value={label} onChange={(e) => setLabel(e.target.value)} placeholder="Ex: Fibra Óptica, Cabo Cat6, VLAN 10..." style={{ width: '100%', padding: '10px', marginTop: '5px', borderRadius: '6px', border: '1px solid #334155', backgroundColor: '#0f172a', color: 'white' }} />
          </div>

          <div style={{ display: 'flex', alignItems: 'flex-start', gap: '10px', backgroundColor: '#0f172a', padding: '12px', borderRadius: '6px' }}>
            <div style={{ flex: 1 }}>
              <label style={{ fontSize: '12px', color: '#94a3b8' }}>Origem</label>
              <select aria-label="Origem" value={source} onChange={(e) => trocarOrigem(e.target.value)} style={seletor}>
                {nodes.filter(n => n.type !== 'rack').map(n => <option key={n.id} value={n.id}>{n.data.label}</option>)}
              </select>
              <SeletorPorta portas={portasOrigem} valor={sourceHandle} onChange={setSourceHandle} ocupadas={usadasOrigem} lado="right" rotulo="Porta na origem" />
            </div>
            <ArrowRightLeft size={20} color="#3b82f6" style={{ marginTop: '28px' }} />
            <div style={{ flex: 1 }}>
              <label style={{ fontSize: '12px', color: '#94a3b8' }}>Destino</label>
              <select aria-label="Destino" value={target} onChange={(e) => trocarDestino(e.target.value)} style={seletor}>
                {nodes.filter(n => n.type !== 'rack').map(n => <option key={n.id} value={n.id}>{n.data.label}</option>)}
              </select>
              <SeletorPorta portas={portasDestino} valor={targetHandle} onChange={setTargetHandle} ocupadas={usadasDestino} lado="left" rotulo="Porta no destino" />
            </div>
          </div>
          {(portasOrigem.length > 0 || portasDestino.length > 0) && (
            <span style={{ fontSize: '12px', color: '#64748b' }}>Dica: você também pode arrastar direto de uma porta para outra no rack.</span>
          )}
        </div>

        <div style={{ display: 'flex', justifyContent: 'space-between', marginTop: '30px' }}>
          <button onClick={() => onDelete(edge.id)} style={{ display: 'flex', alignItems: 'center', gap: '5px', padding: '10px', backgroundColor: '#ef4444', color: 'white', border: 'none', borderRadius: '6px', cursor: 'pointer' }}>
            <Trash2 size={18} /> Excluir Conexão
          </button>
          <button onClick={() => onUpdate(edge.id, label, source, target, sourceHandle, targetHandle)} style={{ display: 'flex', alignItems: 'center', gap: '5px', padding: '10px 20px', backgroundColor: '#3b82f6', color: 'white', border: 'none', borderRadius: '6px', cursor: 'pointer' }}>
            <Save size={18} /> Salvar
          </button>
        </div>
      </div>
    </div>
  )
}
