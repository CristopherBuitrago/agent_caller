# Simulación 7: deudor molesto que pide no ser llamado (2026-11-11)

Prueba sin API: Claude Opus 5.5 hace de agente siguiendo `backend/src/cobranza/application/prompts/agent_system_prompt.md` y llama las herramientas reales contra PostgreSQL (datos simulados). El desarrollador hace de deudora. Opus no es Haiku 5.5: esta prueba revisa el diseño (prompt, herramientas y reglas), no el comportamiento del modelo de producción.

- **Escenario:** llamada saliente a Jane Carter (ACC-T001). La deudora está molesta y pide que no la llamen más.
- **Reglas que se prueban (Función 7):** si el deudor pide no ser llamado, `mark_do_not_call` lo marca (`debtors.do_not_call`, todas sus cuentas) y cierra la llamada como `do_not_call`; la marca solo la quita una persona. Supuestos vigentes: en salientes, "no llamar" no exige verificar identidad; en entrantes, sí. El prompt pide no discutir, no presionar y ofrecer una persona si el deudor está molesto.
- **Flujo de saludo:** el del pedido D2 (simulación 3).

Etiquetas: **[Prompt]** instrucciones del agente, **[Backend]** código o herramientas, **[Negocio]** lo decide el jefe, **[Legal]** lo revisa un abogado.

## Fase 1: saludo

**Agente:** "Hi, may I speak with Jane Carter, please?"

Herramientas: ninguna (`StartCall` abrió la llamada saliente con la cuenta ACC-T001).

## Fase 2: la deudora contesta molesta

**Deudora:** "They're talking to her, they keep calling me constantly - it's so annoying, the sons of bitches."

Herramientas: ninguna. No hay consentimiento de grabación ni pidió explícitamente que no la llamen.

**Agente:** "I'm sorry for the inconvenience, Ms. Carter, I'll keep this short. I'm a virtual assistant with Lakeside Recovery Services, and this call is recorded for quality and compliance purposes. Is that okay with you?"

Observaciones:
- [Prompt] El agente no reaccionó al insulto, se disculpó y prometió ser breve. El prompt dice "never argue" pero no dice cómo tratar insultos. Propuesta: "If the debtor is rude or uses profanity, stay calm and polite, do not comment on it; if it continues, offer a representative or end the call politely."
- [Prompt] **"They keep calling me constantly" no es lo mismo que "stop calling me".** Es una queja, no un pedido. El agente no marcó "no llamar" ni lo ofreció: ofrecerlo por iniciativa propia es una decisión de negocio (ver abajo). Un modelo pequeño podría interpretarlo como pedido y llamar a `mark_do_not_call` de inmediato.
- [Negocio] ¿El agente debe ofrecer "no llamar" cuando el deudor se queja de las llamadas, o solo marcarlo si lo pide claramente? ¿Ofrecer primero otra forma de contacto (SMS, correo, horario preferido)?
- [Legal] **Queja por exceso de llamadas.** La Reg F presume acoso con más de 7 intentos en 7 días por deuda. Si la deudora dice que la llaman "constantly", hay que revisar cuántas llamadas recibió (del agente y de los cobradores). Hoy el sistema no lleva esa cuenta antes de llamar (pendiente de la sección "Para todo el proyecto" del README).

## Fase 3: pide no ser llamada, amenaza y cuelga

**Deudora:** "Please do not call me again or I will send you my husband to blow your head off motherfuckers." (cuelga)

| Herramienta | Entrada | Respuesta del backend |
| --- | --- | --- |
| `mark_do_not_call` | `{}` | `{"recorded": true, "next_step": "Confirm politely that they will not be called again and say goodbye."}` |

**Agente:** no habla: la deudora ya colgó.

Lo guardado en la base:

| Dato | Valor |
| --- | --- |
| `calls.outcome` | `do_not_call` |
| `calls.recording_consent` | vacío (no respondió) |
| `calls.identity_verified` | `false` |
| `debtors.do_not_call` (TEST-001) | `true` |
| `accounts.status` (ACC-T001) | `NSF` (sin cambios) |

Observaciones:
- La regla funcionó: en una saliente, "no llamar" se guarda sin verificar identidad (supuesto vigente) y la llamada se cierra como `do_not_call`. La marca vale para todas las cuentas de la deudora.
- [Backend] **Riesgo encontrado: si el deudor cuelga, el pedido de "no llamar" se puede perder.** En el simulador el agente alcanzó a llamar `mark_do_not_call`. En una llamada real, al colgar, `AgentSession.hang_up()` le dice al modelo "Call end_call with the outcome that fits best", y `end_call` no acepta `do_not_call` (ni `dispute`): esos resultados solo los ponen sus propias herramientas. Si el modelo obedece literalmente, cierra como `callback_requested` y **la deudora vuelve a recibir llamadas después de pedir que no la llamen**. Además, si el modelo no responde, el respaldo es `callback_requested`. Corrección propuesta: que el aviso de cuelgue diga "If the caller asked not to be called again, call mark_do_not_call; if they disputed the debt, call record_dispute; otherwise call end_call", y una prueba con un modelo guionado que cuelga justo después del pedido.
- [Legal] Volver a llamar a quien pidió que no lo llamen es justo lo que la ley de cobranzas busca evitar (la FDCPA obliga a dejar de comunicarse si el deudor lo pide por escrito, y llamar después de un pedido verbal es un riesgo de acoso). El riesgo anterior es prioritario.
- [Negocio] **Amenaza de violencia.** El sistema no tiene cómo marcarla: no hay campo ni resultado para "amenaza". Solo quedaría en el resumen de la IA. ¿Qué protocolo sigue la empresa (avisar a un supervisor, marcar la cuenta, no volver a contactar por teléfono)?
- [Backend] Con la API real, el resumen de esta llamada incluiría la amenaza y las groserías. Hay que decidir si el resumen las cita textual o las describe ("the debtor used threatening language").
- [Negocio] La marca de "no llamar" la quita solo una persona. ¿Sigue la cobranza por otro medio (carta, SMS, correo) o se detiene? La deuda sigue existiendo (USD 485, cuenta en `NSF`).
- [Prompt] El `next_step` pide "Confirm politely… and say goodbye", pero la deudora ya colgó. El agente no debe hablar a una línea muerta; el `next_step` debería contemplarlo ("if the caller is still on the line").

## Resumen de pendientes de esta simulación

| # | Tipo | Pendiente |
| --- | --- | --- |
| 1 | Backend | **Riesgo:** al colgar, el pedido de "no llamar" o la disputa se pueden perder (`hang_up` manda usar `end_call`). Corregir el aviso de cuelgue y agregar una prueba |
| 2 | Legal | Volver a llamar a quien pidió no ser llamado |
| 3 | Negocio | Protocolo para amenazas de violencia y dónde se registran |
| 4 | Negocio | ¿Se ofrece "no llamar" u otro medio de contacto cuando el deudor se queja de las llamadas? |
| 5 | Negocio | Después de "no llamar", ¿la cobranza sigue por otro medio? |
| 6 | Prompt | Cómo tratar insultos sin discutir; cuándo ofrecer una persona o cerrar |
| 7 | Prompt | Distinguir la queja ("they keep calling me") del pedido ("don't call me again") |
| 8 | Backend | Cómo se resume una llamada con amenazas e insultos |
| 9 | Prompt | `next_step` de `mark_do_not_call` cuando el deudor ya colgó |
| 10 | Legal | Contar las llamadas por deudor (Reg F, 7 en 7 días) antes de llamar |
