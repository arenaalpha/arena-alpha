import re
import unicodedata
from datetime import datetime, timedelta

from database.banco import conectar, normalizar_telefone_brasil
from .base import Repositorio


class Agenda(Repositorio):
    tabela = "agenda"
    campos = ("quadra", "data", "horario", "cliente", "tipo_locacao", "duracao_horas", "valor", "whatsapp", "status")

    def reservar(self, quadra, data, horario, cliente):
        super().cadastrar(
            quadra=quadra, data=data, horario=horario, cliente=cliente,
            tipo_locacao="Quadra", duracao_horas=1, valor=40.0, whatsapp="", status="Pendente",
        )

    @staticmethod
    def _normalizar(texto):
        return "".join(
            caractere for caractere in unicodedata.normalize("NFD", texto.lower())
            if unicodedata.category(caractere) != "Mn"
        )

    def _intervalo(self, data, horario, duracao=1):
        numeros = re.findall(r"\b\d{1,2}(?::\d{2})?\b", horario or "")
        if not numeros:
            raise ValueError("Informe o horario no formato HH:MM.")
        inicio_hora = datetime.strptime(numeros[0] if ":" in numeros[0] else f"{numeros[0]}:00", "%H:%M").time()
        inicio = datetime.combine(data, inicio_hora)
        if len(numeros) >= 2:
            fim_hora = datetime.strptime(numeros[1] if ":" in numeros[1] else f"{numeros[1]}:00", "%H:%M").time()
            fim = datetime.combine(data, fim_hora)
            if fim <= inicio:
                raise ValueError("O horario final deve ser depois do horario inicial.")
        else:
            fim = inicio + timedelta(hours=duracao)
        return inicio, fim

    @staticmethod
    def _conflita(inicio_a, fim_a, inicio_b, fim_b):
        return inicio_a < fim_b and fim_a > inicio_b

    def _verificar_disponibilidade(self, data, inicio, fim):
        dias = ["segunda-feira", "terca-feira", "quarta-feira", "quinta-feira", "sexta-feira", "sabado", "domingo"]
        dia = dias[data.weekday()]
        with conectar() as banco:
            turmas = banco.execute(
                "SELECT nome, horario, dia_semana, dia_semana_2 FROM turmas"
            ).fetchall()
            for turma in turmas:
                dias_turma = {self._normalizar(turma["dia_semana"] or ""), self._normalizar(turma["dia_semana_2"] or "")}
                if dia not in dias_turma and dia.replace("-feira", "") not in dias_turma:
                    continue
                try:
                    inicio_turma, fim_turma = self._intervalo(data, turma["horario"])
                except ValueError:
                    continue
                if self._conflita(inicio, fim, inicio_turma, fim_turma):
                    raise ValueError(f"Horario indisponivel: ha aula da turma '{turma['nome']}' ({turma['horario']}).")

            reservas = banco.execute("SELECT cliente, horario FROM agenda WHERE data = ?", (data.strftime("%d/%m/%Y"),)).fetchall()
            for reserva in reservas:
                try:
                    inicio_reserva, fim_reserva = self._intervalo(data, reserva["horario"])
                except ValueError:
                    continue
                if self._conflita(inicio, fim, inicio_reserva, fim_reserva):
                    raise ValueError(f"Horario indisponivel: ja existe locacao para {reserva['cliente']} ({reserva['horario']}).")

    def reservar_locacao(self, cliente, whatsapp, data, tipo_locacao, horario="", duracao_horas=""):
        try:
            data_locacao = datetime.strptime(data, "%d/%m/%Y").date()
        except ValueError:
            raise ValueError("Informe a data no formato dd/mm/aaaa.")
        if tipo_locacao == "Evento - R$ 300,00 (09h as 22h)":
            horario = "09:00 as 22:00"
            duracao = 13
            valor = 300.0
        else:
            try:
                duracao = int(duracao_horas)
            except (TypeError, ValueError):
                raise ValueError("Informe uma quantidade inteira de horas.")
            if duracao < 1:
                raise ValueError("A locacao da quadra deve ter pelo menos 1 hora.")
            if not horario.strip():
                raise ValueError("Informe o horario de inicio da locacao.")
            valor = duracao * 40.0
        inicio, fim = self._intervalo(data_locacao, horario, duracao)
        abertura = datetime.combine(data_locacao, datetime.strptime("09:00", "%H:%M").time())
        fechamento = datetime.combine(data_locacao, datetime.strptime("22:00", "%H:%M").time())
        if inicio < abertura or fim > fechamento:
            raise ValueError("A quadra funciona somente das 09:00 as 22:00.")
        self._verificar_disponibilidade(data_locacao, inicio, fim)
        horario = f"{inicio:%H:%M} as {fim:%H:%M}"
        super().cadastrar(
            quadra="Quadra Principal", data=data, horario=horario, cliente=cliente,
            tipo_locacao=tipo_locacao, duracao_horas=duracao, valor=valor, whatsapp=normalizar_telefone_brasil(whatsapp), status="Pendente",
        )
        return valor, horario

    def confirmar(self, identificador):
        with conectar() as banco:
            banco.execute("UPDATE agenda SET status = 'Confirmada' WHERE id = ?", (identificador,))

    def limpar_historico(self):
        with conectar() as banco:
            banco.execute("DELETE FROM agenda")
