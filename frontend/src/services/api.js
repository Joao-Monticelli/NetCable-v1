// Descobre o IP/Hostname atual onde o Frontend está rodando
const currentHost = window.location.hostname;

// Se estiver rodando local, usa 127.0.0.1. Se estiver na rede, usa o IP.
const BACKEND_URL = `http://${currentHost}:8000`;

export const api = {
  async ping(ip) {
    const res = await fetch(`${BACKEND_URL}/api/ping/${ip}`);
    return res.json();
  },
  
  async listarProjetos() {
    const res = await fetch(`${BACKEND_URL}/api/projetos`);
    return res.json();
  },
  
  async criarProjeto(nome) {
    const res = await fetch(`${BACKEND_URL}/api/projetos?nome=${encodeURIComponent(nome)}`, { method: 'POST' });
    return res.json();
  },
  
  async salvarMapa(projetoId, equipamentos, conexoes) {
    const res = await fetch(`${BACKEND_URL}/api/projetos/${projetoId}/salvar`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ equipamentos, conexoes })
    });
    return res.ok;
  },
  
  async obterProjeto(projetoId) {
    const res = await fetch(`${BACKEND_URL}/api/projetos/${projetoId}/dados`);
    return res.json();
  },
  
  async deletarProjeto(projetoId) {
    const res = await fetch(`${BACKEND_URL}/api/projetos/${projetoId}`, { method: 'DELETE' });
    return res.ok;
  }
};