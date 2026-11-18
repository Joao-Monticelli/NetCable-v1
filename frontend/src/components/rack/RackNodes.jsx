import { memo, useCallback, useEffect } from 'react'
import { Handle, Position, useStore, useUpdateNodeInternals } from 'reactflow'
import { Server, BellOff, Activity, Wrench, Thermometer } from 'lucide-react'
import { resumoPorta } from '../../utils/formatar'
import { classeStatus } from '../../utils/mapa'
import { U_PX, portasDoEquipamento, nomePortaRj45, nomePortaSfp, nomeDaPorta } from './rackUtils'
import { useModelos } from './ModelosContext'
import { t, useI18n } from '../../i18n'

// ---------------------------------------------------------------------------
// Gabinete do rack (vista frontal): cabeçalho, trilhos numerados e vão interno.
// ---------------------------------------------------------------------------
export const RackNode = memo(({ data, selected }) => {
  useI18n()
  const us = data.us || 12
  const numeros = Array.from({ length: us }, (_, i) => us - i) // de cima (U mais alto) para baixo
  const trilho = (lado) => (
    <div className={`rack-trilho rack-trilho-${lado}`}>
      {numeros.map(u => (
        <div key={u} className="rack-trilho-u" style={{ height: U_PX }}>
          <span className="rack-furo" />
          <span className="rack-numero">{u}</span>
          <span className="rack-furo" />
        </div>
      ))}
    </div>
  )
  return (
    <div className={`rack-gabinete ${selected ? 'rack-selecionado' : ''}`}>
      <div className="rack-topo">
        <Server size={14} color="#94a3b8" />
        <span className="rack-nome">{data.label}</span>
        <span className="rack-badge">{us}U</span>
      </div>
      <div className="rack-corpo" style={{ height: us * U_PX }}>
        {trilho('esq')}
        <div className="rack-vao">
          {numeros.map(u => <div key={u} className="rack-vao-u" style={{ height: U_PX }} />)}
        </div>
        {trilho('dir')}
      </div>
      <div className="rack-base"><span /><span /></div>
    </div>
  )
})

// ---------------------------------------------------------------------------
// Portas: cada porta é também um ponto de conexão (Handle) quando `conectavel`.
// ---------------------------------------------------------------------------
const estiloHandlePorta = { top: 0, left: 0, width: '100%', height: '100%', transform: 'none', border: 0, borderRadius: 0, background: 'transparent', minWidth: 0, minHeight: 0 }

function Porta({ id, nome, classe, linhaSuperior, online, uso, conectavel, piscar, link }) {
  const ligada = !!uso
  let titulo = uso ? `${nome} → ${uso}` : `${nome} (${t('livre')})`
  if (link) titulo += `\n${resumoPorta(link)}`
  // Com SNMP, o LED mostra o link real da porta; sem SNMP, uma simulação discreta.
  const acesa = link ? (online && link[1]) : (online && (ligada || piscar))
  return (
    <span className={`${classe} ${ligada ? 'em-uso' : ''} ${link && !link[1] ? 'sem-link' : ''}`} title={titulo}>
      <i className={acesa ? 'led-porta on' : 'led-porta'} />
      {/* O ponto existe sempre (os cabos precisam dele para serem desenhados, inclusive na TV);
          só não aceita novas conexões quando o mapa está em modo leitura. */}
      {conectavel !== null && (
        <Handle type="source" id={id} position={linhaSuperior ? Position.Top : Position.Bottom}
          isConnectable={conectavel} className="handle-porta" style={estiloHandlePorta} title={titulo} />
      )}
    </span>
  )
}

