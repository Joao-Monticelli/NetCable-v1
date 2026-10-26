const currentHost = window.location.hostname;
const BACKEND_URL = `http://${currentHost}:8000`;

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
    
    const res = await fetch(`${BACKEND_URL}/api/login`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/x-www-form-urlencoded' },
      body: formData
    });
    if (!res.ok) throw new Error('Login falhou');
    const data = await res.json();
    localStorage.setItem('netcable_token', data.access_token);
    return data;
  },

  logout() {
    localStorage.removeItem('netcable_token');
  },

  isAuthenticated() {
    return !!getToken();
  },

  async ping(ip) {
    const res = await fetch(`${BACKEND_URL}/api/ping/${ip}`);
    return res.json();
  },
  
  async listarProjetos() {
    const res = await fetch(`${BACKEND_URL}/api/projetos`, { headers: getHeaders() });
    if (res.status === 401) throw new Error('Não autorizado');
    return res.json();
  },
  
  async criarProjeto(nome) {
    const res = await fetch(`${BACKEND_URL}/api/projetos?nome=${encodeURIComponent(nome)}`, { method: 'POST', headers: getHeaders() });
    return res.json();
  },

  async editarNomeProjeto(id, novoNome) {
    const res = await fetch(`${BACKEND_URL}/api/projetos/${id}?novo_nome=${encodeURIComponent(novoNome)}`, { method: 'PUT', headers: getHeaders() });
    return res.json();
  },
  
  async salvarMapa(projetoId, equipamentos, conexoes) {
    const res = await fetch(`${BACKEND_URL}/api/projetos/${projetoId}/salvar`, {
      method: 'POST',
      headers: getHeaders(),
      body: JSON.stringify({ equipamentos, conexoes })
    });
    return res.ok;
  },
  
  async obterProjeto(projetoId) {
    const res = await fetch(`${BACKEND_URL}/api/projetos/${projetoId}/dados`);
    return res.json();
  },
  
  async deletarProjeto(projetoId) {
    const res = await fetch(`${BACKEND_URL}/api/projetos/${projetoId}`, { method: 'DELETE', headers: getHeaders() });
    return res.ok;
  }
};