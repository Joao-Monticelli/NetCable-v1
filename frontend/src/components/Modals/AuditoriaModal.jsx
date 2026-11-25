import { useEffect, useState } from 'react'
import { X, ScrollText, RefreshCw, Loader2 } from 'lucide-react'
import toast from 'react-hot-toast'
import { api } from '../../services/api'
import { t, useI18n, localeAtual } from '../../i18n'

// Readable name of each audit action (the API stores a stable code such as "mapa.salvo").
export const ACOES = {
  'setup.admin_criado': 'Primeiro administrador criado',
  'login.ok': 'Login',
  'login.falhou': 'Login falhou',
  'login.bloqueado': 'Login bloqueado (muitas tentativas)',
  'login.desativado': 'Login de usuário desativado',
  'login.2fa_falhou': 'Código de verificação errado',
  '2fa.ativado': 'Ativou a verificação em duas etapas',
  '2fa.desativado': 'Desativou a verificação em duas etapas',
  '2fa.recuperacao_gerada': 'Gerou novos códigos de recuperação',
  '2fa.removido_cli': 'Verificação em duas etapas removida pelo servidor',
  'perfil.senha_alterada': 'Trocou a própria senha',
  'usuario.criado': 'Usuário criado',
  'usuario.alterado': 'Usuário alterado',
  'usuario.excluido': 'Usuário excluído',
  'mapa.criado': 'Mapa criado',
  'mapa.renomeado': 'Mapa renomeado',
  'mapa.excluido': 'Mapa excluído',
  'mapa.importado': 'Mapa importado',
  'mapa.salvo': 'Mapa salvo',
  'link.criado': 'Link público criado',
  'link.regenerado': 'Link público gerado de novo',
  'link.revogado': 'Link público revogado',
  'status.criado': 'Página de status ativada',
  'status.regenerado': 'Novo endereço da página de status',
  'status.revogado': 'Página de status desativada',
  'manutencao.iniciada': 'Manutenção iniciada',
  'manutencao.encerrada': 'Manutenção encerrada',
  'manutencao.agendada': 'Manutenção agendada',
  'manutencao.removida': 'Manutenção removida da agenda',
  'alerta.reconhecido': 'Alerta reconhecido',
  'alerta.reconhecimento_removido': 'Reconhecimento desfeito',
  'config.email': 'E-mail (SMTP) alterado',
  'config.alertas': 'Canais de alerta alterados',
  'config.backup': 'Configuração de backup alterada',
  'config.metricas': 'Limites de métricas alterados',
  'backup.criado': 'Backup criado',
  'backup.baixado': 'Backup baixado',
}

const FILTROS = [['', 'Tudo'], ['login', 'Logins'], ['usuario', 'Usuários'], ['mapa', 'Mapas'], ['link', 'Links públicos'], ['status', 'Página de status'], ['manutencao', 'Manutenção'], ['alerta', 'Alertas reconhecidos'], ['2fa', 'Verificação em duas etapas'], ['config', 'Configurações'], ['backup', 'Backups']]
const corAcao = (acao) => acao === 'login.falhou' || acao === 'login.bloqueado' || acao === 'login.2fa_falhou' || acao === '2fa.desativado' || acao.endsWith('excluido') || acao === 'link.revogado' ? '#f87171'
  : acao.startsWith('config') || acao.startsWith('usuario') ? '#fbbf24' : '#cbd5e1'
const th = { padding: '8px', fontWeight: 'normal' }
const td = { padding: '7px 8px', verticalAlign: 'top' }
const POR_PAGINA = 100

