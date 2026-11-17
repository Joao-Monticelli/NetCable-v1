// Conversão entre o formato da API e os nós/conexões do React Flow.
// Usado pelo Editor e pela página pública, para que os dois desenhem igual.
import { noRack, noMontado, normalizarRacks } from '../components/rack/rackUtils'

export function equipamentosParaNodes(equipamentos) {
  const base = equipamentos.map(eq => ({
    id: eq.id, type: 'custom', position: { x: eq.pos_x, y: eq.pos_y },
    style: { width: eq.width, height: eq.height },
    data: {
      label: eq.nome, ip: eq.ip, tipo: eq.tipo, status: eq.status, pingTime: eq.ping_time,
      monitorMode: eq.monitor_mode || 'ip', snmpConfig: eq.monitor_config || {},
      notificar: eq.notificar !== false,
      modeloId: eq.modelo_id || null,
    },
    _rack: { id: eq.rack_id, u: eq.rack_u, altura: eq.altura_u },
  }))
  const racks = new Map()
  for (const n of base) {
    if (n.data.tipo === 'Rack') racks.set(n.id, noRack({ ...n, data: { ...n.data, us: n._rack.altura || 12 } }))
  }
  const nodes = base.map(({ _rack, ...n }) => {
    if (racks.has(n.id)) return racks.get(n.id)
    const rack = _rack.id && racks.get(_rack.id)
    if (rack && _rack.u && _rack.altura) return noMontado(n, rack, _rack.u, _rack.altura)
    return n
  })
  return normalizarRacks(nodes)
}

export function conexoesParaEdges(conexoes) {
  return conexoes.map(conn => ({
    id: conn.id, source: conn.source, target: conn.target, label: conn.label,
    sourceHandle: conn.source_handle, targetHandle: conn.target_handle,
    type: 'smoothstep', animated: true, interactionWidth: 20,
    style: { stroke: '#3b82f6', strokeWidth: 2.5 }, markerEnd: { type: 'arrowclosed', color: '#3b82f6' },
  }))
}

export function nodeParaEquipamento(node) {
  const rack = node.type === 'rack'
  return {
    id: node.id, nome: node.data.label, ip: node.data.ip, tipo: node.data.tipo, status: node.data.status,
    pingTime: node.data.pingTime || null, posX: node.position.x, posY: node.position.y,
    width: node.style?.width || 200, height: node.style?.height || 80,
    monitorMode: node.data.monitorMode || 'ip', monitorConfig: node.data.snmpConfig || null,
    notificar: node.data.notificar !== false,
    rackId: node.parentNode || null,
    rackU: node.parentNode ? node.data.rackU : null,
    alturaU: rack ? node.data.us : (node.parentNode ? node.data.alturaU : null),
    modeloId: rack ? null : (node.data.modeloId || null),
  }
}
