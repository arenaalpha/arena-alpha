"""Portal web publico da Arena Alpha."""
import os
from datetime import date, datetime

from flask import Flask, flash, redirect, render_template, request, session, url_for

from database.banco import conectar, criar_tabelas
from modules.agenda import Agenda
from modules.aulas_experimentais import AulasExperimentais


app = Flask(__name__)
app.config["SECRET_KEY"] = os.environ.get("SECRET_KEY") or os.urandom(32)
app.config["SESSION_COOKIE_HTTPONLY"] = True
app.config["SESSION_COOKIE_SAMESITE"] = "Lax"


def data_do_formulario(valor):
    return datetime.strptime(valor, "%Y-%m-%d").strftime("%d/%m/%Y")


def somente_numeros(valor):
    return "".join(caractere for caractere in (valor or "") if caractere.isdigit())


def aluno_do_portal():
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
        nascimento = request.form.get("nascimento", "").strip()
        if not cpf or not nascimento:
            flash("Informe seu CPF e sua data de nascimento.", "erro")
        else:
            with conectar() as banco:
                alunos = banco.execute("SELECT * FROM alunos WHERE cpf IS NOT NULL").fetchall()
                aluno = next((item for item in alunos if somente_numeros(item["cpf"]) == cpf and (item["data_nascimento"] or "").strip() == nascimento), None)
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
    with conectar() as banco:
        pagamentos = banco.execute(
            """SELECT valor, data, data_vencimento, pago_em, status FROM pagamentos
               WHERE aluno_id = ? OR (aluno_id IS NULL AND aluno = ?) ORDER BY id DESC""",
            (aluno["id"], aluno["nome"]),
        ).fetchall()
    return render_template("portal_conta.html", aluno=aluno, pagamentos=pagamentos)


@app.post("/portal/sair")
def sair_portal():
    session.clear()
    flash("Você saiu da sua conta.", "sucesso")
    return redirect(url_for("portal"))


@app.route("/aulas", methods=["GET", "POST"])
def aulas():
    if request.method == "POST":
        if request.form.get("website"):
            return redirect(url_for("aulas"))
        try:
            data = data_do_formulario(request.form["data"])
            AulasExperimentais().agendar(request.form.get("nome", ""), request.form.get("telefone", ""), request.form.get("esporte", ""), data, request.form.get("horario", ""))
        except (KeyError, ValueError) as erro:
            flash(str(erro), "erro")
        else:
            flash("Pedido de aula recebido! Em breve confirmaremos pelo WhatsApp.", "sucesso")
            return redirect(url_for("aulas"))
    return render_template("aulas.html", hoje=date.today().isoformat())


@app.route("/locacao", methods=["GET", "POST"])
def locacao():
    if request.method == "POST":
        if request.form.get("website"):
            return redirect(url_for("locacao"))
        try:
            data = data_do_formulario(request.form["data"])
            Agenda().reservar_locacao(request.form.get("nome", ""), request.form.get("telefone", ""), data, request.form.get("tipo", ""), request.form.get("horario", ""), request.form.get("duracao", ""))
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
            Agenda().reservar_locacao(request.form.get("nome", ""), request.form.get("telefone", ""), data, "Evento - R$ 300,00 (09h as 22h)")
        except (KeyError, ValueError) as erro:
            flash(str(erro), "erro")
        else:
            flash("Solicitação de evento recebida! A Arena confirmará pelo WhatsApp.", "sucesso")
            return redirect(url_for("eventos"))
    return render_template("eventos.html", hoje=date.today().isoformat())


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", "5000")), debug=True)
