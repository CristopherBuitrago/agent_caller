"""Genera el informe PDF de las 7 simulaciones del agente de cobranza NSF.

Uso (dentro del contenedor del backend, con reportlab instalado): python generar_informe_simulaciones.py
El PDF queda en /tmp; copiarlo a docs/.
"""

from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER
from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import cm
from reportlab.platypus import PageBreak, Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

OUT = "/tmp/Informe_Simulaciones_Agente_Cobranza_NSF.pdf"
AZUL = colors.HexColor("#1F3A5F")
GRIS = colors.HexColor("#F2F4F7")
BORDE = colors.HexColor("#C9D1DC")
AVISO_FONDO = colors.HexColor("#FFF4E5")
AVISO_BORDE = colors.HexColor("#F79009")
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
BODY = ParagraphStyle("B", parent=ss["Normal"], fontName="Helvetica", fontSize=9.5, leading=13, spaceAfter=4)
BUL = ParagraphStyle("BUL", parent=BODY, leftIndent=12, bulletIndent=2, spaceAfter=2)
CELL = ParagraphStyle("C", parent=BODY, fontSize=8.3, leading=10.4, spaceAfter=0)
CELLB = ParagraphStyle("CB", parent=CELL, fontName="Helvetica-Bold")
HEAD = ParagraphStyle("HD", parent=CELL, fontName="Helvetica-Bold", textColor=colors.white)
TITLE = ParagraphStyle("T", parent=H1, fontSize=22, leading=27, alignment=TA_CENTER, spaceAfter=10)
SUB = ParagraphStyle("S", parent=BODY, fontSize=11, alignment=TA_CENTER, textColor=colors.HexColor("#475467"))
NOTE = ParagraphStyle("N", parent=BODY, fontSize=8.8, leading=12, textColor=colors.HexColor("#475467"))
AVISO = ParagraphStyle("AV", parent=BODY, fontSize=9.5, leading=13, spaceAfter=0)

W = letter[0] - 3.6 * cm


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
    t.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), AZUL),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("GRID", (0, 0), (-1, -1), 0.4, BORDE),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, GRIS]),
        ("LEFTPADDING", (0, 0), (-1, -1), 4), ("RIGHTPADDING", (0, 0), (-1, -1), 4),
        ("TOPPADDING", (0, 0), (-1, -1), 3), ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
    ]))
    return t


def aviso(text):
    t = Table([[p(text, AVISO)]], colWidths=[W])
    t.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, -1), AVISO_FONDO),
        ("BOX", (0, 0), (-1, -1), 1.2, AVISO_BORDE),
        ("LEFTPADDING", (0, 0), (-1, -1), 8), ("RIGHTPADDING", (0, 0), (-1, -1), 8),
        ("TOPPADDING", (0, 0), (-1, -1), 6), ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
    ]))
    return t


def obs_table(rows):
    """Filas: (id, tema, observación y propuesta, pruebas)."""
    return table(["#", "Tema", "Observación y propuesta", "Pruebas"], rows,
                 [0.9 * cm, 3.3 * cm, W - 6.0 * cm, 1.8 * cm])


def footer(canvas, doc):
    canvas.saveState()
    canvas.setFont("Helvetica", 7.5)
    canvas.setFillColor(colors.HexColor("#667085"))
    canvas.drawString(1.8 * cm, 1.1 * cm, "Agente de voz de cobranza NSF  |  Informe de simulaciones  |  2026-11-11")
    canvas.drawRightString(letter[0] - 1.8 * cm, 1.1 * cm, f"Página {doc.page}")
    canvas.restoreState()


S = []

# --- portada ------------------------------------------------------------------------------
S += [Spacer(1, 4.5 * cm), p("Agente de voz de cobranza NSF", TITLE),
      p("Informe de las pruebas simuladas del agente", SUB), Spacer(1, 0.3 * cm),
      p("Errores, observaciones consolidadas y riesgos del modelo Claude Haiku 5.5", SUB),
      Spacer(1, 1.2 * cm), p("11 de noviembre de 2026", SUB), Spacer(1, 3 * cm)]
