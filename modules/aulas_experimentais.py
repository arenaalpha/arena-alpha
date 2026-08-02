from datetime import datetime
import unicodedata

from database.banco import conectar


class AulasExperimentais:
    @staticmethod
    def _normalizar(texto):
        return "".join(
            caractere for caractere in unicodedata.normalize("NFD", texto.lower())
            if unicodedata.category(caractere) != "Mn"
        )

    def agendar(self, nome, telefone, esporte, data, horario=""):
        try:
            data_aula = datetime.strptime(data, "%d/%m/%Y").date()
        except ValueError:
            raise ValueError("Informe a data no formato dd/mm/aaaa.")
        esporte_normalizado = self._normalizar(esporte)
        if "volei" in esporte_normalizado and "fut" not in esporte_normalizado and data_aula.weekday() != 0:
            raise ValueError("A aula experimental de Volei de Areia acontece somente as segundas-feiras.")
        if not nome.strip() or not telefone.strip():
            raise ValueError("Informe o nome completo e o telefone.")
        with conectar() as banco:
            resultado = banco.execute(
                """INSERT INTO aulas_experimentais (nome, telefone, esporte, data, horario)
                   VALUES (?, ?, ?, ?, ?)""",
                (nome.strip(), telefone.strip(), esporte, data_aula.isoformat(), horario.strip()),
            )
        return resultado.lastrowid

    def listar(self):
        with conectar() as banco:
            return banco.execute("SELECT * FROM aulas_experimentais ORDER BY data DESC, id DESC").fetchall()

    def marcar_confirmacao(self, identificador):
        with conectar() as banco:
            banco.execute("UPDATE aulas_experimentais SET confirmacao_enviada = 1 WHERE id = ?", (identificador,))
