import { useCallback, useRef, useState } from 'react'
import { ehPorta } from './rack/rackUtils'

const CHAVE_CABOS = 'netcable_cabos_porta'

// Preferência "mostrar cabos entre portas", lembrada por navegador.
export function usePreferenciaCabos() {
  const [mostrar, setMostrar] = useState(() => { try { return localStorage.getItem(CHAVE_CABOS) !== '0' } catch { return true } })
  const alternar = useCallback(() => setMostrar(v => {
    try { localStorage.setItem(CHAVE_CABOS, v ? '0' : '1') } catch { /* modo privado */ }
    return !v
  }), [])
  return [mostrar, alternar]
}

// Itens da busca e quantidade de cabos entre portas, atualizados só quando mudam
// (evita re-renderizar a barra a cada movimento do mapa).
export function useResumoMapa() {
  const [itens, setItens] = useState([])
  const [cabosPorta, setCabosPorta] = useState(0)
  const chave = useRef('')
  const atualizar = useCallback((nodes, edges = []) => {
    const racks = new Map(nodes.filter(n => n.type === 'rack').map(n => [n.id, n.data.label]))
    const lista = nodes.filter(n => n.type !== 'rack').map(n => ({
      id: n.id, label: n.data.label, ip: n.data.ip, tipo: n.data.tipo, status: n.data.status, rack: racks.get(n.parentNode) || null,
    }))
    const nova = JSON.stringify(lista)
    if (nova !== chave.current) { chave.current = nova; setItens(lista) }
    setCabosPorta(edges.filter(e => ehPorta(e.sourceHandle) || ehPorta(e.targetHandle)).length)
  }, [])
  return { itens, cabosPorta, atualizar }
}
