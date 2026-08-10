"""Portal web publico da Arena Alpha."""
import os
import calendar
import json
import hmac
import hashlib
import unicodedata
import uuid
from io import BytesIO
from functools import wraps
from datetime import date, datetime, timedelta
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

import qrcode

from flask import Flask, flash, redirect, render_template, request, session, url_for, send_file
from werkzeug.security import check_password_hash

from database.banco import conectar, criar_tabelas, normalizar_telefone_brasil
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

# A chave Pix e publica por natureza. Pode ser alterada no Render pela variavel
# PIX_NUBANK_CHAVE, sem mudar o codigo do portal.
PIX_NUBANK_CHAVE = os.environ.get("PIX_NUBANK_CHAVE", "ef3a3543-0c49-44be-b4a7-966448eb9193")
PIX_BENEFICIARIO = os.environ.get("PIX_BENEFICIARIO", "ARENA ALPHA")
PIX_CIDADE = os.environ.get("PIX_CIDADE", "RIO DE JANEIRO")


def banco_online():
    return os.environ.get("DATABASE_URL", "").startswith(("postgres://", "postgresql://"))


def campo_pix(identificador, valor):
    texto = str(valor)
    return f"{identificador}{len(texto):02d}{texto}"


def crc16_pix(texto):
    """CRC-16/CCITT-FALSE exigido pelo padrao Pix Copia e Cola."""
    crc = 0xFFFF
    for caractere in texto.encode("utf-8"):
        crc ^= caractere << 8
        for _ in range(8):
            crc = ((crc << 1) ^ 0x1021) & 0xFFFF if crc & 0x8000 else (crc << 1) & 0xFFFF
    return f"{crc:04X}"


def codigo_pix(valor, identificador="***"):
    """Gera um Pix com o valor definido para a mensalidade atual."""
    chave = PIX_NUBANK_CHAVE.strip()
    if not chave:
        raise ValueError("A chave Pix da Arena ainda nao foi configurada.")
    conta = campo_pix("00", "BR.GOV.BCB.PIX") + campo_pix("01", chave)
    nome = PIX_BENEFICIARIO.strip().upper()[:25] or "ARENA ALPHA"
    cidade = PIX_CIDADE.strip().upper()[:15] or "RIO DE JANEIRO"
    referencia = "".join(c for c in str(identificador).upper() if c.isalnum())[:25] or "***"
    corpo = (
        campo_pix("00", "01") + campo_pix("26", conta) + campo_pix("52", "0000")
        + campo_pix("53", "986") + campo_pix("54", f"{float(valor):.2f}")
        + campo_pix("58", "BR") + campo_pix("59", nome) + campo_pix("60", cidade)
        + campo_pix("62", campo_pix("05", referencia)) + "6304"
    )
    return corpo + crc16_pix(corpo)


def valor_pix_mensalidade(aluno, pagamentos, referencia=None):
    """Aplica a regra de desconto antes de montar a cobranca Pix."""
    referencia = referencia or date.today()
    valor = float(aluno["valor_plano"] or 0)
    frequencia = (aluno["frequencia"] or "").lower()
    esporte = unicodedata.normalize("NFKD", aluno["esporte"] or "").encode("ascii", "ignore").decode("ascii").lower()
    vencimento = Pagamentos()._vencimento_do_mes(aluno["dia_vencimento"], referencia)
    if esporte == "volei de areia" and frequencia.startswith("2x") and len(pagamentos or []) >= 1 and referencia <= vencimento:
        return max(valor - 20, 0), vencimento, 20
    return valor, vencimento, 0