function Portas({ info, online, usos, conectavel, snmp }) {
  if (!info.rj45 && !info.sfp) return null
  // Porta N do desenho = N-ª interface física do equipamento (RJ45 primeiro, depois SFP).
  const links = new Map((snmp?.portas || []).map(p => [p[0], p]))
  const porLinha = Math.max(1, Math.ceil(info.rj45 / info.linhas))
  // Sem cabos cadastrados, alguns LEDs piscam só para dar vida; com cabos, só as portas em uso acendem.
  const algumUso = usos.size > 0
  return (
    <div className="face-portas">
      {info.rj45 > 0 && (
        <div className="face-portas-grade" style={{ gridTemplateColumns: `repeat(${porLinha}, minmax(4px, 8px))` }}>
          {Array.from({ length: info.rj45 }, (_, i) => {
            const id = `p:${i + 1}`
            return <Porta key={id} id={id} nome={nomePortaRj45(i + 1, info.prefixo)} classe="porta-rj45"
              linhaSuperior={Math.floor(i / porLinha) < info.linhas / 2} online={online} uso={usos.get(id)}
              conectavel={conectavel} piscar={!algumUso && i % 3 !== 2} link={links.get(i + 1)} />
          })}
        </div>
      )}
      {info.sfp > 0 && (
        <div className="face-sfp" style={{ gridTemplateColumns: `repeat(${Math.ceil(info.sfp / Math.min(2, info.sfp))}, 12px)` }}>
          {Array.from({ length: info.sfp }, (_, i) => {
            const id = `s:${i + 1}`
            return <Porta key={id} id={id} nome={nomePortaSfp(i + 1)} classe="porta-sfp"
              linhaSuperior={i < Math.ceil(info.sfp / 2)} online={online} uso={usos.get(id)}
              conectavel={conectavel} piscar={!algumUso && i < 2} link={links.get(info.rj45 + i + 1)} />
          })}
        </div>
      )}
    </div>
  )
}

const Baias = ({ porLinha, linhas, grande, online }) => (
  <div className="face-baias" style={{ gridTemplateColumns: `repeat(${porLinha}, 1fr)`, gridTemplateRows: `repeat(${linhas}, 1fr)` }}>
    {Array.from({ length: porLinha * linhas }, (_, i) => (
      <span key={i} className={grande ? 'baia baia-grande' : 'baia'}>
        <i className={online ? 'led-baia on' : 'led-baia'} style={{ animationDelay: `${(i * 0.53) % 2}s` }} />
      </span>
    ))}
  </div>
)

const Ventilacao = () => <div className="face-ventilacao" />

function Face({ data, info, usos, conectavel }) {
  const { tipo, status } = data
  const alturaU = data.alturaU || 1
  const online = status === 'online'
  const portas = <Portas info={info} online={online} usos={usos} conectavel={conectavel} snmp={data.snmp} />
  const temPortas = info.rj45 + info.sfp > 0
  switch (tipo) {
    case 'Switch Gerenciável':
    case 'Switch Não Gerenciável':
    case 'Patch Panel':
      return portas
    case 'Roteador':
      return <div className="face-linha">{portas}<span className="face-rotulo">{t('CONSOLE')}</span></div>
    case 'Firewall':
      return (
        <div className="face-linha">
          <div className="face-lcd">{status === 'online' ? 'SECURE' : status === 'offline' ? 'DOWN' : '----'}</div>
          {portas}
        </div>
      )
    case 'Servidor':
      return (
        <div className="face-linha">
          <Baias porLinha={temPortas ? 2 : 4} linhas={Math.min(alturaU, 3)} online={online} />
          {portas}
          <span className={`botao-power ${online ? 'on' : ''}`} />
        </div>
      )
    case 'Storage/NAS':
      return (
        <div className="face-linha">
          <Baias porLinha={temPortas ? 3 : 4} linhas={Math.min(alturaU, 4)} grande online={online} />
          {portas}
        </div>
      )
    case 'Nobreak':
      return (
        <div className="face-linha">
          <div className="face-lcd face-lcd-grande">{status === 'online' ? 'ON-LINE  100%' : status === 'offline' ? t('SEM COMUNICAÇÃO') : t('NOBREAK')}</div>
          {temPortas ? portas : <Ventilacao />}
        </div>
      )
    case 'Organizador de Cabos':
      return <div className="face-escova" />
    default:
      return (
        <div className="face-linha">
          {temPortas ? portas : <Ventilacao />}
          <span className={`botao-power ${online ? 'on' : ''}`} />
        </div>
      )
  }
}

// Frente completa (usada no mapa e na prévia da biblioteca de modelos).
function Frente({ data, info, usos, conectavel }) {
  const passivo = data.status === 'visual'
  const online = data.status === 'online'
  const classe = classeStatusDe(data)
  return (
    <>
      <span className="rack-orelha"><i /><i /></span>
      <div className="rack-equip-frente">
        <div className="rack-equip-id">
          <span className={`led-status ${classe}`} />
          <div className="rack-equip-textos">
            <div className="rack-equip-nome">{data.label}</div>
            <div className="rack-equip-ip">
              <span className="rack-equip-ip-texto">{passivo ? (data.modeloNome || t(data.tipo)) : data.ip}</span>
              {online && data.pingTime != null && <span className="rack-equip-ping"><Activity size={8} /> {data.pingTime}ms</span>}
              {online && data.snmp?.temp != null && <span className="rack-equip-ping" title={t('Temperatura')}><Thermometer size={8} /> {Math.round(data.snmp.temp)}°</span>}
            </div>
          </div>
          {data.manutencaoAte
            ? <Wrench size={10} className="rack-equip-sino rack-equip-manutencao" aria-label={t('Em manutenção')} />
            : data.notificar === false && !passivo && <BellOff size={10} className="rack-equip-sino" />}
        </div>
        <div className="rack-equip-face">
          <Face data={data} info={info} usos={usos} conectavel={conectavel} />
        </div>
      </div>
      <span className="rack-orelha"><i /><i /></span>
    </>
  )
}

