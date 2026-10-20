import { useNavigate } from 'react-router-dom'
import { Network } from 'lucide-react'

export default function Login() {
  const navigate = useNavigate()

  const handleLogin = (e) => {
    e.preventDefault()
    // Simulação de login
    navigate('/projects')
  }

  return (
    <div style={{ display: 'flex', justifyContent: 'center', alignItems: 'center', height: '100vh', backgroundColor: '#0f172a' }}>
      <div style={{ backgroundColor: '#1e293b', padding: '40px', borderRadius: '12px', width: '350px', boxShadow: '0 4px 6px rgba(0,0,0,0.3)' }}>
        <div style={{ textAlign: 'center', marginBottom: '30px' }}>
          <Network size={48} color="#3b82f6" style={{ margin: '0 auto' }} />
          <h1 style={{ fontSize: '24px', marginTop: '10px' }}>NetCable</h1>
          <p style={{ color: '#94a3b8', fontSize: '14px' }}>Mapeamento de Rede Inteligente</p>
        </div>
        
        <form onSubmit={handleLogin} style={{ display: 'flex', flexDirection: 'column', gap: '15px' }}>
          <input type="text" placeholder="Usuário" style={{ padding: '10px', borderRadius: '6px', border: '1px solid #334155', backgroundColor: '#0f172a', color: 'white' }} />
          <input type="password" placeholder="Senha" style={{ padding: '10px', borderRadius: '6px', border: '1px solid #334155', backgroundColor: '#0f172a', color: 'white' }} />
          <button type="submit" style={{ padding: '12px', borderRadius: '6px', border: 'none', backgroundColor: '#3b82f6', color: 'white', fontWeight: 'bold', cursor: 'pointer', marginTop: '10px' }}>
            Entrar
          </button>
        </form>
      </div>
    </div>
  )
}