def proxima_fatura_pix(aluno, pagamentos):
    """Retorna a proxima mensalidade que pode receber um novo Pix.

    O mes ja pago e qualquer fatura vencida ficam apenas no historico.
    """
    hoje = date.today()
    referencia = hoje.replace(day=1)
    meses_pagos = set()
    for pagamento in pagamentos or []:
        pago_em = pagamento.get("pago_em") if isinstance(pagamento, dict) else pagamento["pago_em"]
        if pago_em and len(str(pago_em)) >= 7:
            meses_pagos.add(str(pago_em)[:7])
    while True:
        vencimento = Pagamentos()._vencimento_do_mes(aluno["dia_vencimento"], referencia)
        if referencia.strftime("%Y-%m") not in meses_pagos and hoje <= vencimento:
            return referencia
        ano, mes = referencia.year + (referencia.month == 12), 1 if referencia.month == 12 else referencia.month + 1
        referencia = date(ano, mes, 1)


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


def chave_dia_semana(valor):
    """Compara dias do calendário mesmo quando foram cadastrados sem acento."""
    return "".join(
        caractere for caractere in unicodedata.normalize("NFD", str(valor or "").lower())
        if unicodedata.category(caractere) != "Mn"
    ).strip()


def valor_da_turma(turma, frequencia, valor_padrao):
    """Usa os valores configurados na turma; mantém o preço antigo enquanto ela não for configurada."""
    campo = "valor_1x" if str(frequencia).startswith("1x") else "valor_2x" if str(frequencia).startswith("2x") else "valor_diaria"
    try:
        valor = float(turma[campo] or 0)
    except (KeyError, TypeError, ValueError):
        valor = 0
    return valor if valor > 0 else valor_padrao


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
        modalidade = modalidade_para_exibicao(aula.get("esporte"))
        chave = (data_aula, horario, turma, modalidade)
        grupos.setdefault(chave, []).append(aula)
    resultado = []
    for (data_aula, horario, turma, modalidade), participantes in sorted(grupos.items(), key=lambda item: (item[0][0], item[0][1], item[0][2])):
        resultado.append({
            "data": data_aula.strftime("%d/%m/%Y"), "horario": horario,
            "turma": turma, "modalidade": modalidade, "participantes": sorted(participantes, key=lambda item: item["nome"].lower()),
        })
    return sum(len(grupo["participantes"]) for grupo in resultado), resultado


