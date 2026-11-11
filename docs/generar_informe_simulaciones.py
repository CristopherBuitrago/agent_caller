"""Genera el informe PDF de las 7 simulaciones del agente de cobranza NSF.

Uso (dentro del contenedor del backend, con reportlab instalado): python generar_informe_simulaciones.py
El PDF queda en /tmp; copiarlo a docs/.
"""

from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER
from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import cm
from reportlab.platypus import (KeepTogether, PageBreak, Paragraph, SimpleDocTemplate, Spacer, Table,
                                TableStyle)

OUT = "/tmp/Informe_Simulaciones_Agente_Cobranza_NSF.pdf"
AZUL = colors.HexColor("#1F3A5F")
GRIS = colors.HexColor("#F2F4F7")
BORDE = colors.HexColor("#C9D1DC")
CRIT = {
    "Crítico": colors.HexColor("#B42318"),
    "Alto": colors.HexColor("#C4320A"),
    "Medio": colors.HexColor("#B54708"),
    "Bajo": colors.HexColor("#027A48"),
}

ss = getSampleStyleSheet()
H1 = ParagraphStyle("H1", parent=ss["Heading1"], fontName="Helvetica-Bold", fontSize=16, textColor=AZUL,
                    spaceBefore=6, spaceAfter=8)
H2 = ParagraphStyle("H2", parent=ss["Heading2"], fontName="Helvetica-Bold", fontSize=12.5, textColor=AZUL,
                    spaceBefore=10, spaceAfter=5)
H3 = ParagraphStyle("H3", parent=ss["Heading3"], fontName="Helvetica-Bold", fontSize=10.5, spaceBefore=7,
                    spaceAfter=3)
BODY = ParagraphStyle("B", parent=ss["Normal"], fontName="Helvetica", fontSize=9.5, leading=13, spaceAfter=4)
BUL = ParagraphStyle("BUL", parent=BODY, leftIndent=12, bulletIndent=2, spaceAfter=2)
CELL = ParagraphStyle("C", parent=BODY, fontSize=8.3, leading=10.4, spaceAfter=0)
CELLB = ParagraphStyle("CB", parent=CELL, fontName="Helvetica-Bold")
HEAD = ParagraphStyle("HD", parent=CELL, fontName="Helvetica-Bold", textColor=colors.white)
TITLE = ParagraphStyle("T", parent=H1, fontSize=22, leading=27, alignment=TA_CENTER, spaceAfter=10)
SUB = ParagraphStyle("S", parent=BODY, fontSize=11, alignment=TA_CENTER, textColor=colors.HexColor("#475467"))
NOTE = ParagraphStyle("N", parent=BODY, fontSize=8.8, leading=12, textColor=colors.HexColor("#475467"))


def p(text, style=BODY):
    return Paragraph(text, style)


def bullets(items):
    return [Paragraph(t, BUL, bulletText="•") for t in items]


def table(header, rows, widths, crit_col=None):
    data = [[p(h, HEAD) for h in header]]
    for r in rows:
        row = []
        for i, c in enumerate(r):
            if i == crit_col and c in CRIT:
                row.append(p(f"<b>{c}</b>", ParagraphStyle("k", parent=CELL, textColor=CRIT[c])))
            else:
                row.append(p(str(c), CELLB if i == 0 else CELL))
        data.append(row)
    t = Table(data, colWidths=widths, repeatRows=1)
    style = [
        ("BACKGROUND", (0, 0), (-1, 0), AZUL),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("GRID", (0, 0), (-1, -1), 0.4, BORDE),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, GRIS]),
        ("LEFTPADDING", (0, 0), (-1, -1), 4), ("RIGHTPADDING", (0, 0), (-1, -1), 4),
        ("TOPPADDING", (0, 0), (-1, -1), 3), ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
    ]
    t.setStyle(TableStyle(style))
    return t


W = letter[0] - 3.6 * cm


def footer(canvas, doc):
    canvas.saveState()
    canvas.setFont("Helvetica", 7.5)
    canvas.setFillColor(colors.HexColor("#667085"))
    canvas.drawString(1.8 * cm, 1.1 * cm, "Agente de voz de cobranza NSF  |  Informe de simulaciones  |  2026-11-11")
    canvas.drawRightString(letter[0] - 1.8 * cm, 1.1 * cm, f"Página {doc.page}")
    canvas.restoreState()


S = []

