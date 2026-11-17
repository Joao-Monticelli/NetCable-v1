import { useMemo, useState } from 'react'
import { X, Trash2, Save, Minimize, Bell, BellOff, Server } from 'lucide-react'
import { TIPOS, TAMANHOS_RACK, ALTURAS_EQUIP, alturaPadrao, cabe, primeiraPosicaoLivre, ocupados } from '../rack/rackUtils'

const campo = { width: '100%', padding: '10px', marginTop: '5px', borderRadius: '6px', border: '1px solid #334155', backgroundColor: '#0f172a', color: 'white' }
const rotulo = { fontSize: '14px', color: '#94a3b8' }
const caixa = { padding: '12px', backgroundColor: '#0f172a', borderRadius: '6px', border: '1px solid #334155', display: 'grid', gap: '10px' }
const faixaU = (u, a) => a > 1 ? `U${u}–U${u + a - 1}` : `U${u}`

function Moldura({ titulo, onClose, children, rodape }) {
  return (
    <div style={{ position: 'absolute', inset: 0, backgroundColor: 'rgba(0,0,0,0.6)', display: 'flex', justifyContent: 'center', alignItems: 'center', zIndex: 1000 }}>
      <div style={{ backgroundColor: '#1e293b', padding: '25px', borderRadius: '12px', width: '420px', maxHeight: '92vh', overflow: 'auto', border: '1px solid #334155' }}>
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '20px' }}>
          <h2 style={{ fontSize: '20px' }}>{titulo}</h2>
          <button onClick={onClose} style={{ background: 'transparent', border: 'none', color: '#94a3b8', cursor: 'pointer' }}><X size={20} /></button>
        </div>
        <div style={{ display: 'flex', flexDirection: 'column', gap: '15px' }}>{children}</div>
        <div style={{ display: 'flex', justifyContent: 'space-between', marginTop: '28px' }}>{rodape}</div>
      </div>
    </div>
  )
}

const BotaoExcluir = ({ onClick }) => (
  <button onClick={onClick} style={{ display: 'flex', alignItems: 'center', gap: '5px', padding: '10px', backgroundColor: '#ef4444', color: 'white', border: 'none', borderRadius: '6px', cursor: 'pointer' }}><Trash2 size={18} /> Excluir</button>
)
const BotaoSalvar = ({ onClick, disabled }) => (
  <button onClick={onClick} disabled={disabled} style={{ display: 'flex', alignItems: 'center', gap: '5px', padding: '10px 20px', backgroundColor: disabled ? '#475569' : '#3b82f6', color: 'white', border: 'none', borderRadius: '6px', cursor: disabled ? 'not-allowed' : 'pointer' }}><Save size={18} /> Salvar Alterações</button>
)

// ---------------------------------------------------------------- Rack
function RackModal({ node, nodes, onClose, onUpdate, onDelete }) {
  const [nome, setNome] = useState(node.data.label || '')
  const [us, setUs] = useState(node.data.us || 12)
  const montados = nodes.filter(n => n.parentNode === node.id)
  const topoOcupado = Math.max(0, ...montados.map(n => n.data.rackU + n.data.alturaU - 1))
  const livres = node.data.us - ocupados(nodes, node.id).size

  const excluir = () => {
    const aviso = montados.length ? `Excluir o rack "${nome}" e os ${montados.length} equipamento(s) montados nele?` : `Excluir o rack "${nome}"?`
    if (window.confirm(aviso)) onDelete(node.id)
  }

  return (
    <Moldura titulo="Editar Rack" onClose={onClose}
      rodape={<><BotaoExcluir onClick={excluir} /><BotaoSalvar onClick={() => onUpdate(node.id, { label: nome, us: Number(us) })} /></>}>
      <div><label style={rotulo}>Nome do rack</label><input value={nome} onChange={e => setNome(e.target.value)} style={campo} /></div>
      <div>
        <label style={rotulo}>Tamanho</label>
        <select value={us} onChange={e => setUs(e.target.value)} style={campo}>
          {[...new Set([...TAMANHOS_RACK, node.data.us])].sort((a, b) => a - b).map(t => (
            <option key={t} value={t} disabled={t < topoOcupado}>{t}U{t < topoOcupado ? ' (equipamentos não cabem)' : ''}</option>
          ))}
        </select>
      </div>
      <div style={{ ...caixa, fontSize: '13px', color: '#cbd5e1' }}>
        <span><Server size={13} style={{ display: 'inline', marginRight: 5 }} />{montados.length} equipamento(s) montado(s) · {livres}U livres</span>
        <span style={{ color: '#64748b', fontSize: '12px' }}>Arraste equipamentos do mapa para dentro do rack para montá-los, ou escolha o rack ao editar o equipamento.</span>
      </div>
    </Moldura>
  )
}

