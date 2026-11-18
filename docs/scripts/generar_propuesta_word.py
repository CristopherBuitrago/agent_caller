"""Genera la propuesta en Word (.docx), editable, con el mismo contenido de generar_propuesta.py.

Uso (contenedor con reportlab, pypdfium2, pillow y python-docx, desde docs/):
    python scripts/generar_propuesta_word.py es   ->  propuesta/propuesta_es.docx
    python scripts/generar_propuesta_word.py en   ->  propuesta/proposal_en.docx

El diagrama de flujo va como imagen (se dibuja con el mismo código del PDF).
"""

import re
import sys

from docx import Document
from docx.enum.table import WD_TABLE_ALIGNMENT
from docx.enum.text import WD_BREAK
from docx.oxml import OxmlElement
from docx.oxml.ns import qn
from docx.shared import Cm, Pt, RGBColor

from generar_propuesta import TEXT, W, Flow

AZUL = RGBColor(0x1F, 0x3A, 0x5F)
GRIS_TXT = RGBColor(0x34, 0x40, 0x54)
SUAVE = RGBColor(0x66, 0x70, 0x85)


def flow_png(t, path):
    """Dibuja el diagrama en un PDF de una página y lo pasa a PNG."""
    import pypdfium2 as pdfium
    from reportlab.pdfgen import canvas
    flow = Flow(t)
    pad = 6
    c = canvas.Canvas("/tmp/flow.pdf", pagesize=(flow.width + 2 * pad, flow.height + 2 * pad))
    flow.canv = c
    c.translate(pad, pad)
    flow.draw()
    c.save()
    pdfium.PdfDocument("/tmp/flow.pdf")[0].render(scale=3).to_pil().save(path)


def shade(cell, hex_color):
    tc_pr = cell._tc.get_or_add_tcPr()
    shd = OxmlElement("w:shd")
    shd.set(qn("w:val"), "clear")
    shd.set(qn("w:color"), "auto")
    shd.set(qn("w:fill"), hex_color)
    tc_pr.append(shd)


def add_rich(par, html, size=10, color=GRIS_TXT, bold=False):
    """Texto con <b>...</b>; quita las demás marcas de reportlab."""
    html = html.replace("<br/>", " ").replace("&amp;", "&")
    for i, piece in enumerate(re.split(r"</?b>", html)):
        if not piece:
            continue
        run = par.add_run(piece)
        run.bold = bold or i % 2 == 1
        run.font.size = Pt(size)
        run.font.color.rgb = color
    return par


def heading(doc, text):
    p = doc.add_paragraph()
    p.paragraph_format.space_before = Pt(14)
    p.paragraph_format.space_after = Pt(6)
    p.paragraph_format.keep_with_next = True
    r = p.add_run(text)
    r.bold, r.font.size, r.font.color.rgb = True, Pt(15), AZUL


def body(doc, html, size=10, color=GRIS_TXT, style=None):
    p = doc.add_paragraph(style=style)
    p.paragraph_format.space_after = Pt(4)
    return add_rich(p, html, size, color)


def table(doc, head, rows, widths_cm, highlight_last=False):
    t = doc.add_table(rows=1, cols=len(head))
    t.style = "Table Grid"
    t.alignment = WD_TABLE_ALIGNMENT.CENTER
    t.autofit = False
    for i, h in enumerate(head):
        cell = t.rows[0].cells[i]
        cell.text = ""
        add_rich(cell.paragraphs[0], h, 9, RGBColor(0xFF, 0xFF, 0xFF), bold=True)
        shade(cell, "1F3A5F")
    for n, row in enumerate(rows):
        cells = t.add_row().cells
        for i, v in enumerate(row):
            cells[i].text = ""
            add_rich(cells[i].paragraphs[0], str(v), 9, RGBColor(0, 0, 0), bold=(i == 0))
            if highlight_last and n == len(rows) - 1:
                shade(cells[i], "E8EEF7")
            elif n % 2 == 1:
                shade(cells[i], "F2F4F7")
    fix_widths(t, widths_cm)
    doc.add_paragraph().paragraph_format.space_after = Pt(2)
    return t


