import { useState } from 'react'
import { X, Trash2, Save, Maximize, Minimize } from 'lucide-react'

import { useLang, typeLabel } from '../../i18n.jsx'

export default function EquipmentModal({ node, onClose, onUpdate, onDelete }) {
  const { t } = useLang()
  const [nome, setNome] = useState(node.data.label || '')
  const [ip, setIp] = useState(node.data.ip || '')
  const [tipo, setTipo] = useState(node.data.tipo || 'router')
  const [monitorMode, setMonitorMode] = useState(node.data.monitorMode || 'ip')
  const [snmpConfig, setSnmpConfig] = useState({ username: '', authProtocol: 'SHA', authPassword: '', privProtocol: 'AES', privPassword: '', port: 161, ...(node.data.snmpConfig || {}) })

  const handleSave = () => {
    onUpdate(node.id, { label: nome, ip, tipo, monitorMode: (ip === 'Sem IP' || ip === 'No IP') ? 'visual' : monitorMode, snmpConfig: monitorMode === 'snmpv3' ? snmpConfig : null })
  }

  // Função para restaurar o tamanho original
  const handleResetSize = () => {
    // Acessa a referência do elemento pai do React Flow (nó) e altera o CSS
    const nodeElement = document.querySelector(`.react-flow__node[data-id="${node.id}"]`)
    if (nodeElement) {
      nodeElement.style.width = '200px'
      nodeElement.style.height = '80px'
    }
  }

  return (
    <div style={{ position: 'absolute', top: 0, left: 0, width: '100%', height: '100%', backgroundColor: 'rgba(0,0,0,0.6)', display: 'flex', justifyContent: 'center', alignItems: 'center', zIndex: 1000 }}>
      <div style={{ backgroundColor: '#1e293b', padding: '25px', borderRadius: '12px', width: '400px', border: '1px solid #334155' }}>
        
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '20px' }}>
          <h2 style={{ fontSize: '20px' }}>{t('equipment.title')}</h2>
          <button onClick={onClose} style={{ background: 'transparent', border: 'none', color: '#94a3b8', cursor: 'pointer' }}><X size={20} /></button>
        </div>

        <div style={{ display: 'flex', flexDirection: 'column', gap: '15px' }}>
          <div>
            <label style={{ fontSize: '14px', color: '#94a3b8' }}>{t('equipment.name')}</label>
            <input type="text" value={nome} onChange={(e) => setNome(e.target.value)} style={{ width: '100%', padding: '10px', marginTop: '5px', borderRadius: '6px', border: '1px solid #334155', backgroundColor: '#0f172a', color: 'white' }} />
          </div>

          <div>
            <label style={{ fontSize: '14px', color: '#94a3b8' }}>{t('equipment.monitorMethod')}</label>
            <select value={(ip === 'Sem IP' || ip === 'No IP') ? 'visual' : monitorMode} onChange={(e) => setMonitorMode(e.target.value)} disabled={ip === 'Sem IP' || ip === 'No IP'} style={{ width: '100%', padding: '10px', marginTop: '5px', borderRadius: '6px', border: '1px solid #334155', backgroundColor: '#0f172a', color: 'white' }}>
              <option value="ip">{t('addEquipment.ipOption')}</option>
              <option value="snmpv3">{t('addEquipment.snmpOption')}</option>
            </select>
          </div>

          {monitorMode === 'snmpv3' && ip !== 'Sem IP' && ip !== 'No IP' && <div style={{ padding: '12px', backgroundColor: '#0f172a', borderRadius: '6px', border: '1px solid #334155', display: 'grid', gap: '10px' }}>
            <span style={{ fontSize: '13px', color: '#94a3b8' }}>{t('equipment.snmpHint')}</span>
            <input value={snmpConfig.username} onChange={(e) => setSnmpConfig({ ...snmpConfig, username: e.target.value })} placeholder={t('equipment.user')} style={{ padding: '9px', borderRadius: '6px', border: '1px solid #334155', backgroundColor: '#1e293b', color: 'white' }} />
            <div style={{ display: 'flex', gap: '8px' }}><select value={snmpConfig.authProtocol} onChange={(e) => setSnmpConfig({ ...snmpConfig, authProtocol: e.target.value })} style={{ flex: 1, padding: '9px', backgroundColor: '#1e293b', color: 'white', border: '1px solid #334155', borderRadius: '6px' }}><option>SHA</option><option>MD5</option></select><input type="password" value={snmpConfig.authPassword || ''} onChange={(e) => setSnmpConfig({ ...snmpConfig, authPassword: e.target.value })} placeholder={t('equipment.authPass')} style={{ flex: 2, padding: '9px', borderRadius: '6px', border: '1px solid #334155', backgroundColor: '#1e293b', color: 'white' }} /></div>
            <div style={{ display: 'flex', gap: '8px' }}><select value={snmpConfig.privProtocol} onChange={(e) => setSnmpConfig({ ...snmpConfig, privProtocol: e.target.value })} style={{ flex: 1, padding: '9px', backgroundColor: '#1e293b', color: 'white', border: '1px solid #334155', borderRadius: '6px' }}><option>AES</option><option>DES</option><option>3DES</option></select><input type="password" value={snmpConfig.privPassword || ''} onChange={(e) => setSnmpConfig({ ...snmpConfig, privPassword: e.target.value })} placeholder={t('equipment.privPass')} style={{ flex: 2, padding: '9px', borderRadius: '6px', border: '1px solid #334155', backgroundColor: '#1e293b', color: 'white' }} /></div>
            <input type="number" min="1" max="65535" value={snmpConfig.port || 161} onChange={(e) => setSnmpConfig({ ...snmpConfig, port: Number(e.target.value) })} placeholder={t('equipment.snmpPort')} style={{ padding: '9px', borderRadius: '6px', border: '1px solid #334155', backgroundColor: '#0f172a', color: 'white' }} />
          </div>}
          
          <div>
            <label style={{ fontSize: '14px', color: '#94a3b8' }}>{t('equipment.ip')}</label>
            <input type="text" value={ip} onChange={(e) => setIp(e.target.value)} placeholder="Ex: 192.168.0.1" style={{ width: '100%', padding: '10px', marginTop: '5px', borderRadius: '6px', border: '1px solid #334155', backgroundColor: '#0f172a', color: 'white' }} />
          </div>

          <div>
            <label style={{ fontSize: '14px', color: '#94a3b8' }}>{t('equipment.type')}</label>
            <select value={tipo} onChange={(e) => setTipo(e.target.value)} style={{ width: '100%', padding: '10px', marginTop: '5px', borderRadius: '6px', border: '1px solid #334155', backgroundColor: '#0f172a', color: 'white' }}>
              {/* keep legacy PT values selectable for old diagrams */}
              {!['router', 'managed-switch', 'unmanaged-switch', 'firewall', 'server', 'pc'].includes(tipo) && (
                <option value={tipo}>{typeLabel(t, tipo)}</option>
              )}
              <option value="router">{t('types.router')}</option>
              <option value="managed-switch">{t('types.managedSwitch')}</option>
              <option value="unmanaged-switch">{t('types.unmanagedSwitch')}</option>
              <option value="firewall">{t('types.firewall')}</option>
              <option value="server">{t('types.server')}</option>
              <option value="pc">{t('types.pc')}</option>
            </select>
          </div>
          
          {/* Botão de Redimensionamento */}
          <div style={{ marginTop: '10px', padding: '10px', backgroundColor: '#0f172a', borderRadius: '6px', border: '1px solid #334155' }}>
            <span style={{ fontSize: '13px', color: '#94a3b8', display: 'block', marginBottom: '8px' }}>
              <Maximize size={14} style={{ display: 'inline', marginRight: '5px' }} />
              {t('equipment.tip')}
            </span>
            <button onClick={handleResetSize} style={{ display: 'flex', alignItems: 'center', gap: '5px', padding: '8px 12px', backgroundColor: '#334155', color: 'white', border: 'none', borderRadius: '6px', cursor: 'pointer', fontSize: '12px' }}>
              <Minimize size={14} /> {t('equipment.resetSize')}
            </button>
          </div>
        </div>

        <div style={{ display: 'flex', justifyContent: 'space-between', marginTop: '30px' }}>
          <button onClick={() => onDelete(node.id)} style={{ display: 'flex', alignItems: 'center', gap: '5px', padding: '10px', backgroundColor: '#ef4444', color: 'white', border: 'none', borderRadius: '6px', cursor: 'pointer' }}>
            <Trash2 size={18} /> {t('equipment.delete')}
          </button>
          <button onClick={handleSave} style={{ display: 'flex', alignItems: 'center', gap: '5px', padding: '10px 20px', backgroundColor: '#3b82f6', color: 'white', border: 'none', borderRadius: '6px', cursor: 'pointer' }}>
            <Save size={18} /> {t('equipment.saveChanges')}
          </button>
        </div>

      </div>
    </div>
  )
}
