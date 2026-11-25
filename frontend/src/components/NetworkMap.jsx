import { useCallback, useState, useEffect, memo, useRef, useMemo } from 'react'
import ReactFlow, {
  Controls, Background, applyNodeChanges, applyEdgeChanges, addEdge, MarkerType, Handle, Position, NodeResizer, reconnectEdge, SmoothStepEdge, useReactFlow, ReactFlowProvider
} from 'reactflow'
import { Server, Wifi, Shield, Monitor, Activity, BellOff, Wrench, Eye, Printer, Cctv, RadioTower, CircleHelp, Thermometer, Cpu, Map as IconeMapa, CheckCircle2, XCircle, ExternalLink, Lock, Globe } from 'lucide-react'
import { useNavigate } from 'react-router-dom'
import { classeStatus, dadosDeAlerta, calcularUplinks, TIPO_ATALHO } from '../utils/mapa'
import EquipmentModal from './Modals/EquipmentModal'
import EdgeModal from './Modals/EdgeModal'
import MetricasModal from './Modals/MetricasModal'
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

// Atalho para outro mapa: mostra o resumo ao vivo do mapa de destino (vermelho se algo caiu lá).
function NoAtalho({ data, selected }) {
  const r = data.resumoMapa
  const alerta = r && !r.removido && r.offline > 0
  const alca = { background: '#3b82f6', width: '12px', height: '12px' }
  return (
    <div className={`custom-node no-atalho ${alerta ? 'atalho-alerta' : ''}`} style={{ width: '100%', height: '100%' }}
      title={r?.removido ? t('O mapa de destino foi excluído.') : t('Duplo clique para abrir o mapa {nome}', { nome: r?.nome || data.label })}>
      <NodeResizer minWidth={140} minHeight={60} isVisible={selected} lineStyle={{ borderColor: '#3b82f6', borderWidth: '2px' }} handleStyle={{ backgroundColor: '#3b82f6', width: '8px', height: '8px' }} />
      <Handle type="source" position={Position.Top} id="top" style={alca} />
      <Handle type="source" position={Position.Left} id="left" style={alca} />
      <IconeMapa size={20} color={alerta ? '#f87171' : '#818cf8'} />
      <div style={{ display: 'flex', flexDirection: 'column', overflow: 'hidden', paddingRight: '10px' }}>
        <div style={{ fontWeight: 'bold', fontSize: '14px', textOverflow: 'ellipsis', whiteSpace: 'nowrap', overflow: 'hidden', display: 'flex', alignItems: 'center', gap: 5 }}>
          {data.label} <ExternalLink size={11} color="#64748b" />
        </div>
        {!r ? <div style={{ fontSize: '11px', color: '#64748b' }}>{t('Sem mapa de destino')}</div>
          : r.removido ? <div style={{ fontSize: '11px', color: '#f59e0b' }}>{t('Mapa removido')}</div>
          : <div style={{ fontSize: '12px', display: 'flex', gap: '10px', marginTop: 3 }}>
              <span style={{ display: 'flex', alignItems: 'center', gap: 3, color: '#10b981' }}><CheckCircle2 size={12} /> {r.online}</span>
              <span style={{ display: 'flex', alignItems: 'center', gap: 3, color: r.offline ? '#ef4444' : '#64748b', fontWeight: r.offline ? 'bold' : 'normal' }}><XCircle size={12} /> {r.offline}</span>
            </div>}
      </div>
      <Handle type="source" position={Position.Bottom} id="bottom" style={alca} />
      <Handle type="source" position={Position.Right} id="right" style={alca} />
    </div>
  )
}

