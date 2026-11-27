"""Tradução das mensagens do backend (erros da API e e-mails).

O código usa as mensagens em português; para quem pediu inglês (cabeçalho
Accept-Language da interface, ou o idioma salvo no perfil para os e-mails),
`traduzir` devolve o texto em inglês. Inglês é o padrão.
"""

import re

IDIOMAS = ("en", "pt")
PADRAO = "en"

EN = {
    # --- Erros da API
    "A nova senha precisa ter pelo menos 8 caracteres.": "The new password must be at least 8 characters long.",
    "A senha precisa ter pelo menos 8 caracteres.": "The password must be at least 8 characters long.",
    "Altura deve ser de 1U a 8U.": "Height must be between 1U and 8U.",
    "Apenas administradores podem fazer isso.": "Only administrators can do this.",
    "Cadastre um e-mail no seu perfil primeiro.": "Add an email to your profile first.",
    "Credenciais inválidas": "Invalid credentials",
    "Equipamento não encontrado": "Device not found",
    "Horário do relatório inválido (use HH:MM).": "Invalid report time (use HH:MM).",
    "Informe um destinatário ou cadastre um e-mail no seu perfil.": "Enter a recipient or add an email to your profile.",
    "Informe um e-mail para receber alertas e relatórios.": "Enter an email to receive alerts and reports.",
    "Já existe um modelo com esse nome.": "A model with this name already exists.",
    "Já existe um usuário com esse nome.": "A user with this name already exists.",
    "Link inválido ou revogado": "Invalid or revoked link",
    "Modelo não encontrado": "Model not found",
    "Muitas tentativas. Tente novamente em alguns minutos.": "Too many attempts. Try again in a few minutes.",
    "O nome do modelo precisa ter de 2 a 60 caracteres.": "The model name must be 2 to 60 characters long.",
    "O sistema precisa de pelo menos um administrador ativo.": "The system needs at least one active administrator.",
    "Papel inválido.": "Invalid role.",
    "Porta inválida.": "Invalid port.",
    "Prefixo das portas muito longo (máx. 12).": "Port prefix too long (max. 12).",
    "Projeto não encontrado": "Project not found",
    "Rack não é um modelo de equipamento.": "A rack is not a device model.",
    "Segurança inválida (use starttls, ssl ou nenhuma).": "Invalid security (use starttls, ssl or none).",
    "Senha atual incorreta.": "Current password is incorrect.",
    "Seu usuário tem acesso somente de visualização.": "Your user has view-only access.",
    "Use de 0 a 8 portas SFP.": "Use 0 to 8 SFP ports.",
    "Usuário desativado. Fale com um administrador.": "User deactivated. Contact an administrator.",
    "Usuário inválido: use de 3 a 50 letras, números ou . _ @ -": "Invalid username: use 3 to 50 letters, numbers or . _ @ -",
    "Usuário não encontrado": "User not found",
    "Usuário ou senha incorretos": "Incorrect username or password",
    "Você não pode excluir o seu próprio usuário.": "You can't delete your own user.",
    "Idioma inválido (use en ou pt).": "Invalid language (use en or pt).",
    "O NetCable já foi configurado.": "NetCable has already been set up.",
    "Arquivo grande demais.": "File too large.",
    "Arquivo de mapa inválido.": "Invalid map file.",
    "Arquivo criado por uma versão mais nova do NetCable.": "File created by a newer version of NetCable.",
    "O backup não contém mapas.": "The backup contains no maps.",
    "Horário inválido (use HH:MM).": "Invalid time (use HH:MM).",
    "Quantidade de backups deve ser entre 1 e 365.": "Number of backups must be between 1 and 365.",
    "Use um caminho absoluto para a pasta de backup.": "Use an absolute path for the backup folder.",
    "Backup não encontrado": "Backup not found",
    "Informe a duração da manutenção.": "Enter the maintenance duration.",
    "A manutenção deve terminar no futuro e durar no máximo 30 dias.": "Maintenance must end in the future and last at most 30 days.",
    "Use um endereço que comece com http:// ou https://.": "Use an address starting with http:// or https://.",
    "Canal não configurado.": "Channel not configured.",
    "🌡️ Temperatura alta: {valor}{u} (limite {limite}{u})": "🌡️ High temperature: {valor}{u} (limit {limite}{u})",
    "🌡️ Temperatura normalizada: {valor}{u}": "🌡️ Temperature back to normal: {valor}{u}",
    "🔥 CPU alta: {valor}{u} (limite {limite}{u})": "🔥 High CPU: {valor}{u} (limit {limite}{u})",
    "✅ CPU normalizada: {valor}{u}": "✅ CPU back to normal: {valor}{u}",
    "{n} alerta(s) de temperatura/CPU": "{n} temperature/CPU alert(s)",
    "{n} alerta(s) de certificado": "{n} certificate alert(s)",
    "🔒 Certificado renovado: vence em {valor} dia(s)": "🔒 Certificate renewed: expires in {valor} day(s)",
    "🔓 Certificado TLS VENCIDO há {valor} dia(s)": "🔓 TLS certificate EXPIRED {valor} day(s) ago",
    "🔒 Certificado TLS vence em {valor} dia(s) (aviso com {limite} dias)": "🔒 TLS certificate expires in {valor} day(s) (warning at {limite} days)",
    "URL inválida (use http:// ou https://).": "Invalid URL (use http:// or https://).",
    "Certificado TLS inválido.": "Invalid TLS certificate.",
    "Texto esperado não encontrado na página.": "Expected text not found on the page.",
    "Período inválido (use de 1 a 365 dias).": "Invalid period (use 1 to 365 days).",
    "Limites inválidos (temperatura 0–150 °C, CPU 0–100%; 0 desativa).": "Invalid limits (temperature 0–150 °C, CPU 0–100%; 0 disables).",
    "Faixa inválida. Use, por exemplo, 192.168.1.0/24 ou 192.168.1.10-192.168.1.50.": "Invalid range. Use, for example, 192.168.1.0/24 or 192.168.1.10-192.168.1.50.",
    "Faixa grande demais: use no máximo 1024 endereços (ex.: /22).": "Range too large: use at most 1024 addresses (e.g. /22).",
    "Só é possível varrer redes privadas (ex.: 192.168.x.x, 10.x.x.x, 172.16-31.x.x).": "Only private networks can be scanned (e.g. 192.168.x.x, 10.x.x.x, 172.16-31.x.x).",
    "Já existe uma varredura em andamento.": "A scan is already running.",
    "Varredura não encontrada.": "Scan not found.",
    "{n} equipamento(s) atrás dele inalcançável(is): {lista}": "{n} device(s) behind it unreachable: {lista}",
    "{n} equipamento(s) atrás dele voltaram junto: {lista}": "{n} device(s) behind it recovered too: {lista}",
    "Canal desconhecido.": "Unknown channel.",
    "✅ Teste do NetCable: este canal vai receber os alertas de queda e recuperação.": "✅ NetCable test: this channel will receive down and recovery alerts.",
    "Servidor SMTP não configurado.": "SMTP server not configured.",
    "Nenhum destinatário com e-mail cadastrado.": "No recipient with a registered email.",

    # --- E-mails
    "Mudanças de status detectadas pelo NetCable:": "Status changes detected by NetCable:",
    "NetCable — alerta de status": "NetCable — status alert",
    "{n} equipamento(s) offline": "{n} device(s) offline",
    "{n} recuperado(s)": "{n} recovered",
    "mapa": "map",
    "Status": "Status",
    "Equipamento": "Device",
    "IP": "IP",
    "Mapa": "Map",
    "Agora": "Now",
    "Disponibilidade": "Availability",
    "Quedas": "Outages",
    "Latência média": "Avg. latency",
    "Latência": "Latency",
    "sem dados": "no data",
    "{inicio} até {fim}": "{inicio} to {fim}",
    "Relatório do NetCable ({periodo})": "NetCable report ({periodo})",
    "NetCable — relatório diário": "NetCable — daily report",
    "[NetCable] Relatório diário — {quedas} queda(s), {offline} offline agora": "[NetCable] Daily report — {quedas} outage(s), {offline} offline now",
    "{total} equipamento(s) monitorado(s), {quedas} queda(s), {offline} offline agora.": "{total} monitored device(s), {quedas} outage(s), {offline} offline now.",
    "equipamento(s) monitorado(s)": "monitored device(s)",
    "queda(s)": "outage(s)",
    "offline agora": "offline now",
    "Nenhum equipamento monitorado.": "No monitored devices.",
    "Eventos": "Events",
    "Eventos no período:": "Events in the period:",
    "agora {status}, disponibilidade {pct}, {quedas} queda(s), latência {lat}": "now {status}, availability {pct}, {quedas} outage(s), latency {lat}",
    "online": "online",
    "offline": "offline",
    "visual": "visual",
    "[NetCable] E-mail de teste": "[NetCable] Test email",
    "Se você recebeu esta mensagem, o envio de e-mails do NetCable está funcionando.": "If you received this message, NetCable email delivery is working.",
    # Telegram
    "🔴 Equipamento OFFLINE": "🔴 Device OFFLINE",
    "🟢 Equipamento voltou ONLINE": "🟢 Device back ONLINE",
    # --- 2FA, acknowledgements, reminders, scheduled maintenance, status page
    "A verificação em duas etapas já está ativa.": "Two-factor authentication is already on.",
    "A verificação em duas etapas não está ativa.": "Two-factor authentication is not on.",
    "Cada janela semanal deve durar de 5 minutos a 24 horas.": "Each weekly window must last from 5 minutes to 24 hours.",
    "Comece a configuração de novo.": "Start the setup again.",
    "Código de verificação incorreto.": "Wrong verification code.",
    "Código incorreto. Confira o horário do celular e tente o código atual.": "Wrong code. Check your phone's clock and try the current code.",
    "Escolha pelo menos um dia da semana.": "Pick at least one day of the week.",
    "Manutenção não encontrada.": "Maintenance not found.",
    "O início deve ser no futuro (até 1 ano).": "The start must be in the future (up to 1 year).",
    "O lembrete deve ser de 5 a 1440 minutos (0 desliga).": "The reminder must be 5 to 1440 minutes (0 turns it off).",
    "O login expirou. Digite a senha de novo.": "The login expired. Enter your password again.",
    "Página de status inválida ou desativada": "Invalid or disabled status page",
    "RECONHECIDO": "ACKNOWLEDGED",
    "Só dá para reconhecer o alerta de um equipamento offline.": "Only the alert of an offline device can be acknowledged.",
    "{n} alerta(s) reconhecido(s)": "{n} alert(s) acknowledged",
    "{n} dias": "{n} days",
    "⏰ Ainda offline há {duracao} e ninguém reconheceu o alerta": "⏰ Still offline for {duracao} and nobody acknowledged the alert",
    "⏰ Equipamento ainda OFFLINE": "⏰ Device still OFFLINE",
    "👀 Alerta reconhecido": "👀 Alert acknowledged",
    "👀 Reconhecido por {usuario}": "👀 Acknowledged by {usuario}",
    "👀 {usuario} reconheceu o alerta e está cuidando": "👀 {usuario} acknowledged the alert and is on it",
    # --- 1.1: incidents, escalation, LLDP/CDP, LDAP
    "🚨 Alerta escalado: equipamento OFFLINE": "🚨 Escalated alert: device OFFLINE",
    "🚨 Offline há {duracao} e ninguém da equipe reconheceu o alerta": "🚨 Offline for {duracao} and nobody on the team acknowledged the alert",
    "Endereço do servidor inválido (use ldap://servidor ou ldaps://servidor).": "Invalid server address (use ldap://server or ldaps://server).",
    "Configure o servidor e a base de busca (base DN).": "Set the server and the search base (base DN).",
    "Sem resposta do servidor LDAP.": "No answer from the LDAP server.",
    "A conta de serviço (bind DN) foi recusada pelo diretório.": "The directory refused the service account (bind DN).",
    "Informe o servidor e a base de busca (base DN) para ativar.": "Enter the server and the search base (base DN) to turn it on.",
    "O filtro precisa estar entre parênteses e conter {usuario}.": "The filter must be in parentheses and contain {usuario}.",
    "Papel padrão inválido.": "Invalid default role.",
    "O escalonamento deve ser de 5 a 1440 minutos (0 desliga).": "Escalation must be 5 to 1440 minutes (0 turns it off).",
    "E-mail de escalonamento inválido.": "Invalid escalation e-mail.",
    "Seu usuário do diretório não está em nenhum grupo liberado para o NetCable.": "Your directory user is not in any group allowed to use NetCable.",
    "Não foi possível falar com o diretório (LDAP/AD). Tente de novo ou use uma conta local.": "Could not reach the directory (LDAP/AD). Try again or use a local account.",
    "Sua senha é a do diretório da empresa (LDAP/AD): troque-a por lá.": "Your password is your company directory password (LDAP/AD): change it there.",
    "A senha deste usuário é a do diretório (LDAP/AD).": "This user's password is the directory one (LDAP/AD).",
    "Impacto inválido.": "Invalid impact.",
    "Situação inválida.": "Invalid status.",
    "Mapa não encontrado": "Map not found",
    "Incidente não encontrado": "Incident not found",
    "Dê um título ao incidente.": "Give the incident a title.",
    "Escreva o que está acontecendo.": "Write what is happening.",
    "Escreva a atualização.": "Write the update.",
    "Nenhum equipamento deste mapa é monitorado por SNMPv3: configure o SNMPv3 nos switches primeiro.": "No device on this map is monitored by SNMPv3: set up SNMPv3 on the switches first.",
}


