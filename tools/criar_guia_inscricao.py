from pathlib import Path
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import cm
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Image, Table, TableStyle


ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "output" / "pdf" / "guia-inscricao-portal-arena-alpha.pdf"
OUTPUT.parent.mkdir(parents=True, exist_ok=True)

styles = getSampleStyleSheet()
styles.add(ParagraphStyle(name="TituloAlpha", parent=styles["Title"], fontName="Helvetica-Bold", fontSize=24, leading=29, textColor=colors.HexColor("#e69b22"), spaceAfter=12))
styles.add(ParagraphStyle(name="SubtituloAlpha", parent=styles["Heading2"], fontName="Helvetica-Bold", fontSize=14, leading=18, textColor=colors.HexColor("#e69b22"), spaceBefore=14, spaceAfter=7))
styles.add(ParagraphStyle(name="TextoAlpha", parent=styles["BodyText"], fontName="Helvetica", fontSize=10.5, leading=15, textColor=colors.HexColor("#202124")))

doc = SimpleDocTemplate(str(OUTPUT), pagesize=A4, rightMargin=2 * cm, leftMargin=2 * cm, topMargin=1.5 * cm, bottomMargin=1.5 * cm)
conteudo = []
logo = ROOT / "static" / "arena-alpha-logo.jpeg"
if logo.exists():
    imagem = Image(str(logo), width=3.3 * cm, height=3.3 * cm)
    cabecalho = Table([[imagem, Paragraph("<b>ARENA ALPHA</b><br/>Guia de inscrição e acesso ao Portal do Aluno", styles["TituloAlpha"])]], colWidths=[4 * cm, 12 * cm])
    cabecalho.setStyle(TableStyle([("VALIGN", (0, 0), (-1, -1), "MIDDLE"), ("LINEBELOW", (0, 0), (-1, -1), 1, colors.HexColor("#e69b22")), ("BOTTOMPADDING", (0, 0), (-1, -1), 10)]))
    conteudo.append(cabecalho)
else:
    conteudo.append(Paragraph("ARENA ALPHA", styles["TituloAlpha"]))
conteudo.append(Spacer(1, 12))
conteudo.append(Paragraph("Siga este passo a passo para se inscrever nas turmas e depois entrar no Portal do Aluno.", styles["TextoAlpha"]))

conteudo.append(Paragraph("1. Fazer a inscrição", styles["SubtituloAlpha"]))
passos_inscricao = [
    "Abra o site da Arena Alpha e toque em <b>Fazer inscrição</b>.",
    "Preencha todos os dados: nome, data de nascimento, CPF, WhatsApp, endereço, modalidade, frequência e informações de saúde.",
    "Escolha somente uma turma e horário disponíveis.",
    "Confira os dados e toque em <b>Enviar inscrição</b>.",
]
for passo in passos_inscricao:
    conteudo.append(Paragraph("• " + passo, styles["TextoAlpha"]))

conteudo.append(Paragraph("2. Pagamento e comprovante", styles["SubtituloAlpha"]))
passos_pagamento = [
    "Após enviar a inscrição, a tela do PIX será aberta.",
    "Faça o pagamento usando o QR Code ou a chave PIX exibida.",
    "Toque em <b>Enviar comprovante</b> e escolha a imagem ou PDF do pagamento.",
    "Uma nova aba mostrará que a inscrição está aguardando a confirmação da Arena Alpha pelo WhatsApp.",
]
for passo in passos_pagamento:
    conteudo.append(Paragraph("• " + passo, styles["TextoAlpha"]))

conteudo.append(Paragraph("3. Entrar no Portal do Aluno", styles["SubtituloAlpha"]))
passos_portal = [
    "Depois que a Arena confirmar sua matrícula, abra <b>Portal do aluno</b> no site.",
    "Digite somente o <b>CPF cadastrado na inscrição</b>. Não precisa criar senha.",
    "No portal você verá suas aulas, datas, situação de pagamento e poderá solicitar horários e eventos.",
]
for passo in passos_portal:
    conteudo.append(Paragraph("• " + passo, styles["TextoAlpha"]))

conteudo.append(Spacer(1, 16))
aviso = Table([[Paragraph("<b>Importante:</b> a inscrição só fica ativa depois que a Arena Alpha conferir o comprovante e enviar a confirmação pelo WhatsApp.", styles["TextoAlpha"])]], colWidths=[16.5 * cm])
aviso.setStyle(TableStyle([("BACKGROUND", (0, 0), (-1, -1), colors.HexColor("#fff3dc")), ("BOX", (0, 0), (-1, -1), 1, colors.HexColor("#e69b22")), ("LEFTPADDING", (0, 0), (-1, -1), 10), ("RIGHTPADDING", (0, 0), (-1, -1), 10), ("TOPPADDING", (0, 0), (-1, -1), 10), ("BOTTOMPADDING", (0, 0), (-1, -1), 10)]))
conteudo.append(aviso)
conteudo.append(Spacer(1, 18))
conteudo.append(Paragraph("Arena Alpha - Vôlei de Areia e Futvôlei", styles["TextoAlpha"]))
doc.build(conteudo)
print(OUTPUT)
