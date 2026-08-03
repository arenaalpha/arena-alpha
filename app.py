"""Portal web publico da Arena Alpha."""
import os
import calendar
import json
import hmac
import hashlib
from functools import wraps
from datetime import date, datetime, timedelta
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from flask import Flask, flash, redirect, render_template, request, session, url_for
from werkzeug.security import check_password_hash

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


def consultar_painel_local():
    destino, segredo = os.environ.get("LOCAL_SYNC_URL", "").rstrip("/"), os.environ.get("SYNC_SECRET", "")
    if not destino or not segredo:
        return None
    corpo = b""
    assinatura = hmac.new(segredo.encode("utf-8"), corpo, hashlib.sha256).hexdigest()
    requisicao = Request(f"{destino}/painel-admin", data=corpo, method="POST", headers={"X-Arena-Signature": assinatura})
    try:
        with urlopen(requisicao, timeout=12) as resposta:
            return json.loads(resposta.read().decode("utf-8"))
    except (URLError, HTTPError, json.JSONDecodeError):
        return None


def enviar_acao_admin(acao, dados):
    destino, segredo = os.environ.get("LOCAL_SYNC_URL", "").rstrip("/"), os.environ.get("SYNC_SECRET", "")
    if not destino or not segredo:
        raise ValueError("O computador da Arena está sem conexão.")
    corpo = json.dumps({"acao": acao, "dados": dados}, ensure_ascii=False).encode("utf-8")
    assinatura = hmac.new(segredo.encode("utf-8"), corpo, hashlib.sha256).hexdigest()
    requisicao = Request(f"{destino}/admin-acao", data=corpo, method="POST", headers={"Content-Type": "application/json", "X-Arena-Signature": assinatura})
    try:
        with urlopen(requisicao, timeout=12) as resposta:
            return json.loads(resposta.read().decode("utf-8"))
    except HTTPError as erro:
        try:
            raise ValueError(json.loads(erro.read().decode("utf-8")).get("erro", "Ação recusada."))
        except json.JSONDecodeError:
            raise ValueError("Ação recusada pelo sistema local.")
    except (URLError, TimeoutError):
        raise ValueError("O computador da Arena está sem conexão.")


def data_do_formulario(valor):
    return datetime.strptime(valor, "%Y-%m-%d").strftime("%d/%m/%Y")


def somente_numeros(valor):
    return "".join(caractere for caractere in (valor or "") if caractere.isdigit())


def situacao_pagamento_portal(aluno, pagamentos, referencia=None):
    """Resume a mensalidade do mês atual para o Portal do Aluno."""
    referencia = referencia or date.today()
    try:
        dia = int(aluno.get("dia_vencimento") if isinstance(aluno, dict) else aluno["dia_vencimento"])
    except (TypeError, ValueError):
        return {"texto": "Vencimento não configurado", "classe": "pendente", "vencimento": None}
    vencimento = date(referencia.year, referencia.month, min(dia, calendar.monthrange(referencia.year, referencia.month)[1]))
    mes_atual = referencia.strftime("%Y-%m")
    for pagamento in pagamentos:
        pago_em = pagamento.get("pago_em") if isinstance(pagamento, dict) else pagamento["pago_em"]
        if pago_em and str(pago_em).startswith(mes_atual):
            status = (pagamento.get("status") if isinstance(pagamento, dict) else pagamento["status"]) or "Pago em dia"
            return {"texto": status, "classe": "atrasado" if "atraso" in status.lower() else "pago", "vencimento": vencimento}
    if referencia > vencimento:
        return {"texto": "Em atraso", "classe": "atrasado", "vencimento": vencimento}
    return {"texto": "Em dia", "classe": "pago", "vencimento": vencimento}


def tem_desconto_volei(aluno):
    esporte = aluno.get("esporte", "") if isinstance(aluno, dict) else aluno["esporte"]
    return "volei" in (esporte or "").lower().replace("ô", "o")


def aulas_matriculadas_local(aluno_id):
    """Lista exclusivamente as turmas vinculadas ao aluno no sistema local."""
    dias = {"Segunda-feira": 0, "Terca-feira": 1, "Quarta-feira": 2, "Quinta-feira": 3, "Sexta-feira": 4, "Sabado": 5, "Domingo": 6}
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
        proximos = [dias[dia] for dia in dias_turma if dia in dias]
        if not proximos:
            continue
        proxima = hoje + timedelta(days=min((dia - hoje.weekday()) % 7 for dia in proximos))
        resultado.append({"id": turma["id"], "nome": turma["nome"], "modalidade": turma["modalidade"], "horario": turma["horario"], "proxima_data": proxima.strftime("%d/%m/%Y"), "status_aula": turma["status_aula"] or "Normal", "aviso_aula": turma["aviso_aula"] or ""})
    return resultado


