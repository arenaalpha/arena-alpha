from werkzeug.security import generate_password_hash
from .base import Repositorio
from database.banco import conectar


class Professores(Repositorio):
    tabela = "professores"
    campos = ("nome", "telefone", "especialidade", "endereco", "usuario", "senha_hash")

    def cadastrar(self, nome, telefone, especialidade="", endereco="", usuario="prof", senha="12345"):
        with conectar() as banco:
            if banco.execute("SELECT id FROM professores WHERE usuario = ?", (usuario.strip(),)).fetchone():
                raise ValueError("Este usuário de professor já existe.")
        return super().cadastrar(nome=nome, telefone=telefone, especialidade=especialidade, endereco=endereco, usuario=usuario.strip(), senha_hash=generate_password_hash(senha))

    def garantir_padrao(self):
        with conectar() as banco:
            if banco.execute("SELECT id FROM professores WHERE usuario = ?", ("prof",)).fetchone(): return
        self.cadastrar("Professor Arena Alpha", "", "", "", "prof", "12345")
