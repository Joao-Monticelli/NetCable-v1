import { useState } from 'react'
import { useNavigate, useParams } from 'react-router-dom'
import { ArrowLeft, Save, Plus, Network, Settings } from 'lucide-react'
import NetworkMap from '../components/NetworkMap'
import AddEquipmentModal from '../components/Modals/AddEquipmentModal'

export default function Editor() {
  const navigate = useNavigate()
  const { projectId } = useParams()
  
  const [projectName, setProjectName] = useState(projectId === 'novo' ? 'Novo Mapa' : `Mapa #${projectId}`)
  const [isEditingName, setIsEditingName] = useState(false)
  
  // Estados para controlar o Modal de Adicionar e o Novo Equipamento
  const [isAddModalOpen, setIsAddModalOpen] = useState(false)
  const [newEquipment, setNewEquipment] = useState(null)

  const handleAddEquipment = (equipamento) => {
    setNewEquipment({ ...equipamento, id: Date.now() }) // ID único temporário
    setIsAddModalOpen(false)
  }

  return (
    <div style={{ display: 'flex', flexDirection: 'column', height: '100vh', backgroundColor: '#0f172a' }}>
      
      {/* BARRA DE FERRAMENTAS SUPERIOR */}
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', backgroundColor: '#1e293b', padding: '10px 20px', borderBottom: '1px solid #334155' }}>
        
        <div style={{ display: 'flex', alignItems: 'center', gap: '15px' }}>
          <button onClick={() => navigate('/projects')} style={{ background: 'transparent', border: 'none', color: '#94a3b8', cursor: 'pointer', display: 'flex', alignItems: 'center' }}>
            <ArrowLeft size={20} />
          </button>
          <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
            <Network size={20} color="#3b82f6" />
            {isEditingName ? (
              <input autoFocus type="text" value={projectName} onChange={(e) => setProjectName(e.target.value)} onBlur={() => setIsEditingName(false)} onKeyDown={(e) => e.key === 'Enter' && setIsEditingName(false)} style={{ backgroundColor: '#0f172a', color: 'white', border: '1px solid #3b82f6', borderRadius: '4px', padding: '4px 8px', fontSize: '16px', fontWeight: 'bold' }} />
            ) : (
              <span onClick={() => setIsEditingName(true)} style={{ fontWeight: 'bold', cursor: 'pointer', padding: '4px 8px', borderRadius: '4px', border: '1px solid transparent' }} title="Clique para editar o nome">
                {projectName} ✏️
              </span>
            )}
          </div>
        </div>

        <div style={{ display: 'flex', gap: '10px' }}>
          <button onClick={() => alert('Configurações do Projeto estarão disponíveis na Fase 2 (Backend).')} style={{ display: 'flex', alignItems: 'center', gap: '6px', padding: '8px 12px', backgroundColor: '#334155', color: 'white', border: 'none', borderRadius: '6px', cursor: 'pointer' }}>
            <Settings size={18} /> Configurações
          </button>
          <button onClick={() => setIsAddModalOpen(true)} style={{ display: 'flex', alignItems: 'center', gap: '6px', padding: '8px 16px', backgroundColor: '#3b82f6', color: 'white', border: 'none', borderRadius: '6px', cursor: 'pointer' }}>
            <Plus size={18} /> Adicionar Equipamento
          </button>
          <button onClick={() => alert('Salvamento no banco de dados será habilitado na Fase 2.')} style={{ display: 'flex', alignItems: 'center', gap: '6px', padding: '8px 16px', backgroundColor: '#10b981', color: 'white', border: 'none', borderRadius: '6px', cursor: 'pointer' }}>
            <Save size={18} /> Salvar Projeto
          </button>
        </div>
      </div>

      {/* ÁREA DO MAPA */}
      <div style={{ flex: 1 }}>
        <NetworkMap initialNodes={[]} initialEdges={[]} newEquipment={newEquipment} />
      </div>

      {/* MODAL DE ADICIONAR */}
      {isAddModalOpen && (
        <AddEquipmentModal 
          onClose={() => setIsAddModalOpen(false)} 
          onAdd={handleAddEquipment} 
        />
      )}

    </div>
  )
}