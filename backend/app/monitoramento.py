"""Background work: device checks, monitor cycle, reminders, SNMP metrics, daily reports and scheduled backups."""

from .relogio import utcnow
from sqlalchemy.orm import Session
from datetime import datetime, timezone
import ping3
import socket
import time
import os
import threading
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Optional
from .snmp_service import test as snmp_test, SNMPUnavailableError
from . import models, crud, alerts, email_service
from .i18n import normalizar
from .database import SessionLocal, DATA_DIR, DB_PATH
from . import backup, regras_alerta, snmp_service, metricas_snmp, monitor_http, auditoria
from .nucleo import (
    HISTORY_RETENTION_DAYS,
    MONITOR_FAILURE_THRESHOLD,
    MONITOR_INTERVAL,
    MONITOR_WORKERS,
    VERSAO,
    abrir_config,
    get_canais_config,
    get_fuso,
    get_smtp_config,
    iso_utc,
    logger,
)


# Long-lived pools: each worker thread keeps its SNMP engines (and asyncio loop) between cycles,
# which is faster and avoids leaving a loop and its sockets behind every cycle.
_POOL_MONITOR = ThreadPoolExecutor(max_workers=max(1, MONITOR_WORKERS), thread_name_prefix="netcable-monitor")


_POOL_METRICAS = ThreadPoolExecutor(max_workers=8, thread_name_prefix="netcable-snmp")


def registrar_monitoramento(db: Session, equipamento, resultado):
    """Grava o resultado. Retorna o evento de alerta (dict) se o status mudou e o
    equipamento tem notificação ligada; caso contrário None."""
    if not equipamento:
        return None
    status = resultado.get("status", "offline")
    tempo_ms = resultado.get("tempo_ms")
    crud.atualizar_status_equipamento(db, equipamento.id, status, tempo_ms)
    _, mudou, status_anterior = crud.registrar_status(db, equipamento.id, status, tempo_ms)
    if not mudou:
        return None
    logger.info("Status alterado: %s (%s) %s -> %s", equipamento.nome, equipamento.ip, status_anterior, status)
    reconhecido = None
    if status == "offline":
        _offline_desde[equipamento.id] = {"desde": time.monotonic(), "aviso": time.monotonic()}
    else:
        _offline_desde.pop(equipamento.id, None)
        reconhecido = regras_alerta.remover_reconhecimento(db, equipamento.id)  # it is back: nothing left to handle
    if not equipamento.notificar:
        return None
    projeto_nome = equipamento.projeto.nome if equipamento.projeto else None
    evento = alerts.montar_evento(equipamento, projeto_nome, status, status_anterior, tempo_ms)
    if reconhecido:
        evento["reconhecido_por"] = reconhecido.usuario
    return evento


# --- LEMBRETES DE EQUIPAMENTO AINDA OFFLINE ---
# eq_id -> {"desde": monotonic of the fall, "aviso": monotonic of the last alert/reminder}
# (in memory: after a restart the first reminder counts from the first cycle).
_offline_desde = {}


def get_lembrete_min(db: Session):
    try:
        return max(0, int(crud.get_configuracoes(db, "alertas.lembrete_min").get("alertas.lembrete_min") or 0))
    except ValueError:
        return 0


def lembretes_offline(db: Session, agora=None):
    """Reminder events for devices still offline after `alertas.lembrete_min` minutes that nobody acknowledged.
    They go through regras_alerta.aplicar like any fall (maintenance and uplink rules apply)."""
    minutos = get_lembrete_min(db)
    if minutos <= 0:
        return []
    agora = time.monotonic() if agora is None else agora
    reconhecidos = regras_alerta.reconhecimentos(db)
    eventos = []
    for eq in db.query(models.Equipamento).filter(models.Equipamento.status == "offline").all():
        if not eq.notificar or not _equipamento_monitoravel(eq):
            continue
        estado = _offline_desde.setdefault(eq.id, {"desde": agora, "aviso": agora})
        if eq.id in reconhecidos or agora - estado["aviso"] < minutos * 60:
            continue
        estado["aviso"] = agora
        evento = alerts.montar_evento(eq, eq.projeto.nome if eq.projeto else None, "offline", "offline")
        evento.update(evento="equipamento_lembrete", lembrete=True, offline_ha_s=round(agora - estado["desde"]))
        eventos.append(evento)
    return eventos


def enviar_alertas(db: Session, eventos):
    if not eventos:
        return
    por_idioma = {}
    for u in crud.usuarios_para_alertas(db):
        por_idioma.setdefault(normalizar(u.idioma), []).append(u.email)
    alerts.notificar(eventos, get_smtp_config(db), por_idioma, get_canais_config(db))


