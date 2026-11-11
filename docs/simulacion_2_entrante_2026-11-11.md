# Simulación 2: llamada entrante (2026-11-11)

Prueba sin API: Claude Opus 5.5 hace de agente siguiendo `backend/src/cobranza/application/prompts/agent_system_prompt.md` y llama las herramientas reales contra PostgreSQL (datos simulados). El desarrollador hace de deudor. Opus no es Haiku 5.5: esta prueba revisa el diseño (prompt, herramientas y reglas), no el comportamiento del modelo de producción.

- **Escenario:** el deudor llama porque recibió un mensaje de texto que decía que su pago rebotó.
- **Teléfono que llama:** +13055550001 (TEST-001, Jane Carter, ACC-T001, saldo USD 485).
- **call_id:** `68d90795-1c44-4cb3-b654-bedc8752efda`

Cómo leer cada fase: lo que dijo cada parte, las herramientas con su entrada y lo que devolvió el backend, y las observaciones. Las observaciones marcan **[Prompt]** si falta o sobra algo en el prompt, **[Backend]** si es del código o de las herramientas, **[Negocio]** si lo tiene que decidir el jefe y **[Legal]** si lo debe revisar un abogado.

## Fase 1: saludo y grabación

**Agente:** "Thank you for calling Lakeside Recovery Services, you are speaking with a virtual assistant. This call is recorded for quality and compliance purposes. Is that okay with you?"

Herramientas: ninguna todavía (la llamada la abre `StartCall` antes del saludo).

Observaciones:
- [Prompt] El saludo ya incluye "virtual assistant" (ajuste 1 de la simulación 1). El prompt actual todavía no lo pide; se aplicó aquí para no repetir el problema.

**Deudor:** "Hello, thank you very much for your response. I saw a message stating that my payment was returned; could I know the reasons why?"

**Agente:** "Of course, I can help you with that. First, is it okay with you that this call is recorded?"

Herramientas: ninguna. El deudor no respondió a la pregunta de la grabación; sin un "sí" explícito no se llama a `record_recording_consent`.

Observaciones:
- [Prompt] Segunda vez (también en la simulación 1) que el deudor ignora la pregunta de la grabación y pasa a su tema. El prompt debería decir: si el deudor no responde a la grabación, reconocer su pregunta en pocas palabras y volver a pedir el permiso, sin hablar todavía de la cuenta.
- [Backend] El deudor pregunta **por qué** rebotó el pago. La base tiene `nsf_return_code` (R01 = fondos insuficientes), pero `get_account_details` no lo devuelve: el agente no podrá explicar el motivo. Ver fase 3.

**Deudor:** "Yes, that's fine."

Herramienta:

| Herramienta | Entrada | Respuesta del backend |
| --- | --- | --- |
| `record_recording_consent` | `{"accepted": true}` | `{"recorded": true, "next_step": "Confirm who you are speaking with and verify identity."}` |

Observaciones:
- Sin problemas: el consentimiento queda guardado en `calls.recording_consent` antes de hablar de nada más.

## Fase 2: verificación de identidad

**Agente:** "Thank you. To protect your privacy, I first need to verify your identity. Could you please tell me your full name, the last four digits of your Social Security number, and your date of birth?"

Observaciones:
- [Negocio] Se pide nombre completo + últimos 4 del SSN + fecha de nacimiento, como está construido hoy. El jefe pidió quitar el nombre y que el agente lea los datos para que el deudor confirme; sigue pendiente de revisar (ver `notas_simulacion_2026-11-11.md`, pedido J1).
- [Prompt] En una entrante, el deudor ya sabe por qué llama. "To protect your privacy" explica por qué se piden los datos sin mencionar la deuda; conviene dejar esta frase fija en el prompt.

**Deudor:** "Jane Carter, 1234, March 14, 1985"

Herramientas:

