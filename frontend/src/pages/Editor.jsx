import { useState, useCallback, useRef, useEffect } from 'react'
import { useNavigate, useParams } from 'react-router-dom'
import { ArrowLeft, Save, Plus, Network, Settings, CheckCircle2, XCircle, MinusCircle, Loader2, Download, Upload, Share2, LogOut, UserCog, Bell, AlertTriangle, Activity, Eye, Pencil, RefreshCw, Link2Off, Boxes, Cable, Unplug } from 'lucide-react'
import toast from 'react-hot-toast'
import NetworkMap from '../components/NetworkMap'
import AddEquipmentModal from '../components/Modals/AddEquipmentModal'
import SettingsModal from '../components/Modals/SettingsModal'
import DiagnosticsModal from '../components/Modals/DiagnosticsModal'
import HistoryModal from '../components/Modals/HistoryModal'
import ModelosModal from '../components/Modals/ModelosModal'
import BuscaEquipamento from '../components/BuscaEquipamento'
import ManutencaoProjeto from '../components/ManutencaoProjeto'
import { usePreferenciaCabos, useResumoMapa } from '../components/visaoMapa'
import { api } from '../services/api'
import { equipamentosParaNodes, conexoesParaEdges, nodeParaEquipamento } from '../utils/mapa'
import { t, useI18n, SeletorIdioma, getIdioma } from '../i18n'

const tituloPagina = () => t('NetCable - Mapeador de Rede')

// Assinatura do que é salvo no mapa (sem status/latência, que mudam sozinhos).
const assinaturaMapa = (nodes, edges) => JSON.stringify([
  nodes.map(n => [n.id, Math.round(n.position.x), Math.round(n.position.y), n.style?.width, n.style?.height,
    n.data.label, n.data.ip, n.data.tipo, n.data.monitorMode, n.data.snmpConfig || null, n.data.notificar !== false,
    n.parentNode || null, n.data.rackU || null, n.data.alturaU || null, n.data.us || null]),
  edges.map(e => [e.id, e.source, e.target, e.label || null, e.sourceHandle || null, e.targetHandle || null]),
])

