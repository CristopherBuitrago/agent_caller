"""Genera el PDF con las respuestas a las observaciones (mismo contenido que respuestas_observaciones.md).

Uso (dentro del contenedor del backend, con reportlab instalado): python generar_respuestas_observaciones.py
El PDF queda en /tmp; copiarlo a docs/.
"""

from reportlab.lib import colors
from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import cm
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

OUT = "/tmp/Respuestas_Observaciones_Agente_Cobranza_NSF.pdf"
AZUL = colors.HexColor("#1F3A5F")
GRIS = colors.HexColor("#F2F4F7")
BORDE = colors.HexColor("#C9D1DC")
ESTADO = {
    "Aplicada": colors.HexColor("#027A48"),
    "Por confirmar": colors.HexColor("#B54708"),
    "Pendiente": colors.HexColor("#B42318"),
}

ss = getSampleStyleSheet()
H1 = ParagraphStyle("H1", parent=ss["Heading1"], fontName="Helvetica-Bold", fontSize=17, textColor=AZUL,
                    spaceAfter=6)
H2 = ParagraphStyle("H2", parent=ss["Heading2"], fontName="Helvetica-Bold", fontSize=12.5, textColor=AZUL,
                    spaceBefore=12, spaceAfter=6)
BODY = ParagraphStyle("B", parent=ss["Normal"], fontName="Helvetica", fontSize=9.5, leading=13, spaceAfter=4)
NOTE = ParagraphStyle("N", parent=BODY, fontSize=8.8, leading=12, textColor=colors.HexColor("#475467"))
BUL = ParagraphStyle("BUL", parent=BODY, leftIndent=12, bulletIndent=2, spaceAfter=2)
CELL = ParagraphStyle("C", parent=BODY, fontSize=8.4, leading=10.6, spaceAfter=0)
CELLB = ParagraphStyle("CB", parent=CELL, fontName="Helvetica-Bold")
HEAD = ParagraphStyle("HD", parent=CELL, fontName="Helvetica-Bold", textColor=colors.white)
W = letter[0] - 3.4 * cm


def p(text, style=BODY):
    return Paragraph(text, style)


def estado(text):
    """Colorea la etiqueta inicial del estado (Aplicada, Por confirmar, Pendiente)."""
    for label, color in ESTADO.items():
        if text.startswith(label):
            hex_color = color.hexval()[2:]
            return p(f'<font color="#{hex_color}"><b>{label}</b></font>{text[len(label):]}', CELL)
    return p(text, CELL)


def table(header, rows, widths, status_col=None):
    data = [[p(h, HEAD) for h in header]]
    for row in rows:
        data.append([estado(c) if i == status_col else p(c, CELLB if i == 0 else CELL)
                     for i, c in enumerate(row)])
    t = Table(data, colWidths=widths, repeatRows=1)
    t.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), AZUL),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("GRID", (0, 0), (-1, -1), 0.4, BORDE),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, GRIS]),
        ("LEFTPADDING", (0, 0), (-1, -1), 4), ("RIGHTPADDING", (0, 0), (-1, -1), 4),
        ("TOPPADDING", (0, 0), (-1, -1), 3), ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
    ]))
    return t


def footer(canvas, doc):
    canvas.saveState()
    canvas.setFont("Helvetica", 7.5)
    canvas.setFillColor(colors.HexColor("#667085"))
    canvas.drawString(1.7 * cm, 1.1 * cm, "Agente de cobranza NSF  |  Respuestas a las observaciones  |  2026-11-12")
    canvas.drawRightString(letter[0] - 1.7 * cm, 1.1 * cm, f"Página {doc.page}")
    canvas.restoreState()


OBS_WIDTHS = [1.0 * cm, 4.2 * cm, W - 8.6 * cm, 3.4 * cm]
OBS_HEADER = ["#", "Observación", "Respuesta", "Estado"]