# --- portada --------------------------------------------------------------------------
S += [Spacer(1, 4.5 * cm), p("Agente de voz de cobranza NSF", TITLE),
      p("Informe de las 7 pruebas simuladas del agente", SUB), Spacer(1, 0.3 * cm),
      p("Resultados, comportamiento del deudor, brechas, errores y observaciones,<br/>"
        "y criticidad del modelo Claude Haiku 5.5 frente a Claude Sonnet 5.5", SUB),
      Spacer(1, 1.2 * cm), p("11 de noviembre de 2026", SUB), Spacer(1, 3 * cm)]
S.append(table(["Dato", "Detalle"], [
    ["Repositorio", "github.com/CristopherBuitrago/agent_caller (rama main)"],
    ["Detalle de cada prueba", "docs/notas_simulacion_2026-11-11.md y docs/simulacion_2 a 7_*.md"],
    ["Datos usados", "Base PostgreSQL con datos simulados. Deudora de prueba: Jane Carter (TEST-001), "
                     "cuenta ACC-T001 con Lakeside Auto Finance, saldo USD 485 (pago devuelto de USD 450 "
                     "+ cargo de USD 35 del 2026-10-10)"],
    ["Estado del backend", "228 pruebas automáticas pasan"],
], [4 * cm, W - 4 * cm]))
S.append(PageBreak())

# --- 1. cómo se hicieron ----------------------------------------------------------------
S.append(p("1. Cómo se hicieron las pruebas", H1))
S.append(p("No hay <b>ANTHROPIC_API_KEY</b>, así que el agente no pudo probarse con el modelo de "
           "producción (Claude Haiku 5.5). En su lugar:"))
S += bullets([
    "<b>Claude Opus 5.5</b> (el asistente de desarrollo) hizo de agente: siguió el prompt real del agente "
    "(<i>agent_system_prompt.md</i>) y llamó las <b>mismas 11 herramientas</b> del backend contra la base "
    "PostgreSQL de prueba, a través de un simulador.",
    "<b>El desarrollador</b> hizo de deudor (o de la persona que contesta), escribiendo en inglés.",
    "Cada respuesta del backend es real: reglas de negocio, validaciones y lo que queda guardado en la base. "
    "Al terminar cada prueba se revisó la base con una consulta y luego se limpiaron los datos de prueba.",
])
S.append(p("<b>Límite importante:</b> Opus es el modelo más grande de la familia y razona más antes de "
           "responder. Estas pruebas validan el <b>diseño</b> (prompt, herramientas y reglas del backend), "
           "<b>no</b> el comportamiento de Haiku. La sección 4 explica dónde Haiku podría comportarse distinto.",
           NOTE))
S.append(p("Cómo se clasifican las observaciones", H3))
S.append(table(["Etiqueta", "Quién lo resuelve"], [
    ["Prompt", "Cambio en las instrucciones del agente"],
    ["Backend", "Cambio en el código o en las herramientas"],
    ["Negocio", "Lo decide el jefe"],
    ["Legal", "Lo debe revisar un abogado"],
    ["Error", "Falla del código encontrada en la prueba"],
], [3 * cm, W - 3 * cm]))

# --- 2. resumen ---------------------------------------------------------------------------
S.append(p("2. Resumen de las 7 pruebas", H1))
S.append(table(["#", "Escenario", "Llamada", "Cómo terminó", "Guardado en la base", "Obs."], [
    ["1", "Negociación con pago parcial y pedido de descuento", "Saliente",
     "Acuerdo: USD 90 hoy y USD 395 el 2026-12-11", "Cuenta en PTP, acuerdo partial, arrangement_made", "16"],
    ["2", "La deudora llama tras un SMS de pago rebotado", "Entrante",
     "Pago total agendado para mañana y transferencia a una persona", "Cuenta en PTP, acuerdo full, transferred_to_human", "14"],
    ["3", "Contesta el esposo de la deudora", "Saliente",
     "No se reveló la deuda; se cerró para volver a llamar", "callback_requested, sin verificación", "7"],
    ["4", "Disputa: \"ya pagué, fue error del banco\"", "Saliente",
     "Cuenta marcada en disputa, sin pedir pago", "is_disputed = true, outcome dispute", "8"],
    ["5", "Hardship Questions completas", "Entrante",
     "Sin acuerdo: la deudora consulta con su esposo", "Respuestas de Hardship guardadas, callback_requested", "14"],
    ["6", "Verificación fallida dos veces", "Saliente",
     "Cierre sin revelar la deuda", "verification_failed, 2 intentos", "7"],
    ["7", "Deudora molesta que pide no ser llamada y amenaza", "Saliente",
     "Marca de \"no llamar\" guardada", "do_not_call = true, outcome do_not_call", "10"],
], [0.6 * cm, 4.1 * cm, 1.6 * cm, 4.4 * cm, 4.3 * cm, 0.9 * cm]))
S.append(Spacer(1, 6))
S.append(p("Resultado general", H3))
S += bullets([
    "<b>El backend aplicó sus reglas en las 7 pruebas:</b> ningún descuento quedó guardado, ninguna fecha "
    "fuera de rango, nunca se habló de la deuda sin verificar identidad, y ninguna herramienta falló.",
    "<b>Unas 76 observaciones</b> en total, muchas repetidas entre pruebas.",
    "<b>2 problemas en el código</b> (sección 3): uno borra datos y otro puede hacer que se vuelva a llamar a "
    "quien pidió que no lo llamen.",
    "<b>Los huecos más grandes son de negocio:</b> cómo paga el deudor un pago a futuro, qué se le ofrece a "
    "quien no puede pagar ni 10 cuotas, y qué pasa después de una disputa o de \"no llamar\".",
])