export default function Editor() {
  useI18n()
  const navigate = useNavigate()
  const { projectId } = useParams()
  
  const [projectName, setProjectName] = useState(() => projectId === 'novo' ? t('Novo Mapa') : t('Carregando...'))
  const [isEditingName, setIsEditingName] = useState(false)
  const [isAddModalOpen, setIsAddModalOpen] = useState(false)
  const [newEquipment, setNewEquipment] = useState(null)
  const [stats, setStats] = useState({ online: 0, offline: 0, visual: 0 })
  const [isSaving, setIsSaving] = useState(false)
  const [isLoadingData, setIsLoadingData] = useState(projectId !== 'novo')
  
  const [mapNodes, setMapNodes] = useState([])
  const [mapEdges, setMapEdges] = useState([])
  const [showConfigMenu, setShowConfigMenu] = useState(false)
  
  const [isSettingsModalOpen, setIsSettingsModalOpen] = useState(false)
  const [isDiagnosticsModalOpen, setIsDiagnosticsModalOpen] = useState(false)
  const [isHistoryModalOpen, setIsHistoryModalOpen] = useState(false)
  const [isModelosModalOpen, setIsModelosModalOpen] = useState(false)
  // Biblioteca de modelos (portas reais dos equipamentos). O mapa só corrige cabos
  // presos a portas inexistentes depois que os modelos estiverem carregados.
  const [modelos, setModelos] = useState([])
  const [modelosProntos, setModelosProntos] = useState(false)
  const [currentUser, setCurrentUser] = useState(null)
  const [modoVisualizacao, setModoVisualizacao] = useState(false)
  const [mostrarCabos, alternarCabos] = usePreferenciaCabos()
  const { itens: itensBusca, cabosPorta, atualizar: atualizarResumo } = useResumoMapa()
  const [foco, setFoco] = useState(null)
  const [manutencaoAte, setManutencaoAte] = useState(null)
  const handleStatusProjeto = useCallback((s) => setManutencaoAte(s.manutencao_ate || null), [])
  // Papel "visualizador": o editor vira somente leitura (o backend também bloqueia).
  const somenteLeitura = currentUser?.papel === 'visualizador'
  const leitura = modoVisualizacao || somenteLeitura

  // Estado do Alerta
  const [temAlerta, setTemAlerta] = useState(false)

  const currentNodes = useRef([])
  const currentEdges = useRef([])
  const fileInputRef = useRef(null)

  // Controle de alterações não salvas.
  const [mapaAlterado, setMapaAlterado] = useState(false)
  const baselineRef = useRef(null)
  const nomeSalvoRef = useRef(projectId === 'novo' ? t('Novo Mapa') : null)
  const haAlteracoes = mapaAlterado || (nomeSalvoRef.current !== null && projectName !== nomeSalvoRef.current)

  useEffect(() => {
    if (!haAlteracoes) return
    const avisar = (e) => { e.preventDefault(); e.returnValue = '' }
    window.addEventListener('beforeunload', avisar)
    return () => window.removeEventListener('beforeunload', avisar)
  }, [haAlteracoes])

  const sairDoEditor = () => {
    if (haAlteracoes && !window.confirm(t('Existem alterações não salvas. Sair mesmo assim?'))) return
    navigate('/projects')
  }

  useEffect(() => {
    const fetchMe = async () => {
      try {
        const me = await api.me()
        setCurrentUser(me)
        if (me.idioma !== getIdioma()) api.atualizarPerfil({ idioma: getIdioma() }).catch(() => {})
      } catch (error) { console.error(error) }
    }
    fetchMe()
  }, [])

  useEffect(() => {
    api.listarModelos().then(lista => { setModelos(lista); setModelosProntos(true) })
      .catch(() => toast.error(t('Não foi possível carregar a biblioteca de modelos.')))
  }, [])

  useEffect(() => {
    if (projectId === 'novo') return
    const fetchProjeto = async () => {
      try {
        const data = await api.obterProjeto(projectId)
        setProjectName(data.nome)
        nomeSalvoRef.current = data.nome
        baselineRef.current = null // a próxima atualização do mapa vira a referência
        const formattedNodes = equipamentosParaNodes(data.equipamentos)
        const formattedEdges = conexoesParaEdges(data.conexoes)
        setMapNodes(formattedNodes)
        setMapEdges(formattedEdges)
      } catch (error) {
        toast.error(t('Erro ao carregar o projeto.'))
        navigate('/');
      } finally {
        setIsLoadingData(false)
      }
    }
    fetchProjeto()
  }, [projectId, navigate])

  const handleMapUpdate = useCallback((nodes, edges) => {
    currentNodes.current = nodes
    currentEdges.current = edges
    atualizarResumo(nodes, edges)
    const assinatura = assinaturaMapa(nodes, edges)
    if (baselineRef.current === null) baselineRef.current = assinatura
    setMapaAlterado(assinatura !== baselineRef.current)
    const counts = nodes.reduce((acc, node) => {
      if (node.type === 'rack') return acc // o gabinete não é um equipamento
      if (node.data.status === 'online') acc.online++
      else if (node.data.status === 'offline') acc.offline++
      else if (node.data.status === 'visual') acc.visual++
      return acc
    }, { online: 0, offline: 0, visual: 0 })
    setStats(counts)
  }, [atualizarResumo])

  // Callback chamado quando o NetworkMap detecta uma queda
  const handleAlertaQueda = useCallback((mensagem) => {
    setTemAlerta(true)
    toast.error(mensagem, { duration: 5000 }) // Notificação no canto da tela
    
    // Piscar o título da aba do navegador
    let isOriginalTitle = false;
    const interval = setInterval(() => {
      document.title = isOriginalTitle ? t('⚠️ QUEDA DETECTADA ⚠️') : tituloPagina();
      isOriginalTitle = !isOriginalTitle;
    }, 1000);
    
    // Para de piscar depois de 10 segundos e restaura o título.
    setTimeout(() => { clearInterval(interval); document.title = tituloPagina() }, 10000);
    
    // Remove o alerta visual após 10 segundos
    setTimeout(() => setTemAlerta(false), 10000)
  }, [])

  const handleSaveProject = async () => {
    if (isSaving || somenteLeitura) return
    setIsSaving(true)
    try {
      if (projectId !== 'novo' && projectName !== t('Carregando...')) {
        await api.editarNomeProjeto(projectId, projectName)
      }
      const equipamentosFormatados = currentNodes.current.map(nodeParaEquipamento)
      const conexoesFormatadas = currentEdges.current.map(edge => ({
        id: edge.id, source: edge.source, target: edge.target, label: edge.label || null,
        sourceHandle: edge.sourceHandle || null, targetHandle: edge.targetHandle || null
      }))
      let idParaSalvar = projectId
      if (projectId === 'novo') {
        const projetoCriado = await api.criarProjeto(projectName)
        idParaSalvar = projetoCriado.id
      }
      const ok = await api.salvarMapa(idParaSalvar, equipamentosFormatados, conexoesFormatadas)
      if (ok) {
        baselineRef.current = assinaturaMapa(currentNodes.current, currentEdges.current)
        nomeSalvoRef.current = projectName
        setMapaAlterado(false)
        toast.success(t('Projeto salvo com sucesso!'))
        if (projectId === 'novo') navigate(`/editor/${idParaSalvar}`, { replace: true })
      }
    } catch (error) { toast.error(error.message || t('Erro ao salvar o projeto.'), { duration: 6000 }) } finally { setIsSaving(false) }
  }

  // Atalho Ctrl+S / Cmd+S para salvar (ref evita registrar o listener a cada render).
  const salvarRef = useRef(handleSaveProject)
  salvarRef.current = handleSaveProject
  useEffect(() => {
    const onKey = (e) => {
      if ((e.ctrlKey || e.metaKey) && e.key.toLowerCase() === 's') { e.preventDefault(); salvarRef.current() }
    }
    window.addEventListener('keydown', onKey)
    return () => window.removeEventListener('keydown', onKey)
  }, [])

  // navigator.clipboard só existe em contexto seguro (HTTPS ou localhost).
  // Em homelab acessado via http://IP ele é undefined, então usamos fallbacks.
  const copiarTexto = async (texto) => {
    if (navigator.clipboard && window.isSecureContext) {
      try { await navigator.clipboard.writeText(texto); return true } catch { /* tenta o fallback */ }
    }
    const textarea = document.createElement('textarea')
    textarea.value = texto
    textarea.setAttribute('readonly', '')
    textarea.style.position = 'fixed'
    textarea.style.opacity = '0'
    document.body.appendChild(textarea)
    textarea.select()
    let ok = false
    try { ok = document.execCommand('copy') } catch { ok = false }
    document.body.removeChild(textarea)
    return ok
  }

  const handleCopyLink = async (regenerar = false) => {
    setShowConfigMenu(false);
    if (projectId === 'novo') { toast.error(t('Salve o projeto primeiro!')); return; }
    if (regenerar && !window.confirm(t('Gerar um novo link? O link atual deixará de funcionar (inclusive em TVs já abertas).'))) return;
    let token
    try {
      token = await api.gerarLinkPublico(projectId, regenerar)
    } catch (error) { toast.error(error.message); return }
    const link = `${window.location.origin}/share/${token}`;
    if (await copiarTexto(link)) {
      toast.success(regenerar ? t('Novo link público copiado!') : t('Link público copiado!'))
    } else {
      // Último recurso: mostra o link para o usuário copiar manualmente.
      window.prompt(t('Copie o link público (Ctrl+C):'), link)
    }
  };

  const handleRevogarLink = async () => {
    setShowConfigMenu(false);
    if (projectId === 'novo') return;
    if (!window.confirm(t('Revogar o link público? Quem estiver com ele aberto perderá o acesso.'))) return;
    try {
      await api.revogarLinkPublico(projectId)
      toast.success(t('Link público revogado.'))
    } catch (error) { toast.error(error.message) }
  };

  const handleLogout = () => { api.logout(); navigate('/'); };
  const handleAddEquipment = (equipamento) => { setNewEquipment({ ...equipamento, id: Date.now() }); setIsAddModalOpen(false) }
  const handleAddNeighbors = (neighbors) => {
    setNewEquipment(neighbors.map((neighbor, index) => ({ ...neighbor, id: `${Date.now()}_${index}` })))
    setIsAddModalOpen(false)
    toast.success(t('{n} vizinho(s) adicionado(s) ao mapa. Salve o projeto para manter as alterações.', { n: neighbors.length }))
  }

  // Exporta o mapa SALVO (com os modelos do catálogo usados nele; senhas SNMP ficam de fora).
  const handleExport = async () => {
    try {
      if (projectId === 'novo') { toast.error(t('Salve o projeto antes de exportar.')); return }
      await api.exportarProjeto(projectId, projectName)
      toast.success(t('Mapa exportado (versão salva).'))
    } catch (err) { toast.error(err.message) }
  }

  // Importar cria um projeto NOVO (nunca sobrescreve este) e abre o primeiro importado.
  const handleImport = async (event) => {
    const file = event.target.files[0]
    event.target.value = null
    if (!file) return
    try {
      const importados = await api.importarArquivo(file)
      toast.success(t('{n} mapa(s) importado(s) como projeto novo.', { n: importados.length }))
      if (importados[0]) navigate(`/editor/${importados[0].id}`)
    } catch (err) { toast.error(err.message, { duration: 7000 }) }
  }

  if (isLoadingData) return <div style={{ color: '#94a3b8', display: 'flex', justifyContent: 'center', alignItems: 'center', height: '100vh' }}><Loader2 className="spin" /> {t('Carregando...')}</div>

  return (
    <div style={{ display: 'flex', flexDirection: 'column', height: '100vh', backgroundColor: '#0f172a' }}>
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', backgroundColor: '#1e293b', padding: '10px 20px', borderBottom: '1px solid #334155' }}>
        
        <div style={{ display: 'flex', alignItems: 'center', gap: '15px' }}>
          <button onClick={sairDoEditor} title={t('Voltar aos projetos')} style={{ background: 'transparent', border: 'none', color: '#94a3b8', cursor: 'pointer', display: 'flex', alignItems: 'center' }}>
            <ArrowLeft size={20} />
          </button>
          <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
            <Network size={20} color="#3b82f6" />
            {isEditingName ? (
              <input autoFocus type="text" value={projectName} onChange={(e) => setProjectName(e.target.value)} onBlur={() => setIsEditingName(false)} onKeyDown={(e) => e.key === 'Enter' && setIsEditingName(false)} style={{ backgroundColor: '#0f172a', color: 'white', border: '1px solid #3b82f6', borderRadius: '4px', padding: '4px 8px', fontSize: '16px', fontWeight: 'bold' }} />
            ) : (
              <span onClick={() => !somenteLeitura && setIsEditingName(true)} style={{ fontWeight: 'bold', cursor: somenteLeitura ? 'default' : 'pointer', padding: '4px 8px', borderRadius: '4px', border: '1px solid transparent' }}>{projectName}{!somenteLeitura && ' ✏️'}</span>
            )}
          </div>
        </div>

        <div style={{ display: 'flex', gap: '10px', alignItems: 'center' }}>
          
          {/* ÍCONE DE ALERTA NO HEADER */}
          <div title={temAlerta ? t('Atenção: Queda detectada!') : t('Sem alertas')} style={{ padding: '8px', backgroundColor: temAlerta ? '#ef4444' : 'transparent', borderRadius: '50%', display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
            {temAlerta ? <AlertTriangle size={20} color="white" className="animate-pulse" /> : <Bell size={20} color="#64748b" />}
          </div>

          <div style={{ display: 'flex', alignItems: 'center', gap: '12px', backgroundColor: '#0f172a', padding: '6px 15px', borderRadius: '8px', border: '1px solid #334155', marginRight: '10px' }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: '5px', fontSize: '13px' }}><CheckCircle2 size={16} color="#10b981" /> <span style={{ color: '#10b981', fontWeight: 'bold' }}>{stats.online}</span></div>
            <div style={{ display: 'flex', alignItems: 'center', gap: '5px', fontSize: '13px' }}><XCircle size={16} color="#ef4444" /> <span style={{ color: '#ef4444', fontWeight: 'bold' }}>{stats.offline}</span></div>
            <div style={{ display: 'flex', alignItems: 'center', gap: '5px', fontSize: '13px' }}><MinusCircle size={16} color="#64748b" /> <span style={{ color: '#64748b', fontWeight: 'bold' }}>{stats.visual}</span></div>
          </div>

          {somenteLeitura && (
            <span title={t('Seu usuário é Visualizador: peça a um administrador para mudar o papel se precisar editar.')} style={{ display: 'flex', alignItems: 'center', gap: '6px', fontSize: '12px', color: '#94a3b8', padding: '6px 10px', border: '1px solid #334155', borderRadius: '6px' }}>
              <Eye size={15} /> {t('Somente visualização')}
            </span>
          )}
          <BuscaEquipamento itens={itensBusca} onEscolher={(id) => setFoco({ id, n: Date.now() })} />
          <ManutencaoProjeto projectId={projectId} ate={manutencaoAte} podeEditar={!somenteLeitura} onMudou={setManutencaoAte} />

          <button onClick={alternarCabos} title={mostrarCabos ? t('Ocultar cabos entre portas') : t('Mostrar cabos entre portas')} aria-pressed={!mostrarCabos}
            style={{ display: 'flex', alignItems: 'center', gap: '6px', padding: '8px 12px', backgroundColor: mostrarCabos ? '#334155' : '#7c2d12', color: 'white', border: 'none', borderRadius: '6px', cursor: 'pointer' }}>
            {mostrarCabos ? <Cable size={18} /> : <Unplug size={18} />}
            {cabosPorta > 0 && <span style={{ fontSize: '12px', fontWeight: 'bold' }}>{cabosPorta}</span>}
          </button>
          {!somenteLeitura && <button onClick={() => setModoVisualizacao(v => !v)} title={modoVisualizacao ? t('Voltar ao modo edição') : t('Modo visualização (somente leitura)')} style={{ display: 'flex', alignItems: 'center', gap: '6px', padding: '8px 12px', backgroundColor: modoVisualizacao ? '#3b82f6' : '#334155', color: 'white', border: 'none', borderRadius: '6px', cursor: 'pointer' }}>
            {modoVisualizacao ? <><Pencil size={18} /> {t('Editar')}</> : <Eye size={18} />}
          </button>}

          <input type="file" ref={fileInputRef} onChange={handleImport} accept=".json,.zip" style={{ display: 'none' }} />
          {!leitura && <button onClick={() => fileInputRef.current.click()} title={t('Importar mapa ou backup (.json / .zip)')} style={{ padding: '8px 12px', backgroundColor: '#334155', color: 'white', border: 'none', borderRadius: '6px', cursor: 'pointer' }}><Upload size={18} /></button>}
          <button onClick={handleExport} title={t('Exportar mapa (.json)')} style={{ padding: '8px 12px', backgroundColor: '#334155', color: 'white', border: 'none', borderRadius: '6px', cursor: 'pointer' }}><Download size={18} /></button>

          {!leitura && (
            <button onClick={() => setIsAddModalOpen(true)} style={{ display: 'flex', alignItems: 'center', gap: '6px', padding: '8px 16px', backgroundColor: '#3b82f6', color: 'white', border: 'none', borderRadius: '6px', cursor: 'pointer' }}>
              <Plus size={18} /> {t('Adicionar')}
            </button>
          )}
          
          {!somenteLeitura && <button onClick={handleSaveProject} disabled={isSaving} title={haAlteracoes ? t('Há alterações não salvas (Ctrl+S)') : t('Tudo salvo (Ctrl+S)')} style={{ display: 'flex', alignItems: 'center', gap: '6px', padding: '8px 16px', backgroundColor: isSaving ? '#475569' : (haAlteracoes ? '#f59e0b' : '#10b981'), color: 'white', border: 'none', borderRadius: '6px', cursor: isSaving ? 'wait' : 'pointer' }}>
            {isSaving ? <Loader2 size={18} className="spin" /> : <Save size={18} />} {isSaving ? t('Salvando...') : (haAlteracoes ? `${t('Salvar')} *` : t('Salvar'))}
          </button>}
          
          <div style={{ position: 'relative' }}>
            <button onClick={() => setShowConfigMenu(!showConfigMenu)} style={{ display: 'flex', alignItems: 'center', padding: '8px 12px', backgroundColor: showConfigMenu ? '#475569' : '#334155', color: 'white', border: 'none', borderRadius: '6px', cursor: 'pointer' }}>
              <Settings size={18} />
            </button>
            {showConfigMenu && (
              <div style={{ position: 'absolute', top: '110%', right: 0, backgroundColor: '#1e293b', border: '1px solid #334155', borderRadius: '6px', padding: '5px', minWidth: '180px', boxShadow: '0 4px 6px rgba(0,0,0,0.3)', zIndex: 100 }}>
                <button onClick={() => { setShowConfigMenu(false); setIsSettingsModalOpen(true) }} style={{ display: 'flex', alignItems: 'center', gap: '8px', width: '100%', padding: '10px', backgroundColor: 'transparent', color: 'white', border: 'none', textAlign: 'left', cursor: 'pointer', borderRadius: '4px' }} className="hover:bg-slate-700">
                  <UserCog size={16} color="#94a3b8"/> {t('Meu perfil e notificações')}
                </button>
                <button onClick={() => { setShowConfigMenu(false); setIsDiagnosticsModalOpen(true) }} style={{ display: 'flex', alignItems: 'center', gap: '8px', width: '100%', padding: '10px', backgroundColor: 'transparent', color: 'white', border: 'none', textAlign: 'left', cursor: 'pointer', borderRadius: '4px' }}>
                  <Activity size={16} color="#10b981"/> {t('Diagnóstico')}
                </button>
                <button onClick={() => { setShowConfigMenu(false); setIsModelosModalOpen(true) }} style={{ display: 'flex', alignItems: 'center', gap: '8px', width: '100%', padding: '10px', backgroundColor: 'transparent', color: 'white', border: 'none', textAlign: 'left', cursor: 'pointer', borderRadius: '4px' }}>
                  <Boxes size={16} color="#a78bfa"/> {t('Modelos de equipamento')}
                </button>
                <button onClick={() => { setShowConfigMenu(false); setIsHistoryModalOpen(true) }} style={{ display: 'flex', alignItems: 'center', gap: '8px', width: '100%', padding: '10px', backgroundColor: 'transparent', color: 'white', border: 'none', textAlign: 'left', cursor: 'pointer', borderRadius: '4px' }}>
                  <Activity size={16} color="#f59e0b"/> {t('Histórico')}
                </button>
                {!somenteLeitura && <>
                <button onClick={() => handleCopyLink(false)} style={{ display: 'flex', alignItems: 'center', gap: '8px', width: '100%', padding: '10px', backgroundColor: 'transparent', color: 'white', border: 'none', textAlign: 'left', cursor: 'pointer', borderRadius: '4px' }} className="hover:bg-slate-700">
                  <Share2 size={16} color="#3b82f6"/> {t('Copiar Link Público')}
                </button>
                <button onClick={() => handleCopyLink(true)} style={{ display: 'flex', alignItems: 'center', gap: '8px', width: '100%', padding: '10px', backgroundColor: 'transparent', color: 'white', border: 'none', textAlign: 'left', cursor: 'pointer', borderRadius: '4px' }}>
                  <RefreshCw size={16} color="#94a3b8"/> {t('Gerar Novo Link')}
                </button>
                <button onClick={handleRevogarLink} style={{ display: 'flex', alignItems: 'center', gap: '8px', width: '100%', padding: '10px', backgroundColor: 'transparent', color: 'white', border: 'none', textAlign: 'left', cursor: 'pointer', borderRadius: '4px' }}>
                  <Link2Off size={16} color="#f59e0b"/> {t('Revogar Link Público')}
                </button>
                </>}
                <div style={{ height: '1px', backgroundColor: '#334155', margin: '5px 0' }}></div>
                <button onClick={handleLogout} style={{ display: 'flex', alignItems: 'center', gap: '8px', width: '100%', padding: '10px', backgroundColor: 'transparent', color: '#ef4444', border: 'none', textAlign: 'left', cursor: 'pointer', borderRadius: '4px' }}>
                  <LogOut size={16} /> {t('Sair')}
                </button>
                <div style={{ padding: '6px 10px 4px', display: 'flex', justifyContent: 'center' }}>
                  <SeletorIdioma compacto onChange={(i) => api.atualizarPerfil({ idioma: i }).catch(() => {})} />
                </div>
              </div>
            )}
          </div>
        </div>
      </div>

      <div style={{ flex: 1 }}>
        <NetworkMap initialNodes={mapNodes} initialEdges={mapEdges} newEquipment={newEquipment} onMapUpdate={handleMapUpdate} onAlertaQueda={handleAlertaQueda} onStatusProjeto={handleStatusProjeto} readOnly={leitura} projectId={projectId} modelos={modelos} modelosProntos={modelosProntos} mostrarCabosPorta={mostrarCabos} foco={foco} />
      </div>

      {isAddModalOpen && <AddEquipmentModal nodes={currentNodes.current} modelos={modelos} onClose={() => setIsAddModalOpen(false)} onAdd={handleAddEquipment} onAddNeighbors={handleAddNeighbors} />}
      {isSettingsModalOpen && <SettingsModal onClose={() => setIsSettingsModalOpen(false)} currentUser={currentUser} onUpdated={setCurrentUser} />}
      {isDiagnosticsModalOpen && <DiagnosticsModal onClose={() => setIsDiagnosticsModalOpen(false)} />}
      {isHistoryModalOpen && <HistoryModal projectId={projectId} onClose={() => setIsHistoryModalOpen(false)} />}
      {isModelosModalOpen && <ModelosModal podeEditar={!somenteLeitura} onChange={setModelos} onClose={() => setIsModelosModalOpen(false)} />}
    </div>
  )
}
