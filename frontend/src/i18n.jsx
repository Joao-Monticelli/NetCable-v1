// Minimal PT/EN internationalization. No external dependency.
// Default language: English. Persisted in localStorage as `netcable_lang`.
import { createContext, useCallback, useContext, useState } from 'react'

const STRINGS = {
  en: {
    login: {
      restricted: 'Restricted Access',
      user: 'Username',
      password: 'Password',
      enter: 'Sign in',
      welcome: 'Welcome to NetCable!',
      failed: 'Sign in failed.',
    },
    projects: {
      title: 'My Projects',
      editProfile: 'Edit Profile',
      logout: 'Log out',
      loading: 'Loading...',
      newProject: 'Create New Project',
      deleteConfirm: 'Delete project "{name}"?',
      deleted: 'Project deleted.',
      deleteError: 'Failed to delete.',
    },
    editor: {
      newMap: 'New Map',
      loadingProject: 'Loading...',
      loadingData: 'Loading...',
      loadError: 'Failed to load the project.',
      saveSuccess: 'Project saved successfully!',
      saveError: 'Failed to save the project.',
      saveFirst: 'Save the project first!',
      linkCopied: 'Public link copied!',
      exportDone: 'Backup exported!',
      importDone: 'Backup imported!',
      importError: 'Failed to read the JSON file.',
      add: 'Add',
      save: 'Save',
      saving: 'Saving...',
      editProfile: 'Edit Profile',
      diagnostics: 'Diagnostics',
      publicLink: 'Generate Public Link',
      discover: 'Discover',
      discovering: 'Scanning network...',
      discoverNone: 'No new devices found.',
      discoverFound: '{n} new device(s) added to the map. Review and Save.',
      discoverFail: 'Network scan failed.',
      discoverExists: '{n} already on the map, skipped.',
      logout: 'Log out',
      deviceDown: 'Device {name} is down!',
      outageTitle: '⚠️ OUTAGE DETECTED ⚠️',
      alertOn: 'Warning: outage detected!',
      alertOff: 'No alerts',
      importTitle: 'Import JSON',
      exportTitle: 'Export JSON',
    },
    shared: {
      loading: 'Loading public map...',
      loadFail: 'Failed to load',
      notFound: 'Could not connect to the NetCable server or the link is invalid.',
      publicView: '(Public View)',
    },
    addEquipment: {
      title: 'Add Device',
      monitorMethod: 'Monitoring method',
      ipOption: 'IP / ICMP + TCP',
      snmpOption: 'SNMPv3',
      snmpCreds: 'SNMPv3 credentials',
      user: 'Username',
      authPass: 'Authentication password',
      privPass: 'Privacy password',
      snmpPort: 'SNMP port (default 161)',
      discovering: 'Querying neighbors...',
      discover: 'Discover LLDP/CDP neighbors',
      neighborsFound: '{n} neighbor(s) found: {list}',
      noNeighbors: 'No LLDP/CDP neighbors found.',
      unnamed: 'unnamed',
      name: 'Device Name',
      namePh: 'E.g. Floor 1 Switch',
      noIp: 'Device without IP (Layer 2)',
      ipAddress: 'IP Address',
      ipPh: 'E.g. 192.168.0.10',
      ipDisabled: 'Disabled',
      test: 'Test',
      onlineIn: 'Online! Responded in {ms}ms.',
      connFail: 'Connection failed. Check the IP.',
      noResponse: 'The device did not respond.',
      testFail: 'Failed to query the device.',
      fillName: 'Fill in the Name.',
      fillIp: 'Fill in the IP or check No IP.',
      ipNoResponse: 'The IP did not respond. Add anyway?',
      backendError: 'Backend error. Add anyway?',
      newTypePh: 'New type...',
      addType: 'Add',
      newTypeTitle: 'Create new type',
      cancel: 'Cancel',
      add: 'Add',
    },
    equipment: {
      title: 'Edit Device',
      name: 'Device Name',
      monitorMethod: 'Monitoring method',
      snmpHint: 'SNMPv3 credentials (leave passwords empty to keep the current ones)',
      user: 'Username',
      authPass: 'Authentication password',
      privPass: 'Privacy password',
      snmpPort: 'SNMP port (default 161)',
      ip: 'IP Address',
      type: 'Type',
      tip: 'Tip: you can drag the device borders on the map to resize.',
      resetSize: 'Restore Default Size',
      delete: 'Delete',
      saveChanges: 'Save Changes',
    },
    edge: {
      title: 'Edit Connection',
      label: 'Connection Label (Optional)',
      labelPh: 'E.g. Fiber, Cat6 cable...',
      source: 'Source (Parent)',
      target: 'Target (Child)',
      delete: 'Delete Connection',
      save: 'Save',
    },
    settings: {
      title: 'My Profile',
      email: 'Email (for notifications)',
      telegram: 'Telegram alerts',
      soon: 'SOON',
      changePassword: 'Change Password',
      currentPassword: 'Current Password',
      currentPasswordPh: 'Enter your current password',
      newPassword: 'New Password',
      newPasswordPh: 'Enter the new password',
      saving: 'Saving...',
      saveChanges: 'Save Changes',
      updated: 'Profile updated successfully!',
      commError: 'Failed to communicate with the server.',
    },
    diagnostics: {
      title: 'NetCable Diagnostics',
      checking: 'Checking installation...',
      database: 'Database',
      connected: 'connected',
      db: 'DB',
      recheck: 'Check again',
    },
    types: {
      unknown: 'Unknown',
      router: 'Router',
      managedSwitch: 'Managed Switch',
      unmanagedSwitch: 'Unmanaged Switch',
      firewall: 'Firewall',
      server: 'Server',
      pc: 'PC',
    },
    api: {
      connectFail: 'Could not reach the NetCable API: ',
      loginFail: 'Login failed (HTTP ',
      unauthorized: 'Unauthorized',
      profileFail: 'Failed to update profile.',
      monitorFail: 'Monitoring failed',
      discoveryFail: 'Discovery failed',
      apiDown: 'API unavailable (HTTP ',
    },
    misc: {
      centerNode: 'Could not center the node.',
      soundBlocked: 'Browser blocked the sound. Interact with the page first.',
      noIpLabel: 'No IP',
    },
  },
  pt: {
    login: {
      restricted: 'Acesso Restrito',
      user: 'Usuário',
      password: 'Senha',
      enter: 'Entrar',
      welcome: 'Bem-vindo ao NetCable!',
      failed: 'Falha ao fazer login.',
    },
    projects: {
      title: 'Meus Projetos',
      editProfile: 'Editar Perfil',
      logout: 'Sair',
      loading: 'Carregando...',
      newProject: 'Criar Novo Projeto',
      deleteConfirm: 'Excluir o projeto "{name}"?',
      deleted: 'Projeto excluído com sucesso.',
      deleteError: 'Erro ao excluir.',
    },
    editor: {
      newMap: 'Novo Mapa',
      loadingProject: 'Carregando...',
      loadingData: 'Carregando...',
      loadError: 'Erro ao carregar o projeto.',
      saveSuccess: 'Projeto salvo com sucesso!',
      saveError: 'Erro ao salvar o projeto.',
      saveFirst: 'Salve o projeto primeiro!',
      linkCopied: 'Link público copiado!',
      exportDone: 'Backup exportado!',
      importDone: 'Backup importado!',
      importError: 'Erro ao ler o arquivo JSON.',
      add: 'Adicionar',
      save: 'Salvar',
      saving: 'Salvando...',
      editProfile: 'Editar Perfil',
      diagnostics: 'Diagnóstico',
      publicLink: 'Gerar Link Público',
      discover: 'Descobrir',
      discovering: 'Escaneando a rede...',
      discoverNone: 'Nenhum dispositivo novo encontrado.',
      discoverFound: '{n} novo(s) dispositivo(s) no mapa. Revise e Salve.',
      discoverFail: 'Falha no escaneamento da rede.',
      discoverExists: '{n} já estavam no mapa, ignorados.',
      logout: 'Sair',
      deviceDown: 'O equipamento {name} caiu!',
      outageTitle: '⚠️ QUEDA DETECTADA ⚠️',
      alertOn: 'Atenção: Queda detectada!',
      alertOff: 'Sem alertas',
      importTitle: 'Importar JSON',
      exportTitle: 'Exportar JSON',
    },
    shared: {
      loading: 'Carregando mapa público...',
      loadFail: 'Falha ao carregar',
      notFound: 'Não foi possível conectar ao servidor do NetCable ou o link é inválido.',
      publicView: '(Visualização Pública)',
    },
    addEquipment: {
      title: 'Adicionar Equipamento',
      monitorMethod: 'Método de monitoramento',
      ipOption: 'IP / ICMP + TCP',
      snmpOption: 'SNMPv3',
      snmpCreds: 'Credenciais SNMPv3',
      user: 'Usuário',
      authPass: 'Senha de autenticação',
      privPass: 'Senha de privacidade',
      snmpPort: 'Porta SNMP (padrão 161)',
      discovering: 'Consultando vizinhos...',
      discover: 'Descobrir vizinhos LLDP/CDP',
      neighborsFound: '{n} vizinho(s) encontrado(s): {list}',
      noNeighbors: 'Nenhum vizinho LLDP/CDP encontrado.',
      unnamed: 'sem nome',
      name: 'Nome do Equipamento',
      namePh: 'Ex: Switch Andar 1',
      noIp: 'Equipamento sem IP (Camada 2)',
      ipAddress: 'Endereço IP',
      ipPh: 'Ex: 192.168.0.10',
      ipDisabled: 'Desabilitado',
      test: 'Testar',
      onlineIn: 'Online! Resposta em {ms}ms.',
      connFail: 'Falha na conexão. Verifique o IP.',
      noResponse: 'O equipamento não respondeu.',
      testFail: 'Falha ao consultar o equipamento.',
      fillName: 'Preencha o Nome.',
      fillIp: 'Preencha o IP ou marque Sem IP.',
      ipNoResponse: 'O IP não respondeu. Deseja adicionar mesmo assim?',
      backendError: 'Erro no backend. Deseja adicionar mesmo assim?',
      newTypePh: 'Novo tipo...',
      addType: 'Adicionar',
      newTypeTitle: 'Criar novo tipo',
      cancel: 'Cancelar',
      add: 'Adicionar',
    },
    equipment: {
      title: 'Editar Equipamento',
      name: 'Nome do Equipamento',
      monitorMethod: 'Método de monitoramento',
      snmpHint: 'Credenciais SNMPv3 (deixe as senhas vazias para manter as atuais)',
      user: 'Usuário',
      authPass: 'Senha de autenticação',
      privPass: 'Senha de privacidade',
      snmpPort: 'Porta SNMP (padrão 161)',
      ip: 'Endereço IP',
      type: 'Tipo',
      tip: 'Dica: Você pode arrastar as bordas do equipamento no mapa para redimensionar.',
      resetSize: 'Restaurar Tamanho Padrão',
      delete: 'Excluir',
      saveChanges: 'Salvar Alterações',
    },
    edge: {
      title: 'Editar Conexão',
      label: 'Rótulo da Conexão (Opcional)',
      labelPh: 'Ex: Fibra Óptica, Cabo Cat6...',
      source: 'Origem (Pai)',
      target: 'Destino (Filho)',
      delete: 'Excluir Conexão',
      save: 'Salvar',
    },
    settings: {
      title: 'Meu Perfil',
      email: 'E-mail (Para notificações)',
      telegram: 'Alertas via Telegram',
      soon: 'EM BREVE',
      changePassword: 'Alterar Senha',
      currentPassword: 'Senha Atual',
      currentPasswordPh: 'Digite sua senha atual',
      newPassword: 'Nova Senha',
      newPasswordPh: 'Digite a nova senha',
      saving: 'Salvando...',
      saveChanges: 'Salvar Alterações',
      updated: 'Perfil atualizado com sucesso!',
      commError: 'Erro de comunicação com o servidor.',
    },
    diagnostics: {
      title: 'Diagnóstico do NetCable',
      checking: 'Verificando instalação...',
      database: 'Banco de dados',
      connected: 'conectado',
      db: 'Banco',
      recheck: 'Verificar novamente',
    },
    types: {
      unknown: 'Desconhecido',
      router: 'Roteador',
      managedSwitch: 'Switch Gerenciável',
      unmanagedSwitch: 'Switch Não Gerenciável',
      firewall: 'Firewall',
      server: 'Servidor',
      pc: 'PC',
    },
    api: {
      connectFail: 'Não foi possível conectar à API do NetCable: ',
      loginFail: 'Falha no login (HTTP ',
      unauthorized: 'Não autorizado',
      profileFail: 'Erro ao atualizar perfil.',
      monitorFail: 'Falha no monitoramento',
      discoveryFail: 'Falha na descoberta',
      apiDown: 'API indisponível (HTTP ',
    },
    misc: {
      centerNode: 'Não foi possível centralizar o nó.',
      soundBlocked: 'Navegador bloqueou o som. Interaja com a página primeiro.',
      noIpLabel: 'Sem IP',
    },
  },
}

