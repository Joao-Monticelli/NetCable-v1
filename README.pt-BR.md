# NetCable — mapa e monitoramento de rede self-hosted

![Status](https://img.shields.io/badge/status-beta-blue)
![License](https://img.shields.io/badge/license-MIT-green)
![Docker](https://img.shields.io/badge/docker-amd64%20%7C%20arm64-2496ED)

[English](README.md) · **Português**

<img width="1080" alt="Mapa do NetCable" src="https://github.com/user-attachments/assets/792717d9-2239-4b9a-9959-fdead1927bb7" />

O NetCable é uma ferramenta open source e self-hosted para **desenhar a sua rede e ficar de olho nela**.
Arraste equipamentos para o mapa, monte racks com cara de equipamento real, ligue cabos porta a porta,
e o NetCable monitora tudo em segundo plano e avisa (e-mail, Telegram, webhook) quando algo cai.

Roda em **um único container Docker** em qualquer lugar: mini PC, VM, NAS, Raspberry Pi.

> ⚠️ Beta: em desenvolvimento ativo. Feedbacks e issues são muito bem-vindos.

## Funcionalidades

- 🗺️ **Mapa visual** — arrastar e soltar, cabos com rótulo, busca (`Ctrl+K`) e destaque ao passar o mouse.
- 🗄️ **Racks realistas** — de 4U a 48U; switches, servidores, NAS, patch panels, nobreaks… encaixando por U.
- 🧩 **Biblioteca de modelos** — cadastre seus equipamentos reais (ex.: “4 RJ45 + 2 SFP, 1U”) e a frente é desenhada com essas portas.
- 🔌 **Cabos porta a porta** — porta 12 do switch → eth3 do firewall; portas em uso ficam marcadas.
- 📡 **Monitoramento no servidor** — TCP (80/443/22) + ICMP em paralelo, ou SNMPv3; funciona sem navegador aberto.
- 🚨 **Alertas** — e-mail, Telegram e webhook na queda e na volta, agrupados, com liga/desliga por equipamento.
- 📊 **Disponibilidade e latência** — uptime %, quedas, gráfico de latência (24 h / 7 d / 30 d) e relatório diário por e-mail.
- 👥 **Equipe com papéis** — Administrador, Editor e Visualizador (ótimo para a TV do NOC).
- 📺 **Link público e modo TV** — somente leitura, atualização automática, tela cheia e link revogável.
- 💾 **Backups** — `.zip` diário (todos os mapas + catálogo de modelos + banco completo) numa pasta à sua escolha; exportar/importar mapas em JSON.
- 🌐 **English / Português** — por usuário; vale também para e-mails e mensagens de erro.

## Instalação rápida (Docker)

```yaml
# docker-compose.yml
services:
  netcable:
    image: ghcr.io/joao-monticelli/netcable:latest
    container_name: netcable
    restart: unless-stopped
    ports:
      - "8080:8080"
    volumes:
      - ./data:/app/data      # banco, chave secreta e backups
    environment:
      - TZ=America/Sao_Paulo
```

```bash
docker compose up -d
```

Acesse `http://IP-DO-SERVIDOR:8080`. No primeiro acesso o NetCable pede para **criar a conta de administrador** —
não há senha padrão. A chave secreta é gerada automaticamente na pasta de dados.

Imagens para **amd64** e **arm64** (Raspberry Pi 4/5). Para atualizar de forma controlada, fixe uma versão:
`ghcr.io/joao-monticelli/netcable:1.0.0`.

**TrueNAS SCALE:** Apps → Discover Apps → Custom App → *Install via YAML* e cole o [`install/trueNAS.yml`](install/trueNAS.yml)
(ajuste o caminho do pool). Passo a passo no [INSTALL.md](INSTALL.md).

## Configuração

Tudo é opcional. E-mail (SMTP), usuários, backup e idioma ficam na interface (menu ⚙️). As variáveis de
ambiente estão na tabela do [README em inglês](README.md#configuration) e comentadas no `docker-compose.yml`.

## Backup e restauração

- ⚙️ → **Backup** (admin): horário diário, quantos arquivos manter, pasta de destino e botão *Fazer backup agora*.
  No Docker a pasta precisa estar dentro de um volume montado (padrão `/app/data/backups`; monte outro volume para mandar para o seu NAS).
- Cada `.zip` tem o `netcable.db` (tudo: usuários, histórico, configurações), um JSON por mapa e o catálogo de modelos.
- **Recuperar mapas:** na tela de projetos clique em **Importar** e escolha o `.zip` (ou um `.json` de mapa). Importar sempre cria projetos novos; nada é sobrescrito.
- **Recuperar tudo:** pare o container e troque `data/netcable.db` pelo que está dentro do `.zip`.

Antes de qualquer atualização do banco, uma cópia é salva automaticamente em `data/backups/`.

## Atualizar

```bash
docker compose pull && docker compose up -d
```

As migrações do banco rodam sozinhas. Vindo da instalação antiga com dois containers
(`netcable-backend` + `netcable-frontend`)? Troque o compose pela imagem única acima mantendo a mesma pasta de dados em `/app/data`.

## Desenvolvimento

Veja a seção *Development* do [README em inglês](README.md#development). O que mudou em cada versão está no [CHANGELOG](CHANGELOG.md).

## Licença

MIT