// ---------------------------------------------------------- Equipamento
export default function EquipmentModal({ node, nodes = [], onClose, onUpdate, onDelete }) {
  if (node.type === 'rack') return <RackModal node={node} nodes={nodes} onClose={onClose} onUpdate={onUpdate} onDelete={onDelete} />
  return <EquipamentoModal node={node} nodes={nodes} onClose={onClose} onUpdate={onUpdate} onDelete={onDelete} />
}

function EquipamentoModal({ node, nodes, onClose, onUpdate, onDelete }) {
  const [nome, setNome] = useState(node.data.label || '')
  const [semIp, setSemIp] = useState(node.data.ip === 'Sem IP')
  const [ip, setIp] = useState(node.data.ip === 'Sem IP' ? '' : (node.data.ip || ''))
  const [tipo, setTipo] = useState(node.data.tipo || 'Roteador')
  const [monitorMode, setMonitorMode] = useState(node.data.monitorMode === 'visual' ? 'ip' : (node.data.monitorMode || 'ip'))
  const [notificar, setNotificar] = useState(node.data.notificar !== false)
  const [snmpConfig, setSnmpConfig] = useState({ username: '', authProtocol: 'SHA', authPassword: '', privProtocol: 'AES', privPassword: '', port: 161, ...(node.data.snmpConfig || {}) })

  const racks = nodes.filter(n => n.type === 'rack')
  const [rackId, setRackId] = useState(node.parentNode || '')
  const [alturaU, setAlturaU] = useState(node.data.alturaU || alturaPadrao(node.data.tipo))
  const [rackU, setRackU] = useState(node.data.rackU || null)
  const rack = racks.find(r => r.id === rackId)

  // Posições em que o equipamento cabe no rack escolhido (de cima para baixo).
  const posicoes = useMemo(() => {
    if (!rack) return []
    const lista = []
    for (let u = rack.data.us - alturaU + 1; u >= 1; u--) if (cabe(nodes, rack, u, alturaU, node.id)) lista.push(u)
    return lista
  }, [rack, alturaU, nodes, node.id])
  const posicaoValida = rack ? posicoes.includes(Number(rackU)) : true

  const escolherRack = (id) => {
    setRackId(id)
    const r = racks.find(x => x.id === id)
    if (r) setRackU(primeiraPosicaoLivre(nodes, r, alturaU, node.id))
  }
  const escolherAltura = (a) => {
    setAlturaU(a)
    if (!rack) return
    // Mantém a posição atual (ou a original) se couber; senão, a primeira livre.
    const original = node.parentNode === rack.id ? node.data.rackU : null
    const candidatas = [Number(rackU), original].filter(Boolean)
    setRackU(candidatas.find(u => cabe(nodes, rack, u, a, node.id)) ?? primeiraPosicaoLivre(nodes, rack, a, node.id))
  }

  const handleSave = () => {
    const ipFinal = semIp ? 'Sem IP' : ip.trim()
    const dados = {
      label: nome, ip: ipFinal, tipo, notificar,
      monitorMode: semIp ? 'visual' : monitorMode,
      snmpConfig: !semIp && monitorMode === 'snmpv3' ? snmpConfig : null,
      rackId: rack ? rack.id : null, rackU: rack ? Number(rackU) : null, alturaU: rack ? Number(alturaU) : null,
    }
    // Sem IP vira "somente visual"; ao ganhar um IP, aguarda a próxima verificação.
    if (semIp) dados.status = 'visual'
    else if (node.data.status === 'visual') dados.status = 'offline'
    onUpdate(node.id, dados)
  }

  const restaurarTamanho = () => {
    const el = document.querySelector(`.react-flow__node[data-id="${node.id}"]`)
    if (el) { el.style.width = '200px'; el.style.height = '80px' }
  }

  return (
    <Moldura titulo="Editar Equipamento" onClose={onClose}
      rodape={<><BotaoExcluir onClick={() => onDelete(node.id)} /><BotaoSalvar onClick={handleSave} disabled={!posicaoValida} /></>}>
      <div><label style={rotulo}>Nome do Equipamento</label><input type="text" value={nome} onChange={(e) => setNome(e.target.value)} style={campo} /></div>

      <div>
        <label style={rotulo}>Tipo</label>
        <select value={tipo} onChange={(e) => setTipo(e.target.value)} style={campo}>
          {[...new Set([...TIPOS, tipo])].map(t => <option key={t} value={t}>{t}</option>)}
        </select>
      </div>

      <div>
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
          <label style={rotulo}>Endereço IP</label>
          <label style={{ fontSize: '12px', color: '#94a3b8', display: 'flex', alignItems: 'center', gap: '5px', cursor: 'pointer' }}>
            <input type="checkbox" checked={semIp} onChange={(e) => setSemIp(e.target.checked)} /> Sem IP (somente visual)
          </label>
        </div>
        {!semIp && <input type="text" value={ip} onChange={(e) => setIp(e.target.value)} placeholder="Ex: 192.168.0.1" style={campo} />}
      </div>

      {!semIp && <>
        <div>
          <label style={rotulo}>Método de monitoramento</label>
          <select value={monitorMode} onChange={(e) => setMonitorMode(e.target.value)} style={campo}>
            <option value="ip">IP / ICMP + TCP</option>
            <option value="snmpv3">SNMPv3</option>
          </select>
        </div>
        <label style={{ display: 'flex', alignItems: 'center', gap: '8px', fontSize: '14px', color: '#cbd5e1', cursor: 'pointer' }} title="Quando desligado, quedas deste equipamento não geram e-mail/Telegram/webhook (continuam no histórico).">
          <input type="checkbox" checked={notificar} onChange={(e) => setNotificar(e.target.checked)} />
          {notificar ? <Bell size={15} color="#f59e0b" /> : <BellOff size={15} color="#64748b" />} Notificar quando cair ou voltar
        </label>
      </>}

      {!semIp && monitorMode === 'snmpv3' && <div style={caixa}>
        <span style={{ fontSize: '13px', color: '#94a3b8' }}>Credenciais SNMPv3 (deixe as senhas vazias para manter as atuais)</span>
        <input value={snmpConfig.username} onChange={(e) => setSnmpConfig({ ...snmpConfig, username: e.target.value })} placeholder="Usuário" style={{ ...campo, marginTop: 0, backgroundColor: '#1e293b' }} />
        <div style={{ display: 'flex', gap: '8px' }}><select value={snmpConfig.authProtocol} onChange={(e) => setSnmpConfig({ ...snmpConfig, authProtocol: e.target.value })} style={{ ...campo, marginTop: 0, flex: 1, backgroundColor: '#1e293b' }}><option>SHA</option><option>MD5</option></select><input type="password" value={snmpConfig.authPassword || ''} onChange={(e) => setSnmpConfig({ ...snmpConfig, authPassword: e.target.value })} placeholder="Senha de autenticação" style={{ ...campo, marginTop: 0, flex: 2, backgroundColor: '#1e293b' }} /></div>
        <div style={{ display: 'flex', gap: '8px' }}><select value={snmpConfig.privProtocol} onChange={(e) => setSnmpConfig({ ...snmpConfig, privProtocol: e.target.value })} style={{ ...campo, marginTop: 0, flex: 1, backgroundColor: '#1e293b' }}><option>AES</option><option>DES</option><option>3DES</option></select><input type="password" value={snmpConfig.privPassword || ''} onChange={(e) => setSnmpConfig({ ...snmpConfig, privPassword: e.target.value })} placeholder="Senha de privacidade" style={{ ...campo, marginTop: 0, flex: 2, backgroundColor: '#1e293b' }} /></div>
        <input type="number" min="1" max="65535" value={snmpConfig.port || 161} onChange={(e) => setSnmpConfig({ ...snmpConfig, port: Number(e.target.value) })} placeholder="Porta SNMP (padrão 161)" style={{ ...campo, marginTop: 0 }} />
      </div>}

      {racks.length > 0 && (
        <div style={caixa}>
          <span style={{ fontSize: '13px', color: '#cbd5e1', display: 'flex', alignItems: 'center', gap: '6px' }}><Server size={14} /> Montagem em rack</span>
          <select aria-label="Rack" value={rackId} onChange={e => escolherRack(e.target.value)} style={{ ...campo, marginTop: 0 }}>
            <option value="">Fora do rack (solto no mapa)</option>
            {racks.map(r => <option key={r.id} value={r.id}>{r.data.label} ({r.data.us}U)</option>)}
          </select>
          {rack && (
            <div style={{ display: 'flex', gap: '8px' }}>
              <label style={{ ...rotulo, fontSize: '12px', flex: 1 }}>Altura
                <select aria-label="Altura" value={alturaU} onChange={e => escolherAltura(Number(e.target.value))} style={campo}>
                  {ALTURAS_EQUIP.filter(a => a <= rack.data.us).map(a => <option key={a} value={a}>{a}U</option>)}
                </select>
              </label>
              <label style={{ ...rotulo, fontSize: '12px', flex: 2 }}>Posição
                <select aria-label="Posição" value={posicaoValida ? rackU : ''} onChange={e => setRackU(Number(e.target.value))} style={campo}>
                  {!posicaoValida && <option value="">Sem espaço para {alturaU}U</option>}
                  {posicoes.map(u => <option key={u} value={u}>{faixaU(u, alturaU)}</option>)}
                </select>
              </label>
            </div>
          )}
        </div>
      )}

      {node.type === 'custom' && (
        <button onClick={restaurarTamanho} style={{ display: 'flex', alignItems: 'center', gap: '5px', padding: '8px 12px', backgroundColor: '#334155', color: 'white', border: 'none', borderRadius: '6px', cursor: 'pointer', fontSize: '12px', width: 'fit-content' }}>
          <Minimize size={14} /> Restaurar tamanho padrão do card
        </button>
      )}
    </Moldura>
  )
}
