from pathlib import Path

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import cm
from reportlab.platypus import Image, Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle


ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "output" / "pdf" / "guia-inscricao-portal-arena-alpha.pdf"
OUTPUT.parent.mkdir(parents=True, exist_ok=True)

styles = getSampleStyleSheet()
styles.add(ParagraphStyle(name="Titulo", parent=styles["Title"], fontName="Helvetica-Bold", fontSize=24, leading=29, textColor=colors.HexColor("#e69b22")))
styles.add(ParagraphStyle(name="Subtitulo", parent=styles["Heading2"], fontName="Helvetica-Bold", fontSize=15, leading=19, textColor=colors.HexColor("#e69b22"), spaceBefore=16, spaceAfter=7))
styles.add(ParagraphStyle(name="Texto", parent=styles["BodyText"], fontName="Helvetica", fontSize=11, leading=16, textColor=colors.HexColor("#202124")))

documento = SimpleDocTemplate(str(OUTPUT), pagesize=A4, rightMargin=2 * cm, leftMargin=2 * cm, topMargin=1.7 * cm, bottomMargin=1.7 * cm)
conteudo = []
logo = ROOT / "static" / "arena-alpha-logo.jpeg"
if logo.exists():
    cabecalho = Table([[Image(str(logo), width=3.2 * cm, height=3.2 * cm), Paragraph("<b>ARENA ALPHA</b><br/>Guia do Portal do Aluno", styles["Titulo"])]], colWidths=[4 * cm, 12 * cm])
    cabecalho.setStyle(TableStyle([("VALIGN", (0, 0), (-1, -1), "MIDDLE"), ("LINEBELOW", (0, 0), (-1, -1), 1, colors.HexColor("#e69b22")), ("BOTTOMPADDING", (0, 0), (-1, -1), 10)]))
    conteudo.append(cabecalho)
conteudo.append(Spacer(1, 14))
conteudo.append(Paragraph("Sua matrícula já foi confirmada. Agora use o Portal do Aluno para acompanhar suas informações na Arena Alpha.", styles["Texto"]))

conteudo.append(Paragraph("Como entrar no Portal do Aluno", styles["Subtitulo"]))
conteudo.append(Paragraph('Link direto: <a href="https://arena-alpha-portal.onrender.com/portal" color="#a96f10"><u>https://arena-alpha-portal.onrender.com/portal</u></a>', styles["Texto"]))
conteudo.append(Spacer(1, 6))
passos = [
    "Abra o site da Arena Alpha: <b>arena-alpha-portal.onrender.com</b>.",
    "Toque em <b>Portal do aluno</b> no menu superior.",
    "Digite somente o <b>CPF informado no seu cadastro</b>.",
    "Toque em <b>Entrar</b>. Não é necessário criar senha.",
]
for passo in passos:
    conteudo.append(Paragraph("• " + passo, styles["Texto"]))

conteudo.append(Paragraph("O que você encontra no portal", styles["Subtitulo"]))
for item in ["Suas aulas e próximas datas.", "Situação da mensalidade e vencimento.", "Solicitação de reserva de horários e eventos."]:
    conteudo.append(Paragraph("• " + item, styles["Texto"]))

conteudo.append(Spacer(1, 18))
aviso = Table([[Paragraph("<b>Importante:</b> use sempre o mesmo CPF cadastrado na sua inscrição. Caso não consiga entrar, fale com a Arena Alpha pelo WhatsApp.", styles["Texto"])]], colWidths=[16.5 * cm])
aviso.setStyle(TableStyle([("BACKGROUND", (0, 0), (-1, -1), colors.HexColor("#fff3dc")), ("BOX", (0, 0), (-1, -1), 1, colors.HexColor("#e69b22")), ("LEFTPADDING", (0, 0), (-1, -1), 10), ("RIGHTPADDING", (0, 0), (-1, -1), 10), ("TOPPADDING", (0, 0), (-1, -1), 10), ("BOTTOMPADDING", (0, 0), (-1, -1), 10)]))
conteudo.append(aviso)
conteudo.append(Spacer(1, 20))
conteudo.append(Paragraph("Arena Alpha - Vôlei de Areia e Futvôlei", styles["Texto"]))
documento.build(conteudo)
print(OUTPUT)
