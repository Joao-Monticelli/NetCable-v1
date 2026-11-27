"""NetCable API: creates the FastAPI app and plugs in the routers (app/rotas/) and background tasks."""

from fastapi import FastAPI, Depends, HTTPException, Request
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.orm import Session
from sqlalchemy import text
import ping3
import os
from contextlib import asynccontextmanager
import threading
from . import models, alerts  # noqa: F401 (tests use app.main.*)
from .i18n import traduzir, idioma_do_cabecalho
from .database import engine
from . import segredos  # noqa: F401 (tests use app.main.*)
from .segredos import CHAVE_DEV
from fastapi.responses import FileResponse
from .nucleo import (  # noqa: F401 (tests use app.main.*)
    HISTORY_RETENTION_DAYS,
    MONITOR_FAILURE_THRESHOLD,
    MONITOR_INTERVAL,
    SECRET_KEY,
    VERSAO,
    _recifrar_segredos_antigos,
    abrir_config,
    criar_token,
    get_canais_config,
    get_db,
    get_smtp_config,
    iso_utc,
    pwd_context,
)
from .monitoramento import (  # noqa: F401 (tests use app.main.*)
    SNMP_METRICS_INTERVAL,
    _http,
    _limites_estado,
    _loop_metricas,
    _loop_monitoramento,
    _loop_relatorios,
    _metricas,
    _monitor_stop,
    _offline_desde,
    _sonda_icmp,
    _ultimo_ciclo,
    avaliar_certificado,
    avaliar_limites,
    lembretes_offline,
    ping_equipamento,
    registrar_monitoramento,
    verificar_backup_agendado,
)
from .rotas.contas import ADMIN_PASSWORD, LOGIN_MAX_FAILURES, login_failures  # noqa: F401 (tests use app.main.*)
from .rotas.mapas import _cache_status  # noqa: F401 (tests use app.main.*)
from .rotas import contas, configuracoes, mapas, rede, prometheus, incidentes


@asynccontextmanager
async def ciclo_de_vida(_app):
    """Starts the background threads with the API and stops the monitor on shutdown."""
    iniciar_tarefas()
    yield
    parar_tarefas()


app = FastAPI(title="NetCable API", version=VERSAO, lifespan=ciclo_de_vida)


ALLOWED_ORIGINS = [origin.strip() for origin in os.getenv("ALLOWED_ORIGINS", "").split(",") if origin.strip()]


app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS or ["http://localhost", "http://localhost:3080", "http://localhost:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.exception_handler(StarletteHTTPException)
async def erro_traduzido(request: Request, exc: StarletteHTTPException):
    """Devolve a mensagem de erro no idioma da interface (cabeçalho Accept-Language)."""
    idioma = idioma_do_cabecalho(request.headers.get("accept-language"))
    return JSONResponse({"detail": traduzir(exc.detail, idioma)}, status_code=exc.status_code, headers=getattr(exc, "headers", None))


@app.middleware("http")
async def security_headers(request: Request, call_next):
    response = await call_next(request)
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["Referrer-Policy"] = "same-origin"
    return response


@app.get("/api/health")
def health_check(db: Session = Depends(get_db)):
    database_ok = False
    database_error = None
    try:
        db.execute(text("SELECT 1"))
        database_ok = True
    except Exception as exc:
        database_error = str(exc)
    try:
        from .snmp_service import _hlapi
        _hlapi()
        snmp = {"installed": True, "status": "ready"}
    except Exception as exc:
        snmp = {"installed": False, "status": "unavailable", "detail": str(exc)}
    return {
        "status": "ok" if database_ok else "degraded",
        "api": "online",
        "version": VERSAO,
        "database": {"connected": database_ok, "error": database_error},
        "snmp": snmp,
        "database_path": str(engine.url.database),
        "monitor": {
            "enabled": MONITOR_INTERVAL > 0,
            "interval": MONITOR_INTERVAL,
            "failure_threshold": MONITOR_FAILURE_THRESHOLD,
            "last_cycle": iso_utc(_ultimo_ciclo["fim"]),
            "last_cycle_seconds": _ultimo_ciclo["duracao"],
            "equipments": _ultimo_ciclo["equipamentos"],
        },
        "alerts": alerts.canais_configurados(get_smtp_config(db), get_canais_config(db)) if database_ok else {},
        "history_retention_days": HISTORY_RETENTION_DAYS,
        "security": {
            "secret_key_configured": SECRET_KEY != CHAVE_DEV,
            "default_admin_password": (ADMIN_PASSWORD or "") in {"admin", "altere_esta_senha"},
        },
    }


def iniciar_tarefas():
    if MONITOR_INTERVAL > 0:
        threading.Thread(target=_loop_monitoramento, name="netcable-monitor", daemon=True).start()
        if SNMP_METRICS_INTERVAL > 0:
            threading.Thread(target=_loop_metricas, name="netcable-metricas", daemon=True).start()
    threading.Thread(target=_loop_relatorios, name="netcable-relatorios", daemon=True).start()


def parar_tarefas():
    _monitor_stop.set()


app.include_router(contas.router)
app.include_router(configuracoes.router)
app.include_router(mapas.router)
app.include_router(rede.router)
app.include_router(prometheus.router)
app.include_router(incidentes.router)


# --- INTERFACE WEB (imagem única) ---
# Quando a pasta com o build do frontend existe (imagem Docker única, versão Windows),
# o próprio backend serve a interface: uma porta só para tudo. No desenvolvimento
# (Vite em 5173) e na imagem separada (Nginx) esta parte simplesmente não é ativada.
PASTA_WEB = os.path.abspath(os.getenv("NETCABLE_STATIC_DIR") or os.path.join(os.path.dirname(__file__), "..", "static"))


if os.path.isfile(os.path.join(PASTA_WEB, "index.html")):
    @app.get("/{caminho:path}", include_in_schema=False)
    def interface_web(caminho: str):
        if caminho.startswith("api/") or caminho == "api":
            raise HTTPException(status_code=404, detail="Not Found")
        arquivo = os.path.abspath(os.path.join(PASTA_WEB, caminho))
        if caminho and arquivo.startswith(PASTA_WEB + os.sep) and os.path.isfile(arquivo):
            # Arquivos com hash no nome (assets/) nunca mudam: cache longo.
            cache = "public, max-age=31536000, immutable" if caminho.startswith("assets/") else "no-cache"
            return FileResponse(arquivo, headers={"Cache-Control": cache})
        # Rotas do React (/projects, /editor/1, /share/...) recebem o index.html.
        return FileResponse(os.path.join(PASTA_WEB, "index.html"), headers={"Cache-Control": "no-cache"})