def consultar_painel_local():
    if banco_online():
        with conectar() as banco:
            alunos = banco.execute("SELECT a.*, (SELECT m.turma_id FROM matriculas_turma m WHERE m.aluno_id = a.id ORDER BY m.id LIMIT 1) AS turma_id FROM alunos a ORDER BY a.nome").fetchall()
            turmas = banco.execute("SELECT id, nome, modalidade, descricao, dia_semana, dia_semana_2, horario, professor, valor_1x, valor_2x, valor_diaria, status_aula, aviso_aula FROM turmas ORDER BY horario").fetchall()
            reservas = banco.execute("SELECT id, cliente, whatsapp, data, horario, tipo_locacao, valor, status FROM agenda ORDER BY id DESC LIMIT 30").fetchall()
            pagamentos = banco.execute("SELECT id, aluno, valor, pago_em, data_vencimento, status FROM pagamentos ORDER BY id DESC LIMIT 30").fetchall()
            pagamentos_rifa = banco.execute("SELECT id, aluno, valor, pago_em, status FROM pagamentos WHERE status = ? OR aluno LIKE ? ORDER BY id DESC", ("Rifa confirmada", "Rifa %")).fetchall()
            total_mensalistas = banco.execute("SELECT COALESCE(SUM(p.valor), 0) AS total FROM pagamentos p JOIN alunos a ON a.id = p.aluno_id WHERE p.pago_em IS NOT NULL AND LOWER(COALESCE(a.frequencia, '')) NOT LIKE ?", ("%diar%",)).fetchone()["total"]
            total_diaristas = banco.execute("SELECT COALESCE(SUM(p.valor), 0) AS total FROM pagamentos p JOIN alunos a ON a.id = p.aluno_id WHERE p.pago_em IS NOT NULL AND LOWER(COALESCE(a.frequencia, '')) LIKE ?", ("%diar%",)).fetchone()["total"]
            total_locacao_espaco = banco.execute("SELECT COALESCE(SUM(valor), 0) AS total FROM agenda WHERE status = ? AND LOWER(COALESCE(tipo_locacao, '')) LIKE ?", ("Confirmada", "%evento%")).fetchone()["total"]
            total_locacao_horas = banco.execute("SELECT COALESCE(SUM(valor), 0) AS total FROM agenda WHERE status = ? AND LOWER(COALESCE(tipo_locacao, '')) NOT LIKE ?", ("Confirmada", "%evento%")).fetchone()["total"]
            despesas = banco.execute("SELECT id, descricao, categoria, valor, data FROM despesas ORDER BY id DESC LIMIT 30").fetchall()
            experimentais = banco.execute("SELECT id, nome, telefone, esporte, data, horario, turma, confirmacao_enviada FROM aulas_experimentais ORDER BY data, horario, id").fetchall()
            modalidades = Modalidades().listar()
            professores = banco.execute("SELECT id, nome, telefone, especialidade, endereco, usuario FROM professores ORDER BY nome").fetchall()
            professor_turmas = banco.execute("SELECT pt.professor_id, pt.turma_id, p.nome AS professor, t.nome AS turma, t.modalidade, t.horario FROM professor_turmas pt JOIN professores p ON p.id=pt.professor_id JOIN turmas t ON t.id=pt.turma_id ORDER BY p.nome, t.horario").fetchall()
            inscricoes = banco.execute("SELECT i.*, t.nome AS turma_nome, t.horario AS turma_horario FROM inscricoes_portal i JOIN turmas t ON t.id = i.turma_id WHERE i.status = ? ORDER BY i.id DESC", ("Pendente",)).fetchall()
            rifa_numeros = banco.execute("SELECT numero, nome, whatsapp, lote, status, criado_em FROM rifa_numeros ORDER BY numero").fetchall()
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
        rifa_lista = [dict(item) for item in rifa_numeros]
        rifa_confirmados = [item for item in rifa_lista if item["status"] == "Confirmado"]
        rifa_pagamentos_lista = [dict(item) for item in pagamentos_rifa]
        rifa_financeiro = {"receita": sum(float(item.get("valor") or 0) for item in rifa_pagamentos_lista), "numeros_confirmados": len(rifa_confirmados), "compradores": len({item["lote"] for item in rifa_confirmados}), "pagamentos": rifa_pagamentos_lista}
        financeiro_geral = financeiro.resumo_geral()
        receitas_locacao = float(total_locacao_espaco or 0) + float(total_locacao_horas or 0)
        financeiro_categorias = {"caixa": financeiro_geral["caixa"] + receitas_locacao, "receitas": financeiro_geral["receitas"] + receitas_locacao, "mensalistas": float(total_mensalistas or 0), "diaristas": float(total_diaristas or 0), "locacao_espaco": float(total_locacao_espaco or 0), "locacao_horas": float(total_locacao_horas or 0), "rifa": rifa_financeiro["receita"]}
        return {"alunos": [dict(item) for item in alunos], "turmas": [dict(item) for item in turmas], "resumo_turmas": resumo_turmas, "alunos_por_turma": alunos_por_turma, "reservas": [dict(item) for item in reservas], "pagamentos": [dict(item) for item in pagamentos], "despesas": [dict(item) for item in despesas], "experimentais": [dict(item) for item in experimentais], "experimentais_agendadas": experimentais_agendadas, "grupos_experimentais": grupos_experimentais, "experimentais_pendentes": experimentais_pendentes, "modalidades": [dict(item) for item in modalidades], "professores": [dict(item) for item in professores], "professor_turmas": [dict(item) for item in professor_turmas], "inscricoes": [dict(item) for item in inscricoes], "rifa_numeros": rifa_lista, "rifa_pendentes": [item for item in rifa_lista if item["status"] == "Pendente"], "rifa_financeiro": rifa_financeiro, "financeiro_categorias": financeiro_categorias, "atrasados": atrasados, "financeiro_geral": financeiro_geral, "financeiro_mes": financeiro.resumo_mes(), "lancamentos": financeiro.lancamentos_recentes(50)}
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
        if acao == "excluir_experimental":
            AulasExperimentais().excluir(int(dados["aula_id"]))
            return {"mensagem": "Aula experimental excluída."}
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
        if acao == "confirmar_rifa":
            lote = dados.get("lote", "")
            with conectar() as banco:
                itens = banco.execute("SELECT numero, nome, whatsapp FROM rifa_numeros WHERE lote = ? AND status = 'Pendente' ORDER BY numero", (lote,)).fetchall()
                registro = itens[0] if itens else None
                if registro is None: raise ValueError("Esta solicitacao da rifa nao esta mais pendente.")
                banco.execute("UPDATE rifa_numeros SET status = 'Confirmado', confirmado_em = ? WHERE lote = ? AND status = 'Pendente'", (datetime.now().isoformat(timespec="seconds"), lote))
                quantidade, valor = len(itens), len(itens) * 10.0
                numeros = ", ".join(f"{item['numero']:03d}" for item in itens)
                banco.execute("""INSERT INTO pagamentos (aluno, valor, data, aluno_id, data_vencimento, valor_original, desconto, pago_em, status)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""", (f"Rifa · {registro['nome']} · números {numeros}", valor, date.today().strftime("%d/%m/%Y"), None, None, valor, 0, date.today().isoformat(), "Rifa confirmada"))
            return {"mensagem": "Numeros da rifa confirmados e lancados no caixa.", "nome": registro["nome"], "whatsapp": registro["whatsapp"], "quantidade": quantidade}
        if acao == "cancelar_rifa":
            with conectar() as banco: banco.execute("DELETE FROM rifa_numeros WHERE lote = ? AND status = 'Pendente'", (dados.get("lote", ""),))
            return {"mensagem": "Solicitacao da rifa removida."}
        if acao == "liberar_numero_rifa":
            numero = int(dados["numero"])
            with conectar() as banco:
                banco.execute("DELETE FROM rifa_numeros WHERE numero = ?", (numero,))
            return {"mensagem": f"Numero {numero:03d} liberado para a rifa."}
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
        if acao == "editar_turma":
            Turmas().atualizar_configuracao(int(dados["turma_id"]), dados["nome"], dados["modalidade"], dados.get("descricao", ""), dados["dia_semana"], dados.get("dia_semana_2", ""), dados["horario"], dados.get("professor", ""), dados.get("valor_1x", 0), dados.get("valor_2x", 0), dados.get("valor_diaria", 0))
            return {"mensagem": "Turma, descrição e valores atualizados."}
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
        if acao == "novo_professor":
            professor_id = Professores().cadastrar(dados["nome"], dados.get("telefone", ""), dados.get("especialidade", ""), dados.get("endereco", ""), "", "12345")
            with conectar() as banco:
                professor = banco.execute("SELECT usuario FROM professores WHERE id = ?", (professor_id,)).fetchone()
            return {"mensagem": f"Professor cadastrado. Usuário: {professor['usuario']} · senha inicial: 12345."}
        if acao == "vincular_professor":
            with conectar() as banco:
                professor = banco.execute("SELECT nome FROM professores WHERE id = ?", (int(dados["professor_id"]),)).fetchone()
                if professor is None: raise ValueError("Professor não encontrado.")
                banco.execute("INSERT INTO professor_turmas (professor_id, turma_id) VALUES (?, ?) ON CONFLICT (professor_id, turma_id) DO NOTHING", (int(dados["professor_id"]), int(dados["turma_id"])))
            return {"mensagem": "Professor vinculado à turma."}
        if acao == "remover_vinculo_professor":
            with conectar() as banco: banco.execute("DELETE FROM professor_turmas WHERE professor_id = ? AND turma_id = ?", (int(dados["professor_id"]), int(dados["turma_id"])))
            return {"mensagem": "Vínculo removido."}
        if acao == "novo_aluno":
            obrigatorios = ("nome", "data_nascimento", "cpf", "whatsapp", "endereco", "esporte", "frequencia", "como_conheceu", "restricoes_alimentares", "problema_saude", "necessidades_especiais", "menor_idade", "autorizacao_imagem", "turma_id")
            if any(not str(dados.get(campo, "")).strip() for campo in obrigatorios):
                raise ValueError("Preencha todos os campos obrigatorios do cadastro.")
            planos = {"Volei de areia": {"1x por semana - R$ 65,00": 65, "2x por semana - R$ 120,00": 120, "Diaria - R$ 25,00 por dia": 25}, "Futvolei": {"1x por semana - R$ 60,00": 60, "2x por semana - R$ 85,00": 85, "Diaria - R$ 20,00 por dia": 20}}
            valor = next((preco for plano, preco in planos.get(dados["esporte"], {}).items() if dados["frequencia"].startswith(plano.split(" - ")[0])), None)
            if valor is None: raise ValueError("Escolha uma frequencia valida para o esporte.")
            turma = next((item for item in Turmas().listar() if item["id"] == int(dados["turma_id"])), None)
            if turma is None: raise ValueError("Turma selecionada nao encontrada.")
            valor = valor_da_turma(turma, dados["frequencia"], valor)
            valores = {campo: str(dados.get(campo, "")).strip() for campo in Alunos.campos}
            valores.update(telefone=dados["whatsapp"], whatsapp=dados["whatsapp"], modalidade=dados["esporte"], valor_plano=valor, data_inscricao=date.today().isoformat(), dia_vencimento=date.today().day)
            aluno_id = Alunos().cadastrar(**valores)
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


