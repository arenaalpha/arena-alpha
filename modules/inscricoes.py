from datetime import date

from database.banco import conectar
from .alunos import Alunos
from .turmas import Turmas


class Inscricoes:
    """Inscrições feitas no portal, aguardando confirmação pelo WhatsApp."""

    campos = Alunos.campos

    def pendentes(self):
        with conectar() as banco:
            return banco.execute("SELECT * FROM inscricoes_portal WHERE status = ? ORDER BY id DESC", ("Pendente",)).fetchall()

    def criar(self, dados, turma_id):
        registro = {campo: str(dados.get(campo, "")).strip() for campo in self.campos}
        registro["cpf"] = "".join(c for c in registro["cpf"] if c.isdigit())
        registro["whatsapp"] = "".join(c for c in registro["whatsapp"] if c.isdigit())
        registro["telefone"] = registro["whatsapp"]
        if not registro["cpf"] or not registro["whatsapp"]:
            raise ValueError("Informe CPF e WhatsApp válidos.")
        with conectar() as banco:
            existentes = banco.execute("SELECT cpf, whatsapp, telefone FROM alunos").fetchall()
            pendentes = banco.execute("SELECT cpf, whatsapp FROM inscricoes_portal WHERE status = ?", ("Pendente",)).fetchall()
            for item in list(existentes) + list(pendentes):
                cpf = "".join(c for c in str(item["cpf"] or "") if c.isdigit())
                whatsapp = "".join(c for c in str(item["whatsapp"] or item["telefone"] or "") if c.isdigit())
                if registro["cpf"] == cpf:
                    raise ValueError("Já existe uma inscrição ou aluno com este CPF.")
                if registro["whatsapp"] == whatsapp:
                    raise ValueError("Já existe uma inscrição ou aluno com este WhatsApp.")
            if banco.execute("SELECT id FROM turmas WHERE id = ?", (turma_id,)).fetchone() is None:
                raise ValueError("A turma escolhida não está mais disponível.")
            colunas = ", ".join((*self.campos, "turma_id", "status", "criada_em"))
            marcadores = ", ".join("?" for _ in range(len(self.campos) + 3))
            resultado = banco.execute(f"INSERT INTO inscricoes_portal ({colunas}) VALUES ({marcadores})", (*[registro[campo] for campo in self.campos], turma_id, "Pendente", date.today().isoformat()))
        return resultado.lastrowid

    def confirmar(self, inscricao_id):
        with conectar() as banco:
            inscricao = banco.execute("SELECT * FROM inscricoes_portal WHERE id = ? AND status = ?", (inscricao_id, "Pendente")).fetchone()
            if inscricao is None:
                raise ValueError("Inscrição pendente não encontrada.")
            dados = {campo: inscricao[campo] or "" for campo in self.campos}
            aluno_id = Alunos().cadastrar(**dados)
            turma = banco.execute("SELECT * FROM turmas WHERE id = ?", (inscricao["turma_id"],)).fetchone()
            if turma is None:
                raise ValueError("A turma desta inscrição não existe mais.")
            dia = turma["dia_semana"] if dados["frequencia"].startswith("1x") else "Todos os dias da turma"
            Turmas().vincular_aluno(aluno_id, turma["id"], dia)
            banco.execute("UPDATE inscricoes_portal SET status = ? WHERE id = ?", ("Confirmada", inscricao_id))
        return dados["nome"]
