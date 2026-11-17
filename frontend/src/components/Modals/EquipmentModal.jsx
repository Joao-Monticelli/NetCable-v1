import { useMemo, useState } from 'react'
import { X, Trash2, Save, Minimize, Bell, BellOff, Server, GitBranch, Wrench, Wand2, Gauge } from 'lucide-react'
import toast from 'react-hot-toast'
import { api } from '../../services/api'
import { TIPOS, TAMANHOS_RACK, ALTURAS_EQUIP, alturaPadrao, cabe, primeiraPosicaoLivre, ocupados } from '../rack/rackUtils'
import { t, useI18n } from '../../i18n'

const campo = { width: '100%', padding: '10px', marginTop: '5px', borderRadius: '6px', border: '1px solid #334155', backgroundColor: '#0f172a', color: 'white' }
const rotulo = { fontSize: '14px', color: '#94a3b8' }
const caixa = { padding: '12px', backgroundColor: '#0f172a', borderRadius: '6px', border: '1px solid #334155', display: 'grid', gap: '10px' }
const resumoModelo = (m) => [m.portas_rj45 && `${m.portas_rj45}× RJ45`, m.portas_sfp && `${m.portas_sfp}× SFP`].filter(Boolean).join(' + ') || t('sem portas')
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
  <button onClick={onClick} style={{ display: 'flex', alignItems: 'center', gap: '5px', padding: '10px', backgroundColor: '#ef4444', color: 'white', border: 'none', borderRadius: '6px', cursor: 'pointer' }}><Trash2 size={18} /> {t('Excluir')}</button>
)
const BotaoSalvar = ({ onClick, disabled }) => (
  <button onClick={onClick} disabled={disabled} style={{ display: 'flex', alignItems: 'center', gap: '5px', padding: '10px 20px', backgroundColor: disabled ? '#475569' : '#3b82f6', color: 'white', border: 'none', borderRadius: '6px', cursor: disabled ? 'not-allowed' : 'pointer' }}><Save size={18} /> {t('Salvar Alterações')}</button>
)

// ---------------------------------------------------------------- Rack
function RackModal({ node, nodes, onClose, onUpdate, onDelete }) {
  const [nome, setNome] = useState(node.data.label || '')
  const [us, setUs] = useState(node.data.us || 12)
  const montados = nodes.filter(n => n.parentNode === node.id)
  const topoOcupado = Math.max(0, ...montados.map(n => n.data.rackU + n.data.alturaU - 1))
  const livres = node.data.us - ocupados(nodes, node.id).size

  const excluir = () => {
    const aviso = montados.length ? t('Excluir o rack "{nome}" e os {n} equipamento(s) montados nele?', { nome, n: montados.length }) : t('Excluir o rack "{nome}"?', { nome })
    if (window.confirm(aviso)) onDelete(node.id)
  }

  return (
    <Moldura titulo={t('Editar Rack')} onClose={onClose}
      rodape={<><BotaoExcluir onClick={excluir} /><BotaoSalvar onClick={() => onUpdate(node.id, { label: nome, us: Number(us) })} /></>}>
      <div><label style={rotulo}>{t('Nome do rack')}</label><input value={nome} onChange={e => setNome(e.target.value)} style={campo} /></div>
      <div>
        <label style={rotulo}>{t('Tamanho')}</label>
        <select value={us} onChange={e => setUs(e.target.value)} style={campo}>
          {[...new Set([...TAMANHOS_RACK, node.data.us])].sort((a, b) => a - b).map(tam => (
            <option key={tam} value={tam} disabled={tam < topoOcupado}>{tam}U{tam < topoOcupado ? ` ${t('(equipamentos não cabem)')}` : ''}</option>
          ))}
        </select>
      </div>
      <div style={{ ...caixa, fontSize: '13px', color: '#cbd5e1' }}>
        <span><Server size={13} style={{ display: 'inline', marginRight: 5 }} />{t('{n} equipamento(s) montado(s) · {u}U livres', { n: montados.length, u: livres })}</span>
        <span style={{ color: '#64748b', fontSize: '12px' }}>{t('Arraste equipamentos do mapa para dentro do rack para montá-los, ou escolha o rack ao editar o equipamento.')}</span>
      </div>
    </Moldura>
  )
}

