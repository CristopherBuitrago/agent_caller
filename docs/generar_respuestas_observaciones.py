"""Genera el PDF de las respuestas a las observaciones a partir de respuestas_observaciones.md.

El .md es la única fuente: se edita el .md y se vuelve a generar el PDF.

Uso (dentro del contenedor del backend, con reportlab instalado):
    python generar_respuestas_observaciones.py respuestas_observaciones.md
El PDF queda en /tmp; copiarlo a docs/.
"""

import html
import re
import sys

from reportlab.lib import colors
from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import cm
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

OUT = "/tmp/Respuestas_Observaciones_Agente_Cobranza_NSF.pdf"
AZUL = colors.HexColor("#1F3A5F")
GRIS = colors.HexColor("#F2F4F7")
BORDE = colors.HexColor("#C9D1DC")
# Color de la primera palabra de la columna "Estado".
ESTADO = [
    ("Aplicada", "#027A48"),
    ("Decidida", "#175CD3"),
    ("Por confirmar", "#B54708"),
    ("En pausa", "#667085"),
    ("Pendiente", "#B42318"),
]

ss = getSampleStyleSheet()
H1 = ParagraphStyle("H1", parent=ss["Heading1"], fontName="Helvetica-Bold", fontSize=17, textColor=AZUL,
                    spaceAfter=6)
H2 = ParagraphStyle("H2", parent=ss["Heading2"], fontName="Helvetica-Bold", fontSize=12.5, textColor=AZUL,
                    spaceBefore=12, spaceAfter=6)
BODY = ParagraphStyle("B", parent=ss["Normal"], fontName="Helvetica", fontSize=9.2, leading=12.5, spaceAfter=4,
                      textColor=colors.HexColor("#344054"))
BUL = ParagraphStyle("BUL", parent=BODY, leftIndent=12, bulletIndent=2, spaceAfter=2)
CELL = ParagraphStyle("C", parent=BODY, fontSize=8.2, leading=10.4, spaceAfter=0, textColor=colors.black)
CELLB = ParagraphStyle("CB", parent=CELL, fontName="Helvetica-Bold")
HEAD = ParagraphStyle("HD", parent=CELL, fontName="Helvetica-Bold", textColor=colors.white)
W = letter[0] - 3.4 * cm


def inline(text: str) -> str:
    """Markdown en línea -> marcas de reportlab: **negrita**, `código` e *itálica*."""
    text = html.escape(text, quote=False)
    text = re.sub(r"\*\*(.+?)\*\*", r"<b>\1</b>", text)
    text = re.sub(r"`(.+?)`", r'<font face="Courier">\1</font>', text)
    text = re.sub(r"(?<![\w*])\*(?!\s)(.+?)(?<!\s)\*(?![\w*])", r"<i>\1</i>", text)
    return text


def status_cell(text: str) -> Paragraph:
    for label, color in ESTADO:
        for prefix in (f"**{label}**", label):
            if text.startswith(prefix):
                return Paragraph(f'<font color="{color}"><b>{label}</b></font>{inline(text[len(prefix):])}', CELL)
    return Paragraph(inline(text), CELL)


def widths_for(header: list[str]) -> list[float]:
    if header[0] == "#":
        if len(header) == 4:
            return [1.0 * cm, 3.8 * cm, W - 8.2 * cm, 3.4 * cm]
        return [1.0 * cm, W - 4.4 * cm, 3.4 * cm]
    if len(header) == 3:
        return [3.8 * cm, W - 7.2 * cm, 3.4 * cm]
    return [W / len(header)] * len(header)


def table(rows: list[list[str]]) -> Table:
    header, body = rows[0], rows[1:]
    status_col = header.index("Estado") if "Estado" in header else None
    data = [[Paragraph(inline(h), HEAD) for h in header]]
    for row in body:
        data.append([status_cell(c) if i == status_col else Paragraph(inline(c), CELLB if i == 0 else CELL)
                     for i, c in enumerate(row)])
    t = Table(data, colWidths=widths_for(header), repeatRows=1)
    t.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), AZUL),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("GRID", (0, 0), (-1, -1), 0.4, BORDE),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, GRIS]),
        ("LEFTPADDING", (0, 0), (-1, -1), 4), ("RIGHTPADDING", (0, 0), (-1, -1), 4),
        ("TOPPADDING", (0, 0), (-1, -1), 3), ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
    ]))
    return t


def parse(markdown: str) -> list:
    story, rows = [], []
    for line in markdown.splitlines() + [""]:
        line = line.rstrip()
        if line.startswith("|"):
            cells = [c.strip() for c in line.strip("|").split("|")]
            if not all(re.fullmatch(r":?-{3,}:?", c) for c in cells):
                rows.append(cells)
            continue
        if rows:
            story += [table(rows), Spacer(1, 4)]
            rows = []
        if line.startswith("# "):
            story.append(Paragraph(inline(line[2:]), H1))
        elif line.startswith("## "):
            story.append(Paragraph(inline(line[3:]), H2))
        elif line.startswith("- "):
            story.append(Paragraph(inline(line[2:]), BUL, bulletText="•"))
        elif line:
            story.append(Paragraph(inline(line), BODY))
    return story


def footer(canvas, doc):
    canvas.saveState()
    canvas.setFont("Helvetica", 7.5)
    canvas.setFillColor(colors.HexColor("#667085"))
    canvas.drawString(1.7 * cm, 1.1 * cm, "Agente de cobranza NSF  |  Respuestas a las observaciones")
    canvas.drawRightString(letter[0] - 1.7 * cm, 1.1 * cm, f"Página {doc.page}")
    canvas.restoreState()


if __name__ == "__main__":
    source = sys.argv[1] if len(sys.argv) > 1 else "respuestas_observaciones.md"
    with open(source, encoding="utf-8") as f:
        story = parse(f.read())
    doc = SimpleDocTemplate(OUT, pagesize=letter, leftMargin=1.7 * cm, rightMargin=1.7 * cm, topMargin=1.6 * cm,
                            bottomMargin=1.8 * cm, title="Respuestas a las observaciones del agente de cobranza NSF",
                            author="Agente de cobranza NSF")
    doc.build(story, onFirstPage=footer, onLaterPages=footer)
    print("ok", OUT)
