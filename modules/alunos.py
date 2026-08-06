from .base import Repositorio
from database.banco import conectar


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

    def atualizar(self, identificador, **dados):
        registro = {campo: str(dados.get(campo, "")).strip() for campo in self.campos}
        registro["cpf"] = "".join(caractere for caractere in registro["cpf"] if caractere.isdigit())
        registro["whatsapp"] = "".join(caractere for caractere in registro["whatsapp"] if caractere.isdigit())
        registro["telefone"] = "".join(caractere for caractere in registro["telefone"] if caractere.isdigit()) or registro["whatsapp"]
        with conectar() as banco:
            atual = banco.execute("SELECT id FROM alunos WHERE id = ?", (identificador,)).fetchone()
            if atual is None:
                raise ValueError("Aluno não encontrado.")
            existentes = banco.execute("SELECT id, cpf, whatsapp, telefone FROM alunos WHERE id <> ?", (identificador,)).fetchall()
            for aluno in existentes:
                cpf = "".join(c for c in str(aluno["cpf"] or "") if c.isdigit())
                whatsapp = "".join(c for c in str(aluno["whatsapp"] or aluno["telefone"] or "") if c.isdigit())
                if registro["cpf"] and registro["cpf"] == cpf:
                    raise ValueError("Já existe outro aluno cadastrado com este CPF.")
                if registro["whatsapp"] and registro["whatsapp"] == whatsapp:
                    raise ValueError("Já existe outro aluno cadastrado com este WhatsApp.")
            atualizacoes = ", ".join(f"{campo} = ?" for campo in self.campos)
            banco.execute(f"UPDATE alunos SET {atualizacoes} WHERE id = ?", (*[registro[campo] for campo in self.campos], identificador))
