from werkzeug.security import generate_password_hash
import unicodedata
from .base import Repositorio
from database.banco import conectar


class Professores(Repositorio):
    tabela = "professores"
    campos = ("nome", "telefone", "especialidade", "endereco", "usuario", "senha_hash")

    def cadastrar(self, nome, telefone, especialidade="", endereco="", usuario="", senha="12345"):
        base = "".join(c for c in unicodedata.normalize("NFD", nome.lower()) if unicodedata.category(c) != "Mn")
        base = "".join(c for c in base if c.isalnum()) or "professor"
        usuario = usuario.strip() or base
        with conectar() as banco:
            candidato, numero = usuario, 2
            while banco.execute("SELECT id FROM professores WHERE usuario = ?", (candidato,)).fetchone():
                candidato, numero = f"{usuario}{numero}", numero + 1
        return super().cadastrar(nome=nome, telefone=telefone, especialidade=especialidade, endereco=endereco, usuario=candidato, senha_hash=generate_password_hash(senha))

    def garantir_padrao(self):
        with conectar() as banco:
            if banco.execute("SELECT id FROM professores WHERE usuario = ?", ("prof",)).fetchone(): return
        self.cadastrar("Professor Arena Alpha", "", "", "", "prof", "12345")