S.append(table(["Dato", "Detalle"], [
    ["Repositorio", "github.com/CristopherBuitrago/agent_caller (rama main)"],
    ["Detalle de cada prueba", "docs/notas_simulacion_2026-11-11.md y docs/simulacion_2 a 7_*.md"],
    ["Datos usados", "Base PostgreSQL con datos simulados. Deudora de prueba: Jane Carter (TEST-001), "
                     "cuenta ACC-T001 con Lakeside Auto Finance, saldo USD 485"],
    ["Estado del backend", "228 pruebas automáticas pasan"],
], [4 * cm, W - 4 * cm]))
S.append(PageBreak())

# --- 1. cómo se hicieron ------------------------------------------------------------------
S.append(p("1. Cómo se hicieron las pruebas", H1))
S.append(p("No hay <b>ANTHROPIC_API_KEY</b>, así que el agente no pudo probarse con el modelo de producción "
           "(Claude Haiku 5.5). En su lugar, <b>Claude Opus 5.5</b> (el asistente de desarrollo) hizo de agente: "
           "siguió el prompt real del agente y llamó las <b>mismas 11 herramientas</b> del backend contra la base "
           "de prueba. El desarrollador hizo de deudor. Las reglas, las validaciones y lo guardado en la base son "
           "reales."))
S.append(p("Se simularon 7 llamadas, numeradas así en el resto del informe:"))
S.append(table(["#", "Escenario", "Llamada"], [
    ["1", "Negociación con pago parcial y pedido de descuento", "Saliente"],
    ["2", "La deudora llama tras un SMS de pago rebotado", "Entrante"],
    ["3", "Contesta el esposo de la deudora", "Saliente"],
    ["4", "Disputa: \"ya pagué, fue error del banco\"", "Saliente"],
    ["5", "Hardship Questions completas", "Entrante"],
    ["6", "Verificación fallida dos veces", "Saliente"],
    ["7", "Deudora molesta que pide no ser llamada y amenaza", "Saliente"],
], [0.8 * cm, W - 3.3 * cm, 2.5 * cm]))
S.append(Spacer(1, 6))
S.append(p("<b>Resultado general:</b> el backend aplicó sus reglas en las 7 llamadas (ningún descuento guardado, "
           "ninguna fecha fuera de rango, nunca se habló de la deuda sin verificar) y ninguna herramienta falló. "
           "Salieron <b>2 errores de código</b> y <b>48 observaciones distintas</b>, sin repetir (15 de negocio, 15 "
           "de backend, 11 del prompt y 7 legales), agrupadas por quién las resuelve."))
S.append(p("<b>Límite:</b> Opus es el modelo más grande y razona más antes de responder. Estas pruebas validan el "
           "diseño, no el comportamiento de Haiku (ver sección 6).", NOTE))

# --- 2. errores ---------------------------------------------------------------------------
S.append(p("2. Errores encontrados en el código", H1))
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