| Herramienta | Entrada | Respuesta del backend |
| --- | --- | --- |
| `verify_identity` | `{"full_name": "Jane Carter", "ssn_last4": "1234", "date_of_birth": "1985-03-14"}` | `{"outcome": "verified", "next_step": "Say this sentence exactly, before anything else: \"This is an attempt to collect a debt...\" Then call get_account_details."}` |
| `get_account_details` | `{}` | Lakeside Auto Finance, cuenta terminada en 4821, saldo `$485.00`, mínimo parcial `$48.50`, pago devuelto `$450.00` + cargo `$35.00` el `2026-10-10` |

Observaciones:
- Verificación correcta al primer intento.

## Fase 3: aviso legal y la deuda

**Agente:** "Thank you, Ms. Carter. This is an attempt to collect a debt, and any information obtained will be used for that purpose. This communication is from a debt collector. Your payment of four hundred fifty dollars to Lakeside Auto Finance, on the account ending in four eight two one, was returned by your bank on October tenth. I don't have the specific reason your bank gave, but with the thirty-five dollar returned payment fee, the balance is now four hundred eighty-five dollars. Would you like to take care of it today?"

Observaciones:
- [Backend] **El agente no puede responder la pregunta del deudor ("why was it returned?").** La base guarda `nsf_return_code` (R01), pero `get_account_details` no lo entrega. Propuesta: que la herramienta devuelva el motivo en palabras sencillas según el código ACH (R01 "insufficient funds", R02 "account closed", R03 "no account found", etc.). Así el agente responde sin inventar.
- [Prompt] Se aplicó el ajuste 4 de la simulación 1: aviso legal y deuda en este turno y la oferta en el siguiente, con "Would you like to take care of it today?". Pero el `next_step` de `get_account_details` dice "then call propose_offer"; el agente se desvió a propósito. Si se adopta el ajuste, hay que cambiar también ese `next_step` en `agent_tools.py`.
- [Prompt] El turno sigue siendo largo para voz (aviso de 2 frases + deuda + pregunta). El aviso legal es fijo, así que lo que se puede acortar es la explicación de la deuda.
- [Legal] El aviso "This communication is from a debt collector" sigue completo (pedido D1 de quitarlo, pendiente de abogado).

## Fase 4: negociación

**Deudor:** "Right!! I had forgotten about this. Is it possible for me to pay tomorrow? I'll be receiving my paycheck from work tomorrow - could you give me a call then?"

Herramienta:

| Herramienta | Entrada | Respuesta del backend |
| --- | --- | --- |
| `propose_offer` | `{"account_ref": "ACC-T001", "first_payment_date": "2026-11-12"}` | Oferta 1, pago total: `$485.00` el jueves 2026-11-12 (`proposal_id: P8a673f6b`) |

**Agente:** "Yes, you can pay tomorrow. I can set it up right now so you don't need another call: the full four hundred eighty-five dollars on Thursday, November twelfth. Would you like me to do that?"

Observaciones:
- El deudor elige la fecha del primer pago y el sistema la acepta (está dentro de los 8 días). Es el caso ideal: un deudor que olvidó el pago y puede pagar todo.
- [Prompt] **Situación no prevista: el deudor pide que lo llamen mañana.** El agente prefirió dejar el pago agendado ya, para no perder el compromiso ni gastar otra llamada. El prompt no dice qué hacer cuando el deudor pide una devolución de llamada pero ya puede comprometerse; conviene decir "si el deudor puede fijar una fecha de pago dentro de los 8 días, agenda el pago en vez de una nueva llamada".
- [Backend] Si el deudor insiste en que lo llamen, solo existe `end_call` con `callback_requested`: **no se guarda a qué hora ni qué día** quiere la llamada. Haría falta un campo o una herramienta para agendar la devolución de llamada (fecha, hora y zona horaria).
- [Legal] Cada llamada de vuelta cuenta para el límite de 7 llamadas en 7 días (Reg F). Agendar el pago en lugar de llamar de nuevo también ayuda con ese límite.