def checar_equipamento(ip: str, mode: str = "ip", config: Optional[dict] = None):
    """Verifica um equipamento por ping/TCP ou SNMPv3.
    Propaga SNMPUnavailableError quando o pysnmp não está instalado."""
    if mode == "http":
        return monitor_http.checar(ip, config)
    if mode != "snmpv3":
        return ping_equipamento(ip)  # função interna de ping (não a rota HTTP)
    config = {**(config or {}), "host": ip}
    try:
        return {"ip": ip, "status": "online", "tempo_ms": None, **snmp_test(config)}
    except SNMPUnavailableError:
        raise
    except Exception as exc:
        return {"ip": ip, "status": "offline", "tempo_ms": None, "error": str(exc)}


# --- MONITORAMENTO EM SEGUNDO PLANO ---
# Mantém o status no banco atualizado mesmo sem nenhum Editor aberto,
# para que o link público (ex.: TV do NOC) mostre dados reais.
_monitor_stop = threading.Event()


_falhas_consecutivas = {}


_ultimo_ciclo = {"fim": None, "duracao": None, "equipamentos": 0}


_ultima_limpeza = {"momento": 0.0}


def _equipamento_monitoravel(eq):
    return eq.monitor_mode != "visual" and eq.status != "visual" and eq.ip and eq.ip != "Sem IP"


def _checar_seguro(alvo):
    eq_id, ip, mode, config = alvo
    try:
        return eq_id, checar_equipamento(ip, mode, config)
    except Exception as exc:
        logger.warning("Monitor: falha ao verificar %s (%s): %s", ip, mode, exc)
        return eq_id, None


def executar_ciclo_monitoramento():
    db = SessionLocal()
    try:
        alvos = [
            (eq.id, eq.ip, eq.monitor_mode or "ip", abrir_config(eq.monitor_config) if eq.monitor_mode in ("snmpv3", "http") else None)
            for eq in db.query(models.Equipamento).all() if _equipamento_monitoravel(eq)
        ]
    finally:
        db.close()
    inicio = time.monotonic()
    resultados = []
    if alvos:
        resultados = list(_POOL_MONITOR.map(_checar_seguro, alvos))
    db = SessionLocal()
    eventos = []
    try:
        for eq_id, resultado in resultados:
            if resultado is None:
                continue
            # Recarrega: o mapa pode ter sido salvo (e o equipamento removido) durante o ciclo.
            equipamento = crud.get_equipamento(db, eq_id)
            if not equipamento:
                _falhas_consecutivas.pop(eq_id, None)
                continue
            if equipamento.monitor_mode == "http":
                _http[eq_id] = _http_compacto(resultado)
                if equipamento.notificar:
                    eventos += avaliar_certificado(equipamento, resultado.get("certificado"), abrir_config(equipamento.monitor_config))
            if resultado.get("status") == "offline":
                falhas = _falhas_consecutivas.get(eq_id, 0) + 1
                _falhas_consecutivas[eq_id] = falhas
                # Equipamento estava online: só derruba após N falhas seguidas.
                if equipamento.status == "online" and falhas < MONITOR_FAILURE_THRESHOLD:
                    continue
            else:
                _falhas_consecutivas.pop(eq_id, None)
            evento = registrar_monitoramento(db, equipamento, resultado)
            if evento:
                eventos.append(evento)
        eventos += lembretes_offline(db)
        # Um único alerta por ciclo, mesmo que vários equipamentos mudem juntos; quedas "em cascata"
        # (uplink offline) e equipamentos em manutenção não geram alerta próprio.
        enviar_alertas(db, regras_alerta.aplicar(db, eventos))
        if time.monotonic() - _ultima_limpeza["momento"] > 3600:
            regras_alerta.limpar_manutencoes_vencidas(db)
            regras_alerta.limpar_reconhecimentos_orfaos(db)
        if HISTORY_RETENTION_DAYS > 0 and time.monotonic() - _ultima_limpeza["momento"] > 3600:
            _ultima_limpeza["momento"] = time.monotonic()
            auditoria.limpar(db)
            apagados = crud.limpar_historico(db, HISTORY_RETENTION_DAYS)
            if apagados:
                logger.info("Histórico: %s registros com mais de %s dias removidos", apagados, HISTORY_RETENTION_DAYS)
    finally:
        db.close()
    _ultimo_ciclo.update(fim=utcnow(), duracao=round(time.monotonic() - inicio, 2), equipamentos=len(alvos))