S = [
    p("Agente de cobranza NSF: respuestas a las observaciones", H1),
    p("Actualizado: 12 de noviembre de 2026. Referencia: informe de simulaciones (códigos N, B, P y L) y la "
      "simulación 8 (S1 y S2).", NOTE),
    p("<b>Estado:</b> <b>Aplicada</b> = construida y probada · <b>Por confirmar</b> = aplicada o decidida, pero "
      "falta validarla · <b>Pendiente</b> = falta decidir.", NOTE),

    p("Errores y seguridad", H2),
    table(OBS_HEADER, [
        ["E1", "Si el deudor pide \"no llamar\" o disputa y cuelga, el pedido se podía perder",
         "Al colgar, el agente guarda primero el \"no llamar\" o la disputa y después cierra la llamada",
         "Aplicada"],
        ["E2", "Guardar las Hardship Questions de a una borraba las respuestas anteriores",
         "Cada respuesta se agrega sin borrar las anteriores", "Aplicada"],
        ["S1", "Quien llamó dijo \"Paul Carter\", falló, y luego dijo \"Jane Carter\" y pasó (verificación por "
               "tanteo)",
         "Si quien llama cambia de nombre entre intentos, la llamada se cierra (resultado identity_mismatch) sin "
         "revisar sus datos, y se le pide llamar de nuevo con sus propios datos", "Aplicada"],
        ["S2", "Se pedía deletrear el apellido aunque fallara el nombre y antes de revisar el SSN y la fecha",
         "Solo se pide deletrear si el SSN, la fecha y el nombre coinciden y lo único que no coincide es el "
         "apellido. Cualquier otro fallo cuenta como intento fallido, sin decir qué dato falló", "Aplicada"],
    ], OBS_WIDTHS, status_col=3),

    p("Negocio", H2),
    table(OBS_HEADER, [
        ["N1", "No había forma de que el deudor pagara un pago agendado",
         "Al cerrar el acuerdo se envía un SMS de confirmación; el día de cada cuota, otro SMS con el link de "
         "pago. Se envían aunque el deudor esté marcado \"no llamar\" (aceptó el acuerdo)",
         "Aplicada con proveedor de prueba. Por confirmar: qué proveedor de SMS usa la empresa (empieza por "
         "\"V\") y si hay página de pago del procesador"],
        ["N2", "Verificar leyendo el SSN y la fecha para que el deudor diga sí o no",
         "Se deja como está: el deudor dice su nombre completo, los últimos 4 del SSN y su fecha de nacimiento. "
         "Leerle los datos los revela a quien conteste y no se puede con el diseño actual (los datos están "
         "cifrados). Si se prefiere la otra forma, se hace", "Por confirmar"],
        ["N3", "Saludo y aviso de grabación en las salientes",
         "El saludo solo pregunta por el deudor (\"May I speak with Jane Carter?\"). Cuando confirma que es él, "
         "el agente se identifica y avisa de la grabación, y con su \"sí\" verifica. La grabación empieza con ese "
         "\"sí\": a un familiar que conteste no se le dice ni se le graba nada", "Aplicada"],
        ["N4", "Se ofrecían opciones que el deudor ya había descartado",
         "Si el deudor dice cuánto puede pagar, se saltan las ofertas mayores, pero nunca la de 3 cuotas (antes "
         "de las Hardship Questions) ni la última. Esas se presentan como \"la opción más baja disponible "
         "ahora\", sin mencionar mínimos ni reglas", "Aplicada"],
        ["N5", "Lo que podía pagar el deudor no alcanzaba ni para 10 cuotas",
         "Después de las Hardship Questions, la última oferta es un primer pago del 10% y el resto en 12 cuotas "
         "mensuales iguales (1 año). Con USD 485: 48,50 hoy y 12 cuotas de unos 36,40", "Aplicada"],
        ["N6", "Un parcial dejaba un resto imposible (USD 395 en un solo pago)",
         "Si el deudor dice cuánto puede pagar al mes, el resto se reparte en cuotas mensuales iguales (dentro "
         "del año). Con más de 3 pagos se hacen antes las Hardship Questions. El parcial de último recurso (5% a "
         "10%) lo sigue ofreciendo el agente antes de transferir", "Aplicada"],
        ["N7", "Se aceptó un acuerdo con duda (\"I'll give it a try\")",
         "Ante una aceptación con duda, el agente pregunta cuánto puede pagar cómodo al mes y vuelve a ofrecer "
         "con ese monto; solo cierra si el deudor dice que puede cumplir",
         "Decidida; va en el ajuste de instrucciones del agente"],
        ["N8", "El primer pago siempre caía hoy, aunque el deudor pidiera tiempo",
         "Siempre se intenta hoy. Si pide tiempo, el primer pago puede ir hasta fin de mes. Si faltan menos de 8 "
         "días, primero se ofrece fin de este mes y, si no puede, fin del mes siguiente. Reemplaza el límite de "
         "8 días", "Aplicada. Por confirmar el cambio de 8 días a fin de mes"],
        ["N9", "Nadie volvía a llamar si la llamada terminaba sin acuerdo",
         "La lista diaria de salientes: el deudor vuelve a ella cuando la ley lo permite (7 días después de una "
         "conversación). Si pidió que lo llamen un día y una hora, se le llama entonces (falta guardar esa hora)",
         "Aplicada en parte"],
        ["N10", "Qué pasa después de que el deudor acepta el acuerdo",
         "SMS solo de aviso 3 días antes de cada cuota y el link de pago el día de la cuota. Los cobradores ya no "
         "hacen recordatorios",
         "Aviso aplicado. Por confirmar: si a los 5 días sin pago el acuerdo se marca roto y se avisa al equipo "
         "por Teams (u otro canal) sin cambiar el estado de la cuenta"],
        ["N11", "Nadie revisaba las disputas",
         "Al registrarse una disputa: la cuenta pasa a estado de disputa, sale una alerta al equipo y un cobrador "
         "decide si es válida o no. El agente busca en la base el pago que dice el deudor (\"One moment while I "
         "check that for you\"). Si no lo encuentra, no acusa a nadie: pide más datos y registra la disputa igual",
         "Decidida, sin construir. Por confirmar: qué estado se le pone a la cuenta, qué se hace con el resultado "
         "y si se puede consultar en la base si un pago entró"],
        ["N12", "Quien no lograba verificarse se quedaba sin salida",
         "El agente le da un número para devolver la llamada: la línea de entrada que atiende el mismo agente",
         "Aplicada. Por confirmar: la opción y el número"],
        ["N13", "\"No llamar\" y quejas por las llamadas",
         "Ante una queja: (A) disculparse y ofrecer otro horario o SMS; (B) solo disculparse; o (C) ofrecer \"no "
         "llamar\". Después de \"no llamar\": (A) solo se dejan las llamadas (la deuda sigue por SMS o cartas de "
         "la empresa) o (B) se detiene toda la cobranza hasta que la revise una persona", "Pendiente de decidir"],
        ["N14", "Deudores vulnerables y amenazas: no había protocolo ni dónde registrarlas",
         "Ante angustia fuerte (llanto, \"estoy desesperado\"): (A) pausar la cobranza y pasar a una persona, o "
         "(B) seguir con empatía y ofrecer una persona. Si menciona hacerse daño: siempre pasar a una persona y dar "
         "la línea de crisis 988. Ante una amenaza de violencia: (A) cerrar con calma, registrarla (resultado nuevo "
         "threat), alertar a un supervisor y no volver a llamar hasta que una persona lo revise, o (B) solo dejarla "
         "en el resumen. Recomendada: A en ambos casos", "Pendiente de decidir"],
        ["N15", "Proveedor de telefonía y programa de los cobradores",
         "Si el proveedor de SMS de la empresa (\"empieza por V\") también da llamadas de voz con audio en vivo, se "
         "usa ese en vez de Telnyx (ya tiene contrato y números). Preguntas: ¿cuál es el proveedor? ¿Las llamadas "
         "de los cobradores van por el mismo? ¿Qué programa usan para recibir llamadas (marcador o CRM)? De eso "
         "depende cómo se transfiere la llamada y cómo le llega el motivo al cobrador", "Pendiente de información"],
    ], OBS_WIDTHS, status_col=3),

    p("Otras decisiones", H2),
    table(["Tema", "Respuesta", "Estado"], [
        ["Organización del sistema", "Tres partes separadas en el mismo proyecto: reglas de cobranza, agente de "
         "voz y mensajería por SMS", "Aplicada"],
        ["Lista diaria de salientes", "Cada día se consulta la base y se arma la lista de cuentas a llamar: NSF, "
         "sin disputa, sin \"no llamar\", sin acuerdo activo y con teléfono. Respeta el límite de 7 llamadas en 7 "
         "días y no llama durante 7 días después de una conversación. Si el deudor llama antes y verifica su "
         "identidad, sale de la lista", "Aplicada"],
        ["Llamadas entrantes", "Las entrantes de deudores en NSF pasarían directo al agente; las de otros estados, "
         "a una persona", "Por confirmar"],
    ], [4.2 * cm, W - 7.6 * cm, 3.4 * cm], status_col=2),

    p("Para revisar antes del piloto", H2),
    p("<b>Con el jefe.</b> Temas técnicos o de las instrucciones del agente que cambian lo que ve el equipo o cómo se trata a las personas."),
    table(["#", "Tema", "Propuesta", "Estado"], [
        ['B12', 'Resumen con IA de llamadas delicadas', 'Hoy se genera resumen aunque solo haya hablado un tercero o alguien no verificado, y en llamadas con amenazas o insultos. Propuesta: si no hubo verificación, el resumen solo dice quién contestó y cómo terminó, sin mencionar la deuda; con amenazas o insultos, el resumen lo dice en una línea sin repetir las palabras', 'Pendiente'],
        ['B13', 'Un impostor puede bloquear a la verdadera deudora', 'Con 5 fallos de verificación en 24 horas, entre varias llamadas, la cuenta se bloquea y pasa a una persona. Un impostor puede provocarlo a propósito y la deudora real no podría resolver con el agente ese día. Propuesta: mantener el bloqueo y enviar una alerta al equipo cuando ocurra, para que una persona contacte a la deudora', 'Pendiente'],
        ['P3', 'Qué se le dice a un tercero que contesta', 'Propuesta de frases fijas: "I\'m calling about a personal business matter" y "I\'m only able to speak with her directly". El agente nunca deja recados, no dice el nombre de la empresa si delata la cobranza (ver L3) y no acepta que el tercero pague o ayude', 'Pendiente'],
        ['P7', 'Quejas, insultos y "no llamar"', '"Me llaman todo el tiempo" es una queja; "no me llamen más" es un pedido de "no llamar". Propuesta ante insultos: mantener la calma sin comentarlos y, si siguen, ofrecer una persona o cerrar la llamada con amabilidad. Depende de N13', 'Pendiente'],
    ], OBS_WIDTHS, status_col=3),
    p("<b>Con el abogado en EE. UU. (por medio del jefe).</b> Nadie los ha revisado todavía. Conviene resolverlos antes de llamar a deudores reales, porque algunos cambian cómo se diseña la llamada."),
    table(["#", "Tema", "Qué hay que revisar", "Estado"], [
        ['L1', 'Volver a llamar a quien pidió no ser llamado', 'El error E1 ya está corregido: el pedido se guarda aunque el deudor cuelgue. Falta confirmar qué exige la ley cuando el deudor lo pide (por qué medio se puede seguir contactando, si vale el pedido por teléfono). Prioritario', 'Pendiente'],
        ['L2', 'Consentimiento de grabación', 'Florida y otros estados exigen el consentimiento de todas las partes. Ya se aplicó que la grabación empiece con el "sí" del deudor (N3). Falta confirmar que eso basta, y si una llamada sin consentimiento puede tener transcripción y resumen con IA', 'Pendiente'],
        ['L3', 'Qué se le dice a un tercero', 'El nombre de la empresa ("Recovery Services") delata la cobranza. Definir qué nombre se dice, a quién y en qué momento', 'Pendiente'],
        ['L4', 'Límite de 7 llamadas en 7 días (Reg F)', 'La lista diaria ya respeta el límite y espera 7 días después de una conversación. Falta confirmar qué cuenta: devoluciones de llamada, llamadas fallidas, SMS, y las llamadas del agente sumadas a las de los cobradores', 'Pendiente'],
        ['L5', 'Disputas', 'Plazos y formato para verificar una deuda disputada, y si basta una disputa por teléfono (relacionado con N11)', 'Pendiente'],
        ['L6', 'Aviso "This communication is from a debt collector"', 'Se propuso quitarlo por repetido; la frase no se había dicho antes en la llamada. Confirmar el texto exacto del aviso legal', 'Pendiente'],
        ['L7', 'Deudores vulnerables y SMS', 'Obligaciones con deudores en situación vulnerable (relacionado con N14). Además: el consentimiento para enviar SMS de cobranza, la forma de darse de baja y el texto de los SMS (N1 y N10)', 'Pendiente'],
    ], OBS_WIDTHS, status_col=3),
    p("Siguen sin revisar", H2),
    Paragraph("<b>Técnicas:</b> 10 de backend (B1–B6, B8, B9, B14, B15).", BUL, bulletText="•"),
    Paragraph("<b>Instrucciones del agente:</b> P1, P2, P4–P6 y P8–P12, en un solo ajuste al final.", BUL, bulletText="•"),
]

doc = SimpleDocTemplate(OUT, pagesize=letter, leftMargin=1.7 * cm, rightMargin=1.7 * cm, topMargin=1.6 * cm,
                        bottomMargin=1.8 * cm, title="Respuestas a las observaciones del agente de cobranza NSF",
                        author="Agente de cobranza NSF")
doc.build(S, onFirstPage=footer, onLaterPages=footer)
print("ok", OUT)
