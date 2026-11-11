# Simulación 6: verificación fallida dos veces (2026-11-11)

Prueba sin API: Claude Opus 5.5 hace de agente siguiendo `backend/src/cobranza/application/prompts/agent_system_prompt.md` y llama las herramientas reales contra PostgreSQL (datos simulados). El desarrollador hace de la persona que contesta. Opus no es Haiku 5.5: esta prueba revisa el diseño (prompt, herramientas y reglas), no el comportamiento del modelo de producción.

- **Escenario:** llamada saliente a Jane Carter (ACC-T001). Quien contesta no logra verificar su identidad dos veces.
- **Reglas que se prueban (Función 2):** se verifica con nombre completo + últimos 4 del SSN + fecha de nacimiento; nunca se dice qué dato falló; si el nombre no coincide, se pide deletrear el apellido sin contar el intento; máximo 2 fallos por llamada y después se cierra sin revelar la deuda; 5 fallos en 24 horas bloquean la verificación y pasan a una persona.
- **Flujo de saludo:** el del pedido D2 (simulación 3): solo se pregunta por Jane; cuando confirma que es ella, aviso de grabación; después, verificación.

Etiquetas: **[Prompt]** instrucciones del agente, **[Backend]** código o herramientas, **[Negocio]** lo decide el jefe, **[Legal]** lo revisa un abogado.

## Fase 1: saludo

**Agente:** "Hi, may I speak with Jane Carter, please?"

Herramientas: ninguna (`StartCall` abrió la llamada saliente con la cuenta ACC-T001).

## Fase 2: dice ser Jane y pregunta quién llama

**Persona:** "Good afternoon. You're speaking with her - may I ask who I have the pleasure of speaking with?"

Herramientas: ninguna.

**Agente:** "Good afternoon, Ms. Carter. I'm a virtual assistant with Lakeside Recovery Services. Before we continue, this call is recorded for quality and compliance purposes. Is that okay with you?"

Observaciones:
- Mismo turno que en la simulación 4: identificación y aviso de grabación juntos. Se repite la nota [Legal] de esa simulación: el nombre de la empresa se dice antes de verificar.

## Fase 3: acepta la grabación

**Persona:** "Yes, that's fine."

| Herramienta | Entrada | Respuesta del backend |
| --- | --- | --- |
| `record_recording_consent` | `{"accepted": true}` | `{"recorded": true, ...}` |

**Agente:** "Thank you. To protect your privacy, could you please tell me your full name, the last four digits of your Social Security number, and your date of birth?"

## Fase 4: primer intento fallido

**Persona:** "Jane Carter, 1243, March 14, 1985" (SSN equivocado: el correcto es 1234)

| Herramienta | Entrada | Respuesta del backend |
| --- | --- | --- |
| `verify_identity` | `{"full_name": "Jane Carter", "ssn_last4": "1243", "date_of_birth": "1985-03-14"}` | `{"outcome": "failed", "next_step": "Say the information did not match our records, without saying which item, and ask them to repeat it. Then call verify_identity again."}` |

**Agente:** "I'm sorry, that information doesn't match our records. Could you please repeat your full name, the last four digits of your Social Security number, and your date of birth?"

Observaciones:
- El agente no dijo qué dato falló, como exige la regla.
- [Backend] La respuesta no dice cuántos intentos quedan. El agente no sabe que el próximo fallo cierra la llamada, así que no puede avisar ("please double-check, this is the last try"). Propuesta: devolver `attempts_left` en `verify_identity`.
- [Prompt] Pedir "repeat" los tres datos: si la persona se equivocó por un dígito traspuesto (1243 en vez de 1234), un "please double-check the numbers" ayuda más que "repeat", sin revelar cuál falló.

## Fase 5: segundo intento fallido y cierre

**Persona:** "Jane Carter, 1234, March 15, 1985" (fecha equivocada: la correcta es March 14)

| Herramienta | Entrada | Respuesta del backend |
| --- | --- | --- |
| `verify_identity` | `{"full_name": "Jane Carter", "ssn_last4": "1234", "date_of_birth": "1985-03-15"}` | `{"outcome": "max_attempts_reached", "next_step": "Say you could not verify their identity. Do not mention any debt. Call end_call with outcome verification_failed."}` |
| `end_call` | `{"outcome": "verification_failed"}` | `{"ended": true, ...}` |

**Agente:** "I'm sorry, I wasn't able to verify your identity, so I can't continue with this call. Thank you for your time, and have a good afternoon."

Lo guardado en la base:

| Campo de `calls` | Valor |
| --- | --- |
| `outcome` | `verification_failed` |
| `recording_consent` | `true` |
| `identity_verified` | `false` |
| `verification_attempts` | 2 |

Observaciones:
- Las reglas funcionaron: 2 fallos cierran la llamada, el agente no dijo qué dato falló y no mencionó la deuda. Aunque la IA hubiera querido seguir, `get_account_details` y las ofertas devuelven `identity_not_verified`.
- [Negocio] **Si era la verdadera Jane, se queda sin salida.** Es una llamada saliente: no sabe por qué la llamaron ni cómo resolverlo. El agente no puede darle un número para devolver la llamada ni pasarla a una persona (el `next_step` manda cerrar). Preguntas para el jefe: ¿se le da un número de contacto?, ¿se le ofrece una persona que verifique de otra forma?, ¿se vuelve a llamar otro día?
- [Prompt] Un cierre más útil, sin revelar nada: "If you'd like, you can call us back at [número] and we'll be happy to help." Depende de la respuesta del jefe.
- [Backend] El bloqueo de 24 horas (5 fallos) cuenta los fallos de todas las llamadas. Aquí van 2; si la verdadera Jane devuelve la llamada, le quedan 3 intentos ese día. Funciona como se diseñó; solo se anota para recordar que un impostor con 3 llamadas más bloquea a la verdadera deudora por 24 horas.
- [Backend] Esta llamada también genera un resumen con IA de una conversación con alguien no verificado (mismo punto de la simulación 3). El resumen no debe mencionar la deuda.
- [Legal] Cada llamada fallida cuenta para el límite de 7 llamadas en 7 días (Reg F), aunque no se haya hablado de la deuda.

## Resumen de pendientes de esta simulación

| # | Tipo | Pendiente |
| --- | --- | --- |
| 1 | Backend | `verify_identity` debe devolver los intentos que quedan (`attempts_left`) |
| 2 | Prompt | Tras un fallo, "please double-check the numbers" en vez de solo "repeat" |
| 3 | Negocio | Qué se le ofrece a quien no logra verificarse en una saliente: número de contacto, persona o nueva llamada |
| 4 | Prompt | Cierre con número de contacto, según lo que decida el jefe |
| 5 | Backend | Un impostor puede bloquear a la verdadera deudora 24 horas (5 fallos entre varias llamadas); evaluar alertas |
| 6 | Backend / Legal | Resumen con IA de llamadas sin verificar: que no mencione la deuda |
| 7 | Legal | Las llamadas fallidas cuentan para el límite de 7 en 7 días |
