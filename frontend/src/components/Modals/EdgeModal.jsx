import { useState } from 'react'
import { X, Trash2, Save, ArrowRightLeft } from 'lucide-react'

export default function EdgeModal({ edge, onClose, onUpdate, onDelete, nodes }) {
  const [label, setLabel] = useState(edge.label || '')
  const [source, setSource] = useState(edge.source)
  const [target, setTarget] = useState(edge.target)

  const handleSave = () => {
    onUpdate(edge.id, label, source, target)
  }

  return (
    <div style={{ position: 'absolute', top: 0, left: 0, width: '100%', height: '100%', backgroundColor: 'rgba(0,0,0,0.6)', display: 'flex', justifyContent: 'center', alignItems: 'center', zIndex: 1000 }}>
      <div style={{ backgroundColor: '#1e293b', padding: '25px', borderRadius: '12px', width: '450px', border: '1px solid #334155' }}>
        
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '20px' }}>
          <h2 style={{ fontSize: '20px' }}>Editar Conexão</h2>
          <button onClick={onClose} style={{ background: 'transparent', border: 'none', color: '#94a3b8', cursor: 'pointer' }}><X size={20} /></button>
        </div>

        <div style={{ display: 'flex', flexDirection: 'column', gap: '15px' }}>
          <div>
            <label style={{ fontSize: '14px', color: '#94a3b8' }}>Rótulo da Conexão (Opcional)</label>
            <input type="text" value={label} onChange={(e) => setLabel(e.target.value)} placeholder="Ex: Fibra Óptica, Cabo Cat6..." style={{ width: '100%', padding: '10px', marginTop: '5px', borderRadius: '6px', border: '1px solid #334155', backgroundColor: '#0f172a', color: 'white' }} />
          </div>

          {/* Reconexão de Origem e Destino */}
          <div style={{ display: 'flex', alignItems: 'center', gap: '10px', marginTop: '10px', backgroundColor: '#0f172a', padding: '10px', borderRadius: '6px' }}>
            <div style={{ flex: 1 }}>
              <label style={{ fontSize: '12px', color: '#94a3b8' }}>Origem (Pai)</label>
              <select value={source} onChange={(e) => setSource(e.target.value)} style={{ width: '100%', padding: '8px', marginTop: '5px', borderRadius: '4px', border: '1px solid #334155', backgroundColor: '#1e293b', color: 'white' }}>
                {nodes.map(n => <option key={n.id} value={n.id}>{n.data.label}</option>)}
              </select>
            </div>
            
            <ArrowRightLeft size={20} color="#3b82f6" style={{ marginTop: '15px' }} />
            
            <div style={{ flex: 1 }}>
              <label style={{ fontSize: '12px', color: '#94a3b8' }}>Destino (Filho)</label>
              <select value={target} onChange={(e) => setTarget(e.target.value)} style={{ width: '100%', padding: '8px', marginTop: '5px', borderRadius: '4px', border: '1px solid #334155', backgroundColor: '#1e293b', color: 'white' }}>
                {nodes.map(n => <option key={n.id} value={n.id}>{n.data.label}</option>)}
              </select>
            </div>
          </div>
        </div>

        <div style={{ display: 'flex', justifyContent: 'space-between', marginTop: '30px' }}>
          <button onClick={() => onDelete(edge.id)} style={{ display: 'flex', alignItems: 'center', gap: '5px', padding: '10px', backgroundColor: '#ef4444', color: 'white', border: 'none', borderRadius: '6px', cursor: 'pointer' }}>
            <Trash2 size={18} /> Excluir Conexão
          </button>
          <button onClick={handleSave} style={{ display: 'flex', alignItems: 'center', gap: '5px', padding: '10px 20px', backgroundColor: '#3b82f6', color: 'white', border: 'none', borderRadius: '6px', cursor: 'pointer' }}>
            <Save size={18} /> Salvar
          </button>
        </div>

      </div>
    </div>
  )
}