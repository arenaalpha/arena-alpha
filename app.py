"""Portal web publico da Arena Alpha."""
import os
import calendar
import json
import hmac
import hashlib
import unicodedata
from io import BytesIO
from functools import wraps
from datetime import date, datetime, timedelta
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from flask import Flask, flash, redirect, render_template, request, session, url_for, send_file
from werkzeug.security import check_password_hash

from database.banco import conectar, criar_tabelas
from modules.agenda import Agenda
from modules.aulas_experimentais import AulasExperimentais
from modules.alunos import Alunos
from modules.financeiro import Financeiro
from modules.pagamentos import Pagamentos
from modules.professores import Professores
from modules.turmas import Turmas
from modules.modalidades import Modalidades
from modules.inscricoes import Inscricoes


app = Flask(__name__)
app.config["SECRET_KEY"] = os.environ.get("SECRET_KEY") or os.urandom(32)
app.config["SESSION_COOKIE_HTTPONLY"] = True
app.config["SESSION_COOKIE_SAMESITE"] = "Lax"
app.config["MAX_CONTENT_LENGTH"] = 5 * 1024 * 1024


def banco_online():
    return os.environ.get("DATABASE_URL", "").startswith(("postgres://", "postgresql://"))


def encaminhar_para_banco_local(tipo, dados):
    """Envia um registro do portal hospedado ao conector em execucao no PC."""
    if banco_online():
        if tipo == "aula":
            AulasExperimentais().agendar(**dados)
        elif tipo == "locacao":
            Agenda().reservar_locacao(**dados)
        else:
            raise ValueError("Tipo de registro invalido.")
        return True
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
    if banco_online():
        dias = {"segunda-feira": 0, "terca-feira": 1, "quarta-feira": 2, "quinta-feira": 3, "sexta-feira": 4, "sabado": 5, "domingo": 6}
        hoje, resultado = date.today(), []
        for turma in Turmas().listar():
            modalidade = (turma["modalidade"] or "").lower().replace("ô", "o")
            nomes_dias = [(turma["dia_semana"] or "").lower().replace("ç", "c").replace("á", "a"), (turma["dia_semana_2"] or "").lower().replace("ç", "c").replace("á", "a")]
            indices = [dias[nome] for nome in nomes_dias if nome in dias]
            if "volei" in modalidade and "fut" not in modalidade:
                indices = [0] if 0 in indices else []
            if not indices:
                continue
            proxima = hoje + timedelta(days=min((item - hoje.weekday()) % 7 for item in indices))
            resultado.append({"id": turma["id"], "nome": turma["nome"], "modalidade": turma["modalidade"], "horario": turma["horario"], "proxima_data": proxima.strftime("%d/%m/%Y"), "status_aula": turma["status_aula"] or "Normal", "aviso_aula": turma["aviso_aula"] or ""})
        return resultado
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


def modalidade_para_exibicao(modalidade):
    texto = "".join(
        caractere for caractere in unicodedata.normalize("NFD", str(modalidade or "").lower())
        if unicodedata.category(caractere) != "Mn"
    )
    if "fut" in texto and "volei" in texto:
        return "Futvôlei"
    if "volei" in texto:
        return "Vôlei de areia"
    return str(modalidade or "Modalidade não informada")


def turmas_experimentais_abertas():
    """Repete os próximos encontros de cada turma por até 30 dias."""
    limite = date.today() + timedelta(days=30)
    resultado = []
    for turma in turmas_abertas():
        try:
            data_aula = datetime.strptime(turma["proxima_data"], "%d/%m/%Y").date()
        except (KeyError, TypeError, ValueError):
            continue
        while data_aula <= limite:
            opcao = dict(turma)
            opcao["modalidade"] = modalidade_para_exibicao(turma.get("modalidade"))
            opcao["data_agendamento"] = data_aula.strftime("%d/%m/%Y")
            resultado.append(opcao)
            data_aula += timedelta(days=7)
    return sorted(resultado, key=lambda item: (datetime.strptime(item["data_agendamento"], "%d/%m/%Y").date(), item["horario"], item["nome"]))


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


