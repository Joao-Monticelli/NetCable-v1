import { useState, useEffect } from 'react'
import { useNavigate } from 'react-router-dom'
import { FolderPlus, Folder, LogOut, Network, Loader2, Trash2, Settings, UserCog } from 'lucide-react'
import toast from 'react-hot-toast'
import { api } from '../services/api'
import SettingsModal from '../components/Modals/SettingsModal'

export default function Projects() {
  const navigate = useNavigate()
  const [projetos, setProjetos] = useState([])
  const [isLoading, setIsLoading] = useState(true)
  
  // Estados para o Menu de Configurações e Modal
  const [showConfigMenu, setShowConfigMenu] = useState(false)
  const [isSettingsModalOpen, setIsSettingsModalOpen] = useState(false)
  const [currentUser, setCurrentUser] = useState(null)

  const fetchProjetos = async () => {
    try {
      const data = await api.listarProjetos()
      setProjetos(data)
    } catch (error) {
      if (error.message === 'Não autorizado') {
        api.logout(); navigate('/');
      }
    } finally {
      setIsLoading(false)
    }
  }

  useEffect(() => {
    fetchProjetos()
    
    // Busca os dados do usuário logado para preencher o Modal de Perfil
    const fetchMe = async () => {
      try {
        const res = await fetch(`http://${window.location.hostname}:8000/api/me`, {
          headers: { 'Authorization': `Bearer ${localStorage.getItem('netcable_token')}` }
        })
        if (res.ok) setCurrentUser(await res.json())
      } catch (error) { console.error(error) }
    }
    fetchMe()
  }, [])

  const handleDeleteProject = async (e, id, nome) => {
    e.stopPropagation() 
    if (!window.confirm(`Excluir o projeto "${nome}"?`)) return
    try {
      const ok = await api.deletarProjeto(id)
      if (ok) {
        setProjetos(projetos.filter(p => p.id !== id))
        toast.success('Projeto excluído com sucesso.')
      }
    } catch (error) { toast.error('Erro ao excluir.') }
  }

  const handleLogout = () => {
    api.logout();
    navigate('/');
  }

  return (
    <div style={{ minHeight: '100vh', backgroundColor: '#0f172a', padding: '40px' }}>
      <header style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '40px', borderBottom: '1px solid #334155', paddingBottom: '20px' }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
          <Network size={32} color="#3b82f6" />
          <h1 style={{ fontSize: '24px' }}>Meus Projetos</h1>
        </div>

        {/* LADO DIREITO: MENU DE CONFIGURAÇÕES */}
        <div style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
          <div style={{ position: 'relative' }}>
            <button 
              onClick={() => setShowConfigMenu(!showConfigMenu)} 
              style={{ display: 'flex', alignItems: 'center', padding: '8px 12px', backgroundColor: showConfigMenu ? '#475569' : '#334155', color: 'white', border: 'none', borderRadius: '6px', cursor: 'pointer' }}
            >
              <Settings size={20} />
            </button>

            {showConfigMenu && (
              <div style={{ position: 'absolute', top: '110%', right: 0, backgroundColor: '#1e293b', border: '1px solid #334155', borderRadius: '6px', padding: '5px', minWidth: '180px', boxShadow: '0 4px 6px rgba(0,0,0,0.3)', zIndex: 100 }}>
                
                <button 
                  onClick={() => { setShowConfigMenu(false); setIsSettingsModalOpen(true) }} 
                  style={{ display: 'flex', alignItems: 'center', gap: '8px', width: '100%', padding: '10px', backgroundColor: 'transparent', color: 'white', border: 'none', textAlign: 'left', cursor: 'pointer', borderRadius: '4px' }} 
                  className="hover:bg-slate-700"
                >
                  <UserCog size={16} color="#94a3b8"/> Editar Perfil
                </button>
                
                <div style={{ height: '1px', backgroundColor: '#334155', margin: '5px 0' }}></div>
                
                <button 
                  onClick={handleLogout} 
                  style={{ display: 'flex', alignItems: 'center', gap: '8px', width: '100%', padding: '10px', backgroundColor: 'transparent', color: '#ef4444', border: 'none', textAlign: 'left', cursor: 'pointer', borderRadius: '4px' }}
                >
                  <LogOut size={16} /> Sair
                </button>
              </div>
            )}
          </div>
        </div>
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

      {/* MODAL DE PERFIL */}
      {isSettingsModalOpen && (
        <SettingsModal 
          onClose={() => setIsSettingsModalOpen(false)} 
          currentUser={currentUser} 
        />
      )}
    </div>
  )
}