# --- 3. errores ----------------------------------------------------------------------------
S.append(p("3. Errores encontrados en el código", H1))
S.append(table(["#", "Error", "Dónde y por qué", "Consecuencia", "Corrección propuesta", "Criticidad"], [
    ["E1", "Al colgar, el pedido de \"no llamar\" o la disputa se pueden perder (prueba 7)",
     "agent_conversation.py, hang_up(): le dice al modelo \"Call end_call\", y end_call no acepta do_not_call "
     "ni dispute. Si el modelo no responde, el respaldo es callback_requested",
     "Se vuelve a llamar a quien pidió que no lo llamen: riesgo legal de acoso",
     "Cambiar el aviso de cuelgue para que use mark_do_not_call o record_dispute cuando corresponda, y una "
     "prueba con un modelo guionado que cuelga justo después del pedido", "Crítico"],
    ["E2", "Guardar las Hardship Questions en dos pasos borra las respuestas anteriores (prueba 5)",
     "postgres_hardship_repository.py: ON CONFLICT ... SET campo = EXCLUDED.campo pisa todos los campos, "
     "incluso con vacíos. La documentación dice que se puede repetir para completarlas",
     "Si el agente guarda de a una respuesta, se pierden las anteriores sin que nadie lo note",
     "Usar COALESCE para no pisar con vacíos, y una prueba que guarde en dos pasos", "Alto"],
], [0.7 * cm, 3.1 * cm, 3.9 * cm, 2.9 * cm, 3.5 * cm, 1.8 * cm], crit_col=5))

