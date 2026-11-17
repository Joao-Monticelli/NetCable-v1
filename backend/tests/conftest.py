"""Configuração comum dos testes: banco e chave secreta numa pasta temporária,
para que importar app.main nunca toque no banco real (nem crie backend/data)."""
import os
import tempfile

os.environ.setdefault("NETCABLE_DATA_DIR", tempfile.mkdtemp(prefix="netcable-testes-"))
os.environ.setdefault("MONITOR_INTERVAL", "0")
os.environ.pop("ADMIN_PASSWORD", None)  # força o fluxo de primeiro acesso nos testes da API
