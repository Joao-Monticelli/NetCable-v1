// Em produção e no desenvolvimento o frontend usa o mesmo host do backend
// através de proxy. VITE_API_URL continua disponível para instalações externas.
const API_BASE_URL = import.meta.env.VITE_API_URL || '';
const API_URL = `${API_BASE_URL}/api`;

// Pega o token salvo no navegador
const getToken = () => localStorage.getItem('netcable_token');

// Função genérica para headers
const getHeaders = () => ({
  'Content-Type': 'application/json',
  'Authorization': `Bearer ${getToken()}`
});

export const api = {
  async login(username, password) {
    const formData = new URLSearchParams();
    formData.append('username', username);
    formData.append('password', password);
    
    let res
    try {
      res = await fetch(`${API_URL}/login`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/x-www-form-urlencoded' },
        body: formData
      });
    } catch (error) {
      throw new Error(`Não foi possível conectar à API do NetCable: ${error.message}`)
    }
    if (!res.ok) {
      let detail = `Falha no login (HTTP ${res.status})`
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
    if (!res.ok) throw new Error(data.detail || 'Erro ao atualizar perfil.');
    return data;
  },

  logout() {
    localStorage.removeItem('netcable_token');
  },

  isAuthenticated() {
    return !!getToken();
  },

  async ping(ip) {
    const res = await fetch(`${API_URL}/ping/${encodeURIComponent(ip)}`);
    return res.json();
  },

  async monitor(equipmentId, ip, mode = 'ip', config = null) {
    const res = await fetch(`${API_URL}/monitor`, {
      method: 'POST', headers: getHeaders(),
      body: JSON.stringify({ equipmentId, ip, mode, config })
    });
    if (!res.ok) throw new Error((await res.json()).detail || 'Falha no monitoramento');
    return res.json();
  },

  async discoverNeighbors(ip, config) {
    const res = await fetch(`${API_URL}/discovery/neighbors`, {
      method: 'POST', headers: getHeaders(), body: JSON.stringify({ ip, config })
    });
    if (!res.ok) throw new Error((await res.json()).detail || 'Falha na descoberta');
    return res.json();
  },
  
  async listarProjetos() {
    const res = await fetch(`${API_URL}/projetos`, { headers: getHeaders() });
    if (res.status === 401) throw new Error('Não autorizado');
    return res.json();
  },
  
  async criarProjeto(nome) {
    const res = await fetch(`${API_URL}/projetos?nome=${encodeURIComponent(nome)}`, { method: 'POST', headers: getHeaders() });
    return res.json();
  },

  async editarNomeProjeto(id, novoNome) {
    const res = await fetch(`${API_URL}/projetos/${id}?novo_nome=${encodeURIComponent(novoNome)}`, { method: 'PUT', headers: getHeaders() });
    return res.json();
  },
  
  async salvarMapa(projetoId, equipamentos, conexoes) {
    const res = await fetch(`${API_URL}/projetos/${projetoId}/salvar`, {
      method: 'POST',
      headers: getHeaders(),
      body: JSON.stringify({ equipamentos, conexoes })
    });
    if (!res.ok) {
      const data = await res.json().catch(() => ({}));
      throw new Error(data.detail || 'Erro ao salvar o mapa.');
    }
    return true;
  },
  
  async obterProjeto(projetoId, publico = false) {
    const endpoint = publico
      ? `${API_URL}/public/projetos/${projetoId}/dados`
      : `${API_URL}/projetos/${projetoId}/dados`;
    const res = await fetch(endpoint, { headers: publico ? {} : getHeaders() });
    const data = await res.json();
    if (!res.ok) throw new Error(data.detail || 'Projeto não encontrado');
    return data;
  },
  
  async deletarProjeto(projetoId) {
    const res = await fetch(`${API_URL}/projetos/${projetoId}`, { method: 'DELETE', headers: getHeaders() });
    return res.ok;
  },

  async health() {
    const res = await fetch(`${API_URL}/health`);
    if (!res.ok) throw new Error(`API indisponível (HTTP ${res.status})`);
    return res.json();
  },

  async historicoProjeto(projetoId, limite = 100) {
    const res = await fetch(`${API_URL}/projetos/${projetoId}/historico?limite=${limite}`, { headers: getHeaders() });
    const data = await res.json();
    if (!res.ok) throw new Error(data.detail || 'Não foi possível carregar o histórico.');
    return data;
  }
};
