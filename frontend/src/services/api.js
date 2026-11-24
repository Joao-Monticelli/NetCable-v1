import { t, getIdioma } from '../i18n'

// Em produção e no desenvolvimento o frontend usa o mesmo host do backend
// através de proxy. VITE_API_URL continua disponível para instalações externas.
const API_BASE_URL = import.meta.env.VITE_API_URL || '';
const API_URL = `${API_BASE_URL}/api`;

// Pega o token salvo no navegador
const getToken = () => localStorage.getItem('netcable_token');

// Função genérica para headers
const getHeaders = () => ({
  'Content-Type': 'application/json',
  'Authorization': `Bearer ${getToken()}`,
  'Accept-Language': getIdioma(), // o backend responde as mensagens de erro neste idioma
});

// Requisição autenticada genérica: devolve o JSON ou lança Error com o "detail" da API.
async function requisicao(caminho, opcoes = {}, erroPadrao = t('Falha na comunicação com o servidor.')) {
  const res = await fetch(`${API_URL}${caminho}`, { ...opcoes, headers: getHeaders() });
  const data = await res.json().catch(() => ({}));
  if (!res.ok) throw new Error(data.detail || erroPadrao);
  return data;
}

// Baixa um Blob como arquivo no navegador.
function salvarArquivo(blob, nome) {
  const url = URL.createObjectURL(blob)
  const link = document.createElement('a')
  link.href = url
  link.download = nome
  link.click()
  setTimeout(() => URL.revokeObjectURL(url), 1000)
}

const nomeSeguro = (texto) => (texto || 'mapa').normalize('NFD').replace(/[̀-ͯ]/g, '').replace(/[^\w.-]+/g, '_').slice(0, 60)

