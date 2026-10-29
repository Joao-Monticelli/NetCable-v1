🌐 NetCable — Mapeador Visual de Rede (BETA)

![Status](https://img.shields.io/badge/Status-BETA-blue)
![License](https://img.shields.io/badge/License-MIT-green)
![Python](https://img.shields.io/badge/Python-3.11-yellow)
![React](https://img.shields.io/badge/React-18-blue)


O NetCable é uma ferramenta open-source e self-hosted para mapear e monitorar sua rede em tempo real. Crie diagramas visuais arrastando e soltando equipamentos, conecte-os com cabos virtuais e acompanhe o status de cada dispositivo com alertas em tempo real.

⚠️ Este projeto está em fase BETA e em desenvolvimento ativo. Funcionalidades podem mudar, bugs podem aparecer e várias melhorias estão planejadas (veja a seção Roadmap). Feedbacks e contribuições são bem-vindos.

✨ Funcionalidades
🔐 Login seguro — autenticação via JWT

🎨 Mapeamento visual — crie diagramas de rede arrastando ícones e puxando linhas (cabos)

📡 Monitoramento inteligente — testa cada equipamento usando TCP (portas 80, 443, 22) e ICMP (ping)

🚨 Alertas em tempo real — bolinhas verdes/vermelhas, efeito cascata (amarelo) e alerta sonoro

🔗 Link público — compartilhe o diagrama em modo somente leitura

💾 Exportar/Importar JSON — faça backup e restaure seu diagrama facilmente

🚀 Como Rodar (Docker — recomendado)
A forma mais simples de rodar o NetCable é via Docker Compose, em qualquer máquina com Docker instalado (VPS, mini PC, Raspberry Pi, VM, PC de laboratório etc.).

bash
git clone https://github.com/Joao-Monticelli/NetCable-v1.git
cd NetCable-v1
# edite o docker-compose.yml com usuário, senha e caminho dos dados
docker compose up -d
Depois acesse http://localhost:<porta> no navegador.

💡 O NetCable não exige TrueNAS. Ele roda em qualquer ambiente com Docker. O TrueNAS é apenas uma das formas de hospedar — veja abaixo.

🖥️ Opção: Instalar no TrueNAS (Custom App)
Se você já usa TrueNAS SCALE e quer rodar o NetCable junto aos seus apps:

Baixe o arquivo YAML de instalação: install/trueNAS.yml

No TrueNAS, vá em Apps → Custom App → Install via YAML

Cole o conteúdo do YAML e edite usuário, senha e o caminho do pool

Clique em Install

Para o passo a passo detalhado, veja o INSTALL.md.

⚠️ Nota: o NetCable é um app de rede, não um app de storage. Ele roda bem no TrueNAS, mas o TrueNAS não é obrigatório — use a opção Docker acima se preferir simplicidade.

🛠️ Tecnologias Utilizadas
Frontend: React, Vite, React Flow, Lucide React, React Hot Toast

Backend: Python, FastAPI, SQLAlchemy, SQLite, Ping3

Infraestrutura: Docker, Docker Compose, GitHub Actions, GitHub Container Registry (GHCR)

🗺️ Roadmap
O projeto está em beta e as seguintes melhorias estão planejadas:

□ Suporte a múltiplos usuários e permissões
□ Histórico de status dos dispositivos (uptime/downtime)
□ Notificações externas (e-mail, webhook, Telegram/Discord)
□ Suporte a PostgreSQL como alternativa ao SQLite
□ Melhorias de performance no monitoramento (fila/agendamento)
□ Testes automatizados (backend e frontend)
□ Documentação de API (OpenAPI/Swagger)
□ Temas claro/escuro
□ Internacionalização (pt-BR / en)
Sugestões de funcionalidades são bem-vindas via Issues.

🤝 Contribuindo
Contribuições são muito bem-vindas! Sinta-se à vontade para abrir Issues com bugs, sugestões ou dúvidas, e Pull Requests com melhorias.

📄 Licença
Este projeto está sob a licença MIT. Sinta-se livre para usar, modificar e contribuir.

🔍 O que mudou em relação ao README atual
Docker como opção principal — o README antigo abria direto com "Como Instalar (TrueNAS)", o que fazia o projeto parecer um app de storage. Agora o Docker é o caminho padrão e o TrueNAS é uma opção entre outras.

Aviso de beta + Roadmap — deixa explícito que o projeto está em evolução, reduzindo críticas do tipo "isso não está pronto".

Nota de que o TrueNAS é opcional — antecipa a crítica mais comum de comunidades de storage.

Seção de contribuição — abre espaço para feedback construtivo.

Roadmap com melhorias reais — mostra direção e maturidade.

Sugestões de melhorias futuras (para depois)
Screenshots/GIF do diagrama funcionando — isso aumenta muito o engajamento em qualquer comunidade.

Badges no topo (build status, licença, versão) — dá aparência profissional.

Seção "Por que NetCable?" — um parágrafo curto explicando o problema que ele resolve (mapear rede visualmente sem ferramentas pagas).

- **Frontend:** React, Vite, React Flow, Lucide React, React Hot Toast.
- **Backend:** Python, FastAPI, SQLAlchemy, SQLite, Ping3.
- **Infraestrutura:** Docker, GitHub Actions, GitHub Container Registry (GHCR).

---

## 📄 Licença
Este projeto está sob a licença MIT. Sinta-se livre para contribuir e usar.

---
*Documento gerado e mantido pela equipe NetCable.*
