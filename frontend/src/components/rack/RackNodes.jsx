import { memo } from 'react'
import { Handle, Position } from 'reactflow'
import { Server, BellOff, Activity } from 'lucide-react'
import { U_PX } from './rackUtils'

// ---------------------------------------------------------------------------
// Gabinete do rack (vista frontal): cabeçalho, trilhos numerados e vão interno.
// ---------------------------------------------------------------------------
export const RackNode = memo(({ data, selected }) => {
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
// Frentes dos equipamentos montados.
// ---------------------------------------------------------------------------
const Portas = ({ total, linhas = 2, online, sfp = 0, rotulo }) => {
  const porLinha = Math.ceil(total / linhas)
  return (
    <div className="face-portas">
      <div className="face-portas-grade" style={{ gridTemplateColumns: `repeat(${porLinha}, 8px)` }}>
        {Array.from({ length: total }, (_, i) => (
          <span key={i} className="porta-rj45">
            <i className={online && i % 3 !== 2 ? 'led-porta on' : 'led-porta'} style={{ animationDelay: `${(i * 0.37) % 1.6}s` }} />
          </span>
        ))}
      </div>
      {sfp > 0 && (
        <div className="face-sfp">
          {Array.from({ length: sfp }, (_, i) => <span key={i} className="porta-sfp"><i className={online && i < 2 ? 'led-porta on' : 'led-porta'} /></span>)}
        </div>
      )}
      {rotulo && <span className="face-rotulo">{rotulo}</span>}
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

function Face({ tipo, alturaU, online, status }) {
  const linhasPorU = Math.max(1, alturaU)
  switch (tipo) {
    case 'Switch Gerenciável':
    case 'Switch Não Gerenciável':
      return <Portas total={alturaU >= 2 ? 48 : 24} online={online} sfp={tipo === 'Switch Gerenciável' ? 4 : 0} />
    case 'Patch Panel':
      return <Portas total={24 * Math.min(alturaU, 2)} linhas={Math.min(alturaU, 2)} online={false} />
    case 'Roteador':
      return <Portas total={8} linhas={alturaU >= 2 ? 2 : 1} online={online} sfp={2} rotulo="CONSOLE" />
    case 'Firewall':
      return (
        <div className="face-linha">
          <div className="face-lcd">{status === 'online' ? 'SECURE' : status === 'offline' ? 'DOWN' : '----'}</div>
          <Portas total={6} linhas={1} online={online} />
        </div>
      )
    case 'Servidor':
      return (
        <div className="face-linha">
          <Baias porLinha={4} linhas={Math.min(linhasPorU, 3)} online={online} />
          <span className={`botao-power ${online ? 'on' : ''}`} />
        </div>
      )
    case 'Storage/NAS':
      return <Baias porLinha={4} linhas={Math.min(linhasPorU, 4)} grande online={online} />
    case 'Nobreak':
      return (
        <div className="face-linha">
          <div className="face-lcd face-lcd-grande">{status === 'online' ? 'ON-LINE  100%' : status === 'offline' ? 'SEM COMUNICAÇÃO' : 'NOBREAK'}</div>
          <Ventilacao />
        </div>
      )
    case 'Organizador de Cabos':
      return <div className="face-escova" />
    default:
      return (
        <div className="face-linha">
          <Ventilacao />
          <span className={`botao-power ${online ? 'on' : ''}`} />
        </div>
      )
  }
}

const handleOculto = { opacity: 0, pointerEvents: 'none', width: 6, height: 6 }
const handleLateral = { background: '#3b82f6', width: 10, height: 10 }

export const RackDeviceNode = memo(({ data, selected }) => {
  const passivo = data.status === 'visual'
  const online = data.status === 'online'
  const classeStatus = passivo ? 'eq-passivo' : online ? 'eq-online' : 'eq-offline'
  const compacto = (data.alturaU || 1) === 1
  return (
    <div className={`rack-equip ${classeStatus} ${selected ? 'rack-equip-selecionado' : ''}`} title={`${data.label}${data.ip && data.ip !== 'Sem IP' ? ` — ${data.ip}` : ''} · U${data.rackU}${data.alturaU > 1 ? `-${data.rackU + data.alturaU - 1}` : ''}`}>
      <Handle type="source" position={Position.Left} id="left" style={handleLateral} />
      <Handle type="source" position={Position.Right} id="right" style={handleLateral} />
      {/* Mantidos (invisíveis) para conexões criadas quando o equipamento estava fora do rack */}
      <Handle type="source" position={Position.Top} id="top" style={handleOculto} />
      <Handle type="source" position={Position.Bottom} id="bottom" style={handleOculto} />

      <span className="rack-orelha"><i /><i /></span>
      <div className="rack-equip-frente">
        <div className="rack-equip-id">
          <span className={`led-status ${classeStatus}`} />
          <div className="rack-equip-textos">
            <div className="rack-equip-nome">{data.label}</div>
            {!compacto || !passivo ? (
              <div className="rack-equip-ip">
                {passivo ? data.tipo : data.ip}
                {online && data.pingTime != null && <span className="rack-equip-ping"><Activity size={8} /> {data.pingTime}ms</span>}
              </div>
            ) : null}
          </div>
          {data.notificar === false && !passivo && <BellOff size={10} className="rack-equip-sino" />}
        </div>
        <div className="rack-equip-face">
          <Face tipo={data.tipo} alturaU={data.alturaU || 1} online={online} status={data.status} />
        </div>
      </div>
      <span className="rack-orelha"><i /><i /></span>
    </div>
  )
})
