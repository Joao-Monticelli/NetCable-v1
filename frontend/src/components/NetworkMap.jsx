import { useCallback, useState, useEffect, memo } from 'react'
import ReactFlow, {
  Controls, Background, applyNodeChanges, applyEdgeChanges, addEdge, MarkerType, Handle, Position, NodeResizer, reconnectEdge, SmoothStepEdge, useReactFlow, ReactFlowProvider
} from 'reactflow'
import { Server, Wifi, Shield, Monitor, Activity } from 'lucide-react'
import EquipmentModal from './Modals/EquipmentModal'
import EdgeModal from './Modals/EdgeModal'

const CustomNode = memo(({ data, selected }) => {
  const getIcon = () => {
    switch (data.tipo) {
      case 'Roteador': return <Wifi size={18} color="#3b82f6" />
      case 'Firewall': return <Shield size={18} color="#f59e0b" />
      case 'PC': return <Monitor size={18} color="#94a3b8" />
      default: return <Server size={18} color="#10b981" />
    }
  }

  return (
    <div className="custom-node" style={{ width: '100%', height: '100%' }}>
      <NodeResizer minWidth={120} minHeight={60} isVisible={selected} lineStyle={{ borderColor: '#3b82f6', borderWidth: '2px' }} handleStyle={{ backgroundColor: '#3b82f6', width: '8px', height: '8px' }} keepAspectRatio={false} />
      
      <Handle type="source" position={Position.Top} id="top" style={{ background: '#3b82f6', width: '12px', height: '12px' }} />
      <Handle type="source" position={Position.Left} id="left" style={{ background: '#3b82f6', width: '12px', height: '12px' }} />
      
      <div className={`status-dot ${data.status === 'visual' ? 'status-visual' : (data.status === 'online' ? 'status-online' : 'status-offline')}`} />
      
      {getIcon()}
      <div style={{ display: 'flex', flexDirection: 'column', overflow: 'hidden', paddingRight: '10px' }}>
        <div style={{ fontWeight: 'bold', fontSize: '14px', textOverflow: 'ellipsis', whiteSpace: 'nowrap', overflow: 'hidden' }}>{data.label}</div>
        <div style={{ fontSize: '11px', color: '#94a3b8' }}>{data.ip}</div>
        
        {data.status === 'online' && data.pingTime && (
          <div style={{ fontSize: '10px', color: '#10b981', display: 'flex', alignItems: 'center', gap: '3px', marginTop: '2px' }}>
            <Activity size={10} /> {data.pingTime}ms
          </div>
        )}
      </div>
      
      <Handle type="source" position={Position.Bottom} id="bottom" style={{ background: '#3b82f6', width: '12px', height: '12px' }} />
      <Handle type="source" position={Position.Right} id="right" style={{ background: '#3b82f6', width: '12px', height: '12px' }} />
    </div>
  )
})

const nodeTypes = { custom: CustomNode }
const edgeTypes = { smoothstep: SmoothStepEdge }

const defaultEdgeOptions = {
  animated: true,
  type: 'smoothstep',
  interactionWidth: 20, 
}

// Função que calcula a cor do cabo baseado na hierarquia (Pai e Filho)
const calcularCorConexao = (sourceNode, targetNode) => {
  if (!sourceNode || !targetNode) return { stroke: '#64748b', color: '#64748b' } // Padrão cinza
  
  const isSourceOnline = sourceNode.data.status === 'online';
  const isSourceOffline = sourceNode.data.status === 'offline';
  const isTargetOnline = targetNode.data.status === 'online';
  const isTargetOffline = targetNode.data.status === 'offline';
  const isTargetVisual = targetNode.data.status === 'visual';

  if (isTargetVisual) return { stroke: '#64748b', color: '#64748b' }; // Destino Visual (Cinza)
  if (isTargetOffline) return { stroke: '#ef4444', color: '#ef4444' }; // Destino caiu (Vermelho)
  
  // Se chegou aqui, o destino está online.
  if (isSourceOffline) {
     return { stroke: '#f59e0b', color: '#f59e0b' }; // Alerta: Pai caiu, mas o filho responde (Amarelo)
  }
  
  // Ambos online
  return { stroke: '#10b981', color: '#10b981' }; // Verde
}