const CustomNode = memo(({ data, selected }) => {
  useI18n()
  if (data.tipo === TIPO_ATALHO) return <NoAtalho data={data} selected={selected} />
  const getIcon = () => {
    switch (data.tipo) {
      case 'Roteador': return <Wifi size={18} color="#3b82f6" />
      case 'Firewall': return <Shield size={18} color="#f59e0b" />
      case 'PC': return <Monitor size={18} color="#94a3b8" />
      case 'Access Point': return <RadioTower size={18} color="#22d3ee" />
      case 'Impressora': return <Printer size={18} color="#a78bfa" />
      case 'Câmera': return <Cctv size={18} color="#f472b6" />
      case 'Outro': return <CircleHelp size={18} color="#94a3b8" />
      default: return <Server size={18} color="#10b981" />
    }
  }

  return (
    <div className="custom-node" style={{ width: '100%', height: '100%' }}>
      <NodeResizer minWidth={120} minHeight={60} isVisible={selected} lineStyle={{ borderColor: '#3b82f6', borderWidth: '2px' }} handleStyle={{ backgroundColor: '#3b82f6', width: '8px', height: '8px' }} keepAspectRatio={false} />
      
      <Handle type="source" position={Position.Top} id="top" style={{ background: '#3b82f6', width: '12px', height: '12px' }} />
      <Handle type="source" position={Position.Left} id="left" style={{ background: '#3b82f6', width: '12px', height: '12px' }} />
      
      <div className={`status-dot status-${classeStatus(data)}`}
        title={data.inalcancavelPor ? t('Inalcançável: {nome} (uplink) está offline', { nome: data.inalcancavelNome }) : undefined} />
      {data.reconhecido && data.status === 'offline' && (
        <span className="node-reconhecido" title={t('{usuario} está cuidando desde {hora}', { usuario: data.reconhecido.usuario, hora: new Date(data.reconhecido.em).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }) }) + (data.reconhecido.nota ? `: ${data.reconhecido.nota}` : '')}>
          <Eye size={12} />
        </span>
      )}
      {data.manutencaoAte ? (
        <span className="node-sem-alerta node-manutencao" title={t('Em manutenção até {hora} (alertas silenciados)', { hora: new Date(data.manutencaoAte).toLocaleString() })}><Wrench size={12} /></span>
      ) : data.notificar === false && data.status !== 'visual' && (
        <span className="node-sem-alerta" title={t('Notificações desligadas para este equipamento')}><BellOff size={12} /></span>
      )}
      
      {getIcon()}
      <div style={{ display: 'flex', flexDirection: 'column', overflow: 'hidden', paddingRight: '10px' }}>
        <div style={{ fontWeight: 'bold', fontSize: '14px', textOverflow: 'ellipsis', whiteSpace: 'nowrap', overflow: 'hidden' }}>{data.label}</div>
        <div style={{ fontSize: '11px', color: '#94a3b8' }}>{data.ip}</div>
        
        {((data.status === 'online' && (data.pingTime || data.snmp)) || data.http?.certificado?.dias != null || (data.monitorMode === 'http' && data.status === 'offline' && data.http?.error)) && (
          <div style={{ fontSize: '10px', color: '#10b981', display: 'flex', alignItems: 'center', gap: '6px', marginTop: '2px', whiteSpace: 'nowrap' }}>
            {data.status === 'online' && data.pingTime ? <span style={{ display: 'flex', alignItems: 'center', gap: '3px' }}><Activity size={10} /> {data.pingTime}ms</span> : null}
            {data.monitorMode === 'http' && data.status === 'offline' && data.http?.error && (
              <span className="metrica-no" style={{ color: '#f87171' }} title={data.http.url || ''}><Globe size={10} /> {data.http.http_status ? `HTTP ${data.http.http_status}` : t(data.http.error)}</span>
            )}
            {data.http?.certificado?.dias != null && (
              <span className="metrica-no" style={{ color: corCertificado(data.http.certificado.dias) }}
                title={t('Certificado TLS vence em {data} ({emissor})', { data: new Date(data.http.certificado.expira_em).toLocaleDateString(), emissor: data.http.certificado.emissor || '?' })}>
                <Lock size={10} /> {data.http.certificado.dias < 0 ? t('vencido') : `${data.http.certificado.dias}d`}
              </span>
            )}
            {data.snmp?.temp != null && <span className="metrica-no" title={t('Temperatura')}><Thermometer size={10} /> {Math.round(data.snmp.temp)}°</span>}
            {data.snmp?.cpu != null && <span className="metrica-no" title={t('CPU')}><Cpu size={10} /> {Math.round(data.snmp.cpu)}%</span>}
          </div>
        )}
      </div>
      
      <Handle type="source" position={Position.Bottom} id="bottom" style={{ background: '#3b82f6', width: '12px', height: '12px' }} />
      <Handle type="source" position={Position.Right} id="right" style={{ background: '#3b82f6', width: '12px', height: '12px' }} />
    </div>
  )
})

