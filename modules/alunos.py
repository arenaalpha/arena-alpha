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
        cpf = "".join(caractere for caractere in str(dados.get("cpf", "")) if caractere.isdigit())
        whatsapp = "".join(caractere for caractere in str(dados.get("whatsapp", telefone)) if caractere.isdigit())
        with conectar() as banco:
            existentes = banco.execute("SELECT cpf, whatsapp, telefone FROM alunos").fetchall()
        for aluno in existentes:
            cpf_existente = "".join(caractere for caractere in str(aluno["cpf"] or "") if caractere.isdigit())
            whatsapp_existente = "".join(caractere for caractere in str(aluno["whatsapp"] or aluno["telefone"] or "") if caractere.isdigit())
            if cpf and cpf == cpf_existente:
                raise ValueError("Já existe um aluno cadastrado com este CPF.")
            if whatsapp and whatsapp == whatsapp_existente:
                raise ValueError("Já existe um aluno cadastrado com este WhatsApp.")
        registro = {campo: "" for campo in self.campos}
        registro.update(nome=nome, telefone=telefone, modalidade=modalidade, **dados)
        return super().cadastrar(**registro)