export const DEFAULT_LANG = 'en'
export const LANG_KEY = 'netcable_lang'

export function getLang() {
  const saved = typeof localStorage !== 'undefined' ? localStorage.getItem(LANG_KEY) : null
  return saved === 'pt' || saved === 'en' ? saved : DEFAULT_LANG
}

// Non-React helper (used by api.js): t('login.failed') with {var} interpolation.
export function tr(lang, key, vars) {
  const parts = key.split('.')
  let node = STRINGS[lang] || STRINGS[DEFAULT_LANG]
  for (const p of parts) node = node?.[p]
  if (typeof node !== 'string') node = key
  if (vars) for (const [k, v] of Object.entries(vars)) node = node.replace(`{${k}}`, v)
  return node
}

const LangContext = createContext({ lang: DEFAULT_LANG, setLang: () => {}, t: (k, v) => tr(DEFAULT_LANG, k, v) })

export function LanguageProvider({ children }) {
  const [lang, setLangState] = useState(getLang())
  const setLang = useCallback((l) => {
    if (l !== 'pt' && l !== 'en') return
    localStorage.setItem(LANG_KEY, l)
    setLangState(l)
  }, [])
  const t = useCallback((key, vars) => tr(lang, key, vars), [lang])
  return <LangContext.Provider value={{ lang, setLang, t }}>{children}</LangContext.Provider>
}

