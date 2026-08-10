from datetime import date

from database.banco import conectar, normalizar_telefone_brasil


class Parceiros:
    def criar(self, empresa, whatsapp):
        empresa = (empresa or "").strip()
        whatsapp = normalizar_telefone_brasil(whatsapp)
        if not empresa or not whatsapp:
            raise ValueError("Informe o nome da empresa e o WhatsApp.")
        with conectar() as banco:
            existente = banco.execute("SELECT id FROM parceiros WHERE lower(empresa) = lower(?)", (empresa,)).fetchone()
            if existente:
                raise ValueError("Esta empresa já está cadastrada.")
            resultado = banco.execute("INSERT INTO parceiros (empresa, whatsapp) VALUES (?, ?)", (empresa, whatsapp))
        return resultado.lastrowid

    def registrar_doacao(self, parceiro_id, motivo, valor, data_texto):
        try:
            valor = float(str(valor).replace(",", "."))
        except ValueError:
            raise ValueError("Informe um valor válido para a doação.")
        if valor <= 0:
            raise ValueError("A doação deve ser maior que zero.")
        motivo = (motivo or "").strip()
        if not motivo:
            raise ValueError("Informe o motivo da doação.")
        try:
            data = date.fromisoformat(data_texto)
        except (TypeError, ValueError):
            raise ValueError("Informe a data da doação.")
        with conectar() as banco:
            parceiro = banco.execute("SELECT id FROM parceiros WHERE id = ?", (parceiro_id,)).fetchone()
            if parceiro is None:
                raise ValueError("Empresa parceira não encontrada.")
            banco.execute(
                "INSERT INTO doacoes_parceiros (parceiro_id, motivo, valor, data) VALUES (?, ?, ?, ?)",
                (parceiro_id, motivo, valor, data.isoformat()),
            )
