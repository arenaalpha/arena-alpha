from datetime import date, datetime, timedelta
import unicodedata

from database.banco import conectar, normalizar_telefone_brasil


class AulasExperimentais:
    @staticmethod
    def _normalizar(texto):
        return "".join(
            caractere for caractere in unicodedata.normalize("NFD", texto.lower())
            if unicodedata.category(caractere) != "Mn"
        )

    def agendar(self, nome, telefone, esporte, data, horario="", turma=""):
        try:
            data_aula = datetime.strptime(data, "%d/%m/%Y").date()
        except ValueError:
            raise ValueError("Informe a data no formato dd/mm/aaaa.")
        if data_aula < date.today() or data_aula > date.today() + timedelta(days=30):
            raise ValueError("A aula experimental pode ser agendada somente para os próximos 30 dias.")
        esporte_normalizado = self._normalizar(esporte)
        if "volei" in esporte_normalizado and "fut" not in esporte_normalizado and data_aula.weekday() != 0:
            raise ValueError("A aula experimental de Volei de Areia acontece somente as segundas-feiras.")
        if not nome.strip() or not telefone.strip():
            raise ValueError("Informe o nome completo e o telefone.")
        with conectar() as banco:
            resultado = banco.execute(
                """INSERT INTO aulas_experimentais (nome, telefone, esporte, data, horario, turma)
                   VALUES (?, ?, ?, ?, ?, ?)""",
                (nome.strip(), normalizar_telefone_brasil(telefone), esporte, data_aula.isoformat(), horario.strip(), turma.strip()),
            )
        return resultado.lastrowid

    def listar(self):
        with conectar() as banco:
            return banco.execute("SELECT * FROM aulas_experimentais ORDER BY data DESC, id DESC").fetchall()

    def marcar_confirmacao(self, identificador):
        with conectar() as banco:
            banco.execute("UPDATE aulas_experimentais SET confirmacao_enviada = 1 WHERE id = ?", (identificador,))

    def marcar_resultado(self, identificador, resultado):
        opcoes = {"Fez aula - sem inscrição", "Faltou aula experimental", "Aula experimental cancelada"}
        if resultado not in opcoes:
            raise ValueError("Resultado da aula experimental inválido.")
        with conectar() as banco:
            registro = banco.execute(
                "UPDATE aulas_experimentais SET resultado = ?, resultado_em = ? WHERE id = ? AND confirmacao_enviada = 1",
                (resultado, datetime.now().isoformat(timespec="seconds"), identificador),
            )
        if registro.rowcount == 0:
            raise ValueError("Aula experimental não encontrada ou ainda não confirmada.")

    def limpar_historico(self):
        with conectar() as banco:
            banco.execute("DELETE FROM aulas_experimentais")

    def excluir(self, identificador):
        with conectar() as banco:
            resultado = banco.execute("DELETE FROM aulas_experimentais WHERE id = ?", (identificador,))
        if resultado.rowcount == 0:
            raise ValueError("Aula experimental não encontrada.")

    def limpar_vencidas(self):
        """Remove automaticamente os agendamentos cuja data já passou."""
        with conectar() as banco:
            resultado = banco.execute(
                "DELETE FROM aulas_experimentais WHERE data < ? AND COALESCE(resultado, '') = ''", (date.today().isoformat(),)
            )
        return resultado.rowcount
