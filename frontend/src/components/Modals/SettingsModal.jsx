import { useState } from 'react'
import { X, Save, User, Key, Mail, Send } from 'lucide-react'
import toast from 'react-hot-toast'
import { api } from '../../services/api'
import { useLang } from '../../i18n.jsx'

export default function SettingsModal({ onClose, currentUser }) {
  const { t } = useLang()
  const [email, setEmail] = useState(currentUser?.email || '')
  const [senhaAtual, setSenhaAtual] = useState('')
  const [novaSenha, setNovaSenha] = useState('')
  const [isSaving, setIsSaving] = useState(false)

  const handleSave = async (e) => {
    e.preventDefault()
    setIsSaving(true)
    try {
      await api.atualizarPerfil({ email, senha_atual: senhaAtual || null, nova_senha: novaSenha || null })
      toast.success(t('settings.updated'))
      onClose()
    } catch (error) {
      toast.error(t('settings.commError'))
    } finally {
      setIsSaving(false)
    }
  }

  return (
    <div style={{ position: 'absolute', top: 0, left: 0, width: '100%', height: '100%', backgroundColor: 'rgba(0,0,0,0.6)', display: 'flex', justifyContent: 'center', alignItems: 'center', zIndex: 1000 }}>
      <div style={{ backgroundColor: '#1e293b', padding: '25px', borderRadius: '12px', width: '400px', border: '1px solid #334155' }}>
        
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '20px' }}>
          <h2 style={{ fontSize: '20px', display: 'flex', alignItems: 'center', gap: '8px' }}>
            <User size={20} color="#3b82f6" /> {t('settings.title')}
          </h2>
          <button onClick={onClose} style={{ background: 'transparent', border: 'none', color: '#94a3b8', cursor: 'pointer' }}><X size={20} /></button>
        </div>

        <form onSubmit={handleSave} style={{ display: 'flex', flexDirection: 'column', gap: '15px' }}>
          
          <div>
            <label style={{ fontSize: '14px', color: '#94a3b8', display: 'flex', alignItems: 'center', gap: '5px' }}><Mail size={14}/> {t('settings.email')}</label>
            <input type="email" value={email} onChange={(e) => setEmail(e.target.value)} placeholder="seu@email.com" style={{ width: '100%', padding: '10px', marginTop: '5px', borderRadius: '6px', border: '1px solid #334155', backgroundColor: '#0f172a', color: 'white' }} />
          </div>

          {/* OPÇÕES EM BREVE */}
          <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', opacity: 0.6, padding: '10px', backgroundColor: '#0f172a', borderRadius: '6px', border: '1px solid #334155' }}>
            <span style={{ fontSize: '13px', display: 'flex', alignItems: 'center', gap: '5px' }}><Send size={14}/> {t('settings.telegram')}</span>
            <span style={{ fontSize: '10px', backgroundColor: '#ef4444', color: 'white', padding: '2px 6px', borderRadius: '10px', fontWeight: 'bold' }}>{t('settings.soon')}</span>
          </div>

          <div style={{ height: '1px', backgroundColor: '#334155', margin: '10px 0' }}></div>

          <h3 style={{ fontSize: '16px', display: 'flex', alignItems: 'center', gap: '5px' }}><Key size={16}/> {t('settings.changePassword')}</h3>
          
          <div>
            <label style={{ fontSize: '14px', color: '#94a3b8' }}> {t('settings.currentPassword')}</label>
            <input type="password" value={senhaAtual} onChange={(e) => setSenhaAtual(e.target.value)} placeholder={t('settings.currentPasswordPh')} style={{ width: '100%', padding: '10px', marginTop: '5px', borderRadius: '6px', border: '1px solid #334155', backgroundColor: '#0f172a', color: 'white' }} />
          </div>
          
          <div>
            <label style={{ fontSize: '14px', color: '#94a3b8' }}>{t('settings.newPassword')}</label>
            <input type="password" value={novaSenha} onChange={(e) => setNovaSenha(e.target.value)} placeholder={t('settings.newPasswordPh')} style={{ width: '100%', padding: '10px', marginTop: '5px', borderRadius: '6px', border: '1px solid #334155', backgroundColor: '#0f172a', color: 'white' }} />
          </div>

          <button type="submit" disabled={isSaving} style={{ display: 'flex', justifyContent: 'center', alignItems: 'center', gap: '5px', padding: '10px 20px', backgroundColor: isSaving ? '#475569' : '#3b82f6', color: 'white', border: 'none', borderRadius: '6px', cursor: isSaving ? 'wait' : 'pointer', marginTop: '10px' }}>
            <Save size={18} /> {isSaving ? t('settings.saving') : t('settings.saveChanges')}
          </button>
        </form>

      </div>
    </div>
  )
}