def cpf_para_acesso(valor):
    """Normaliza CPFs antigos que foram salvos sem o zero inicial."""
    cpf = somente_numeros(valor)
    return cpf.zfill(11) if len(cpf) in (10, 11) else cpf


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
    Professores().garantir_padrao()
    AulasExperimentais().limpar_vencidas()


@app.get("/")
def inicio():
    return render_template("inicio.html")


@app.route("/portal", methods=["GET", "POST"])
def portal():
    if request.method == "POST":
        cpf = cpf_para_acesso(request.form.get("cpf"))
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
                aluno = next((item for item in alunos if cpf_para_acesso(item["cpf"]) == cpf), None)
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


@app.route("/professor", methods=["GET", "POST"])
def professor_login():
    if request.method == "POST":
        with conectar() as banco:
            professor = banco.execute("SELECT * FROM professores WHERE usuario = ?", (request.form.get("usuario", "").strip(),)).fetchone()
        if professor and professor["senha_hash"] and check_password_hash(professor["senha_hash"], request.form.get("senha", "")):
            session.clear(); session["professor_id"] = professor["id"]
            return redirect(url_for("painel_professor"))
        flash("Usuário ou senha incorretos.", "erro")
    return render_template("professor_login.html")


@app.get("/professor/painel")
def painel_professor():
    professor_id = session.get("professor_id")
    if not professor_id: return redirect(url_for("professor_login"))
    with conectar() as banco:
        professor = banco.execute("SELECT * FROM professores WHERE id = ?", (professor_id,)).fetchone()
        turmas = banco.execute("SELECT DISTINCT t.* FROM turmas t LEFT JOIN professor_turmas pt ON pt.turma_id = t.id WHERE pt.professor_id = ? OR t.professor = ? ORDER BY t.horario", (professor_id, professor["nome"])).fetchall() if professor else []
        ids = [turma["id"] for turma in turmas]
        alunos = []
        for turma_id in ids:
            alunos.extend(Turmas().alunos_da_turma(turma_id))
    return render_template("professor_painel.html", professor=professor, turmas=turmas, alunos=alunos)


