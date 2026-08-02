from .base import Repositorio


class Alunos(Repositorio):
    tabela = "alunos"
    campos = (
        "nome", "telefone", "modalidade", "data_nascimento", "cpf", "endereco",
        "esporte", "frequencia", "valor_plano", "como_conheceu",
        "restricoes_alimentares", "problema_saude", "necessidades_especiais",
        "menor_idade", "responsavel_nome", "responsavel_cpf",
        "responsavel_parentesco", "autorizacao_imagem",
        "data_inscricao", "dia_vencimento",
        "whatsapp",
    )

    def cadastrar(self, nome, telefone="", modalidade="", **dados):
        registro = {campo: "" for campo in self.campos}
        registro.update(nome=nome, telefone=telefone, modalidade=modalidade, **dados)
        return super().cadastrar(**registro)
