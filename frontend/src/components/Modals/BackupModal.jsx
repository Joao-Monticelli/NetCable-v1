import { useEffect, useState } from 'react'
import { X, Archive, Save, Download, Loader2, CheckCircle2, AlertTriangle, PlayCircle } from 'lucide-react'
import toast from 'react-hot-toast'
import { api } from '../../services/api'
import { t, useI18n, localeAtual } from '../../i18n'

const rotulo = { fontSize: '13px', color: '#94a3b8' }
const campo = { width: '100%', padding: '9px', marginTop: '4px', borderRadius: '6px', border: '1px solid #334155', backgroundColor: '#0f172a', color: 'white' }
const botao = { display: 'flex', alignItems: 'center', gap: '6px', padding: '9px 14px', border: 0, borderRadius: '6px', cursor: 'pointer', color: 'white' }

const tamanho = (bytes) => bytes > 1048576 ? `${(bytes / 1048576).toFixed(1)} MB` : `${Math.max(1, Math.round(bytes / 1024))} KB`
const quando = (iso) => iso ? new Date(iso).toLocaleString(localeAtual()) : '—'

export default function BackupModal({ onClose }) {
  useI18n()
  const [cfg, setCfg] = useState(null)
  const [salvando, setSalvando] = useState(false)
  const [rodando, setRodando] = useState(false)

  useEffect(() => { api.obterBackup().then(setCfg).catch(e => toast.error(e.message)) }, [])

  const set = (k, conv = (v) => v) => (e) => setCfg({ ...cfg, [k]: conv(e.target.type === 'checkbox' ? e.target.checked : e.target.value) })

  const salvar = async (e) => {
    e?.preventDefault()
    setSalvando(true)
    try {
      setCfg(await api.salvarBackup({ ativo: cfg.ativo, diretorio: cfg.diretorio, horario: cfg.horario, manter: Number(cfg.manter) }))
      toast.success(t('Configuração de backup salva.'))
      return true
    } catch (err) { toast.error(err.message, { duration: 8000 }); return false } finally { setSalvando(false) }
  }

  const agora = async () => {
    setRodando(true)
    try {
      const r = await api.backupAgora()
      setCfg(r)
      toast.success(t('Backup criado: {nome}', { nome: r.arquivo }))
    } catch (err) { toast.error(err.message, { duration: 8000 }) } finally { setRodando(false) }
  }

  const baixar = (nome) => api.baixarBackup(nome).catch(err => toast.error(err.message))

  return (
    <div style={{ position: 'fixed', inset: 0, backgroundColor: 'rgba(0,0,0,0.65)', display: 'flex', justifyContent: 'center', alignItems: 'center', zIndex: 1100 }}>
      <div role="dialog" aria-label={t('Backup')} style={{ backgroundColor: '#1e293b', padding: '25px', borderRadius: '12px', width: 'min(560px, 94vw)', maxHeight: '92vh', overflow: 'auto', border: '1px solid #334155', color: 'white' }}>
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '6px' }}>
          <h2 style={{ display: 'flex', alignItems: 'center', gap: '8px', fontSize: '20px' }}><Archive size={20} color="#10b981" /> {t('Backup')}</h2>
          <button onClick={onClose} aria-label={t('Fechar')} style={{ background: 'transparent', border: 0, color: '#94a3b8', cursor: 'pointer' }}><X size={20} /></button>
        </div>
        <p style={{ color: '#94a3b8', fontSize: '13px', marginBottom: '14px', lineHeight: 1.45 }}>
          {t('Um arquivo .zip por dia com todos os mapas, o catálogo de modelos e o banco completo (usuários e histórico). Para recuperar mapas, importe o .zip na tela de projetos.')}
        </p>

        {!cfg ? <div style={{ color: '#94a3b8' }}><Loader2 size={16} className="spin" /> {t('Carregando...')}</div> : (
          <form onSubmit={salvar} style={{ display: 'grid', gap: '12px' }}>
            <label style={{ display: 'flex', alignItems: 'center', gap: '8px', fontSize: '14px', cursor: 'pointer' }}>
              <input type="checkbox" checked={cfg.ativo} onChange={set('ativo')} /> {t('Backup automático diário')}
            </label>
            <label style={rotulo}>{t('Pasta de destino')}
              <input value={cfg.diretorio} onChange={set('diretorio')} placeholder={cfg.diretorio_padrao} style={campo} />
              <span style={{ display: 'block', fontSize: '11px', color: '#64748b', marginTop: '4px', lineHeight: 1.4 }}>
                {t('No Docker, use uma pasta montada como volume (ex.: /app/data/backups ou um volume extra apontando para o seu NAS). Padrão: {pasta}', { pasta: cfg.diretorio_padrao })}
              </span>
            </label>
            <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '10px' }}>
              <label style={rotulo}>{t('Horário')}<input type="time" required value={cfg.horario} onChange={set('horario')} style={campo} /></label>
              <label style={rotulo}>{t('Manter os últimos')}<input type="number" min="1" max="365" required value={cfg.manter} onChange={set('manter')} style={campo} /></label>
            </div>

            <div style={{ fontSize: '12px', color: '#94a3b8', display: 'grid', gap: '4px' }}>
              <span style={{ display: 'flex', alignItems: 'center', gap: '6px' }}><CheckCircle2 size={14} color="#10b981" /> {t('Último backup: {quando}', { quando: quando(cfg.ultimo) })}</span>
              {cfg.ultimo_erro && <span style={{ display: 'flex', alignItems: 'center', gap: '6px', color: '#f59e0b' }}><AlertTriangle size={14} /> {t('Última falha: {erro}', { erro: cfg.ultimo_erro })}</span>}
            </div>

            <div style={{ display: 'flex', gap: '8px', justifyContent: 'flex-end' }}>
              <button type="button" onClick={agora} disabled={rodando || salvando} style={{ ...botao, background: '#334155' }}>{rodando ? <Loader2 size={15} className="spin" /> : <PlayCircle size={15} />} {t('Fazer backup agora')}</button>
              <button type="submit" disabled={salvando} style={{ ...botao, background: '#3b82f6' }}>{salvando ? <Loader2 size={15} className="spin" /> : <Save size={15} />} {t('Salvar')}</button>
            </div>

            <div style={{ borderTop: '1px solid #334155', paddingTop: '12px' }}>
              <div style={{ ...rotulo, marginBottom: '8px' }}>{t('Arquivos na pasta ({n})', { n: cfg.arquivos.length })}</div>
              {cfg.arquivos.length === 0 && <div style={{ fontSize: '13px', color: '#64748b' }}>{t('Nenhum backup ainda.')}</div>}
              <div style={{ display: 'grid', gap: '6px' }}>
                {cfg.arquivos.map(a => (
                  <div key={a.nome} style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', gap: '8px', padding: '7px 10px', background: '#0f172a', borderRadius: '6px', fontSize: '13px' }}>
                    <span style={{ fontFamily: 'monospace', overflow: 'hidden', textOverflow: 'ellipsis' }}>{a.nome}</span>
                    <span style={{ display: 'flex', alignItems: 'center', gap: '10px', color: '#94a3b8', whiteSpace: 'nowrap' }}>
                      {tamanho(a.tamanho)}
                      <button type="button" onClick={() => baixar(a.nome)} title={t('Baixar')} aria-label={t('Baixar')} style={{ background: 'transparent', border: 0, color: '#3b82f6', cursor: 'pointer', padding: 0 }}><Download size={16} /></button>
                    </span>
                  </div>
                ))}
              </div>
            </div>
          </form>
        )}
      </div>
    </div>
  )
}
