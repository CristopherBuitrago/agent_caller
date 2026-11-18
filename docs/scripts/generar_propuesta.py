"""Genera la propuesta del agente de cobranza NSF para Live Oac Financial (español e inglés).

Uso (dentro de un contenedor con reportlab instalado, desde docs/; deja el PDF en docs/propuesta/):
    python scripts/generar_propuesta.py es   ->  propuesta/propuesta_es.pdf
    python scripts/generar_propuesta.py en   ->  propuesta/proposal_en.pdf
"""

import sys
from pathlib import Path

from reportlab.lib import colors
from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import cm
from reportlab.platypus import (Flowable, KeepTogether, PageBreak, Paragraph, SimpleDocTemplate, Spacer,
                                Table, TableStyle)

# Los PDF y los Word quedan en docs/propuesta/ (este script está en docs/scripts/).
OUT_DIR = Path(__file__).resolve().parents[1] / "propuesta"

AZUL = colors.HexColor("#1F3A5F")
AZUL_CLARO = colors.HexColor("#E8EEF7")
GRIS = colors.HexColor("#F2F4F7")
BORDE = colors.HexColor("#C9D1DC")
VERDE = colors.HexColor("#E7F6EC")
VERDE_BORDE = colors.HexColor("#3B8C5A")
NARANJA = colors.HexColor("#FDF2E6")
NARANJA_BORDE = colors.HexColor("#C4741B")
W = letter[0] - 3.4 * cm

ss = getSampleStyleSheet()
TITLE = ParagraphStyle("T", parent=ss["Title"], fontName="Helvetica-Bold", fontSize=21, leading=25,
                       textColor=AZUL, alignment=0, spaceAfter=4)
SUB = ParagraphStyle("S", parent=ss["Normal"], fontName="Helvetica", fontSize=11, textColor=colors.HexColor("#475467"),
                     spaceAfter=14)
H1 = ParagraphStyle("H1", parent=ss["Heading1"], fontName="Helvetica-Bold", fontSize=14.5, textColor=AZUL,
                    spaceBefore=14, spaceAfter=6, keepWithNext=True)
BODY = ParagraphStyle("B", parent=ss["Normal"], fontName="Helvetica", fontSize=9.8, leading=13.6, spaceAfter=5,
                      textColor=colors.HexColor("#344054"))
BUL = ParagraphStyle("BUL", parent=BODY, leftIndent=13, bulletIndent=3, spaceAfter=3)
NOTE = ParagraphStyle("N", parent=BODY, fontSize=8.6, leading=11.5, textColor=colors.HexColor("#667085"))
CELL = ParagraphStyle("C", parent=BODY, fontSize=8.8, leading=11.4, spaceAfter=0, textColor=colors.black)
CELLB = ParagraphStyle("CB", parent=CELL, fontName="Helvetica-Bold")
HEAD = ParagraphStyle("HD", parent=CELL, fontName="Helvetica-Bold", textColor=colors.white)
BOX = ParagraphStyle("BX", parent=CELL, fontSize=8.4, leading=10.4, alignment=1)
BOXL = ParagraphStyle("BXL", parent=BOX, alignment=0)

