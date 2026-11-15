"""Genera el PDF de lo que falta y no depende del desarrollo, a partir de pendientes_externos.md.

Usa el mismo formato que generar_respuestas_observaciones.py. El .md es la única fuente.

Uso (dentro de un contenedor con reportlab instalado, desde docs/):
    python generar_pendientes_externos.py pendientes_externos.md
El PDF queda en /tmp; copiarlo a docs/.
"""

import sys

from reportlab.lib import colors
from reportlab.lib.pagesizes import letter
from reportlab.lib.units import cm
from reportlab.platypus import SimpleDocTemplate

from generar_respuestas_observaciones import H2, parse

H2.keepWithNext = True  # que un título no quede solo al final de una página

OUT = "/tmp/Pendientes_Externos_Agente_Cobranza_NSF.pdf"


def footer(canvas, doc):
    canvas.saveState()
    canvas.setFont("Helvetica", 7.5)
    canvas.setFillColor(colors.HexColor("#667085"))
    canvas.drawString(1.7 * cm, 1.1 * cm, "Agente de cobranza NSF  |  Lo que falta y no depende del desarrollo")
    canvas.drawRightString(letter[0] - 1.7 * cm, 1.1 * cm, f"Página {doc.page}")
    canvas.restoreState()


if __name__ == "__main__":
    source = sys.argv[1] if len(sys.argv) > 1 else "pendientes_externos.md"
    with open(source, encoding="utf-8") as f:
        story = parse(f.read())
    doc = SimpleDocTemplate(OUT, pagesize=letter, leftMargin=1.7 * cm, rightMargin=1.7 * cm, topMargin=1.6 * cm,
                            bottomMargin=1.8 * cm, title="Agente de cobranza NSF: lo que falta",
                            author="Agente de cobranza NSF")
    doc.build(story, onFirstPage=footer, onLaterPages=footer)
    print("ok", OUT)
