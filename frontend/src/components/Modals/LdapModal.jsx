import { useEffect, useState } from 'react'
import { X, Building2, Save, Loader2, Search, Trash2, CheckCircle2, XCircle } from 'lucide-react'
import toast from 'react-hot-toast'
import { api } from '../../services/api'
import { t, useI18n } from '../../i18n'

const rotulo = { fontSize: '13px', color: '#94a3b8', display: 'grid', gap: '4px' }
const campo = { width: '100%', padding: '8px', borderRadius: '6px', border: '1px solid #334155', backgroundColor: '#0f172a', color: 'white', boxSizing: 'border-box', fontSize: '13px' }
const botao = (cor) => ({ display: 'inline-flex', alignItems: 'center', gap: '6px', padding: '8px 12px', border: 0, borderRadius: '6px', background: cor, color: 'white', cursor: 'pointer', fontSize: '13px' })
const cartao = { padding: '12px', backgroundColor: '#0f172a', borderRadius: '8px', border: '1px solid #334155', display: 'grid', gap: '10px' }
const ajuda = { fontSize: '11px', color: '#64748b', lineHeight: 1.45 }
const PAPEIS = { admin: 'Administrador', editor: 'Editor', visualizador: 'Visualizador' }
const GRUPOS = { admin: 'Grupo dos administradores', editor: 'Grupo dos editores', visualizador: 'Grupo dos visualizadores' }