**Deudor:** "How would that work? Does that mean I won't be receiving any more calls starting tomorrow? And how would I make the payment, then? Will you send me a link?"

Herramientas: ninguna. El agente no tiene información para responder y no la inventa.

**Agente:** "Good questions. Once it's set up, your account will show that you're paying the full amount tomorrow, so you won't need another call to arrange it, although you may still get a reminder. The payment itself goes through our secure payment system, but I don't have the details of how the payment instructions are sent, so I'd rather not guess. I can set up tomorrow's payment now and then transfer you to a representative who can confirm how to pay. Would that work for you?"

Observaciones:
- [Negocio] **Pregunta clave que el sistema no sabe responder: ¿cómo paga el deudor un pago agendado?** Hoy el único medio previsto es transferir al IVR PCI durante la llamada (Función 6, bloqueada). Para un pago a futuro no hay nada definido: ¿link por SMS?, ¿correo?, ¿débito automático?, ¿el deudor vuelve a llamar? Hay que decidirlo; después el agente tendrá una respuesta fija.
- [Negocio] **"¿Me van a dejar de llamar?"** Según lo decidido, al quedar en `PTP` termina el trabajo del agente, pero un cobrador hace las llamadas de recordatorio. Falta decidir qué se le promete al deudor: ¿recibe recordatorio?, ¿por qué medio?, ¿y si no paga ese día?
- [Backend] No hay herramienta para enviar un link de pago ni un mensaje de confirmación. Si se decide el link por SMS, haría falta una herramienta (`send_payment_link`) y un proveedor de SMS (Telnyx ya lo ofrece).
- [Prompt] El `next_step` de `record_offer_response` le hace decir al agente "they will receive the payment instructions", algo que hoy no existe (ver nota 14 de la simulación 1). El agente aquí evitó prometerlo y ofreció pasar a una persona.
- [Prompt] Ofrecer una persona solo para explicar cómo pagar agrega costo a una llamada que el agente casi resolvió. Cuando exista el medio de pago, esta transferencia sobra.

**Deudor:** "In other words, will someone else call me tomorrow and charge me right then and there during the call?"

Herramientas: ninguna.

**Agente:** "I understand why you're asking, and I don't want to promise something I can't confirm. What I can do is note that you'll pay the full four hundred eighty-five dollars tomorrow, and a representative can tell you exactly how the payment works. Would you like me to set that up and transfer you now?"

Observaciones:
- [Negocio] **El deudor insiste porque el agente no tiene la respuesta.** Dos turnos seguidos sobre lo mismo: la falta de un medio de pago definido no solo es un hueco técnico, también genera desconfianza ("¿me van a cobrar en una llamada?"). En voz, un deudor así cuelga o pide una persona.
- [Prompt] El agente evitó dos respuestas tentadoras pero inventadas: "no se le cobrará nada automáticamente" (no sabe si el acreedor tiene autorización de débito) y "le enviaremos un link" (no existe). Con Haiku y esfuerzo bajo, este es un punto de riesgo de inventar: conviene una regla explícita en el prompt sobre qué decir de los medios de pago mientras no estén definidos.
- [Prompt] Riesgo de bucle: si el deudor sigue preguntando, el agente no tiene nada nuevo que decir. El prompt debería indicar que, después de una segunda pregunta sin respuesta, se ofrezca la persona y se deje de repetir.

## Fase 5: acuerdo y transferencia

**Deudor:** "Yes, please set it up and transfer me. I need to handle this"

Herramientas:

| Herramienta | Entrada | Respuesta del backend |
| --- | --- | --- |
| `record_offer_response` | `{"proposal_id": "P8a673f6b", "accepted": true}` | Acuerdo creado (`arrangement_id: 70b182b7-…`): `$485.00` el 2026-11-12. `next_step`: "…say they will receive the payment instructions. Then call end_call with outcome arrangement_made." |
| `transfer_to_human` | `{"reason": "Arrangement made for full payment on 2026-11-12; debtor needs to know how to make the payment."}` | `{"transferring": true, "next_step": "Tell them you are transferring them to a representative now."}` |