// ---------------------------------------------------------- Equipamento
export default function EquipmentModal({ node, nodes = [], modelos = [], onClose, onUpdate, onDelete, projectId, onCalcularUplinks, onAbrirMetricas }) {
  useI18n()
  if (node.type === 'rack') return <RackModal node={node} nodes={nodes} onClose={onClose} onUpdate={onUpdate} onDelete={onDelete} />
  return <EquipamentoModal node={node} nodes={nodes} modelos={modelos} onClose={onClose} onUpdate={onUpdate} onDelete={onDelete} projectId={projectId} onCalcularUplinks={onCalcularUplinks} onAbrirMetricas={onAbrirMetricas} />
}

const DURACOES = [[1, '1 h'], [4, '4 h'], [8, '8 h'], [24, '24 h']]

// Silenciar alertas deste equipamento por um tempo (o monitoramento continua).
function Manutencao({ node, projectId }) {
  const [ate, setAte] = useState(node.data.manutencaoAte || null)
  const [horas, setHoras] = useState(4)
  const [enviando, setEnviando] = useState(false)
  if (!projectId || projectId === 'novo') return null
  const iniciar = async () => {
    setEnviando(true)
    try {
      const r = await api.iniciarManutencao(projectId, { horas: Number(horas), equipamento_id: node.id })
      setAte(r.ate)
      toast.success(t('Alertas de {nome} silenciados até {hora}.', { nome: node.data.label, hora: new Date(r.ate).toLocaleString() }))
    } catch (err) { toast.error(err.message) } finally { setEnviando(false) }
  }
  const encerrar = async () => {
    setEnviando(true)
    try { await api.encerrarManutencao(projectId, node.id); setAte(null); toast.success(t('Manutenção encerrada.')) }
    catch (err) { toast.error(err.message) } finally { setEnviando(false) }
  }
  return (
    <div style={{ display: 'flex', alignItems: 'center', gap: '8px', fontSize: '13px', color: '#cbd5e1', flexWrap: 'wrap' }}>
      <Wrench size={14} color="#38bdf8" />
      {ate ? <>
        <span>{t('Em manutenção até {hora}', { hora: new Date(ate).toLocaleString() })}</span>
        <button type="button" onClick={encerrar} disabled={enviando} style={{ ...botaoPequeno, background: '#334155' }}>{t('Encerrar')}</button>
      </> : <>
        <span>{t('Manutenção: silenciar por')}</span>
        <select aria-label={t('Duração da manutenção')} value={horas} onChange={e => setHoras(e.target.value)} style={{ ...campo, marginTop: 0, width: 'auto', padding: '5px' }}>
          {DURACOES.map(([h, rotuloH]) => <option key={h} value={h}>{rotuloH}</option>)}
        </select>
        <button type="button" onClick={iniciar} disabled={enviando} style={{ ...botaoPequeno, background: '#0369a1' }}>{t('Silenciar')}</button>
      </>}
    </div>
  )
}

const botaoPequeno = { padding: '5px 10px', border: 0, borderRadius: '6px', color: 'white', cursor: 'pointer', fontSize: '12px' }