TEXT = {
    "es": {
        "out": str(OUT_DIR / "propuesta_es.pdf"),
        "title": "Propuesta: agente de cobranza con inteligencia artificial para cuentas NSF",
        "subtitle": "Live Oac Financial · Llamadas entrantes y salientes · Noviembre de 2026",
        "footer": "Propuesta: agente de cobranza NSF",
        "page": "Página",
        "s1": "1. Propuesta",
        "s1_body": [
            "Un <b>agente de voz con inteligencia artificial</b> que atiende las llamadas de cobranza de las cuentas en "
            "estado <b>NSF</b> (pagos devueltos por fondos insuficientes), tanto las que <b>entran</b> (el deudor llama) "
            "como las que <b>salen</b> (el agente llama a una lista diaria de cuentas NSF).",
            "En cada llamada el agente informa la grabación, verifica la identidad del deudor, da el aviso legal de "
            "cobranza, explica la deuda y ofrece opciones de pago en un orden fijo: pago total, cuotas y, si hace falta, "
            "un plan de hasta 12 meses. Cuando hay acuerdo, el deudor recibe por SMS la confirmación, un aviso antes de "
            "cada cuota y el link de pago. Lo que el agente no debe resolver solo (disputas, otros estados de cuenta o "
            "un deudor que pide hablar con una persona) pasa a los cobradores.",
            "<b>Nunca ofrece descuentos</b>: siempre se cobra el saldo completo. Los montos, las fechas y lo que se "
            "guarda los decide el sistema con las reglas de la empresa, no la inteligencia artificial.",
        ],
        "status_title": "Estado actual",
        "status": [
            "Las reglas de cobranza, la base de datos y el agente conversacional están construidos y probados "
            "(443 pruebas automáticas y 7 simulaciones de llamadas revisadas).",
            "Hay una demo por chat en el navegador, con el historial completo de cada llamada para auditarla.",
            "<b>Siguiente fase:</b> la voz (hablar y escuchar), la conexión con Vaspian, el procesador de pagos y la "
            "base de datos real, y un piloto con llamadas reales.",
        ],
        "s2": "2. Objetivos",
        "goals": [
            ("Liberar a los cobradores", "El agente atiende las llamadas NSF de rutina; los cobradores se "
             "concentran en los casos que necesitan a una persona."),
            ("Contactar más deudores", "Una lista diaria automática de cuentas NSF, respetando el límite legal "
             "de 7 llamadas en 7 días (Reg F) y el horario permitido."),
            ("Más acuerdos de pago", "Ofrece siempre las opciones en el mismo orden, sin presionar, hasta un plan de "
             "12 meses; nunca descuentos."),
            ("Cumplimiento constante", "Aviso de grabación y aviso legal en cada llamada, verificación de identidad, "
             "nada de información a terceros y respeto al pedido de no llamar."),
            ("Menor costo por contacto", "Unos USD 0,08 por llamada en servicios nuevos, más la telefonía que ya se "
             "tiene."),
            ("Todo queda registrado", "Cada llamada guarda su resultado, un resumen escrito por la IA y la "
             "conversación completa."),
        ],
        "goals_head": ["Objetivo", "Cómo lo logra"],
        "kpi": "En el piloto se medirán: porcentaje de llamadas resueltas sin un cobrador, acuerdos por cada 100 "
               "llamadas, porcentaje de acuerdos cumplidos y duración promedio de la llamada.",
        "s3": "3. Flujo de una llamada",
        "flow_note": "En cualquier momento de la llamada: si el deudor dice que ya pagó o que la deuda no es suya, el "
                     "agente primero busca el pago en la base de la empresa (cuando Lariat esté conectada); si no lo "
                     "encuentra, pide la fecha y el número de confirmación, registra la disputa (estado DISPUTE) y "
                     "deja de cobrar hasta que la revise un cobrador. Si pide explícitamente no ser "
                     "llamado, se marca \"no llamar\"; si pide una persona, se transfiere a la cola de cobradores. "
                     "Ante angustia, insultos o amenazas, el agente mantiene la calma y sigue.",
        "flow": {
            "in": "<b>Entrante</b><br/>El deudor llama",
            "out": "<b>Saliente</b><br/>Lista diaria de cuentas NSF",
            "greet": "<b>Saludo y aviso de grabación</b><br/>En salientes, primero confirma que habla con el deudor",
            "third": "<b>Contesta otra persona</b><br/>\"Es un asunto personal\". Sin recados. Se agenda otra llamada",
            "verify": "<b>Verificación de identidad</b><br/>Nombre completo, últimos 4 del SSN y fecha de nacimiento",
            "fail": "<b>No se verifica</b><br/>2 intentos o cambia de nombre: se cierra sin hablar de la deuda y se da "
                    "el número de la línea",
            "disclose": "<b>Aviso legal y la deuda</b><br/>Aviso de cobranza (FDCPA), acreedor, saldo y motivo del "
                        "rebote",
            "offers": "<b>Opciones de pago, en orden</b><br/>Pago total → 2 cuotas → 3 cuotas → preguntas de "
                      "dificultad económica → 4 a 10 cuotas → 10% y 12 cuotas",
            "accept": "<b>¿Acepta con un sí claro?</b>",
            "no": "<b>No acepta</b><br/>Se agenda otra llamada o se transfiere a un cobrador",
            "deal": "<b>Acuerdo (cuenta en PTP)</b><br/>SMS de confirmación, aviso 3 días antes y link de pago en "
                    "cada fecha",
            "end": "<b>Cierre</b><br/>Resultado, resumen con IA e historial completo",
            "broken": "Si una cuota pasa 5 días sin pagarse, el acuerdo se rompe y la cuenta vuelve a NSF y a la lista",
            "yes": "Sí", "no_lbl": "No",
        },
        "s4": "4. Los tres sistemas",
        "systems_head": ["Sistema", "Qué hace"],
        "systems": [
            ("Backend (núcleo de reglas)",
             "Guarda deudores, cuentas, llamadas y acuerdos. Aplica todas las reglas: verificación de identidad, orden "
             "y montos de las ofertas, fechas de las cuotas, disputas, \"no llamar\" y la lista diaria de salientes. "
             "La inteligencia artificial no decide montos ni fechas: los calcula este núcleo. Python y PostgreSQL."),
            ("Agente (conversación y voz)",
             "Claude Haiku 5.5 conversa con el deudor y usa 13 herramientas del núcleo para verificar, ofrecer y "
             "registrar. La voz se arma con AssemblyAI (entiende lo que dice el deudor), Deepgram Aura-2 (habla) y "
             "Pipecat (une las piezas), sobre la telefonía de Vaspian. Incluye una página web de prueba con historial."),
            ("Mensajería (SMS)",
             "Envía la confirmación del acuerdo, un aviso 3 días antes de cada cuota y el link de pago el día de la "
             "cuota. Detecta los acuerdos rotos (5 días sin pago) y devuelve la cuenta a NSF."),
        ],
        "s6": "6. Inversión y forma de trabajo",
        "s6_intro": "La empresa paga directamente a los proveedores (sección 5). El trabajo de implementación y "
                    "operación del agente se cobra así:",
        "inv_head": ["Concepto", "Qué incluye", "Precio (USD)"],
        "inv": [
            ("Piloto", "Montaje del agente con voz, conexión con Vaspian, el procesador de pagos y Lariat, instalación "
             "en AWS y pruebas con llamadas reales de cuentas NSF", "500, una sola vez"),
            ("Producción", "<b>Auditoría:</b> revisión de llamadas y del cumplimiento (aviso legal, verificación, "
             "\"no llamar\", terceros). <b>Mantenimiento:</b> atención de fallas y ajustes al prompt y a las reglas "
             "existentes. <b>Reporte mensual de llamadas:</b> llamadas atendidas, acuerdos, acuerdos cumplidos, "
             "disputas, transferencias y hallazgos", "2.000 al mes"),
            ("Nuevo estado de cuenta", "NSF ya está incluido. Cada estado nuevo (por ejemplo, PTP): nuevas reglas de "
             "negocio, ajustes en el flujo del agente y pruebas", "1.000 por estado"),
        ],
        "inv_notes": [
            "La mensualidad empieza cuando el agente pasa a producción.",
            "No incluye los costos de los proveedores (~USD 1.966 al mes con 800 llamadas diarias), que la empresa "
            "paga directamente.",
            "Las funciones nuevas que estén fuera de este alcance se cotizan aparte.",
        ],
        "s7": "7. Propiedad del código y licencia de uso",
        "s7_intro": "La empresa no compra el software del agente: recibe una licencia para usarlo. El Desarrollador "
                    "es quien implementa, opera y mantiene el agente.",
        "s7_items": [
            "<b>Propiedad.</b> El software del agente (código fuente, instrucciones del modelo de IA, reglas de "
            "negocio programadas, pruebas, documentación técnica y diseño), con sus mejoras y versiones futuras, es y "
            "sigue siendo propiedad exclusiva del Desarrollador, aunque se instale en los servidores de la empresa.",
            "<b>Licencia.</b> La empresa recibe una licencia de uso no exclusiva e intransferible, solo para su propia "
            "operación de cobranza, mientras el servicio esté vigente y los pagos estén al día.",
            "<b>Restricciones.</b> Sin autorización escrita del Desarrollador, la empresa no puede vender, ceder, "
            "sublicenciar, copiar, modificar ni entregar el software a terceros, ni crear productos derivados de él.",
            "<b>Uso por el Desarrollador.</b> El Desarrollador puede usar y licenciar el software a otras empresas, "
            "sin usar ni revelar datos de Live Oac Financial.",
            "<b>Datos.</b> Los datos de los deudores, las cuentas y las llamadas son de la empresa. El Desarrollador "
            "solo los usa para prestar el servicio y los mantiene confidenciales.",
            "<b>Fin del servicio.</b> Si el servicio termina, termina la licencia: el software se desinstala y la "
            "empresa conserva sus datos, que se le entregan en un formato estándar (por ejemplo, CSV).",
        ],
        "s5": "5. Proveedores y costos",
        "have_title": "Lo que la empresa ya tiene (sin costo nuevo)",
        "have_head": ["Servicio", "Proveedor", "Uso"],
        "have": [
            ("Telefonía y SMS", "Vaspian", "Llamadas entrantes y salientes, grabación, transferencia a cobradores y SMS. "
             "Puede sumar minutos y mensajes según el contrato actual"),
            ("Servidores y base de datos", "AWS", "Donde corre el sistema, dentro de la cuenta que ya se usa"),
            ("Datos de los deudores", "Lariat Software", "Fuente de deudores, cuentas y pagos"),
        ],
        "buy_title": "Lo que hay que contratar",
        "buy_head": ["Servicio", "Proveedor", "USD al mes"],
        "buy": [
            ("Inteligencia artificial: conversación, resúmenes y respaldo", "Anthropic: Claude Haiku 5.5 (respaldo "
             "Sonnet 5.5)", "~166"),
            ("Voz a texto (entender al deudor)", "AssemblyAI Universal-Streaming", "~240"),
            ("Texto a voz (la voz del agente)", "Deepgram Aura-2", "~1.080"),
            ("Pago con tarjeta seguro (IVR PCI)", "Por elegir, según Vaspian y el procesador de pagos", "~480"),
            ("Orquestación de la voz", "Pipecat (código abierto)", "0"),
        ],
        "total": ("Total", "", "~1.966"),
        "cost_notes": [
            "Calculado con <b>800 llamadas diarias</b> (24.000 al mes, 4 minutos en promedio), precios de lista de "
            "noviembre de 2026. Son unos <b>USD 0,08 por llamada</b>, más los minutos de Vaspian.",
            "El IVR PCI es una estimación (USD 0,20 por pago, en el 10% de las llamadas). Las comisiones del "
            "procesador de pagos no están incluidas: se cobran sobre el dinero recaudado.",
            "Falta confirmar que Vaspian puede enviar el audio de la llamada en vivo al agente; es lo único que "
            "falta para la parte de voz.",
        ],
    },
    "en": {
        "out": str(OUT_DIR / "proposal_en.pdf"),
        "title": "Proposal: AI collection agent for NSF accounts",
        "subtitle": "Live Oac Financial · Inbound and outbound calls · November 2026",
        "footer": "Proposal: NSF collection agent",
        "page": "Page",
        "s1": "1. Proposal",
        "s1_body": [
            "An <b>AI voice agent</b> that handles collection calls for accounts in <b>NSF</b> status (payments "
            "returned for non-sufficient funds), both <b>inbound</b> (the debtor calls) and <b>outbound</b> (the "
            "agent calls a daily list of NSF accounts).",
            "On every call the agent gives the recording notice, verifies the debtor's identity, gives the debt "
            "collection disclosure, explains the debt, and offers payment options in a fixed order: full payment, "
            "installments and, if needed, a plan of up to 12 months. When there is an agreement, the debtor gets a "
            "text confirmation, a reminder before each installment, and the payment link. Anything the agent should "
            "not handle alone (disputes, other account statuses, or a debtor asking for a person) goes to the "
            "collectors.",
            "<b>It never offers discounts</b>: the full balance is always collected. Amounts, dates, and what gets "
            "saved are decided by the system using the company's rules, not by the AI.",
        ],
        "status_title": "Current status",
        "status": [
            "The collection rules, the database, and the conversational agent are built and tested (443 automated "
            "tests and 7 reviewed call simulations).",
            "A chat demo runs in the browser, with the full history of every call for auditing.",
            "<b>Next phase:</b> voice (speaking and listening), the Vaspian connection, the payment processor, the "
            "real database, and a pilot with real calls.",
        ],
        "s2": "2. Goals",
        "goals": [
            ("Free up collectors", "The agent handles routine NSF calls; collectors focus on the cases that need "
             "a person."),
            ("Reach more debtors", "An automatic daily list of NSF accounts that respects the legal limit of 7 "
             "calls in 7 days (Reg F) and allowed calling hours."),
            ("More payment arrangements", "It always offers the options in the same order, without pressure, up to "
             "a 12-month plan; never discounts."),
            ("Consistent compliance", "Recording notice and debt collection disclosure on every call, identity "
             "verification, no information to third parties, and honoring do-not-call requests."),
            ("Lower cost per contact", "About USD 0.08 per call in new services, plus the phone service already in "
             "place."),
            ("Everything is recorded", "Every call saves its outcome, an AI-written summary, and the full "
             "conversation."),
        ],
        "goals_head": ["Goal", "How it gets there"],
        "kpi": "The pilot will measure: percentage of calls resolved without a collector, arrangements per 100 calls, "
               "percentage of arrangements kept, and average call length.",
        "s3": "3. Call flow",
        "flow_note": "At any point in the call: if the debtor says they already paid or that the debt is not theirs, "
                     "the agent first looks for the payment in the company database (once Lariat is connected); if it "
                     "is not found, it asks for the payment date and confirmation number, records the dispute "
                     "(DISPUTE status), and stops collecting until a collector reviews it. If the debtor explicitly "
                     "asks not to be called, the account is marked do-not-call; if they ask for a person, the call is "
                     "transferred to the collectors' queue. If the debtor is distressed, insulting, or threatening, "
                     "the agent stays calm and continues.",
        "flow": {
            "in": "<b>Inbound</b><br/>The debtor calls",
            "out": "<b>Outbound</b><br/>Daily list of NSF accounts",
            "greet": "<b>Greeting and recording notice</b><br/>On outbound calls, first confirms it is speaking with "
                     "the debtor",
            "third": "<b>Someone else answers</b><br/>\"It's a personal matter.\" No messages left. Another call is "
                     "scheduled",
            "verify": "<b>Identity verification</b><br/>Full name, last 4 of the SSN, and date of birth",
            "fail": "<b>Not verified</b><br/>2 attempts or a name change: the call ends without discussing the debt, "
                    "and the callback number is given",
            "disclose": "<b>Disclosure and the debt</b><br/>FDCPA notice, creditor, balance, and return reason",
            "offers": "<b>Payment options, in order</b><br/>Full payment → 2 installments → 3 installments → "
                      "hardship questions → 4 to 10 installments → 10% and 12 installments",
            "accept": "<b>Clear yes?</b>",
            "no": "<b>Declines</b><br/>Another call is scheduled or the call goes to a collector",
            "deal": "<b>Arrangement (account in PTP)</b><br/>Text confirmation, reminder 3 days before, and payment "
                    "link on each date",
            "end": "<b>Call ends</b><br/>Outcome, AI summary, and full history",
            "broken": "If an installment is 5 days past due, the arrangement is broken and the account goes back "
                      "to NSF and to the daily list",
            "yes": "Yes", "no_lbl": "No",
        },
        "s4": "4. The three systems",
        "systems_head": ["System", "What it does"],
        "systems": [
            ("Backend (rules core)",
             "Stores debtors, accounts, calls, and arrangements. Applies every rule: identity verification, order "
             "and amounts of offers, installment dates, disputes, do-not-call, and the daily outbound list. The AI "
             "never decides amounts or dates: this core calculates them. Python and PostgreSQL."),
            ("Agent (conversation and voice)",
             "Claude Haiku 5.5 talks with the debtor and uses 13 tools from the core to verify, offer, and record. "
             "Voice is built with AssemblyAI (understands the debtor), Deepgram Aura-2 (speaks), and Pipecat (connects "
             "the pieces), over Vaspian phone service. Includes a test web page with call history."),
            ("Messaging (text messages)",
             "Sends the arrangement confirmation, a reminder 3 days before each installment, and the payment link on "
             "the due date. Detects broken arrangements (5 days unpaid) and returns the account to NSF."),
        ],
        "s6": "6. Investment and terms",
        "s6_intro": "The company pays the providers directly (section 5). The work to implement and run the agent is "
                    "billed as follows:",
        "inv_head": ["Item", "What it includes", "Price (USD)"],
        "inv": [
            ("Pilot", "Setting up the voice agent, connecting Vaspian, the payment processor, and Lariat, deploying on "
             "AWS, and testing with real calls on NSF accounts", "500, one time"),
            ("Production", "<b>Auditing:</b> review of calls and compliance (disclosure, verification, do-not-call, "
             "third parties). <b>Maintenance:</b> fixing issues and adjusting the prompt and existing rules. "
             "<b>Monthly call report:</b> calls handled, arrangements, arrangements kept, disputes, transfers, and "
             "findings", "2,000 per month"),
            ("New account status", "NSF is already included. Each new status (for example, PTP): new business rules, "
             "changes to the agent's flow, and testing", "1,000 per status"),
        ],
        "inv_notes": [
            "The monthly fee starts when the agent goes into production.",
            "It does not include provider costs (~USD 1,966 per month at 800 calls per day), which the company pays "
            "directly.",
            "New features outside this scope are quoted separately.",
        ],
        "s7": "7. Code ownership and license",
        "s7_intro": "The company does not buy the agent's software: it receives a license to use it. The Developer "
                    "implements, runs, and maintains the agent.",
        "s7_items": [
            "<b>Ownership.</b> The agent's software (source code, AI model instructions, programmed business rules, "
            "tests, technical documentation, and design), including its improvements and future versions, is and "
            "remains the exclusive property of the Developer, even when installed on the company's servers.",
            "<b>License.</b> The company receives a non-exclusive, non-transferable license to use the software, only "
            "for its own collection operations, while the service is active and payments are up to date.",
            "<b>Restrictions.</b> Without the Developer's written permission, the company may not sell, assign, "
            "sublicense, copy, modify, or give the software to third parties, or create derivative products from it.",
            "<b>Use by the Developer.</b> The Developer may use and license the software to other companies, without "
            "using or disclosing any Live Oac Financial data.",
            "<b>Data.</b> Debtor, account, and call data belong to the company. The Developer uses it only to provide "
            "the service and keeps it confidential.",
            "<b>End of service.</b> If the service ends, the license ends: the software is uninstalled and the company "
            "keeps its data, delivered in a standard format (for example, CSV).",
        ],
        "s5": "5. Providers and costs",
        "have_title": "Already in place (no new cost)",
        "have_head": ["Service", "Provider", "Use"],
        "have": [
            ("Phone and text messages", "Vaspian", "Inbound and outbound calls, recording, transfers to collectors, "
             "and text messages. Minutes and messages may add to the current contract"),
            ("Servers and database", "AWS", "Where the system runs, within the account already in use"),
            ("Debtor data", "Lariat Software", "Source of debtors, accounts, and payments"),
        ],
        "buy_title": "To be purchased",
        "buy_head": ["Service", "Provider", "USD per month"],
        "buy": [
            ("AI: conversation, summaries, and backup", "Anthropic: Claude Haiku 5.5 (Sonnet 5.5 backup)", "~166"),
            ("Speech to text (understanding the debtor)", "AssemblyAI Universal-Streaming", "~240"),
            ("Text to speech (the agent's voice)", "Deepgram Aura-2", "~1,080"),
            ("Secure card payment (PCI IVR)", "To be chosen, based on Vaspian and the payment processor", "~480"),
            ("Voice orchestration", "Pipecat (open source)", "0"),
        ],
        "total": ("Total", "", "~1,966"),
        "cost_notes": [
            "Based on <b>800 calls per day</b> (24,000 per month, 4 minutes on average), list prices as of November "
            "2026. That is about <b>USD 0.08 per call</b>, plus Vaspian minutes.",
            "The PCI IVR is an estimate (USD 0.20 per payment, on 10% of calls). Payment processor fees are not "
            "included: they are charged on the money collected.",
            "It still needs to be confirmed that Vaspian can stream live call audio to the agent; it is the only open "
            "item for the voice part.",
        ],
    },
}


