import calendar
from datetime import date, datetime

from database.banco import conectar


class Pagamentos:
    def excluir(self, identificador):
        with conectar() as banco:
            resultado = banco.execute("DELETE FROM pagamentos WHERE id = ?", (identificador,))
        if resultado.rowcount == 0:
            raise ValueError("Pagamento nao encontrado.")

    def _vencimento_do_mes(self, dia_vencimento, referencia):
        ultimo_dia = calendar.monthrange(referencia.year, referencia.month)[1]
        return date(referencia.year, referencia.month, min(int(dia_vencimento), ultimo_dia))

    def alunos_com_plano(self):
        with conectar() as banco:
            return banco.execute(
                """SELECT id, nome, whatsapp, esporte, frequencia, valor_plano, data_inscricao, dia_vencimento
                   FROM alunos WHERE valor_plano IS NOT NULL AND dia_vencimento IS NOT NULL
                   ORDER BY nome"""
            ).fetchall()

    def registrar_mensalidade(self, aluno_id, data_pagamento):
        if isinstance(data_pagamento, str):
            data_pagamento = datetime.strptime(data_pagamento, "%d/%m/%Y").date()
        with conectar() as banco:
            aluno = banco.execute(
                "SELECT * FROM alunos WHERE id = ?", (aluno_id,)
            ).fetchone()
            if aluno is None:
                raise ValueError("Aluno nao encontrado.")
            if aluno["valor_plano"] is None or aluno["dia_vencimento"] is None:
                raise ValueError("Este aluno nao possui plano ou vencimento configurado.")
            vencimento = self._vencimento_do_mes(aluno["dia_vencimento"], data_pagamento)
            valor_original = float(aluno["valor_plano"])
            em_dia = data_pagamento <= vencimento
            desconto = 20.0 if aluno["esporte"] == "Volei de areia" and em_dia else 0.0
            valor_final = max(valor_original - desconto, 0.0)
            status = "Pago em dia" if em_dia else "Pago em atraso"
            banco.execute(
                """INSERT INTO pagamentos
                   (aluno, valor, data, aluno_id, data_vencimento, valor_original, desconto, pago_em, status)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    aluno["nome"], valor_final, data_pagamento.strftime("%d/%m/%Y"), aluno_id,
                    vencimento.isoformat(), valor_original, desconto,
                    data_pagamento.isoformat(), status,
                ),
            )
        return {
            "nome": aluno["nome"], "vencimento": vencimento, "valor_original": valor_original,
            "desconto": desconto, "valor_final": valor_final, "status": status,
        }

    def situacao_atual(self, referencia=None):
        referencia = referencia or date.today()
        alunos = self.alunos_com_plano()
        resultado = []
        with conectar() as banco:
            for aluno in alunos:
                vencimento = self._vencimento_do_mes(aluno["dia_vencimento"], referencia)
                pagamento = banco.execute(
                    """SELECT status, pago_em, valor FROM pagamentos
                       WHERE aluno_id = ? AND substr(pago_em, 1, 7) = ?
                       ORDER BY id DESC LIMIT 1""",
                    (aluno["id"], referencia.strftime("%Y-%m")),
                ).fetchone()
                if pagamento:
                    status = pagamento["status"]
                    pago_em = pagamento["pago_em"]
                elif referencia > vencimento:
                    status = "Em atraso"
                    pago_em = "-"
                else:
                    status = "Pendente"
                    pago_em = "-"
                resultado.append({
                    "aluno": aluno, "vencimento": vencimento, "status": status, "pago_em": pago_em,
                })
        return resultado
