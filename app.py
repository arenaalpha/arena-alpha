"""Portal web publico da Arena Alpha."""
import os
import json
import hmac
import hashlib
from datetime import date, datetime
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from flask import Flask, flash, redirect, render_template, request, session, url_for

from database.banco import conectar, criar_tabelas
from modules.agenda import Agenda
from modules.aulas_experimentais import AulasExperimentais
from modules.turmas import Turmas


app = Flask(__name__)
app.config["SECRET_KEY"] = os.environ.get("SECRET_KEY") or os.urandom(32)
app.config["SESSION_COOKIE_HTTPONLY"] = True
app.config["SESSION_COOKIE_SAMESITE"] = "Lax"


def encaminhar_para_banco_local(tipo, dados):
    """Envia um registro do portal hospedado ao conector em execucao no PC."""
    destino = os.environ.get("LOCAL_SYNC_URL", "").rstrip("/")
    segredo = os.environ.get("SYNC_SECRET", "")
    if not destino:
        return False
    if not segredo:
        raise ValueError("O conector local ainda nao foi configurado.")
    corpo = json.dumps({"tipo": tipo, "dados": dados}, ensure_ascii=False).encode("utf-8")
    assinatura = hmac.new(segredo.encode("utf-8"), corpo, hashlib.sha256).hexdigest()
    requisicao = Request(
        f"{destino}/registrar", data=corpo, method="POST",
        headers={"Content-Type": "application/json", "X-Arena-Signature": assinatura},
    )
    try:
        with urlopen(requisicao, timeout=12) as resposta:
            if resposta.status != 201:
                raise ValueError("O banco local recusou a solicitacao.")
    except HTTPError as erro:
        try:
            detalhe = json.loads(erro.read().decode("utf-8")).get("erro", "")
        except (UnicodeDecodeError, json.JSONDecodeError):
            detalhe = ""
        raise ValueError(detalhe or "O banco local recusou a solicitacao.")
    except (URLError, TimeoutError):
        raise ValueError("A Arena esta temporariamente sem conexao com o banco. Tente novamente em alguns minutos.")
    return True


def turmas_abertas():
    destino = os.environ.get("LOCAL_SYNC_URL", "").rstrip("/")
    segredo = os.environ.get("SYNC_SECRET", "")
    if not destino:
        return [dict(turma) for turma in Turmas().listar()]
    assinatura = hmac.new(segredo.encode("utf-8"), b"", hashlib.sha256).hexdigest()
    requisicao = Request(f"{destino}/turmas-abertas", headers={"X-Arena-Signature": assinatura})
    try:
        with urlopen(requisicao, timeout=8) as resposta:
            return json.loads(resposta.read().decode("utf-8"))
    except (URLError, HTTPError, json.JSONDecodeError):
        return []


def consultar_aluno_local(cpf):
    destino, segredo = os.environ.get("LOCAL_SYNC_URL", "").rstrip("/"), os.environ.get("SYNC_SECRET", "")
    if not destino:
        return None
    corpo = json.dumps({"cpf": cpf}).encode("utf-8")
    assinatura = hmac.new(segredo.encode("utf-8"), corpo, hashlib.sha256).hexdigest()
    requisicao = Request(f"{destino}/aluno-portal", data=corpo, method="POST", headers={"Content-Type":"application/json", "X-Arena-Signature":assinatura})
    try:
        with urlopen(requisicao, timeout=10) as resposta:
            return json.loads(resposta.read().decode("utf-8"))
    except (URLError, HTTPError, json.JSONDecodeError):
        return None


def data_do_formulario(valor):
    return datetime.strptime(valor, "%Y-%m-%d").strftime("%d/%m/%Y")


def somente_numeros(valor):
    return "".join(caractere for caractere in (valor or "") if caractere.isdigit())


def aluno_do_portal():
    aluno_sessao = session.get("aluno_portal")
    if aluno_sessao:
        return aluno_sessao
    identificador = session.get("aluno_portal_id")
    if not identificador:
        return None
    with conectar() as banco:
        return banco.execute(
            "SELECT id, nome, esporte, frequencia, valor_plano, dia_vencimento FROM alunos WHERE id = ?",
            (identificador,),
        ).fetchone()


@app.before_request
def preparar_banco():
    criar_tabelas()


@app.get("/")
def inicio():
    return render_template("inicio.html")