class Flow(Flowable):
    """Diagrama de flujo dibujado con cajas y flechas."""

    def __init__(self, t):
        super().__init__()
        self.t = t
        self.width, self.height = W, 470

    def wrap(self, *_):
        return self.width, self.height

    def _box(self, c, x, y, w, h, html, fill=AZUL_CLARO, stroke=AZUL, style=BOX):
        c.setFillColor(fill)
        c.setStrokeColor(stroke)
        c.setLineWidth(0.9)
        c.roundRect(x, y, w, h, 6, stroke=1, fill=1)
        p = Paragraph(html, style)
        pw, ph = p.wrap(w - 10, h)
        p.drawOn(c, x + 5, y + (h - ph) / 2)

    def _arrow(self, c, x1, y1, x2, y2, label=None):
        c.setStrokeColor(colors.HexColor("#475467"))
        c.setFillColor(colors.HexColor("#475467"))
        c.setLineWidth(1)
        c.line(x1, y1, x2, y2)
        import math
        a = math.atan2(y2 - y1, x2 - x1)
        s = 5
        p = c.beginPath()
        p.moveTo(x2, y2)
        p.lineTo(x2 - s * math.cos(a - 0.45), y2 - s * math.sin(a - 0.45))
        p.lineTo(x2 - s * math.cos(a + 0.45), y2 - s * math.sin(a + 0.45))
        p.close()
        c.drawPath(p, fill=1, stroke=0)
        if label:
            c.setFont("Helvetica-Bold", 7.5)
            c.drawString((x1 + x2) / 2 + 3, (y1 + y2) / 2 + 2, label)

    def draw(self):
        c, f = self.canv, self.t["flow"]
        mw, mx = 230, 20                    # columna principal
        sx, sw = 300, W - 300               # columna lateral
        h = 40
        ys = {"start": 425, "greet": 365, "verify": 300, "disclose": 235, "offers": 165, "accept": 112,
              "deal": 52, "end": 0}
        # inicio: dos entradas
        half = (mw - 10) / 2
        self._box(c, mx, ys["start"], half, h, f["in"], GRIS, BORDE)
        self._box(c, mx + half + 10, ys["start"], half, h, f["out"], GRIS, BORDE)
        cx = mx + mw / 2
        self._arrow(c, mx + half / 2, ys["start"], cx - 20, ys["greet"] + 44)
        self._arrow(c, mx + half + 10 + half / 2, ys["start"], cx + 20, ys["greet"] + 44)
        self._box(c, mx, ys["greet"], mw, 44, f["greet"])
        self._box(c, sx, ys["greet"], sw, 44, f["third"], NARANJA, NARANJA_BORDE)
        self._arrow(c, mx + mw, ys["greet"] + 22, sx, ys["greet"] + 22)
        self._arrow(c, cx, ys["greet"], cx, ys["verify"] + 44)
        self._box(c, mx, ys["verify"], mw, 44, f["verify"])
        self._box(c, sx, ys["verify"], sw, 44, f["fail"], NARANJA, NARANJA_BORDE)
        self._arrow(c, mx + mw, ys["verify"] + 22, sx, ys["verify"] + 22, f["no_lbl"])
        self._arrow(c, cx, ys["verify"], cx, ys["disclose"] + 44, f["yes"])
        self._box(c, mx, ys["disclose"], mw, 44, f["disclose"])
        self._arrow(c, cx, ys["disclose"], cx, ys["offers"] + 50)
        self._box(c, mx, ys["offers"], mw, 50, f["offers"])
        self._arrow(c, cx, ys["offers"], cx, ys["accept"] + 32)
        self._box(c, mx + 30, ys["accept"], mw - 60, 32, f["accept"], colors.white, AZUL)
        self._box(c, sx, ys["accept"] - 4, sw, 40, f["no"], NARANJA, NARANJA_BORDE)
        self._arrow(c, mx + mw - 30, ys["accept"] + 16, sx, ys["accept"] + 16, f["no_lbl"])
        self._arrow(c, cx, ys["accept"], cx, ys["deal"] + 44, f["yes"])
        self._box(c, mx, ys["deal"], mw, 44, f["deal"], VERDE, VERDE_BORDE)
        self._box(c, sx, ys["deal"], sw, 44, f["broken"], GRIS, BORDE, BOXL)
        self._arrow(c, mx + mw, ys["deal"] + 22, sx, ys["deal"] + 22)
        self._arrow(c, cx, ys["deal"], cx, ys["end"] + 36)
        self._box(c, mx, ys["end"], mw, 36, f["end"], GRIS, BORDE)