# --- 3. negocio ---------------------------------------------------------------------------
S.append(PageBreak())
S.append(p("3. Observaciones de negocio", H1))
S.append(p("Están ordenadas por impacto."))
S.append(obs_table([
    ["N1", "Medio de pago a futuro",
     "No hay forma definida de que el deudor pague un pago agendado: el único medio previsto es el IVR PCI "
     "durante la llamada (Función 6, bloqueada). El agente promete \"payment instructions\" que hoy no existen, y "
     "la deudora preguntó dos veces cómo pagaría. ¿Link por SMS, correo, débito, volver a llamar? La empresa ya "
     "tiene una campaña de SMS, así que podría usar ese proveedor", "1, 2"],
    ["N2", "Verificación de identidad",
     "Se pidió quitar el nombre completo y que el agente lea los últimos 4 del SSN y la fecha de nacimiento "
     "para que el deudor diga sí o no. Revela datos personales a quien conteste, no verifica nada (cualquiera dice "
     "\"sí\") y no es posible con el diseño actual (los datos se guardan como hash). Propuesta: quitar el nombre, "
     "pero que el deudor siga diciendo los dos datos", "1"],
    ["N3", "Saludo y aviso de grabación en salientes (pedido del desarrollador)",
     "Se pidió que el saludo solo pregunte por el deudor y que el aviso de grabación vaya después de verificar. "
     "Propuesta intermedia, ya probada en las llamadas 4, 6 y 7: aviso cuando la persona confirma ser el deudor, "
     "antes de verificar, y sin grabar hasta su \"sí\"", "3, 4, 6, 7"],
    ["N4", "Ofertas que el deudor ya descartó",
     "El sistema obliga a ofrecer pago total, 2 y 3 cuotas en orden, aunque el deudor ya dijo que no puede pagar o "
     "que su máximo son 4 cuotas. Alarga la llamada y suena a que el agente no escucha. ¿Se mantiene, se presentan "
     "varias opciones juntas o se saltan las que superan lo que el deudor dijo poder pagar?", "1, 5"],
    ["N5", "Cuando lo que puede pagar el deudor no alcanza",
     "Una deudora ofreció USD 30 al mes; el plan más largo permitido (10 cuotas, 1 año) es de USD 48,50 al mes. "
     "El sistema obliga a recorrer 7 ofertas más para llegar al mismo final. ¿Saltar a 10 cuotas o a una persona, "
     "permitir planes más largos con Hardship, o dejarlo como está?", "5"],
    ["N6", "Pago parcial con un resto imposible",
     "Un parcial de USD 90 deja USD 395 en un solo pago a 30 días, para alguien con USD 300 al mes. ¿Se ofrecen "
     "cuotas antes de aceptar el parcial que propone el deudor? ¿El resto puede ir en cuotas?", "1"],
    ["N7", "Acuerdos con riesgo alto de incumplirse",
     "\"I'll give it a try\" se tomó como aceptación de un acuerdo que la deudora dudaba poder cumplir. ¿El agente "
     "acepta igual o insiste en otra opción?", "1"],
    ["N8", "Fecha de la primera cuota",
     "Las ofertas llegan con la primera cuota hoy, aunque el deudor pida tiempo (puede ser hasta en 8 días). "
     "¿Hoy por defecto o la próxima fecha de pago del deudor?", "5"],
    ["N9", "Seguimiento sin acuerdo",
     "Si la llamada termina sin acuerdo (el deudor consulta con alguien, contestó un tercero, pidió que lo llamen), "
     "¿quién vuelve a llamar y cuándo? El trabajo del agente hoy termina solo en PTP", "2, 3, 5"],
    ["N10", "Qué pasa después de PTP",
     "¿El deudor recibe recordatorios, por qué medio, y qué pasa si no paga en la fecha? La deudora preguntó si "
     "la seguirían llamando", "2"],
    ["N11", "Revisión de disputas",
     "¿Quién revisa una disputa, en cuánto tiempo y cómo se le informa el resultado al deudor? ¿Se puede consultar "
     "si un pago entró, para confirmarlo en la misma llamada?", "4"],
    ["N12", "Deudor que no logra verificarse",
     "En una saliente, la verdadera deudora que falla la verificación se queda sin saber por qué la llamaron ni "
     "cómo resolverlo. ¿Se le da un número de contacto, una persona o una nueva llamada?", "6"],
    ["N13", "\"No llamar\" y quejas por las llamadas",
     "¿El agente ofrece \"no llamar\" u otro medio (SMS, horario) cuando el deudor se queja, o solo lo marca si lo "
     "pide? Después de \"no llamar\", ¿la cobranza sigue por otro medio? La deuda sigue existiendo", "7"],
    ["N14", "Deudores vulnerables y amenazas",
     "No hay protocolo para un deudor desesperado ni para amenazas de violencia, y no hay dónde registrarlas. "
     "¿Pasar a una persona, pausar la cobranza, avisar a un supervisor?", "5, 7"],
    ["N15", "Proveedor de telefonía y programa de los cobradores",
     "¿Qué proveedor usa la empresa para sus SMS? ¿Sirve para voz? ¿Qué programa usan los cobradores para recibir "
     "llamadas? De eso depende cómo se transfiere la llamada y cómo le llega el motivo al cobrador", "2"],
]))