@app.post("/professor/aula")
def acao_professor_aula():
    professor_id = session.get("professor_id")
    if not professor_id: return redirect(url_for("professor_login"))
    with conectar() as banco:
        professor = banco.execute("SELECT nome FROM professores WHERE id = ?", (professor_id,)).fetchone()
        turma = banco.execute(
            """SELECT DISTINCT t.id FROM turmas t
               LEFT JOIN professor_turmas pt ON pt.turma_id = t.id
               WHERE t.id = ? AND (pt.professor_id = ? OR t.professor = ?)""",
            (int(request.form["turma_id"]), professor_id, professor["nome"]),
        ).fetchone() if professor else None
    if turma is None:
        flash("Você não tem permissão para alterar esta turma.", "erro")
    else:
        try: Turmas().atualizar_status_aula(int(request.form["turma_id"]), request.form["status"], request.form.get("aviso", ""))
        except ValueError as erro: flash(str(erro), "erro")
        else: flash("Status da aula atualizado.", "sucesso")
    return redirect(url_for("painel_professor"))


@app.get("/admin/painel")
@exige_admin
def painel_admin():
    secao = request.args.get("secao", "inicio")
    painel = consultar_painel_local()
    if painel is None:
        flash("O computador da Arena está sem conexão no momento.", "erro")
        painel = {"alunos": [], "turmas": [], "resumo_turmas": {}, "alunos_por_turma": {}, "reservas": [], "pagamentos": [], "despesas": [], "experimentais": [], "experimentais_agendadas": 0, "grupos_experimentais": [], "experimentais_pendentes": [], "modalidades": [], "professores": [], "inscricoes": [], "rifa_numeros": [], "rifa_pendentes": [], "atrasados": []}
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
                dia_atual = chave_dia_semana(nomes_dias[data_atual.weekday()])
                dias_da_turma = {
                    chave_dia_semana(turma.get("dia_semana")),
                    chave_dia_semana(turma.get("dia_semana_2")),
                }
                if dia_atual in dias_da_turma:
                    modalidade = modalidade_para_exibicao(turma.get("modalidade"))
                    itens.append(f"{turma['nome']} · {modalidade}")
            agenda_mensal[numero] = itens
    agenda_experimentais_mensal = {}
    for aula in painel.get("experimentais", []):
        if not aula.get("confirmacao_enviada"):
            continue
        texto_data = str(aula.get("data") or "")
        try:
            data_aula = datetime.strptime(texto_data, "%Y-%m-%d").date()
        except ValueError:
            try:
                data_aula = datetime.strptime(texto_data, "%d/%m/%Y").date()
            except ValueError:
                continue
        if data_aula.year != hoje.year or data_aula.month != hoje.month:
            continue
        primeiro_nome = str(aula.get("nome") or "Participante").strip().split()[0]
        turma = aula.get("turma") or aula.get("esporte") or "Turma não informada"
        agenda_experimentais_mensal.setdefault(data_aula.day, []).append({"nome": primeiro_nome, "turma": turma})
    reservas_pendentes = [item for item in painel.get("reservas", []) if (item.get("status") or "Pendente") == "Pendente"]
    avisos_pendentes = {
        "experimentais": len(painel.get("experimentais_pendentes", [])),
        "inscricoes": len(painel.get("inscricoes", [])),
        "reservas": len(reservas_pendentes),
        "rifa": len(painel.get("rifa_pendentes", [])),
    }
    avisos_total = sum(avisos_pendentes.values())
    modelo = "admin_alunos.html" if secao == "alunos" else "admin_turmas.html" if secao == "turmas" else "admin_professores.html" if secao == "professores" else "admin_financeiro.html" if secao == "pagamentos" else "admin_inicio.html" if secao == "inicio" else "admin_experimentais.html" if secao == "experimentais" else "admin_whatsapp.html" if secao == "whatsapp" else "admin_rifa.html" if secao == "rifa" else "admin_administracao.html" if secao == "administracao" else "admin_painel.html"
    return render_template(modelo, secao=secao, calendario_mes=calendario_mes, agenda_mensal=agenda_mensal, agenda_experimentais_mensal=agenda_experimentais_mensal, hoje=hoje.day, mes_calendario=hoje.strftime("%m/%Y"), avisos_pendentes=avisos_pendentes, avisos_total=avisos_total, **painel)


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
    referencia_pix = proxima_fatura_pix(aluno, pagamentos)
    valor_pix, vencimento_pix, desconto_pix = valor_pix_mensalidade(aluno, pagamentos, referencia_pix)
    codigo_pix_mensalidade = codigo_pix(valor_pix, f"ALUNO{aluno['id']}") if valor_pix > 0 else ""
    return render_template(
        "portal_conta.html", aluno=aluno, pagamentos=pagamentos, aulas=aulas,
        situacao_pagamento=situacao_pagamento_portal(aluno, pagamentos), desconto_volei=tem_desconto_volei(aluno),
        valor_pix=valor_pix, vencimento_pix=vencimento_pix, desconto_pix=desconto_pix,
        codigo_pix_mensalidade=codigo_pix_mensalidade, referencia_pix=referencia_pix,
    )


