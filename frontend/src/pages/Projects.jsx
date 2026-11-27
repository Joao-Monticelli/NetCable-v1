import { useState, useEffect, useRef } from 'react'
import { useNavigate } from 'react-router-dom'
import { FolderPlus, Folder, LogOut, Network, Loader2, Trash2, Settings, UserCog, CheckCircle2, XCircle, MinusCircle, Share2, Users, Mail, Eye, Boxes, Upload, Download, Archive, BellRing, ScrollText, Building2 } from 'lucide-react'
import toast from 'react-hot-toast'
import { api } from '../services/api'
import SettingsModal from '../components/Modals/SettingsModal'
import UsersModal from '../components/Modals/UsersModal'
import EmailConfigModal from '../components/Modals/EmailConfigModal'
import ModelosModal from '../components/Modals/ModelosModal'
import BackupModal from '../components/Modals/BackupModal'
import CanaisModal from '../components/Modals/CanaisModal'
import AuditoriaModal from '../components/Modals/AuditoriaModal'
import LdapModal from '../components/Modals/LdapModal'
import { t, useI18n, SeletorIdioma, getIdioma } from '../i18n'

const itemMenu = { display: 'flex', alignItems: 'center', gap: '8px', width: '100%', padding: '10px', backgroundColor: 'transparent', color: 'white', border: 'none', textAlign: 'left', cursor: 'pointer', borderRadius: '4px' }

