import { useState, useCallback, useRef, useEffect } from 'react'
import { useNavigate, useParams } from 'react-router-dom'
import { ArrowLeft, Save, Plus, Network, Settings, CheckCircle2, XCircle, MinusCircle, Loader2, Download, Upload } from 'lucide-react'
import NetworkMap from '../components/NetworkMap'
import AddEquipmentModal from '../components/Modals/AddEquipmentModal'

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

  const currentNodes = useRef([])
  const currentEdges = useRef([])
  const fileInputRef = useRef(null)

  useEffect(() => {
    if (projectId === 'novo') return
    const fetchProjeto = async () => {
      try {
        const res = await fetch(`http://127.0.0.1:8000/api/projetos/${projectId}/dados`)
        const data = await res.json()
        setProjectName(data.nome)
        
        const formattedNodes = data.equipamentos.map(eq => ({
          id: eq.id, type: 'custom', position: { x: eq.pos_x, y: eq.pos_y },
          style: { width: eq.width, height: eq.height },
          data: { label: eq.nome, ip: eq.ip, tipo: eq.tipo, status: eq.status, pingTime: eq.ping_time }
        }))
        
        const formattedEdges = data.conexoes.map(conn => ({
          id: conn.id, source: conn.source, target: conn.target, label: conn.label,
          sourceHandle: conn.source_handle, // NOVO
          targetHandle: conn.target_handle, // NOVO
          type: 'smoothstep', animated: true, interactionWidth: 20,
          style: { stroke: '#3b82f6', strokeWidth: 2.5 }, markerEnd: { type: 'arrowclosed', color: '#3b82f6' }
        }))
        
        setMapNodes(formattedNodes)
        setMapEdges(formattedEdges)
      } catch (error) {
        alert('Erro ao carregar os dados do projeto.')
      } finally {
        setIsLoadingData(false)
      }
    }
    fetchProjeto()
  }, [projectId])

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

  const handleAddEquipment = (equipamento) => {
    setNewEquipment({ ...equipamento, id: Date.now() })
    setIsAddModalOpen(false)
  }

  const handleExport = () => {
    const dataToExport = { projeto: projectName, equipamentos: currentNodes.current, conexoes: currentEdges.current }
    const blob = new Blob([JSON.stringify(dataToExport, null, 2)], { type: "application/json" })
    const url = URL.createObjectURL(blob)
    const link = document.createElement('a')
    link.href = url
    link.download = `netcable_backup_${projectName.replace(/\s+/g, '_')}.json`
    link.click()
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
        }
      } catch (err) { alert('Erro ao ler o arquivo JSON.') }
    }
    reader.readAsText(file)
    event.target.value = null
  }

  const handleSaveProject = async () => {
    if (isSaving) return
    setIsSaving(true)
    try {
      const equipamentosFormatados = currentNodes.current.map(node => ({
        id: node.id, nome: node.data.label, ip: node.data.ip, tipo: node.data.tipo, status: node.data.status,
        pingTime: node.data.pingTime || null, posX: node.position.x, posY: node.position.y, width: node.style?.width || 200, height: node.style?.height || 80
      }))
      
      const conexoesFormatadas = currentEdges.current.map(edge => ({
        id: edge.id, 
        source: edge.source, 
        target: edge.target, 
        label: edge.label || null,
        sourceHandle: edge.sourceHandle || null, // NOVO
        targetHandle: edge.targetHandle || null  // NOVO
      }))

      let idParaSalvar = projectId
      if (projectId === 'novo') {
        const res = await fetch(`http://127.0.0.1:8000/api/projetos?nome=${encodeURIComponent(projectName)}`, { method: 'POST' })
        const projetoCriado = await res.json()
        idParaSalvar = projetoCriado.id
      }
      const response = await fetch(`http://127.0.0.1:8000/api/projetos/${idParaSalvar}/salvar`, {
        method: 'POST', headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ equipamentos: equipamentosFormatados, conexoes: conexoesFormatadas })
      })
      if (response.ok) {
        alert('Projeto salvo!')
        if (projectId === 'novo') navigate(`/editor/${idParaSalvar}`, { replace: true })
      }
    } catch (error) { alert('Erro ao salvar.') } finally { setIsSaving(false) }
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
          
          <button onClick={() => alert('Em breve.')} style={{ display: 'flex', alignItems: 'center', gap: '6px', padding: '8px 12px', backgroundColor: '#334155', color: 'white', border: 'none', borderRadius: '6px', cursor: 'pointer' }}><Settings size={18} /></button>
        </div>
      </div>

      <div style={{ flex: 1 }}>
        <NetworkMap initialNodes={mapNodes} initialEdges={mapEdges} newEquipment={newEquipment} onMapUpdate={handleMapUpdate} />
      </div>

      {isAddModalOpen && <AddEquipmentModal onClose={() => setIsAddModalOpen(false)} onAdd={handleAddEquipment} />}
    </div>
  )
}