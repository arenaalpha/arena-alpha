from .base import Repositorio


class Quadras(Repositorio):
    tabela = "quadras"
    campos = ("nome", "modalidade")

    def cadastrar(self, nome, modalidade):
        if self.listar():
            raise ValueError("A Arena Alpha possui apenas uma quadra.")
        super().cadastrar(nome=nome, modalidade=modalidade)
