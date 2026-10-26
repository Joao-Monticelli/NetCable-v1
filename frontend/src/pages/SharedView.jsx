import { useState, useEffect, useCallback } from 'react'
import { useParams } from 'react-router-dom'
import { Network, Loader2, CheckCircle2, XCircle, MinusCircle, AlertTriangle } from 'lucide-react'
import NetworkMap from '../components/NetworkMap'
import { api } from '../services/api'

export default function SharedView() {
  const { projectId } = useParams()
  const [projectName, setProjectName] = useState('Carregando...')
  const [mapNodes, setMapNodes] = useState([])
  const [mapEdges, setMapEdges] = useState([])
  const [stats, setStats] = useState({ online: 0, offline: 0, visual: 0 })
  const [isLoading, setIsLoading] = useState(true)
  const [error, setError] = useState(null)

  useEffect(() => {
    const fetchProjeto = async () => {
      try {
        const data = await api.obterProjeto(projectId)
        if (data.detail || data.erro) throw new Error('Projeto não encontrado.')
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
      } catch (err) {
        setError("Não foi possível conectar ao servidor do NetCable ou o link é inválido.")
      } finally {
        setIsLoading(false)
      }
    }
    fetchProjeto()
  }, [projectId])

  const handleMapUpdate = useCallback((nodes) => {
    const counts = nodes.reduce((acc, node) => {
      if (node.data.status === 'online') acc.online++
      else if (node.data.status === 'offline') acc.offline++
      else if (node.data.status === 'visual') acc.visual++
      return acc
    }, { online: 0, offline: 0, visual: 0 })
    setStats(counts)
  }, [])

  if (isLoading) return (
    <div style={{ color: '#94a3b8', display: 'flex', justifyContent: 'center', alignItems: 'center', height: '100vh', backgroundColor: '#0f172a' }}>
      <Loader2 className="spin" style={{marginRight: '10px'}} /> Carregando mapa público...
    </div>
  )

  if (error) return (
    <div style={{ display: 'flex', flexDirection: 'column', justifyContent: 'center', alignItems: 'center', height: '100vh', backgroundColor: '#0f172a', color: 'white', padding: '20px', textAlign: 'center' }}>
      <AlertTriangle size={64} color="#ef4444" style={{ marginBottom: '20px' }} />
      <h1 style={{ fontSize: '24px', marginBottom: '10px' }}>Falha ao carregar</h1>
      <p style={{ color: '#94a3b8', maxWidth: '500px', lineHeight: '1.5' }}>{error}</p>
    </div>
  )

  return (
    <div style={{ display: 'flex', flexDirection: 'column', height: '100vh', backgroundColor: '#0f172a' }}>
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', backgroundColor: '#1e293b', padding: '10px 20px', borderBottom: '1px solid #334155' }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
          <Network size={20} color="#3b82f6" />
          <span style={{ fontWeight: 'bold' }}>{projectName} (Visualização Pública)</span>
        </div>
        <div style={{ display: 'flex', gap: '12px', alignItems: 'center' }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: '12px', backgroundColor: '#0f172a', padding: '6px 15px', borderRadius: '8px', border: '1px solid #334155' }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: '5px', fontSize: '13px' }}><CheckCircle2 size={16} color="#10b981" /> <span style={{ color: '#10b981', fontWeight: 'bold' }}>{stats.online}</span></div>
            <div style={{ display: 'flex', alignItems: 'center', gap: '5px', fontSize: '13px' }}><XCircle size={16} color="#ef4444" /> <span style={{ color: '#ef4444', fontWeight: 'bold' }}>{stats.offline}</span></div>
            <div style={{ display: 'flex', alignItems: 'center', gap: '5px', fontSize: '13px' }}><MinusCircle size={16} color="#64748b" /> <span style={{ color: '#64748b', fontWeight: 'bold' }}>{stats.visual}</span></div>
          </div>
        </div>
      </div>
      <div style={{ flex: 1 }}>
        <NetworkMap initialNodes={mapNodes} initialEdges={mapEdges} onMapUpdate={handleMapUpdate} readOnly={true} />
      </div>
    </div>
  )
}