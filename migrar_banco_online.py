"""Copia os dados do banco local da Arena Alpha para o PostgreSQL online."""
import os
import sqlite3
from pathlib import Path


RAIZ = Path(__file__).resolve().parent
URL = os.environ.get("DATABASE_URL", "")
if not URL.startswith(("postgres://", "postgresql://")):
    raise SystemExit("Defina DATABASE_URL com a URL externa do banco online.")

os.environ["DATABASE_URL"] = URL
from database.banco import criar_tabelas  # noqa: E402


def main():
    import psycopg2
    origem = sqlite3.connect(RAIZ / "arena_alpha.db")
    origem.row_factory = sqlite3.Row
    criar_tabelas()
    destino = psycopg2.connect(URL, sslmode="require")
    try:
        tabelas = [linha[0] for linha in origem.execute("SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'")]
        with destino.cursor() as cursor:
            for tabela in tabelas:
                linhas = origem.execute(f"SELECT * FROM {tabela}").fetchall()
                if not linhas:
                    continue
                colunas = list(linhas[0].keys())
                marcadores = ", ".join(["%s"] * len(colunas))
                sql = f"INSERT INTO {tabela} ({', '.join(colunas)}) VALUES ({marcadores}) ON CONFLICT DO NOTHING"
                for linha in linhas:
                    cursor.execute(sql, tuple(linha[coluna] for coluna in colunas))
                if "id" in colunas:
                    cursor.execute(f"SELECT setval(pg_get_serial_sequence('{tabela}', 'id'), COALESCE((SELECT MAX(id) FROM {tabela}), 1), true)")
        destino.commit()
        print("Migração concluída com sucesso.")
    except Exception:
        destino.rollback()
        raise
    finally:
        origem.close()
        destino.close()


if __name__ == "__main__":
    main()