function corCertificado(dias) {
  if (dias < 0) return '#ef4444'
  if (dias <= 14) return '#f59e0b'
  return '#cbd5e1'
}

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
function NetworkMapContent({ initialNodes = [], initialEdges = [], newEquipment = null, onMapUpdate, onAlertaQueda, onStatusProjeto, onAbrirMapa, readOnly = false, monitor = true, projectId = null, modelos = [], modelosProntos = true, mostrarCabosPorta = true, foco = null }) {
  const mapaModelos = useMemo(() => new Map(modelos.map(m => [m.id, m])), [modelos])
  const alturaDoEquipamento = (data) => mapaModelos.get(data.modeloId)?.altura_u || alturaPadrao(data.tipo)
  const [nodes, setNodes] = useState(initialNodes)
  const [edges, setEdges] = useState(initialEdges)
  const [selectedNode, setSelectedNode] = useState(null)
  const [selectedEdge, setSelectedEdge] = useState(null)
  
  const { screenToFlowPosition, getViewport, fitView } = useReactFlow()
  const [hoverId, setHoverId] = useState(null)   // equipamento sob o mouse (destaca seus cabos)
  const [destaqueId, setDestaqueId] = useState(null) // equipamento escolhido na busca (pisca)
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
          mapaDestinoId: equipment.mapaDestinoId || null,
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
        const resposta = await api.statusProjeto(projectId)
        const { equipamentos = [] } = resposta
        if (!ativo) return
        if (onStatusProjeto) onStatusProjeto(resposta)
        const porId = new Map(equipamentos.map(e => [e.id, e]))
        const nomePorId = new Map(nodesRef.current.map(n => [n.id, n.data?.label]))
        // Detecta quedas fora do updater do setState (que deve ser puro).
        const quedas = []
        for (const node of nodesRef.current) {
          const atual = porId.get(node.id)
          if (!atual) continue
          // Inalcançáveis (uplink caiu) e equipamentos em manutenção não tocam o alarme.
          if (statusAnterior.current[node.id] === 'online' && atual.status === 'offline' && !atual.inalcancavel_por && !atual.manutencao_ate && !resposta.manutencao_ate) quedas.push(node.data.label)
          statusAnterior.current[node.id] = atual.status
        }
        setNodes((currentNodes) => {
          let mudou = false
          const proximos = currentNodes.map(node => {
            const atual = porId.get(node.id)
            if (!atual) return node // equipamento ainda não salvo
            const alerta = dadosDeAlerta(atual, nomePorId)
            if (atual.status === node.data.status && atual.ping_time === node.data.pingTime &&
                alerta.inalcancavelPor === (node.data.inalcancavelPor || null) && alerta.manutencaoAte === (node.data.manutencaoAte || null) &&
                alerta.snmp?.coletado_em === node.data.snmp?.coletado_em &&
                JSON.stringify(alerta.reconhecido) === JSON.stringify(node.data.reconhecido || null) &&
                JSON.stringify(alerta.http) === JSON.stringify(node.data.http || null) &&
                JSON.stringify(alerta.resumoMapa) === JSON.stringify(node.data.resumoMapa || null)) return node
            mudou = true
            return { ...node, data: { ...node.data, status: atual.status, pingTime: atual.ping_time, ...alerta } }
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
  }, [onAlertaQueda, onStatusProjeto, monitor, projectId])

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
    if (node.type !== 'custom' || node.data?.tipo === TIPO_ATALHO) return  // atalhos não vão para dentro de racks
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

  // Busca: centraliza o equipamento escolhido e faz ele piscar.
  useEffect(() => {
    if (!foco?.id) return
    fitView({ nodes: [{ id: foco.id }], duration: 600, maxZoom: 1.6, padding: 0.8 })
    setDestaqueId(foco.id)
    const fim = setTimeout(() => setDestaqueId(null), 2600)
    return () => clearTimeout(fim)
  }, [foco, fitView])

  // O que é desenhado (sem alterar o mapa salvo):
  // - cabos entre portas podem ser ocultados pelo botão da barra superior;
  // - passar o mouse num equipamento acende os cabos dele (e revela os ocultos) e esmaece o resto.
  const vizinhos = useMemo(() => {
    if (!hoverId) return null
    const set = new Set([hoverId])
    for (const e of edges) { if (e.source === hoverId) set.add(e.target); if (e.target === hoverId) set.add(e.source) }
    return set
  }, [hoverId, edges])

  const edgesExibidas = useMemo(() => edges.map(e => {
    const ligado = hoverId && (e.source === hoverId || e.target === hoverId)
    const ehCaboPorta = ehPorta(e.sourceHandle) || ehPorta(e.targetHandle)
    let ne = e
    if (ehCaboPorta && !mostrarCabosPorta && !ligado) ne = { ...ne, hidden: true }
    if (hoverId) {
      const op = ligado ? 1 : 0.12
      ne = { ...ne, zIndex: ligado ? 6 : ne.zIndex, animated: ligado || ne.animated,
        style: { ...ne.style, opacity: op, strokeWidth: ligado ? 3.5 : (ne.style?.strokeWidth || 2.5) },
        labelStyle: { ...(ne.labelStyle || {}), opacity: op }, labelBgStyle: { ...(ne.labelBgStyle || {}), opacity: op } }
    }
    return ne
  }), [edges, mostrarCabosPorta, hoverId])

  const nodesExibidos = useMemo(() => {
    if (!vizinhos && !destaqueId) return nodes
    return nodes.map(n => {
      const classes = []
      if (vizinhos && n.type !== 'rack' && !vizinhos.has(n.id)) classes.push('no-esmaecido')
      if (n.id === destaqueId) classes.push('no-destaque')
      return classes.length ? { ...n, className: classes.join(' ') } : n
    })
  }, [nodes, vizinhos, destaqueId])

  const onNodeMouseEnter = useCallback((event, node) => { if (node.type !== 'rack') setHoverId(node.id) }, [])
  const onNodeMouseLeave = useCallback(() => setHoverId(null), [])

  const [metricasNode, setMetricasNode] = useState(null)
  const navigate = useNavigate()
  const autenticado = projectId && projectId !== 'novo' // a página pública (TV) não navega entre mapas
  const abrirAtalho = (node) => {
    const destino = node.data?.mapaDestinoId
    if (!destino || node.data?.resumoMapa?.removido) return false
    if (onAbrirMapa) onAbrirMapa(destino)
    else navigate(`/editor/${destino}`)
    return true
  }
  // No modo leitura (ex.: visualizador, TV), clicar abre o atalho ou as métricas SNMP.
  const timerClique = useRef(null)
  const onNodeClick = (event, node) => {
    if (!readOnly) {
      // Atalho: espera um instante para o duplo clique (abrir o mapa) não abrir o modal de edição antes.
      clearTimeout(timerClique.current)
      if (node.data?.tipo === TIPO_ATALHO) timerClique.current = setTimeout(() => setSelectedNode(node), 250)
      else setSelectedNode(node)
      return
    }
    if (!autenticado) return
    if (node.data?.tipo === TIPO_ATALHO) abrirAtalho(node)
    else if (node.data?.monitorMode === 'snmpv3') setMetricasNode(node)
  }
  // Duplo clique num atalho abre o mapa de destino também no modo edição.
  const onNodeDoubleClick = (event, node) => {
    clearTimeout(timerClique.current)
    if (autenticado && node.data?.tipo === TIPO_ATALHO && abrirAtalho(node)) setSelectedNode(null)
  }
  const onEdgeClick = (event, edge) => { if (!readOnly) setSelectedEdge(edges.find(e => e.id === edge.id) || edge) }
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
  // Define o uplink de todos os equipamentos percorrendo os cabos a partir da raiz escolhida.
  const handleCalcularUplinks = (raizId) => {
    if (readOnly) return
    const pais = calcularUplinks(nodesRef.current, edges, raizId)
    const definidos = [...pais.values()].filter(Boolean).length
    if (!definidos) { toast.error(t('Nenhum equipamento ligado por cabo a este.')); return }
    const semCaminho = nodesRef.current.filter(n => n.type !== 'rack' && !pais.has(n.id)).length
    if (!window.confirm(t('Definir o uplink de {n} equipamento(s) a partir dos cabos? Os uplinks atuais deles serão substituídos.', { n: definidos }))) return
    setNodes((nds) => nds.map(n => pais.has(n.id) ? { ...n, data: { ...n.data, dependeDe: pais.get(n.id) } } : n))
    setSelectedNode(null)
    toast.success(t('{n} uplink(s) definidos. Salve o mapa para aplicar.', { n: definidos }) + (semCaminho ? ' ' + t('{n} equipamento(s) sem cabo até a raiz ficaram como estavam.', { n: semCaminho }) : ''), { duration: 6000 })
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
        nodes={nodesExibidos} edges={edgesExibidas} nodeTypes={nodeTypes} edgeTypes={edgeTypes}
        onNodeMouseEnter={onNodeMouseEnter} onNodeMouseLeave={onNodeMouseLeave}
        defaultEdgeOptions={defaultEdgeOptions} onNodesChange={onNodesChange} onEdgesChange={onEdgesChange}
        onConnect={onConnect} onNodeClick={onNodeClick} onNodeDoubleClick={onNodeDoubleClick} onEdgeClick={onEdgeClick}
        onEdgeMouseEnter={onEdgeMouseEnter} onEdgeMouseLeave={onEdgeMouseLeave}
        onReconnect={onReconnect} onNodeDragStop={onNodeDragStop} nodesConnectable={!readOnly} nodesDraggable={!readOnly}
        elementsSelectable={!readOnly} edgesUpdatable={!readOnly} nodesFocusable={!readOnly} edgesFocusable={!readOnly} deleteKeyCode={readOnly ? null : 'Backspace'}
        reconnectRadius={20} connectionRadius={18} connectionMode="loose" fitView
      >
        <Background />
        <Controls showInteractive={!readOnly} />
      </ReactFlow>

      {metricasNode && <MetricasModal projectId={projectId} node={metricasNode} onClose={() => setMetricasNode(null)} />}
      {selectedNode && <EquipmentModal node={selectedNode} nodes={nodes} modelos={modelos} projectId={projectId} onCalcularUplinks={handleCalcularUplinks}
        onAbrirMetricas={(n) => { setSelectedNode(null); setMetricasNode(n) }} onAbrirAtalho={(n) => { setSelectedNode(null); abrirAtalho(n) }} onClose={() => setSelectedNode(null)} onUpdate={handleUpdateNode} onDelete={handleDeleteNode} />}
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
