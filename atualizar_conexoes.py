"""Atualizador seguro da conexão online da Arena Alpha."""
import ctypes
import os
import sys


def avisar(titulo, mensagem, erro=False):
    estilo = 0x10 if erro else 0x40
    ctypes.windll.user32.MessageBoxW(None, mensagem, titulo, estilo)


def carregar_conexao_do_windows():
    if os.environ.get("DATABASE_URL"):
        return True
    try:
        import winreg
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, "Environment") as chave:
            os.environ["DATABASE_URL"] = winreg.QueryValueEx(chave, "DATABASE_URL")[0]
        return bool(os.environ["DATABASE_URL"])
    except (FileNotFoundError, OSError):
        return False


def main():
    if not carregar_conexao_do_windows():
        avisar("Arena Alpha", "A conexão online ainda não foi configurada neste computador.", True)
        return 1
    try:
        from database.banco import conectar, criar_tabelas, USAR_POSTGRES
        if not USAR_POSTGRES:
            raise ValueError("A conexão online não foi reconhecida.")
        criar_tabelas()
        with conectar() as banco:
            quantidade = banco.execute("SELECT COUNT(*) AS quantidade FROM alunos").fetchone()["quantidade"]
        avisar("Arena Alpha", f"Conexões atualizadas com sucesso.\nBanco online ativo com {quantidade} aluno(s) cadastrado(s).")
        return 0
    except Exception:
        avisar("Arena Alpha", "Não foi possível conectar ao banco online. Verifique a internet e tente novamente.", True)
        return 1


if __name__ == "__main__":
    sys.exit(main())
