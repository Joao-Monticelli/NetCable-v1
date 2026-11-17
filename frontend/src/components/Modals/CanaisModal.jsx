import { useEffect, useState } from 'react'
import { X, BellRing, Save, Send, Loader2, CheckCircle2, Circle, Trash2 } from 'lucide-react'
import toast from 'react-hot-toast'
import { api } from '../../services/api'
import { t, useI18n } from '../../i18n'

const rotulo = { fontSize: '13px', color: '#94a3b8' }
const campo = { width: '100%', padding: '9px', marginTop: '4px', borderRadius: '6px', border: '1px solid #334155', backgroundColor: '#0f172a', color: 'white' }
const botao = { display: 'flex', alignItems: 'center', gap: '6px', padding: '7px 12px', border: 0, borderRadius: '6px', cursor: 'pointer', color: 'white', fontSize: '13px' }
const cartao = { padding: '12px', backgroundColor: '#0f172a', borderRadius: '8px', border: '1px solid #334155', display: 'grid', gap: '8px' }

// Campo secreto: vazio mantém o valor salvo; a lixeira apaga.
function Segredo({ rotuloCampo, nome, cfg, valores, setValores, placeholder }) {
  const definido = cfg[`${nome}_definido`] && valores[nome] !== ''
  return (
    <label style={rotulo}>{rotuloCampo}
      <div style={{ display: 'flex', gap: '6px' }}>
        <input type="password" autoComplete="new-password" value={valores[nome] || ''} onChange={e => setValores({ ...valores, [nome]: e.target.value })}
          placeholder={definido ? `•••••• (${t('manter atual')})` : (cfg[`${nome}_ambiente`] ? t('definido por variável de ambiente') : placeholder)} style={campo} />
        {definido && <button type="button" title={t('Remover')} aria-label={t('Remover')} onClick={() => setValores({ ...valores, [nome]: '' })} style={{ ...botao, background: '#334155', marginTop: '4px' }}><Trash2 size={14} /></button>}
      </div>
    </label>
  )
}

function Cabecalho({ titulo, ativo, canal, testando, onTestar }) {
  return (
    <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
      <strong style={{ display: 'flex', alignItems: 'center', gap: '6px', fontSize: '14px' }}>
        {ativo ? <CheckCircle2 size={15} color="#10b981" /> : <Circle size={15} color="#475569" />} {titulo}
      </strong>
      <button type="button" disabled={!ativo || testando === canal} onClick={() => onTestar(canal)} title={ativo ? t('Enviar mensagem de teste') : t('Salve a configuração primeiro')}
        style={{ ...botao, background: ativo ? '#334155' : '#1e293b', color: ativo ? 'white' : '#475569', cursor: ativo ? 'pointer' : 'not-allowed' }}>
        {testando === canal ? <Loader2 size={13} className="spin" /> : <Send size={13} />} {t('Testar')}
      </button>
    </div>
  )
}

// Limites para alertas de temperatura e CPU (equipamentos em SNMPv3).
function Limites() {
  const [lim, setLim] = useState(null)
  const [salvando, setSalvando] = useState(false)
  useEffect(() => { api.obterLimites().then(setLim).catch(() => {}) }, [])
  if (!lim) return null
  const salvar = async () => {
    setSalvando(true)
    try { setLim(await api.salvarLimites({ temperatura: Number(lim.temperatura), cpu: Number(lim.cpu) })); toast.success(t('Limites salvos.')) }
    catch (err) { toast.error(err.message) } finally { setSalvando(false) }
  }
  return (
    <div style={cartao}>
      <strong style={{ fontSize: '14px' }}>{t('Limites de temperatura e CPU (SNMP)')}</strong>
      <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr auto', gap: '8px', alignItems: 'end' }}>
        <label style={rotulo}>{t('Temperatura máx. (°C)')}<input type="number" min="0" max="150" aria-label={t('Temperatura máx. (°C)')} value={lim.temperatura} onChange={e => setLim({ ...lim, temperatura: e.target.value })} style={campo} /></label>
        <label style={rotulo}>{t('CPU máx. (%)')}<input type="number" min="0" max="100" aria-label={t('CPU máx. (%)')} value={lim.cpu} onChange={e => setLim({ ...lim, cpu: e.target.value })} style={campo} /></label>
        <button type="button" onClick={salvar} disabled={salvando} style={{ ...botao, background: '#334155', height: 38 }}>{salvando ? <Loader2 size={13} className="spin" /> : <Save size={13} />} {t('Salvar limites')}</button>
      </div>
      <span style={{ fontSize: '11px', color: '#64748b' }}>{t('Alerta após 3 leituras seguidas acima do limite; avisa de novo quando normalizar. Use 0 para desativar.')}</span>
    </div>
  )
}