@app.get("/portal/pix/qr")
def qr_pix_mensalidade():
    """Entrega o QR Code somente para o aluno que estiver logado."""
    aluno = aluno_do_portal()
    if not aluno:
        return redirect(url_for("portal"))
    pagamentos = session.get("pagamentos_portal") if not banco_online() else None
    if pagamentos is None:
        with conectar() as banco:
            pagamentos = banco.execute(
                "SELECT * FROM pagamentos WHERE aluno_id = ? ORDER BY id DESC", (aluno["id"],)
            ).fetchall()
    if aluno["valor_plano"] is None or aluno["dia_vencimento"] is None:
        return "Mensalidade indisponivel.", 404
    referencia_pix = proxima_fatura_pix(aluno, pagamentos)
    valor, _, _ = valor_pix_mensalidade(aluno, pagamentos, referencia_pix)
    imagem = qrcode.make(codigo_pix(valor, f"ALUNO{aluno['id']}"))
    arquivo = BytesIO()
    imagem.save(arquivo, "PNG")
    arquivo.seek(0)
    return send_file(arquivo, mimetype="image/png", download_name="pix-mensalidade-arena-alpha.png")


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
            if modalidade_para_exibicao(turma["modalidade"]) != modalidade_para_exibicao(dados["esporte"]):
                raise ValueError("Escolha uma turma da modalidade selecionada.")
            planos = {"Volei de areia": {"1x por semana - R$ 65,00": 65, "2x por semana - R$ 120,00": 120, "Diaria - R$ 25,00 por dia": 25}, "Futvolei": {"1x por semana - R$ 60,00": 60, "2x por semana - R$ 85,00": 85, "Diaria - R$ 20,00 por dia": 20}}
            valor = next((preco for plano, preco in planos.get(dados["esporte"], {}).items() if dados["frequencia"].startswith(plano.split(" - ")[0])), None)
            if valor is None:
                raise ValueError("Escolha uma frequência válida para o esporte.")
            valor = valor_da_turma(turma, dados["frequencia"], valor)
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
        inscricao = banco.execute("SELECT id, nome, valor_plano, status, comprovante_status FROM inscricoes_portal WHERE id = ?", (inscricao_id,)).fetchone()
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
    valor_pix = float(inscricao["valor_plano"] or 0)
    return render_template(
        "pagamento_inscricao.html", inscricao=inscricao, valor_pix=valor_pix,
        codigo_pix_inscricao=codigo_pix(valor_pix, f"INSCRICAO{inscricao_id}") if valor_pix > 0 else "",
    )


