from .base import Repositorio


class Torneios(Repositorio):
    tabela = "torneios"
    campos = ("nome", "data", "modalidade")

    def criar(self, nome, data, modalidade):
        super().cadastrar(nome=nome, data=data, modalidade=modalidade)