# --- 4. backend ---------------------------------------------------------------------------
S.append(PageBreak())
S.append(p("4. Observaciones de backend: código y herramientas", H1))
S.append(obs_table([
    ["B1", "Continuidad entre llamadas",
     "Las Hardship Questions quedan atadas a la llamada y las ofertas rechazadas viven en memoria. Si el deudor "
     "vuelve a llamar, se repite todo. Propuesta: que las Hardship valgan por deudor un tiempo (p. ej. 30 días) y "
     "guardar las ofertas rechazadas en la base", "5"],
    ["B2", "Devoluciones de llamada",
     "callback_requested no guarda cuándo volver a llamar, el motivo ni el monto mencionado (p. ej. \"vuelve a "
     "las 6 p. m.\", \"pagaría USD 30 a fin de mes\")", "2, 3, 5"],
    ["B3", "Resultados de llamada",
     "Una llamada con acuerdo y transferencia queda solo como transferred_to_human y esconde el acuerdo. Falta un "
     "resultado para \"contestó un tercero, la deudora no estaba\"", "2, 3"],
    ["B4", "Motivo de la transferencia",
     "El motivo de transfer_to_human no se guarda: quien recibe la llamada no sabe por qué se la pasaron", "2"],
    ["B5", "Disputas sin detalles",
     "Solo se guarda is_disputed. Faltan fecha del pago que dice haber hecho, medio, número de confirmación y "
     "notas (tabla disputes, requiere aprobar el modelo de datos)", "4"],
    ["B6", "Motivo del rebote",
     "get_account_details no devuelve el motivo aunque la base tiene nsf_return_code (R01 = fondos insuficientes). "
     "Devolverlo en palabras sencillas", "2"],
    ["B7", "Fecha límite del primer pago",
     "propose_offer no dice hasta cuándo puede ser el primer pago (hoy + 8 días); el agente no puede ofrecerlo "
     "sin conocer la regla", "5"],
    ["B8", "Intentos de verificación",
     "verify_identity no dice cuántos intentos quedan; el agente no puede avisar que es el último", "6"],
    ["B9", "Instrucciones de las herramientas (next_step)",
     "Varias no cubren casos reales: tras rechazar un parcial manda pedir la siguiente oferta aunque el deudor dio "
     "otro monto; get_account_details manda ofrecer de inmediato; record_offer_response promete \"payment "
     "instructions\" y no contempla la transferencia; mark_do_not_call pide despedirse aunque el deudor ya colgó",
     "1, 2, 7"],
    ["B10", "Enviar link de pago o confirmación",
     "No hay herramienta para enviar un SMS con el link o la confirmación del acuerdo. Depende de N1", "2"],
    ["B11", "Grabación después del \"sí\"",
     "Con el saludo de N3, la telefonía debe empezar a grabar después del consentimiento. Hoy no hay una acción "
     "para eso; se agrega al integrar la telefonía", "3, 4"],
    ["B12", "Resumen con IA de llamadas delicadas",
     "Se genera resumen aunque solo haya hablado un tercero o alguien no verificado, y en llamadas con amenazas o "
     "insultos. Definir qué incluye el resumen y que nunca mencione la deuda si no hubo verificación",
     "3, 6, 7"],
    ["B13", "Bloqueo por un impostor",
     "Con 5 fallos en 24 horas entre varias llamadas, un impostor puede bloquear a la verdadera deudora un día. "
     "Evaluar alertas", "6"],
    ["B14", "Plan elegido en Hardship",
     "recommended_plan existe en la tabla, pero no en la herramienta. Debería llenarlo el sistema al crear el "
     "acuerdo", "5"],
    ["B15", "Propuesta rechazada",
     "Un parcial rechazado no se puede aceptar después; el agente arma otro igual. Funciona; se anota para "
     "entender el registro", "1"],
]))