const CLASSES = { visual: 'eq-passivo', online: 'eq-online', offline: 'eq-offline', inalcancavel: 'eq-inalcancavel' }
function classeStatusDe(data) { return CLASSES[classeStatus(data)] }

export function FrentePreview({ data, modelo }) {
  const info = portasDoEquipamento(data, modelo)
  return (
    <div className={`rack-equip ${classeStatusDe(data)}`} style={{ width: 380, height: (data.alturaU || 1) * U_PX }}>
      {/* Prévia fora do mapa: sem pontos de conexão (null) */}
      <Frente data={data} info={info} usos={new Map()} conectavel={null} />
    </div>
  )
}

const handleOculto = { opacity: 0, pointerEvents: 'none', width: 6, height: 6 }
const handleLateral = { background: '#3b82f6', width: 10, height: 10 }

export const RackDeviceNode = memo(({ id, data, selected, isConnectable }) => {
  useI18n()
  const modelos = useModelos()
  const modelo = modelos.get(data.modeloId)
  const info = portasDoEquipamento(data, modelo)

  // Quando as portas mudam (troca de modelo, altura...), o React Flow precisa medir de
  // novo os pontos de conexão; sem isso, cabos em portas novas só apareceriam ao recarregar.
  const atualizarInternos = useUpdateNodeInternals()
  useEffect(() => { atualizarInternos(id) }, [id, info.rj45, info.sfp, info.linhas, data.alturaU, data.tipo, atualizarInternos])

  // Portas em uso: handle -> "Outro equipamento · porta". Selecionado como texto para evitar re-renderizações.
  const chave = useStore(useCallback((s) => {
    const itens = []
    for (const e of s.edges) {
      if (e.source !== id && e.target !== id) continue
      const souOrigem = e.source === id
      const meu = souOrigem ? e.sourceHandle : e.targetHandle
      const outroId = souOrigem ? e.target : e.source
      const outroHandle = souOrigem ? e.targetHandle : e.sourceHandle
      const outro = s.nodeInternals.get(outroId)
      if (!meu) continue
      const nomeOutro = outro?.data?.label || outroId
      const portaOutro = outro ? nomeDaPorta(outroHandle, portasDoEquipamento(outro.data, modelos.get(outro.data.modeloId))) : null
      itens.push([meu, portaOutro ? `${nomeOutro} · ${portaOutro}` : nomeOutro])
    }
    return JSON.stringify(itens)
  }, [id, modelos]))
  const usos = new Map(JSON.parse(chave))

  return (
    <div className={`rack-equip ${classeStatusDe(data)} ${selected ? 'rack-equip-selecionado' : ''}`}
      title={`${data.inalcancavelPor ? t('Inalcançável: {nome} (uplink) está offline', { nome: data.inalcancavelNome }) + '\n' : ''}${data.label}${data.ip && data.ip !== 'Sem IP' ? ` — ${data.ip}` : ''}${modelo ? ` · ${modelo.nome}` : ''} · U${data.rackU}${data.alturaU > 1 ? `-${data.rackU + data.alturaU - 1}` : ''}`}>
      <Handle type="source" position={Position.Left} id="left" style={handleLateral} />
      <Handle type="source" position={Position.Right} id="right" style={handleLateral} />
      {/* Mantidos (invisíveis) para conexões criadas quando o equipamento estava fora do rack */}
      <Handle type="source" position={Position.Top} id="top" style={handleOculto} />
      <Handle type="source" position={Position.Bottom} id="bottom" style={handleOculto} />
      <Frente data={{ ...data, modeloNome: modelo?.nome }} info={info} usos={usos} conectavel={isConnectable} />
    </div>
  )
})

// Rótulo legível de uma porta (para o tooltip do cabo e o modal).
export { nomeDaPorta }