def organizar_experimentais(experimentais):
    """Agrupa aulas futuras por data, horário e turma para a visão geral."""
    grupos = {}
    hoje = date.today()
    for aula in experimentais:
        texto_data = str(aula.get("data") or "")
        try:
            data_aula = datetime.strptime(texto_data, "%Y-%m-%d").date()
        except ValueError:
            try:
                data_aula = datetime.strptime(texto_data, "%d/%m/%Y").date()
            except ValueError:
                continue
        if data_aula < hoje:
            continue
        turma = aula.get("turma") or aula.get("esporte") or "Turma não informada"
        horario = aula.get("horario") or "Horário não informado"
        chave = (data_aula, horario, turma)
        grupos.setdefault(chave, []).append(aula)
    resultado = []
    for (data_aula, horario, turma), participantes in sorted(grupos.items(), key=lambda item: (item[0][0], item[0][1], item[0][2])):
        resultado.append({
            "data": data_aula.strftime("%d/%m/%Y"), "horario": horario,
            "turma": turma, "participantes": sorted(participantes, key=lambda item: item["nome"].lower()),
        })
    return sum(len(grupo["participantes"]) for grupo in resultado), resultado


def consultar_painel_local():
    if banco_online():
        with conectar() as banco:
            alunos = banco.execute("SELECT a.*, (SELECT m.turma_id FROM matriculas_turma m WHERE m.aluno_id = a.id ORDER BY m.id LIMIT 1) AS turma_id FROM alunos a ORDER BY a.nome").fetchall()
            turmas = banco.execute("SELECT id, nome, modalidade, dia_semana, dia_semana_2, horario, status_aula, aviso_aula FROM turmas ORDER BY horario").fetchall()
            reservas = banco.execute("SELECT id, cliente, whatsapp, data, horario, tipo_locacao, valor, status FROM agenda ORDER BY id DESC LIMIT 30").fetchall()
            pagamentos = banco.execute("SELECT id, aluno, valor, pago_em, data_vencimento, status FROM pagamentos ORDER BY id DESC LIMIT 30").fetchall()
            despesas = banco.execute("SELECT id, descricao, categoria, valor, data FROM despesas ORDER BY id DESC LIMIT 30").fetchall()
            experimentais = banco.execute("SELECT id, nome, telefone, esporte, data, horario, turma, confirmacao_enviada FROM aulas_experimentais ORDER BY data, horario, id").fetchall()
            modalidades = Modalidades().listar()
            professores = banco.execute("SELECT id, nome, telefone, especialidade FROM professores ORDER BY nome").fetchall()
            inscricoes = banco.execute("SELECT i.*, t.nome AS turma_nome, t.horario AS turma_horario FROM inscricoes_portal i JOIN turmas t ON t.id = i.turma_id WHERE i.status = ? ORDER BY i.id DESC", ("Pendente",)).fetchall()
        financeiro = Financeiro()
        atrasados, status_por_aluno = [], {}
        for item in Pagamentos().situacao_atual():
            status_por_aluno[item["aluno"]["id"]] = item["status"]
            if item["status"] == "Em atraso" and item["aluno"]["whatsapp"]:
                atrasados.append({"nome": item["aluno"]["nome"], "whatsapp": item["aluno"]["whatsapp"], "vencimento": item["vencimento"].strftime("%d/%m/%Y")})
        resumo_turmas = Turmas().resumo_financeiro(status_por_aluno)
        alunos_por_turma = {turma["id"]: [dict(aluno) for aluno in Turmas().alunos_da_turma(turma["id"])] for turma in turmas}
        experimentais_agendadas, grupos_experimentais = organizar_experimentais([dict(item) for item in experimentais])
        experimentais_pendentes = []
        for aula in experimentais:
            try:
                data_aula = datetime.strptime(str(aula["data"]), "%Y-%m-%d").date()
            except ValueError:
                continue
            if not aula["confirmacao_enviada"] and data_aula >= date.today():
                item = dict(aula)
                item["data_exibicao"] = data_aula.strftime("%d/%m/%Y")
                experimentais_pendentes.append(item)
        return {"alunos": [dict(item) for item in alunos], "turmas": [dict(item) for item in turmas], "resumo_turmas": resumo_turmas, "alunos_por_turma": alunos_por_turma, "reservas": [dict(item) for item in reservas], "pagamentos": [dict(item) for item in pagamentos], "despesas": [dict(item) for item in despesas], "experimentais": [dict(item) for item in experimentais], "experimentais_agendadas": experimentais_agendadas, "grupos_experimentais": grupos_experimentais, "experimentais_pendentes": experimentais_pendentes, "modalidades": [dict(item) for item in modalidades], "professores": [dict(item) for item in professores], "inscricoes": [dict(item) for item in inscricoes], "atrasados": atrasados, "financeiro_geral": financeiro.resumo_geral(), "financeiro_mes": financeiro.resumo_mes(), "lancamentos": financeiro.lancamentos_recentes(50)}
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
    if banco_online():
        if acao == "limpar_experimentais":
            AulasExperimentais().limpar_historico()
            return {"mensagem": "Historico de aulas experimentais apagado."}
        if acao == "confirmar_experimental":
            AulasExperimentais().marcar_confirmacao(int(dados["aula_id"]))
            return {"mensagem": "Aula experimental confirmada."}
        if acao == "limpar_reservas":
            Agenda().limpar_historico()
            return {"mensagem": "Historico de reservas da quadra apagado."}
        if acao == "confirmar_reserva":
            Agenda().confirmar(int(dados["reserva_id"]))
            return {"mensagem": "Reserva confirmada e adicionada ao calendário."}
        if acao == "confirmar_inscricao":
            nome = Inscricoes().confirmar(int(dados["inscricao_id"]))
            return {"mensagem": f"Inscrição de {nome} confirmada e matrícula criada."}
        if acao == "excluir_pagamento":
            Pagamentos().excluir(int(dados["pagamento_id"]))
            return {"mensagem": "Pagamento excluido."}
        if acao == "excluir_despesa":
            Financeiro().excluir(int(dados["despesa_id"]))
            return {"mensagem": "Despesa excluida."}
        if acao == "excluir_aluno":
            Alunos().excluir(int(dados["aluno_id"]))
            return {"mensagem": "Aluno excluído."}
        if acao == "excluir_turma":
            Turmas().excluir(int(dados["turma_id"]))
            return {"mensagem": "Turma excluída."}
        if acao == "excluir_professor":
            Professores().excluir(int(dados["professor_id"]))
            return {"mensagem": "Professor excluído."}
        if acao == "excluir_modalidade":
            Modalidades().excluir(int(dados["modalidade_id"]))
            return {"mensagem": "Modalidade excluída."}
        if acao == "status_turma":
            Turmas().atualizar_status_aula(int(dados["turma_id"]), dados["status"], dados.get("aviso", ""))
            return {"mensagem": "Status da aula atualizado."}
        if acao == "pagamento":
            resultado = Pagamentos().registrar_mensalidade(int(dados["aluno_id"]), data_do_formulario(dados["data_pagamento"]))
            return {"mensagem": f"Pagamento registrado: {resultado['status']}."}
        if acao == "nova_despesa":
            Financeiro().registrar_despesa(
                dados.get("descricao", ""), dados.get("categoria", "Outros"),
                dados.get("valor", ""), data_do_formulario(dados["data"]), dados.get("observacao", ""),
            )
            return {"mensagem": "Despesa registrada no financeiro."}
        if acao == "nova_turma":
            Turmas().criar(dados["nome"], dados["dia_semana"], dados["dia_semana_2"], dados["horario"], dados.get("professor", ""), dados["modalidade"])
            return {"mensagem": "Turma criada."}
        if acao == "nova_modalidade":
            Modalidades().criar(dados.get("nome", ""))
            return {"mensagem": "Modalidade criada e disponível para novas turmas."}
        if acao == "novo_aluno":
            obrigatorios = ("nome", "data_nascimento", "cpf", "whatsapp", "endereco", "esporte", "frequencia", "como_conheceu", "restricoes_alimentares", "problema_saude", "necessidades_especiais", "menor_idade", "autorizacao_imagem", "turma_id")
            if any(not str(dados.get(campo, "")).strip() for campo in obrigatorios):
                raise ValueError("Preencha todos os campos obrigatorios do cadastro.")
            planos = {"Volei de areia": {"1x por semana - R$ 65,00": 65, "2x por semana - R$ 120,00": 120, "Diaria - R$ 25,00 por dia": 25}, "Futvolei": {"1x por semana - R$ 60,00": 60, "2x por semana - R$ 85,00": 85, "Diaria - R$ 20,00 por dia": 20}}
            valor = planos.get(dados["esporte"], {}).get(dados["frequencia"])
            if valor is None: raise ValueError("Escolha uma frequencia valida para o esporte.")
            valores = {campo: str(dados.get(campo, "")).strip() for campo in Alunos.campos}
            valores.update(telefone=dados["whatsapp"], whatsapp=dados["whatsapp"], modalidade=dados["esporte"], valor_plano=valor, data_inscricao=date.today().isoformat(), dia_vencimento=date.today().day)
            aluno_id = Alunos().cadastrar(**valores)
            turma = next((item for item in Turmas().listar() if item["id"] == int(dados["turma_id"])), None)
            if turma is None: raise ValueError("Turma selecionada nao encontrada.")
            Turmas().vincular_aluno(aluno_id, turma["id"], turma["dia_semana"] if dados["frequencia"].startswith("1x") else "Todos os dias da turma")
            return {"mensagem": "Aluno cadastrado."}
        if acao == "editar_aluno":
            aluno_id = int(dados["aluno_id"])
            valores = {campo: dados.get(campo, "") for campo in Alunos.campos}
            Alunos().atualizar(aluno_id, **valores)
            Turmas().transferir_aluno(aluno_id, int(dados["turma_id"]), valores["frequencia"])
            return {"mensagem": "Dados do aluno e turma atualizados."}
        raise ValueError("Acao administrativa invalida.")
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
    frequencia = aluno.get("frequencia", "") if isinstance(aluno, dict) else aluno["frequencia"]
    return "volei" in (esporte or "").lower().replace("ô", "o") and (frequencia or "").startswith("2x")


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
    identificador = session.get("aluno_portal_id")
    # No banco online, a sessao guarda apenas o identificador. Assim, qualquer
    # alteracao feita no painel aparece imediatamente no Portal do Aluno.
    if banco_online():
        if not identificador:
            return None
        with conectar() as banco:
            return banco.execute(
                "SELECT id, nome, whatsapp, esporte, frequencia, valor_plano, dia_vencimento FROM alunos WHERE id = ?",
                (identificador,),
            ).fetchone()

    aluno_sessao = session.get("aluno_portal")
    if aluno_sessao:
        return aluno_sessao
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
    AulasExperimentais().limpar_vencidas()


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
            resposta_local = None if banco_online() else consultar_aluno_local(cpf)
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
                    banco.execute("INSERT INTO portal_acessos (aluno_id, ultimo_acesso) VALUES (?, ?) ON CONFLICT (aluno_id) DO UPDATE SET ultimo_acesso = EXCLUDED.ultimo_acesso", (aluno["id"], datetime.now().isoformat(timespec="seconds")))
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
    secao = request.args.get("secao", "inicio")
    painel = consultar_painel_local()
    if painel is None:
        flash("O computador da Arena está sem conexão no momento.", "erro")
        painel = {"alunos": [], "turmas": [], "resumo_turmas": {}, "alunos_por_turma": {}, "reservas": [], "pagamentos": [], "despesas": [], "experimentais": [], "experimentais_agendadas": 0, "grupos_experimentais": [], "experimentais_pendentes": [], "modalidades": [], "professores": [], "inscricoes": [], "atrasados": []}
    hoje = date.today()
    calendario_mes = calendar.monthcalendar(hoje.year, hoje.month)
    nomes_dias = ("segunda-feira", "terça-feira", "quarta-feira", "quinta-feira", "sexta-feira", "sábado", "domingo")
    agenda_mensal = {}
    for semana in calendario_mes:
        for numero in semana:
            if not numero:
                continue
            data_atual, itens = date(hoje.year, hoje.month, numero), []
            for turma in painel.get("turmas", []):
                if turma.get("status_aula") == "Aula cancelada":
                    continue
                if nomes_dias[data_atual.weekday()] in ((turma.get("dia_semana") or "").lower(), (turma.get("dia_semana_2") or "").lower()):
                    modalidade = modalidade_para_exibicao(turma.get("modalidade"))
                    itens.append(f"{turma['nome']} · {modalidade}")
            agenda_mensal[numero] = itens
    modelo = "admin_alunos.html" if secao == "alunos" else "admin_financeiro.html" if secao == "pagamentos" else "admin_inicio.html" if secao == "inicio" else "admin_whatsapp.html" if secao == "whatsapp" else "admin_painel.html"
    return render_template(modelo, secao=secao, calendario_mes=calendario_mes, agenda_mensal=agenda_mensal, hoje=hoje.day, mes_calendario=hoje.strftime("%m/%Y"), **painel)


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
        session.clear()
        flash("Entre para acessar sua conta.", "erro")
        return redirect(url_for("portal"))
    pagamentos = None if banco_online() else session.get("pagamentos_portal")
    if pagamentos is None:
        with conectar() as banco:
            pagamentos = banco.execute(
                """SELECT valor, data, data_vencimento, pago_em, status FROM pagamentos
                   WHERE aluno_id = ? OR (aluno_id IS NULL AND aluno = ?) ORDER BY id DESC""",
                (aluno["id"], aluno["nome"]),
            ).fetchall()
    aulas = None if banco_online() else session.get("aulas_portal")
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
    turmas = turmas_experimentais_abertas()
    if request.method == "POST":
        if request.form.get("website"):
            return redirect(url_for("aulas"))
        try:
            turma_id, separador, data_agendamento = request.form.get("turma_id", "").partition("|")
            turma = next((item for item in turmas if str(item["id"]) == turma_id and item["data_agendamento"] == data_agendamento), None)
            if turma is None:
                raise ValueError("Escolha uma turma aberta e um horario disponivel.")
            dados = {"nome": request.form.get("nome", ""), "telefone": request.form.get("telefone", ""), "esporte": turma["modalidade"], "turma": turma["nome"], "data": turma["data_agendamento"], "horario": turma["horario"]}
            if not encaminhar_para_banco_local("aula", dados):
                AulasExperimentais().agendar(**dados)
        except (KeyError, ValueError) as erro:
            flash(str(erro), "erro")
        else:
            flash("Pedido de aula recebido! Em breve confirmaremos pelo WhatsApp.", "sucesso")
            return redirect(url_for("aulas"))
    esportes_experimentais = ["Vôlei de areia", "Futvôlei"]
    for turma in turmas:
        modalidade = turma.get("modalidade")
        if modalidade and modalidade not in esportes_experimentais:
            esportes_experimentais.append(modalidade)
    return render_template("aulas.html", turmas=turmas, esportes_experimentais=esportes_experimentais)