// Login with the company directory (LDAP / Active Directory). Admins only.
export default function LdapModal({ onClose }) {
  useI18n()
  const [cfg, setCfg] = useState(null)
  const [senha, setSenha] = useState(undefined) // undefined keeps the saved one; '' removes it
  const [salvando, setSalvando] = useState(false)
  const [teste, setTeste] = useState({ usuario: '', senha: '' })
  const [resultado, setResultado] = useState(null)
  const [testando, setTestando] = useState(false)
  useEffect(() => { api.obterLdap().then(setCfg).catch(e => toast.error(e.message)) }, [])
  const set = (k) => (e) => setCfg({ ...cfg, [k]: e.target.type === 'checkbox' ? e.target.checked : e.target.value })

  const salvar = async (e) => {
    e.preventDefault()
    setSalvando(true)
    try {
      const { bind_senha_definida, filtro_padrao, ...dados } = cfg
      setCfg(await api.salvarLdap({ ...dados, filtro: dados.filtro === filtro_padrao ? '' : dados.filtro, bind_senha: senha === undefined ? null : senha }))
      setSenha(undefined)
      toast.success(t('Configuração do diretório salva.'))
    } catch (err) { toast.error(err.message, { duration: 7000 }) } finally { setSalvando(false) }
  }
  const testar = async () => {
    if (!teste.usuario.trim()) return
    setTestando(true)
    setResultado(null)
    try { setResultado(await api.testarLdap(teste.usuario, teste.senha)) } catch (err) { setResultado({ erro: err.message }) } finally { setTestando(false) }
  }

  return (
    <div style={{ position: 'fixed', inset: 0, backgroundColor: 'rgba(0,0,0,0.65)', display: 'flex', justifyContent: 'center', alignItems: 'center', zIndex: 1100 }}>
      <div role="dialog" aria-label={t('Diretório (LDAP/AD)')} style={{ backgroundColor: '#1e293b', padding: '22px', borderRadius: '12px', width: 'min(600px, 94vw)', maxHeight: '92vh', overflow: 'auto', border: '1px solid #334155', color: 'white', boxSizing: 'border-box' }}>
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '6px' }}>
          <h2 style={{ display: 'flex', alignItems: 'center', gap: '8px', fontSize: '19px' }}><Building2 size={20} color="#60a5fa" /> {t('Diretório (LDAP/AD)')}</h2>
          <button onClick={onClose} aria-label={t('Fechar')} style={{ background: 'transparent', border: 0, color: '#94a3b8', cursor: 'pointer' }}><X size={20} /></button>
        </div>
        <p style={{ fontSize: '13px', color: '#94a3b8', lineHeight: 1.5, marginBottom: '14px' }}>
          {t('As pessoas entram no NetCable com o usuário e a senha da empresa. A conta é criada no primeiro login e o papel vem dos grupos do diretório. As contas locais (como a do administrador) continuam funcionando.')}
        </p>
        {!cfg ? <Loader2 size={18} className="spin" /> : (
          <form onSubmit={salvar} style={{ display: 'grid', gap: '12px' }}>
            <label style={{ display: 'flex', alignItems: 'center', gap: '8px', fontSize: '14px', cursor: 'pointer' }}>
              <input type="checkbox" checked={cfg.ativo} onChange={set('ativo')} /> {t('Permitir login pelo diretório')}
            </label>
            <div style={cartao}>
              <label style={rotulo}>{t('Servidor')}<input aria-label={t('Servidor LDAP')} value={cfg.servidor} onChange={set('servidor')} placeholder="ldaps://dc01.empresa.local" style={campo} /></label>
              <div style={{ display: 'flex', gap: '16px', flexWrap: 'wrap', fontSize: '13px' }}>
                <label style={{ display: 'flex', alignItems: 'center', gap: '6px' }}><input type="checkbox" checked={cfg.starttls} onChange={set('starttls')} /> {t('STARTTLS (ldap:// cifrado)')}</label>
                <label style={{ display: 'flex', alignItems: 'center', gap: '6px' }}><input type="checkbox" checked={cfg.verificar_cert} onChange={set('verificar_cert')} /> {t('Verificar o certificado')}</label>
              </div>
              <span style={ajuda}>{t('Use ldaps:// (porta 636) ou STARTTLS: com ldap:// puro as senhas passam sem cifra pela rede. No Active Directory com várias florestas, a porta 3268 (catálogo global) também funciona.')}</span>
              <label style={rotulo}>{t('Base de busca (base DN)')}<input aria-label={t('Base DN')} value={cfg.base_dn} onChange={set('base_dn')} placeholder="dc=empresa,dc=local" style={campo} /></label>
              <div style={{ display: 'grid', gridTemplateColumns: '3fr 2fr', gap: '8px' }}>
                <label style={rotulo}>{t('Conta de serviço (bind DN)')}<input aria-label={t('Bind DN')} value={cfg.bind_dn} onChange={set('bind_dn')} placeholder="cn=svc-netcable,ou=Servicos,dc=empresa,dc=local" style={campo} /></label>
                <label style={rotulo}>{t('Senha da conta de serviço')}
                  <div style={{ display: 'flex', gap: '6px' }}>
                    <input type="password" autoComplete="new-password" aria-label={t('Senha da conta de serviço')} value={senha || ''} onChange={e => setSenha(e.target.value)}
                      placeholder={cfg.bind_senha_definida && senha !== '' ? `•••••• (${t('manter atual')})` : ''} style={campo} />
                    {cfg.bind_senha_definida && senha !== '' && <button type="button" title={t('Remover')} aria-label={t('Remover')} onClick={() => setSenha('')} style={botao('#334155')}><Trash2 size={14} /></button>}
                  </div>
                </label>
              </div>
              <span style={ajuda}>{t('Deixe a conta de serviço vazia se o diretório permite busca anônima. Ela só precisa de permissão de leitura.')}</span>
              <label style={rotulo}>{t('Filtro de usuário')}<input aria-label={t('Filtro de usuário')} value={cfg.filtro} onChange={set('filtro')} style={{ ...campo, fontFamily: 'monospace', fontSize: '12px' }} /></label>
              <span style={ajuda}>{t('{usuario} é trocado pelo nome digitado no login. O padrão aceita sAMAccountName (AD), uid (OpenLDAP) e userPrincipalName.')}</span>
            </div>

            <div style={cartao}>
              <strong style={{ fontSize: '14px' }}>{t('Papéis pelos grupos')}</strong>
              {['admin', 'editor', 'visualizador'].map(p => (
                <label key={p} style={rotulo}>{t(GRUPOS[p])}
                  <input aria-label={t(GRUPOS[p])} value={cfg[`grupo_${p}`]} onChange={set(`grupo_${p}`)} placeholder={p === 'admin' ? 'cn=NetCable-Admins,ou=Grupos,dc=empresa,dc=local' : `NetCable-${p === 'editor' ? 'Editores' : 'Leitores'}`} style={campo} />
                </label>
              ))}
              <label style={rotulo}>{t('Quem não está em nenhum desses grupos')}
                <select aria-label={t('Papel padrão')} value={cfg.papel_padrao} onChange={set('papel_padrao')} style={campo}>
                  <option value="">{t('Não pode entrar')}</option>
                  <option value="visualizador">{t('Entra como visualizador')}</option>
                  <option value="editor">{t('Entra como editor')}</option>
                </select>
              </label>
              <span style={ajuda}>{t('Use o DN completo do grupo ou só o nome (cn). Vale a participação direta no grupo (memberOf, member ou memberUid). O papel é atualizado a cada login.')}</span>
            </div>

            <div style={{ display: 'flex', justifyContent: 'flex-end' }}>
              <button type="submit" disabled={salvando} style={botao('#3b82f6')}>{salvando ? <Loader2 size={14} className="spin" /> : <Save size={14} />} {t('Salvar')}</button>
            </div>

            <div style={cartao}>
              <strong style={{ fontSize: '14px' }}>{t('Testar (usa a configuração salva)')}</strong>
              <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr auto', gap: '8px' }}>
                <input aria-label={t('Usuário para testar')} value={teste.usuario} onChange={e => setTeste({ ...teste, usuario: e.target.value })} placeholder={t('usuário')} style={campo} />
                <input type="password" autoComplete="off" aria-label={t('Senha para testar')} value={teste.senha} onChange={e => setTeste({ ...teste, senha: e.target.value })} placeholder={t('senha (opcional)')} style={campo} />
                <button type="button" onClick={testar} disabled={testando} style={botao('#334155')}>{testando ? <Loader2 size={14} className="spin" /> : <Search size={14} />} {t('Testar')}</button>
              </div>
              {resultado && (resultado.erro ? <div role="alert" style={{ fontSize: '13px', color: '#fca5a5' }}><XCircle size={13} /> {resultado.erro}</div>
                : !resultado.encontrado ? <div style={{ fontSize: '13px', color: '#fca5a5' }}><XCircle size={13} /> {resultado.senha_ok === false ? t('Usuário não encontrado ou senha incorreta.') : t('Usuário não encontrado.')}</div>
                : (
                  <div style={{ fontSize: '13px', display: 'grid', gap: '4px' }}>
                    <span style={{ color: '#86efac' }}><CheckCircle2 size={13} /> {resultado.senha_ok ? t('Usuário encontrado e senha correta.') : t('Usuário encontrado.')}</span>
                    <span style={{ color: '#94a3b8', wordBreak: 'break-all' }}>{resultado.dn}{resultado.email ? ` · ${resultado.email}` : ''}</span>
                    <span>{resultado.papel ? t('Entraria como: {papel}', { papel: t(PAPEIS[resultado.papel]) }) : <span style={{ color: '#fca5a5' }}>{t('Não poderia entrar: não está em nenhum grupo configurado.')}</span>}</span>
                    {resultado.grupos?.length > 0 && <span style={{ ...ajuda, wordBreak: 'break-all' }}>{t('Grupos: {lista}', { lista: resultado.grupos.join('; ') })}</span>}
                  </div>
                ))}
            </div>
          </form>
        )}
      </div>
    </div>
  )
}
