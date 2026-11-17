import { useState } from 'react'
import { X, Save, User, Key, Mail, Bell, FileText, Send, Loader2 } from 'lucide-react'
import toast from 'react-hot-toast'
import { api } from '../../services/api'

const PAPEL_ROTULO = { admin: 'Administrador', editor: 'Editor', visualizador: 'Visualizador' }
const input = { width: '100%', padding: '10px', marginTop: '5px', borderRadius: '6px', border: '1px solid #334155', backgroundColor: '#0f172a', color: 'white' }
const caixa = { padding: '12px', backgroundColor: '#0f172a', borderRadius: '6px', border: '1px solid #334155', display: 'grid', gap: '10px' }
const linhaCheck = { display: 'flex', alignItems: 'center', gap: '8px', fontSize: '14px', cursor: 'pointer' }

export default function SettingsModal({ onClose, currentUser, onUpdated }) {
  const [email, setEmail] = useState(currentUser?.email || '')
  const [receberAlertas, setReceberAlertas] = useState(!!currentUser?.receber_alertas)
  const [relatorioDiario, setRelatorioDiario] = useState(!!currentUser?.relatorio_diario)
  const [relatorioHorario, setRelatorioHorario] = useState(currentUser?.relatorio_horario || '08:00')
  const [senhaAtual, setSenhaAtual] = useState('')
  const [novaSenha, setNovaSenha] = useState('')
  const [isSaving, setIsSaving] = useState(false)
  const [enviandoRelatorio, setEnviandoRelatorio] = useState(false)

  const handleSave = async (e) => {
    e.preventDefault()
    setIsSaving(true)
    try {
      const atualizado = await api.atualizarPerfil({
        email, senha_atual: senhaAtual || null, nova_senha: novaSenha || null,
        receber_alertas: receberAlertas, relatorio_diario: relatorioDiario, relatorio_horario: relatorioHorario,
      })
      toast.success('Perfil atualizado com sucesso!')
      if (onUpdated) onUpdated(atualizado)
      onClose()
    } catch (error) {
      toast.error(error.message || 'Erro de comunicação com o servidor.')
    } finally {
      setIsSaving(false)
    }
  }

  const enviarRelatorioAgora = async () => {
    if (!email.trim()) { toast.error('Informe seu e-mail primeiro.'); return }
    setEnviandoRelatorio(true)
    try {
      // O relatório vai para o e-mail salvo: se o usuário acabou de digitar, salva antes.
      if (email.trim() !== (currentUser?.email || '')) {
        const atualizado = await api.atualizarPerfil({ email: email.trim() })
        if (onUpdated) onUpdated(atualizado)
      }
      const r = await api.enviarMeuRelatorio()
      toast.success(`Relatório enviado para ${r.para}`)
    } catch (error) { toast.error(error.message) } finally { setEnviandoRelatorio(false) }
  }

  return (
    <div style={{ position: 'absolute', inset: 0, backgroundColor: 'rgba(0,0,0,0.6)', display: 'flex', justifyContent: 'center', alignItems: 'center', zIndex: 1000 }}>
      <div style={{ backgroundColor: '#1e293b', padding: '25px', borderRadius: '12px', width: '420px', maxHeight: '92vh', overflow: 'auto', border: '1px solid #334155' }}>

        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '20px' }}>
          <h2 style={{ fontSize: '20px', display: 'flex', alignItems: 'center', gap: '8px' }}>
            <User size={20} color="#3b82f6" /> Meu Perfil
          </h2>
          <button onClick={onClose} style={{ background: 'transparent', border: 'none', color: '#94a3b8', cursor: 'pointer' }}><X size={20} /></button>
        </div>

        {currentUser && (
          <div style={{ fontSize: '13px', color: '#94a3b8', marginBottom: '15px' }}>
            {currentUser.username} · <span style={{ color: '#cbd5e1' }}>{PAPEL_ROTULO[currentUser.papel] || currentUser.papel}</span>
          </div>
        )}

        <form onSubmit={handleSave} style={{ display: 'flex', flexDirection: 'column', gap: '15px' }}>
          <div>
            <label style={{ fontSize: '14px', color: '#94a3b8', display: 'flex', alignItems: 'center', gap: '5px' }}><Mail size={14}/> E-mail (para notificações)</label>
            <input type="email" value={email} onChange={(e) => setEmail(e.target.value)} placeholder="seu@email.com" style={input} />
          </div>

          <div style={caixa}>
            <label style={linhaCheck}>
              <input type="checkbox" checked={receberAlertas} onChange={(e) => setReceberAlertas(e.target.checked)} />
              <Bell size={15} color="#f59e0b" /> Receber e-mail quando um equipamento cair ou voltar
            </label>
            <span style={{ fontSize: '12px', color: '#64748b', marginTop: '-4px' }}>
              Só equipamentos com a opção "Notificar quando cair ou voltar" ligada geram alerta. Ajuste isso em cada equipamento no mapa.
            </span>
            <div style={{ height: '1px', backgroundColor: '#334155' }} />
            <label style={linhaCheck}>
              <input type="checkbox" checked={relatorioDiario} onChange={(e) => setRelatorioDiario(e.target.checked)} />
              <FileText size={15} color="#3b82f6" /> Receber relatório diário (últimas 24 h)
            </label>
            <div style={{ display: 'flex', alignItems: 'center', gap: '10px', opacity: relatorioDiario ? 1 : 0.5 }}>
              <span style={{ fontSize: '13px', color: '#94a3b8' }}>Enviar às</span>
              <input type="time" value={relatorioHorario} disabled={!relatorioDiario} onChange={(e) => setRelatorioHorario(e.target.value)} style={{ ...input, width: '120px', marginTop: 0, padding: '6px 8px' }} />
              <button type="button" onClick={enviarRelatorioAgora} disabled={enviandoRelatorio} title="Envia agora um relatório das últimas 24 h para o seu e-mail salvo" style={{ marginLeft: 'auto', display: 'flex', alignItems: 'center', gap: '5px', padding: '6px 10px', background: '#334155', color: 'white', border: 0, borderRadius: '6px', cursor: 'pointer', fontSize: '12px' }}>
                {enviandoRelatorio ? <Loader2 size={13} className="spin" /> : <Send size={13} />} Enviar agora
              </button>
            </div>
            <span style={{ fontSize: '12px', color: '#64748b' }}>
              O envio usa o servidor de e-mail configurado pelo administrador. Telegram e webhook continuam disponíveis via docker-compose.
            </span>
          </div>

          <div style={{ height: '1px', backgroundColor: '#334155', margin: '5px 0' }}></div>

          <h3 style={{ fontSize: '16px', display: 'flex', alignItems: 'center', gap: '5px' }}><Key size={16}/> Alterar Senha</h3>
          <div>
            <label style={{ fontSize: '14px', color: '#94a3b8' }}>Senha Atual</label>
            <input type="password" value={senhaAtual} onChange={(e) => setSenhaAtual(e.target.value)} placeholder="Digite sua senha atual" style={input} />
          </div>
          <div>
            <label style={{ fontSize: '14px', color: '#94a3b8' }}>Nova Senha</label>
            <input type="password" minLength={8} value={novaSenha} onChange={(e) => setNovaSenha(e.target.value)} placeholder="Mínimo de 8 caracteres" style={input} />
          </div>

          <button type="submit" disabled={isSaving} style={{ display: 'flex', justifyContent: 'center', alignItems: 'center', gap: '5px', padding: '10px 20px', backgroundColor: isSaving ? '#475569' : '#3b82f6', color: 'white', border: 'none', borderRadius: '6px', cursor: isSaving ? 'wait' : 'pointer', marginTop: '5px' }}>
            <Save size={18} /> {isSaving ? 'Salvando...' : 'Salvar Alterações'}
          </button>
        </form>
      </div>
    </div>
  )
}