@app.route("/inscricao", methods=["GET", "POST"])
def inscricao():
    turmas = turmas_abertas()
    if request.method == "POST":
        if request.form.get("website"):
            return redirect(url_for("inscricao"))
        try:
            obrigatorios = ("nome", "data_nascimento", "cpf", "whatsapp", "endereco", "esporte", "frequencia", "como_conheceu", "restricoes_alimentares", "problema_saude", "necessidades_especiais", "menor_idade", "autorizacao_imagem", "turma_id")
            if any(not request.form.get(campo, "").strip() for campo in obrigatorios):
                raise ValueError("Preencha todos os campos obrigatórios da inscrição.")
            turma = next((item for item in turmas if str(item["id"]) == request.form.get("turma_id")), None)
            if turma is None:
                raise ValueError("Escolha uma turma aberta e um horário disponível.")
            dados = {campo: request.form.get(campo, "") for campo in Alunos.campos}
            planos = {"Volei de areia": {"1x por semana - R$ 65,00": 65, "2x por semana - R$ 120,00": 120, "Diaria - R$ 25,00 por dia": 25}, "Futvolei": {"1x por semana - R$ 60,00": 60, "2x por semana - R$ 85,00": 85, "Diaria - R$ 20,00 por dia": 20}}
            valor = planos.get(dados["esporte"], {}).get(dados["frequencia"])
            if valor is None:
                raise ValueError("Escolha uma frequência válida para o esporte.")
            dados.update(telefone=dados["whatsapp"], modalidade=dados["esporte"], valor_plano=valor, data_inscricao=date.today().isoformat(), dia_vencimento=date.today().day)
            inscricao_id = Inscricoes().criar(dados, int(turma["id"]))
        except (KeyError, ValueError) as erro:
            flash(str(erro), "erro")
        else:
            session["inscricao_pagamento_id"] = inscricao_id
            return redirect(url_for("pagamento_inscricao", inscricao_id=inscricao_id))
    return render_template("inscricao.html", turmas=turmas)