@app.route("/portal", methods=["GET", "POST"])
def portal():
    if request.method == "POST":
        cpf = somente_numeros(request.form.get("cpf"))
        if len(cpf) != 11:
            flash("Informe um CPF válido com 11 números.", "erro")
        else:
            resposta_local = consultar_aluno_local(cpf)
            if resposta_local:
                session.clear()
                session["aluno_portal"] = resposta_local["aluno"]
                session["pagamentos_portal"] = resposta_local["pagamentos"]
                return redirect(url_for("meu_portal"))
            with conectar() as banco:
                alunos = banco.execute("SELECT * FROM alunos WHERE cpf IS NOT NULL").fetchall()
                aluno = next((item for item in alunos if somente_numeros(item["cpf"]) == cpf), None)
                if aluno:
                    session.clear()
                    session["aluno_portal_id"] = aluno["id"]
                    banco.execute("INSERT OR REPLACE INTO portal_acessos (aluno_id, ultimo_acesso) VALUES (?, ?)", (aluno["id"], datetime.now().isoformat(timespec="seconds")))
                    return redirect(url_for("meu_portal"))
            flash("Não encontramos um aluno com esses dados. Peça à Arena para conferir seu cadastro.", "erro")
    return render_template("portal_login.html")


@app.get("/portal/minha-conta")
def meu_portal():
    aluno = aluno_do_portal()
    if not aluno:
        flash("Entre para acessar sua conta.", "erro")
        return redirect(url_for("portal"))
    pagamentos = session.get("pagamentos_portal")
    if pagamentos is None:
        with conectar() as banco:
            pagamentos = banco.execute(
                """SELECT valor, data, data_vencimento, pago_em, status FROM pagamentos
                   WHERE aluno_id = ? OR (aluno_id IS NULL AND aluno = ?) ORDER BY id DESC""",
                (aluno["id"], aluno["nome"]),
            ).fetchall()
    return render_template("portal_conta.html", aluno=aluno, pagamentos=pagamentos, aulas=turmas_abertas())


@app.post("/portal/sair")
def sair_portal():
    session.clear()
    flash("Você saiu da sua conta.", "sucesso")
    return redirect(url_for("portal"))


@app.route("/aulas", methods=["GET", "POST"])
def aulas():
    turmas = turmas_abertas()
    if request.method == "POST":
        if request.form.get("website"):
            return redirect(url_for("aulas"))
        try:
            turma = next((item for item in turmas if str(item["id"]) == request.form.get("turma_id")), None)
            if turma is None:
                raise ValueError("Escolha uma turma aberta e um horario disponivel.")
            dados = {"nome": request.form.get("nome", ""), "telefone": request.form.get("telefone", ""), "esporte": turma["modalidade"], "data": turma["proxima_data"], "horario": turma["horario"]}
            if not encaminhar_para_banco_local("aula", dados):
                AulasExperimentais().agendar(**dados)
        except (KeyError, ValueError) as erro:
            flash(str(erro), "erro")
        else:
            flash("Pedido de aula recebido! Em breve confirmaremos pelo WhatsApp.", "sucesso")
            return redirect(url_for("aulas"))
    return render_template("aulas.html", turmas=turmas)


@app.route("/locacao", methods=["GET", "POST"])
def locacao():
    if request.method == "POST":
        if request.form.get("website"):
            return redirect(url_for("locacao"))
        try:
            data = data_do_formulario(request.form["data"])
            dados = {"cliente": request.form.get("nome", ""), "whatsapp": request.form.get("telefone", ""), "data": data, "tipo_locacao": request.form.get("tipo", ""), "horario": request.form.get("horario", ""), "duracao_horas": request.form.get("duracao", "")}
            if not encaminhar_para_banco_local("locacao", dados):
                Agenda().reservar_locacao(**dados)
        except (KeyError, ValueError) as erro:
            flash(str(erro), "erro")
        else:
            flash("Solicitação recebida! A reserva será confirmada pelo WhatsApp.", "sucesso")
            return redirect(url_for("locacao"))
    return render_template("locacao.html", hoje=date.today().isoformat())


@app.route("/eventos", methods=["GET", "POST"])
def eventos():
    if request.method == "POST":
        if request.form.get("website"):
            return redirect(url_for("eventos"))
        try:
            data = data_do_formulario(request.form["data"])
            dados = {"cliente": request.form.get("nome", ""), "whatsapp": request.form.get("telefone", ""), "data": data, "tipo_locacao": "Evento - R$ 300,00 (09h as 22h)", "horario": "", "duracao_horas": ""}
            if not encaminhar_para_banco_local("locacao", dados):
                Agenda().reservar_locacao(**dados)
        except (KeyError, ValueError) as erro:
            flash(str(erro), "erro")
        else:
            flash("Sua reserva entrou na fila. Aguarde a confirmação da Arena pelo WhatsApp.", "sucesso")
            return redirect(url_for("eventos"))
    return render_template("eventos.html", hoje=date.today().isoformat())


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", "5000")), debug=True)