# --- detalle por prueba -------------------------------------------------------------------
PRUEBAS = [
    dict(
        titulo="Prueba 1: negociación con pago parcial y pedido de descuento",
        doc="docs/notas_simulacion_2026-11-11.md",
        hizo="Llamada saliente a Jane Carter (al principio se abrió una entrante por error y se cerró). "
             "Verificación con un fallo y luego correcta; aviso legal; ofertas en orden; pagos parciales "
             "propuestos por la deudora; cierre con acuerdo.",
        deudor=[
            "Preguntó quién llamaba antes de aceptar la grabación y dijo no saber por qué la llamaban.",
            "Se equivocó en el SSN (1324) en el primer intento.",
            "Dijo que intentó pagar ese día y no sabe qué pasó; pidió pagar solo los USD 450 y preguntó por "
            "qué le cobran USD 35.",
            "Contó que tiene USD 300 para todo el mes; ofreció USD 90; pidió 4 cuotas; volvió a los USD 90 "
            "con el resto el mes siguiente.",
            "Pidió un descuento sobre \"los 370 que quedan\" (el resto real era USD 395).",
            "Aceptó con duda: \"I'll give it a try\".",
        ],
        resultado="Acuerdo parcial: USD 90 el 2026-11-11 y USD 395 el 2026-12-11. Cuenta en PTP, llamada "
                  "arrangement_made con 2 intentos de verificación.",
        obs=[
            ["Negocio", "Pedido del jefe (J1): verificar sin nombre completo, leyendo SSN y fecha para que el "
             "deudor diga sí o no. Revela datos personales a quien conteste, no verifica nada y no es posible "
             "con el diseño actual (datos guardados como hash). Propuesta: quitar el nombre, pero que el deudor "
             "siga diciendo los datos"],
            ["Legal", "Pedido del desarrollador (D1): quitar \"This communication is from a debt collector\". "
             "La frase no se había dicho antes en la llamada; lo debe confirmar el abogado"],
            ["Prompt", "Presentarse como asistente virtual desde el saludo"],
            ["Prompt", "Frase fija para \"¿por qué me llaman?\" antes de verificar"],
            ["Prompt", "Saludo saliente: preguntar por el deudor y pedir la grabación en una sola frase"],
            ["Prompt", "Turno demasiado largo tras verificar: aviso + deuda + oferta"],
            ["Prompt", "Cómo explicar el cargo de USD 35 sin inventar quién lo cobra"],
            ["Prompt", "Límite entre disputa y confusión (\"I tried to pay, I'm not sure what happened\")"],
            ["Negocio", "Un parcial propuesto por el deudor deja un resto imposible (USD 395 en un pago para "
             "alguien con USD 300 al mes). ¿Cuotas primero? ¿El resto puede ir en cuotas?"],
            ["Backend", "Tras rechazar un parcial, el next_step manda pedir la siguiente oferta aunque el "
             "deudor ya dio otro monto"],
            ["Negocio", "Recorrer 2 y 3 cuotas una por una aunque el deudor ya dijo su límite (4 cuotas)"],
            ["Backend", "Un parcial rechazado no se puede aceptar después; se arma otro igual"],
            ["Prompt", "Repetir montos y fechas y esperar un \"sí\" limpio antes de crear el acuerdo"],
            ["Prompt", "\"Sí, pero con descuento\" no es un sí; corregir cifras equivocadas del deudor"],
            ["Negocio", "Aceptación tibia de un acuerdo con riesgo alto de incumplirse"],
            ["Negocio", "\"You will receive the payment instructions\": ese envío no existe hoy"],
        ],
    ),
    dict(
        titulo="Prueba 2: llamada entrante tras un SMS de pago rebotado",
        doc="docs/simulacion_2_entrante_2026-11-11.md",
        hizo="La deudora llama porque vio un mensaje de texto. Grabación, verificación al primer intento, "
             "aviso legal y deuda, pago total agendado para el día siguiente y transferencia a una persona "
             "para saber cómo pagar.",
        deudor=[
            "Antes de aceptar la grabación preguntó por qué rebotó el pago.",
            "Recordó el pago (\"I had forgotten\") y pidió pagar mañana, cuando le pagan, y que la llamaran.",
            "Preguntó cómo funcionaría, si dejarían de llamarla y si le enviarían un link de pago.",
            "Insistió: \"¿alguien me va a llamar y me va a cobrar en la llamada?\"",
            "Aceptó el pago para mañana y pidió que la transfirieran.",
        ],
        resultado="Pago total de USD 485 para el 2026-11-12. Cuenta en PTP, llamada transferred_to_human.",
        obs=[
            ["Negocio", "Cómo paga el deudor un pago agendado (link por SMS, correo, débito, volver a llamar). "
             "Fue lo que más fricción causó"],
            ["Negocio", "Qué se le promete al deudor después de PTP: recordatorios, medio, qué pasa si no paga"],
            ["Backend", "get_account_details no devuelve el motivo del rebote (nsf_return_code R01)"],
            ["Backend", "callback_requested no guarda fecha ni hora para volver a llamar"],
            ["Backend", "El resultado transferred_to_human esconde que sí hubo acuerdo"],
            ["Backend", "El motivo de transfer_to_human no se guarda para quien recibe la llamada"],
            ["Backend", "No hay herramienta para enviar link de pago o confirmación"],
            ["Prompt", "Volver a pedir la grabación si el deudor la ignora; frase \"To protect your privacy\""],
            ["Prompt", "Aviso y deuda en un turno y oferta en el siguiente; ajustar el next_step"],
            ["Prompt", "Si el deudor pide que lo llamen pero puede fijar fecha en 8 días, agendar el pago"],
            ["Prompt", "Regla sobre medios de pago no definidos para no inventar (\"no se le cobrará nada\", "
             "\"le enviaremos un link\")"],
            ["Prompt", "Si una pregunta se repite sin respuesta, ofrecer una persona"],
            ["Prompt", "next_step de record_offer_response cuando el deudor pide transferencia"],
            ["Legal", "Devoluciones de llamada y recordatorios cuentan para el límite de 7 en 7 días"],
        ],
    ),
    dict(
        titulo="Prueba 3: contesta el esposo de la deudora",
        doc="docs/simulacion_3_tercero_contesta_2026-11-11.md",
        hizo="Llamada saliente a Jane Carter; contesta su esposo. El agente no revela nada de la deuda y cierra "
             "para volver a llamar.",
        deudor=[
            "El esposo preguntó quién llamaba y cómo podía ayudar.",
            "Ofreció ayudar \"con lo que necesite\" y dijo que Jane vuelve hacia las 6 p. m.",
        ],
        resultado="Llamada callback_requested, sin consentimiento ni verificación. No se reveló monto, acreedor "
                  "ni motivo.",
        obs=[
            ["Negocio", "Pedido del desarrollador (D2): el saludo solo pregunta por Jane y el aviso de "
             "grabación va después de verificar. Propuesta: aviso cuando la persona confirma que es Jane, antes "
             "de verificar, y no grabar hasta su \"sí\""],
            ["Legal", "El nombre de la empresa (\"Recovery Services\") delata la cobranza ante un tercero"],
            ["Legal", "No grabar hasta que la deudora acepte (Florida exige consentimiento de todas las partes)"],
            ["Prompt", "Frases fijas para terceros: \"a personal business matter\" y \"I'm only able to speak "
             "with her directly\"; nunca dejar recados"],
            ["Backend", "Se pierde la hora que dio el tercero (6 p. m.)"],
            ["Backend", "Falta un resultado para \"contestó un tercero, la deudora no estaba\""],
            ["Backend", "Qué hacer con la transcripción y el resumen de una llamada sin consentimiento"],
        ],
    ),
    dict(
        titulo="Prueba 4: disputa, \"ya pagué, fue error del banco\"",
        doc="docs/simulacion_4_disputa_2026-11-11.md",
        hizo="Llamada saliente con el saludo del pedido D2. Grabación, verificación, aviso legal y deuda; la "
             "deudora disputa y la llamada se cierra sin pedir pago.",
        deudor=[
            "Confirmó ser Jane y preguntó quién llamaba y para qué.",
            "Al escuchar la deuda dijo: \"I already paid that; it was the bank's fault, not mine.\"",
        ],
        resultado="Cuenta marcada en disputa (is_disputed = true), estado NSF sin cambios, llamada dispute, "
                  "sin acuerdos.",
        obs=[
            ["Backend", "La disputa se guarda sin detalles: fecha del pago, medio, número de confirmación"],
            ["Prompt", "Preguntar esos detalles antes de record_dispute, que cierra la llamada al instante"],
            ["Negocio", "Quién revisa la disputa, en cuánto tiempo y cómo se informa el resultado"],
            ["Negocio", "¿Se puede consultar si el pago entró, para confirmarlo en la llamada?"],
            ["Prompt", "Qué respuestas cuentan como aceptación de la grabación"],
            ["Backend", "Acción para empezar a grabar después del \"sí\" (flujo D2)"],
            ["Legal", "Plazos y formato de la verificación de una deuda disputada; disputa verbal o escrita"],
            ["Legal", "Qué nombre de empresa se dice al identificarse y en qué momento"],
        ],
    ),
    dict(
        titulo="Prueba 5: Hardship Questions completas",
        doc="docs/simulacion_5_hardship_2026-11-11.md",
        hizo="Llamada entrante. La deudora rechaza el pago total, 2 y 3 cuotas; el sistema exige las Hardship "
             "Questions; se hacen las 5 preguntas; se ofrecen 4 cuotas y la deudora queda en consultar.",
        deudor=[
            "Llamó para decir que no puede pagar y necesita tiempo.",
            "Perdió el trabajo el mes pasado; busca por LinkedIn y en persona; dijo estar desesperada.",
            "Su esposo ayuda un poco, pero trabaja medio tiempo.",
            "Ofreció USD 30 a fin de mes y luego USD 30 al mes desde fin de mes.",
            "Ante 4 cuotas de USD 121,25 dijo que necesita hablar primero con su esposo.",
        ],
        resultado="Sin acuerdo. Respuestas de Hardship guardadas (monto ofrecido USD 30, ayuda en el hogar, "
                  "duración vacía a propósito). Llamada callback_requested.",
        obs=[
            ["Error", "Guardar las Hardship Questions en dos pasos borra las respuestas anteriores (E2)"],
            ["Backend", "Las Hardship y las ofertas rechazadas no valen para la próxima llamada: se repite todo"],
            ["Backend", "propose_offer debe devolver la fecha límite del primer pago (hoy + 8 días)"],
            ["Backend", "recommended_plan no está en la herramienta; debería llenarlo el sistema"],
            ["Backend", "callback_requested sin fecha, motivo ni monto mencionado"],
            ["Negocio", "Si lo que ofrece el deudor no alcanza ni para 10 cuotas (USD 48,50 al mes), ¿saltar, "
             "permitir planes más largos o recorrer las 10 ofertas?"],
            ["Negocio", "¿La primera cuota se ofrece hoy o en la próxima fecha de pago del deudor?"],
            ["Negocio", "¿Ofrecer pago total, 2 y 3 cuotas aunque el deudor ya dijo que no puede?"],
            ["Negocio", "Protocolo para deudores vulnerables (\"I'm desperate\")"],
            ["Negocio", "Seguimiento cuando la llamada termina sin acuerdo"],
            ["Prompt", "duration_type vacío si la respuesta no es clara; adaptar la pregunta 4 a lo ya dicho"],
            ["Prompt", "Cuotas \"iguales\" con centavos distintos: cómo decirlas en voz"],
            ["Prompt", "Permitir la oferta en el mismo turno que la deuda si el deudor ya planteó su situación"],
            ["Legal", "Obligaciones con deudores en situación vulnerable"],
        ],
    ),
    dict(
        titulo="Prueba 6: verificación fallida dos veces",
        doc="docs/simulacion_6_verificacion_fallida_2026-11-11.md",
        hizo="Llamada saliente. Quien contesta dice ser Jane, acepta la grabación y falla la verificación dos "
             "veces; la llamada se cierra sin revelar la deuda.",
        deudor=[
            "Primer intento: SSN con dos dígitos invertidos (1243 en vez de 1234).",
            "Segundo intento: SSN correcto, fecha de nacimiento un día corrida (March 15).",
        ],
        resultado="Llamada verification_failed con 2 intentos; grabación aceptada; identidad sin verificar.",
        obs=[
            ["Backend", "verify_identity no dice cuántos intentos quedan (attempts_left)"],
            ["Prompt", "Tras un fallo, \"please double-check the numbers\" en vez de solo \"repeat\""],
            ["Negocio", "Qué se le ofrece a la verdadera deudora que no logra verificarse: número de contacto, "
             "persona o nueva llamada"],
            ["Prompt", "Cierre con número de contacto, según lo que decida el jefe"],
            ["Backend", "Un impostor puede bloquear a la verdadera deudora 24 horas (5 fallos entre llamadas)"],
            ["Backend", "Resumen con IA de llamadas sin verificar: que no mencione la deuda"],
            ["Legal", "Las llamadas fallidas cuentan para el límite de 7 en 7 días"],
        ],
    ),
    dict(
        titulo="Prueba 7: deudora molesta que pide no ser llamada",
        doc="docs/simulacion_7_deudor_molesto_2026-11-11.md",
        hizo="Llamada saliente. La deudora contesta molesta, se queja de las llamadas con insultos, pide que no "
             "la llamen, amenaza y cuelga. Se marca \"no llamar\" sin verificar (supuesto vigente en salientes).",
        deudor=[
            "Se quejó de que la llaman todo el tiempo, con insultos.",
            "Pidió que no la volvieran a llamar, amenazó con violencia y colgó.",
        ],
        resultado="Deudora marcada do_not_call (todas sus cuentas); llamada do_not_call; cuenta NSF sin cambios.",
        obs=[
            ["Error", "Al colgar, el pedido de \"no llamar\" o la disputa se pueden perder (E1)"],
            ["Legal", "Volver a llamar a quien pidió no ser llamado"],
            ["Negocio", "Protocolo para amenazas de violencia y dónde se registran"],
            ["Negocio", "¿Se ofrece \"no llamar\" u otro medio de contacto cuando el deudor se queja?"],
            ["Negocio", "Después de \"no llamar\", ¿la cobranza sigue por otro medio?"],
            ["Prompt", "Cómo tratar insultos sin discutir; cuándo ofrecer una persona o cerrar"],
            ["Prompt", "Distinguir la queja (\"they keep calling me\") del pedido (\"don't call me again\")"],
            ["Backend", "Cómo se resume una llamada con amenazas e insultos"],
            ["Prompt", "next_step de mark_do_not_call cuando el deudor ya colgó"],
            ["Legal", "Contar las llamadas por deudor (7 en 7 días) antes de llamar"],
        ],
    ),
]

