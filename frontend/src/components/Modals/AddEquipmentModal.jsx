import { useState } from 'react'
import { X, Plus, Server, Wifi, Shield, Monitor, Activity, CheckCircle, XCircle, Network } from 'lucide-react'
import { api } from '../../services/api' // IMPORTANDO A API

export default function AddEquipmentModal({ onClose, onAdd }) {
  const [nome, setNome] = useState('')
  const [ip, setIp] = useState('')
  const [tipo, setTipo] = useState('Roteador')
  const [semIp, setSemIp] = useState(false)
  
  const [tipos, setTipos] = useState([
    { value: 'Roteador', icon: Wifi },
    { value: 'Switch Gerenciável', icon: Server },
    { value: 'Switch Não Gerenciável', icon: Server },
    { value: 'Firewall', icon: Shield },
    { value: 'Servidor', icon: Server },
    { value: 'PC', icon: Monitor }
  ])
  const [novoTipo, setNovoTipo] = useState('')
  const [mostrarNovoTipo, setMostrarNovoTipo] = useState(false)

  const [isTesting, setIsTesting] = useState(false)
  const [testResult, setTestResult] = useState(null)
  const [pingTime, setPingTime] = useState(null)

  const handleTestConnection = async () => {
    if (semIp) return
    if (!ip) { setTestResult('error'); return }
    
    setIsTesting(true)
    setTestResult(null)
    setPingTime(null)

    try {
      const data = await api.ping(ip) // Usando a API
      if (data.status === 'online') {
        setTestResult('success')
        setPingTime(data.tempo_ms)
      } else {
        setTestResult('error')
      }
    } catch (error) {
      setTestResult('error')
    } finally {
      setIsTesting(false)
    }
  }

  const handleAdd = async () => {
    if (!nome) { alert('Preencha o Nome.'); return }
    if (!semIp && !ip) { alert('Preencha o IP ou marque Sem IP.'); return }

    let finalStatus = 'offline'
    let finalPingTime = null

    if (semIp) {
      finalStatus = 'visual'
    } else {
      if (testResult !== 'success') {
        try {
          const data = await api.ping(ip)
          if (data.status === 'online') {
            finalStatus = 'online'
            finalPingTime = data.tempo_ms
          } else {
            if (!window.confirm('O IP não respondeu. Deseja adicionar mesmo assim?')) return
          }
        } catch (error) {
          if (!window.confirm('Erro no backend. Deseja adicionar mesmo assim?')) return
        }
      } else {
        finalStatus = 'online'
        finalPingTime = pingTime
      }
    }
    
    onAdd({ nome, ip: semIp ? 'Sem IP' : ip, tipo, status: finalStatus, pingTime: finalPingTime })
  }

  const handleAddTipo = () => {
    if (novoTipo.trim() !== '') {
      setTipos([...tipos, { value: novoTipo, icon: Server }])
      setTipo(novoTipo)
      setNovoTipo('')
      setMostrarNovoTipo(false)
    }
  }

  return (
    <div style={{ position: 'absolute', top: 0, left: 0, width: '100%', height: '100%', backgroundColor: 'rgba(0,0,0,0.6)', display: 'flex', justifyContent: 'center', alignItems: 'center', zIndex: 1000 }}>
      <div style={{ backgroundColor: '#1e293b', padding: '25px', borderRadius: '12px', width: '480px', border: '1px solid #334155' }}>
        
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '20px' }}>
          <h2 style={{ fontSize: '20px' }}>Adicionar Equipamento</h2>
          <button onClick={onClose} style={{ background: 'transparent', border: 'none', color: '#94a3b8', cursor: 'pointer' }}><X size={20} /></button>
        </div>

        <div style={{ display: 'flex', flexDirection: 'column', gap: '15px' }}>
          <div>
            <label style={{ fontSize: '14px', color: '#94a3b8' }}>Nome do Equipamento</label>
            <input type="text" value={nome} onChange={(e) => setNome(e.target.value)} placeholder="Ex: Switch Andar 1" style={{ width: '100%', padding: '10px', marginTop: '5px', borderRadius: '6px', border: '1px solid #334155', backgroundColor: '#0f172a', color: 'white' }} />
          </div>
          
          <div style={{ display: 'flex', alignItems: 'center', gap: '10px', marginTop: '5px' }}>
            <input type="checkbox" id="semIp" checked={semIp} onChange={(e) => setSemIp(e.target.checked)} style={{ width: '16px', height: '16px', cursor: 'pointer' }} />
            <label htmlFor="semIp" style={{ fontSize: '14px', color: '#94a3b8', cursor: 'pointer', display: 'flex', alignItems: 'center', gap: '5px' }}>
              <Network size={16} /> Equipamento sem IP (Camada 2)
            </label>
          </div>

          <div style={{ opacity: semIp ? 0.5 : 1, pointerEvents: semIp ? 'none' : 'auto' }}>
            <label style={{ fontSize: '14px', color: '#94a3b8' }}>Endereço IP</label>
            <div style={{ display: 'flex', gap: '10px', marginTop: '5px' }}>
              <input type="text" value={ip} onChange={(e) => setIp(e.target.value)} placeholder={semIp ? "Desabilitado" : "Ex: 192.168.0.10"} disabled={semIp} style={{ flex: 1, padding: '10px', borderRadius: '6px', border: '1px solid #334155', backgroundColor: '#0f172a', color: 'white' }} />
              <button onClick={handleTestConnection} disabled={isTesting || semIp} style={{ display: 'flex', alignItems: 'center', gap: '5px', padding: '0 15px', backgroundColor: isTesting ? '#475569' : '#334155', color: 'white', border: 'none', borderRadius: '6px', cursor: isTesting ? 'wait' : 'pointer' }}>
                {isTesting ? <Activity size={18} className="spin" /> : <Wifi size={18} />} Testar
              </button>
            </div>
            {testResult === 'success' && (
              <div style={{ display: 'flex', alignItems: 'center', gap: '5px', color: '#10b981', fontSize: '13px', marginTop: '8px' }}>
                <CheckCircle size={16} /> Online! Resposta em {pingTime}ms.
              </div>
            )}
            {testResult === 'error' && (
              <div style={{ display: 'flex', alignItems: 'center', gap: '5px', color: '#ef4444', fontSize: '13px', marginTop: '8px' }}>
                <XCircle size={16} /> Falha na conexão. Verifique o IP.
              </div>
            )}
          </div>

          <div>
            <label style={{ fontSize: '14px', color: '#94a3b8' }}>Tipo de Equipamento</label>
            <div style={{ display: 'flex', gap: '10px', marginTop: '5px' }}>
              <select value={tipo} onChange={(e) => setTipo(e.target.value)} style={{ flex: 1, padding: '10px', borderRadius: '6px', border: '1px solid #334155', backgroundColor: '#0f172a', color: 'white' }}>
                {tipos.map((t) => <option key={t.value} value={t.value}>{t.value}</option>)}
              </select>
              <button onClick={() => setMostrarNovoTipo(!mostrarNovoTipo)} style={{ padding: '10px', backgroundColor: '#334155', color: 'white', border: 'none', borderRadius: '6px', cursor: 'pointer' }} title="Criar novo tipo"><Plus size={18} /></button>
            </div>
          </div>

          {mostrarNovoTipo && (
            <div style={{ display: 'flex', gap: '10px', marginTop: '5px' }}>
              <input type="text" value={novoTipo} onChange={(e) => setNovoTipo(e.target.value)} placeholder="Novo tipo..." style={{ flex: 1, padding: '10px', borderRadius: '6px', border: '1px solid #3b82f6', backgroundColor: '#0f172a', color: 'white' }} />
              <button onClick={handleAddTipo} style={{ padding: '10px', backgroundColor: '#3b82f6', color: 'white', border: 'none', borderRadius: '6px', cursor: 'pointer' }}>Adicionar</button>
            </div>
          )}
        </div>

        <div style={{ display: 'flex', justifyContent: 'flex-end', marginTop: '30px', gap: '10px' }}>
          <button onClick={onClose} style={{ padding: '10px 20px', backgroundColor: 'transparent', color: '#94a3b8', border: '1px solid #334155', borderRadius: '6px', cursor: 'pointer' }}>Cancelar</button>
          <button onClick={handleAdd} style={{ display: 'flex', alignItems: 'center', gap: '5px', padding: '10px 20px', backgroundColor: '#3b82f6', color: 'white', border: 'none', borderRadius: '6px', cursor: 'pointer' }}><Plus size={18} /> Adicionar</button>
        </div>

      </div>
    </div>
  )
}