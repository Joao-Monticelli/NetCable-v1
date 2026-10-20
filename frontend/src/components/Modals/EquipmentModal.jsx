import { useState } from 'react'
import { X, Trash2, Save, Maximize, Minimize } from 'lucide-react'

export default function EquipmentModal({ node, onClose, onUpdate, onDelete }) {
  const [nome, setNome] = useState(node.data.label || '')
  const [ip, setIp] = useState(node.data.ip || '')
  const [tipo, setTipo] = useState(node.data.tipo || 'Roteador')

  const handleSave = () => {
    onUpdate(node.id, { label: nome, ip, tipo })
  }

  // Função para restaurar o tamanho original
  const handleResetSize = () => {
    // Acessa a referência do elemento pai do React Flow (nó) e altera o CSS
    const nodeElement = document.querySelector(`.react-flow__node[data-id="${node.id}"]`)
    if (nodeElement) {
      nodeElement.style.width = '200px'
      nodeElement.style.height = '80px'
    }
  }

  return (
    <div style={{ position: 'absolute', top: 0, left: 0, width: '100%', height: '100%', backgroundColor: 'rgba(0,0,0,0.6)', display: 'flex', justifyContent: 'center', alignItems: 'center', zIndex: 1000 }}>
      <div style={{ backgroundColor: '#1e293b', padding: '25px', borderRadius: '12px', width: '400px', border: '1px solid #334155' }}>
        
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '20px' }}>
          <h2 style={{ fontSize: '20px' }}>Editar Equipamento</h2>
          <button onClick={onClose} style={{ background: 'transparent', border: 'none', color: '#94a3b8', cursor: 'pointer' }}><X size={20} /></button>
        </div>

        <div style={{ display: 'flex', flexDirection: 'column', gap: '15px' }}>
          <div>
            <label style={{ fontSize: '14px', color: '#94a3b8' }}>Nome do Equipamento</label>
            <input type="text" value={nome} onChange={(e) => setNome(e.target.value)} style={{ width: '100%', padding: '10px', marginTop: '5px', borderRadius: '6px', border: '1px solid #334155', backgroundColor: '#0f172a', color: 'white' }} />
          </div>
          
          <div>
            <label style={{ fontSize: '14px', color: '#94a3b8' }}>Endereço IP</label>
            <input type="text" value={ip} onChange={(e) => setIp(e.target.value)} placeholder="Ex: 192.168.0.1" style={{ width: '100%', padding: '10px', marginTop: '5px', borderRadius: '6px', border: '1px solid #334155', backgroundColor: '#0f172a', color: 'white' }} />
          </div>

          <div>
            <label style={{ fontSize: '14px', color: '#94a3b8' }}>Tipo</label>
            <select value={tipo} onChange={(e) => setTipo(e.target.value)} style={{ width: '100%', padding: '10px', marginTop: '5px', borderRadius: '6px', border: '1px solid #334155', backgroundColor: '#0f172a', color: 'white' }}>
              <option value="Roteador">Roteador</option>
              <option value="Switch Gerenciável">Switch Gerenciável</option>
              <option value="Switch Não Gerenciável">Switch Não Gerenciável</option>
              <option value="Firewall">Firewall</option>
              <option value="Servidor">Servidor</option>
              <option value="PC">PC</option>
            </select>
          </div>
          
          {/* Botão de Redimensionamento */}
          <div style={{ marginTop: '10px', padding: '10px', backgroundColor: '#0f172a', borderRadius: '6px', border: '1px solid #334155' }}>
            <span style={{ fontSize: '13px', color: '#94a3b8', display: 'block', marginBottom: '8px' }}>
              <Maximize size={14} style={{ display: 'inline', marginRight: '5px' }} /> 
              Dica: Você pode arrastar as bordas do equipamento no mapa para redimensionar.
            </span>
            <button onClick={handleResetSize} style={{ display: 'flex', alignItems: 'center', gap: '5px', padding: '8px 12px', backgroundColor: '#334155', color: 'white', border: 'none', borderRadius: '6px', cursor: 'pointer', fontSize: '12px' }}>
              <Minimize size={14} /> Restaurar Tamanho Padrão
            </button>
          </div>
        </div>

        <div style={{ display: 'flex', justifyContent: 'space-between', marginTop: '30px' }}>
          <button onClick={() => onDelete(node.id)} style={{ display: 'flex', alignItems: 'center', gap: '5px', padding: '10px', backgroundColor: '#ef4444', color: 'white', border: 'none', borderRadius: '6px', cursor: 'pointer' }}>
            <Trash2 size={18} /> Excluir
          </button>
          <button onClick={handleSave} style={{ display: 'flex', alignItems: 'center', gap: '5px', padding: '10px 20px', backgroundColor: '#3b82f6', color: 'white', border: 'none', borderRadius: '6px', cursor: 'pointer' }}>
            <Save size={18} /> Salvar Alterações
          </button>
        </div>

      </div>
    </div>
  )
}