@app.route("/inscricao/<int:inscricao_id>/pagamento", methods=["GET", "POST"])
def pagamento_inscricao(inscricao_id):
    if session.get("inscricao_pagamento_id") != inscricao_id:
        flash("Abra o pagamento logo após enviar sua inscrição.", "erro")
        return redirect(url_for("inscricao"))
    with conectar() as banco:
        inscricao = banco.execute("SELECT id, nome, status, comprovante_status FROM inscricoes_portal WHERE id = ?", (inscricao_id,)).fetchone()
    if inscricao is None or inscricao["status"] != "Pendente":
        flash("Esta inscrição não está mais disponível para pagamento.", "erro")
        return redirect(url_for("inscricao"))
    if request.method == "POST":
        arquivo = request.files.get("comprovante")
        tipos_permitidos = {"image/jpeg", "image/png", "application/pdf"}
        if not arquivo or not arquivo.filename:
            flash("Selecione o comprovante para enviar.", "erro")
        elif arquivo.mimetype not in tipos_permitidos:
            flash("Envie uma imagem JPG, PNG ou arquivo PDF.", "erro")
        else:
            conteudo = arquivo.read()
            if not conteudo:
                flash("Não foi possível ler o comprovante.", "erro")
            else:
                with conectar() as banco:
                    banco.execute("UPDATE inscricoes_portal SET comprovante = ?, comprovante_nome = ?, comprovante_tipo = ?, comprovante_status = ? WHERE id = ?", (conteudo, arquivo.filename[:180], arquivo.mimetype, "Enviado", inscricao_id))
                flash("Comprovante enviado. Aguarde a confirmação da Arena pelo WhatsApp.", "sucesso")
                return redirect(url_for("inicio"))
    return render_template("pagamento_inscricao.html", inscricao=inscricao)


