import { useNavigate } from 'react-router-dom'
import { FolderPlus, Folder, LogOut, Network } from 'lucide-react'

export default function Projects() {
  const navigate = useNavigate()
  
  // Projetos simulados (depois virão do banco de dados)
  const projetos = [
    { id: 1, nome: 'Rede Escritório Matriz', data: 'Hoje' },
    { id: 2, nome: 'Laboratório de Testes', data: 'Ontem' }
  ]

  return (
    <div style={{ minHeight: '100vh', backgroundColor: '#0f172a', padding: '40px' }}>
      <header style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '40px', borderBottom: '1px solid #334155', paddingBottom: '20px' }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
          <Network size={32} color="#3b82f6" />
          <h1 style={{ fontSize: '24px' }}>Meus Projetos</h1>
        </div>
        <button onClick={() => navigate('/')} style={{ display: 'flex', alignItems: 'center', gap: '8px', background: 'transparent', border: 'none', color: '#94a3b8', cursor: 'pointer' }}>
          <LogOut size={20} /> Sair
        </button>
      </header>

      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(250px, 1fr))', gap: '20px' }}>
        {/* Botão Criar Novo */}
        <button 
          onClick={() => navigate('/editor/novo')}
          style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center', height: '160px', backgroundColor: '#1e293b', border: '2px dashed #475569', borderRadius: '12px', color: '#94a3b8', cursor: 'pointer', transition: 'all 0.2s' }}>
          <FolderPlus size={40} style={{ marginBottom: '10px' }} />
          <span>Criar Novo Projeto</span>
        </button>

        {/* Lista de Projetos */}
        {projetos.map(proj => (
          <div 
            key={proj.id}
            onClick={() => navigate(`/editor/${proj.id}`)}
            style={{ display: 'flex', flexDirection: 'column', height: '160px', backgroundColor: '#1e293b', border: '1px solid #334155', borderRadius: '12px', padding: '20px', cursor: 'pointer', justifyContent: 'space-between' }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
              <Folder size={24} color="#3b82f6" />
              <h3 style={{ fontSize: '18px' }}>{proj.nome}</h3>
            </div>
            <span style={{ fontSize: '12px', color: '#64748b' }}>Criado: {proj.data}</span>
          </div>
        ))}
      </div>
    </div>
  )
}