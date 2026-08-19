from datetime import date, datetime

from database.banco import conectar


class ComissoesProfessor:
    """Comissões de 50% exclusivas das turmas de Futvôlei."""

    percentual = 0.50

    def _pagamentos_do_professor(self, professor_id, referencia=None):
        referencia = referencia or date.today()
        mes = referencia.strftime("%Y-%m")
        with conectar() as banco:
            professor = banco.execute("SELECT id, nome FROM professores WHERE id = ?", (professor_id,)).fetchone()
            if professor is None:
                raise ValueError("Professor não encontrado.")
            pagamentos = banco.execute(
                """SELECT DISTINCT p.id AS pagamento_id, p.aluno, p.valor, p.pago_em,
                          a.nome AS aluno_nome, t.nome AS turma, t.modalidade,
                          cp.status AS comissao_status, cp.valor AS comissao_registrada, cp.pago_em AS comissao_paga_em
                   FROM pagamentos p
                   JOIN alunos a ON a.id = p.aluno_id
                   JOIN matriculas_turma m ON m.aluno_id = a.id
                   JOIN turmas t ON t.id = m.turma_id
                   LEFT JOIN comissoes_professores cp ON cp.professor_id = ? AND cp.pagamento_id = p.id
                   WHERE substr(COALESCE(p.pago_em, ''), 1, 7) = ?
                     AND lower(COALESCE(t.modalidade, '')) LIKE ?
                     AND (
                        EXISTS(SELECT 1 FROM professor_turmas pt WHERE pt.turma_id = t.id AND pt.professor_id = ?)
                        OR (
                            NOT EXISTS(SELECT 1 FROM professor_turmas pt2 WHERE pt2.turma_id = t.id)
                            AND lower(COALESCE(t.professor, '')) = lower(?)
                        )
                     )
                   ORDER BY p.pago_em DESC, p.id DESC""",
                (professor_id, mes, "%fut%", professor_id, professor["nome"]),
            ).fetchall()
        itens = []
        for pagamento in pagamentos:
            item = dict(pagamento)
            item["valor_comissao"] = round(float(item.get("comissao_registrada") or item.get("valor") or 0) * self.percentual if item.get("comissao_registrada") is None else float(item["comissao_registrada"]), 2)
            itens.append(item)
        return dict(professor), itens

    def resumo_professor(self, professor_id, referencia=None):
        referencia = referencia or date.today()
        professor, itens = self._pagamentos_do_professor(professor_id, referencia)
        pendente = sum(item["valor_comissao"] for item in itens if item.get("comissao_status") != "Pago")
        pago = sum(item["valor_comissao"] for item in itens if item.get("comissao_status") == "Pago")
        return {
            "professor": professor,
            "mes": referencia.strftime("%m/%Y"),
            "itens": itens,
            "a_receber": round(pendente, 2),
            "pago": round(pago, 2),
            "quantidade_pendente": sum(1 for item in itens if item.get("comissao_status") != "Pago"),
        }

    def resumos_do_mes(self, referencia=None):
        referencia = referencia or date.today()
        with conectar() as banco:
            professores = banco.execute(
                """SELECT DISTINCT p.id FROM professores p
                   JOIN professor_turmas pt ON pt.professor_id = p.id
                   JOIN turmas t ON t.id = pt.turma_id
                   WHERE lower(COALESCE(t.modalidade, '')) LIKE ?
                   UNION
                   SELECT DISTINCT p.id FROM professores p
                   JOIN turmas t ON lower(COALESCE(t.professor, '')) = lower(p.nome)
                   WHERE lower(COALESCE(t.modalidade, '')) LIKE ?
                     AND NOT EXISTS(SELECT 1 FROM professor_turmas pt WHERE pt.turma_id = t.id)""",
                ("%fut%", "%fut%"),
            ).fetchall()
        return [self.resumo_professor(item["id"], referencia) for item in professores]

    def confirmar_pagamento(self, professor_id, referencia=None):
        referencia = referencia or date.today()
        professor, itens = self._pagamentos_do_professor(professor_id, referencia)
        pendentes = [item for item in itens if item.get("comissao_status") != "Pago"]
        if not pendentes:
            raise ValueError("Não há comissão pendente para este professor neste mês.")
        total = round(sum(item["valor_comissao"] for item in pendentes), 2)
        momento = datetime.now().isoformat(timespec="seconds")
        mes = referencia.strftime("%Y-%m")
        with conectar() as banco:
            for item in pendentes:
                banco.execute(
                    """INSERT INTO comissoes_professores (professor_id, pagamento_id, valor, mes, status, pago_em)
                       VALUES (?, ?, ?, ?, ?, ?)
                       ON CONFLICT (professor_id, pagamento_id)
                       DO UPDATE SET valor = EXCLUDED.valor, mes = EXCLUDED.mes, status = EXCLUDED.status, pago_em = EXCLUDED.pago_em""",
                    (professor_id, item["pagamento_id"], item["valor_comissao"], mes, "Pago", momento),
                )
            banco.execute(
                """INSERT INTO despesas (descricao, categoria, valor, data, observacao)
                   VALUES (?, ?, ?, ?, ?)""",
                (f"Comissão Futvôlei · {professor['nome']} · {referencia.strftime('%m/%Y')}", "Comissão de professor", total, date.today().isoformat(), f"50% de {len(pendentes)} pagamento(s) de Futvôlei."),
            )
        return {"nome": professor["nome"], "total": total, "quantidade": len(pendentes)}