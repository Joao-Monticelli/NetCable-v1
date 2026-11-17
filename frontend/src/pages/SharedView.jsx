import { useState, useEffect, useCallback } from 'react'
import { useParams } from 'react-router-dom'
import { Network, Loader2, CheckCircle2, XCircle, MinusCircle, AlertTriangle, Maximize, Minimize } from 'lucide-react'
import NetworkMap from '../components/NetworkMap'
import { api } from '../services/api'
import { equipamentosParaNodes, conexoesParaEdges } from '../utils/mapa'

const REFRESH_MS = 10000

export default function SharedView() {
  const { token } = useParams()
  const [projectName, setProjectName] = useState('Carregando...')
  const [mapNodes, setMapNodes] = useState([])
  const [modelos, setModelos] = useState([])
  const [mapEdges, setMapEdges] = useState([])
  const [stats, setStats] = useState({ online: 0, offline: 0, visual: 0 })
  const [isLoading, setIsLoading] = useState(true)
  const [error, setError] = useState(null)

  const [ultimaAtualizacao, setUltimaAtualizacao] = useState(null)
  const [falhaAtualizacao, setFalhaAtualizacao] = useState(false)
  const [telaCheia, setTelaCheia] = useState(false)

  const carregarProjeto = useCallback(async (inicial = false) => {
    try {
      const data = await api.obterMapaPublico(token)
      setProjectName(data.nome)
      const formattedNodes = equipamentosParaNodes(data.equipamentos)
      const formattedEdges = conexoesParaEdges(data.conexoes)
      setModelos(data.modelos || [])
      setMapNodes(formattedNodes)
      setMapEdges(formattedEdges)
      setUltimaAtualizacao(new Date())
      setFalhaAtualizacao(false)
    } catch (err) {
      // Link revogado: tira o mapa do ar mesmo numa TV já aberta.
      // Falha de rede numa atualização: mantém o último estado e sinaliza.
      if (err.status === 404) setError("Este link público é inválido ou foi revogado pelo dono do mapa.")
      else if (inicial) setError("Não foi possível conectar ao servidor do NetCable.")
      else setFalhaAtualizacao(true)
    } finally {
      if (inicial) setIsLoading(false)
    }
  }, [token])

  useEffect(() => {
    carregarProjeto(true)
    // Atualização automática para exibição contínua (ex.: TV do NOC).
    const interval = setInterval(() => carregarProjeto(false), REFRESH_MS)
    return () => clearInterval(interval)
  }, [carregarProjeto])

  useEffect(() => {
    const onChange = () => setTelaCheia(Boolean(document.fullscreenElement))
    document.addEventListener('fullscreenchange', onChange)
    return () => document.removeEventListener('fullscreenchange', onChange)
  }, [])

  const alternarTelaCheia = () => {
    if (document.fullscreenElement) document.exitFullscreen?.()
    else document.documentElement.requestFullscreen?.().catch(() => {})
  }

  const handleMapUpdate = useCallback((nodes) => {
    const counts = nodes.reduce((acc, node) => {
      if (node.type === 'rack') return acc
      if (node.data.status === 'online') acc.online++
      else if (node.data.status === 'offline') acc.offline++
      else if (node.data.status === 'visual') acc.visual++
      return acc
    }, { online: 0, offline: 0, visual: 0 })
    setStats(counts)
  }, [])

  if (isLoading) return (
    <div style={{ color: '#94a3b8', display: 'flex', justifyContent: 'center', alignItems: 'center', height: '100vh', backgroundColor: '#0f172a' }}>
      <Loader2 className="spin" style={{marginRight: '10px'}} /> Carregando mapa público...
    </div>
  )

  if (error) return (
    <div style={{ display: 'flex', flexDirection: 'column', justifyContent: 'center', alignItems: 'center', height: '100vh', backgroundColor: '#0f172a', color: 'white', padding: '20px', textAlign: 'center' }}>
      <AlertTriangle size={64} color="#ef4444" style={{ marginBottom: '20px' }} />
      <h1 style={{ fontSize: '24px', marginBottom: '10px' }}>Falha ao carregar</h1>
      <p style={{ color: '#94a3b8', maxWidth: '500px', lineHeight: '1.5' }}>{error}</p>
    </div>
  )

  return (
    <div style={{ display: 'flex', flexDirection: 'column', height: '100vh', backgroundColor: '#0f172a' }}>
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', backgroundColor: '#1e293b', padding: '10px 20px', borderBottom: '1px solid #334155' }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
          <Network size={20} color="#3b82f6" />
          <span style={{ fontWeight: 'bold' }}>{projectName} (Visualização Pública)</span>
        </div>
        <div style={{ display: 'flex', gap: '12px', alignItems: 'center' }}>
          {ultimaAtualizacao && (
            <span title={falhaAtualizacao ? 'Falha na última atualização — exibindo dados anteriores' : 'Atualiza automaticamente'} style={{ fontSize: '12px', color: falhaAtualizacao ? '#f59e0b' : '#64748b' }}>
              {falhaAtualizacao && '⚠ '}Atualizado às {ultimaAtualizacao.toLocaleTimeString()}
            </span>
          )}
          <div style={{ display: 'flex', alignItems: 'center', gap: '12px', backgroundColor: '#0f172a', padding: '6px 15px', borderRadius: '8px', border: '1px solid #334155' }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: '5px', fontSize: '13px' }}><CheckCircle2 size={16} color="#10b981" /> <span style={{ color: '#10b981', fontWeight: 'bold' }}>{stats.online}</span></div>
            <div style={{ display: 'flex', alignItems: 'center', gap: '5px', fontSize: '13px' }}><XCircle size={16} color="#ef4444" /> <span style={{ color: '#ef4444', fontWeight: 'bold' }}>{stats.offline}</span></div>
            <div style={{ display: 'flex', alignItems: 'center', gap: '5px', fontSize: '13px' }}><MinusCircle size={16} color="#64748b" /> <span style={{ color: '#64748b', fontWeight: 'bold' }}>{stats.visual}</span></div>
          </div>
          <button onClick={alternarTelaCheia} title={telaCheia ? 'Sair da tela cheia' : 'Tela cheia (TV / NOC)'} style={{ display: 'flex', alignItems: 'center', padding: '8px 12px', backgroundColor: '#334155', color: 'white', border: 'none', borderRadius: '6px', cursor: 'pointer' }}>
            {telaCheia ? <Minimize size={18} /> : <Maximize size={18} />}
          </button>
        </div>
      </div>
      <div style={{ flex: 1 }}>
        <NetworkMap initialNodes={mapNodes} initialEdges={mapEdges} onMapUpdate={handleMapUpdate} readOnly={true} monitor={false} modelos={modelos} />
      </div>
    </div>
  )
}
