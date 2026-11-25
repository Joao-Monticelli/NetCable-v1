import { useEffect, useState } from 'react'
import { Smartphone, ShieldCheck, Loader2, Copy, Download } from 'lucide-react'
import QRCode from 'qrcode'
import toast from 'react-hot-toast'
import { api } from '../services/api'
import { t, useI18n } from '../i18n'

const input = { width: '100%', padding: '9px', borderRadius: '6px', border: '1px solid #334155', backgroundColor: '#0f172a', color: 'white', boxSizing: 'border-box' }
const botao = (cor = '#3b82f6') => ({ display: 'inline-flex', alignItems: 'center', gap: '5px', padding: '8px 12px', background: cor, color: 'white', border: 0, borderRadius: '6px', cursor: 'pointer', fontSize: '13px' })
const nota = { fontSize: '12px', color: '#94a3b8', lineHeight: 1.45 }

// Recovery codes are shown only once: copy / download them before closing.
function CodigosRecuperacao({ codigos, onOk }) {
  const texto = codigos.join('\n')
  const baixar = () => {
    const url = URL.createObjectURL(new Blob([`NetCable - ${t('códigos de recuperação')}\n\n${texto}\n`], { type: 'text/plain' }))
    const a = document.createElement('a'); a.href = url; a.download = 'netcable-recovery-codes.txt'; a.click()
    setTimeout(() => URL.revokeObjectURL(url), 1000)
  }
  return (
    <div style={{ display: 'grid', gap: '10px' }}>
      <div style={{ ...nota, color: '#fbbf24' }}>
        {t('Guarde estes códigos de recuperação num lugar seguro. Cada um entra uma vez se você perder o celular. Eles não serão mostrados de novo.')}
      </div>
      <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '4px 16px', padding: '10px', background: '#0f172a', borderRadius: '6px', fontFamily: 'monospace', fontSize: '14px' }}>
        {codigos.map(c => <span key={c}>{c}</span>)}
      </div>
      <div style={{ display: 'flex', gap: '8px', flexWrap: 'wrap' }}>
        <button type="button" style={botao('#334155')} onClick={() => navigator.clipboard?.writeText(texto).then(() => toast.success(t('Copiado!')))}><Copy size={14} /> {t('Copiar')}</button>
        <button type="button" style={botao('#334155')} onClick={baixar}><Download size={14} /> {t('Baixar .txt')}</button>
        <button type="button" style={{ ...botao('#10b981'), marginLeft: 'auto' }} onClick={onOk}>{t('Já guardei')}</button>
      </div>
    </div>
  )
}