export default function CanaisModal({ onClose }) {
  useI18n()
  const [cfg, setCfg] = useState(null)
  const [valores, setValores] = useState({})
  const [salvando, setSalvando] = useState(false)
  const [testando, setTestando] = useState(null)

  const carregar = (c) => { setCfg(c); setValores({ telegram_chat: c.telegram_chat, ntfy_url: c.ntfy_url, idioma: c.idioma }) }
  useEffect(() => { api.obterCanais().then(carregar).catch(e => toast.error(e.message)) }, [])

  const salvar = async (e) => {
    e?.preventDefault()
    setSalvando(true)
    try {
      // Segredos não preenchidos vão como null (mantém); '' apaga.
      const dados = { ...valores }
      for (const k of ['telegram_token', 'discord_url', 'ntfy_token', 'webhook_url']) if (dados[k] === undefined) dados[k] = null
      carregar(await api.salvarCanais(dados))
      toast.success(t('Canais de alerta salvos.'))
    } catch (err) { toast.error(err.message, { duration: 7000 }) } finally { setSalvando(false) }
  }

  const testar = async (canal) => {
    setTestando(canal)
    try { await api.testarCanal(canal); toast.success(t('Mensagem de teste enviada.')) }
    catch (err) { toast.error(err.message, { duration: 8000 }) } finally { setTestando(null) }
  }

  const p = { cfg, valores, setValores }
  return (
    <div style={{ position: 'fixed', inset: 0, backgroundColor: 'rgba(0,0,0,0.65)', display: 'flex', justifyContent: 'center', alignItems: 'center', zIndex: 1100 }}>
      <div role="dialog" aria-label={t('Canais de alerta')} style={{ backgroundColor: '#1e293b', padding: '25px', borderRadius: '12px', width: 'min(560px, 94vw)', maxHeight: '92vh', overflow: 'auto', border: '1px solid #334155', color: 'white' }}>
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '6px' }}>
          <h2 style={{ display: 'flex', alignItems: 'center', gap: '8px', fontSize: '20px' }}><BellRing size={20} color="#f59e0b" /> {t('Canais de alerta')}</h2>
          <button onClick={onClose} aria-label={t('Fechar')} style={{ background: 'transparent', border: 0, color: '#94a3b8', cursor: 'pointer' }}><X size={20} /></button>
        </div>
        <p style={{ color: '#94a3b8', fontSize: '13px', marginBottom: '14px', lineHeight: 1.45 }}>
          {t('Além do e-mail, o NetCable avisa quedas e recuperações nestes canais. Tokens e URLs ficam cifrados no banco.')}
        </p>
        {!cfg ? <div style={{ color: '#94a3b8' }}><Loader2 size={16} className="spin" /> {t('Carregando...')}</div> : (
          <form onSubmit={salvar} style={{ display: 'grid', gap: '12px' }}>
            <div style={cartao}>
              <Cabecalho titulo="Discord" ativo={cfg.ativos.discord} canal="discord" testando={testando} onTestar={testar} />
              <Segredo rotuloCampo={t('URL do webhook do canal')} nome="discord_url" placeholder="https://discord.com/api/webhooks/..." {...p} />
              <span style={{ fontSize: '11px', color: '#64748b' }}>{t('No Discord: Configurações do canal → Integrações → Webhooks → Novo webhook → Copiar URL.')}</span>
            </div>
            <div style={cartao}>
              <Cabecalho titulo="ntfy" ativo={cfg.ativos.ntfy} canal="ntfy" testando={testando} onTestar={testar} />
              <label style={rotulo}>{t('URL do tópico')}<input value={valores.ntfy_url || ''} onChange={e => setValores({ ...valores, ntfy_url: e.target.value })} placeholder={cfg.ntfy_url_ambiente ? t('definido por variável de ambiente') : 'https://ntfy.sh/meu-topico-secreto'} style={campo} /></label>
              <Segredo rotuloCampo={t('Token de acesso (opcional)')} nome="ntfy_token" placeholder="tk_..." {...p} />
              <span style={{ fontSize: '11px', color: '#64748b' }}>{t('Notificação no celular pelo app ntfy (ntfy.sh ou o seu servidor). Quedas chegam com prioridade alta.')}</span>
            </div>
            <div style={cartao}>
              <Cabecalho titulo="Telegram" ativo={cfg.ativos.telegram} canal="telegram" testando={testando} onTestar={testar} />
              <div style={{ display: 'grid', gridTemplateColumns: '3fr 2fr', gap: '8px' }}>
                <Segredo rotuloCampo={t('Token do bot')} nome="telegram_token" placeholder="123456:ABC..." {...p} />
                <label style={rotulo}>{t('ID do chat')}<input value={valores.telegram_chat || ''} onChange={e => setValores({ ...valores, telegram_chat: e.target.value })} placeholder={cfg.telegram_chat_ambiente ? t('definido por variável de ambiente') : '-1001234567890'} style={campo} /></label>
              </div>
            </div>
            <div style={cartao}>
              <Cabecalho titulo={t('Webhook (JSON)')} ativo={cfg.ativos.webhook} canal="webhook" testando={testando} onTestar={testar} />
              <Segredo rotuloCampo={t('URL que recebe um POST por evento')} nome="webhook_url" placeholder="https://..." {...p} />
            </div>
            <Limites />
            <label style={rotulo}>{t('Idioma das mensagens destes canais')}
              <select value={valores.idioma || 'en'} onChange={e => setValores({ ...valores, idioma: e.target.value })} style={campo}>
                <option value="en">English</option>
                <option value="pt">Português</option>
              </select>
            </label>
            <div style={{ display: 'flex', justifyContent: 'flex-end' }}>
              <button type="submit" disabled={salvando} style={{ ...botao, padding: '9px 14px', background: '#3b82f6' }}>{salvando ? <Loader2 size={15} className="spin" /> : <Save size={15} />} {t('Salvar')}</button>
            </div>
          </form>
        )}
      </div>
    </div>
  )
}
