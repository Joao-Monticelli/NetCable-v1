# 🗺️ Mapa Estrutural do NetCable

Este documento detalha a função de cada arquivo do Frontend para facilitar a manutenção e o contexto em novas sessões de desenvolvimento.

## 📂 Raiz do Projeto
- `README.md`: Documentação principal, histórico de funcionalidades e guia de instalação.
- `ESTRUTURA_E_CODIGO.md`: Este arquivo. Mapeia a função de cada arquivo.
- `docker-compose.yml`: (A ser criado) Orquestração dos containers do Frontend e Backend.
- `.gitignore`: Arquivos que não devem ser enviados ao GitHub (node_modules, venv, etc).

## 📂 Pasta `frontend/`
Configurações básicas do Vite e React.
- `package.json`: Lista de dependências (React, React Flow, Lucide, Router).
- `vite.config.js`: Configuração do servidor de desenvolvimento.
- `index.html`: Página HTML raiz onde o React é injetado.

## 📂 Pasta `frontend/src/`
Coração do Frontend.
- `main.jsx`: Ponto de entrada. Renderiza o React e importa o CSS global.
- `index.css`: Estilos globais, animações de status (pulse-green, pulse-red) e estilos dos nós.
- `App.jsx`: Define as rotas (BrowserRouter). Rotas atuais: `/` (Login), `/projects` (Projetos), `/editor/:id` (Editor).

### 📂 Pasta `frontend/src/pages/`
Telas principais do sistema.
- `Login.jsx`: Tela inicial de autenticação (atualmente simulada, sem backend).
- `Projects.jsx`: Tela que lista os projetos do usuário e permite criar um novo.
- `Editor.jsx`: Tela do diagrama. Contém a barra superior (Adicionar, Salvar, Configurações) e renderiza o `NetworkMap`.

### 📂 Pasta `frontend/src/components/`
Componentes reutilizáveis e lógicas complexas.
- `NetworkMap.jsx`: **O arquivo mais importante.** Contém o React Flow, a definição do `CustomNode` (aparência dos equipamentos), a lógica de criar conexões coloridas, redimensionamento e os modais.

#### 📂 Pasta `frontend/src/components/Modals/`
Janelas pop-up de interação.
- `AddEquipmentModal.jsx`: Formulário para adicionar um novo equipamento (Nome, IP, Tipo, Checkbox "Sem IP").
- `EquipmentModal.jsx`: Formulário para editar um nó já existente (Mudar Nome, IP, Tipo, Excluir nó).
- `EdgeModal.jsx`: Formulário para editar uma conexão (Mudar Rótulo, trocar Origem/Destino, Excluir cabo).

## 📂 Pasta `backend/` (Aguardando Fase 2)
- `app/`: Onde ficará o código Python (FastAPI).
- `requirements.txt`: Dependências do Python.
- `Dockerfile`: Receita para criar a imagem Docker do backend.