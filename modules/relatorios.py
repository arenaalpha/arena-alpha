from database.banco import conectar


class Relatorios:
    def total_alunos(self):
        with conectar() as banco:
            return banco.execute("SELECT COUNT(*) FROM alunos").fetchone()[0]

    def total_receita(self):
        with conectar() as banco:
            return banco.execute("SELECT COALESCE(SUM(valor), 0) FROM pagamentos").fetchone()[0]