function NetworkMapContent({ initialNodes = [], initialEdges = [], newEquipment = null, onMapUpdate }) {
  const [nodes, setNodes] = useState(initialNodes)
  const [edges, setEdges] = useState(initialEdges)
  const [selectedNode, setSelectedNode] = useState(null)
  const [selectedEdge, setSelectedEdge] = useState(null)
  
  const { screenToFlowPosition, getViewport } = useReactFlow()

  // Efeito para avisar o Editor
  useEffect(() => {
    if (onMapUpdate) onMapUpdate(nodes, edges)
  }, [nodes, edges, onMapUpdate])

  // Efeito que RECALCULA as cores ao carregar ou mudar os nós/arestas
  useEffect(() => {
    setEdges((currentEdges) => 
      currentEdges.map((edge) => {
        const sourceNode = nodes.find(n => n.id === edge.source)
        const targetNode = nodes.find(n => n.id === edge.target)
        
        // Se as cores já estiverem certas, não recria o objeto (evita loop)
        const corEsperada = calcularCorConexao(sourceNode, targetNode)
        if (edge.style?.stroke === corEsperada.stroke) return edge;

        return {
          ...edge,
          style: { ...edge.style, stroke: corEsperada.stroke, strokeWidth: 2.5 },
          markerEnd: { type: MarkerType.ArrowClosed, color: corEsperada.color }
        }
      })
    )
  }, [nodes, initialEdges]) // Recalcula sempre que os nós (status) mudarem

  // Efeito para adicionar novo equipamento
  useEffect(() => {
    if (newEquipment) {
      let posicaoNoMapa = { x: 250, y: 250 }
      try {
        const centerX = window.innerWidth / 2
        const centerY = window.innerHeight / 2
        posicaoNoMapa = screenToFlowPosition({ x: centerX, y: centerY })
      } catch(e) { console.warn("Não foi possível centralizar o nó.") }

      const newNode = {
        id: `node_${Date.now()}`, type: 'custom', position: posicaoNoMapa, style: { width: 200, height: 80 }, 
        data: { label: newEquipment.nome, ip: newEquipment.ip, tipo: newEquipment.tipo, status: newEquipment.status || 'offline', pingTime: newEquipment.pingTime }
      }
      setNodes((nds) => [...nds, newNode])
    }
  }, [newEquipment, screenToFlowPosition, getViewport])

  // Efeito de Monitoramento
  useEffect(() => {
    const interval = setInterval(async () => {
      if (nodes.length === 0) return

      const pingPromises = nodes.map(async (node) => {
        if (node.data.status === 'visual' || node.data.ip === 'Sem IP') return null
        try {
          const response = await fetch(`http://127.0.0.1:8000/api/ping/${node.data.ip}`)
          const data = await response.json()
          return { id: node.id, status: data.status, pingTime: data.tempo_ms }
        } catch (error) { return { id: node.id, status: 'offline', pingTime: null } }
      })

      const results = await Promise.all(pingPromises)

      setNodes((currentNodes) => 
        currentNodes.map(node => {
          const result = results.find(r => r && r.id === node.id)
          if (result && result.status !== node.data.status) {
            return { ...node, data: { ...node.data, status: result.status, pingTime: result.pingTime } }
          }
          if (result) {
            return { ...node, data: { ...node.data, pingTime: result.pingTime } }
          }
          return node
        })
      )
    }, 5000)

    return () => clearInterval(interval)
  }, [nodes])

  const onNodesChange = useCallback((changes) => setNodes((nds) => applyNodeChanges(changes, nds)), [])
  const onEdgesChange = useCallback((changes) => setEdges((eds) => applyEdgeChanges(changes, eds)), [])
  
  const onConnect = useCallback((params) => {
    const sourceNode = nodes.find(n => n.id === params.source)
    const targetNode = nodes.find(n => n.id === params.target)
    const cor = calcularCorConexao(sourceNode, targetNode)

    setEdges((eds) => addEdge({ 
      ...params, ...defaultEdgeOptions,
      style: { stroke: cor.stroke, strokeWidth: 2.5 },
      markerEnd: { type: MarkerType.ArrowClosed, color: cor.color },
    }, eds))
  }, [nodes])

  const onNodeClick = (event, node) => setSelectedNode(node)
  const onEdgeClick = (event, edge) => setSelectedEdge(edge)
  const onReconnect = useCallback((oldEdge, newConnection) => {
      setEdges((eds) => reconnectEdge(oldEdge, newConnection, eds))
  }, [])
  
  const onEdgeMouseEnter = (event, edge) => setEdges((eds) => eds.map((e) => e.id === edge.id ? { ...e, style: { ...e.style, strokeWidth: 4 } } : e))
  const onEdgeMouseLeave = (event, edge) => setEdges((eds) => eds.map((e) => e.id === edge.id ? { ...e, style: { ...e.style, strokeWidth: 2.5 } } : e))

  const handleUpdateNode = (id, newData) => { setNodes((nds) => nds.map((node) => node.id === id ? { ...node, data: { ...node.data, ...newData } } : node)); setSelectedNode(null) }
  const handleDeleteNode = (id) => { setNodes((nds) => nds.filter((node) => node.id !== id)); setEdges((eds) => eds.filter((edge) => edge.source !== id && edge.target !== id)); setSelectedNode(null) }
  const handleUpdateEdge = (id, newLabel, newSource, newTarget) => {
    setEdges((eds) => eds.map((edge) => {
      if (edge.id === id) {
        const sourceNode = nodes.find(n => n.id === newSource)
        const targetNode = nodes.find(n => n.id === newTarget)
        const cor = calcularCorConexao(sourceNode, targetNode)
        return { ...edge, source: newSource, target: newTarget, label: newLabel, labelStyle: { fill: 'white', fontWeight: 'bold' }, labelBgStyle: { fill: '#1e293b' }, style: { stroke: cor.stroke, strokeWidth: 2.5 }, markerEnd: { type: MarkerType.ArrowClosed, color: cor.color } }
      }
      return edge
    }))
    setSelectedEdge(null)
  }
  const handleDeleteEdge = (id) => { setEdges((eds) => eds.filter((edge) => edge.id !== id)); setSelectedEdge(null) }

  return (
    <>
      <ReactFlow
        nodes={nodes} edges={edges} nodeTypes={nodeTypes} edgeTypes={edgeTypes}
        defaultEdgeOptions={defaultEdgeOptions} onNodesChange={onNodesChange} onEdgesChange={onEdgesChange}
        onConnect={onConnect} onNodeClick={onNodeClick} onEdgeClick={onEdgeClick}
        onEdgeMouseEnter={onEdgeMouseEnter} onEdgeMouseLeave={onEdgeMouseLeave}
        onReconnect={onReconnect} edgesReconnectable={true} reconnectRadius={20} connectionMode="loose" fitView
      >
        <Background />
        <Controls />
      </ReactFlow>

      {selectedNode && <EquipmentModal node={selectedNode} onClose={() => setSelectedNode(null)} onUpdate={handleUpdateNode} onDelete={handleDeleteNode} />}
      {selectedEdge && <EdgeModal edge={selectedEdge} nodes={nodes} onClose={() => setSelectedEdge(null)} onUpdate={handleUpdateEdge} onDelete={handleDeleteEdge} />}
    </>
  )
}

export default function NetworkMap(props) {
  return (
    <ReactFlowProvider>
      <NetworkMapContent {...props} />
    </ReactFlowProvider>
  )
}