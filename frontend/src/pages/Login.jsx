import { useEffect, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { Network, Loader2, ShieldCheck } from 'lucide-react'
import toast from 'react-hot-toast'
import { api } from '../services/api'
import { t, useI18n, SeletorIdioma, getIdioma } from '../i18n'

const campo = { padding: '10px', borderRadius: '6px', border: '1px solid #334155', backgroundColor: '#0f172a', color: 'white' }
const botao = (carregando) => ({ display: 'flex', justifyContent: 'center', alignItems: 'center', gap: '8px', padding: '12px', borderRadius: '6px', border: 'none', backgroundColor: '#3b82f6', color: 'white', fontWeight: 'bold', cursor: carregando ? 'wait' : 'pointer', marginTop: '10px' })

// Primeiro acesso: enquanto não existe nenhum usuário, quem abrir o NetCable cria o administrador.
function PrimeiroAcesso({ onConcluido }) {
  const [dados, setDados] = useState({ username: 'admin', email: '', senha: '', confirmar: '' })
  const [salvando, setSalvando] = useState(false)
  const set = (k) => (e) => setDados({ ...dados, [k]: e.target.value })

  const criar = async (e) => {
    e.preventDefault()
    if (dados.senha !== dados.confirmar) { toast.error(t('As senhas não conferem.')); return }
    setSalvando(true)
    try {
      await api.concluirSetup({ username: dados.username, senha: dados.senha, email: dados.email || null, idioma: getIdioma() })
      toast.success(t('Conta de administrador criada. Bem-vindo ao NetCable!'))
      onConcluido()
    } catch (err) { toast.error(err.message, { duration: 7000 }) } finally { setSalvando(false) }
  }

  return (
    <>
      <div style={{ textAlign: 'center', marginBottom: '22px' }}>
        <ShieldCheck size={44} color="#10b981" style={{ margin: '0 auto' }} />
        <h1 style={{ fontSize: '22px', marginTop: '10px' }}>{t('Bem-vindo ao NetCable!')}</h1>
        <p style={{ color: '#94a3b8', fontSize: '13px', marginTop: '6px', lineHeight: 1.4 }}>
          {t('Primeiro acesso: crie a conta de administrador. Depois você pode convidar a equipe em ⚙️ → Usuários.')}
        </p>
      </div>
      <form onSubmit={criar} style={{ display: 'flex', flexDirection: 'column', gap: '12px' }}>
        <input required aria-label={t('Usuário')} placeholder={t('Usuário')} value={dados.username} onChange={set('username')} style={campo} />
        <input type="email" aria-label={t('E-mail (opcional)')} placeholder={t('E-mail (opcional)')} value={dados.email} onChange={set('email')} style={campo} />
        <input required type="password" minLength={8} aria-label={t('Senha (mín. 8)')} placeholder={t('Senha (mín. 8)')} value={dados.senha} onChange={set('senha')} style={campo} />
        <input required type="password" minLength={8} aria-label={t('Confirmar senha')} placeholder={t('Confirmar senha')} value={dados.confirmar} onChange={set('confirmar')} style={campo} />
        <button type="submit" disabled={salvando} style={{ ...botao(salvando), backgroundColor: '#10b981' }}>
          {salvando ? <Loader2 size={18} className="spin" /> : t('Criar administrador e entrar')}
        </button>
      </form>
    </>
  )
}

export default function Login() {
  useI18n()
  const navigate = useNavigate()
  const [username, setUsername] = useState('')
  const [password, setPassword] = useState('')
  const [isLoading, setIsLoading] = useState(false)
  const [setup, setSetup] = useState(null) // null = verificando; true = primeiro acesso
  const [versao, setVersao] = useState('')

  useEffect(() => { api.statusSetup().then(s => { setSetup(!!s.necessario); setVersao(s.versao || '') }).catch(() => setSetup(false)) }, [])

  const handleLogin = async (e) => {
    e.preventDefault()
    setIsLoading(true)
    try {
      await api.login(username, password)
      toast.success(t('Bem-vindo ao NetCable!'))
      navigate('/projects')
    } catch (err) {
      toast.error(err.message || t('Falha ao fazer login.'), { duration: 7000 })
    } finally {
      setIsLoading(false)
    }
  }

  return (
    <div style={{ display: 'flex', justifyContent: 'center', alignItems: 'center', height: '100vh', backgroundColor: '#0f172a' }}>
      <div style={{ position: 'relative', backgroundColor: '#1e293b', padding: '40px', borderRadius: '12px', width: '350px', boxShadow: '0 4px 6px rgba(0,0,0,0.3)' }}>
        <SeletorIdioma compacto style={{ position: 'absolute', top: '12px', right: '12px' }} />
        {setup === null ? (
          <div style={{ textAlign: 'center', color: '#94a3b8' }}><Loader2 className="spin" /></div>
        ) : setup ? (
          <PrimeiroAcesso onConcluido={() => navigate('/projects')} />
        ) : (
          <>
            <div style={{ textAlign: 'center', marginBottom: '30px' }}>
              <Network size={48} color="#3b82f6" style={{ margin: '0 auto' }} />
              <h1 style={{ fontSize: '24px', marginTop: '10px' }}>NetCable</h1>
              <p style={{ color: '#94a3b8', fontSize: '14px' }}>{t('Acesso Restrito')}</p>
            </div>
            <form onSubmit={handleLogin} style={{ display: 'flex', flexDirection: 'column', gap: '15px' }}>
              <input type="text" placeholder={t('Usuário')} value={username} onChange={e => setUsername(e.target.value)} style={campo} />
              <input type="password" placeholder={t('Senha')} value={password} onChange={e => setPassword(e.target.value)} style={campo} />
              <button type="submit" disabled={isLoading} style={botao(isLoading)}>
                {isLoading ? <Loader2 size={18} className="spin" /> : t('Entrar')}
              </button>
            </form>
          </>
        )}
        {versao && <div style={{ textAlign: 'center', marginTop: '22px', fontSize: '11px', color: '#475569' }}>NetCable v{versao}</div>}
      </div>
    </div>
  )
}