_http = {}  # eq_id -> last HTTP(S) check (status code, error, certificate)


def _http_compacto(resultado):
    return {k: resultado.get(k) for k in ("url", "http_status", "error", "certificado") if resultado.get(k) is not None}


def avaliar_certificado(eq, cert, config):
    """Alert once when the certificate gets within `diasCert` days of expiring (or is already expired),
    and once more when it is renewed."""
    if not cert or cert.get("dias") is None:
        return []
    try:
        limite = int((config or {}).get("diasCert", monitor_http.DIAS_CERT_PADRAO))
    except (TypeError, ValueError):
        limite = monitor_http.DIAS_CERT_PADRAO
    if limite <= 0:
        return []
    estado = _limites_estado.setdefault((eq.id, "certificado"), {"acima": 0, "alertado": False})
    projeto_nome = eq.projeto.nome if eq.projeto else None
    if cert["dias"] <= limite and not estado["alertado"]:
        estado["alertado"] = True
        return [alerts.montar_evento_metrica(eq, projeto_nome, "certificado", cert["dias"], limite, "alerta")]
    if cert["dias"] > limite and estado["alertado"]:
        estado["alertado"] = False
        return [alerts.montar_evento_metrica(eq, projeto_nome, "certificado", cert["dias"], limite, "normal")]
    return []


def _loop_monitoramento():
    logger.info("Monitoramento em segundo plano ativo (intervalo: %ss)", MONITOR_INTERVAL)
    # Primeiro ciclo logo após iniciar, para não exibir status antigos por um intervalo inteiro.
    while True:
        try:
            executar_ciclo_monitoramento()
        except Exception:
            logger.exception("Erro no ciclo de monitoramento")
        if _monitor_stop.wait(MONITOR_INTERVAL):
            break


# --- RELATÓRIO DIÁRIO POR E-MAIL ---
_falhas_relatorio = {}  # user_id -> momento (monotonic) da última falha, para não tentar a cada minuto


def enviar_relatorio(db: Session, destinatarios, horas: int = 24, idioma: str = "en"):
    fuso = get_fuso(db)
    formato = "%d/%m/%Y %H:%M" if normalizar(idioma) == "pt" else "%Y-%m-%d %H:%M"
    formatar = lambda momento: momento.replace(tzinfo=timezone.utc).astimezone(fuso).strftime(formato)
    assunto, texto, html = email_service.montar_email_relatorio(crud.montar_relatorio(db, horas), formatar, normalizar(idioma))
    email_service.enviar_email(get_smtp_config(db), destinatarios, assunto, texto, html)


def verificar_relatorios_agendados(agora_utc: datetime = None):
    """Envia o relatório diário a quem chegou no horário escolhido e ainda não recebeu hoje."""
    db = SessionLocal()
    try:
        if not email_service.smtp_configurado(get_smtp_config(db)):
            return
        agora_local = (agora_utc or datetime.now(timezone.utc)).astimezone(get_fuso(db))
        hoje, hora = agora_local.strftime("%Y-%m-%d"), agora_local.strftime("%H:%M")
        for user in crud.listar_usuarios(db):
            if not (user.ativo and user.relatorio_diario and user.email):
                continue
            if user.ultimo_relatorio == hoje or hora < (user.relatorio_horario or "08:00"):
                continue
            if time.monotonic() - _falhas_relatorio.get(user.id, -1e9) < 1800:
                continue
            try:
                enviar_relatorio(db, [user.email], idioma=user.idioma)
                crud.atualizar_usuario(db, user.id, ultimo_relatorio=hoje)
                logger.info("Relatório diário enviado para %s", user.email)
            except Exception as exc:
                _falhas_relatorio[user.id] = time.monotonic()
                logger.warning("Falha ao enviar relatório diário para %s: %s", user.email, exc)
    finally:
        db.close()


# --- BACKUP AUTOMÁTICO ---
BACKUP_DIR_PADRAO = os.path.join(DATA_DIR, "backups")


_trava_backup = threading.Lock()


_falha_backup = {"momento": -1e9}


def get_backup_config(db: Session):
    c = crud.get_configuracoes(db, "backup.")
    try:
        manter = max(1, int(c.get("backup.manter") or 7))
    except ValueError:
        manter = 7
    return {
        "ativo": c.get("backup.ativo", "1") == "1",
        "diretorio": c.get("backup.diretorio") or BACKUP_DIR_PADRAO,
        "horario": c.get("backup.horario") or "03:00",
        "manter": manter,
        "ultimo": c.get("backup.ultimo") or None,
        "ultimo_erro": c.get("backup.ultimo_erro") or None,
    }