# --- 5. prompt y legal --------------------------------------------------------------------
S.append(PageBreak())
S.append(p("5. Observaciones del prompt del agente y temas legales", H1))
S.append(p("5.1 Prompt del agente", H2))
S.append(obs_table([
    ["P1", "Frases fijas al inicio",
     "Presentarse como asistente virtual en el saludo. \"I can share the reason once I confirm I'm speaking with "
     "the right person\" ante \"¿para qué me llaman?\". \"To protect your privacy\" al pedir los datos", "1, 2, 3"],
    ["P2", "Consentimiento de grabación",
     "Si el deudor ignora la pregunta, reconocer lo que dijo y volver a preguntar. Definir qué cuenta como \"sí\" "
     "(\"yes\", \"okay\", \"that sounds fine\")", "1, 2, 4"],
    ["P3", "Terceros",
     "Frases fijas: \"a personal business matter\" y \"I'm only able to speak with her directly\". Nunca dejar "
     "recados ni aceptar ayuda", "3"],
    ["P4", "Confirmar antes de cerrar",
     "Repetir montos y fechas y esperar un \"sí\" limpio. Un \"sí, pero con descuento\" no es aceptación. "
     "Corregir siempre las cifras equivocadas del deudor (dijo USD 370 y eran USD 395)", "1"],
    ["P5", "No inventar",
     "Regla para lo que el agente no sabe: medios de pago, si habrá cobros automáticos, quién cobra el cargo de "
     "USD 35. Si una pregunta se repite sin respuesta, ofrecer una persona", "1, 2"],
    ["P6", "Disputa o confusión",
     "Definir el límite: \"ya pagué\" y \"error del banco\" son disputa; \"intenté pagar, no sé qué pasó\" no. "
     "Antes de registrar la disputa, preguntar fecha y número de confirmación", "1, 4"],
    ["P7", "Queja o pedido de \"no llamar\"",
     "\"Me llaman todo el tiempo\" es una queja; \"no me llamen más\" es un pedido. Ante insultos, mantener la "
     "calma sin comentarlos y, si siguen, ofrecer una persona o cerrar", "7"],
    ["P8", "Largo de los turnos",
     "Aviso legal y deuda en un turno y la oferta en el siguiente, salvo que el deudor ya haya planteado su "
     "situación. Montos con centavos distintos (USD 161,68 y 161,66): decir \"about 162 dollars a month\" y los "
     "centavos solo al confirmar", "1, 2, 5"],
    ["P9", "Devolución de llamada",
     "Si el deudor pide que lo llamen pero puede fijar una fecha de pago dentro de 8 días, agendar el pago", "2"],
    ["P10", "Hardship Questions",
     "Si la respuesta no dice claramente temporal o permanente, dejar duration_type vacío y usar notes. Adaptar la "
     "pregunta 4 (\"on your next pay date\") cuando el deudor dijo que no tiene trabajo", "5"],
    ["P11", "Verificación fallida",
     "Tras un fallo, \"please double-check the numbers\". Al cerrar, dar un número de contacto si se aprueba "
     "(N12)", "6"],
]))
S.append(p("5.2 Temas legales para revisar con un abogado", H2))
S.append(obs_table([
    ["L1", "Volver a llamar a quien pidió no ser llamado",
     "Es la consecuencia del error E1. Prioritario", "7"],
    ["L2", "Consentimiento de grabación",
     "Florida y otros estados exigen el consentimiento de todas las partes. No grabar antes del \"sí\" (un tercero "
     "que contesta queda grabado sin aviso). Revisar también si una llamada sin consentimiento puede tener "
     "transcripción y resumen", "3"],
    ["L3", "Qué se le dice a un tercero",
     "El nombre de la empresa (\"Recovery Services\") delata la cobranza. Definir qué nombre se dice, a quién y en "
     "qué momento", "3, 4"],
    ["L4", "Límite de 7 llamadas en 7 días (Reg F)",
     "Cuentan las devoluciones de llamada, los recordatorios y las llamadas fallidas, del agente y de los "
     "cobradores. Hoy el sistema no cuenta las llamadas antes de llamar", "2, 6, 7"],
    ["L5", "Disputas",
     "Plazos y formato de la verificación de una deuda disputada; si basta una disputa por teléfono", "4"],
    ["L6", "Aviso \"This communication is from a debt collector\"",
     "El desarrollador pidió quitarlo por repetido; la frase no se había dicho antes en la llamada. Confirmar el "
     "texto exacto del aviso", "1"],
    ["L7", "Deudores vulnerables",
     "Obligaciones con deudores en situación vulnerable (pérdida de empleo, angustia)", "5"],
]))

