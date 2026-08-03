from datetime import date, datetime

from database.banco import conectar


class Financeiro:
    def excluir(self, identificador):
        with conectar() as banco:
            resultado = banco.execute("DELETE FROM despesas WHERE id = ?", (identificador,))
        if resultado.rowcount == 0:
            raise ValueError("Despesa nao encontrada.")

    def listar(self):
        with conectar() as banco:
            return banco.execute("SELECT * FROM despesas ORDER BY id DESC").fetchall()

    @staticmethod
    def _data_iso(data_texto):
        if isinstance(data_texto, date):
            return data_texto.isoformat()
        return datetime.strptime(data_texto, "%d/%m/%Y").date().isoformat()

    def registrar_despesa(self, descricao, categoria, valor, data, observacao=""):
        try:
            valor = float(str(valor).replace(",", "."))
        except ValueError:
            raise ValueError("Informe um valor numerico para a despesa.")
        if valor <= 0:
            raise ValueError("A despesa deve ser maior que zero.")
        if not descricao.strip():
            raise ValueError("Informe a descricao da despesa.")
        data_iso = self._data_iso(data)
        with conectar() as banco:
            banco.execute(
                """INSERT INTO despesas (descricao, categoria, valor, data, observacao)
                   VALUES (?, ?, ?, ?, ?)""",
                (descricao.strip(), categoria, valor, data_iso, observacao.strip()),
            )

    def resumo_mes(self, referencia=None):
        referencia = referencia or date.today()
        mes = referencia.strftime("%Y-%m")
        with conectar() as banco:
            receitas = banco.execute(
                "SELECT COALESCE(SUM(valor), 0) FROM pagamentos WHERE substr(pago_em, 1, 7) = ?", (mes,)
            ).fetchone()[0]
            despesas = banco.execute(
                "SELECT COALESCE(SUM(valor), 0) FROM despesas WHERE substr(data, 1, 7) = ?", (mes,)
            ).fetchone()[0]
            quantidade_receitas = banco.execute(
                "SELECT COUNT(*) FROM pagamentos WHERE substr(pago_em, 1, 7) = ?", (mes,)
            ).fetchone()[0]
        receitas = float(receitas)
        despesas = float(despesas)
        return {
            "receitas": receitas,
            "despesas": despesas,
            "saldo": receitas - despesas,
            "pagamentos": quantidade_receitas,
        }

    def lancamentos_recentes(self, limite=20):
        with conectar() as banco:
            receitas = banco.execute(
                """SELECT aluno AS descricao, valor, pago_em AS data, 'Receita' AS tipo,
                   'Mensalidade' AS categoria FROM pagamentos
                   WHERE pago_em IS NOT NULL"""
            ).fetchall()
            despesas = banco.execute(
                "SELECT descricao, valor, data, 'Despesa' AS tipo, categoria FROM despesas"
            ).fetchall()
        itens = [dict(item) for item in receitas] + [dict(item) for item in despesas]
        itens.sort(key=lambda item: item["data"] or "", reverse=True)
        return itens[:limite]

    def relatorio(self):
        resumo = self.resumo_mes()
        return {"receita": resumo["receitas"], "despesas": resumo["despesas"], "saldo": resumo["saldo"]}
