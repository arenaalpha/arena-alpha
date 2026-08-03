"""Recebe registros do portal e os grava no banco local da Arena Alpha."""
import hashlib
import hmac
import os
from datetime import date, timedelta
import unicodedata

from flask import Flask, jsonify, request

from database.banco import conectar, criar_tabelas
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


@app.post("/aluno-portal")
def aluno_portal():
    corpo = request.get_data()
    assinatura = request.headers.get("X-Arena-Signature", "")
    esperada = hmac.new(SEGREDO.encode("utf-8"), corpo, hashlib.sha256).hexdigest()
    if not SEGREDO or not hmac.compare_digest(assinatura, esperada):
        return jsonify(erro="Assinatura invalida."), 401
    dados = request.get_json(silent=True) or {}
    cpf = "".join(c for c in dados.get("cpf", "") if c.isdigit())
    if len(cpf) != 11:
        return jsonify(erro="CPF inválido."), 422
    with conectar() as banco:
        alunos = banco.execute("SELECT * FROM alunos WHERE cpf IS NOT NULL").fetchall()
        aluno = next((item for item in alunos if "".join(c for c in (item["cpf"] or "") if c.isdigit()) == cpf), None)
        if aluno is None:
            return jsonify(erro="Aluno nao encontrado."), 404
        pagamentos = banco.execute("SELECT valor, data, data_vencimento, pago_em, status FROM pagamentos WHERE aluno_id = ? OR (aluno_id IS NULL AND aluno = ?) ORDER BY id DESC", (aluno["id"], aluno["nome"])).fetchall()
    campos = ("id", "nome", "whatsapp", "esporte", "frequencia", "valor_plano", "dia_vencimento")
    return jsonify(aluno={campo: aluno[campo] for campo in campos}, pagamentos=[dict(item) for item in pagamentos], aulas=aulas_matriculadas(aluno["id"]))


def normalizar(texto):
    return "".join(c for c in unicodedata.normalize("NFD", (texto or "").lower()) if unicodedata.category(c) != "Mn")


def aulas_matriculadas(aluno_id):
    dias = {"segunda-feira": 0, "terca-feira": 1, "quarta-feira": 2, "quinta-feira": 3, "sexta-feira": 4, "sabado": 5, "domingo": 6}
    hoje, resultado = date.today(), []
    with conectar() as banco:
        turmas = banco.execute(
            """SELECT t.*, m.dia_treino FROM matriculas_turma m
               JOIN turmas t ON t.id = m.turma_id WHERE m.aluno_id = ?""", (aluno_id,)
        ).fetchall()
    for turma in turmas:
        dias_turma = [turma["dia_semana"], turma["dia_semana_2"]]
        if turma["dia_treino"] != "Todos os dias da turma":
            dias_turma = [turma["dia_treino"]]
        proximos = [dias[dia] for dia in map(normalizar, dias_turma) if dia in dias]
        if not proximos:
            continue
        proxima = hoje + timedelta(days=min((dia - hoje.weekday()) % 7 for dia in proximos))
        resultado.append({"id": turma["id"], "nome": turma["nome"], "modalidade": turma["modalidade"], "horario": turma["horario"], "proxima_data": proxima.strftime("%d/%m/%Y"), "status_aula": turma["status_aula"] or "Normal", "aviso_aula": turma["aviso_aula"] or ""})
    return resultado


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
    app.run(host="127.0.0.1", port=int(os.environ.get("CONNECTOR_PORT", "5050")))
