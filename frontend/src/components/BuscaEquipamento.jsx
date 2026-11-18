import { useEffect, useMemo, useRef, useState } from 'react'
import { Search } from 'lucide-react'
import { t, useI18n } from '../i18n'

const COR_STATUS = { online: '#22c55e', offline: '#ef4444', visual: '#64748b' }
const normalizar = (s) => (s || '').toString().normalize('NFD').replace(/[̀-ͯ]/g, '').toLowerCase()

// Busca de equipamento por nome, IP ou tipo. Ctrl+K (ou Cmd+K) foca o campo;
// ↑/↓ escolhem, Enter centraliza o equipamento no mapa.
export default function BuscaEquipamento({ itens = [], onEscolher }) {
  useI18n()
  const [texto, setTexto] = useState('')
  const [aberto, setAberto] = useState(false)
  const [indice, setIndice] = useState(0)
  const campo = useRef(null)

  useEffect(() => {
    const atalho = (e) => {
      if ((e.ctrlKey || e.metaKey) && e.key.toLowerCase() === 'k') { e.preventDefault(); campo.current?.focus(); setAberto(true) }
    }
    window.addEventListener('keydown', atalho)
    return () => window.removeEventListener('keydown', atalho)
  }, [])

  const resultados = useMemo(() => {
    const q = normalizar(texto.trim())
    if (!q) return []
    return itens.filter(i => normalizar(i.label).includes(q) || normalizar(i.ip).includes(q) || normalizar(t(i.tipo || '')).includes(q)).slice(0, 8)
  }, [texto, itens])

  const escolher = (item) => {
    if (!item) return
    onEscolher?.(item.id)
    setTexto(''); setAberto(false); campo.current?.blur()
  }

  const teclas = (e) => {
    if (e.key === 'ArrowDown') { e.preventDefault(); setIndice(i => Math.min(i + 1, resultados.length - 1)) }
    else if (e.key === 'ArrowUp') { e.preventDefault(); setIndice(i => Math.max(i - 1, 0)) }
    else if (e.key === 'Enter') { e.preventDefault(); escolher(resultados[indice] || resultados[0]) }
    else if (e.key === 'Escape') { setTexto(''); setAberto(false); campo.current?.blur() }
  }

  return (
    <div style={{ position: 'relative' }}>
      <div style={{ display: 'flex', alignItems: 'center', gap: '6px', background: '#0f172a', border: '1px solid #334155', borderRadius: '6px', padding: '0 8px', height: '36px' }}>
        <Search size={15} color="#64748b" />
        <input ref={campo} value={texto} aria-label={t('Buscar equipamento (Ctrl+K)')} placeholder={t('Buscar nome ou IP…')}
          onChange={(e) => { setTexto(e.target.value); setAberto(true); setIndice(0) }}
          onFocus={() => setAberto(true)} onBlur={() => setTimeout(() => setAberto(false), 150)} onKeyDown={teclas}
          style={{ background: 'transparent', border: 0, outline: 'none', color: 'white', width: '150px', fontSize: '13px' }} />
        <kbd style={{ fontSize: '10px', color: '#64748b', border: '1px solid #334155', borderRadius: '4px', padding: '1px 4px' }}>Ctrl K</kbd>
      </div>
      {aberto && texto.trim() && (
        <div role="listbox" style={{ position: 'absolute', top: '110%', left: 0, minWidth: '100%', width: '280px', background: '#1e293b', border: '1px solid #334155', borderRadius: '6px', boxShadow: '0 8px 20px rgba(0,0,0,.4)', zIndex: 200, overflow: 'hidden' }}>
          {resultados.length === 0 && <div style={{ padding: '10px 12px', color: '#94a3b8', fontSize: '13px' }}>{t('Nenhum equipamento encontrado')}</div>}
          {resultados.map((item, i) => (
            <div key={item.id} role="option" aria-selected={i === indice} onMouseDown={() => escolher(item)} onMouseEnter={() => setIndice(i)}
              style={{ display: 'flex', alignItems: 'center', gap: '8px', padding: '8px 12px', cursor: 'pointer', background: i === indice ? '#334155' : 'transparent' }}>
              <span style={{ width: 8, height: 8, borderRadius: '50%', background: COR_STATUS[item.status] || '#64748b', flex: '0 0 8px' }} />
              <div style={{ minWidth: 0 }}>
                <div style={{ fontSize: '13px', color: 'white', whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis' }}>{item.label}</div>
                <div style={{ fontSize: '11px', color: '#94a3b8' }}>{item.ip && item.ip !== 'Sem IP' ? item.ip : t(item.tipo || '')}{item.rack ? ` · ${item.rack}` : ''}</div>
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  )
}