// Section of "My profile": turn two-factor authentication (authenticator app) on or off.
export default function DoisFatores({ currentUser, onUpdated }) {
  useI18n()
  const ativo = !!currentUser?.totp_ativo
  const [etapa, setEtapa] = useState(null) // null | 'senha' | 'qr' | 'codigos' | 'desativar' | 'novos'
  const [senha, setSenha] = useState('')
  const [codigo, setCodigo] = useState('')
  const [config, setConfig] = useState(null) // { segredo, uri }
  const [qr, setQr] = useState('')
  const [codigos, setCodigos] = useState([])
  const [ocupado, setOcupado] = useState(false)

  useEffect(() => {
    if (!config?.uri) return
    QRCode.toDataURL(config.uri, { margin: 1, width: 180 }).then(setQr).catch(() => setQr(''))
  }, [config])

  const recarregar = async () => { try { onUpdated?.(await api.me()) } catch { /* keeps the current state */ } }
  const limpar = () => { setEtapa(null); setSenha(''); setCodigo(''); setConfig(null); setQr('') }
  const executar = async (fn) => {
    setOcupado(true)
    try { await fn() } catch (err) { toast.error(err.message) } finally { setOcupado(false) }
  }

  const iniciar = (e) => { e.preventDefault(); executar(async () => { setConfig(await api.iniciar2fa(senha)); setSenha(''); setEtapa('qr') }) }
  const ativar = (e) => {
    e.preventDefault()
    executar(async () => {
      const r = await api.ativar2fa(codigo.trim())
      setCodigos(r.codigos_recuperacao); setCodigo(''); setEtapa('codigos')
      toast.success(t('Verificação em duas etapas ativada.'))
    })
  }
  const desativar = (e) => {
    e.preventDefault()
    executar(async () => { await api.desativar2fa(senha, codigo.trim()); toast.success(t('Verificação em duas etapas desativada.')); limpar(); await recarregar() })
  }
  const gerarNovos = (e) => {
    e.preventDefault()
    executar(async () => { const r = await api.novosCodigosRecuperacao(codigo.trim()); setCodigos(r.codigos_recuperacao); setCodigo(''); setEtapa('codigos') })
  }

  return (
    <div style={{ display: 'grid', gap: '10px' }}>
      <h3 style={{ fontSize: '16px', display: 'flex', alignItems: 'center', gap: '6px' }}>
        <Smartphone size={16} /> {t('Verificação em duas etapas')}
        {ativo && <span style={{ display: 'inline-flex', alignItems: 'center', gap: '3px', fontSize: '12px', color: '#10b981', fontWeight: 'normal' }}><ShieldCheck size={13} /> {t('ativa')}</span>}
      </h3>

      {etapa === 'codigos' ? (
        <CodigosRecuperacao codigos={codigos} onOk={async () => { setCodigos([]); limpar(); await recarregar() }} />
      ) : etapa === 'senha' ? (
        <form onSubmit={iniciar} style={{ display: 'grid', gap: '8px' }}>
          <span style={nota}>{t('Confirme sua senha para começar.')}</span>
          <input type="password" required autoFocus aria-label={t('Senha Atual')} placeholder={t('Senha Atual')} value={senha} onChange={e => setSenha(e.target.value)} style={input} />
          <div style={{ display: 'flex', gap: '8px' }}>
            <button type="submit" disabled={ocupado} style={botao()}>{ocupado ? <Loader2 size={14} className="spin" /> : t('Continuar')}</button>
            <button type="button" onClick={limpar} style={botao('#334155')}>{t('Cancelar')}</button>
          </div>
        </form>
      ) : etapa === 'qr' ? (
        <form onSubmit={ativar} style={{ display: 'grid', gap: '8px' }}>
          <span style={nota}>{t('1. Leia o QR code com o app autenticador (Google Authenticator, Microsoft Authenticator, Authy, 1Password...).')}</span>
          {qr && <img src={qr} alt={t('QR code da verificação em duas etapas')} width={180} height={180} style={{ background: 'white', borderRadius: '6px', justifySelf: 'center' }} />}
          <span style={nota}>{t('Não consegue ler? Digite esta chave no app:')} <code style={{ color: '#e2e8f0', wordBreak: 'break-all' }}>{config?.segredo}</code></span>
          <span style={nota}>{t('2. Digite o código de 6 dígitos que aparece no app:')}</span>
          <input required autoFocus inputMode="numeric" autoComplete="one-time-code" maxLength={7} aria-label={t('Código de verificação')} placeholder="123456" value={codigo} onChange={e => setCodigo(e.target.value)} style={{ ...input, textAlign: 'center', letterSpacing: '4px', fontSize: '18px' }} />
          <div style={{ display: 'flex', gap: '8px' }}>
            <button type="submit" disabled={ocupado} style={botao('#10b981')}>{ocupado ? <Loader2 size={14} className="spin" /> : t('Ativar')}</button>
            <button type="button" onClick={limpar} style={botao('#334155')}>{t('Cancelar')}</button>
          </div>
        </form>
      ) : etapa === 'desativar' || etapa === 'novos' ? (
        <form onSubmit={etapa === 'desativar' ? desativar : gerarNovos} style={{ display: 'grid', gap: '8px' }}>
          {etapa === 'desativar' && <input type="password" required autoFocus aria-label={t('Senha Atual')} placeholder={t('Senha Atual')} value={senha} onChange={e => setSenha(e.target.value)} style={input} />}
          <input required autoFocus={etapa === 'novos'} maxLength={14} aria-label={t('Código de verificação')}
            placeholder={etapa === 'desativar' ? t('Código do app ou de recuperação') : t('Código do app (6 dígitos)')} value={codigo} onChange={e => setCodigo(e.target.value)} style={input} />
          <div style={{ display: 'flex', gap: '8px' }}>
            <button type="submit" disabled={ocupado} style={botao(etapa === 'desativar' ? '#ef4444' : '#3b82f6')}>
              {ocupado ? <Loader2 size={14} className="spin" /> : etapa === 'desativar' ? t('Desativar') : t('Gerar novos códigos')}
            </button>
            <button type="button" onClick={limpar} style={botao('#334155')}>{t('Cancelar')}</button>
          </div>
        </form>
      ) : ativo ? (
        <>
          <span style={nota}>
            {t('Ao entrar, o NetCable pede o código do app autenticador além da senha.')}{' '}
            {currentUser?.totp_recuperacao_restantes !== undefined && t('Códigos de recuperação restantes: {n}.', { n: currentUser.totp_recuperacao_restantes })}
          </span>
          <div style={{ display: 'flex', gap: '8px', flexWrap: 'wrap' }}>
            <button type="button" onClick={() => setEtapa('novos')} style={botao('#334155')}>{t('Gerar novos códigos de recuperação')}</button>
            <button type="button" onClick={() => setEtapa('desativar')} style={botao('#7f1d1d')}>{t('Desativar')}</button>
          </div>
        </>
      ) : (
        <>
          <span style={nota}>{t('Proteja sua conta: além da senha, o login pede um código do app autenticador do celular.')}</span>
          <div><button type="button" onClick={() => setEtapa('senha')} style={botao('#10b981')}><ShieldCheck size={14} /> {t('Ativar verificação em duas etapas')}</button></div>
        </>
      )}
    </div>
  )
}
