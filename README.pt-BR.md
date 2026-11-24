# NetCable — mapa e monitoramento de rede self-hosted

![Status](https://img.shields.io/badge/status-beta-blue)
![License](https://img.shields.io/badge/license-MIT-green)
![Docker](https://img.shields.io/badge/docker-amd64%20%7C%20arm64-2496ED)

[English](README.md) · **Português**
<img width="1920" alt="NetCable" src="https://github.com/user-attachments/assets/91e328d3-c12c-4d81-887d-38ea06ef9e4c" />
<img width="1080" alt="Mapa do NetCable" src="https://github.com/user-attachments/assets/792717d9-2239-4b9a-9959-fdead1927bb7" />

O NetCable é uma ferramenta open source e self-hosted para **desenhar a sua rede e ficar de olho nela**.
Arraste equipamentos para o mapa, monte racks com cara de equipamento real, ligue cabos porta a porta,
e o NetCable monitora tudo em segundo plano e avisa (e-mail, Telegram, webhook) quando algo cai.

Roda em **um único container Docker** em qualquer lugar: mini PC, VM, NAS, Raspberry Pi.

> ⚠️ Beta: em desenvolvimento ativo. Feedbacks e issues são muito bem-vindos.

## Funcionalidades

- 📡 **Descoberta da rede** — varre uma faixa (ex.: `192.168.1.0/24`), mostra quem respondeu com nome, portas abertas e tipo sugerido, e adiciona ao mapa num clique.
- 🗺️ **Mapa visual** — arrastar e soltar, cabos com rótulo, busca (`Ctrl+K`) e destaque ao passar o mouse.
- 🧭 **Atalhos entre mapas** — monte um mapa geral (matriz → filiais → datacenter); cada atalho mostra ao vivo quantos equipamentos estão online/offline no mapa dele, fica vermelho quando algo cai lá e abre com duplo clique.
- 🗄️ **Racks realistas** — de 4U a 48U; switches, servidores, NAS, patch panels, nobreaks… encaixando por U.
- 🧩 **Biblioteca de modelos** — cadastre seus equipamentos reais (ex.: “4 RJ45 + 2 SFP, 1U”) e a frente é desenhada com essas portas.
- 🔌 **Cabos porta a porta** — porta 12 do switch → eth3 do firewall; portas em uso ficam marcadas.
- 📡 **Monitoramento no servidor** — TCP (80/443/22) + ICMP em paralelo, SNMPv3 ou HTTP(S); funciona sem navegador aberto.
- 🔒 **Monitor HTTP(S) e de certificado** — verifica um site, API ou painel web (código de resposta, tempo, texto na página) e avisa antes de o certificado TLS vencer.
- 🚨 **Alertas** — e-mail, Discord, ntfy, Telegram e webhook na queda e na volta, agrupados, com liga/desliga por equipamento.
- 🧠 **Alertas inteligentes** — defina o uplink de cada equipamento (ou calcule pelos cabos): quando um switch cai chega **um** alerta com a lista do que está atrás dele, e esses equipamentos ficam âmbar (*inalcançáveis*) no mapa. **Janelas de manutenção** silenciam um equipamento ou o mapa inteiro por um tempo.
- 🌡️ **Métricas SNMP** — CPU, memória, temperatura, uptime e link/tráfego por porta dos equipamentos em SNMPv3, com gráficos, LEDs reais das portas no rack e alertas de temperatura/CPU.
- 📊 **Disponibilidade e latência** — uptime %, quedas, gráfico de latência (24 h / 7 d / 30 d), relatório diário por e-mail e **relatório de SLA em CSV** (7 / 30 / 90 dias).
- 📈 **`/metrics` para Prometheus** — status, latência, métricas SNMP e validade dos certificados para o Grafana.
- 🕵️ **Log de auditoria** — quem entrou, mexeu em usuários, salvou ou excluiu mapas, compartilhou links ou alterou configurações, e quando.
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

## Redes grandes: atalhos entre mapas

Divida uma rede grande em vários mapas (um por site, andar ou sala) e crie um **mapa geral** com atalhos:
**Adicionar → tipo "Atalho para outro mapa"** e escolha o mapa de destino. O atalho mostra quantos equipamentos estão online/offline lá,
fica vermelho quando algo cai e abre o mapa com **duplo clique** (ou um clique no modo visualização). Atalhos podem ter cabos como qualquer
equipamento (ex.: o link WAN entre dois sites) e vão nos backups/exportações (religados pelo nome do mapa ao importar).

## Descoberta da rede

No editor, clique no botão 📡 (radar), informe a faixa (`192.168.1.0/24`, `10.0.0.10-10.0.0.60` ou um IP) e clique em **Varrer**.
O servidor do NetCable pinga cada endereço e testa portas comuns (SSH, HTTP/S, SMB, RDP, DNS, impressoras, câmeras, Proxmox, Synology)
e lista quem respondeu, com o nome DNS reverso e um tipo sugerido (pelas portas abertas e por pistas no nome, como
`printer`, `cam`, `sw-`, `ap-`, `nas`; celulares, VoIP, IoT ou qualquer coisa sem evidência aparecem como **Outro**). O que já está em algum mapa aparece marcado e desmarcado.
Escolha, ajuste nomes/tipos, clique em **Adicionar ao mapa** e salve.

- Só faixas privadas (10/8, 172.16/12, 192.168/16, 100.64/10) de até 1024 endereços. `DISCOVERY_ALLOW_PUBLIC=1` libera faixas públicas (laboratório).
- No Docker, a rede bridge padrão alcança a LAN, então a varredura funciona. O **endereço MAC** só aparece com a rede do host,
  porque no modo bridge o container não enxerga a tabela ARP da sua LAN. Para ativar, troque `ports:` por `network_mode: host`
  e, se a porta 8080 já estiver ocupada no servidor, defina `PORT` (ex.: `PORT=3080` no TrueNAS):

  ```yaml
  services:
    netcable:
      image: ghcr.io/joao-monticelli/netcable:latest
      network_mode: host        # no lugar de ports:
      environment:
        - PORT=3080             # o NetCable escuta aqui: http://IP-DO-SERVIDOR:3080
  ```
- Editores e admins podem varrer; visualizadores não.

## Métricas SNMP

Para equipamentos monitorados por **SNMPv3**, o NetCable coleta a cada minuto (`SNMP_METRICS_INTERVAL`):
CPU (HOST-RESOURCES, Cisco, UCD), memória (hrStorage, UCD, Cisco), temperatura (ENTITY-SENSOR, lm-sensors, MikroTik, Cisco — o maior sensor)
e as portas pela IF-MIB (nome, descrição, link, velocidade, tráfego em contadores de 64 bits e erros).

- No mapa: temperatura e CPU ao lado do equipamento; no rack, **a porta N acende com o link real da N-ª interface física** (RJ45 primeiro, depois SFP), e o tooltip mostra nome, descrição, velocidade e tráfego.
- **Ver métricas** no equipamento (ou clique nele no modo visualização) abre os gráficos (1 h / 24 h / 7 dias, também em tabela) e a tabela de portas.
- **Alertas:** ⚙️ → Canais de alerta → *Limites de temperatura e CPU* (padrão 75 °C e 95%; `0` desativa). Alerta após 3 leituras seguidas acima do limite e avisa de novo quando normalizar. A manutenção também silencia.
- O **contexto** SNMPv3 é opcional (alguns equipamentos usam um por VRF/instância).
- Testado contra um agente SNMPv3 simulado (snmpsim) no CI; se alguma métrica aparecer como "—" no seu equipamento, abra uma issue com o modelo.

## Alertas inteligentes

- **Uplink (depende de):** abra um equipamento e escolha de qual ele depende (ex.: o switch onde está ligado).
  Mais rápido: abra o gateway/firewall e clique em **Usar como raiz e calcular uplinks pelos cabos** — o NetCable percorre os cabos e preenche todos. Salve o mapa.
- Quando um uplink cai, os equipamentos atrás dele ficam **âmbar (inalcançáveis)**, não geram alerta próprio e aparecem listados no alerta do uplink
  (*"Switch core OFFLINE — 12 equipamentos atrás dele inalcançáveis: …"*). Na volta, um único alerta de recuperação também os lista.
- **Manutenção:** o 🔧 na barra silencia o mapa inteiro por 1–24 h; dentro de um equipamento dá para silenciar só ele.
  O monitoramento e o histórico continuam; quem caiu durante a manutenção não manda "voltou" depois.
- **Canais:** ⚙️ → **Canais de alerta** (admin) para Discord, ntfy (notificação no celular), Telegram e webhook JSON, cada um com botão *Testar*. Tokens e URLs ficam cifrados.
  Também dá para usar variáveis de ambiente (`DISCORD_WEBHOOK_URL`, `NTFY_URL`, `NTFY_TOKEN`, `TELEGRAM_BOT_TOKEN`, `TELEGRAM_CHAT_ID`, `ALERT_WEBHOOK_URL`); o que for definido na interface tem prioridade.

## Monitor HTTP(S) e de certificado

Escolha **HTTP(S): site, API ou painel web** como método de monitoramento do equipamento:

- **URL** — ex.: `https://intranet.local/health`. Vazio usa `http://<IP do equipamento>/`.
- **Código esperado** — vazio aceita qualquer 2xx/3xx; informe `200`, `401`… para exigir um código.
- **Texto na página** — opcional; sem o texto o equipamento fica offline (pega páginas de erro que respondem "200 OK").
- **Validar o certificado** — desligue para equipamentos com certificado autoassinado (impressoras, NAS, firewalls).
- **Aviso de certificado** — alerta quando faltarem N dias ou menos para vencer (padrão 14; `0` desliga).
  O certificado é lido mesmo quando é autoassinado, então o aviso vale também para equipamentos internos.
  Chega um alerta quando está perto de vencer (ou venceu) e outro quando é renovado; a manutenção silencia.

O mapa mostra os dias restantes (🔒 `12d`, âmbar com 14 dias ou menos, vermelho se vencido) e o erro HTTP quando a verificação falha.

## Relatório de SLA, auditoria e Prometheus

- **Relatório de SLA:** ⚙️ → **Histórico** → *Disponibilidade* → **Exportar SLA (CSV)** de 7, 30 ou 90 dias: disponibilidade %,
  tempo fora do ar (`h:mm:ss` e segundos), quedas e latência média de cada equipamento. Abre direto no Excel/LibreOffice.
  O período é limitado por `HISTORY_RETENTION_DAYS` (padrão 30): aumente se precisar de relatórios de 90 dias.
- **Log de auditoria:** ⚙️ → **Log de auditoria** (admin): logins (inclusive os que falharam ou foram bloqueados), usuários
  criados/alterados/excluídos, mapas criados/renomeados/salvos/excluídos/importados, links públicos, manutenção,
  configurações e backups, com usuário, horário e IP. Senhas e segredos nunca são registrados.
- **Prometheus:** defina `METRICS_TOKEN` e colete `/metrics` com `authorization: { credentials: "seu-token" }`
  (ou `METRICS_PUBLIC=true` para liberar sem token numa rede confiável). Séries e exemplo no [README em inglês](README.md#sla-report-audit-log-and-prometheus).
  O log de auditoria fica guardado por `AUDIT_RETENTION_DAYS` (padrão 365) dias.

## Trocar a chave secreta

O `data/secret.key` cifra os segredos guardados (senhas SMTP/SNMP, canais de alerta, URLs do monitor HTTP) e assina os logins.
Se ela pode ter vazado, troque:

```bash
docker compose stop netcable
docker compose run --rm netcable python -m app.rotacao_chave
docker compose start netcable
```

Todos os segredos são cifrados de novo com uma chave nova numa única transação; uma cópia do banco e da chave antiga fica em
`data/backups/` (a chave antiga só serve para restaurar backups anteriores). Todo mundo precisa entrar de novo.
Se você define `SECRET_KEY` por variável, rode com `--nova-chave "<valor novo>"` e depois atualize a variável.
Se o banco também vazou, troque as senhas e tokens cadastrados no NetCable: trocar a chave não protege segredos que já vazaram.

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