export const api = {
  // --- Exportar / importar / backup ---
  async exportarProjeto(projetoId, nomeProjeto) {
    const dados = await requisicao(`/projetos/${projetoId}/exportar`, {}, t('Não foi possível exportar o mapa.'))
    salvarArquivo(new Blob([JSON.stringify(dados, null, 2)], { type: 'application/json' }), `netcable-${nomeSeguro(nomeProjeto || dados.projeto?.nome)}.json`)
    return dados
  },
  async importarArquivo(arquivo) {
    const form = new FormData()
    form.append('arquivo', arquivo)
    const res = await fetch(`${API_URL}/projetos/importar`, {
      method: 'POST', body: form, headers: { 'Authorization': `Bearer ${getToken()}`, 'Accept-Language': getIdioma() }
    })
    const data = await res.json().catch(() => ({}))
    if (!res.ok) throw new Error(data.detail || t('Não foi possível importar o arquivo.'))
    return data.importados
  },
  obterBackup() { return requisicao('/backup', {}, t('Não foi possível carregar a configuração de backup.')) },
  salvarBackup(dados) { return requisicao('/backup', { method: 'PUT', body: JSON.stringify(dados) }, t('Não foi possível salvar a configuração de backup.')) },
  backupAgora() { return requisicao('/backup/agora', { method: 'POST' }, t('Falha ao criar o backup.')) },
  async baixarBackup(nome) {
    const res = await fetch(`${API_URL}/backup/arquivo/${encodeURIComponent(nome)}`, { headers: getHeaders() })
    if (!res.ok) throw new Error(t('Não foi possível baixar o backup.'))
    salvarArquivo(await res.blob(), nome)
  },

  // --- Audit log (admin) and SLA report ---
  listarAuditoria({ acao = '', usuario = '', antesDe = null, limite = 100 } = {}) {
    const q = new URLSearchParams({ limite: String(limite) })
    if (acao) q.set('acao', acao)
    if (usuario) q.set('usuario', usuario)
    if (antesDe) q.set('antes_de', String(antesDe))
    return requisicao(`/auditoria?${q}`, {}, t('Não foi possível carregar o log de auditoria.'))
  },
  async baixarSlaCsv(projetoId, dias = 30) {
    const res = await fetch(`${API_URL}/projetos/${projetoId}/sla.csv?dias=${dias}`, { headers: getHeaders() })
    if (!res.ok) throw new Error((await res.json().catch(() => ({}))).detail || t('Não foi possível gerar o relatório de SLA.'))
    const nome = /filename="([^"]+)"/.exec(res.headers.get('Content-Disposition') || '')?.[1] || `netcable-sla-${dias}d.csv`
    salvarArquivo(await res.blob(), nome)
  },

  // --- Métricas SNMP ---
  metricasEquipamento(projetoId, equipamentoId, horas = 24) {
    return requisicao(`/projetos/${projetoId}/equipamentos/${encodeURIComponent(equipamentoId)}/metricas?horas=${horas}`, {}, t('Não foi possível carregar as métricas.'))
  },
  obterLimites() { return requisicao('/config/metricas', {}, t('Não foi possível carregar os limites.')) },
  salvarLimites(dados) { return requisicao('/config/metricas', { method: 'PUT', body: JSON.stringify(dados) }, t('Não foi possível salvar os limites.')) },

  // --- Descoberta da rede ---
  iniciarDescoberta(faixa) { return requisicao('/descoberta', { method: 'POST', body: JSON.stringify({ faixa }) }, t('Não foi possível iniciar a varredura.')) },
  statusDescoberta(id) { return requisicao(`/descoberta/${id}`, {}, t('Não foi possível consultar a varredura.')) },
  cancelarDescoberta(id) { return requisicao(`/descoberta/${id}`, { method: 'DELETE' }, t('Não foi possível parar a varredura.')) },

  // --- Manutenção e canais de alerta ---
  iniciarManutencao(projetoId, dados) { return requisicao(`/projetos/${projetoId}/manutencao`, { method: 'POST', body: JSON.stringify(dados) }, t('Não foi possível iniciar a manutenção.')) },
  encerrarManutencao(projetoId, equipamentoId = null) {
    const q = equipamentoId ? `?equipamento_id=${encodeURIComponent(equipamentoId)}` : ''
    return requisicao(`/projetos/${projetoId}/manutencao${q}`, { method: 'DELETE' }, t('Não foi possível encerrar a manutenção.'))
  },
  obterCanais() { return requisicao('/config/alertas', {}, t('Não foi possível carregar os canais de alerta.')) },
  salvarCanais(dados) { return requisicao('/config/alertas', { method: 'PUT', body: JSON.stringify(dados) }, t('Não foi possível salvar os canais de alerta.')) },
  testarCanal(canal) { return requisicao('/config/alertas/teste', { method: 'POST', body: JSON.stringify({ canal }) }, t('Falha ao enviar o teste.')) },

  async login(username, password) {
    const formData = new URLSearchParams();
    formData.append('username', username);
    formData.append('password', password);
    
    let res
    try {
      res = await fetch(`${API_URL}/login`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/x-www-form-urlencoded', 'Accept-Language': getIdioma() },
        body: formData
      });
    } catch (error) {
      throw new Error(t('Não foi possível conectar à API do NetCable: {erro}', { erro: error.message }))
    }
    if (!res.ok) {
      let detail = t('Falha no login (HTTP {status})', { status: res.status })
      try {
        const body = await res.json()
        if (body.detail) detail = body.detail
      } catch (error) {
        // Mantém a mensagem HTTP quando o backend não retorna JSON.
      }
      throw new Error(detail)
    }
    const data = await res.json();
    localStorage.setItem('netcable_token', data.access_token);
    return data;
  },

  // Primeiro acesso: enquanto não houver usuários, a tela de login vira "criar administrador".
  async statusSetup() {
    const res = await fetch(`${API_URL}/setup`, { headers: { 'Accept-Language': getIdioma() } });
    if (!res.ok) throw new Error(t('Falha na comunicação com o servidor.'));
    return res.json();
  },

  async concluirSetup(dados) {
    const res = await fetch(`${API_URL}/setup`, {
      method: 'POST', headers: { 'Content-Type': 'application/json', 'Accept-Language': getIdioma() }, body: JSON.stringify(dados)
    });
    const data = await res.json().catch(() => ({}));
    if (!res.ok) throw new Error(data.detail || t('Falha na comunicação com o servidor.'));
    localStorage.setItem('netcable_token', data.access_token);
    return data;
  },

  async me() {
    const res = await fetch(`${API_URL}/me`, { headers: getHeaders() });
    if (!res.ok) throw new Error('Não autorizado');
    return res.json();
  },

  async atualizarPerfil(dados) {
    const res = await fetch(`${API_URL}/me/perfil`, {
      method: 'PUT', headers: getHeaders(), body: JSON.stringify(dados)
    });
    const data = await res.json();
    if (!res.ok) throw new Error(data.detail || t('Erro ao atualizar perfil.'));
    return data;
  },

  async enviarMeuRelatorio() {
    return requisicao('/me/relatorio/enviar', { method: 'POST' }, t('Falha ao enviar o relatório.'));
  },

  // --- Usuários (admin) ---
  listarUsuarios() { return requisicao('/usuarios', {}, t('Não foi possível listar os usuários.')) },
  criarUsuario(dados) { return requisicao('/usuarios', { method: 'POST', body: JSON.stringify(dados) }, t('Não foi possível criar o usuário.')) },
  atualizarUsuario(id, dados) { return requisicao(`/usuarios/${id}`, { method: 'PUT', body: JSON.stringify(dados) }, t('Não foi possível atualizar o usuário.')) },
  excluirUsuario(id) { return requisicao(`/usuarios/${id}`, { method: 'DELETE' }, t('Não foi possível excluir o usuário.')) },

  // --- E-mail / SMTP (admin) ---
  obterConfigEmail() { return requisicao('/config/email', {}, t('Não foi possível carregar a configuração de e-mail.')) },
  salvarConfigEmail(dados) { return requisicao('/config/email', { method: 'PUT', body: JSON.stringify(dados) }, t('Não foi possível salvar a configuração de e-mail.')) },
  testarEmail(destinatario) { return requisicao('/config/email/teste', { method: 'POST', body: JSON.stringify({ destinatario }) }, t('Falha no envio do e-mail de teste.')) },

  // --- Biblioteca de modelos de equipamento ---
  listarModelos() { return requisicao('/modelos', {}, t('Não foi possível carregar os modelos.')) },
  criarModelo(dados) { return requisicao('/modelos', { method: 'POST', body: JSON.stringify(dados) }, t('Não foi possível criar o modelo.')) },
  atualizarModelo(id, dados) { return requisicao(`/modelos/${id}`, { method: 'PUT', body: JSON.stringify(dados) }, t('Não foi possível salvar o modelo.')) },
  excluirModelo(id) { return requisicao(`/modelos/${id}`, { method: 'DELETE' }, t('Não foi possível excluir o modelo.')) },

  latenciaEquipamento(projetoId, equipamentoId, horas = 24) {
    return requisicao(`/projetos/${projetoId}/equipamentos/${encodeURIComponent(equipamentoId)}/latencia?horas=${horas}`, {}, t('Não foi possível carregar a latência.'))
  },

  logout() {
    localStorage.removeItem('netcable_token');
  },

  isAuthenticated() {
    return !!getToken();
  },

  async ping(ip) {
    const res = await fetch(`${API_URL}/ping/${encodeURIComponent(ip)}`, { headers: getHeaders() });
    if (!res.ok) throw new Error((await res.json().catch(() => ({}))).detail || t('Falha no teste de conexão'));
    return res.json();
  },

  // Status atual dos equipamentos, mantido pelo monitor do backend.
  async statusProjeto(projetoId) {
    const res = await fetch(`${API_URL}/projetos/${projetoId}/status`, { headers: getHeaders() });
    if (!res.ok) throw new Error(t('Não foi possível obter o status dos equipamentos.'));
    return res.json();
  },

  async disponibilidadeProjeto(projetoId, horas = 24) {
    const res = await fetch(`${API_URL}/projetos/${projetoId}/disponibilidade?horas=${horas}`, { headers: getHeaders() });
    const data = await res.json().catch(() => ({}));
    if (!res.ok) throw new Error(data.detail || t('Não foi possível calcular a disponibilidade.'));
    return data;
  },

  async monitor(equipmentId, ip, mode = 'ip', config = null) {
    const res = await fetch(`${API_URL}/monitor`, {
      method: 'POST', headers: getHeaders(),
      body: JSON.stringify({ equipmentId, ip, mode, config })
    });
    if (!res.ok) throw new Error((await res.json()).detail || t('Falha no monitoramento'));
    return res.json();
  },

  async discoverNeighbors(ip, config) {
    const res = await fetch(`${API_URL}/discovery/neighbors`, {
      method: 'POST', headers: getHeaders(), body: JSON.stringify({ ip, config })
    });
    if (!res.ok) throw new Error((await res.json()).detail || t('Falha na descoberta'));
    return res.json();
  },
  
  async listarProjetos() {
    const res = await fetch(`${API_URL}/projetos`, { headers: getHeaders() });
    if (res.status === 401) throw new Error('Não autorizado');
    return res.json();
  },
  
  criarProjeto(nome) {
    return requisicao(`/projetos?nome=${encodeURIComponent(nome)}`, { method: 'POST' }, t('Não foi possível criar o projeto.'))
  },

  editarNomeProjeto(id, novoNome) {
    return requisicao(`/projetos/${id}?novo_nome=${encodeURIComponent(novoNome)}`, { method: 'PUT' }, t('Não foi possível renomear o projeto.'))
  },
  
  async salvarMapa(projetoId, equipamentos, conexoes) {
    const res = await fetch(`${API_URL}/projetos/${projetoId}/salvar`, {
      method: 'POST',
      headers: getHeaders(),
      body: JSON.stringify({ equipamentos, conexoes })
    });
    if (!res.ok) {
      const data = await res.json().catch(() => ({}));
      throw new Error(data.detail || t('Erro ao salvar o mapa.'));
    }
    return true;
  },
  
  async obterProjeto(projetoId) {
    const res = await fetch(`${API_URL}/projetos/${projetoId}/dados`, { headers: getHeaders() });
    const data = await res.json();
    if (!res.ok) throw new Error(data.detail || t('Projeto não encontrado'));
    return data;
  },

  // Visualização pública: acessa o mapa pelo token do link (sem login).
  async obterMapaPublico(token) {
    const res = await fetch(`${API_URL}/public/mapas/${encodeURIComponent(token)}/dados`, { headers: { 'Accept-Language': getIdioma() } });
    const data = await res.json().catch(() => ({}));
    if (!res.ok) {
      const err = new Error(data.detail || t('Link inválido ou revogado'));
      err.status = res.status;
      throw err;
    }
    return data;
  },

  async gerarLinkPublico(projetoId, regenerar = false) {
    const res = await fetch(`${API_URL}/projetos/${projetoId}/compartilhar?regenerar=${regenerar}`, { method: 'POST', headers: getHeaders() });
    const data = await res.json().catch(() => ({}));
    if (!res.ok) throw new Error(data.detail || t('Não foi possível gerar o link público.'));
    return data.token;
  },

  async revogarLinkPublico(projetoId) {
    const res = await fetch(`${API_URL}/projetos/${projetoId}/compartilhar`, { method: 'DELETE', headers: getHeaders() });
    if (!res.ok) throw new Error(t('Não foi possível revogar o link público.'));
    return true;
  },
  
  async deletarProjeto(projetoId) {
    const res = await fetch(`${API_URL}/projetos/${projetoId}`, { method: 'DELETE', headers: getHeaders() });
    return res.ok;
  },

  async health() {
    const res = await fetch(`${API_URL}/health`);
    if (!res.ok) throw new Error(t('API indisponível (HTTP {status})', { status: res.status }));
    return res.json();
  },

  async historicoProjeto(projetoId, limite = 100) {
    const res = await fetch(`${API_URL}/projetos/${projetoId}/historico?limite=${limite}`, { headers: getHeaders() });
    const data = await res.json();
    if (!res.ok) throw new Error(data.detail || t('Não foi possível carregar o histórico.'));
    return data;
  }
};
