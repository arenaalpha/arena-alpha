"""Recebe registros do portal e os grava no banco local da Arena Alpha."""
import hashlib
import hmac
import os

from flask import Flask, jsonify, request

from database.banco import criar_tabelas
from modules.agenda import Agenda
from modules.aulas_experimentais import AulasExperimentais


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


if __name__ == "__main__":
    app.run(host="127.0.0.1", port=5050)