# --- 6. riesgos de Haiku ------------------------------------------------------------------
S.append(PageBreak())
S.append(p("6. Riesgos de Claude Haiku 5.5 vistos en las pruebas", H1))
S.append(aviso("<b>Falta la ANTHROPIC_API_KEY.</b> Ni Claude Haiku 5.5 ni Claude Sonnet 5.5 se han podido "
               "probar. Todo lo de esta sección es una <b>hipótesis</b> basada en lo que pasó en las 7 llamadas y en "
               "cómo suelen comportarse los modelos pequeños con poco razonamiento. Solo se confirma o descarta "
               "probando con la API."))
S.append(Spacer(1, 6))
S.append(p("Configuración actual", H2))
S += bullets([
    "<b>Claude Haiku 5.5 conversa</b> en todas las llamadas, con <b>esfuerzo bajo</b> (effort: low): razona poco "
    "antes de responder para que la voz sea rápida.",
    "<b>Claude Sonnet 5.5 es solo respaldo:</b> responde un turno únicamente si Haiku falla o rechaza. "
    "<b>No</b> entra en los turnos difíciles; esos los resuelve Haiku.",
])
S.append(p("Por qué hay riesgo", H2))
S.append(p("En varias llamadas el agente tuvo que razonar en momentos ambiguos que el prompt no cubre. Un modelo "
           "pequeño con poco razonamiento tiende a seguir la instrucción más literal (la de la herramienta o la "
           "última frase del deudor). El backend protege montos, fechas y verificación, pero <b>no protege lo que "
           "el agente dice ni qué herramienta elige</b>."))
