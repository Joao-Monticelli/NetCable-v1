import { useEffect, useState } from 'react'
import { X, Users, UserPlus, Trash2, KeyRound, Loader2, ShieldCheck, Pencil, Eye, Smartphone, ShieldOff } from 'lucide-react'
import toast from 'react-hot-toast'
import { api } from '../../services/api'
import { t, useI18n } from '../../i18n'

export const PAPEIS = [
  { valor: 'admin', rotulo: 'Administrador', icon: ShieldCheck, descricao: 'Tudo, inclusive usuários e e-mail' },
  { valor: 'editor', rotulo: 'Editor', icon: Pencil, descricao: 'Cria e edita mapas' },
  { valor: 'visualizador', rotulo: 'Visualizador', icon: Eye, descricao: 'Apenas visualiza (ex.: TV do NOC)' },
]

const campo = { padding: '8px', borderRadius: '6px', border: '1px solid #334155', backgroundColor: '#0f172a', color: 'white', fontSize: '13px', minWidth: 0, width: '100%', boxSizing: 'border-box' }
const botao = { display: 'flex', alignItems: 'center', gap: '5px', padding: '8px 12px', border: 0, borderRadius: '6px', cursor: 'pointer', color: 'white', fontSize: '13px' }

export default function UsersModal({ onClose, currentUser }) {
  useI18n()
  const [usuarios, setUsuarios] = useState(null)
  const [novo, setNovo] = useState({ username: '', email: '', senha: '', papel: 'editor' })
  const [criando, setCriando] = useState(false)

  const carregar = () => api.listarUsuarios().then(setUsuarios).catch(e => { toast.error(e.message); setUsuarios([]) })
  useEffect(() => { carregar() }, [])

  const criar = async (e) => {
    e.preventDefault()
    setCriando(true)
    try {
      await api.criarUsuario(novo)
      toast.success(t('Usuário {nome} criado.', { nome: novo.username }))
      setNovo({ username: '', email: '', senha: '', papel: 'editor' })
      carregar()
    } catch (err) { toast.error(err.message) } finally { setCriando(false) }
  }

  const atualizar = async (u, dados, mensagem) => {
    try {
      await api.atualizarUsuario(u.id, dados)
      if (mensagem) toast.success(mensagem)
      carregar()
    } catch (err) { toast.error(err.message); carregar() }
  }

  const redefinirSenha = (u) => {
    const senha = window.prompt(t('Nova senha para {nome} (mínimo 8 caracteres):', { nome: u.username }))
    if (senha) atualizar(u, { nova_senha: senha }, t('Senha redefinida.'))
  }

  const remover2fa = (u) => {
    if (window.confirm(t('Remover a verificação em duas etapas de "{nome}"? Use só se a pessoa perdeu o celular e os códigos de recuperação; ela poderá configurar de novo no perfil.', { nome: u.username })))
      atualizar(u, { remover_2fa: true }, t('Verificação em duas etapas removida.'))
  }

  const excluir = async (u) => {
    if (!window.confirm(t('Excluir o usuário "{nome}"? Os mapas criados por ele continuam disponíveis para a equipe.', { nome: u.username }))) return
    try { await api.excluirUsuario(u.id); toast.success(t('Usuário excluído.')); carregar() } catch (err) { toast.error(err.message) }
  }

  return (
    <div style={{ position: 'fixed', inset: 0, backgroundColor: 'rgba(0,0,0,0.65)', display: 'flex', justifyContent: 'center', alignItems: 'center', zIndex: 1100 }}>
      <div style={{ backgroundColor: '#1e293b', padding: '25px', borderRadius: '12px', width: 'min(780px, 94vw)', maxHeight: '90vh', overflowY: 'auto', overflowX: 'hidden', border: '1px solid #334155', color: 'white' }}>
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '6px' }}>
          <h2 style={{ display: 'flex', alignItems: 'center', gap: '8px', fontSize: '20px' }}><Users size={20} color="#3b82f6" /> {t('Usuários da equipe')}</h2>
          <button onClick={onClose} style={{ background: 'transparent', border: 0, color: '#94a3b8', cursor: 'pointer' }}><X size={20} /></button>
        </div>
        <p style={{ color: '#94a3b8', fontSize: '13px', marginBottom: '16px' }}>
          {t('Todos os usuários enxergam os mesmos mapas. O papel define o que cada um pode fazer.')}
        </p>

        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(3, 1fr)', gap: '8px', marginBottom: '18px' }}>
          {PAPEIS.map(({ valor, rotulo, icon: Icon, descricao }) => (
            <div key={valor} style={{ padding: '8px 10px', background: '#0f172a', border: '1px solid #334155', borderRadius: '6px', fontSize: '12px' }}>
              <div style={{ display: 'flex', alignItems: 'center', gap: '5px', fontWeight: 'bold', marginBottom: '2px' }}><Icon size={13} /> {t(rotulo)}</div>
              <span style={{ color: '#94a3b8' }}>{t(descricao)}</span>
            </div>
          ))}
        </div>

        {usuarios === null ? <div style={{ color: '#94a3b8' }}><Loader2 size={16} className="spin" /> {t('Carregando...')}</div> : (
          <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: '13px', marginBottom: '20px' }}>
            <thead><tr style={{ color: '#94a3b8', textAlign: 'left' }}>
              <th style={{ padding: '6px', fontWeight: 'normal' }}>{t('Usuário')}</th><th style={{ padding: '6px', fontWeight: 'normal' }}>{t('E-mail')}</th>
              <th style={{ padding: '6px', fontWeight: 'normal' }}>{t('Papel')}</th><th style={{ padding: '6px', fontWeight: 'normal' }}>{t('Ativo')}</th><th></th>
            </tr></thead>
            <tbody>{usuarios.map(u => {
              const souEu = u.id === currentUser?.id
              return (
                <tr key={u.id} style={{ borderTop: '1px solid #334155', opacity: u.ativo ? 1 : 0.55 }}>
                  <td style={{ padding: '6px', fontWeight: 'bold' }}>
                    {u.username}{souEu && <span style={{ color: '#64748b', fontWeight: 'normal' }}> {t('(você)')}</span>}
                    {u.totp_ativo && <span title={t('Verificação em duas etapas ativa')} style={{ marginLeft: '6px', verticalAlign: 'middle' }}><Smartphone size={13} color="#10b981" /></span>}
                    {u.origem === 'ldap' && <span title={t('Entra pelo diretório da empresa (LDAP/AD); o papel vem dos grupos a cada login')} style={{ marginLeft: '6px', fontSize: '10px', padding: '1px 5px', borderRadius: '4px', background: '#1e3a8a', color: '#bfdbfe', fontWeight: 'normal', verticalAlign: 'middle' }}>LDAP</span>}
                  </td>
                  <td style={{ padding: '6px' }}>
                    <input defaultValue={u.email || ''} placeholder={t('sem e-mail')} onBlur={(e) => e.target.value !== (u.email || '') && atualizar(u, { email: e.target.value }, t('E-mail atualizado.'))} style={{ ...campo, width: '100%' }} />
                  </td>
                  <td style={{ padding: '6px' }}>
                    <select value={u.papel} onChange={(e) => atualizar(u, { papel: e.target.value }, t('Papel atualizado.'))} style={{ ...campo, width: 'auto' }}>
                      {PAPEIS.map(p => <option key={p.valor} value={p.valor}>{t(p.rotulo)}</option>)}
                    </select>
                  </td>
                  <td style={{ padding: '6px' }}>
                    <input type="checkbox" checked={u.ativo} disabled={souEu} title={souEu ? t('Você não pode desativar a si mesmo') : t('Ativar/desativar acesso')} onChange={(e) => atualizar(u, { ativo: e.target.checked }, e.target.checked ? t('Usuário reativado.') : t('Usuário desativado.'))} />
                  </td>
                  <td style={{ padding: '6px', whiteSpace: 'nowrap', textAlign: 'right' }}>
                    {u.totp_ativo && !souEu && <button onClick={() => remover2fa(u)} title={t('Remover verificação em duas etapas')} style={{ ...botao, display: 'inline-flex', background: '#334155', padding: '6px 8px', marginRight: '6px' }}><ShieldOff size={14} /></button>}
                    {u.origem !== 'ldap' && <button onClick={() => redefinirSenha(u)} title={t('Redefinir senha')} style={{ ...botao, display: 'inline-flex', background: '#334155', padding: '6px 8px', marginRight: '6px' }}><KeyRound size={14} /></button>}
                    <button onClick={() => excluir(u)} disabled={souEu} title={souEu ? t('Você não pode excluir a si mesmo') : t('Excluir usuário')} style={{ ...botao, display: 'inline-flex', background: souEu ? '#475569' : '#ef4444', padding: '6px 8px', cursor: souEu ? 'not-allowed' : 'pointer' }}><Trash2 size={14} /></button>
                  </td>
                </tr>
              )
            })}</tbody>
          </table>
        )}

        <form onSubmit={criar} style={{ padding: '14px', background: '#0f172a', border: '1px solid #334155', borderRadius: '8px' }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: '6px', fontWeight: 'bold', marginBottom: '10px' }}><UserPlus size={16} color="#10b981" /> {t('Novo usuário')}</div>
          <div style={{ display: 'grid', gridTemplateColumns: 'minmax(0,1fr) minmax(0,1.3fr) minmax(0,1fr) minmax(0,0.9fr) auto', gap: '8px' }}>
            <input required placeholder={t('Usuário')} value={novo.username} onChange={e => setNovo({ ...novo, username: e.target.value })} style={campo} />
            <input type="email" placeholder={t('E-mail (opcional)')} value={novo.email} onChange={e => setNovo({ ...novo, email: e.target.value })} style={campo} />
            <input required type="password" minLength={8} placeholder={t('Senha (mín. 8)')} value={novo.senha} onChange={e => setNovo({ ...novo, senha: e.target.value })} style={campo} />
            <select value={novo.papel} onChange={e => setNovo({ ...novo, papel: e.target.value })} style={campo}>
              {PAPEIS.map(p => <option key={p.valor} value={p.valor}>{t(p.rotulo)}</option>)}
            </select>
            <button type="submit" disabled={criando} style={{ ...botao, background: '#10b981' }}>{criando ? <Loader2 size={14} className="spin" /> : <UserPlus size={14} />} {t('Criar')}</button>
          </div>
        </form>
      </div>
    </div>
  )
}
