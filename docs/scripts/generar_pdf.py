"""Genera el PDF de un .md de docs/ y lo deja al lado, con el mismo nombre.

El .md es la única fuente: se edita el .md y se vuelve a generar el PDF. El título del PDF es el primer
"# " del .md y el pie de página es lo que va después de "Agente de cobranza NSF: ".

Uso (en un contenedor con reportlab, con docs/ montado en /docs):
    python scripts/generar_pdf.py para_el_jefe/pendientes_externos.md
    python scripts/generar_pdf.py para_el_jefe/*.md            # varios a la vez
"""

import sys
from pathlib import Path

from reportlab.lib import colors
from reportlab.lib.pagesizes import letter
from reportlab.lib.units import cm
from reportlab.platypus import SimpleDocTemplate

from pdf_desde_md import H2, parse

H2.keepWithNext = True  # que un título no quede solo al final de una página
PREFIX = "Agente de cobranza NSF: "


def build(source: Path) -> Path:
    text = source.read_text(encoding="utf-8")
    title = next((line[2:].strip() for line in text.splitlines() if line.startswith("# ")), source.stem)
    section = title[len(PREFIX):] if title.startswith(PREFIX) else title
    section = section[:1].upper() + section[1:]

    def footer(canvas, doc):
        canvas.saveState()
        canvas.setFont("Helvetica", 7.5)
        canvas.setFillColor(colors.HexColor("#667085"))
        canvas.drawString(1.7 * cm, 1.1 * cm, f"Agente de cobranza NSF  |  {section}")
        canvas.drawRightString(letter[0] - 1.7 * cm, 1.1 * cm, f"Página {doc.page}")
        canvas.restoreState()

    out = source.with_suffix(".pdf")
    doc = SimpleDocTemplate(str(out), pagesize=letter, leftMargin=1.7 * cm, rightMargin=1.7 * cm,
                            topMargin=1.6 * cm, bottomMargin=1.8 * cm, title=title, author="Agente de cobranza NSF")
    doc.build(parse(text), onFirstPage=footer, onLaterPages=footer)
    return out


if __name__ == "__main__":
    if len(sys.argv) < 2:
        sys.exit(__doc__)
    for arg in sys.argv[1:]:
        print("ok", build(Path(arg)))
