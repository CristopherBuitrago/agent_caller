# Simulación 4: disputa, "ya pagué, fue error del banco" (2026-11-11)

Prueba sin API: Claude Opus 5.5 hace de agente siguiendo `backend/src/cobranza/application/prompts/agent_system_prompt.md` y llama las herramientas reales contra PostgreSQL (datos simulados). El desarrollador hace de deudora. Opus no es Haiku 5.5: esta prueba revisa el diseño (prompt, herramientas y reglas), no el comportamiento del modelo de producción.

- **Escenario:** llamada saliente a Jane Carter (ACC-T001, saldo USD 485). La deudora dice que ya pagó y que el rebote fue un error del banco.
- **Regla que se prueba (Función 7):** "Yo sí pagué" o "fue error del banco" cuentan como disputa: se marca la cuenta (`accounts.is_disputed`), la llamada se cierra como `dispute` y pasa a una persona. El agente deja de cobrar.
- **Flujo de saludo usado:** la propuesta intermedia del pedido D2 (simulación 3): el saludo solo pregunta por Jane; cuando confirma que es ella, aviso de grabación; después, verificación.

Etiquetas: **[Prompt]** instrucciones del agente, **[Backend]** código o herramientas, **[Negocio]** lo decide el jefe, **[Legal]** lo revisa un abogado.

## Fase 1: saludo

**Agente:** "Hi, may I speak with Jane Carter, please?"

Herramientas: ninguna (`StartCall` abrió la llamada saliente con la cuenta ACC-T001).

Observaciones:
- [Prompt] Saludo según el pedido D2: sin nombre de empresa, sin aviso de grabación y sin motivo. Si contesta un tercero, no se le dice nada.
- [Legal] Sin el nombre de la empresa en el saludo, la persona no sabe quién llama. Si pregunta, el agente debe identificarse (la FDCPA exige que un cobrador se identifique al comunicarse); falta definir con el abogado qué nombre se dice y en qué momento.

## Fase 2: confirma que es Jane y pregunta quién llama

**Deudora:** "You're speaking with her; with whom do I have the pleasure of speaking?"

Herramientas: ninguna. Todavía no hay consentimiento de grabación.

**Agente:** "Thank you, Ms. Carter. I'm a virtual assistant with Lakeside Recovery Services. Before we continue, this call is recorded for quality and compliance purposes. Is that okay with you?"

Observaciones:
- [Prompt] Con el flujo D2, la persona dice "soy ella" y en el mismo turno el agente se identifica y da el aviso de grabación. Funciona en un solo turno, sin vueltas extra.
- [Legal] El agente dice el nombre de la empresa a alguien que *dice* ser Jane pero no está verificado. Es lo esperado (el cobrador debe identificarse), pero si quien contesta miente, ya sabe que llama una empresa de "Recovery". Riesgo bajo; lo confirma el abogado junto con el nombre real de la empresa.
- [Backend] Con el flujo D2, la telefonía tendría que empezar a grabar recién después del "sí" del siguiente turno. Hoy no hay una acción en el backend para "empezar a grabar"; se agregaría al integrar la telefonía (`record_recording_consent` sería el punto natural para pedirlo).

## Fase 3: acepta la grabación y pregunta el motivo

**Deudora:** "That sounds fine; what is the purpose of the call?"

Herramienta:

| Herramienta | Entrada | Respuesta del backend |
| --- | --- | --- |
| `record_recording_consent` | `{"accepted": true}` | `{"recorded": true, "next_step": "Confirm who you are speaking with and verify identity."}` |

**Agente:** "Thank you. I can share the reason once I confirm I'm speaking with the right person. To protect your privacy, could you please tell me your full name, the last four digits of your Social Security number, and your date of birth?"

Observaciones:
- [Prompt] Se usaron las dos frases fijas propuestas en la simulación 1 (ajuste 2) y en la 2 (fase 2): "I can share the reason once I confirm I'm speaking with the right person" y "To protect your privacy". Responden a "what is the purpose of the call?" sin revelar la deuda antes de verificar.
- [Prompt] "That sounds fine" se tomó como un sí a la grabación. Es claro, pero conviene que el prompt diga qué cuenta como aceptación ("yes", "okay", "that's fine") y que ante una respuesta ambigua se vuelva a preguntar.

## Fase 4: verificación, aviso legal y la deuda

**Deudora:** "Jane Carter, 1234, March 14, 1985"

Herramientas:

| Herramienta | Entrada | Respuesta del backend |
| --- | --- | --- |
| `verify_identity` | `{"full_name": "Jane Carter", "ssn_last4": "1234", "date_of_birth": "1985-03-14"}` | `{"outcome": "verified", ...}` |
| `get_account_details` | `{}` | Lakeside Auto Finance, saldo `$485.00`, pago devuelto `$450.00` + cargo `$35.00` el `2026-10-10` |