for pr in PRUEBAS:
    S.append(PageBreak())
    S.append(p(pr["titulo"], H1))
    S.append(p(f"Detalle completo: <i>{pr['doc']}</i>", NOTE))
    S.append(p("Qué se hizo", H3))
    S.append(p(pr["hizo"]))
    S.append(p("Cómo actuó el deudor", H3))
    S += bullets(pr["deudor"])
    S.append(p("Resultado", H3))
    S.append(p(pr["resultado"]))
    S.append(p("Brechas, errores y observaciones", H3))
    S.append(table(["Tipo", "Observación"], pr["obs"], [2 * cm, W - 2 * cm]))

# --- 4. Haiku vs Sonnet -------------------------------------------------------------------
S.append(PageBreak())
S.append(p("4. Criticidad de Claude Haiku 5.5 frente a Claude Sonnet 5.5", H1))
S.append(p("Configuración actual", H2))
S += bullets([
    "<b>Claude Haiku 5.5 conversa</b> en todas las llamadas, con <b>esfuerzo bajo</b> (effort: low): razona "
    "poco antes de responder para que la voz sea rápida.",
    "<b>Claude Sonnet 5.5 es solo respaldo:</b> responde un turno únicamente si Haiku falla o rechaza. "
    "<b>No</b> se usa para los turnos difíciles; esos los resuelve Haiku.",
    "Ninguno de los dos se ha probado todavía: falta la ANTHROPIC_API_KEY.",
])
S.append(p("Por qué importa", H2))
S.append(p("En las 7 pruebas, el agente (Opus) tuvo que razonar en momentos ambiguos que el prompt no cubre: "
           "un \"sí\" con condiciones, una queja que parece un pedido, una pregunta sin respuesta que invita a "
           "inventar. Un modelo pequeño con poco razonamiento tiende a seguir la instrucción más literal (el "
           "next_step de la herramienta o la última frase del deudor). El backend protege los montos, las fechas "
           "y la verificación, pero <b>no protege lo que el agente dice ni qué herramienta elige</b> en estos "
           "momentos."))
