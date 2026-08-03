"""Recebe registros do portal e os grava no banco local da Arena Alpha."""
import hashlib
import hmac
import os
from datetime import date, timedelta
import unicodedata

from flask import Flask, jsonify, request

from database.banco import criar_tabelas
from modules.agenda import Agenda
from modules.aulas_experimentais import AulasExperimentais
from modules.turmas import Turmas


app = Flask(__name__)
SEGREDO = os.environ.get("SYNC_SECRET", "")


@app.before_request
def preparar_banco():
    criar_tabelas()


@app.post("/registrar")
def registrar():
    if not SEGREDO:
        return jsonify(erro="Defina SYNC_SECRET antes de iniciar o conector."), 503
    corpo = request.get_data()
    assinatura = request.headers.get("X-Arena-Signature", "")
    esperada = hmac.new(SEGREDO.encode("utf-8"), corpo, hashlib.sha256).hexdigest()
    if not hmac.compare_digest(assinatura, esperada):
        return jsonify(erro="Assinatura invalida."), 401
    conteudo = request.get_json(silent=True) or {}
    dados = conteudo.get("dados") or {}
    try:
        if conteudo.get("tipo") == "aula":
            AulasExperimentais().agendar(**dados)
        elif conteudo.get("tipo") == "locacao":
            Agenda().reservar_locacao(**dados)
        else:
            return jsonify(erro="Tipo de registro invalido."), 400
    except (TypeError, ValueError) as erro:
        return jsonify(erro=str(erro)), 422
    return jsonify(status="registrado"), 201


def normalizar(texto):
    return "".join(c for c in unicodedata.normalize("NFD", (texto or "").lower()) if unicodedata.category(c) != "Mn")


@app.get("/turmas-abertas")
def listar_turmas_abertas():
    assinatura = request.headers.get("X-Arena-Signature", "")
    esperada = hmac.new(SEGREDO.encode("utf-8"), b"", hashlib.sha256).hexdigest()
    if not SEGREDO or not hmac.compare_digest(assinatura, esperada):
        return jsonify(erro="Assinatura invalida."), 401
    dias = {"segunda-feira": 0, "terca-feira": 1, "quarta-feira": 2, "quinta-feira": 3, "sexta-feira": 4, "sabado": 5, "domingo": 6}
    hoje, resultado = date.today(), []
    for turma in Turmas().listar():
        modalidade = normalizar(turma["modalidade"])
        dias_turma = [normalizar(turma["dia_semana"]), normalizar(turma["dia_semana_2"])]
        dias_indices = [dias[d] for d in dias_turma if d in dias]
        volei = "volei" in modalidade and "fut" not in modalidade
        if volei and 0 not in dias_indices:
            continue
        alvos = [0] if volei else dias_indices
        if not alvos:
            continue
        proxima = hoje + timedelta(days=min((dia - hoje.weekday()) % 7 for dia in alvos))
        resultado.append({"id": turma["id"], "nome": turma["nome"], "modalidade": turma["modalidade"], "horario": turma["horario"], "proxima_data": proxima.strftime("%d/%m/%Y"), "status_aula": turma["status_aula"] or "Normal", "aviso_aula": turma["aviso_aula"] or ""})
    return jsonify(resultado)


if __name__ == "__main__":
    app.run(host="127.0.0.1", port=5050)
