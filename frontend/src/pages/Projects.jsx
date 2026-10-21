import { useState, useEffect } from 'react'
import { useNavigate } from 'react-router-dom'
import { FolderPlus, Folder, LogOut, Network, Loader2, Trash2 } from 'lucide-react'
import { api } from '../services/api' // IMPORTANDO A API

export default function Projects() {
  const navigate = useNavigate()
  const [projetos, setProjetos] = useState([])
  const [isLoading, setIsLoading] = useState(true)

  const fetchProjetos = async () => {
    try {
      const data = await api.listarProjetos()
      setProjetos(data)
    } catch (error) {
      console.error("Erro ao buscar projetos:", error)
    } finally {
      setIsLoading(false)
    }
  }

  useEffect(() => { fetchProjetos() }, [])

  const handleDeleteProject = async (e, id, nome) => {
    e.stopPropagation() 
    if (!window.confirm(`Excluir o projeto "${nome}"?`)) return
    try {
      const ok = await api.deletarProjeto(id)
      if (ok) setProjetos(projetos.filter(p => p.id !== id))
    } catch (error) { alert('Erro ao excluir.') }
  }

  return (
    <div style={{ minHeight: '100vh', backgroundColor: '#0f172a', padding: '40px' }}>
      <header style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '40px', borderBottom: '1px solid #334155', paddingBottom: '20px' }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
          <Network size={32} color="#3b82f6" />
          <h1 style={{ fontSize: '24px' }}>Meus Projetos</h1>
        </div>
        <button onClick={() => navigate('/')} style={{ display: 'flex', alignItems: 'center', gap: '8px', background: 'transparent', border: 'none', color: '#94a3b8', cursor: 'pointer' }}><LogOut size={20} /> Sair</button>
      </header>

      {isLoading ? (
        <div style={{ display: 'flex', justifyContent: 'center', alignItems: 'center', height: '200px', color: '#94a3b8' }}><Loader2 size={32} className="spin" style={{ marginRight: '10px' }} /> Carregando...</div>
      ) : (
        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(250px, 1fr))', gap: '20px' }}>
          <button onClick={() => navigate('/editor/novo')} style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center', height: '160px', backgroundColor: '#1e293b', border: '2px dashed #475569', borderRadius: '12px', color: '#94a3b8', cursor: 'pointer' }}>
            <FolderPlus size={40} style={{ marginBottom: '10px' }} /><span>Criar Novo Projeto</span>
          </button>
          {projetos.map(proj => (
            <div key={proj.id} onClick={() => navigate(`/editor/${proj.id}`)} style={{ position: 'relative', display: 'flex', flexDirection: 'column', height: '160px', backgroundColor: '#1e293b', border: '1px solid #334155', borderRadius: '12px', padding: '20px', cursor: 'pointer', justifyContent: 'space-between' }}>
              <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
                <div style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
                  <Folder size={24} color="#3b82f6" /><h3 style={{ fontSize: '18px', wordBreak: 'break-word', paddingRight: '10px' }}>{proj.nome}</h3>
                </div>
                <button onClick={(e) => handleDeleteProject(e, proj.id, proj.nome)} style={{ background: 'transparent', border: 'none', color: '#ef4444', cursor: 'pointer', padding: '5px' }}><Trash2 size={18} /></button>
              </div>
              <span style={{ fontSize: '12px', color: '#64748b' }}>ID: {proj.id}</span>
            </div>
          ))}
        </div>
      )}
    </div>
  )
}