import { useCallback, useState, useEffect, memo, useRef, useMemo } from 'react'
import ReactFlow, {
  Controls, Background, applyNodeChanges, applyEdgeChanges, addEdge, MarkerType, Handle, Position, NodeResizer, reconnectEdge, SmoothStepEdge, useReactFlow, ReactFlowProvider
} from 'reactflow'
import { Server, Wifi, Shield, Monitor, Activity, BellOff } from 'lucide-react'
import EquipmentModal from './Modals/EquipmentModal'
import EdgeModal from './Modals/EdgeModal'
import { api } from '../services/api'
import toast from 'react-hot-toast'
import { RackNode, RackDeviceNode } from './rack/RackNodes'
import './rack/rack.css'
import { ModelosContext } from './rack/ModelosContext'
import {
  TRILHO, U_PX, alturaPadrao, uPelaPosicao, posicaoLivreMaisProxima, primeiraPosicaoLivre,
  noRack, noMontado, noLivre, normalizarRacks, rackNoPonto, posicaoADireita, handlesDoNo, ehPorta,
  portasDoEquipamento, nomeDaPorta,
} from './rack/rackUtils'
import { t, useI18n } from '../i18n'

const CustomNode = memo(({ data, selected }) => {
  useI18n()
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
      {data.notificar === false && data.status !== 'visual' && (
        <span className="node-sem-alerta" title={t('Notificações desligadas para este equipamento')}><BellOff size={12} /></span>
      )}
      
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

const nodeTypes = { custom: CustomNode, rack: RackNode, rackDevice: RackDeviceNode }
const edgeTypes = { smoothstep: SmoothStepEdge }
const defaultEdgeOptions = { animated: true, type: 'smoothstep', interactionWidth: 20 }

const calcularCorConexao = (sourceNode, targetNode) => {
  if (!sourceNode || !targetNode) return { stroke: '#64748b', color: '#64748b' }
  const isSourceOffline = sourceNode.data.status === 'offline';
  const isTargetOnline = targetNode.data.status === 'online';
  const isTargetOffline = targetNode.data.status === 'offline';
  const isTargetVisual = targetNode.data.status === 'visual';

  if (isTargetVisual) return { stroke: '#64748b', color: '#64748b' };
  if (isTargetOffline) return { stroke: '#ef4444', color: '#ef4444' };
  if (isSourceOffline && isTargetOnline) return { stroke: '#f59e0b', color: '#f59e0b' };
  return { stroke: '#10b981', color: '#10b981' };
}

// readOnly: trava a edição e esconde os pontos de conexão (modo visualização / TV).
// monitor: consulta o status mantido pelo backend (requer login e projectId). A página pública passa false.
function NetworkMapContent({ initialNodes = [], initialEdges = [], newEquipment = null, onMapUpdate, onAlertaQueda, readOnly = false, monitor = true, projectId = null, modelos = [], modelosProntos = true }) {
  const mapaModelos = useMemo(() => new Map(modelos.map(m => [m.id, m])), [modelos])
  const alturaDoEquipamento = (data) => mapaModelos.get(data.modeloId)?.altura_u || alturaPadrao(data.tipo)
  const [nodes, setNodes] = useState(initialNodes)
  const [edges, setEdges] = useState(initialEdges)
  const [selectedNode, setSelectedNode] = useState(null)
  const [selectedEdge, setSelectedEdge] = useState(null)
  
  const { screenToFlowPosition, getViewport } = useReactFlow()
  const statusAnterior = useRef({}) // Guarda o status anterior para saber se caiu
  const nodesRef = useRef(initialNodes)
  const monitoringRef = useRef(false)

  useEffect(() => { nodesRef.current = nodes }, [nodes])

  // Permite atualizar o mapa depois de importar um backup.
  useEffect(() => {
    setNodes(initialNodes)
    nodesRef.current = initialNodes
  }, [initialNodes])

  useEffect(() => { setEdges(initialEdges) }, [initialEdges])

  useEffect(() => {
    if (onMapUpdate) onMapUpdate(nodes, edges)
  }, [nodes, edges, onMapUpdate])

  useEffect(() => {
    setEdges((currentEdges) => 
      currentEdges.map((edge) => {
        const sourceNode = nodes.find(n => n.id === edge.source)
        const targetNode = nodes.find(n => n.id === edge.target)
        const corEsperada = calcularCorConexao(sourceNode, targetNode)
        if (edge.style?.stroke === corEsperada.stroke) return edge;
        return {
          ...edge, style: { ...edge.style, stroke: corEsperada.stroke, strokeWidth: 2.5 },
          markerEnd: { type: MarkerType.ArrowClosed, color: corEsperada.color }
        }
      })
    )
  }, [nodes, initialEdges])

  useEffect(() => {
    if (newEquipment && !readOnly) {
      let posicaoNoMapa = { x: 250, y: 250 }
      try {
        const centerX = window.innerWidth / 2
        const centerY = window.innerHeight / 2
        posicaoNoMapa = screenToFlowPosition({ x: centerX, y: centerY })
      } catch(e) { console.warn("Não foi possível centralizar o nó.") }

      const equipmentList = Array.isArray(newEquipment) ? newEquipment : [newEquipment]
      const timestamp = Date.now()
      const baseNodes = equipmentList.map((equipment, index) => ({
        id: `node_${equipment.id || `${timestamp}_${index}`}`,
        type: 'custom',
        position: { x: posicaoNoMapa.x + (index % 3) * 230, y: posicaoNoMapa.y + Math.floor(index / 3) * 110 },
        style: { width: 200, height: 80 },
        data: {
          label: equipment.nome,
          ip: equipment.ip,
          tipo: equipment.tipo,
          status: equipment.status || 'offline',
          pingTime: equipment.pingTime,
          monitorMode: equipment.monitorMode || 'ip',
          snmpConfig: equipment.snmpConfig || {},
          notificar: equipment.notificar !== false,
          us: equipment.us,
          modeloId: equipment.modeloId || null,
        },
        _rack: { id: equipment.rackId, u: equipment.rackU, altura: equipment.alturaU },
      }))
      setNodes((nds) => {
        const novos = []
        for (const { _rack, ...base } of baseNodes) {
          if (base.data.tipo === 'Rack') {
            const livre = posicaoADireita([...nds, ...novos])
            novos.push(noRack(livre ? { ...base, position: livre } : base))
            continue
          }
          const rack = _rack.id && [...nds, ...novos].find(n => n.id === _rack.id)
          if (rack) {
            const altura = _rack.altura || alturaDoEquipamento(base.data)
            const u = _rack.u || primeiraPosicaoLivre([...nds, ...novos], rack, altura)
            if (u) { novos.push(noMontado(base, rack, u, altura)); continue }
            toast.error(t('Sem espaço no rack para {nome}; adicionado fora do rack.', { nome: base.data.label }))
          }
          novos.push(base)
        }
        return normalizarRacks([...nds, ...novos])
      })
    }
  }, [newEquipment, screenToFlowPosition, getViewport, readOnly])

  // Status em tempo real: o backend monitora todos os equipamentos em segundo
  // plano; aqui só lemos o resultado (uma requisição leve a cada 5s, em vez de
  // um ping por equipamento a partir do navegador).
  useEffect(() => {
    if (!monitor || !projectId || projectId === 'novo') return
    let ativo = true
    const atualizar = async () => {
      if (monitoringRef.current) return
      monitoringRef.current = true
      try {
        const { equipamentos = [] } = await api.statusProjeto(projectId)
        if (!ativo) return
        const porId = new Map(equipamentos.map(e => [e.id, e]))
        // Detecta quedas fora do updater do setState (que deve ser puro).
        const quedas = []
        for (const node of nodesRef.current) {
          const atual = porId.get(node.id)
          if (!atual) continue
          if (statusAnterior.current[node.id] === 'online' && atual.status === 'offline') quedas.push(node.data.label)
          statusAnterior.current[node.id] = atual.status
        }
        setNodes((currentNodes) => {
          let mudou = false
          const proximos = currentNodes.map(node => {
            const atual = porId.get(node.id)
            if (!atual) return node // equipamento ainda não salvo
            if (atual.status === node.data.status && atual.ping_time === node.data.pingTime) return node
            mudou = true
            return { ...node, data: { ...node.data, status: atual.status, pingTime: atual.ping_time } }
          })
          return mudou ? proximos : currentNodes
        })
        if (quedas.length) {
          new Audio('/alert.mp3').play().catch(() => console.log("Navegador bloqueou o som. Interaja com a página primeiro."))
          if (onAlertaQueda) onAlertaQueda(quedas.length === 1 ? t('O equipamento {nome} caiu!', { nome: quedas[0] }) : t('{n} equipamentos caíram: {nomes}', { n: quedas.length, nomes: quedas.join(', ') }))
        }
      } catch (error) {
        console.warn(error.message)
      } finally {
        monitoringRef.current = false
      }
    }
    atualizar()
    const interval = setInterval(atualizar, 5000)
    return () => { ativo = false; clearInterval(interval) }
  }, [onAlertaQueda, monitor, projectId])

  // Ao entrar no modo visualização, limpa seleção e fecha modais abertos.
  useEffect(() => {
    if (!readOnly) return
    setSelectedNode(null)
    setSelectedEdge(null)
    setNodes((nds) => nds.some(n => n.selected) ? nds.map(n => n.selected ? { ...n, selected: false } : n) : nds)
    setEdges((eds) => eds.some(e => e.selected) ? eds.map(e => e.selected ? { ...e, selected: false } : e) : eds)
  }, [readOnly])

  const onNodesChange = useCallback((changes) => setNodes((nds) => {
    const ajustadas = changes.map(c => {
      if (c.type === 'position' && c.position) {
        const n = nds.find(x => x.id === c.id)
        if (n?.type === 'rackDevice') return { ...c, position: { ...c.position, x: TRILHO } }
      }
      return c
    })
    const resultado = applyNodeChanges(ajustadas, nds)
    // Se um rack foi apagado (tecla Delete), solta os equipamentos que estavam nele.
    return changes.some(c => c.type === 'remove') ? normalizarRacks(resultado) : resultado
  }), [])

  // Encaixe ao soltar: dentro do rack encaixa no U livre mais próximo; um equipamento
  // solto em cima de um rack é montado nele.
  const onNodeDragStop = useCallback((event, node) => {
    if (readOnly) return
    const atuais = nodesRef.current
    if (node.type === 'rackDevice') {
      const rack = atuais.find(n => n.id === node.parentNode)
      if (!rack) return
      const desejado = uPelaPosicao(node.position.y, node.data.alturaU, rack.data.us)
      const u = posicaoLivreMaisProxima(atuais, rack, desejado, node.data.alturaU, node.id) ?? node.data.rackU
      if (u !== desejado) toast(t('Posição ocupada: encaixado no U livre mais próximo.'), { icon: '🧲' })
      setNodes(nds => normalizarRacks(nds.map(n => n.id === node.id ? { ...n, data: { ...n.data, rackU: u } } : n)))
      return
    }
    if (node.type !== 'custom') return
    const largura = node.width || node.style?.width || 200
    const altura = node.height || node.style?.height || 80
    const centro = { x: node.position.x + largura / 2, y: node.position.y + altura / 2 }
    const rack = rackNoPonto(atuais.filter(n => n.id !== node.id), centro)
    if (!rack) return
    const alturaU = alturaDoEquipamento(node.data)
    const desejado = uPelaPosicao(centro.y - rack.position.y - (alturaU * U_PX) / 2, alturaU, rack.data.us)
    const u = posicaoLivreMaisProxima(atuais, rack, desejado, alturaU, node.id)
    if (u == null) { toast.error(t('Não há {u}U livres no rack {rack}.', { u: alturaU, rack: rack.data.label })); return }
    setNodes(nds => normalizarRacks(nds.map(n => n.id === node.id ? noMontado(n, rack, u, alturaU) : n)))
    toast.success(t('{nome} montado no {rack} ({faixa})', { nome: node.data.label, rack: rack.data.label, faixa: `U${u}${alturaU > 1 ? `-${u + alturaU - 1}` : ''}` }))
  }, [readOnly, mapaModelos])

  // Cabos presos a portas que deixaram de existir (equipamento saiu do rack, trocou de
  // modelo, etc.) voltam para o ponto lateral, em vez de sumirem do mapa.
  useEffect(() => {
    if (!modelosProntos) return // sem os modelos, as portas reais ainda não são conhecidas
    const porId = new Map(nodes.map(n => [n.id, n]))
    setEdges(eds => {
      let mudou = false
      const corrigidas = eds.map(e => {
        const validosOrigem = handlesDoNo(porId.get(e.source), mapaModelos)
        const validosDestino = handlesDoNo(porId.get(e.target), mapaModelos)
        const origemOk = !e.sourceHandle || !validosOrigem.size || validosOrigem.has(e.sourceHandle)
        const destinoOk = !e.targetHandle || !validosDestino.size || validosDestino.has(e.targetHandle)
        const sourceHandle = origemOk ? e.sourceHandle : 'right'
        const targetHandle = destinoOk ? e.targetHandle : 'left'
        // Patch cord ligado em porta fica na frente dos equipamentos, como num rack real.
        const zIndex = ehPorta(sourceHandle) || ehPorta(targetHandle) ? 1 : undefined
        if (origemOk && destinoOk && e.zIndex === zIndex) return e
        mudou = true
        return { ...e, sourceHandle, targetHandle, zIndex }
      })
      return mudou ? corrigidas : eds
    })
  }, [nodes, mapaModelos, modelosProntos])
  const onEdgesChange = useCallback((changes) => setEdges((eds) => applyEdgeChanges(changes, eds)), [])
  
  const portaOcupada = (nodeId, handle, ignorarEdgeId = null) => ehPorta(handle) && edges.some(e => e.id !== ignorarEdgeId &&
    ((e.source === nodeId && e.sourceHandle === handle) || (e.target === nodeId && e.targetHandle === handle)))
  const nomePortaNo = (nodeId, handle) => {
    const n = nodes.find(x => x.id === nodeId)
    return n ? `${n.data.label} · ${nomeDaPorta(handle, portasDoEquipamento(n.data, mapaModelos.get(n.data.modeloId)))}` : handle
  }

  const onConnect = useCallback((params) => {
    if (readOnly) return
    for (const [no, handle] of [[params.source, params.sourceHandle], [params.target, params.targetHandle]]) {
      if (portaOcupada(no, handle)) { toast.error(t('{porta} já tem um cabo conectado.', { porta: nomePortaNo(no, handle) })); return }
    }
    const sourceNode = nodes.find(n => n.id === params.source)
    const targetNode = nodes.find(n => n.id === params.target)
    const cor = calcularCorConexao(sourceNode, targetNode)

    setEdges((eds) => addEdge({ 
      ...params, ...defaultEdgeOptions,
      style: { stroke: cor.stroke, strokeWidth: 2.5 },
      markerEnd: { type: MarkerType.ArrowClosed, color: cor.color },
    }, eds))
  }, [nodes, edges, readOnly, mapaModelos])

  const onNodeClick = (event, node) => { if (!readOnly) setSelectedNode(node) }
  const onEdgeClick = (event, edge) => { if (!readOnly) setSelectedEdge(edge) }
  const onReconnect = useCallback((oldEdge, newConnection) => { if (!readOnly) setEdges((eds) => reconnectEdge(oldEdge, newConnection, eds)) }, [readOnly])
  
  const onEdgeMouseEnter = (event, edge) => !readOnly && setEdges((eds) => eds.map((e) => e.id === edge.id ? { ...e, style: { ...e.style, strokeWidth: 4 } } : e))
  const onEdgeMouseLeave = (event, edge) => !readOnly && setEdges((eds) => eds.map((e) => e.id === edge.id ? { ...e, style: { ...e.style, strokeWidth: 2.5 } } : e))

  const handleUpdateNode = (id, newData) => {
    if (readOnly) return
    const { rackId, rackU, alturaU, us, ...dados } = newData
    setNodes((nds) => {
      const alvo = nds.find(n => n.id === id)
      if (!alvo) return nds
      let novo = { ...alvo, data: { ...alvo.data, ...dados } }
      if (alvo.type === 'rack') {
        novo = noRack({ ...novo, data: { ...novo.data, us: us || alvo.data.us } })
      } else if (rackId) {
        const rack = nds.find(n => n.id === rackId)
        if (rack) novo = noMontado(novo, rack, rackU, alturaU)
      } else if (alvo.parentNode && 'rackId' in newData) {
        novo = noLivre(novo, nds.find(n => n.id === alvo.parentNode))
      }
      return normalizarRacks(nds.map(n => n.id === id ? novo : n))
    })
    setSelectedNode(null)
  }
  const handleDeleteNode = (id) => {
    if (readOnly) return
    // Excluir um rack exclui também os equipamentos montados nele.
    const removidos = new Set([id, ...nodesRef.current.filter(n => n.parentNode === id).map(n => n.id)])
    setNodes((nds) => normalizarRacks(nds.filter((node) => !removidos.has(node.id))))
    setEdges((eds) => eds.filter((edge) => !removidos.has(edge.source) && !removidos.has(edge.target)))
    setSelectedNode(null)
  }
  
  const handleUpdateEdge = (id, newLabel, newSource, newTarget, sourceHandle, targetHandle) => {
    if (readOnly) return;
    for (const [no, handle] of [[newSource, sourceHandle], [newTarget, targetHandle]]) {
      if (portaOcupada(no, handle, id)) { toast.error(t('{porta} já tem outro cabo conectado.', { porta: nomePortaNo(no, handle) })); return }
    }
    setEdges((eds) => eds.map((edge) => {
      if (edge.id === id) {
        const sourceNode = nodes.find(n => n.id === newSource)
        const targetNode = nodes.find(n => n.id === newTarget)
        const cor = calcularCorConexao(sourceNode, targetNode)
        return { ...edge, source: newSource, target: newTarget, label: newLabel,
          sourceHandle: sourceHandle ?? edge.sourceHandle, targetHandle: targetHandle ?? edge.targetHandle, labelStyle: { fill: 'white', fontWeight: 'bold' }, labelBgStyle: { fill: '#1e293b' }, style: { stroke: cor.stroke, strokeWidth: 2.5 }, markerEnd: { type: MarkerType.ArrowClosed, color: cor.color } }
      }
      return edge
    }))
    setSelectedEdge(null)
  }
  const handleDeleteEdge = (id) => { if (!readOnly) { setEdges((eds) => eds.filter((edge) => edge.id !== id)); setSelectedEdge(null) } }

  return (
    <ModelosContext.Provider value={mapaModelos}>
      <ReactFlow
        className={readOnly ? 'netmap-readonly' : ''}
        nodes={nodes} edges={edges} nodeTypes={nodeTypes} edgeTypes={edgeTypes}
        defaultEdgeOptions={defaultEdgeOptions} onNodesChange={onNodesChange} onEdgesChange={onEdgesChange}
        onConnect={onConnect} onNodeClick={onNodeClick} onEdgeClick={onEdgeClick}
        onEdgeMouseEnter={onEdgeMouseEnter} onEdgeMouseLeave={onEdgeMouseLeave}
        onReconnect={onReconnect} onNodeDragStop={onNodeDragStop} nodesConnectable={!readOnly} nodesDraggable={!readOnly}
        elementsSelectable={!readOnly} edgesUpdatable={!readOnly} nodesFocusable={!readOnly} edgesFocusable={!readOnly} deleteKeyCode={readOnly ? null : 'Backspace'}
        reconnectRadius={20} connectionRadius={18} connectionMode="loose" fitView
      >
        <Background />
        <Controls showInteractive={!readOnly} />
      </ReactFlow>

      {selectedNode && <EquipmentModal node={selectedNode} nodes={nodes} modelos={modelos} onClose={() => setSelectedNode(null)} onUpdate={handleUpdateNode} onDelete={handleDeleteNode} />}
      {selectedEdge && <EdgeModal edge={selectedEdge} nodes={nodes} edges={edges} modelos={mapaModelos} onClose={() => setSelectedEdge(null)} onUpdate={handleUpdateEdge} onDelete={handleDeleteEdge} />}
    </ModelosContext.Provider>
  )
}

export default function NetworkMap(props) {
  useI18n()
  return (
    <ReactFlowProvider>
      <NetworkMapContent {...props} />
    </ReactFlowProvider>
  )
}
