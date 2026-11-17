// Conversão entre o formato da API e os nós/conexões do React Flow.
// Usado pelo Editor e pela página pública, para que os dois desenhem igual.
import { noRack, noMontado, normalizarRacks } from '../components/rack/rackUtils'

// Estado de alerta vindo da API: inalcançável (uplink offline) e manutenção.
export function dadosDeAlerta(eq, nomePorId) {
  const causa = eq.inalcancavel_por || null
  return {
    inalcancavelPor: causa, inalcancavelNome: causa ? (nomePorId.get(causa) || causa) : null,
    manutencaoAte: eq.manutencao_ate || null,
  }
}

export function equipamentosParaNodes(equipamentos) {
  const nomePorId = new Map(equipamentos.map(eq => [eq.id, eq.nome]))
  const base = equipamentos.map(eq => ({
    id: eq.id, type: 'custom', position: { x: eq.pos_x, y: eq.pos_y },
    style: { width: eq.width, height: eq.height },
    data: {
      label: eq.nome, ip: eq.ip, tipo: eq.tipo, status: eq.status, pingTime: eq.ping_time,
      monitorMode: eq.monitor_mode || 'ip', snmpConfig: eq.monitor_config || {},
      notificar: eq.notificar !== false,
      modeloId: eq.modelo_id || null,
      dependeDe: eq.depende_de || null,
      ...dadosDeAlerta(eq, nomePorId),
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

// Classe do status para desenhar: offline por causa do uplink vira "inalcançável" (âmbar).
export function classeStatus(data) {
  if (data.status === 'visual') return 'visual'
  if (data.status === 'online') return 'online'
  return data.inalcancavelPor ? 'inalcancavel' : 'offline'
}

// Uplinks calculados pelos cabos: busca em largura a partir da raiz (ex.: firewall/roteador).
// Cada equipamento passa a depender do vizinho pelo qual foi alcançado. Racks são ignorados.
export function calcularUplinks(nodes, edges, raizId) {
  const validos = new Set(nodes.filter(n => n.type !== 'rack').map(n => n.id))
  const vizinhos = new Map([...validos].map(id => [id, []]))
  for (const e of edges) {
    if (validos.has(e.source) && validos.has(e.target) && e.source !== e.target) {
      vizinhos.get(e.source).push(e.target)
      vizinhos.get(e.target).push(e.source)
    }
  }
  const pai = new Map([[raizId, null]])
  const fila = [raizId]
  while (fila.length) {
    const atual = fila.shift()
    for (const v of vizinhos.get(atual) || []) {
      if (!pai.has(v)) { pai.set(v, atual); fila.push(v) }
    }
  }
  return pai // Map id -> uplink (a raiz fica com null; quem não foi alcançado não aparece)
}

export function conexoesParaEdges(conexoes) {
  return conexoes.map(conn => ({
    id: conn.id, source: conn.source, target: conn.target, label: conn.label,
    sourceHandle: conn.source_handle, targetHandle: conn.target_handle,
    type: 'smoothstep', animated: true, interactionWidth: 20,
    style: { stroke: '#3b82f6', strokeWidth: 2.5 }, markerEnd: { type: 'arrowclosed', color: '#3b82f6' },
    // Mesmo estilo de rótulo usado ao editar o cabo (antes, ao recarregar, o fundo ficava branco).
    labelStyle: { fill: 'white', fontWeight: 'bold' }, labelBgStyle: { fill: '#1e293b' },
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
    dependeDe: rack ? null : (node.data.dependeDe || null),
  }
}