**Agente:** "Thank you, Ms. Carter. This is an attempt to collect a debt, and any information obtained will be used for that purpose. This communication is from a debt collector. I'm calling because your payment of four hundred fifty dollars to Lakeside Auto Finance was returned by your bank on October tenth, and with the thirty-five dollar returned payment fee the balance is four hundred eighty-five dollars. Would you like to take care of it today?"

Observaciones:
- Verificación al primer intento. Aviso legal completo, deuda en el mismo turno y la oferta para el siguiente (ajuste 4 de la simulación 1).
- [Prompt] Para que el deudor pueda decir "yo ya pagué", el agente le da la fecha y el monto del pago devuelto. Es justo la información que necesita para reconocer o disputar el cobro.

## Fase 5: la disputa

**Deudora:** "I already paid that; it was the bank's fault, not mine."

Herramienta:

| Herramienta | Entrada | Respuesta del backend |
| --- | --- | --- |
| `record_dispute` | `{"account_ref": "ACC-T001"}` | `{"recorded": true, "next_step": "Tell them a representative will review it, thank them and say goodbye. Do not ask for any payment."}` |

**Agente:** "I understand, Ms. Carter, and I'm sorry for the confusion. I've noted that you dispute this balance, and a representative will review it. I won't ask you for any payment today. Thank you for your time, and have a good day."

Lo guardado en la base:

| Dato | Valor |
| --- | --- |
| `accounts.is_disputed` (ACC-T001) | `true` |
| `accounts.status` | `NSF` (no cambia) |
| `calls.outcome` | `dispute` |
| Acuerdos creados | 0 |

Observaciones:
- La regla de la Función 7 funcionó: las dos frases ("I already paid", "the bank's fault") son disputa, la cuenta quedó marcada, la llamada se cerró como `dispute` y no se pidió ningún pago. A diferencia de la simulación 1 ("I tried to pay, I'm not sure what happened"), aquí no hay duda.
- [Backend] **La disputa se guarda sin ningún detalle.** Solo queda `is_disputed = true`. La persona que la revise no sabe cuándo dice la deudora que pagó, por qué medio ni con qué número de confirmación, y tendrá que llamarla de nuevo para preguntarlo. Propuesta: que `record_dispute` reciba campos opcionales (`claimed_payment_date`, `payment_method`, `confirmation_number`, `notes`) y guardarlos en una tabla `disputes` (requiere aprobar el modelo de datos).
- [Prompt] **El agente cerró sin preguntar nada,** porque `record_dispute` termina la llamada en el mismo momento y el `next_step` solo pide despedirse. Propuesta: antes de llamar a `record_dispute`, preguntar con amabilidad "When did you make the payment, and do you have a confirmation number?". Así la disputa llega completa a la persona.
- [Negocio] **¿Qué pasa con el cobro después de una disputa?** Hoy el supuesto vigente es que una disputa impide cobrar y que solo una persona quita la marca. Falta decidir: ¿quién la revisa?, ¿en cuánto tiempo?, ¿se le avisa a la deudora el resultado?, ¿por qué medio?
- [Negocio] **El agente no sabe si el pago realmente entró.** Si la empresa puede consultar los pagos recibidos (por fecha o referencia), el agente podría confirmar en la misma llamada si el pago existe. Hoy no hay esa consulta.
- [Prompt] El agente dijo "I won't ask you for any payment today" y no "you won't be contacted again": no sabe qué hará la persona que revise la disputa y no lo promete.
- [Legal] La FDCPA y la Reg F obligan al cobrador a dejar de cobrar una deuda disputada (si se disputa dentro del plazo de validación) hasta enviar la verificación de la deuda. Falta definir con el abogado el plazo, el formato de esa respuesta y si una disputa por teléfono basta o debe ser por escrito.
- [Backend] El resumen de la llamada es lo único que hoy guarda lo que dijo la deudora. Con la API real, el resumen diría "Jane Carter said she already paid…", pero un texto libre no reemplaza los campos de la disputa.

## Resumen de pendientes de esta simulación

| # | Tipo | Pendiente |
| --- | --- | --- |
| 1 | Backend | Guardar los detalles de la disputa (fecha, medio, número de confirmación, notas) |
| 2 | Prompt | Preguntar esos detalles antes de `record_dispute`, que cierra la llamada |
| 3 | Negocio | Quién revisa la disputa, en cuánto tiempo, y cómo se le informa el resultado a la deudora |
| 4 | Negocio | ¿Se puede consultar si el pago entró? El agente podría confirmarlo en la llamada |
| 5 | Prompt | Qué cuenta como aceptación de la grabación ("yes", "okay", "that sounds fine") |
| 6 | Backend | Acción para empezar a grabar después del "sí" (flujo D2), al integrar la telefonía |
| 7 | Legal | Plazos y formato de la verificación de la deuda disputada; si basta una disputa por teléfono |
| 8 | Legal | Qué nombre de empresa se dice al identificarse y en qué momento |
