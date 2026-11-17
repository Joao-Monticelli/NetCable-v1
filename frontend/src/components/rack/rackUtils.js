// Geometria e regras dos racks.
// U são numerados de baixo para cima (U1 = base), como nos racks reais.
// Um equipamento montado ocupa de rackU (U mais baixo) até rackU + alturaU - 1.

export const U_PX = 28          // altura de 1U na tela
export const RACK_LARGURA = 440 // largura total do gabinete
export const TRILHO = 30        // largura de cada trilho lateral (numeração dos U)
export const TOPO = 34          // cabeçalho com o nome do rack
export const BASE = 14          // rodapé do gabinete
export const LARGURA_EQUIP = RACK_LARGURA - 2 * TRILHO

export const TAMANHOS_RACK = [4, 6, 9, 12, 16, 20, 24, 32, 42, 44, 48]
export const ALTURAS_EQUIP = [1, 2, 3, 4, 5, 6, 8]

export const TIPOS = [
  'Roteador', 'Switch Gerenciável', 'Switch Não Gerenciável', 'Firewall', 'Servidor',
  'Storage/NAS', 'Patch Panel', 'Nobreak', 'Organizador de Cabos', 'PC',
]

// Altura padrão (em U) de cada tipo ao montar no rack.
const ALTURA_PADRAO = {
  'Servidor': 2, 'Storage/NAS': 2, 'Nobreak': 2, 'PC': 4,
}
export const alturaPadrao = (tipo) => ALTURA_PADRAO[tipo] || 1

// Tipos "passivos" não têm IP para monitorar por padrão.
export const TIPOS_PASSIVOS = ['Patch Panel', 'Organizador de Cabos']

export const alturaRackPx = (us) => TOPO + us * U_PX + BASE

// Posição (relativa ao rack) de um equipamento montado.
export const posicaoNoRack = (rackU, alturaU, us) => ({
  x: TRILHO,
  y: TOPO + (us - (rackU + alturaU - 1)) * U_PX,
})

// U mais baixo correspondente a uma coordenada y (relativa ao rack), já limitado ao rack.
export function uPelaPosicao(y, alturaU, us) {
  const indiceTopo = Math.round((y - TOPO) / U_PX)
  const u = us - indiceTopo - alturaU + 1
  return Math.max(1, Math.min(us - alturaU + 1, u))
}

// Conjunto de U ocupados em um rack (ignorando um equipamento, ex.: o que está sendo movido).
export function ocupados(nodes, rackId, ignorarId = null) {
  const set = new Set()
  for (const n of nodes) {
    if (n.parentNode !== rackId || n.id === ignorarId) continue
    for (let u = n.data.rackU; u < n.data.rackU + n.data.alturaU; u++) set.add(u)
  }
  return set
}

export function cabe(nodes, rack, rackU, alturaU, ignorarId = null) {
  if (!rack || rackU < 1 || rackU + alturaU - 1 > rack.data.us) return false
  const usados = ocupados(nodes, rack.id, ignorarId)
  for (let u = rackU; u < rackU + alturaU; u++) if (usados.has(u)) return false
  return true
}

// Primeira posição livre, procurando de cima para baixo (como se monta um rack).
export function primeiraPosicaoLivre(nodes, rack, alturaU, ignorarId = null) {
  for (let u = rack.data.us - alturaU + 1; u >= 1; u--) {
    if (cabe(nodes, rack, u, alturaU, ignorarId)) return u
  }
  return null
}

// Posição livre mais próxima de um U desejado (para o encaixe ao arrastar).
export function posicaoLivreMaisProxima(nodes, rack, uDesejado, alturaU, ignorarId = null) {
  for (let d = 0; d <= rack.data.us; d++) {
    for (const u of [uDesejado - d, uDesejado + d]) {
      if (cabe(nodes, rack, u, alturaU, ignorarId)) return u
    }
  }
  return null
}

// --- Conversões de nó --------------------------------------------------------

export function noRack(base) {
  const us = base.data.us || 12
  return {
    ...base,
    type: 'rack',
    parentNode: undefined,
    extent: undefined,
    // Gabinete abaixo dos cabos; os equipamentos montados (filhos) ficam acima deles.
    zIndex: -1,
    style: { width: RACK_LARGURA, height: alturaRackPx(us) },
    data: { ...base.data, us, status: 'visual', monitorMode: 'visual', ip: 'Sem IP', tipo: 'Rack' },
  }
}

export function noMontado(base, rack, rackU, alturaU) {
  return {
    ...base,
    type: 'rackDevice',
    parentNode: rack.id,
    extent: 'parent',
    position: posicaoNoRack(rackU, alturaU, rack.data.us),
    style: { width: LARGURA_EQUIP, height: alturaU * U_PX },
    data: { ...base.data, rackU, alturaU },
  }
}

export function noLivre(base, rack) {
  const absoluto = rack ? { x: rack.position.x + RACK_LARGURA + 40, y: rack.position.y + (base.position?.y || 0) } : base.position
  const { rackU, alturaU, ...data } = base.data
  return { ...base, type: 'custom', parentNode: undefined, extent: undefined, position: absoluto, style: { width: 200, height: 80 }, data }
}