S.append(p("<b>Todo lo que sigue es una hipótesis</b>, basada en lo que se vio en las pruebas y en cómo "
           "suelen comportarse los modelos pequeños con poco razonamiento. Se confirma o descarta probando con "
           "la API.", NOTE))
S.append(p("Momentos de riesgo encontrados en las pruebas", H2))
S.append(table(["Momento (prueba)", "Qué podría hacer Haiku con esfuerzo bajo", "¿Lo protege el backend?",
                "Mitigación", "Criticidad"], [
    ["Deudor cuelga justo después de pedir \"no llamar\" o disputar (7)",
     "Seguir el aviso de cuelgue y cerrar con end_call como callback_requested",
     "No (error E1)", "Corregir el aviso de cuelgue y probarlo", "Crítico"],
    ["Contesta un tercero (3)",
     "Ser amable de más: \"it's about her payment\", aceptar ayuda o dejar recado",
     "Parcial: sin verificación no puede consultar la cuenta, pero sí puede hablar",
     "Frases fijas para terceros; casos de prueba", "Crítico"],
    ["Medio de pago no definido (2)",
     "Inventar: \"we'll text you a link\" o \"nothing will be charged\"",
     "No", "Decidir el medio de pago; regla en el prompt", "Alto"],
    ["\"Sí, pero con descuento\" (1)",
     "Registrar la aceptación; el deudor cuelga creyendo que pidió un descuento",
     "Parcial: el acuerdo se guarda sin descuento, pero el deudor queda mal informado",
     "Regla: un sí con condiciones no cuenta", "Alto"],
    ["Disputa o confusión (1 y 4)",
     "Marcar disputa ante \"I'm not sure what happened\", o ignorar una disputa real",
     "No", "Definir el límite en el prompt; casos de prueba", "Alto"],
    ["Queja o pedido de \"no llamar\" (7)",
     "Marcar \"no llamar\" ante una simple queja, o no marcarlo ante un pedido",
     "No", "Definir el límite en el prompt; casos de prueba", "Alto"],
    ["Guardar las Hardship de a una (5)",
     "Guardar después de cada respuesta, que es lo natural",
     "No (error E2: borra las anteriores)", "Corregir el repositorio", "Alto"],
    ["Cifras equivocadas del deudor (1)",
     "No corregir \"los 370 que quedan\" (eran USD 395)", "No", "Regla en el prompt", "Medio"],
    ["Aceptación tibia de un acuerdo difícil (1)",
     "Aceptar \"I'll give it a try\" sin más", "No", "Decisión de negocio y regla en el prompt", "Medio"],
    ["Clasificar respuestas de Hardship (5)",
     "Forzar temporary o long_term cuando la respuesta no es clara", "No",
     "Dejar vacío y usar notes", "Medio"],
    ["Motivo del rebote (2)",
     "Inventar el motivo (\"insufficient funds\") sin dato", "No", "Devolver el motivo en la herramienta", "Medio"],
    ["Montos con centavos y turnos largos (1 y 5)",
     "Leer cifras exactas largas; turnos que no caben en voz", "No aplica", "Frases habladas en la herramienta", "Bajo"],
    ["Avanzar sin consentimiento de grabación (1 y 2)",
     "Seguir la conversación sin el \"sí\"", "Sí: sin consentimiento, las herramientas devuelven error",
     "Regla en el prompt", "Bajo"],
], [3.2 * cm, 4 * cm, 3.2 * cm, 3.2 * cm, 1.8 * cm], crit_col=4))

