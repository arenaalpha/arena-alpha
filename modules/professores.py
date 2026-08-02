from .base import Repositorio


class Professores(Repositorio):
    tabela = "professores"
    campos = ("nome", "telefone", "especialidade")

    def cadastrar(self, nome, telefone, especialidade):
        super().cadastrar(nome=nome, telefone=telefone, especialidade=especialidade)
