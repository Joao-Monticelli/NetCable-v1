import { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { Network, Loader2 } from 'lucide-react'
import toast from 'react-hot-toast'
import { api } from '../services/api'

export default function Login() {
  const navigate = useNavigate()
  const [username, setUsername] = useState('')
  const [password, setPassword] = useState('')
  const [isLoading, setIsLoading] = useState(false)

  const handleLogin = async (e) => {
    e.preventDefault()
    setIsLoading(true)
    try {
      await api.login(username, password)
      toast.success('Bem-vindo ao NetCable!')
      navigate('/projects')
    } catch (err) {
      toast.error('Usuário ou senha incorretos.')
    } finally {
      setIsLoading(false)
    }
  }

  return (
    <div style={{ display: 'flex', justifyContent: 'center', alignItems: 'center', height: '100vh', backgroundColor: '#0f172a' }}>
      <div style={{ backgroundColor: '#1e293b', padding: '40px', borderRadius: '12px', width: '350px', boxShadow: '0 4px 6px rgba(0,0,0,0.3)' }}>
        <div style={{ textAlign: 'center', marginBottom: '30px' }}>
          <Network size={48} color="#3b82f6" style={{ margin: '0 auto' }} />
          <h1 style={{ fontSize: '24px', marginTop: '10px' }}>NetCable</h1>
          <p style={{ color: '#94a3b8', fontSize: '14px' }}>Acesso Restrito</p>
        </div>
        
        <form onSubmit={handleLogin} style={{ display: 'flex', flexDirection: 'column', gap: '15px' }}>
          <input type="text" placeholder="Usuário" value={username} onChange={e => setUsername(e.target.value)} style={{ padding: '10px', borderRadius: '6px', border: '1px solid #334155', backgroundColor: '#0f172a', color: 'white' }} />
          <input type="password" placeholder="Senha" value={password} onChange={e => setPassword(e.target.value)} style={{ padding: '10px', borderRadius: '6px', border: '1px solid #334155', backgroundColor: '#0f172a', color: 'white' }} />
          <button type="submit" disabled={isLoading} style={{ display: 'flex', justifyContent: 'center', alignItems: 'center', gap: '8px', padding: '12px', borderRadius: '6px', border: 'none', backgroundColor: '#3b82f6', color: 'white', fontWeight: 'bold', cursor: isLoading ? 'wait' : 'pointer', marginTop: '10px' }}>
            {isLoading ? <Loader2 size={18} className="spin" /> : 'Entrar'}
          </button>
        </form>
      </div>
    </div>
  )
}