function EquipamentoModal({ node, nodes, modelos, onClose, onUpdate, onDelete, projectId, onCalcularUplinks, onAbrirMetricas }) {
  const [modeloId, setModeloId] = useState(node.data.modeloId || '')
  const modelo = modelos.find(m => m.id === Number(modeloId))
  const [nome, setNome] = useState(node.data.label || '')
  const [semIp, setSemIp] = useState(node.data.ip === 'Sem IP')
  const [ip, setIp] = useState(node.data.ip === 'Sem IP' ? '' : (node.data.ip || ''))
  const [tipo, setTipo] = useState(node.data.tipo || 'Roteador')
  const [monitorMode, setMonitorMode] = useState(node.data.monitorMode === 'visual' ? 'ip' : (node.data.monitorMode || 'ip'))
  const [notificar, setNotificar] = useState(node.data.notificar !== false)
  const [snmpConfig, setSnmpConfig] = useState({ username: '', authProtocol: 'SHA', authPassword: '', privProtocol: 'AES', privPassword: '', port: 161, ...(node.data.snmpConfig || {}) })
  const [dependeDe, setDependeDe] = useState(node.data.dependeDe || '')
  const candidatosUplink = nodes.filter(n => n.type !== 'rack' && n.id !== node.id).sort((a, b) => String(a.data.label).localeCompare(String(b.data.label)))

  const racks = nodes.filter(n => n.type === 'rack')
  const [rackId, setRackId] = useState(node.parentNode || '')
  const [alturaU, setAlturaU] = useState(node.data.alturaU || modelos.find(m => m.id === node.data.modeloId)?.altura_u || alturaPadrao(node.data.tipo))
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

  const escolherModelo = (id) => {
    setModeloId(id)
    const m = modelos.find(x => x.id === Number(id))
    if (m) { setTipo(m.tipo); escolherAltura(m.altura_u) }
  }

  const handleSave = () => {
    const ipFinal = semIp ? 'Sem IP' : ip.trim()
    const dados = {
      label: nome, ip: ipFinal, tipo, notificar, modeloId: modelo ? modelo.id : null, dependeDe: dependeDe || null,
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
    <Moldura titulo={t('Editar Equipamento')} onClose={onClose}
      rodape={<><BotaoExcluir onClick={() => onDelete(node.id)} /><BotaoSalvar onClick={handleSave} disabled={!posicaoValida} /></>}>
      <div><label style={rotulo}>{t('Nome do Equipamento')}</label><input type="text" value={nome} onChange={(e) => setNome(e.target.value)} style={campo} /></div>

      <div>
        <label style={rotulo}>{t('Modelo')}</label>
        <select aria-label={t('Modelo')} value={modeloId} onChange={(e) => escolherModelo(e.target.value)} style={campo}>
          <option value="">{t('Sem modelo (portas padrão do tipo)')}</option>
          {modelos.map(m => <option key={m.id} value={m.id}>{m.nome} — {t(m.tipo)}, {m.altura_u}U, {resumoModelo(m)}</option>)}
        </select>
        {modelos.length === 0 && <span style={{ fontSize: '11px', color: '#64748b' }}>{t('Cadastre modelos em ⚙️ → Modelos de equipamento.')}</span>}
      </div>

      <div>
        <label style={rotulo}>{t('Tipo')}</label>
        <select value={tipo} onChange={(e) => setTipo(e.target.value)} disabled={!!modelo} title={modelo ? t('Definido pelo modelo') : ''} style={{ ...campo, opacity: modelo ? 0.6 : 1 }}>
          {[...new Set([...TIPOS, tipo])].map(tp => <option key={tp} value={tp}>{t(tp)}</option>)}
        </select>
      </div>

      <div>
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
          <label style={rotulo}>{t('Endereço IP')}</label>
          <label style={{ fontSize: '12px', color: '#94a3b8', display: 'flex', alignItems: 'center', gap: '5px', cursor: 'pointer' }}>
            <input type="checkbox" checked={semIp} onChange={(e) => setSemIp(e.target.checked)} /> {t('Sem IP (somente visual)')}
          </label>
        </div>
        {!semIp && <input type="text" value={ip} onChange={(e) => setIp(e.target.value)} placeholder={t('Ex: 192.168.0.1')} style={campo} />}
      </div>

      {!semIp && <>
        <div>
          <label style={rotulo}>{t('Método de monitoramento')}</label>
          <select value={monitorMode} onChange={(e) => setMonitorMode(e.target.value)} style={campo}>
            <option value="ip">{t('IP / ICMP + TCP')}</option>
            <option value="snmpv3">{t('SNMPv3')}</option>
          </select>
        </div>
        <label style={{ display: 'flex', alignItems: 'center', gap: '8px', fontSize: '14px', color: '#cbd5e1', cursor: 'pointer' }} title={t('Quando desligado, quedas deste equipamento não geram e-mail/Telegram/webhook (continuam no histórico).')}>
          <input type="checkbox" checked={notificar} onChange={(e) => setNotificar(e.target.checked)} />
          {notificar ? <Bell size={15} color="#f59e0b" /> : <BellOff size={15} color="#64748b" />} {t('Notificar quando cair ou voltar')}
        </label>
      </>}

      <div style={caixa}>
        <span style={{ fontSize: '13px', color: '#cbd5e1', display: 'flex', alignItems: 'center', gap: '6px' }}><GitBranch size={14} /> {t('Depende de (uplink)')}</span>
        <select aria-label={t('Depende de (uplink)')} value={dependeDe} onChange={e => setDependeDe(e.target.value)} style={{ ...campo, marginTop: 0 }}>
          <option value="">{t('Nenhum (equipamento independente)')}</option>
          {candidatosUplink.map(n => <option key={n.id} value={n.id}>{n.data.label}{n.data.ip && n.data.ip !== 'Sem IP' ? ` — ${n.data.ip}` : ''}</option>)}
        </select>
        <span style={{ fontSize: '11px', color: '#64748b', lineHeight: 1.4 }}>{t('Se o uplink cair, este equipamento aparece como inalcançável (âmbar) e entra no alerta do uplink, em vez de gerar um alerta próprio.')}</span>
        {onCalcularUplinks && (
          <button type="button" onClick={() => onCalcularUplinks(node.id)} title={t('Percorre os cabos a partir deste equipamento e define o uplink de todos os outros.')}
            style={{ ...botaoPequeno, background: '#334155', display: 'flex', alignItems: 'center', gap: '6px', width: 'fit-content' }}>
            <Wand2 size={13} /> {t('Usar como raiz e calcular uplinks pelos cabos')}
          </button>
        )}
        {!semIp && <Manutencao node={node} projectId={projectId} />}
      </div>

      {!semIp && monitorMode === 'snmpv3' && <div style={caixa}>
        <span style={{ fontSize: '13px', color: '#94a3b8' }}>{t('Credenciais SNMPv3 (deixe as senhas vazias para manter as atuais)')}</span>
        <input value={snmpConfig.username} onChange={(e) => setSnmpConfig({ ...snmpConfig, username: e.target.value })} placeholder={t('Usuário')} style={{ ...campo, marginTop: 0, backgroundColor: '#1e293b' }} />
        <div style={{ display: 'flex', gap: '8px' }}><select value={snmpConfig.authProtocol} onChange={(e) => setSnmpConfig({ ...snmpConfig, authProtocol: e.target.value })} style={{ ...campo, marginTop: 0, flex: 1, backgroundColor: '#1e293b' }}><option>{t('SHA')}</option><option>{t('MD5')}</option></select><input type="password" value={snmpConfig.authPassword || ''} onChange={(e) => setSnmpConfig({ ...snmpConfig, authPassword: e.target.value })} placeholder={t('Senha de autenticação')} style={{ ...campo, marginTop: 0, flex: 2, backgroundColor: '#1e293b' }} /></div>
        <div style={{ display: 'flex', gap: '8px' }}><select value={snmpConfig.privProtocol} onChange={(e) => setSnmpConfig({ ...snmpConfig, privProtocol: e.target.value })} style={{ ...campo, marginTop: 0, flex: 1, backgroundColor: '#1e293b' }}><option>{t('AES')}</option><option>{t('DES')}</option><option>{t('3DES')}</option></select><input type="password" value={snmpConfig.privPassword || ''} onChange={(e) => setSnmpConfig({ ...snmpConfig, privPassword: e.target.value })} placeholder={t('Senha de privacidade')} style={{ ...campo, marginTop: 0, flex: 2, backgroundColor: '#1e293b' }} /></div>
        <div style={{ display: 'flex', gap: '8px' }}>
          <input type="number" min="1" max="65535" value={snmpConfig.port || 161} onChange={(e) => setSnmpConfig({ ...snmpConfig, port: Number(e.target.value) })} placeholder={t('Porta SNMP (padrão 161)')} style={{ ...campo, marginTop: 0, flex: 1 }} />
          <input value={snmpConfig.context || ''} onChange={(e) => setSnmpConfig({ ...snmpConfig, context: e.target.value })} placeholder={t('Contexto (opcional)')} aria-label={t('Contexto SNMPv3 (opcional)')} style={{ ...campo, marginTop: 0, flex: 2 }} />
        </div>
        {onAbrirMetricas && node.data.monitorMode === 'snmpv3' && projectId && projectId !== 'novo' && (
          <button type="button" onClick={() => onAbrirMetricas(node)} style={{ ...botaoPequeno, background: '#1d4ed8', display: 'flex', alignItems: 'center', gap: '6px', width: 'fit-content' }}>
            <Gauge size={13} /> {t('Ver métricas (CPU, temperatura, portas)')}
          </button>
        )}
      </div>}

      {racks.length > 0 && (
        <div style={caixa}>
          <span style={{ fontSize: '13px', color: '#cbd5e1', display: 'flex', alignItems: 'center', gap: '6px' }}><Server size={14} /> {t('Montagem em rack')}</span>
          <select aria-label={t('Rack')} value={rackId} onChange={e => escolherRack(e.target.value)} style={{ ...campo, marginTop: 0 }}>
            <option value="">{t('Fora do rack (solto no mapa)')}</option>
            {racks.map(r => <option key={r.id} value={r.id}>{r.data.label} ({r.data.us}U)</option>)}
          </select>
          {rack && (
            <div style={{ display: 'flex', gap: '8px' }}>
              <label style={{ ...rotulo, fontSize: '12px', flex: 1 }}>{t('Altura')}
                <select aria-label={t('Altura')} value={alturaU} onChange={e => escolherAltura(Number(e.target.value))} disabled={!!modelo} title={modelo ? t('Definida pelo modelo') : ''} style={{ ...campo, opacity: modelo ? 0.6 : 1 }}>
                  {ALTURAS_EQUIP.filter(a => a <= rack.data.us).map(a => <option key={a} value={a}>{a}U</option>)}
                </select>
              </label>
              <label style={{ ...rotulo, fontSize: '12px', flex: 2 }}>{t('Posição')}
                <select aria-label={t('Posição')} value={posicaoValida ? rackU : ''} onChange={e => setRackU(Number(e.target.value))} style={campo}>
                  {!posicaoValida && <option value="">{t('Sem espaço para {u}U', { u: alturaU })}</option>}
                  {posicoes.map(u => <option key={u} value={u}>{faixaU(u, alturaU)}</option>)}
                </select>
              </label>
            </div>
          )}
        </div>
      )}

      {node.type === 'custom' && (
        <button onClick={restaurarTamanho} style={{ display: 'flex', alignItems: 'center', gap: '5px', padding: '8px 12px', backgroundColor: '#334155', color: 'white', border: 'none', borderRadius: '6px', cursor: 'pointer', fontSize: '12px', width: 'fit-content' }}>
          <Minimize size={14} /> {t('Restaurar tamanho padrão do card')}
        </button>
      )}
    </Moldura>
  )
}
