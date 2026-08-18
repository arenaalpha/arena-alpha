from datetime import date

from database.banco import conectar
from .base import Repositorio


class Turmas(Repositorio):
    tabela = "turmas"
    campos = ("nome", "dia_semana", "dia_semana_2", "horario", "professor", "modalidade")

    def criar(self, nome, dia_semana, dia_semana_2, horario, professor, modalidade):
        dia_semana = (dia_semana or "").strip()
        dia_semana_2 = (dia_semana_2 or "").strip()
        if dia_semana_2.lower() in ("não tem segundo dia", "nao tem segundo dia"):
            dia_semana_2 = ""
        if not dia_semana:
            raise ValueError("Escolha o primeiro dia da turma.")
        if dia_semana_2 and dia_semana == dia_semana_2:
            raise ValueError("Escolha dois dias da semana diferentes para a turma.")
        super().cadastrar(nome=nome, dia_semana=dia_semana, dia_semana_2=dia_semana_2, horario=horario, professor=professor, modalidade=modalidade)

    def atualizar_status_aula(self, turma_id, status, aviso=""):
        if status not in ("Normal", "Aula cancelada"):
            raise ValueError("Status de aula invalido.")
        if status == "Aula cancelada" and not aviso.strip():
            raise ValueError("Digite um aviso para o cancelamento.")
        with conectar() as banco:
            banco.execute("UPDATE turmas SET status_aula = ?, aviso_aula = ? WHERE id = ?", (status, aviso.strip(), turma_id))

    def atualizar_configuracao(self, turma_id, nome, modalidade, descricao, dia_semana, dia_semana_2, horario, professor, valor_1x, valor_2x, valor_diaria):
        valores = (float(valor_1x or 0), float(valor_2x or 0), float(valor_diaria or 0))
        if any(valor < 0 for valor in valores):
            raise ValueError("Os valores da turma não podem ser negativos.")
        with conectar() as banco:
            banco.execute(
                """UPDATE turmas SET nome=?, modalidade=?, descricao=?, dia_semana=?, dia_semana_2=?, horario=?, professor=?, valor_1x=?, valor_2x=?, valor_diaria=? WHERE id=?""",
                (nome.strip(), modalidade.strip(), descricao.strip(), dia_semana.strip(), dia_semana_2.strip(), horario.strip(), professor.strip(), *valores, turma_id),
            )
            for frequencia, valor in (("1x%", valores[0]), ("2x%", valores[1]), ("Diaria%", valores[2])):
                if valor > 0:
                    banco.execute("""UPDATE alunos SET valor_plano=? WHERE id IN (SELECT aluno_id FROM matriculas_turma WHERE turma_id=?) AND frequencia LIKE ?""", (valor, turma_id, frequencia))

    def vincular_aluno(self, aluno_id, turma_id, dia_treino):
        with conectar() as banco:
            aluno = banco.execute("SELECT nome, frequencia FROM alunos WHERE id = ?", (aluno_id,)).fetchone()
            turma = banco.execute("SELECT dia_semana, dia_semana_2 FROM turmas WHERE id = ?", (turma_id,)).fetchone()
            if aluno is None or turma is None:
                raise ValueError("Aluno ou turma nao encontrado.")
            dias_turma = {turma["dia_semana"], turma["dia_semana_2"]}
            plano_uma_vez = (aluno["frequencia"] or "").startswith("1x")
            if plano_uma_vez and dia_treino not in dias_turma:
                raise ValueError("Para plano 1x por semana, escolha um dos dias da turma.")
            if not plano_uma_vez:
                dia_treino = "Todos os dias da turma"
            try:
                banco.execute(
                    "INSERT INTO matriculas_turma (aluno_id, turma_id, dia_treino) VALUES (?, ?, ?)",
                    (aluno_id, turma_id, dia_treino),
                )
            except Exception as erro:
                if "UNIQUE" in str(erro).upper():
                    raise ValueError("Este aluno ja esta vinculado a esta turma.")
                raise

    def matriculas_do_dia(self, referencia=None):
        referencia = referencia or date.today()
        dias = ["Segunda-feira", "Terca-feira", "Quarta-feira", "Quinta-feira", "Sexta-feira", "Sabado", "Domingo"]
        hoje = dias[referencia.weekday()]
        with conectar() as banco:
            registros = banco.execute(
                """SELECT m.id AS matricula_id, a.nome AS aluno, a.frequencia, t.nome AS turma,
                   t.horario, m.dia_treino,
                   EXISTS(SELECT 1 FROM presencas p WHERE p.matricula_id = m.id AND p.data = ?) AS presente
                   FROM matriculas_turma m
                   JOIN alunos a ON a.id = m.aluno_id
                   JOIN turmas t ON t.id = m.turma_id
                   WHERE m.dia_treino = ?
                      OR (m.dia_treino = 'Todos os dias da turma' AND (t.dia_semana = ? OR t.dia_semana_2 = ?))
                   ORDER BY t.horario, a.nome""",
                (referencia.isoformat(), hoje, hoje, hoje),
            ).fetchall()
        return registros

    def registrar_checkin(self, matricula_id, referencia=None):
        referencia = referencia or date.today()
        with conectar() as banco:
            try:
                banco.execute(
                    "INSERT INTO presencas (matricula_id, data) VALUES (?, ?)",
                    (matricula_id, referencia.isoformat()),
                )
            except Exception as erro:
                if "UNIQUE" in str(erro).upper():
                    raise ValueError("O check-in deste aluno ja foi registrado hoje.")
                raise

    def alunos_da_turma(self, turma_id):
        with conectar() as banco:
            return banco.execute(
                """SELECT a.id, a.nome, a.whatsapp, a.esporte, a.frequencia, a.data_nascimento, m.dia_treino
                   FROM matriculas_turma m
                   JOIN alunos a ON a.id = m.aluno_id
                   WHERE m.turma_id = ? ORDER BY a.nome""",
                (turma_id,),
            ).fetchall()

    def turma_do_aluno(self, aluno_id):
        with conectar() as banco:
            return banco.execute(
                """SELECT t.id, t.nome, t.horario, t.modalidade, m.dia_treino
                   FROM matriculas_turma m JOIN turmas t ON t.id = m.turma_id
                   WHERE m.aluno_id = ? ORDER BY m.id LIMIT 1""", (aluno_id,)
            ).fetchone()

    def transferir_aluno(self, aluno_id, turma_id, frequencia):
        with conectar() as banco:
            turma = banco.execute("SELECT id, dia_semana FROM turmas WHERE id = ?", (turma_id,)).fetchone()
            if turma is None:
                raise ValueError("Turma selecionada não encontrada.")
            banco.execute("DELETE FROM matriculas_turma WHERE aluno_id = ?", (aluno_id,))
            dia_treino = turma["dia_semana"] if (frequencia or "").startswith("1x") else "Todos os dias da turma"
            banco.execute("INSERT INTO matriculas_turma (aluno_id, turma_id, dia_treino) VALUES (?, ?, ?)", (aluno_id, turma_id, dia_treino))

    def resumo_financeiro(self, status_por_aluno):
        with conectar() as banco:
            linhas = banco.execute(
                """SELECT t.id AS turma_id, a.id AS aluno_id
                   FROM turmas t LEFT JOIN matriculas_turma m ON m.turma_id = t.id
                   LEFT JOIN alunos a ON a.id = m.aluno_id"""
            ).fetchall()
        resumo = {}
        for linha in linhas:
            item = resumo.setdefault(linha["turma_id"], {"total_alunos": 0, "pagos": 0, "em_atraso": 0})
            if linha["aluno_id"] is None:
                continue
            item["total_alunos"] += 1
            status = status_por_aluno.get(linha["aluno_id"], "Pendente")
            if str(status).startswith("Pago"):
                item["pagos"] += 1
            elif status == "Em atraso":
                item["em_atraso"] += 1
        return resumo