S.append(p("Opciones y costo aproximado", H2))
S.append(p("Con 800 llamadas diarias. Los precios por millón de tokens son: Haiku 5.5, USD 0,10 de entrada y "
           "USD 0,50 de salida; Sonnet 5.5, USD 2 y USD 10 (unas 20 veces más). El costo de conversar con Haiku "
           "se estimó en unos USD 132 al mes; el resto del costo mensual (telefonía, voz, servidores) es de unos "
           "USD 3.650 y no cambia con el modelo."))
S.append(table(["Opción", "Cómo funciona", "Costo de la conversación (USD/mes)", "Ventajas", "Riesgos"], [
    ["A. Haiku con esfuerzo bajo (actual)", "Todo lo responde Haiku; Sonnet solo si Haiku falla",
     "~132", "Lo más barato y rápido", "Los momentos de la tabla anterior dependen solo del prompt"],
    ["B. Haiku con esfuerzo medio", "Haiku razona más en cada turno", "Algo más que A (más tokens de salida)",
     "Mejor juicio sin cambiar de modelo", "Más demora por turno: hay que medirla en voz"],
    ["C. Haiku y Sonnet en los momentos difíciles", "Sonnet responde solo en turnos marcados: negociación, "
     "disputa, terceros", "Entre A y D según cuántos turnos pasen a Sonnet",
     "Juicio de Sonnet donde importa", "Más complejo; Sonnet tarda más; cambiar de modelo pierde la caché"],
    ["D. Sonnet en todo", "Sonnet conversa siempre", "~2.640 (unas 20 veces A)",
     "El mejor juicio", "Unos USD 2.500 más al mes y más demora en voz"],
], [3 * cm, 3.6 * cm, 3 * cm, 3 * cm, 2.8 * cm]))
S.append(Spacer(1, 6))
S.append(p("Recomendación", H2))
S += bullets([
    "<b>Primero corregir los errores E1 y E2 y reforzar el prompt</b> con las reglas de las 7 pruebas. Esto "
    "reduce el riesgo con cualquier modelo y no cuesta más por llamada.",
    "<b>Con la API key, armar un set de unos 20 casos difíciles</b> sacados de estas pruebas (sí con condiciones, "
    "tercero que contesta, cuelgue tras \"no llamar\", disputa o confusión, medio de pago) y correrlo con Haiku. "
    "Con Haiku cuesta menos de USD 1; con Sonnet, unos pocos dólares.",
    "<b>Decidir con datos:</b> si Haiku con esfuerzo bajo falla en esos casos, probar primero la opción B y "
    "luego la C, antes de pensar en D.",
    "Medir también la demora por turno: en una llamada de voz, una respuesta lenta también es un error.",
])

S.append(p("5. Siguientes pasos", H1))
S += bullets([
    "Corregir los errores E1 y E2, cada uno con su prueba automática.",
    "Aplicar las observaciones de Prompt y Backend en el orden de las pruebas (1 a 7).",
    "Llevar al jefe las preguntas de Negocio, sin repetidas y ordenadas por importancia.",
    "Llevar las observaciones Legales a un abogado antes del piloto.",
    "Con la ANTHROPIC_API_KEY: probar Haiku y Sonnet con los casos difíciles de este informe.",
])

doc = SimpleDocTemplate(OUT, pagesize=letter, leftMargin=1.8 * cm, rightMargin=1.8 * cm, topMargin=1.7 * cm,
                        bottomMargin=1.8 * cm, title="Informe de simulaciones del agente de cobranza NSF",
                        author="Agente de cobranza NSF", subject="Pruebas simuladas 2026-11-11")
doc.build(S, onFirstPage=footer, onLaterPages=footer)
print("ok", OUT)
