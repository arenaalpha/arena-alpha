"""Recebe registros do portal e os grava no banco local da Arena Alpha."""
import hashlib
import hmac
import os
from datetime import date, timedelta
from pathlib import Path
import unicodedata

from flask import Flask, jsonify, request

# O conector sempre atende o banco principal do programa, mesmo se o Windows
# tiver outra variável DATABASE_PATH definida em segundo plano.
os.environ["DATABASE_PATH"] = str(Path(__file__).resolve().parent / "arena_alpha.db")

from database.banco import conectar, criar_tabelas
from modules.agenda import Agenda
from modules.aulas_experimentais import AulasExperimentais
from modules.alunos import Alunos
from modules.pagamentos import Pagamentos
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


@app.post("/painel-admin")
def painel_admin():
    corpo = request.get_data()
    assinatura = request.headers.get("X-Arena-Signature", "")
    esperada = hmac.new(SEGREDO.encode("utf-8"), corpo, hashlib.sha256).hexdigest()
    if not SEGREDO or not hmac.compare_digest(assinatura, esperada):
        return jsonify(erro="Assinatura invalida."), 401
    with conectar() as banco:
        alunos = banco.execute("SELECT id, nome, whatsapp, esporte, frequencia, valor_plano, dia_vencimento FROM alunos ORDER BY nome").fetchall()
        turmas = banco.execute("SELECT id, nome, modalidade, dia_semana, dia_semana_2, horario, status_aula, aviso_aula FROM turmas ORDER BY horario").fetchall()
        reservas = banco.execute("SELECT cliente, whatsapp, data, horario, tipo_locacao, valor FROM agenda ORDER BY id DESC LIMIT 30").fetchall()
        pagamentos = banco.execute("SELECT aluno, valor, pago_em, data_vencimento, status FROM pagamentos ORDER BY id DESC LIMIT 30").fetchall()
        experimentais = banco.execute("SELECT nome, telefone, esporte, data, horario FROM aulas_experimentais ORDER BY id DESC LIMIT 20").fetchall()
    return jsonify(alunos=[dict(item) for item in alunos], turmas=[dict(item) for item in turmas], reservas=[dict(item) for item in reservas], pagamentos=[dict(item) for item in pagamentos], experimentais=[dict(item) for item in experimentais])


@app.post("/admin-acao")
def admin_acao():
    corpo = request.get_data()
    assinatura = request.headers.get("X-Arena-Signature", "")
    esperada = hmac.new(SEGREDO.encode("utf-8"), corpo, hashlib.sha256).hexdigest()
    if not SEGREDO or not hmac.compare_digest(assinatura, esperada):
        return jsonify(erro="Assinatura invalida."), 401
    conteudo = request.get_json(silent=True) or {}
    dados, acao = conteudo.get("dados") or {}, conteudo.get("acao")
    try:
        if acao == "novo_aluno":
            obrigatorios = ("nome", "data_nascimento", "cpf", "whatsapp", "endereco", "esporte", "frequencia", "como_conheceu", "restricoes_alimentares", "problema_saude", "necessidades_especiais", "menor_idade", "autorizacao_imagem", "turma_id")
            faltando = [campo.replace("_", " ") for campo in obrigatorios if not str(dados.get(campo, "")).strip()]
            if faltando:
                raise ValueError("Preencha: " + ", ".join(faltando) + ".")
            if dados["menor_idade"] == "Sim":
                responsavel = ("responsavel_nome", "responsavel_cpf", "responsavel_parentesco")
                if any(not str(dados.get(campo, "")).strip() for campo in responsavel):
                    raise ValueError("Informe todos os dados do responsavel do menor.")
            planos = {
                "Volei de areia": {"1x por semana - R$ 65,00": 65, "2x por semana - R$ 120,00": 120, "Diaria - R$ 25,00 por dia": 25},
                "Futvolei": {"1x por semana - R$ 60,00": 60, "2x por semana - R$ 85,00": 85, "Diaria - R$ 20,00 por dia": 20},
            }
            valor_plano = planos.get(dados["esporte"], {}).get(dados["frequencia"])
            if valor_plano is None:
                raise ValueError("Escolha uma frequencia valida para o esporte selecionado.")
            turma_id = int(dados["turma_id"])
            turma = next((item for item in Turmas().listar() if item["id"] == turma_id), None)
            if turma is None:
                raise ValueError("Turma selecionada nao encontrada.")
            valores = {campo: str(dados.get(campo, "")).strip() for campo in Alunos.campos}
            valores.update(telefone=dados["whatsapp"].strip(), whatsapp=dados["whatsapp"].strip(), modalidade=dados["esporte"].strip(), valor_plano=valor_plano, data_inscricao=date.today().isoformat(), dia_vencimento=date.today().day)
            aluno_id = Alunos().cadastrar(**valores)
            dia_treino = turma["dia_semana"] if dados["frequencia"].startswith("1x") else "Todos os dias da turma"
            Turmas().vincular_aluno(aluno_id, turma_id, dia_treino)
            mensagem = "Aluno cadastrado."
        elif acao == "nova_turma":
            Turmas().criar(dados["nome"], dados["dia_semana"], dados["dia_semana_2"], dados["horario"], dados.get("professor", ""), dados["modalidade"])
            mensagem = "Turma criada."
        elif acao == "status_turma":
            Turmas().atualizar_status_aula(int(dados["turma_id"]), dados["status"], dados.get("aviso", ""))
            mensagem = "Status da aula atualizado."
        elif acao == "pagamento":
            resultado = Pagamentos().registrar_mensalidade(int(dados["aluno_id"]), dados["data_pagamento"])
            mensagem = f"Pagamento registrado: {resultado['status']}."
        elif acao == "limpar_experimentais":
            AulasExperimentais().limpar_historico()
            mensagem = "Historico de aulas experimentais apagado."
        elif acao == "limpar_reservas":
            Agenda().limpar_historico()
            mensagem = "Historico de reservas da quadra apagado."
        else:
            return jsonify(erro="Ação administrativa inválida."), 400
    except (KeyError, TypeError, ValueError) as erro:
        return jsonify(erro=str(erro)), 422
    return jsonify(mensagem=mensagem)


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