S.append(p("Momentos de riesgo", H2))
S.append(table(["Momento", "Qué podría hacer Haiku con esfuerzo bajo", "¿Lo protege el backend?", "Mitigación",
                "Pruebas", "Criticidad"], [
    ["Deudor cuelga justo después de pedir \"no llamar\" o disputar",
     "Seguir el aviso de cuelgue y cerrar con end_call como callback_requested", "No (error E1)",
     "Corregir el aviso de cuelgue y probarlo", "7", "Crítico"],
    ["Contesta un tercero o alguien no verificado",
     "Ser amable de más: \"it's about her payment\", aceptar ayuda o dejar recado",
     "Parcial: sin verificación no consulta la cuenta, pero puede hablar", "Frases fijas (P3)", "3, 6", "Crítico"],
    ["Preguntas sin respuesta (medio de pago, cobros, cargo de USD 35)",
     "Inventar: \"we'll text you a link\", \"nothing will be charged\"", "No", "N1 y regla P5", "1, 2", "Alto"],
    ["\"Sí\" con condiciones o cifras equivocadas",
     "Registrar la aceptación y no corregir; el deudor cuelga mal informado",
     "Parcial: no se guarda ningún descuento", "Regla P4", "1", "Alto"],
    ["Disputa o confusión",
     "Marcar disputa ante \"no sé qué pasó\", o ignorar una disputa real", "No", "Regla P6", "1, 4", "Alto"],
    ["Queja o pedido de \"no llamar\"",
     "Marcar \"no llamar\" ante una queja, o no marcarlo ante un pedido", "No", "Regla P7", "7", "Alto"],
    ["Guardar las Hardship de a una",
     "Guardar después de cada respuesta, que es lo natural", "No (error E2)", "Corregir el repositorio", "5",
     "Alto"],
    ["Seguir la instrucción de la herramienta al pie de la letra",
     "Ofrecer de inmediato, prometer \"payment instructions\", despedirse de una línea muerta",
     "No", "Corregir los next_step (B9)", "1, 2, 7", "Medio"],
    ["Aceptación tibia de un acuerdo difícil",
     "Aceptar \"I'll give it a try\" sin más", "No", "Decisión N7", "1", "Medio"],
    ["Clasificar y adaptar las Hardship Questions",
     "Forzar temporary o long_term; leer la pregunta 4 tal cual a alguien sin trabajo", "No", "Regla P10", "5",
     "Medio"],
    ["Turnos largos y montos con centavos",
     "Leer cifras exactas largas; turnos que no caben en voz", "No aplica", "Regla P8", "1, 2, 5", "Bajo"],
    ["Avanzar sin consentimiento de grabación",
     "Seguir la conversación sin el \"sí\"", "Sí: las herramientas devuelven error", "Regla P2", "1, 2", "Bajo"],
], [2.8 * cm, 3.5 * cm, 2.6 * cm, 2.5 * cm, 1.5 * cm, 1.8 * cm], crit_col=5))
S.append(p("Opciones y costo aproximado", H2))
S.append(p("Con 800 llamadas diarias. Precios por millón de tokens: Haiku 5.5, USD 0,10 de entrada y USD 0,50 de "
           "salida; Sonnet 5.5, USD 2 y USD 10 (unas 20 veces más). El resto del costo mensual (telefonía, voz, "
           "servidores), unos USD 3.650, no cambia con el modelo."))
S.append(table(["Opción", "Cómo funciona", "Costo de la conversación (USD/mes)", "Ventajas", "Riesgos"], [
    ["A. Haiku con esfuerzo bajo (actual)", "Todo lo responde Haiku; Sonnet solo si Haiku falla", "~132",
     "Lo más barato y rápido", "Los momentos de la tabla dependen solo del prompt"],
    ["B. Haiku con esfuerzo medio", "Haiku razona más en cada turno", "Algo más que A",
     "Mejor juicio sin cambiar de modelo", "Más demora por turno: hay que medirla en voz"],
    ["C. Haiku y Sonnet en momentos difíciles", "Sonnet solo en turnos marcados: negociación, disputa, terceros",
     "Entre A y D", "Juicio de Sonnet donde importa", "Más complejo; Sonnet tarda más; se pierde la caché"],
    ["D. Sonnet en todo", "Sonnet conversa siempre", "~2.640 (unas 20 veces A)", "El mejor juicio",
     "Unos USD 2.500 más al mes y más demora en voz"],
], [3 * cm, 3.6 * cm, 3 * cm, 3 * cm, 2.8 * cm]))
S.append(p("Recomendación", H2))
S += bullets([
    "Corregir los errores E1 y E2 y reforzar el prompt con las observaciones de la sección 5. Reduce el riesgo con "
    "cualquier modelo y no cuesta más por llamada.",
    "<b>Apenas haya API key</b>, armar unos 20 casos difíciles con los momentos de la tabla y correrlos con Haiku "
    "(menos de USD 1) y con Sonnet (unos pocos dólares).",
    "Decidir con datos: si Haiku con esfuerzo bajo falla, probar primero la opción B y luego la C, antes de D. "
    "Medir también la demora por turno.",
])

doc = SimpleDocTemplate(OUT, pagesize=letter, leftMargin=1.8 * cm, rightMargin=1.8 * cm, topMargin=1.7 * cm,
                        bottomMargin=1.8 * cm, title="Informe de simulaciones del agente de cobranza NSF",
                        author="Agente de cobranza NSF", subject="Pruebas simuladas 2026-11-11")
doc.build(S, onFirstPage=footer, onLaterPages=footer)
print("ok", OUT)
