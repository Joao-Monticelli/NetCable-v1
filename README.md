# 🌐 NetCable - Mapeador Visual de Rede (BETA)

![Status](https://img.shields.io/badge/Status-BETA-blue)
![License](https://img.shields.io/badge/License-MIT-green)
![Python](https://img.shields.io/badge/Python-3.11-yellow)
![React](https://img.shields.io/badge/React-18-blue)

O **NetCable** é uma ferramenta open-source para mapear e monitorar sua rede em tempo real. Crie diagramas visuais (arrastando e soltando equipamentos), conecte-os com cabos virtuais e acompanhe o status de cada dispositivo.

> ⚠️ **Este projeto está em fase BETA.** Novas funcionalidades e correções estão sendo adicionadas constantemente.

<!-- ========================================== -->
<!-- 👇 COLE A SUA IMAGEM AQUI NO GITHUB 👇 -->
<!-- ========================================== -->

---

## ✨ Funcionalidades

- **🔐 Login Seguro:** Autenticação via JWT.
- **🎨 Mapeamento Visual:** Crie diagramas de rede arrastando ícones e puxando linhas (cabos).
- **📡 Monitoramento Inteligente:** Testa cada equipamento usando **TCP** (portas 80, 443, 22) e **ICMP** (ping).
- **🚨 Alertas em Tempo Real:** Bolinhas verdes/vermelhas, efeito cascata (amarelo) e alerta sonoro.
- **🔗 Link Público:** Compartilhe o diagrama em modo somente leitura.
- **💾 Exportar/Importar JSON:** Faça backup do seu diagrama.

---

## 🚀 Como Instalar (TrueNAS)

O NetCable é instalado no **TrueNAS** via Docker (Custom App). O processo é simples:

1. **Baixe o arquivo YAML de instalação:** 
   👉 **[Clique aqui para baixar o arquivo `trueNAS.yml`](install/trueNAS.yml)**
2. **No TrueNAS**, vá em **Apps** > **Custom App** > **Install via YAML**.
3. **Cole o conteúdo** do YAML e edite os dados de **usuário**, **senha** e o **caminho do seu pool**.
4. Clique em **Install**.

Para um guia detalhado com todos os passos, acesse o **[Guia de Instalação Passo a Passo (INSTALL.md)](INSTALL.md)**.

---

## 🛠️ Tecnologias Utilizadas

- **Frontend:** React, Vite, React Flow, Lucide React, React Hot Toast.
- **Backend:** Python, FastAPI, SQLAlchemy, SQLite, Ping3.
- **Infraestrutura:** Docker, GitHub Actions, GitHub Container Registry (GHCR).

---

## 📄 Licença
Este projeto está sob a licença MIT. Sinta-se livre para contribuir e usar.

---
*Documento gerado e mantido pela equipe NetCable.*
