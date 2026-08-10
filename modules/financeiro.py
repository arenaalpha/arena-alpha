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
            locacoes = banco.execute(
                "SELECT data, valor FROM agenda WHERE status = 'Confirmada'"
            ).fetchall()
        receitas_locacao = 0.0
        for locacao in locacoes:
            try:
                data_locacao = datetime.strptime(str(locacao["data"]), "%d/%m/%Y").date()
            except ValueError:
                try:
                    data_locacao = datetime.strptime(str(locacao["data"]), "%Y-%m-%d").date()
                except ValueError:
                    continue
            if data_locacao.strftime("%Y-%m") == mes:
                receitas_locacao += float(locacao["valor"] or 0)
        receitas = float(receitas) + receitas_locacao
        despesas = float(despesas)
        return {
            "receitas": receitas,
            "despesas": despesas,
            "saldo": receitas - despesas,
            "pagamentos": quantidade_receitas,
            "locacoes": receitas_locacao,
        }

    def resumo_geral(self):
        """Totais acumulados usados para mostrar o caixa atual da Arena."""
        with conectar() as banco:
            receitas = banco.execute("SELECT COALESCE(SUM(valor), 0) FROM pagamentos WHERE pago_em IS NOT NULL").fetchone()[0]
            despesas = banco.execute("SELECT COALESCE(SUM(valor), 0) FROM despesas").fetchone()[0]
            quantidade_despesas = banco.execute("SELECT COUNT(*) FROM despesas").fetchone()[0]
        receitas, despesas = float(receitas), float(despesas)
        return {
            "receitas": receitas,
            "despesas": despesas,
            "caixa": receitas - despesas,
            "quantidade_despesas": quantidade_despesas,
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
            locacoes = banco.execute(
                """SELECT cliente, tipo_locacao, valor, data, horario FROM agenda
                   WHERE status = 'Confirmada'"""
            ).fetchall()
        itens = [dict(item) for item in receitas] + [dict(item) for item in despesas]
        for locacao in locacoes:
            item = dict(locacao)
            evento = "evento" in str(item.get("tipo_locacao") or "").lower()
            itens.append({
                "descricao": f"{'Evento' if evento else 'Locação por hora'} · {item['cliente']} · {item.get('horario') or '-'}",
                "valor": item["valor"], "data": item["data"], "tipo": "Receita",
                "categoria": "Locação de espaço" if evento else "Locação por hora",
            })
        def ordem(item):
            texto = str(item.get("data") or "")
            for formato in ("%Y-%m-%d", "%d/%m/%Y"):
                try:
                    return datetime.strptime(texto, formato).date().isoformat()
                except ValueError:
                    pass
            return texto
        itens.sort(key=ordem, reverse=True)
        return itens[:limite]

    def relatorio(self):
        resumo = self.resumo_mes()
        return {"receita": resumo["receitas"], "despesas": resumo["despesas"], "saldo": resumo["saldo"]}