def fazer_backup(db: Session, agora_utc: datetime = None):
    cfg = get_backup_config(db)
    with _trava_backup:
        caminho = backup.criar_backup(db, DB_PATH, cfg["diretorio"], abrir_config, VERSAO)
        backup.limpar_antigos(cfg["diretorio"], cfg["manter"])
    momento = (agora_utc or datetime.now(timezone.utc)).astimezone(timezone.utc).replace(tzinfo=None)
    crud.salvar_configuracoes(db, {"backup.ultimo": iso_utc(momento), "backup.ultimo_erro": ""})
    logger.info("Backup criado: %s", caminho)
    return caminho


def verificar_backup_agendado(agora_utc: datetime = None):
    """Um backup por dia, a partir do horário escolhido (no fuso configurado)."""
    db = SessionLocal()
    try:
        cfg = get_backup_config(db)
        if not cfg["ativo"] or not crud.listar_usuarios(db):
            return
        fuso = get_fuso(db)
        agora_local = (agora_utc or datetime.now(timezone.utc)).astimezone(fuso)
        if agora_local.strftime("%H:%M") < cfg["horario"]:
            return
        if cfg["ultimo"]:
            ultimo = datetime.fromisoformat(cfg["ultimo"].replace("Z", "+00:00"))
            if ultimo.tzinfo is None:
                ultimo = ultimo.replace(tzinfo=timezone.utc)
            if ultimo.astimezone(fuso).date() == agora_local.date():
                return
        if time.monotonic() - _falha_backup["momento"] < 1800:
            return
        try:
            fazer_backup(db, agora_utc)
        except Exception as exc:
            _falha_backup["momento"] = time.monotonic()
            crud.salvar_configuracoes(db, {"backup.ultimo_erro": f"{iso_utc(utcnow())} {exc}"})
            logger.warning("Falha no backup automático: %s", exc)
    finally:
        db.close()


def _loop_relatorios():
    while not _monitor_stop.wait(60):
        try:
            verificar_relatorios_agendados()
        except Exception:
            logger.exception("Erro ao verificar relatórios agendados")
        try:
            verificar_backup_agendado()
        except Exception:
            logger.exception("Erro ao verificar o backup agendado")


# --- MÉTRICAS SNMP (CPU, memória, temperatura, portas) ---
# Coletadas de equipamentos em SNMPv3 que estão online, a cada SNMP_METRICS_INTERVAL segundos.
SNMP_METRICS_INTERVAL = int(os.getenv("SNMP_METRICS_INTERVAL", "60"))


AMOSTRAS_PARA_ALERTAR = 3  # leituras seguidas acima do limite antes de alertar (evita picos)


_metricas = {}       # eq_id -> última coleta completa


_estado_snmp = {}    # eq_id -> contadores da coleta anterior (para calcular bit/s)


_limites_estado = {}  # (eq_id, métrica) -> {"acima": n, "alertado": bool}


def _metricas_compactas(m):
    return {
        "cpu": m.get("cpu_pct"), "mem": m.get("memoria_pct"), "temp": m.get("temperatura_c"), "uptime": m.get("uptime_s"),
        "coletado_em": m.get("coletado_em"),
        # [ordem, up, in_bps, out_bps, nome, alias, velocidade_mbps] das portas físicas
        "portas": [[i["ordem"], i["up"], i["in_bps"], i["out_bps"], i["nome"], i["alias"], i["velocidade_mbps"]]
                   for i in m.get("interfaces", []) if i.get("fisica")],
    }


def get_limites(db: Session):
    c = crud.get_configuracoes(db, "metricas.")
    def numero(chave, padrao):
        try:
            return float(c.get(chave)) if c.get(chave) not in (None, "") else padrao
        except ValueError:
            return padrao
    return {"temperatura": numero("metricas.limite_temp", 75.0), "cpu": numero("metricas.limite_cpu", 95.0)}


def avaliar_limites(eq, metricas, limites, projeto_nome=None):
    """Eventos de métrica acima do limite (após N leituras) e de volta ao normal (com folga)."""
    eventos = []
    for metrica, valor, folga in (("temperatura", metricas.get("temperatura_c"), 5), ("cpu", metricas.get("cpu_pct"), 10)):
        limite = limites.get(metrica) or 0
        estado = _limites_estado.setdefault((eq.id, metrica), {"acima": 0, "alertado": False})
        if not limite or valor is None:
            continue
        if valor >= limite:
            estado["acima"] += 1
            if estado["acima"] >= AMOSTRAS_PARA_ALERTAR and not estado["alertado"]:
                estado["alertado"] = True
                eventos.append(alerts.montar_evento_metrica(eq, projeto_nome, metrica, valor, limite, "alerta"))
        else:
            estado["acima"] = 0
            if estado["alertado"] and valor <= limite - folga:
                estado["alertado"] = False
                eventos.append(alerts.montar_evento_metrica(eq, projeto_nome, metrica, valor, limite, "normal"))
    return eventos