// Garante as regras do React Flow (rack antes dos filhos) e recalcula a
// geometria dos equipamentos montados a partir de rackU/alturaU.
export function normalizarRacks(nodes) {
  const racks = new Map(nodes.filter(n => n.type === 'rack').map(n => [n.id, n]))
  const ajustados = nodes.map(n => {
    if (n.type === 'rack') return { ...n, style: { ...n.style, width: RACK_LARGURA, height: alturaRackPx(n.data.us) } }
    if (n.parentNode) {
      const rack = racks.get(n.parentNode)
      if (!rack) return noLivre(n, null) // rack removido: solta o equipamento
      return { ...n, position: posicaoNoRack(n.data.rackU, n.data.alturaU, rack.data.us), style: { ...n.style, width: LARGURA_EQUIP, height: n.data.alturaU * U_PX } }
    }
    return n
  })
  return [...ajustados.filter(n => n.type === 'rack'), ...ajustados.filter(n => n.type !== 'rack')]
}

// Rack cujo retângulo contém o ponto (coordenadas absolutas do mapa).
export function rackNoPonto(nodes, ponto) {
  return nodes.find(n => n.type === 'rack'
    && ponto.x >= n.position.x && ponto.x <= n.position.x + RACK_LARGURA
    && ponto.y >= n.position.y && ponto.y <= n.position.y + alturaRackPx(n.data.us))
}

export const listarRacks = (nodes) => nodes.filter(n => n.type === 'rack').map(n => ({
  id: n.id, nome: n.data.label, us: n.data.us,
  livres: n.data.us - ocupados(nodes, n.id).size,
}))

// Posição livre à direita de tudo que já está no mapa (para racks novos não nascerem por cima).
export function posicaoADireita(nodes, margem = 80) {
  const soltos = nodes.filter(n => !n.parentNode)
  if (!soltos.length) return null
  const direita = Math.max(...soltos.map(n => n.position.x + (n.style?.width || n.width || 200)))
  const topo = Math.min(...soltos.map(n => n.position.y))
  return { x: direita + margem, y: topo }
}

// --- Portas -------------------------------------------------------------------
// Sem modelo, cada tipo usa uma quantidade padrão de portas.
function portasPadrao(tipo, alturaU = 1) {
  switch (tipo) {
    case 'Switch Gerenciável': return { rj45: alturaU >= 2 ? 48 : 24, sfp: 4 }
    case 'Switch Não Gerenciável': return { rj45: alturaU >= 2 ? 48 : 24, sfp: 0 }
    case 'Patch Panel': return { rj45: 24 * Math.min(alturaU, 2), sfp: 0 }
    case 'Roteador': return { rj45: 8, sfp: 2 }
    case 'Firewall': return { rj45: 6, sfp: 0 }
    default: return { rj45: 0, sfp: 0 }
  }
}

// Portas de um equipamento: do modelo (se houver) ou o padrão do tipo.
export function portasDoEquipamento(data, modelo) {
  const alturaU = data.alturaU || modelo?.altura_u || 1
  const { rj45, sfp } = modelo ? { rj45: modelo.portas_rj45, sfp: modelo.portas_sfp } : portasPadrao(data.tipo, alturaU)
  // Até 8 portas numa fileira; acima disso, 2 fileiras por U (até 24 por fileira).
  const linhas = rj45 <= 8 ? 1 : Math.min(2 * alturaU, Math.max(2, Math.ceil(rj45 / 24)))
  return { rj45, sfp, linhas, prefixo: modelo?.prefixo_porta || '' }
}

export const nomePortaRj45 = (n, prefixo) => prefixo ? `${prefixo}${n}` : `Porta ${n}`
export const nomePortaSfp = (n) => `SFP${n}`

export function listarPortas(info) {
  return [
    ...Array.from({ length: info.rj45 }, (_, i) => ({ id: `p:${i + 1}`, nome: nomePortaRj45(i + 1, info.prefixo) })),
    ...Array.from({ length: info.sfp }, (_, i) => ({ id: `s:${i + 1}`, nome: nomePortaSfp(i + 1) })),
  ]
}

export const ehPorta = (handle) => typeof handle === 'string' && /^[ps]:\d+$/.test(handle)

export function nomeDaPorta(handle, info) {
  if (!ehPorta(handle)) return null
  const [t, n] = handle.split(':')
  return t === 'p' ? nomePortaRj45(Number(n), info.prefixo) : nomePortaSfp(Number(n))
}

// Pontos de conexão que existem num nó (as portas só existem nos equipamentos montados em rack).
export function handlesDoNo(node, modelos) {
  if (!node || node.type === 'rack') return new Set()
  const laterais = ['top', 'left', 'right', 'bottom']
  if (node.type !== 'rackDevice') return new Set(laterais)
  const info = portasDoEquipamento(node.data, modelos?.get(node.data.modeloId))
  return new Set([...laterais, ...listarPortas(info).map(p => p.id)])
}
