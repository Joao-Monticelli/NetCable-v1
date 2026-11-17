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
}

# Mensagens com partes variáveis: (padrão em português, modelo em inglês).
PADROES = [
    (re.compile(r"^Falha ao enviar o relatório: (.*)$", re.S), "Failed to send the report: {0}"),
    (re.compile(r"^Falha na descoberta: (.*)$", re.S), "Discovery failed: {0}"),
    (re.compile(r"^Falha no envio: (.*)$", re.S), "Sending failed: {0}"),
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