@app.get("/inscricao/<int:inscricao_id>/pix/qr")
def qr_pix_inscricao(inscricao_id):
    """QR Code Nubank da inscricao que acabou de ser enviada."""
    if session.get("inscricao_pagamento_id") != inscricao_id:
        return redirect(url_for("inscricao"))
    with conectar() as banco:
        inscricao = banco.execute(
            "SELECT valor_plano, status FROM inscricoes_portal WHERE id = ?", (inscricao_id,)
        ).fetchone()
    if inscricao is None or inscricao["status"] != "Pendente" or not inscricao["valor_plano"]:
        return "Pagamento indisponivel.", 404
    imagem = qrcode.make(codigo_pix(float(inscricao["valor_plano"]), f"INSCRICAO{inscricao_id}"))
    arquivo = BytesIO()
    imagem.save(arquivo, "PNG")
    arquivo.seek(0)
    return send_file(arquivo, mimetype="image/png", download_name="pix-inscricao-arena-alpha.png")


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


@app.route("/rifa", methods=["GET", "POST"])
def rifa():
    with conectar() as banco:
        ocupados = {item["numero"]: item["status"] for item in banco.execute("SELECT numero, status FROM rifa_numeros").fetchall()}
    if request.method == "POST":
        try:
            nome = request.form.get("nome", "").strip()
            whatsapp = normalizar_telefone_brasil(request.form.get("whatsapp", ""))
            numeros = sorted({int(numero) for numero in request.form.getlist("numeros")})
            if not nome or len(whatsapp) < 10 or len(whatsapp) > 13: raise ValueError("Informe seu nome e um WhatsApp com DDD válido.")
            if not numeros or any(numero < 1 or numero > 100 for numero in numeros): raise ValueError("Escolha ao menos um número da rifa.")
            indisponiveis = [str(numero).zfill(3) for numero in numeros if numero in ocupados]
            if indisponiveis: raise ValueError("Estes números não estão mais disponíveis: " + ", ".join(indisponiveis))
            lote = uuid.uuid4().hex
            with conectar() as banco:
                if banco_online():
                    banco.execute("SELECT pg_advisory_xact_lock(?)", (847221,))
                ocupados_agora = {item["numero"] for item in banco.execute("SELECT numero FROM rifa_numeros").fetchall()}
                indisponiveis_agora = [str(numero).zfill(3) for numero in numeros if numero in ocupados_agora]
                if indisponiveis_agora:
                    raise ValueError("Estes números acabaram de ser reservados: " + ", ".join(indisponiveis_agora) + ". Escolha outro número.")
                for numero in numeros:
                    banco.execute("INSERT INTO rifa_numeros (numero, nome, whatsapp, lote, status, criado_em) VALUES (?, ?, ?, ?, 'Pendente', ?)", (numero, nome, whatsapp, lote, datetime.now().isoformat(timespec="seconds")))
            session["rifa_lote"] = lote
            return renderizar_pagamento_rifa(lote)
        except ValueError as erro:
            flash(str(erro), "erro")
        except Exception:
            app.logger.exception("Falha ao registrar uma solicitação da rifa")
            flash("Não foi possível reservar os números agora. Atualize a página e tente novamente.", "erro")
    return render_template("rifa.html", ocupados=ocupados)