@app.get("/inscricao/<int:inscricao_id>/confirmacao")
def confirmacao_inscricao(inscricao_id):
    if session.get("inscricao_pagamento_id") != inscricao_id:
        flash("Não encontramos esta inscrição neste navegador.", "erro")
        return redirect(url_for("inscricao"))
    with conectar() as banco:
        inscricao = banco.execute("SELECT nome, status, comprovante_status FROM inscricoes_portal WHERE id = ?", (inscricao_id,)).fetchone()
    if inscricao is None or inscricao["status"] != "Pendente":
        return redirect(url_for("inscricao"))
    return render_template("confirmacao_inscricao.html", inscricao=inscricao)


@app.get("/admin/inscricoes/<int:inscricao_id>/comprovante")
@exige_admin
def comprovante_inscricao(inscricao_id):
    with conectar() as banco:
        comprovante = banco.execute("SELECT comprovante, comprovante_nome, comprovante_tipo FROM inscricoes_portal WHERE id = ?", (inscricao_id,)).fetchone()
    if comprovante is None or not comprovante["comprovante"]:
        flash("Esta inscrição ainda não enviou comprovante.", "erro")
        return redirect(url_for("painel_admin", secao="whatsapp"))
    return send_file(BytesIO(bytes(comprovante["comprovante"])), mimetype=comprovante["comprovante_tipo"] or "application/octet-stream", as_attachment=False, download_name=comprovante["comprovante_nome"] or "comprovante")


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
