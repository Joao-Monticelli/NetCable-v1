from sqlalchemy import create_engine
from sqlalchemy.orm import declarative_base, sessionmaker
import os

# Pasta de dados (banco, chave secreta e backups). No Docker é o volume /app/data;
# fora dele (ex.: Windows) pode ser apontada para outro lugar com NETCABLE_DATA_DIR.
DATA_DIR = os.path.abspath(os.getenv("NETCABLE_DATA_DIR", "./data"))
os.makedirs(DATA_DIR, exist_ok=True)
DB_PATH = os.path.join(DATA_DIR, "netcable.db")

SQLALCHEMY_DATABASE_URL = f"sqlite:///{DB_PATH}"

engine = create_engine(
    SQLALCHEMY_DATABASE_URL, connect_args={"check_same_thread": False}
)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

Base = declarative_base()