def renderizar_pagamento_rifa(lote):
    with conectar() as banco:
        itens = banco.execute("SELECT numero, nome, whatsapp FROM rifa_numeros WHERE lote = ? AND status = 'Pendente' ORDER BY numero", (lote,)).fetchall()
    if not itens: return redirect(url_for("rifa"))
    return render_template("rifa_pagamento.html", itens=itens, lote=lote, valor=len(itens) * 10, codigo_pix_rifa=codigo_pix(len(itens) * 10, "RIFA" + lote[:12]))


@app.get("/rifa/pagamento")
@app.get("/rifa/pagamento/<lote>")
def pagamento_rifa(lote=None):
    return renderizar_pagamento_rifa(lote or request.args.get("lote") or session.get("rifa_lote"))


@app.get("/rifa/pix/qr")
@app.get("/rifa/pix/qr/<lote>")
def qr_pix_rifa(lote=None):
    lote = lote or request.args.get("lote") or session.get("rifa_lote")
    if not lote: return redirect(url_for("rifa"))
    with conectar() as banco: quantidade = banco.execute("SELECT COUNT(*) AS quantidade FROM rifa_numeros WHERE lote = ? AND status = 'Pendente'", (lote,)).fetchone()["quantidade"]
    imagem = qrcode.make(codigo_pix(quantidade * 10, "RIFA" + lote[:12]))
    arquivo = BytesIO(); imagem.save(arquivo, "PNG"); arquivo.seek(0)
    return send_file(arquivo, mimetype="image/png", download_name="pix-rifa-arena-alpha.png")


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