export function useLang() {
  return useContext(LangContext)
}

// Small EN | PT toggle button for headers.
export function LangToggle() {
  const { lang, setLang } = useLang()
  const btn = (l, label) => ({
    padding: '6px 10px',
    backgroundColor: lang === l ? '#3b82f6' : 'transparent',
    color: 'white',
    border: 'none',
    borderRadius: '4px',
    cursor: 'pointer',
    fontWeight: 'bold',
    fontSize: '12px',
  })
  return (
    <div style={{ display: 'flex', gap: '2px', backgroundColor: '#334155', borderRadius: '6px', padding: '2px' }} title="Language / Idioma">
      <button onClick={() => setLang('en')} style={btn('en')}>EN</button>
      <button onClick={() => setLang('pt')} style={btn('pt')}>PT</button>
    </div>
  )
}

// Canonical device-type values (stored in the DB) with bilingual labels.
// Old PT values still in existing diagrams keep working: the icon switch in
// NetworkMap matches both languages.
export const TYPE_VALUES = ['router', 'managed-switch', 'unmanaged-switch', 'firewall', 'server', 'pc', 'unknown']

export function typeLabel(t, value) {
  switch (value) {
    case 'unknown': return t('types.unknown')
    case 'router': case 'Roteador': return t('types.router')
    case 'managed-switch': case 'Switch Gerenciável': return t('types.managedSwitch')
    case 'unmanaged-switch': case 'Switch Não Gerenciável': return t('types.unmanagedSwitch')
    case 'firewall': case 'Firewall': return t('types.firewall')
    case 'server': case 'Servidor': return t('types.server')
    case 'pc': case 'PC': return t('types.pc')
    default: return value // custom user-created types stay as-is
  }
}
