"""Prometheus /metrics endpoint."""

from fastapi import Depends, HTTPException, Request
from sqlalchemy.orm import Session
import os
import secrets
from .. import crud
from fastapi.responses import Response
from ..nucleo import VERSAO, get_db
from ..monitoramento import _http, _metricas, _ultimo_ciclo
from .mapas import _estado_alertas
from fastapi import APIRouter

router = APIRouter()


# --- PROMETHEUS METRICS ---
# Disabled unless METRICS_TOKEN (Bearer token required) or METRICS_PUBLIC=true is set.
METRICS_TOKEN = os.getenv("METRICS_TOKEN", "").strip()


METRICS_PUBLIC = os.getenv("METRICS_PUBLIC", "").strip().lower() in ("1", "true", "yes")


def _rotulo_prom(valor):
    return str(valor if valor is not None else "").replace("\\", "\\\\").replace("\n", "\\n").replace('"', '\\"')


def montar_metricas_prometheus(db: Session):
    linhas = []
    familias = {}

    def metrica(nome, tipo, ajuda, rotulos, valor):
        if valor is None:
            return
        if nome not in familias:
            familias[nome] = True
            linhas.append(f"# HELP {nome} {ajuda}")
            linhas.append(f"# TYPE {nome} {tipo}")
        texto = ",".join(f'{k}="{_rotulo_prom(v)}"' for k, v in rotulos.items())
        linhas.append(f"{nome}{{{texto}}} {float(valor):g}")

    metrica("netcable_info", "gauge", "NetCable version.", {"version": VERSAO}, 1)
    metrica("netcable_monitor_devices", "gauge", "Devices checked in the last monitor cycle.", {}, _ultimo_ciclo["equipamentos"])
    metrica("netcable_monitor_cycle_seconds", "gauge", "Duration of the last monitor cycle.", {}, _ultimo_ciclo["duracao"])
    for projeto in crud.get_projetos(db):
        equipamentos = [e for e in projeto.equipamentos if crud._monitoravel(e) and e.tipo not in crud.TIPOS_NAO_CONTADOS]
        if not equipamentos:
            continue
        extras = _estado_alertas(db, projeto.id, projeto.equipamentos)
        for e in equipamentos:
            r = {"map": projeto.nome, "device": e.nome, "ip": e.ip, "type": e.tipo, "mode": e.monitor_mode or "ip"}
            x = extras["por_equipamento"].get(e.id, {})
            metrica("netcable_device_up", "gauge", "1 if the device answers, 0 if it is offline.", r, 1 if e.status == "online" else 0)
            metrica("netcable_device_unreachable", "gauge", "1 if the device is offline because its uplink is offline.", r, 1 if x.get("inalcancavel_por") else 0)
            metrica("netcable_device_maintenance", "gauge", "1 if the device (or its map) is in a maintenance window.",
                    r, 1 if (x.get("manutencao_ate") or extras["manutencao_ate"]) else 0)
            metrica("netcable_device_latency_ms", "gauge", "Last response time in milliseconds.", r, e.ping_time if e.status == "online" else None)
            snmp = _metricas.get(e.id) or {}
            metrica("netcable_device_cpu_percent", "gauge", "CPU usage (SNMP).", r, snmp.get("cpu_pct"))
            metrica("netcable_device_memory_percent", "gauge", "Memory usage (SNMP).", r, snmp.get("memoria_pct"))
            metrica("netcable_device_temperature_celsius", "gauge", "Temperature (SNMP).", r, snmp.get("temperatura_c"))
            http = _http.get(e.id) if e.monitor_mode == "http" else None
            if http:
                metrica("netcable_http_status_code", "gauge", "Last HTTP status code.", r, http.get("http_status"))
                metrica("netcable_tls_cert_expiry_days", "gauge", "Days until the TLS certificate expires.", r, (http.get("certificado") or {}).get("dias"))
    return "\n".join(linhas) + "\n"


@router.get("/metrics", include_in_schema=False)
def metricas_prometheus(request: Request, db: Session = Depends(get_db)):
    if not (METRICS_TOKEN or METRICS_PUBLIC):
        raise HTTPException(status_code=404, detail="Not Found")
    if METRICS_TOKEN:
        enviado = request.headers.get("authorization", "")
        if not secrets.compare_digest(enviado.encode(), f"Bearer {METRICS_TOKEN}".encode()):
            raise HTTPException(status_code=401, detail="Credenciais inválidas", headers={"WWW-Authenticate": "Bearer"})
    return Response(montar_metricas_prometheus(db), media_type="text/plain; version=0.0.4; charset=utf-8")