def fix_widths(t, widths_cm):
    """Anchos fijos en la tabla (tblGrid y tblLayout) y en cada celda: Word y LibreOffice los respetan."""
    tbl_pr = t._tbl.tblPr
    layout = OxmlElement("w:tblLayout")
    layout.set(qn("w:type"), "fixed")
    tbl_pr.append(layout)
    for i, col in enumerate(t._tbl.tblGrid.findall(qn("w:gridCol"))):
        col.set(qn("w:w"), str(int(Cm(widths_cm[i]).twips)))
    for row in t.rows:
        for i, w in enumerate(widths_cm):
            row.cells[i].width = Cm(w)


def page_break(doc):
    doc.add_paragraph().add_run().add_break(WD_BREAK.PAGE)


def build(lang):
    t = TEXT[lang]
    out = t["out"].replace(".pdf", ".docx")
    doc = Document()
    sec = doc.sections[0]
    sec.page_width, sec.page_height = Cm(21.59), Cm(27.94)          # carta
    sec.left_margin = sec.right_margin = Cm(1.8)
    sec.top_margin, sec.bottom_margin = Cm(1.6), Cm(1.8)
    normal = doc.styles["Normal"]
    normal.font.name, normal.font.size = "Arial", Pt(10)
    normal.element.rPr.rFonts.set(qn("w:eastAsia"), "Arial")
    full = 21.59 - 3.6

    p = doc.add_paragraph()
    r = p.add_run(t["title"])
    r.bold, r.font.size, r.font.color.rgb = True, Pt(20), AZUL
    body(doc, t["subtitle"], 11, SUAVE)

    heading(doc, t["s1"])
    for par in t["s1_body"]:
        body(doc, par)
    box = doc.add_table(rows=1, cols=1)
    box.style = "Table Grid"
    cell = box.rows[0].cells[0]
    shade(cell, "E8EEF7")
    cell.text = ""
    add_rich(cell.paragraphs[0], f"<b>{t['status_title']}</b>", 9.5)
    for item in t["status"]:
        add_rich(cell.add_paragraph(), "• " + item, 9.5)
    fix_widths(box, [full])

    heading(doc, t["s2"])
    table(doc, t["goals_head"], [(a, b) for a, b in t["goals"]], [4.6, full - 4.6])
    body(doc, t["kpi"], 9, SUAVE)

    page_break(doc)
    heading(doc, t["s3"])
    png = f"/tmp/flow_{lang}.png"
    flow_png(t, png)
    doc.add_picture(png, width=Cm(full))
    body(doc, t["flow_note"], 9, SUAVE)

    page_break(doc)
    heading(doc, t["s4"])
    table(doc, t["systems_head"], t["systems"], [4.6, full - 4.6])

    heading(doc, t["s5"])
    body(doc, f"<b>{t['have_title']}</b>")
    table(doc, t["have_head"], t["have"], [4.2, 4.4, full - 8.6])
    body(doc, f"<b>{t['buy_title']}</b>")
    table(doc, t["buy_head"], t["buy"] + [tuple(f"<b>{v}</b>" for v in t["total"])],
          [6.8, full - 9.4, 2.6], highlight_last=True)
    for note in t["cost_notes"]:
        body(doc, note, 9.5, style="List Bullet")

    page_break(doc)
    heading(doc, t["s6"])
    body(doc, t["s6_intro"])
    table(doc, t["inv_head"], t["inv"], [3.6, full - 7.4, 3.8])
    for note in t["inv_notes"]:
        body(doc, note, 9.5, style="List Bullet")

    heading(doc, t["s7"])
    body(doc, t["s7_intro"])
    for item in t["s7_items"]:
        body(doc, item, 9.5, style="List Bullet")

    doc.core_properties.title = t["title"]
    doc.save(out)
    print("ok", out)


if __name__ == "__main__":
    build(sys.argv[1] if len(sys.argv) > 1 else "es")
