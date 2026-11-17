"""Configuração comum dos testes: banco e chave secreta numa pasta temporária,
para que importar app.main nunca toque no banco real (nem crie backend/data)."""
import os
import tempfile

os.environ.setdefault("NETCABLE_DATA_DIR", tempfile.mkdtemp(prefix="netcable-testes-"))
os.environ.setdefault("MONITOR_INTERVAL", "0")
os.environ.pop("ADMIN_PASSWORD", None)  # força o fluxo de primeiro acesso nos testes da API


import pytest  # noqa: E402


@pytest.fixture()
def cliente(tmp_path):
    """Admin temporário (removido no fim, para não afetar o teste de primeiro acesso)."""
    from fastapi.testclient import TestClient
    from app import main, crud, models
    from app.database import SessionLocal
    db = SessionLocal()
    user = crud.criar_usuario(db, "backup-admin", main.pwd_context.hash("senha-forte-1"), papel="admin")
    c = TestClient(main.app)
    c.headers["Authorization"] = f"Bearer {main.criar_token({'sub': user.username})}"
    c.headers["Accept-Language"] = "pt"
    crud.salvar_configuracoes(db, {"backup.diretorio": str(tmp_path / "bkp"), "backup.ultimo": "", "backup.ativo": "1"})
    yield c, db
    for p in crud.get_projetos(db):
        crud.deletar_projeto(db, p.id)
    for m in crud.listar_modelos(db):
        crud.deletar_modelo(db, m.id)
    db.query(models.Configuracao).filter(models.Configuracao.chave.like("backup.%") | models.Configuracao.chave.like("alertas.%")).delete(synchronize_session=False)
    db.query(models.Manutencao).delete()
    db.delete(db.get(models.Usuario, user.id))
    db.commit()
    db.close()