**Agente:** "Done, Ms. Carter: the full four hundred eighty-five dollars is set for Thursday, November twelfth. Thank you for taking care of it. I'm transferring you to a representative now who will explain how to make the payment."

Observaciones:
- [Backend] **El resultado de la llamada esconde el acuerdo.** Una llamada tiene un solo `outcome`; quedó `transferred_to_human` aunque sí hubo acuerdo. En un reporte de "llamadas con acuerdo" esta llamada no aparecería (el acuerdo sí está en `payment_arrangements`). Opciones: un resultado `arrangement_made_and_transferred`, un campo aparte `transferred` en `calls`, o contar los acuerdos desde `payment_arrangements` y no desde `calls.outcome`.
- [Backend] El `reason` de `transfer_to_human` no se guarda en la base: la persona que recibe la llamada no sabe por qué se la pasaron. Debería quedar en `calls` (o enviarse a la telefonía) para que el cobrador no le vuelva a preguntar todo al deudor.
- [Prompt] El `next_step` de `record_offer_response` manda decir "they will receive the payment instructions" y cerrar con `end_call`; el agente no siguió ninguna de las dos cosas porque el deudor pidió la transferencia. El `next_step` debería contemplar ese caso.

## Resultado

Lo guardado en la base, consultado al terminar:

| Dato | Valor |
| --- | --- |
| Cuenta ACC-T001 | `PTP` |
| Acuerdo | `full`, `active`, `$485.00` el 2026-11-12 |
| Llamada | `transferred_to_human`, grabación aceptada, identidad verificada, 1 intento de verificación, con resumen (de prueba) |

Ninguna herramienta devolvió error. El backend aplicó todas las reglas: fecha del primer pago dentro de 8 días, saldo completo y cuenta a `PTP`.

## Resumen de pendientes de esta simulación

| # | Tipo | Pendiente |
| --- | --- | --- |
| 1 | Negocio | Cómo paga el deudor un pago agendado (link por SMS, correo, débito, volver a llamar). Es la pregunta que más fricción causó |
| 2 | Negocio | Qué se le promete al deudor después de `PTP`: ¿recordatorio?, ¿por qué medio?, ¿qué pasa si no paga ese día? |
| 3 | Backend | `get_account_details` debe devolver el motivo del rebote en palabras sencillas (según `nsf_return_code`) |
| 4 | Backend | Guardar fecha y hora de una devolución de llamada (`callback_requested` no las guarda) |
| 5 | Backend | Que el resultado de la llamada no esconda un acuerdo cuando además se transfiere |
| 6 | Backend | Guardar el motivo de `transfer_to_human` para la persona que recibe la llamada |
| 7 | Backend | Herramienta para enviar link de pago o confirmación, si el negocio lo decide |
| 8 | Prompt | Volver a pedir la grabación si el deudor la ignora; frase fija "To protect your privacy" para pedir los datos |
| 9 | Prompt | Aviso y deuda en un turno, oferta en el siguiente (y ajustar el `next_step` de `get_account_details`) |
| 10 | Prompt | Si el deudor pide que lo llamen pero puede fijar una fecha dentro de 8 días, agendar el pago |
| 11 | Prompt | Regla sobre qué decir de los medios de pago mientras no estén definidos; no inventar ("no se le cobrará nada", "le enviaremos un link") |
| 12 | Prompt | Si una pregunta se repite sin respuesta, ofrecer una persona en vez de dar vueltas |
| 13 | Prompt | `next_step` de `record_offer_response` cuando el deudor pide transferencia después del acuerdo |
| 14 | Legal | Llamadas de vuelta y recordatorios cuentan para el límite de 7 en 7 días (Reg F) |