def contato_da_reserva(formulario):
    """Usa os dados do cadastro quando a reserva é feita pelo Portal do Aluno."""
    aluno = aluno_do_portal()
    if not aluno:
        return {"nome": formulario.get("nome", "").strip(), "telefone": formulario.get("telefone", "").strip()}
    whatsapp = aluno.get("whatsapp", "") if isinstance(aluno, dict) else aluno["whatsapp"]
    if not whatsapp:
        raise ValueError("O WhatsApp não está cadastrado. Peça à Arena para atualizar seu cadastro.")
    return {"nome": aluno["nome"], "telefone": whatsapp}


def aluno_do_portal():
    aluno_sessao = session.get("aluno_portal")
    if aluno_sessao:
        return aluno_sessao
    identificador = session.get("aluno_portal_id")
    if not identificador:
        return None
    with conectar() as banco:
        return banco.execute(
            "SELECT id, nome, whatsapp, esporte, frequencia, valor_plano, dia_vencimento FROM alunos WHERE id = ?",
            (identificador,),
        ).fetchone()


def exige_admin(funcao):
    @wraps(funcao)
    def protegida(*args, **kwargs):
        if not session.get("admin_portal"):
            flash("Entre com o acesso administrativo.", "erro")
            return redirect(url_for("admin"))
        return funcao(*args, **kwargs)
    return protegida


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
                session["aulas_portal"] = resposta_local.get("aulas", [])
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


@app.route("/admin", methods=["GET", "POST"])
def admin():
    if request.method == "POST":
        usuario = request.form.get("usuario", "").strip()
        senha = request.form.get("senha", "")
        usuario_admin = os.environ.get("ADMIN_USER", "")
        senha_admin = os.environ.get("ADMIN_PASSWORD_HASH", "")
        if usuario == usuario_admin and senha_admin and check_password_hash(senha_admin, senha):
            session.clear()
            session["admin_portal"] = True
            return redirect(url_for("painel_admin"))
        flash("Usuário ou senha incorretos.", "erro")
    return render_template("admin_login.html")


@app.get("/admin/painel")
@exige_admin
def painel_admin():
    painel = consultar_painel_local()
    if painel is None:
        flash("O computador da Arena está sem conexão no momento.", "erro")
        painel = {"alunos": [], "turmas": [], "reservas": []}
    return render_template("admin_painel.html", secao=request.args.get("secao", "inicio"), **painel)


@app.post("/admin/acao")
@exige_admin
def acao_admin():
    acao = request.form.get("acao", "")
    dados = {chave: valor.strip() for chave, valor in request.form.items() if chave != "acao"}
    try:
        resultado = enviar_acao_admin(acao, dados)
        flash(resultado.get("mensagem", "Alteração salva."), "sucesso")
    except ValueError as erro:
        flash(str(erro), "erro")
    return redirect(url_for("painel_admin", secao=request.form.get("secao", "inicio")))


@app.post("/admin/sair")
def sair_admin():
    session.clear()
    return redirect(url_for("admin"))


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
    aulas = session.get("aulas_portal")
    if aulas is None:
        aulas = aulas_matriculadas_local(aluno["id"])
    return render_template(
        "portal_conta.html", aluno=aluno, pagamentos=pagamentos, aulas=aulas,
        situacao_pagamento=situacao_pagamento_portal(aluno, pagamentos), desconto_volei=tem_desconto_volei(aluno),
    )


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
            contato = contato_da_reserva(request.form)
            dados = {"cliente": contato["nome"], "whatsapp": contato["telefone"], "data": data, "tipo_locacao": request.form.get("tipo", ""), "horario": request.form.get("horario", ""), "duracao_horas": request.form.get("duracao", "")}
            if not encaminhar_para_banco_local("locacao", dados):
                Agenda().reservar_locacao(**dados)
        except (KeyError, ValueError) as erro:
            flash(str(erro), "erro")
        else:
            flash("Solicitação recebida! A reserva será confirmada pelo WhatsApp.", "sucesso")
            return redirect(url_for("locacao"))
    return render_template("locacao.html", hoje=date.today().isoformat(), aluno_portal=aluno_do_portal())


@app.route("/eventos", methods=["GET", "POST"])
def eventos():
    if request.method == "POST":
        if request.form.get("website"):
            return redirect(url_for("eventos"))
        try:
            data = data_do_formulario(request.form["data"])
            contato = contato_da_reserva(request.form)
            dados = {"cliente": contato["nome"], "whatsapp": contato["telefone"], "data": data, "tipo_locacao": "Evento - R$ 300,00 (09h as 22h)", "horario": "", "duracao_horas": ""}
            if not encaminhar_para_banco_local("locacao", dados):
                Agenda().reservar_locacao(**dados)
        except (KeyError, ValueError) as erro:
            flash(str(erro), "erro")
        else:
            flash("Sua reserva entrou na fila. Aguarde a confirmação da Arena pelo WhatsApp.", "sucesso")
            return redirect(url_for("eventos"))
    return render_template("eventos.html", hoje=date.today().isoformat(), aluno_portal=aluno_do_portal())


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", "5000")), debug=True)
