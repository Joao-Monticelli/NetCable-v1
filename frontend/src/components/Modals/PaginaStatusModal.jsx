import { useEffect, useState } from 'react'
import { X, Gauge, Copy, ExternalLink, RefreshCw, Link2Off, Loader2 } from 'lucide-react'
import toast from 'react-hot-toast'
import { api } from '../../services/api'
import { t, useI18n } from '../../i18n'

const botao = (cor) => ({ display: 'inline-flex', alignItems: 'center', gap: '6px', padding: '8px 12px', border: 0, borderRadius: '6px', background: cor, color: 'white', cursor: 'pointer', fontSize: '13px', textDecoration: 'none' })

// Public status page of the map: on/off, link, new link. It shows names, status and uptime only (no IPs or topology).
export default function PaginaStatusModal({ projectId, podeEditar, onClose }) {
  useI18n()
  const [token, setToken] = useState(undefined)
  const [ocupado, setOcupado] = useState(false)
  useEffect(() => { api.obterPaginaStatus(projectId).then(r => setToken(r.token)).catch(e => { toast.error(e.message); setToken(null) }) }, [projectId])
  const link = token ? `${window.location.origin}/status/${token}` : ''

  const executar = async (fn) => { setOcupado(true); try { await fn() } catch (e) { toast.error(e.message) } finally { setOcupado(false) } }
  const ativar = (regenerar = false) => {
    if (regenerar && !window.confirm(t('Gerar um novo endereço? O atual deixa de funcionar.'))) return
    executar(async () => { setToken((await api.gerarPaginaStatus(projectId, regenerar)).token) })
  }
  const desativar = () => {
    if (!window.confirm(t('Desativar a página de status? Quem tiver o endereço perde o acesso.'))) return
    executar(async () => { await api.revogarPaginaStatus(projectId); setToken(null); toast.success(t('Página de status desativada.')) })
  }
  const copiar = async () => {
    try { await navigator.clipboard.writeText(link); toast.success(t('Endereço copiado!')) } catch { window.prompt(t('Copie o endereço (Ctrl+C):'), link) }
  }

  return (
    <div style={{ position: 'fixed', inset: 0, backgroundColor: 'rgba(0,0,0,0.65)', display: 'flex', justifyContent: 'center', alignItems: 'center', zIndex: 1100 }}>
      <div role="dialog" aria-label={t('Página de status pública')} style={{ backgroundColor: '#1e293b', padding: '22px', borderRadius: '12px', width: 'min(520px, 94vw)', border: '1px solid #334155', color: 'white', boxSizing: 'border-box' }}>
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '8px' }}>
          <h2 style={{ display: 'flex', alignItems: 'center', gap: '8px', fontSize: '19px' }}><Gauge size={20} color="#10b981" /> {t('Página de status pública')}</h2>
          <button onClick={onClose} aria-label={t('Fechar')} style={{ background: 'transparent', border: 0, color: '#94a3b8', cursor: 'pointer' }}><X size={20} /></button>
        </div>
        <p style={{ fontSize: '13px', color: '#94a3b8', lineHeight: 1.5, marginBottom: '14px' }}>
          {t('Uma página simples para clientes ou para a equipe: se cada serviço está no ar e a disponibilidade dos últimos 90 dias, além das manutenções programadas. Não mostra IPs nem o desenho da rede.')}
          {' '}{t('Escolha o que aparece em cada equipamento ("Mostrar na página de status").')}
        </p>
        {token === undefined ? <Loader2 size={18} className="spin" /> : token ? (
          <div style={{ display: 'grid', gap: '10px' }}>
            <input readOnly value={link} aria-label={t('Endereço da página')} onFocus={e => e.target.select()}
              style={{ padding: '8px', borderRadius: '6px', border: '1px solid #334155', background: '#0f172a', color: '#e2e8f0', fontSize: '13px' }} />
            <div style={{ display: 'flex', gap: '8px', flexWrap: 'wrap' }}>
              <button onClick={copiar} style={botao('#3b82f6')}><Copy size={14} /> {t('Copiar')}</button>
              <a href={link} target="_blank" rel="noreferrer" style={botao('#334155')}><ExternalLink size={14} /> {t('Abrir')}</a>
              {podeEditar && <>
                <button onClick={() => ativar(true)} disabled={ocupado} style={botao('#334155')}><RefreshCw size={14} /> {t('Novo endereço')}</button>
                <button onClick={desativar} disabled={ocupado} style={{ ...botao('#7f1d1d'), marginLeft: 'auto' }}><Link2Off size={14} /> {t('Desativar')}</button>
              </>}
            </div>
          </div>
        ) : podeEditar ? (
          <button onClick={() => ativar(false)} disabled={ocupado} style={botao('#10b981')}>{ocupado ? <Loader2 size={14} className="spin" /> : <Gauge size={14} />} {t('Ativar página de status')}</button>
        ) : <span style={{ fontSize: '13px', color: '#94a3b8' }}>{t('A página de status deste mapa está desativada.')}</span>}
      </div>
    </div>
  )
}
