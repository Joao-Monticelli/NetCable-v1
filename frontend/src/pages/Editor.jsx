import { useState, useCallback, useRef, useEffect } from 'react'
import { useNavigate, useParams } from 'react-router-dom'
import { ArrowLeft, Save, Plus, Network, Settings, CheckCircle2, XCircle, MinusCircle, Loader2, Download, Upload, Share2, LogOut, UserCog, Bell, AlertTriangle } from 'lucide-react'
import toast from 'react-hot-toast'
import NetworkMap from '../components/NetworkMap'
import AddEquipmentModal from '../components/Modals/AddEquipmentModal'
import SettingsModal from '../components/Modals/SettingsModal'
import { api } from '../services/api'

export default function Editor() {
  const navigate = useNavigate()
  const { projectId } = useParams()
  
  const [projectName, setProjectName] = useState(projectId === 'novo' ? 'Novo Mapa' : `Carregando...`)
  const [isEditingName, setIsEditingName] = useState(false)
  const [isAddModalOpen, setIsAddModalOpen] = useState(false)
  const [newEquipment, setNewEquipment] = useState(null)
  const [stats, setStats] = useState({ online: 0, offline: 0, visual: 0 })
  const [isSaving, setIsSaving] = useState(false)
  const [isLoadingData, setIsLoadingData] = useState(projectId !== 'novo')
  
  const [mapNodes, setMapNodes] = useState([])
  const [mapEdges, setMapEdges] = useState([])
  const [showConfigMenu, setShowConfigMenu] = useState(false)
  
  const [isSettingsModalOpen, setIsSettingsModalOpen] = useState(false)
  const [currentUser, setCurrentUser] = useState(null)

  // Estado do Alerta
  const [temAlerta, setTemAlerta] = useState(false)

  const currentNodes = useRef([])
  const currentEdges = useRef([])
  const fileInputRef = useRef(null)

  useEffect(() => {
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

  useEffect(() => {
    if (projectId === 'novo') return
    const fetchProjeto = async () => {
      try {
        const data = await api.obterProjeto(projectId)
        setProjectName(data.nome)
        const formattedNodes = data.equipamentos.map(eq => ({
          id: eq.id, type: 'custom', position: { x: eq.pos_x, y: eq.pos_y },
          style: { width: eq.width, height: eq.height },
          data: { label: eq.nome, ip: eq.ip, tipo: eq.tipo, status: eq.status, pingTime: eq.ping_time }
        }))
        const formattedEdges = data.conexoes.map(conn => ({
          id: conn.id, source: conn.source, target: conn.target, label: conn.label,
          sourceHandle: conn.source_handle, targetHandle: conn.target_handle,
          type: 'smoothstep', animated: true, interactionWidth: 20,
          style: { stroke: '#3b82f6', strokeWidth: 2.5 }, markerEnd: { type: 'arrowclosed', color: '#3b82f6' }
        }))
        setMapNodes(formattedNodes)
        setMapEdges(formattedEdges)
      } catch (error) {
        toast.error('Erro ao carregar o projeto.')
        navigate('/');
      } finally {
        setIsLoadingData(false)
      }
    }
    fetchProjeto()
  }, [projectId, navigate])

  const handleMapUpdate = useCallback((nodes, edges) => {
    currentNodes.current = nodes
    currentEdges.current = edges
    const counts = nodes.reduce((acc, node) => {
      if (node.data.status === 'online') acc.online++
      else if (node.data.status === 'offline') acc.offline++
      else if (node.data.status === 'visual') acc.visual++
      return acc
    }, { online: 0, offline: 0, visual: 0 })
    setStats(counts)
  }, [])

  // Callback chamado quando o NetworkMap detecta uma queda
  const handleAlertaQueda = useCallback((mensagem) => {
    setTemAlerta(true)
    toast.error(mensagem, { duration: 5000 }) // Notificação no canto da tela
    
    // Piscar o título da aba do navegador
    let isOriginalTitle = false;
    const interval = setInterval(() => {
      document.title = isOriginalTitle ? '⚠️ QUEDA DETECTADA ⚠️' : 'NetCable';
      isOriginalTitle = !isOriginalTitle;
    }, 1000);
    
    // Para de piscar depois de 10 segundos
    setTimeout(() => clearInterval(interval), 10000);
    
    // Remove o alerta visual após 10 segundos
    setTimeout(() => setTemAlerta(false), 10000)
  }, [])

  const handleSaveProject = async () => {
    if (isSaving) return
    setIsSaving(true)
    try {
      if (projectId !== 'novo' && projectName !== `Carregando...`) {
        await api.editarNomeProjeto(projectId, projectName)
      }
      const equipamentosFormatados = currentNodes.current.map(node => ({
        id: node.id, nome: node.data.label, ip: node.data.ip, tipo: node.data.tipo, status: node.data.status,
        pingTime: node.data.pingTime || null, posX: node.position.x, posY: node.position.y, width: node.style?.width || 200, height: node.style?.height || 80
      }))
      const conexoesFormatadas = currentEdges.current.map(edge => ({
        id: edge.id, source: edge.source, target: edge.target, label: edge.label || null,
        sourceHandle: edge.sourceHandle || null, targetHandle: edge.targetHandle || null
      }))
      let idParaSalvar = projectId
      if (projectId === 'novo') {
        const projetoCriado = await api.criarProjeto(projectName)
        idParaSalvar = projetoCriado.id
      }
      const ok = await api.salvarMapa(idParaSalvar, equipamentosFormatados, conexoesFormatadas)
      if (ok) {
        toast.success('Projeto salvo com sucesso!')
        if (projectId === 'novo') navigate(`/editor/${idParaSalvar}`, { replace: true })
      }
    } catch (error) { toast.error('Erro ao salvar o projeto.') } finally { setIsSaving(false) }
  }

  const handleCopyLink = () => {
    if (projectId === 'novo') { toast.error("Salve o projeto primeiro!"); return; }
    const link = `${window.location.origin}/share/${projectId}`;
    navigator.clipboard.writeText(link);
    toast.success('Link público copiado!');
    setShowConfigMenu(false);
  };

  const handleLogout = () => { api.logout(); navigate('/'); };
  const handleAddEquipment = (equipamento) => { setNewEquipment({ ...equipamento, id: Date.now() }); setIsAddModalOpen(false) }

  const handleExport = () => {
    const dataToExport = { projeto: projectName, equipamentos: currentNodes.current, conexoes: currentEdges.current }
    const blob = new Blob([JSON.stringify(dataToExport, null, 2)], { type: "application/json" })
    const url = URL.createObjectURL(blob)
    const link = document.createElement('a')
    link.href = url
    link.download = `netcable_backup_${projectName.replace(/\s+/g, '_')}.json`
    link.click()
    toast.success('Backup exportado!')
  }

  const handleImport = (event) => {
    const file = event.target.files[0]
    if (!file) return
    const reader = new FileReader()
    reader.onload = (e) => {
      try {
        const importedData = JSON.parse(e.target.result)
        if (importedData.equipamentos && importedData.conexoes) {
          setMapNodes(importedData.equipamentos)
          setMapEdges(importedData.conexoes)
          toast.success('Backup importado!')
        }
      } catch (err) { toast.error('Erro ao ler o arquivo JSON.') }
    }
    reader.readAsText(file)
    event.target.value = null
  }

  if (isLoadingData) return <div style={{ color: '#94a3b8', display: 'flex', justifyContent: 'center', alignItems: 'center', height: '100vh' }}><Loader2 className="spin" /> Carregando...</div>

  return (
    <div style={{ display: 'flex', flexDirection: 'column', height: '100vh', backgroundColor: '#0f172a' }}>
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
              <span onClick={() => setIsEditingName(true)} style={{ fontWeight: 'bold', cursor: 'pointer', padding: '4px 8px', borderRadius: '4px', border: '1px solid transparent' }}>{projectName} ✏️</span>
            )}
          </div>
        </div>

        <div style={{ display: 'flex', gap: '10px', alignItems: 'center' }}>
          
          {/* ÍCONE DE ALERTA NO HEADER */}
          <div title={temAlerta ? "Atenção: Queda detectada!" : "Sem alertas"} style={{ padding: '8px', backgroundColor: temAlerta ? '#ef4444' : 'transparent', borderRadius: '50%', display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
            {temAlerta ? <AlertTriangle size={20} color="white" className="animate-pulse" /> : <Bell size={20} color="#64748b" />}
          </div>

          <div style={{ display: 'flex', alignItems: 'center', gap: '12px', backgroundColor: '#0f172a', padding: '6px 15px', borderRadius: '8px', border: '1px solid #334155', marginRight: '10px' }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: '5px', fontSize: '13px' }}><CheckCircle2 size={16} color="#10b981" /> <span style={{ color: '#10b981', fontWeight: 'bold' }}>{stats.online}</span></div>
            <div style={{ display: 'flex', alignItems: 'center', gap: '5px', fontSize: '13px' }}><XCircle size={16} color="#ef4444" /> <span style={{ color: '#ef4444', fontWeight: 'bold' }}>{stats.offline}</span></div>
            <div style={{ display: 'flex', alignItems: 'center', gap: '5px', fontSize: '13px' }}><MinusCircle size={16} color="#64748b" /> <span style={{ color: '#64748b', fontWeight: 'bold' }}>{stats.visual}</span></div>
          </div>

          <input type="file" ref={fileInputRef} onChange={handleImport} accept=".json" style={{ display: 'none' }} />
          <button onClick={() => fileInputRef.current.click()} title="Importar JSON" style={{ padding: '8px 12px', backgroundColor: '#334155', color: 'white', border: 'none', borderRadius: '6px', cursor: 'pointer' }}><Upload size={18} /></button>
          <button onClick={handleExport} title="Exportar JSON" style={{ padding: '8px 12px', backgroundColor: '#334155', color: 'white', border: 'none', borderRadius: '6px', cursor: 'pointer' }}><Download size={18} /></button>

          <button onClick={() => setIsAddModalOpen(true)} style={{ display: 'flex', alignItems: 'center', gap: '6px', padding: '8px 16px', backgroundColor: '#3b82f6', color: 'white', border: 'none', borderRadius: '6px', cursor: 'pointer' }}>
            <Plus size={18} /> Adicionar
          </button>
          
          <button onClick={handleSaveProject} disabled={isSaving} style={{ display: 'flex', alignItems: 'center', gap: '6px', padding: '8px 16px', backgroundColor: isSaving ? '#475569' : '#10b981', color: 'white', border: 'none', borderRadius: '6px', cursor: isSaving ? 'wait' : 'pointer' }}>
            {isSaving ? <Loader2 size={18} className="spin" /> : <Save size={18} />} {isSaving ? 'Salvando...' : 'Salvar'}
          </button>
          
          <div style={{ position: 'relative' }}>
            <button onClick={() => setShowConfigMenu(!showConfigMenu)} style={{ display: 'flex', alignItems: 'center', padding: '8px 12px', backgroundColor: showConfigMenu ? '#475569' : '#334155', color: 'white', border: 'none', borderRadius: '6px', cursor: 'pointer' }}>
              <Settings size={18} />
            </button>
            {showConfigMenu && (
              <div style={{ position: 'absolute', top: '110%', right: 0, backgroundColor: '#1e293b', border: '1px solid #334155', borderRadius: '6px', padding: '5px', minWidth: '180px', boxShadow: '0 4px 6px rgba(0,0,0,0.3)', zIndex: 100 }}>
                <button onClick={() => { setShowConfigMenu(false); setIsSettingsModalOpen(true) }} style={{ display: 'flex', alignItems: 'center', gap: '8px', width: '100%', padding: '10px', backgroundColor: 'transparent', color: 'white', border: 'none', textAlign: 'left', cursor: 'pointer', borderRadius: '4px' }} className="hover:bg-slate-700">
                  <UserCog size={16} color="#94a3b8"/> Editar Perfil
                </button>
                <button onClick={handleCopyLink} style={{ display: 'flex', alignItems: 'center', gap: '8px', width: '100%', padding: '10px', backgroundColor: 'transparent', color: 'white', border: 'none', textAlign: 'left', cursor: 'pointer', borderRadius: '4px' }} className="hover:bg-slate-700">
                  <Share2 size={16} color="#3b82f6"/> Gerar Link Público
                </button>
                <div style={{ height: '1px', backgroundColor: '#334155', margin: '5px 0' }}></div>
                <button onClick={handleLogout} style={{ display: 'flex', alignItems: 'center', gap: '8px', width: '100%', padding: '10px', backgroundColor: 'transparent', color: '#ef4444', border: 'none', textAlign: 'left', cursor: 'pointer', borderRadius: '4px' }}>
                  <LogOut size={16} /> Sair
                </button>
              </div>
            )}
          </div>
        </div>
      </div>

      <div style={{ flex: 1 }}>
        <NetworkMap initialNodes={mapNodes} initialEdges={mapEdges} newEquipment={newEquipment} onMapUpdate={handleMapUpdate} onAlertaQueda={handleAlertaQueda} />
      </div>

      {isAddModalOpen && <AddEquipmentModal onClose={() => setIsAddModalOpen(false)} onAdd={handleAddEquipment} />}
      {isSettingsModalOpen && <SettingsModal onClose={() => setIsSettingsModalOpen(false)} currentUser={currentUser} />}
    </div>
  )
}