def table(head, rows, widths, bold_last=False):
    data = [[Paragraph(h, HEAD) for h in head]]
    for r in rows:
        data.append([Paragraph(str(v), CELLB if i == 0 else CELL) for i, v in enumerate(r)])
    t = Table(data, colWidths=widths, repeatRows=1)
    style = [
        ("BACKGROUND", (0, 0), (-1, 0), AZUL),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("GRID", (0, 0), (-1, -1), 0.4, BORDE),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, GRIS]),
        ("LEFTPADDING", (0, 0), (-1, -1), 5), ("RIGHTPADDING", (0, 0), (-1, -1), 5),
        ("TOPPADDING", (0, 0), (-1, -1), 4), ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
    ]
    if bold_last:
        style += [("BACKGROUND", (0, -1), (-1, -1), AZUL_CLARO)]
    t.setStyle(TableStyle(style))
    return t


def build(lang):
    t = TEXT[lang]
    s = [Paragraph(t["title"], TITLE), Paragraph(t["subtitle"], SUB)]

    s.append(Paragraph(t["s1"], H1))
    s += [Paragraph(p, BODY) for p in t["s1_body"]]
    s.append(Spacer(1, 4))
    status = [Paragraph(f"<b>{t['status_title']}</b>", CELL)] + [
        Paragraph("• " + p, CELL) for p in t["status"]]
    box = Table([[status]], colWidths=[W])
    box.setStyle(TableStyle([("BACKGROUND", (0, 0), (-1, -1), AZUL_CLARO), ("BOX", (0, 0), (-1, -1), 0.6, AZUL),
                             ("LEFTPADDING", (0, 0), (-1, -1), 9), ("TOPPADDING", (0, 0), (-1, -1), 7),
                             ("BOTTOMPADDING", (0, 0), (-1, -1), 7)]))
    s.append(box)

    s.append(Paragraph(t["s2"], H1))
    s.append(table(t["goals_head"], [(f"<b>{a}</b>", b) for a, b in t["goals"]], [4.6 * cm, W - 4.6 * cm]))
    s.append(Spacer(1, 4))
    s.append(Paragraph(t["kpi"], NOTE))

    s.append(PageBreak())
    s.append(Paragraph(t["s3"], H1))
    s.append(Flow(t))
    s.append(Spacer(1, 8))
    s.append(Paragraph(t["flow_note"], NOTE))

    s.append(PageBreak())
    s.append(Paragraph(t["s4"], H1))
    s.append(table(t["systems_head"], t["systems"], [4.6 * cm, W - 4.6 * cm]))

    s.append(Paragraph(t["s5"], H1))
    s.append(Paragraph(f"<b>{t['have_title']}</b>", BODY))
    s.append(table(t["have_head"], t["have"], [4.2 * cm, 4.6 * cm, W - 8.8 * cm]))
    s.append(Spacer(1, 8))
    s.append(KeepTogether([Paragraph(f"<b>{t['buy_title']}</b>", BODY),
                           table(t["buy_head"], t["buy"] + [tuple(f"<b>{v}</b>" for v in t["total"])],
                                 [7.0 * cm, W - 9.6 * cm, 2.6 * cm], bold_last=True)]))
    s.append(Spacer(1, 6))
    s += [Paragraph(n, BUL, bulletText="•") for n in t["cost_notes"]]

    s.append(PageBreak())
    s.append(Paragraph(t["s6"], H1))
    s.append(Paragraph(t["s6_intro"], BODY))
    s.append(table(t["inv_head"], t["inv"], [3.6 * cm, W - 7.4 * cm, 3.8 * cm]))
    s.append(Spacer(1, 6))
    s += [Paragraph(n, BUL, bulletText="•") for n in t["inv_notes"]]

    s.append(Spacer(1, 10))
    s.append(Paragraph(t["s7"], H1))
    s.append(Paragraph(t["s7_intro"], BODY))
    s += [Paragraph(n, BUL, bulletText="•") for n in t["s7_items"]]

    def footer(canvas, doc):
        canvas.saveState()
        canvas.setFont("Helvetica", 7.5)
        canvas.setFillColor(colors.HexColor("#667085"))
        canvas.drawString(1.7 * cm, 1.1 * cm, t["footer"])
        canvas.drawRightString(letter[0] - 1.7 * cm, 1.1 * cm, f"{t['page']} {doc.page}")
        canvas.restoreState()

    doc = SimpleDocTemplate(t["out"], pagesize=letter, leftMargin=1.7 * cm, rightMargin=1.7 * cm,
                            topMargin=1.6 * cm, bottomMargin=1.8 * cm, title=t["title"], author="Live Oac Financial")
    doc.build(s, onFirstPage=footer, onLaterPages=footer)
    print("ok", t["out"])


if __name__ == "__main__":
    build(sys.argv[1] if len(sys.argv) > 1 else "es")
