🌐 NetCable — Mapeador Visual de Rede (BETA)

![Status](https://img.shields.io/badge/Status-BETA-blue)
![License](https://img.shields.io/badge/License-MIT-green)
![Python](https://img.shields.io/badge/Python-3.11-yellow)
![React](https://img.shields.io/badge/React-18-blue)

<img width="1080" height="602" alt="image" src="https://github.com/user-attachments/assets/792717d9-2239-4b9a-9959-fdead1927bb7" />

<img width="1678" height="894" alt="netcable2" src="https://github.com/user-attachments/assets/1267e35c-83bc-4099-a174-ea4889ac81d1" />

<img width="1678" height="894" alt="netcable2" src="https://github.com/user-attachments/assets/8c297d1f-fed7-4df8-8d4c-0ecd2af1c5fa" />




O NetCable é uma ferramenta open-source e self-hosted para mapear e monitorar sua rede em tempo real. Crie diagramas visuais arrastando e soltando equipamentos, conecte-os com cabos virtuais e acompanhe o status de cada dispositivo com alertas em tempo real.

⚠️ Este projeto está em fase BETA e em desenvolvimento ativo. Funcionalidades podem mudar, bugs podem aparecer e várias melhorias estão planejadas (veja a seção Roadmap). Feedbacks e contribuições são bem-vindos.

✨ Funcionalidades
🔐 Login seguro — autenticação via JWT

👥 Equipe com papéis — Administrador (tudo + usuários e e-mail), Editor (edita mapas) e Visualizador (só vê, ideal para TV do NOC); todos enxergam os mesmos mapas

🎨 Mapeamento visual — crie diagramas de rede arrastando ícones e puxando linhas (cabos)

🗄️ Racks com equipamentos em formato real — monte switches, servidores, storage, patch panels, nobreaks e organizadores em racks de 4U a 48U; arraste para encaixar por U e conecte os cabos normalmente

📡 Monitoramento contínuo no servidor — testa cada equipamento via TCP (portas 80, 443, 22), ICMP (ping) ou SNMPv3, mesmo sem nenhum navegador aberto

🚨 Alertas em tempo real — bolinhas verdes/vermelhas, efeito cascata (amarelo), alerta sonoro e notificações por **e-mail**, **Telegram** ou webhook (queda e recuperação), com opção de ligar/desligar por equipamento

📧 Relatório diário por e-mail — cada usuário escolhe o horário e recebe a disponibilidade, quedas e eventos das últimas 24 h

📊 Disponibilidade e latência — uptime %, quedas, latência média e gráfico de latência por equipamento (24 h / 7 dias / 30 dias)

🔗 Link público — compartilhe o diagrama em modo somente leitura, com link secreto revogável e atualização automática

📺 Modo visualização / TV de NOC — esconde os pontos de conexão e trava a edição, com tela cheia na página pública

💾 Exportar/Importar JSON — faça backup e restaure seu diagrama facilmente

## 🔧 Atualizações recentes

✅ **Biblioteca de modelos de equipamento** — em ⚙️ → Modelos de equipamento, cadastre seus equipamentos reais (ex.: "Grandstream GWN7003": firewall 1U, 4 RJ45 + 2 SFP, portas "eth1…eth4") com prévia ao vivo. Ao adicionar um equipamento, escolha o modelo e a frente no rack é desenhada com exatamente essas portas.

✅ **Cabos porta a porta** — no rack, arraste de uma porta até outra (ex.: porta 12 do switch → eth3 do firewall). O cabo sai da própria porta, a porta fica marcada como em uso e o tooltip mostra para onde ela vai. No modal do cabo também dá para escolher as portas numa lista; uma porta não aceita dois cabos.

✅ **Racks em formato real** — adicione um *Rack* (4U a 48U) e monte os equipamentos nele: cada tipo tem a frente desenhada como o equipamento real (portas RJ45/SFP com LEDs, baias de disco, display do nobreak/firewall...). Arraste um equipamento do mapa para dentro do rack e ele encaixa no U mais próximo; dentro do rack ele só se move na vertical, encaixando nos U livres. Também dá para escolher rack, altura (1U, 2U, 4U...) e posição ao adicionar ou editar. O servidor recusa sobreposições ao salvar.

✅ **Vários usuários com papéis** — o admin cria usuários em ⚙️ → Usuários e define o papel de cada um (Administrador, Editor ou Visualizador). O Visualizador abre os mapas já em modo somente leitura. O usuário de `ADMIN_USER` é sempre mantido como admin ativo (serve para recuperar o acesso).

✅ **Notificações por e-mail** — o admin configura o servidor SMTP em ⚙️ → E-mail (SMTP) (atalhos para Gmail/Outlook/Office 365 e botão "Salvar e testar"); a senha fica cifrada no banco. Cada usuário escolhe no perfil se recebe os alertas de queda/recuperação.

✅ **Relatório diário** — cada usuário define o horário (ex.: 07:30) e recebe por e-mail o resumo das últimas 24 h: disponibilidade, quedas, latência média e a lista de eventos. Há um botão "Enviar agora" para testar.

✅ **Notificação por equipamento** — opção "Notificar quando cair ou voltar" em cada equipamento (impressoras, PCs etc. podem cair sem gerar alerta). Equipamentos com a notificação desligada mostram um sino riscado no mapa.

✅ **Gráfico de latência** — ⚙️ → Histórico → Latência (ou clique no equipamento na aba Disponibilidade): linha de latência, períodos offline destacados, média/mín/p95/máx e alternativa em tabela.

✅ **Alertas agrupados** — se vários equipamentos caem no mesmo ciclo, é enviado um único e-mail/mensagem com todos eles.

✅ **Monitoramento centralizado** — o servidor verifica todos os equipamentos (padrão a cada 15 s, `MONITOR_INTERVAL`) e o editor apenas lê o resultado. Antes, cada navegador aberto pingava todos os equipamentos a cada 5 s.

✅ **Menos alarmes falsos** — um equipamento só é marcado offline após 2 falhas seguidas (`MONITOR_FAILURE_THRESHOLD`).

✅ **Alertas no Telegram** — configure `TELEGRAM_BOT_TOKEN` e `TELEGRAM_CHAT_ID` e receba avisos de queda e de recuperação. O webhook (`ALERT_WEBHOOK_URL`) também passou a avisar a recuperação.

✅ **Relatório de disponibilidade** — no menu ⚙️ → Histórico: uptime %, quedas e latência média por equipamento; a aba de eventos agora mostra o nome do equipamento e o horário no fuso correto.

✅ **Histórico com retenção** — registros mais antigos que `HISTORY_RETENTION_DAYS` (padrão 30) são apagados automaticamente; excluir um projeto também apaga o histórico dele.

✅ **Aviso de alterações não salvas** — o botão Salvar fica laranja quando há mudanças, o navegador avisa antes de sair e `Ctrl+S` salva o mapa.

✅ **Painel de projetos** — cada projeto mostra quantos equipamentos estão online/offline e se tem link público ativo.

✅ **Docker mais robusto** — healthcheck no backend, frontend só sobe depois da API estar saudável, build com Node 20 e `.dockerignore` (a imagem não leva mais banco local nem venv).

✅ **Correção (segurança): `/api/ping` exigia login** — antes qualquer pessoa com acesso ao NetCable podia usá-lo para varrer portas da rede interna.

✅ **Correção: salvar mapa com equipamento SNMPv3** — retornava erro 500; as senhas SNMP existentes agora são preservadas ao salvar.

✅ **Modo visualização (somente leitura)** — botão no editor que esconde os pontos de conexão e bloqueia edições, ideal para telas de NOC.

✅ **Link público mais seguro** — o link agora usa um token aleatório (não mais o ID do projeto) e pode ser regenerado ou revogado. Links antigos no formato `/share/<id>` deixam de funcionar: gere um novo pelo menu ⚙️.

✅ **Página pública para TV** — atualização automática a cada 10 s, indicador da última atualização e botão de tela cheia.

✅ **Correção: copiar link público em HTTP** — o botão agora funciona ao acessar o NetCable por `http://IP` (homelab), sem exigir HTTPS.

✅ **Correção: alertas por webhook** — o envio para `ALERT_WEBHOOK_URL` não estava sendo realizado.

O NetCable recebeu uma primeira evolução no monitoramento e na integração com redes reais:

✅ **Método de monitoramento por equipamento** — escolha entre IP/ICMP + TCP, SNMPv3 ou modo somente visual.

✅ **Suporte inicial a SNMPv3** — autenticação MD5/SHA, privacidade AES/DES, teste de conexão e porta SNMP configurável.

✅ **Descoberta de vizinhos LLDP/CDP** — consulta as tabelas de vizinhança disponibilizadas pelo equipamento via SNMP.

✅ **Proteção das credenciais** — configurações SNMP são cifradas no backend e as senhas não são incluídas nos backups JSON.

✅ **Diagnóstico da instalação** — nova verificação da API, banco de dados, caminho do SQLite e disponibilidade do PySNMP.

✅ **Comunicação simplificada** — o frontend usa o caminho `/api`, com proxy no Vite e no Nginx. Usuários não precisam configurar ou conhecer a porta interna do backend.

✅ **Mensagens de erro mais claras** — falhas de conexão, API e monitoramento agora são exibidas com mais detalhes.

✅ **Projetos separados por usuário** — cada usuário autenticado só acessa os próprios mapas.

✅ **Configuração mais segura** — chave JWT, CORS e credenciais administrativas podem ser definidos por ambiente, com proteção contra tentativas repetidas de login.

✅ **Backups validados** — arquivos JSON muito grandes ou fora do formato esperado são rejeitados antes de alterar o mapa.

✅ **Diagnóstico ampliado** — a tela de diagnóstico informa a versão da API e alerta configurações inseguras.

✅ **Compatibilidade com bancos existentes** — novas configurações de monitoramento são adicionadas automaticamente sem apagar os projetos atuais.

Esses recursos estão em validação com switches, firewalls e outros equipamentos reais. A criação automática de nós e conexões a partir da descoberta, além da coleta detalhada de interfaces, CPU e memória, permanece planejada para as próximas versões.

🚀 Como Rodar (Docker — recomendado)
A forma mais simples de rodar o NetCable é via Docker Compose, em qualquer máquina com Docker instalado (VPS, mini PC, Raspberry Pi, VM, PC de laboratório etc.).

bash
git clone https://github.com/Joao-Monticelli/NetCable-v1.git
cd NetCable-v1
# edite o docker-compose.yml com usuário, senha, chave secreta e caminho dos dados
docker compose up -d
Depois acesse `http://localhost` no navegador. A porta 8000 do backend é
interna e não precisa ser publicada no host; a API e sua documentação ficam
acessíveis pelo frontend em `/api` e `/docs`.

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
□ Notificações por e-mail e Discord
□ Suporte a PostgreSQL como alternativa ao SQLite
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
