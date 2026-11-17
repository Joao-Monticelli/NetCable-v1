import { useEffect, useState } from 'react'
import { X, Mail, Save, Send, Loader2, CheckCircle2, XCircle } from 'lucide-react'
import toast from 'react-hot-toast'
import { api } from '../../services/api'

const PRESETS = [
  { nome: 'Gmail', host: 'smtp.gmail.com', porta: 587, seguranca: 'starttls', dica: 'Use uma "senha de app" (Conta Google → Segurança → Senhas de app).' },
  { nome: 'Outlook', host: 'smtp-mail.outlook.com', porta: 587, seguranca: 'starttls' },
  { nome: 'Office 365', host: 'smtp.office365.com', porta: 587, seguranca: 'starttls' },
]
const FUSOS = ['America/Sao_Paulo', 'America/Manaus', 'America/Fortaleza', 'America/Cuiaba', 'America/Rio_Branco', 'America/Noronha', 'Europe/Lisbon', 'UTC']

const rotulo = { fontSize: '13px', color: '#94a3b8' }
const campo = { width: '100%', padding: '9px', marginTop: '4px', borderRadius: '6px', border: '1px solid #334155', backgroundColor: '#0f172a', color: 'white' }
const botao = { display: 'flex', alignItems: 'center', gap: '6px', padding: '9px 14px', border: 0, borderRadius: '6px', cursor: 'pointer', color: 'white' }

export default function EmailConfigModal({ onClose, currentUser }) {
  const [cfg, setCfg] = useState(null)
  const [senha, setSenha] = useState('')
  const [salvando, setSalvando] = useState(false)
  const [testando, setTestando] = useState(false)
  const [destino, setDestino] = useState(currentUser?.email || '')
  const [dica, setDica] = useState('')

  useEffect(() => { api.obterConfigEmail().then(setCfg).catch(e => toast.error(e.message)) }, [])

  const set = (campoNome) => (e) => setCfg({ ...cfg, [campoNome]: campoNome === 'porta' ? Number(e.target.value) : e.target.value })

  const salvar = async (e) => {
    e?.preventDefault()
    setSalvando(true)
    try {
      const salvo = await api.salvarConfigEmail({ ...cfg, senha: senha || null })
      setCfg(salvo); setSenha('')
      toast.success('Configuração de e-mail salva.')
      return true
    } catch (err) { toast.error(err.message); return false } finally { setSalvando(false) }
  }

  const testar = async () => {
    if (!(await salvar())) return
    setTestando(true)
    try {
      const r = await api.testarEmail(destino || null)
      toast.success(`E-mail de teste enviado para ${r.para}`)
    } catch (err) { toast.error(err.message, { duration: 8000 }) } finally { setTestando(false) }
  }

  return (
    <div style={{ position: 'fixed', inset: 0, backgroundColor: 'rgba(0,0,0,0.65)', display: 'flex', justifyContent: 'center', alignItems: 'center', zIndex: 1100 }}>
      <div style={{ backgroundColor: '#1e293b', padding: '25px', borderRadius: '12px', width: 'min(520px, 94vw)', maxHeight: '92vh', overflow: 'auto', border: '1px solid #334155', color: 'white' }}>
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '6px' }}>
          <h2 style={{ display: 'flex', alignItems: 'center', gap: '8px', fontSize: '20px' }}><Mail size={20} color="#3b82f6" /> E-mail e notificações</h2>
          <button onClick={onClose} style={{ background: 'transparent', border: 0, color: '#94a3b8', cursor: 'pointer' }}><X size={20} /></button>
        </div>
        <p style={{ color: '#94a3b8', fontSize: '13px', marginBottom: '14px' }}>
          Servidor usado para enviar os alertas de queda e os relatórios diários. Cada usuário escolhe no próprio perfil o que quer receber.
        </p>

        {!cfg ? <div style={{ color: '#94a3b8' }}><Loader2 size={16} className="spin" /> Carregando...</div> : (
          <form onSubmit={salvar} style={{ display: 'grid', gap: '12px' }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: '6px', fontSize: '13px', color: cfg.configurado ? '#10b981' : '#f59e0b' }}>
              {cfg.configurado ? <CheckCircle2 size={15} /> : <XCircle size={15} />} {cfg.configurado ? 'Servidor configurado' : 'Servidor ainda não configurado'}
            </div>

            <div style={{ display: 'flex', gap: '6px', alignItems: 'center', flexWrap: 'wrap' }}>
              <span style={rotulo}>Preencher com:</span>
              {PRESETS.map(p => (
                <button type="button" key={p.nome} onClick={() => { setCfg({ ...cfg, host: p.host, porta: p.porta, seguranca: p.seguranca }); setDica(p.dica || '') }} style={{ padding: '4px 10px', fontSize: '12px', borderRadius: '12px', border: '1px solid #334155', background: 'transparent', color: 'white', cursor: 'pointer' }}>{p.nome}</button>
              ))}
            </div>
            {dica && <div style={{ fontSize: '12px', color: '#f59e0b' }}>💡 {dica}</div>}

            <div style={{ display: 'grid', gridTemplateColumns: '2fr 1fr', gap: '10px' }}>
              <label style={rotulo}>Servidor SMTP<input value={cfg.host} onChange={set('host')} placeholder="smtp.seudominio.com" style={campo} /></label>
              <label style={rotulo}>Porta<input type="number" min="1" max="65535" value={cfg.porta} onChange={set('porta')} style={campo} /></label>
            </div>
            <label style={rotulo}>Segurança
              <select value={cfg.seguranca} onChange={set('seguranca')} style={campo}>
                <option value="starttls">STARTTLS (normalmente porta 587)</option>
                <option value="ssl">SSL/TLS (normalmente porta 465)</option>
                <option value="nenhuma">Nenhuma (porta 25, só em rede interna)</option>
              </select>
            </label>
            <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '10px' }}>
              <label style={rotulo}>Usuário<input value={cfg.usuario} onChange={set('usuario')} placeholder="usuario@dominio.com" autoComplete="off" style={campo} /></label>
              <label style={rotulo}>Senha<input type="password" value={senha} onChange={(e) => setSenha(e.target.value)} placeholder={cfg.senha_definida ? '•••••• (manter atual)' : 'Senha do e-mail'} autoComplete="new-password" style={campo} /></label>
            </div>
            <label style={rotulo}>Remetente (De:)<input value={cfg.remetente} onChange={set('remetente')} placeholder="NetCable <noc@seudominio.com>" style={campo} /></label>
            <label style={rotulo}>Fuso horário dos relatórios
              <select value={cfg.fuso} onChange={set('fuso')} style={campo}>
                {[...new Set([cfg.fuso, ...FUSOS])].map(f => <option key={f} value={f}>{f}</option>)}
              </select>
            </label>

            <div style={{ display: 'flex', gap: '8px', alignItems: 'flex-end', marginTop: '6px', paddingTop: '12px', borderTop: '1px solid #334155' }}>
              <label style={{ ...rotulo, flex: 1 }}>Enviar teste para<input type="email" value={destino} onChange={(e) => setDestino(e.target.value)} placeholder="seu@email.com" style={campo} /></label>
              <button type="button" onClick={testar} disabled={testando || salvando} style={{ ...botao, background: '#334155' }}>{testando ? <Loader2 size={15} className="spin" /> : <Send size={15} />} Salvar e testar</button>
              <button type="submit" disabled={salvando} style={{ ...botao, background: '#3b82f6' }}>{salvando ? <Loader2 size={15} className="spin" /> : <Save size={15} />} Salvar</button>
            </div>
          </form>
        )}
      </div>
    </div>
  )
}
