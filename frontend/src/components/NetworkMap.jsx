import { useCallback, useState, useEffect, memo } from 'react'
import ReactFlow, {
  Controls, Background, applyNodeChanges, applyEdgeChanges, addEdge, MarkerType, Handle, Position, NodeResizer, reconnectEdge
} from 'reactflow'
import { Server, Wifi, Shield, Monitor } from 'lucide-react'
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
      <NodeResizer minWidth={150} minHeight={60} isVisible={selected} lineStyle={{ borderColor: '#3b82f6' }} handleStyle={{ backgroundColor: '#3b82f6' }} />
      
      {/* Alças de conexão - Aumentadas para facilitar o arrasto */}
      <Handle type="target" position={Position.Top} style={{ background: '#3b82f6', width: '12px', height: '12px', zIndex: 10 }} />
      <Handle type="target" position={Position.Left} style={{ background: '#3b82f6', width: '12px', height: '12px', zIndex: 10 }} />
      
      <div className={`status-dot ${data.status === 'visual' ? 'status-visual' : (data.status === 'online' ? 'status-online' : 'status-offline')}`} />
      
      {getIcon()}
      <div style={{ display: 'flex', flexDirection: 'column', overflow: 'hidden', paddingRight: '10px' }}>
        <div style={{ fontWeight: 'bold', fontSize: '14px', textOverflow: 'ellipsis', whiteSpace: 'nowrap', overflow: 'hidden' }}>{data.label}</div>
        <div style={{ fontSize: '11px', color: '#94a3b8' }}>{data.ip}</div>
      </div>
      
      <Handle type="source" position={Position.Bottom} style={{ background: '#3b82f6', width: '12px', height: '12px', zIndex: 10 }} />
      <Handle type="source" position={Position.Right} style={{ background: '#3b82f6', width: '12px', height: '12px', zIndex: 10 }} />
    </div>
  )
})

const nodeTypes = { custom: CustomNode }

const defaultEdgeOptions = {
  animated: true,
  style: { stroke: '#3b82f6', strokeWidth: 2.5 },
  markerEnd: { type: MarkerType.ArrowClosed, color: '#3b82f6' },
  // Aumenta a área de clique do cabo para facilitar a seleção
  interactionWidth: 20, 
}

export default function NetworkMap({ initialNodes = [], initialEdges = [], newEquipment = null }) {
  const [nodes, setNodes] = useState(initialNodes)
  const [edges, setEdges] = useState(initialEdges)
  const [selectedNode, setSelectedNode] = useState(null)
  const [selectedEdge, setSelectedEdge] = useState(null)

  useEffect(() => {
    if (newEquipment) {
      const newNode = {
        id: `node_${Date.now()}`,
        type: 'custom',
        position: { x: Math.random() * 400 + 100, y: Math.random() * 400 + 100 },
        style: { width: 200, height: 80 }, 
        data: { 
          label: newEquipment.nome, 
          ip: newEquipment.ip, 
          tipo: newEquipment.tipo,
          status: newEquipment.status || 'offline'
        }
      }
      setNodes((nds) => [...nds, newNode])
    }
  }, [newEquipment])

  const onNodesChange = useCallback((changes) => setNodes((nds) => applyNodeChanges(changes, nds)), [])
  const onEdgesChange = useCallback((changes) => setEdges((eds) => applyEdgeChanges(changes, eds)), [])
  const onConnect = useCallback((params) => setEdges((eds) => addEdge({ ...params, ...defaultEdgeOptions }, eds)), [])

  const onNodeClick = (event, node) => setSelectedNode(node)
  const onEdgeClick = (event, edge) => setSelectedEdge(edge)

  // --- LÓGICA DE RECONEXÃO DE CABO ARRASTANDO A PONTA ---
  const onReconnect = useCallback(
    (oldEdge, newConnection) => {
      setEdges((eds) => reconnectEdge(oldEdge, newConnection, eds))
    },
    []
  )

  const onEdgeMouseEnter = (event, edge) => {
    setEdges((eds) => eds.map((e) => e.id === edge.id ? { ...e, style: { ...e.style, strokeWidth: 4, stroke: '#60a5fa' } } : e))
  }
  const onEdgeMouseLeave = (event, edge) => {
    setEdges((eds) => eds.map((e) => e.id === edge.id ? { ...e, style: { ...e.style, strokeWidth: 2.5, stroke: '#3b82f6' } } : e))
  }

  const handleUpdateNode = (id, newData) => {
    setNodes((nds) => nds.map((node) => node.id === id ? { ...node, data: { ...node.data, ...newData } } : node))
    setSelectedNode(null)
  }

  const handleDeleteNode = (id) => {
    setNodes((nds) => nds.filter((node) => node.id !== id))
    setEdges((eds) => eds.filter((edge) => edge.source !== id && edge.target !== id))
    setSelectedNode(null)
  }

  const handleUpdateEdge = (id, newLabel, newSource, newTarget) => {
    setEdges((eds) =>
      eds.map((edge) => {
        if (edge.id === id) {
          return { 
            ...edge, 
            source: newSource, 
            target: newTarget,
            label: newLabel, 
            labelStyle: { fill: 'white', fontWeight: 'bold' }, 
            labelBgStyle: { fill: '#1e293b' } 
          }
        }
        return edge
      })
    )
    setSelectedEdge(null)
  }

  const handleDeleteEdge = (id) => {
    setEdges((eds) => eds.filter((edge) => edge.id !== id))
    setSelectedEdge(null)
  }

  return (
    <>
      <ReactFlow
        nodes={nodes}
        edges={edges}
        nodeTypes={nodeTypes}
        defaultEdgeOptions={defaultEdgeOptions}
        onNodesChange={onNodesChange}
        onEdgesChange={onEdgesChange}
        onConnect={onConnect}
        onNodeClick={onNodeClick}
        onEdgeClick={onEdgeClick}
        onEdgeMouseEnter={onEdgeMouseEnter}
        onEdgeMouseLeave={onEdgeMouseLeave}
        // --- PROPS PARA PERMITIR ARRASTAR A PONTA DO CABO ---
        onReconnect={onReconnect}
        edgesReconnectable={true}
        reconnectRadius={20} // Facilita acertar a ponta do cabo
        fitView
      >
        <Background />
        <Controls />
      </ReactFlow>

      {selectedNode && (
        <EquipmentModal node={selectedNode} onClose={() => setSelectedNode(null)} onUpdate={handleUpdateNode} onDelete={handleDeleteNode} />
      )}

      {selectedEdge && (
        <EdgeModal edge={selectedEdge} nodes={nodes} onClose={() => setSelectedEdge(null)} onUpdate={handleUpdateEdge} onDelete={handleDeleteEdge} />
      )}
    </>
  )
}