export default function Projects() {
  useI18n()
  const navigate = useNavigate()
  const [projetos, setProjetos] = useState([])
  const [isLoading, setIsLoading] = useState(true)

  const [showConfigMenu, setShowConfigMenu] = useState(false)
  const [modal, setModal] = useState(null) // 'perfil' | 'usuarios' | 'email'
  const [currentUser, setCurrentUser] = useState(null)

  const isAdmin = currentUser?.papel === 'admin'
  const podeEditar = currentUser && currentUser.papel !== 'visualizador'

  const fetchProjetos = async () => {
    try {
      const data = await api.listarProjetos()
      setProjetos(Array.isArray(data) ? data : [])
    } catch (error) {
      if (error.message === 'Não autorizado') {
        api.logout(); navigate('/');
      }
    } finally {
      setIsLoading(false)
    }
  }

  useEffect(() => {
    fetchProjetos()
    // Mantém os contadores online/offline atualizados enquanto a tela estiver aberta.
    const interval = setInterval(fetchProjetos, 15000)
    api.me().then(me => {
      setCurrentUser(me)
      // O idioma escolhido neste navegador também vale para os e-mails do usuário.
      if (me.idioma !== getIdioma()) api.atualizarPerfil({ idioma: getIdioma() }).catch(() => {})
    }).catch(() => { api.logout(); navigate('/') })
    return () => clearInterval(interval)
  }, [])

  const handleDeleteProject = async (e, id, nome) => {
    e.stopPropagation()
    if (!window.confirm(t('Excluir o projeto "{nome}"? Ele será removido para toda a equipe.', { nome }))) return
    try {
      const ok = await api.deletarProjeto(id)
      if (!ok) throw new Error()
      setProjetos(projetos.filter(p => p.id !== id))
      toast.success(t('Projeto excluído com sucesso.'))
    } catch (error) { toast.error(t('Erro ao excluir.')) }
  }

  const handleLogout = () => {
    api.logout();
    navigate('/');
  }

  const abrir = (qual) => { setShowConfigMenu(false); setModal(qual) }

  const arquivoRef = useRef(null)
  const [importando, setImportando] = useState(false)
  const importar = async (e) => {
    const arquivo = e.target.files[0]
    e.target.value = null
    if (!arquivo) return
    setImportando(true)
    try {
      const importados = await api.importarArquivo(arquivo)
      toast.success(t('{n} mapa(s) importado(s) como projeto novo.', { n: importados.length }))
      fetchProjetos()
    } catch (err) { toast.error(err.message, { duration: 7000 }) } finally { setImportando(false) }
  }
  const exportar = (e, proj) => {
    e.stopPropagation()
    api.exportarProjeto(proj.id, proj.nome).catch(err => toast.error(err.message))
  }

  return (
    <div style={{ minHeight: '100vh', backgroundColor: '#0f172a', padding: '40px' }}>
      <header style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '40px', borderBottom: '1px solid #334155', paddingBottom: '20px' }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
          <Network size={32} color="#3b82f6" />
          <h1 style={{ fontSize: '24px' }}>{t('Mapas da equipe')}</h1>
        </div>

        <div style={{ display: 'flex', alignItems: 'center', gap: '12px' }}>
          {podeEditar && <>
            <input type="file" ref={arquivoRef} onChange={importar} accept=".json,.zip" style={{ display: 'none' }} />
            <button onClick={() => arquivoRef.current.click()} disabled={importando} title={t('Importar mapa ou backup (.json / .zip)')} style={{ display: 'flex', alignItems: 'center', gap: '6px', padding: '8px 12px', backgroundColor: '#334155', color: 'white', border: 'none', borderRadius: '6px', cursor: 'pointer', fontSize: '13px' }}>
              {importando ? <Loader2 size={16} className="spin" /> : <Upload size={16} />} {t('Importar')}
            </button>
          </>}
          <SeletorIdioma compacto onChange={(i) => api.atualizarPerfil({ idioma: i }).catch(() => {})} />
          {currentUser && (
            <span style={{ fontSize: '13px', color: '#94a3b8', display: 'flex', alignItems: 'center', gap: '6px' }}>
              {currentUser.papel === 'visualizador' && <Eye size={14} />} {currentUser.username}
            </span>
          )}
          <div style={{ position: 'relative' }}>
            <button
              onClick={() => setShowConfigMenu(!showConfigMenu)}
              title={t('Configurações')}
              style={{ display: 'flex', alignItems: 'center', padding: '8px 12px', backgroundColor: showConfigMenu ? '#475569' : '#334155', color: 'white', border: 'none', borderRadius: '6px', cursor: 'pointer' }}
            >
              <Settings size={20} />
            </button>

            {showConfigMenu && (
              <div style={{ position: 'absolute', top: '110%', right: 0, backgroundColor: '#1e293b', border: '1px solid #334155', borderRadius: '6px', padding: '5px', minWidth: '210px', boxShadow: '0 4px 6px rgba(0,0,0,0.3)', zIndex: 100 }}>
                <button onClick={() => abrir('perfil')} style={itemMenu}><UserCog size={16} color="#94a3b8"/> {t('Meu perfil e notificações')}</button>
                <button onClick={() => abrir('modelos')} style={itemMenu}><Boxes size={16} color="#a78bfa"/> {t('Modelos de equipamento')}</button>
                {isAdmin && <>
                  <button onClick={() => abrir('usuarios')} style={itemMenu}><Users size={16} color="#3b82f6"/> {t('Usuários')}</button>
                  <button onClick={() => abrir('ldap')} style={itemMenu}><Building2 size={16} color="#60a5fa"/> {t('Diretório (LDAP/AD)')}</button>
                  <button onClick={() => abrir('email')} style={itemMenu}><Mail size={16} color="#f59e0b"/> {t('E-mail (SMTP)')}</button>
                  <button onClick={() => abrir('canais')} style={itemMenu}><BellRing size={16} color="#f59e0b"/> {t('Canais de alerta')}</button>
                  <button onClick={() => abrir('backup')} style={itemMenu}><Archive size={16} color="#10b981"/> {t('Backup')}</button>
                  <button onClick={() => abrir('auditoria')} style={itemMenu}><ScrollText size={16} color="#38bdf8"/> {t('Log de auditoria')}</button>
                </>}
                <div style={{ height: '1px', backgroundColor: '#334155', margin: '5px 0' }}></div>
                <button onClick={handleLogout} style={{ ...itemMenu, color: '#ef4444' }}><LogOut size={16} /> {t('Sair')}</button>
              </div>
            )}
          </div>
        </div>
      </header>

      {isLoading ? (
        <div style={{ display: 'flex', justifyContent: 'center', alignItems: 'center', height: '200px', color: '#94a3b8' }}><Loader2 size={32} className="spin" style={{ marginRight: '10px' }} /> {t('Carregando...')}</div>
      ) : (
        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(250px, 1fr))', gap: '20px' }}>
          {podeEditar && (
            <button onClick={() => navigate('/editor/novo')} style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center', height: '160px', backgroundColor: '#1e293b', border: '2px dashed #475569', borderRadius: '12px', color: '#94a3b8', cursor: 'pointer' }}>
              <FolderPlus size={40} style={{ marginBottom: '10px' }} /><span>{t('Criar Novo Projeto')}</span>
            </button>
          )}
          {!podeEditar && projetos.length === 0 && <div style={{ color: '#94a3b8' }}>{t('Nenhum mapa disponível ainda.')}</div>}
          {projetos.map(proj => (
            <div key={proj.id} onClick={() => navigate(`/editor/${proj.id}`)} style={{ position: 'relative', display: 'flex', flexDirection: 'column', height: '160px', backgroundColor: '#1e293b', border: `1px solid ${proj.offline ? '#7f1d1d' : '#334155'}`, borderRadius: '12px', padding: '20px', cursor: 'pointer', justifyContent: 'space-between' }}>
              <div style={{ display: 'flex', alignItems: 'flex-start', justifyContent: 'space-between' }}>
                <div style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
                  <Folder size={24} color="#3b82f6" />
                  <div>
                    <h3 style={{ fontSize: '18px', wordBreak: 'break-word', paddingRight: '10px' }}>{proj.nome}</h3>
                    {proj.criado_por && <span style={{ fontSize: '11px', color: '#64748b' }}>{t('criado por {nome}', { nome: proj.criado_por })}</span>}
                  </div>
                </div>
                <div style={{ display: 'flex', alignItems: 'center' }}>
                <button onClick={(e) => exportar(e, proj)} title={t('Exportar mapa (.json)')} aria-label={t('Exportar mapa (.json)')} style={{ background: 'transparent', border: 'none', color: '#94a3b8', cursor: 'pointer', padding: '5px' }}><Download size={18} /></button>
                {podeEditar && <button onClick={(e) => handleDeleteProject(e, proj.id, proj.nome)} title={t('Excluir projeto')} style={{ background: 'transparent', border: 'none', color: '#ef4444', cursor: 'pointer', padding: '5px' }}><Trash2 size={18} /></button>}
                </div>
              </div>
              <div style={{ display: 'flex', alignItems: 'center', gap: '12px', fontSize: '13px' }}>
                <span title={t('Online')} style={{ display: 'flex', alignItems: 'center', gap: '4px', color: '#10b981' }}><CheckCircle2 size={15} /> {proj.online ?? 0}</span>
                <span title={t('Offline')} style={{ display: 'flex', alignItems: 'center', gap: '4px', color: proj.offline ? '#ef4444' : '#64748b', fontWeight: proj.offline ? 'bold' : 'normal' }}><XCircle size={15} /> {proj.offline ?? 0}</span>
                <span title={t('Somente visual')} style={{ display: 'flex', alignItems: 'center', gap: '4px', color: '#64748b' }}><MinusCircle size={15} /> {proj.visual ?? 0}</span>
                {proj.compartilhado && <span title={t('Link público ativo')} style={{ marginLeft: 'auto', display: 'flex', alignItems: 'center', gap: '4px', color: '#3b82f6', fontSize: '12px' }}><Share2 size={14} /> {t('público')}</span>}
              </div>
            </div>
          ))}
        </div>
      )}

      {modal === 'perfil' && <SettingsModal onClose={() => setModal(null)} currentUser={currentUser} onUpdated={setCurrentUser} />}
      {modal === 'usuarios' && <UsersModal onClose={() => setModal(null)} currentUser={currentUser} />}
      {modal === 'modelos' && <ModelosModal podeEditar={podeEditar} onClose={() => setModal(null)} />}
      {modal === 'canais' && <CanaisModal onClose={() => setModal(null)} />}
      {modal === 'backup' && <BackupModal onClose={() => setModal(null)} />}
      {modal === 'auditoria' && <AuditoriaModal onClose={() => setModal(null)} />}
      {modal === 'ldap' && <LdapModal onClose={() => setModal(null)} />}
      {modal === 'email' && <EmailConfigModal onClose={() => setModal(null)} currentUser={currentUser} />}
    </div>
  )
}
