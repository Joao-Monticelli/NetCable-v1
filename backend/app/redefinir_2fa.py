"""Turns off two-factor authentication of a user who lost the phone and the recovery codes
(when no other administrator can do it in ⚙️ → Users).

    python -m app.redefinir_2fa <username>
    docker compose exec netcable python -m app.redefinir_2fa admin
"""

import sys

from . import migracoes, models
from .database import DB_PATH, SessionLocal, engine


def redefinir(username):
    models.Base.metadata.create_all(bind=engine)
    migracoes.aplicar(engine, DB_PATH)  # database of an older version
    db = SessionLocal()
    try:
        user = db.query(models.Usuario).filter(models.Usuario.username == username).first()
        if not user:
            return None
        user.totp_ativo, user.totp_segredo, user.totp_ultimo_passo, user.totp_recuperacao = False, None, None, None
        db.add(models.Auditoria(usuario=username, acao="2fa.removido_cli", detalhe="python -m app.redefinir_2fa"))
        db.commit()
        return user
    finally:
        db.close()


def main(argv=None):
    argv = sys.argv[1:] if argv is None else argv
    if len(argv) != 1:
        print(__doc__.strip(), file=sys.stderr)
        return 2
    if redefinir(argv[0]) is None:
        print(f"User '{argv[0]}' not found.", file=sys.stderr)
        return 1
    print(f"Two-factor authentication turned off for '{argv[0]}'. They can log in with the password and set it up again.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