def _coletar_um(alvo):
    eq_id, ip, config = alvo
    cfg = {**(config or {}), "host": ip}
    try:
        return eq_id, metricas_snmp.coletar(lambda *oids: snmp_service.get(cfg, *oids),
                                            lambda oid: snmp_service.walk(cfg, oid), _estado_snmp.get(eq_id))
    except Exception as exc:
        logger.debug("Métricas SNMP de %s indisponíveis: %s", ip, exc)
        return eq_id, None


def executar_coleta_metricas():
    try:
        snmp_service._hlapi()
    except SNMPUnavailableError:
        return 0
    db = SessionLocal()
    try:
        equipamentos = db.query(models.Equipamento).filter(models.Equipamento.monitor_mode == "snmpv3").all()
        alvos = [(eq.id, eq.ip, abrir_config(eq.monitor_config)) for eq in equipamentos if eq.status == "online"]
    finally:
        db.close()
    if not alvos:
        return 0
    resultados = list(_POOL_METRICAS.map(_coletar_um, alvos))
    db = SessionLocal()
    eventos = []
    try:
        limites = get_limites(db)
        agora = utcnow()
        for eq_id, resultado in resultados:
            if not resultado:
                continue
            metricas, estado = resultado
            _estado_snmp[eq_id] = estado
            _metricas[eq_id] = {**metricas, "coletado_em": iso_utc(agora)}
            fisicas = [i for i in metricas["interfaces"] if i["fisica"]]
            soma = lambda campo: sum(i[campo] for i in fisicas if i[campo] is not None) if any(i[campo] is not None for i in fisicas) else None
            db.add(models.MetricaSnmp(equipamento_id=eq_id, criado_em=agora, cpu_pct=metricas["cpu_pct"], memoria_pct=metricas["memoria_pct"],
                                      temperatura_c=metricas["temperatura_c"], in_bps=soma("in_bps"), out_bps=soma("out_bps")))
            eq = crud.get_equipamento(db, eq_id)
            if eq and eq.notificar:
                eventos += avaliar_limites(eq, metricas, limites, eq.projeto.nome if eq.projeto else None)
        db.commit()
        enviar_alertas(db, regras_alerta.aplicar(db, eventos))
    finally:
        db.close()
    return len([r for _, r in resultados if r])


def _loop_metricas():
    while not _monitor_stop.wait(SNMP_METRICS_INTERVAL):
        try:
            executar_coleta_metricas()
        except Exception:
            logger.exception("Erro na coleta de métricas SNMP")


# Pool compartilhado: as sondagens de cada equipamento rodam em paralelo.
_POOL_PING = ThreadPoolExecutor(max_workers=64, thread_name_prefix="netcable-ping")


PING_TIMEOUT = 1.5


PORTAS_TCP = (80, 443, 22)


def _sonda_tcp(ip, porta):
    inicio = time.perf_counter()
    try:
        with socket.create_connection((ip, porta), timeout=PING_TIMEOUT):
            return round((time.perf_counter() - inicio) * 1000, 2)
    except OSError:
        return None


def _sonda_icmp(ip):
    try:
        resposta = ping3.ping(ip, timeout=PING_TIMEOUT)
    except Exception:
        return None
    # ping3 devolve None (sem resposta) ou False (erro, ex.: sem permissão / host inválido).
    if resposta is None or resposta is False:
        return None
    return round(resposta * 1000, 2)


def ping_equipamento(ip: str):
    """Online se qualquer sonda responder (TCP 80/443/22 ou ICMP), todas em paralelo.
    Antes eram sequenciais: um equipamento fora do ar levava ~6 s para ser verificado."""
    sondas = [_POOL_PING.submit(_sonda_tcp, ip, porta) for porta in PORTAS_TCP]
    sondas.append(_POOL_PING.submit(_sonda_icmp, ip))
    try:
        for sonda in as_completed(sondas, timeout=PING_TIMEOUT + 1):
            tempo = sonda.result()
            if tempo is not None:
                return {"ip": ip, "status": "online", "tempo_ms": tempo}
    except Exception:
        pass
    finally:
        for sonda in sondas:
            sonda.cancel()
    return {"ip": ip, "status": "offline", "tempo_ms": None}
