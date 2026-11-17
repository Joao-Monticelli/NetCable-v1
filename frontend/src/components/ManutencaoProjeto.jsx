import { useEffect, useRef, useState } from 'react'
import { Wrench } from 'lucide-react'
import toast from 'react-hot-toast'
import { api } from '../services/api'
import { t, useI18n, localeAtual } from '../i18n'

const OPCOES = [[1, '1 h'], [2, '2 h'], [4, '4 h'], [8, '8 h'], [24, '24 h']]
const item = { display: 'block', width: '100%', padding: '8px 12px', background: 'transparent', color: 'white', border: 0, textAlign: 'left', cursor: 'pointer', borderRadius: '4px', fontSize: '13px' }

// Botão da barra: silencia os alertas do mapa inteiro por um tempo (ex.: janela de manutenção da rede).
export default function ManutencaoProjeto({ projectId, ate, podeEditar, onMudou }) {
  useI18n()
  const [aberto, setAberto] = useState(false)
  const ref = useRef(null)
  useEffect(() => {
    if (!aberto) return
    const fechar = (e) => { if (ref.current && !ref.current.contains(e.target)) setAberto(false) }
    document.addEventListener('mousedown', fechar)
    return () => document.removeEventListener('mousedown', fechar)
  }, [aberto])

  if (!projectId || projectId === 'novo' || (!ate && !podeEditar)) return null
  const hora = ate ? new Date(ate).toLocaleTimeString(localeAtual(), { hour: '2-digit', minute: '2-digit' }) : ''

  const iniciar = async (horas) => {
    setAberto(false)
    try {
      const r = await api.iniciarManutencao(projectId, { horas })
      onMudou?.(r.ate)
      toast.success(t('Mapa em manutenção até {hora}: alertas silenciados.', { hora: new Date(r.ate).toLocaleString(localeAtual()) }))
    } catch (err) { toast.error(err.message) }
  }
  const encerrar = async () => {
    setAberto(false)
    try { await api.encerrarManutencao(projectId); onMudou?.(null); toast.success(t('Manutenção encerrada.')) } catch (err) { toast.error(err.message) }
  }

  return (
    <div ref={ref} style={{ position: 'relative' }}>
      <button onClick={() => podeEditar && setAberto(a => !a)} aria-pressed={!!ate}
        title={ate ? t('Mapa em manutenção até {hora} (alertas silenciados)', { hora }) : t('Manutenção: silenciar os alertas deste mapa')}
        style={{ display: 'flex', alignItems: 'center', gap: '6px', padding: '8px 12px', backgroundColor: ate ? '#0369a1' : '#334155', color: 'white', border: 'none', borderRadius: '6px', cursor: podeEditar ? 'pointer' : 'default', fontSize: '12px' }}>
        <Wrench size={18} /> {ate && t('até {hora}', { hora })}
      </button>
      {aberto && (
        <div role="menu" style={{ position: 'absolute', top: '110%', right: 0, background: '#1e293b', border: '1px solid #334155', borderRadius: '6px', padding: '5px', minWidth: '210px', zIndex: 100, boxShadow: '0 4px 6px rgba(0,0,0,.3)' }}>
          <div style={{ padding: '6px 12px', fontSize: '12px', color: '#94a3b8' }}>{t('Silenciar alertas do mapa por:')}</div>
          {OPCOES.map(([h, r]) => <button key={h} role="menuitem" onClick={() => iniciar(h)} style={item}>{r}</button>)}
          {ate && <>
            <div style={{ height: 1, background: '#334155', margin: '5px 0' }} />
            <button role="menuitem" onClick={encerrar} style={{ ...item, color: '#38bdf8' }}>{t('Encerrar manutenção')}</button>
          </>}
        </div>
      )}
    </div>
  )
}