export default function AuditoriaModal({ onClose }) {
  useI18n()
  const [itens, setItens] = useState(null)
  const [filtro, setFiltro] = useState('')
  const [usuario, setUsuario] = useState('')
  const [temMais, setTemMais] = useState(false)
  const [carregando, setCarregando] = useState(false)

  const carregar = async (antesDe = null) => {
    setCarregando(true)
    try {
      const novos = await api.listarAuditoria({ acao: filtro, usuario: usuario.trim(), antesDe, limite: POR_PAGINA })
      setItens(antes => antesDe ? [...(antes || []), ...novos] : novos)
      setTemMais(novos.length === POR_PAGINA)
    } catch (err) { toast.error(err.message); setItens(i => i || []) } finally { setCarregando(false) }
  }
  useEffect(() => { carregar() }, [filtro]) // eslint-disable-line react-hooks/exhaustive-deps

  return (
    <div style={{ position: 'fixed', inset: 0, backgroundColor: 'rgba(0,0,0,0.65)', display: 'flex', justifyContent: 'center', alignItems: 'center', zIndex: 1100 }}>
      <div role="dialog" aria-label={t('Log de auditoria')} style={{ backgroundColor: '#1e293b', padding: '25px', borderRadius: '12px', width: 'min(900px, 95vw)', maxHeight: '90vh', display: 'flex', flexDirection: 'column', border: '1px solid #334155', color: 'white' }}>
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '6px' }}>
          <h2 style={{ display: 'flex', alignItems: 'center', gap: '8px', fontSize: '20px' }}><ScrollText size={20} color="#38bdf8" /> {t('Log de auditoria')}</h2>
          <button onClick={onClose} aria-label={t('Fechar')} style={{ background: 'transparent', border: 0, color: '#94a3b8', cursor: 'pointer' }}><X size={20} /></button>
        </div>
        <p style={{ fontSize: '12px', color: '#64748b', marginBottom: '12px' }}>{t('Quem fez o quê e quando: logins, usuários, mapas, links públicos, manutenção, configurações e backups. Senhas nunca são registradas.')}</p>

        <form onSubmit={e => { e.preventDefault(); carregar() }} style={{ display: 'flex', gap: '8px', flexWrap: 'wrap', alignItems: 'center', marginBottom: '12px' }}>
          <select aria-label={t('Tipo de ação')} value={filtro} onChange={e => setFiltro(e.target.value)} style={{ padding: '6px 8px', borderRadius: '6px', border: '1px solid #334155', background: '#0f172a', color: 'white', fontSize: '13px' }}>
            {FILTROS.map(([v, r]) => <option key={v} value={v}>{t(r)}</option>)}
          </select>
          <input aria-label={t('Usuário')} value={usuario} onChange={e => setUsuario(e.target.value)} placeholder={t('Usuário (exato)')}
            style={{ padding: '6px 8px', borderRadius: '6px', border: '1px solid #334155', background: '#0f172a', color: 'white', fontSize: '13px', width: '160px' }} />
          <button type="submit" style={{ display: 'flex', alignItems: 'center', gap: '5px', padding: '6px 12px', borderRadius: '6px', border: 0, background: '#334155', color: 'white', cursor: 'pointer', fontSize: '13px' }}>
            {carregando ? <Loader2 size={14} className="spin" /> : <RefreshCw size={14} />} {t('Atualizar')}
          </button>
        </form>

        <div style={{ overflow: 'auto', flex: 1, minHeight: '200px' }}>
          {itens === null ? <div style={{ color: '#94a3b8' }}>{t('Carregando...')}</div>
            : itens.length === 0 ? <div style={{ color: '#94a3b8' }}>{t('Nenhum registro encontrado.')}</div> : (
              <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: '13px' }}>
                <thead><tr style={{ color: '#94a3b8', textAlign: 'left', position: 'sticky', top: 0, background: '#1e293b' }}>
                  <th style={th}>{t('Horário')}</th><th style={th}>{t('Usuário')}</th><th style={th}>{t('Ação')}</th><th style={th}>{t('Detalhe')}</th><th style={th}>IP</th>
                </tr></thead>
                <tbody>{itens.map(a => (
                  <tr key={a.id} style={{ borderTop: '1px solid #334155' }}>
                    <td style={{ ...td, color: '#94a3b8', whiteSpace: 'nowrap' }}>{new Date(a.criado_em).toLocaleString(localeAtual())}</td>
                    <td style={{ ...td, fontWeight: 'bold' }}>{a.usuario || '—'}</td>
                    <td style={{ ...td, color: corAcao(a.acao) }}>{ACOES[a.acao] ? t(ACOES[a.acao]) : a.acao}</td>
                    <td style={{ ...td, color: '#cbd5e1', wordBreak: 'break-word' }}>{a.detalhe || ''}</td>
                    <td style={{ ...td, color: '#64748b', whiteSpace: 'nowrap' }}>{a.ip || ''}</td>
                  </tr>
                ))}</tbody>
              </table>
            )}
          {temMais && (
            <button onClick={() => carregar(itens[itens.length - 1].id)} disabled={carregando} style={{ margin: '12px auto 0', display: 'block', padding: '6px 14px', borderRadius: '6px', border: '1px solid #334155', background: 'transparent', color: '#cbd5e1', cursor: 'pointer', fontSize: '13px' }}>
              {t('Carregar mais')}
            </button>
          )}
        </div>
      </div>
    </div>
  )
}