# Mensagens com partes variáveis: (padrão em português, modelo em inglês).
PADROES = [
    (re.compile(r"^Falha no diretório: (.*)$", re.S), "Directory error: {0}"),
    (re.compile(r"^Falha no STARTTLS: (.*)$", re.S), "STARTTLS failed: {0}"),
    (re.compile(r"^Busca recusada: (.*)$", re.S), "Search refused: {0}"),
    (re.compile(r"^Mais de uma conta no diretório responde por '(.*)': ajuste o filtro\.$"), "More than one directory account matches '{0}': adjust the filter."),
    (re.compile(r"^Falha ao enviar o relatório: (.*)$", re.S), "Failed to send the report: {0}"),
    (re.compile(r"^Falha na descoberta: (.*)$", re.S), "Discovery failed: {0}"),
    (re.compile(r"^Falha no envio: (.*)$", re.S), "Sending failed: {0}"),
    (re.compile(r"^Falha no backup: (.*)$", re.S), "Backup failed: {0}"),
    (re.compile(r"^Não foi possível gravar na pasta: (.*)$", re.S), "Cannot write to the folder: {0}"),
    (re.compile(r"^Fuso horário desconhecido: (.*)$"), "Unknown time zone: {0}"),
    (re.compile(r"^Modelo em uso por (\d+) equipamento\(s\)\. Troque o modelo deles antes de excluir\.$"), "Model in use by {0} device(s). Change their model before deleting."),
    (re.compile(r"^Para (\d+)U, use de 0 a (\d+) portas RJ45\.$"), "For {0}U, use 0 to {1} RJ45 ports."),
    (re.compile(r"^Rack '(.*)': tamanho inválido \(use de 1U a 60U\)\.$"), "Rack '{0}': invalid size (use 1U to 60U)."),
    (re.compile(r"^'(.*)' está montado em um rack que não existe mais\.$"), "'{0}' is mounted in a rack that no longer exists."),
    (re.compile(r"^'(.*)' não cabe no rack '(.*)' nessa posição\.$"), "'{0}' does not fit in rack '{1}' at that position."),
    (re.compile(r"^'(.*)' e '(.*)' ocupam o mesmo U(\d+) no rack '(.*)'\.$"), "'{0}' and '{1}' use the same U{2} in rack '{3}'."),
]


def normalizar(idioma):
    return idioma if idioma in IDIOMAS else PADRAO


def idioma_do_cabecalho(accept_language):
    """'pt-BR,pt;q=0.9' -> 'pt'; qualquer outra coisa (ou vazio) -> inglês."""
    primeiro = (accept_language or "").split(",")[0].strip().lower()
    return "pt" if primeiro.startswith("pt") else "en"


def traduzir(texto, idioma, **variaveis):
    """Traduz `texto` (em português) para `idioma` e aplica {variaveis}."""
    if not isinstance(texto, str):
        return texto
    resultado = texto
    if normalizar(idioma) == "en":
        if texto in EN:
            resultado = EN[texto]
        else:
            for padrao, modelo in PADROES:
                m = padrao.match(texto)
                if m:
                    # As partes variáveis também podem ser mensagens conhecidas (ex.: erro do SMTP).
                    resultado = modelo.format(*(traduzir(g, idioma) for g in m.groups()))
                    break
    return resultado.format(**variaveis) if variaveis else resultado
