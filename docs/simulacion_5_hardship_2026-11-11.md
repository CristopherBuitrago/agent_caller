# Simulación 5: Hardship Questions completas (2026-11-11)

Prueba sin API: Claude Opus 5.5 hace de agente siguiendo `backend/src/cobranza/application/prompts/agent_system_prompt.md` y llama las herramientas reales contra PostgreSQL (datos simulados). El desarrollador hace de deudora. Opus no es Haiku 5.5: esta prueba revisa el diseño (prompt, herramientas y reglas), no el comportamiento del modelo de producción.

- **Escenario:** llamada entrante de Jane Carter (ACC-T001, saldo USD 485). La deudora no puede con el pago total ni con 2 o 3 cuotas, y pasa por las Hardship Questions.
- **Reglas que se prueban (Funciones 4 y 5):** ofertas en orden (todo de una, 2 cuotas, 3 cuotas); desde la 4.ª oferta el sistema exige las Hardship Questions (`hardship_required`); las 5 preguntas del jefe, una por una y en orden; después, planes de 4 a 10 cuotas; si sigue sin poder pagar, se transfiere a una persona.
- **Las 5 preguntas** (`HARDSHIP_QUESTIONS` en `domain/hardship.py`):
  1. "Can you tell me a little about what happened and when this situation started?"
  2. "Do you expect this to be temporary, or a longer-term change in your income?"
  3. "Is there anyone else in your household who could help out while things stabilize?"
  4. "I understand things are difficult. Is there a partial amount you could put toward this today or on your next pay date?"
  5. "What realistic arrangement could we set for the next 30 or 60 days that you could keep up with comfortably?"

Etiquetas: **[Prompt]** instrucciones del agente, **[Backend]** código o herramientas, **[Negocio]** lo decide el jefe, **[Legal]** lo revisa un abogado.

## Fase 1: saludo

**Agente:** "Thank you for calling Lakeside Recovery Services, you're speaking with a virtual assistant. This call is recorded for quality and compliance purposes. Is that okay with you?"

Herramientas: ninguna (`StartCall` abrió la llamada entrante desde +13055550001).

Observaciones:
- En una entrante quien llama ya sabe a quién llamó, así que el aviso de grabación va en el saludo (el pedido D2 aplica a las salientes, donde puede contestar un tercero).

## Fase 2: acepta la grabación y dice que no puede pagar

**Deudora:** "Yes, that sounds fine; I was calling to say that I can't pay right now and that I need more time."

Herramienta:

| Herramienta | Entrada | Respuesta del backend |
| --- | --- | --- |
| `record_recording_consent` | `{"accepted": true}` | `{"recorded": true, ...}` |

**Agente:** "Thank you for letting us know, I'll do my best to help. To protect your privacy, could you please tell me your full name, the last four digits of your Social Security number, and your date of birth?"

Observaciones:
- [Prompt] La deudora adelanta que no puede pagar antes de verificar. El agente reconoce lo que dijo sin hablar de la cuenta y verifica primero. El prompt no lo cubre, pero la regla general ("verify before saying anything about a debt") alcanza.
- [Negocio] **Primera duda del flujo:** la deudora ya dijo "no puedo pagar ahora". ¿Igual hay que ofrecerle el pago total, luego 2 cuotas y luego 3, antes de las Hardship Questions? Hoy el sistema lo exige. Es lo mismo que la nota 9 de la simulación 1 (ofrecer opciones que el deudor ya descartó alarga la llamada).

## Fase 3: verificación, aviso legal, deuda y oferta 1

**Deudora:** "Jane Carter, 1234, March 14, 1985"

Herramientas:

| Herramienta | Entrada | Respuesta del backend |
| --- | --- | --- |
| `verify_identity` | `{"full_name": "Jane Carter", "ssn_last4": "1234", "date_of_birth": "1985-03-14"}` | `{"outcome": "verified", ...}` |
| `get_account_details` | `{}` | Saldo `$485.00` (pago devuelto `$450.00` + cargo `$35.00`, 2026-10-10) |
| `propose_offer` | `{"account_ref": "ACC-T001"}` | Oferta 1, pago total: `$485.00` el 2026-11-11 (`proposal_id: P6415c53b`) |

**Agente:** "Thank you, Ms. Carter. This is an attempt to collect a debt, and any information obtained will be used for that purpose. This communication is from a debt collector. Your payment of four hundred fifty dollars to Lakeside Auto Finance was returned on October tenth, and with the thirty-five dollar fee the balance is four hundred eighty-five dollars. I understand you need more time; the fastest way to resolve it would be the full amount, and it doesn't have to be today. Would paying it within the next week be possible?"

Observaciones:
- [Prompt] Como la deudora ya pidió tiempo, el agente presentó la oferta 1 en el mismo turno que la deuda (se desvía del ajuste 4, que la deja para el turno siguiente). Tiene sentido cuando el deudor ya planteó su situación: el prompt debería permitirlo.
- [Backend] **El agente sabe que el primer pago puede ser hasta en 8 días, pero la herramienta no se lo dice.** `propose_offer` devuelve la oferta con fecha de hoy y no indica el rango permitido. El prompt dice "the debtor can pick the date of the first payment, within the range the tools give", pero ninguna herramienta da el rango. Aquí el agente lo dijo porque conoce las reglas; Haiku no las conoce. Propuesta: que `propose_offer` devuelva `latest_first_payment_date` (hoy + 8 días).
- [Prompt] "Within the next week" es más claro para voz que "within eight days", pero no es exacto (8 días). Con el campo propuesto, el agente diría la fecha límite real ("by Thursday, November nineteenth").

## Fase 4: rechaza el pago total, oferta 2

**Deudora:** "No, I can't pay the full amount within a week."

Herramientas:

| Herramienta | Entrada | Respuesta del backend |
| --- | --- | --- |
| `record_offer_response` | `{"proposal_id": "P6415c53b", "accepted": false}` | `{"recorded": true, "next_step": "Call propose_offer for the next option."}` |
| `propose_offer` | `{"account_ref": "ACC-T001"}` | Oferta 2: 2 cuotas de `$242.50`, 2026-11-11 y 2026-12-11 (`proposal_id: P78c5c729`) |

**Agente:** "I understand. Another option is two equal monthly payments of two hundred forty-two dollars and fifty cents, the first one today and the second on Friday, December eleventh. Would that work for you?"

Observaciones:
- [Negocio] La primera cuota es hoy. La deudora pidió tiempo; podría poner la primera cuota hasta en 8 días, pero la oferta llega con fecha de hoy y el agente no la movió porque la deudora no dio una fecha. Pregunta para el jefe: ¿la primera cuota debería ofrecerse por defecto en la próxima fecha de pago del deudor, o siempre hoy?

## Fase 5: rechaza 2 cuotas, oferta 3

**Deudora:** "No, two payments is still too much for me."

Herramientas:

| Herramienta | Entrada | Respuesta del backend |
| --- | --- | --- |
| `record_offer_response` | `{"proposal_id": "P78c5c729", "accepted": false}` | `{"recorded": true, ...}` |
| `propose_offer` | `{"account_ref": "ACC-T001"}` | Oferta 3: `$161.68` (2026-11-11), `$161.66` (2026-12-11), `$161.66` (2027-01-11) (`proposal_id: P025073fe`) |

**Agente:** "Okay. I could also set it up in three monthly payments: one hundred sixty-one dollars and sixty-eight cents today, then one hundred sixty-one dollars and sixty-six cents on December eleventh and on January eleventh. Would that be manageable?"

Observaciones:
- [Prompt] **"3 equal monthly payments" no son iguales al centavo:** 485 / 3 no da exacto y la primera cuota lleva 2 centavos más. La herramienta dice "equal" y el agente tiene que decir dos montos distintos. En voz suena largo y confuso. Propuesta: que el prompt permita decir "about one hundred sixty-two dollars a month" y dar los centavos exactos solo al confirmar el acuerdo; o que la herramienta devuelva una frase hablada ya armada (`spoken_summary`).

## Fase 6: rechaza 3 cuotas, el sistema exige las Hardship Questions

**Deudora:** "No, three payments is still too much for me."

Herramientas:

| Herramienta | Entrada | Respuesta del backend |
| --- | --- | --- |
| `record_offer_response` | `{"proposal_id": "P025073fe", "accepted": false}` | `{"recorded": true, ...}` |
| `propose_offer` | `{"account_ref": "ACC-T001"}` | **Error** `hardship_required`: "Before more options, ask the hardship questions one at a time, save the answers with record_hardship_answers, then call propose_offer again." |

**Agente:** "I understand, and I want to find something that really works for you. May I ask you a few quick questions about your situation? First, can you tell me a little about what happened and when this situation started?"

Observaciones:
- La regla funcionó: el backend no deja ofrecer 4 cuotas sin las Hardship Questions, aunque la IA lo intente.
- [Prompt] El agente pidió permiso antes de preguntar ("May I ask you a few quick questions?") y en el mismo turno hizo la pregunta 1. Pedir permiso suaviza el cambio de tema; el prompt no lo pide, pero va con el tono "with empathy".
- [Backend] **Error encontrado: guardar las respuestas de a una borra las anteriores.** El `next_step` no dice si guardar al final o después de cada respuesta, y la documentación dice que `RecordHardshipAssessment` "se puede repetir en la llamada para completarlas". Pero `postgres_hardship_repository.py` hace `ON CONFLICT (call_id) DO UPDATE SET campo = EXCLUDED.campo` para todos los campos: si la segunda llamada solo trae `duration_type`, deja en `NULL` la `situation_description` que se guardó antes. Corrección: `COALESCE(EXCLUDED.campo, hardship_assessments.campo)` para no pisar con vacíos, más una prueba que guarde en dos pasos. Mientras tanto, en esta simulación el agente guarda todas las respuestas juntas al final.

## Fase 7: las Hardship Questions

| # | Pregunta del agente | Respuesta de la deudora |
| --- | --- | --- |
| 1 | "Can you tell me a little about what happened and when this situation started?" | "I lost my job last month and haven't found another one yet." |
| 2 | "I'm sorry to hear that, that's a hard situation. Do you expect this to be temporary, or a longer-term change in your income?" | "I'm currently looking, but I haven't found anything. I've tried on LinkedIn and searched in person, dropping off resumes, but still nothing - believe me, I'm desperate." |
| 3 | "I believe you, and thank you for being so open with me. It sounds like you're doing everything you can. Is there anyone else in your household who could help out while things stabilize?" | (pendiente) |

Herramientas: ninguna todavía. Las respuestas se guardan juntas al final (ver el error del repositorio en la fase 6).

Observaciones:
- [Prompt] **La respuesta 2 no encaja en `duration_type`** (`temporary` o `long_term`). La deudora no dijo ninguna de las dos: está buscando trabajo y no sabe cuánto tardará. Un modelo pequeño podría forzar `temporary` (porque está buscando) o `long_term` (porque no encuentra). Propuesta: que el prompt diga "if the answer doesn't clearly say temporary or long-term, leave duration_type empty and put the debtor's words in notes"; o agregar el valor `unknown`.
- [Prompt] **La deudora dice "I'm desperate".** El agente respondió con empatía sin presionar ni prometer. El prompt pide empatía, pero no dice qué hacer ante señales de angustia fuerte (llanto, "no sé qué hacer"). [Negocio] ¿Hay un protocolo de deudor vulnerable (pasar a una persona, pausar la cobranza)?
- [Legal] Las agencias de cobranza en EE. UU. suelen tener políticas para deudores en situación vulnerable (pérdida de empleo, enfermedad). Revisar con el abogado si aplica alguna obligación.
| 3 | (ver arriba) | "My husband helps a little, but he only works part-time." |
| 4 | "Thank you, that helps me understand. I know things are difficult. Is there a partial amount you could put toward this today, or on your next pay date?" | "I could speak with him about helping me pay 30 dollars at the end of the month; all I would need is time until that date so I can give him an answer." |
| 5 | "That's helpful to know, thank you. One last question: what realistic arrangement could we set for the next thirty or sixty days that you could keep up with comfortably?" | (pendiente) |

Observaciones de las respuestas 3 y 4:
- [Prompt] **La pregunta 4 dice "on your next pay date", pero la deudora acaba de decir que no tiene trabajo.** Leída tal cual suena a que el agente no escuchó. Propuesta: permitir adaptar la pregunta a lo que ya se dijo ("…today, or when your husband gets paid?") sin cambiar su sentido.
- [Negocio] **USD 30 está por debajo del 10% (es el 6,2%).** Solo se acepta entre 5% y 10% como último recurso: con Hardship hecho y con las 10 ofertas de cuotas rechazadas. Aquí van rechazadas 3 de 10, así que el sistema hoy no dejaría armar ese parcial.
- [Negocio] **"A fin de mes" está fuera de plazo.** El primer pago puede ser hasta en 8 días (hasta el 2026-11-19); fin de mes es el 2026-11-30, 19 días después. Ni el monto ni la fecha que ofrece la deudora caben en las reglas.
- [Negocio] **La deudora no se compromete: necesita hablar con su esposo.** El sistema no tiene un estado para "el deudor va a consultar y vuelve a llamar". Hoy solo quedaría `callback_requested`, sin guardar el monto ni la fecha que mencionó (mismo hueco de las simulaciones 2 y 3).

Respuesta 5: "Maybe 30 dollars a month, starting at the end of the month."

## Fase 8: guardar las respuestas y oferta 4

Herramientas:

| Herramienta | Entrada | Respuesta del backend |
| --- | --- | --- |
| `record_hardship_answers` | `{"situation_description": "Lost her job last month and has not found another one yet; actively looking (LinkedIn, in person).", "situation_started": "last month", "household_support": true, "offered_amount_dollars": 30, "notes": "Duration unclear: looking for work, no expected date. Husband works part-time and helps a little. Debtor offered 30 dollars at the end of the month, then 30 dollars a month starting at the end of the month; needs to talk to her husband first. Said she feels desperate."}` | `{"saved": true, "next_step": "Thank them for sharing, then call propose_offer."}` |
| `propose_offer` | `{"account_ref": "ACC-T001"}` | Oferta 4: 4 cuotas de `$121.25` (2026-11-11, 2026-12-11, 2027-01-11, 2027-02-11) (`proposal_id: P531d8d77`) |

**Agente:** "Thank you for sharing all of that with me. With what you told me, I can offer four monthly payments of one hundred twenty-one dollars and twenty-five cents, starting today and then on the eleventh of each month through February. Would that be something you could manage?"

Observaciones:
- `duration_type` quedó vacío a propósito y la situación se explicó en `notes` (ver fase 7).
- [Backend] **`record_hardship_answers` no tiene el campo `recommended_plan`**, aunque existe en la tabla y en el caso de uso. El agente no puede guardar qué plan terminó ofreciendo. Debería llenarlo el sistema solo, al crear el acuerdo, en vez de la IA.
- [Negocio] **Ningún plan permitido se acerca a lo que puede pagar la deudora.** Ofreció USD 30 al mes; el plan más largo permitido (10 cuotas en hasta 1 año) es de USD 48,50 al mes. Pagando 30 al mes tardaría 17 meses. Las ofertas 4 a 10 van a ser rechazadas una por una (7 turnos más) para llegar al mismo final: transferir a una persona o un parcial de último recurso. Las Hardship Questions ya dieron la información para saberlo. Propuestas para el jefe: (a) si el monto que ofrece el deudor en la pregunta 4 o 5 no alcanza ni para 10 cuotas, saltar directo a la oferta de 10 cuotas o a la persona; (b) permitir planes más largos que 1 año con pagos menores, en casos de Hardship; (c) dejarlo como está.
- [Prompt] La oferta 4 empieza hoy, pero la deudora acaba de decir "starting at the end of the month". El agente podría correr la primera cuota hasta el 2026-11-19 (8 días), pero no a fin de mes. No la movió porque igual no llega a la fecha que pidió.

## Fase 9: la deudora necesita consultar con su esposo

**Deudora:** "I need to talk to my husband first. Because he's not paid yet, I need to talk first with him."

**Agente:** "Of course, that makes sense. Please take the time to talk with him, and you can call us back whenever you're ready. Thank you for calling, Ms. Carter, and I wish you the best with your job search."

Herramienta:

| Herramienta | Entrada | Respuesta del backend |
| --- | --- | --- |
| `end_call` | `{"outcome": "callback_requested"}` | `{"ended": true, ...}` |

Lo guardado en la base:

| Dato | Valor |
| --- | --- |
| `calls.outcome` | `callback_requested` |
| `accounts.status` (ACC-T001) | `NSF` (sin cambios) |
| Acuerdos | 0 |
| `hardship_assessments` | `situation_started` "last month", `duration_type` vacío, `household_support` true, `offered_amount_cents` 3000, `recommended_plan` vacío |

Observaciones:
- [Prompt] La oferta 4 no se marcó como rechazada: la deudora no dijo que no, dijo que necesita consultar. El agente no presionó ni insistió con las ofertas 5 a 10, y no prometió nada.
- [Backend] **Lo hablado en esta llamada no sirve para la siguiente.** Las Hardship Questions quedan atadas a esta llamada (`exists_for_call(call_id)`) y el registro de ofertas rechazadas vive en memoria por llamada. Cuando Jane vuelva a llamar con la respuesta de su esposo, el sistema le va a ofrecer otra vez el pago total, 2 y 3 cuotas, y le va a repetir las 5 preguntas. Propuesta: que las Hardship Questions valgan por deudor durante un tiempo (por ejemplo, 30 días) y que las ofertas rechazadas se guarden en la base por cuenta, no solo en memoria.
- [Backend] `callback_requested` otra vez no guarda lo esencial: que la deudora vuelve con una respuesta sobre un pago de USD 30 a fin de mes (mismo hueco que las simulaciones 2 y 3).
- [Negocio] ¿Quién da seguimiento? Si Jane no vuelve a llamar, ¿la llama el agente (saliente) o un cobrador? ¿Cuándo? El trabajo del agente hoy termina en `PTP`, y aquí no se llegó a `PTP`.

## Resumen de pendientes de esta simulación

| # | Tipo | Pendiente |
| --- | --- | --- |
| 1 | Backend | **Error:** guardar las Hardship Questions en dos pasos borra las respuestas anteriores (`ON CONFLICT ... SET campo = EXCLUDED.campo`). Corregir con `COALESCE` y una prueba |
| 2 | Backend | Las Hardship Questions y las ofertas rechazadas deben valer para la próxima llamada del mismo deudor |
| 3 | Backend | `propose_offer` debe devolver la fecha límite del primer pago (hoy + 8 días) |
| 4 | Backend | `recommended_plan` lo debe llenar el sistema al crear el acuerdo |
| 5 | Backend | `callback_requested` sin datos: fecha, motivo y monto mencionado |
| 6 | Negocio | Si lo que ofrece el deudor no alcanza ni para 10 cuotas: ¿saltar directo, permitir planes más largos o recorrer las 10 ofertas? |
| 7 | Negocio | ¿La primera cuota se ofrece hoy o en la próxima fecha de pago del deudor? |
| 8 | Negocio | ¿Hay que ofrecer pago total, 2 y 3 cuotas aunque el deudor ya dijo que no puede pagar? |
| 9 | Negocio | Protocolo para deudores vulnerables ("I'm desperate") |
| 10 | Negocio | Seguimiento cuando la llamada termina sin acuerdo |
| 11 | Prompt | `duration_type` vacío si la respuesta no es clara; adaptar la pregunta 4 a lo ya dicho |
| 12 | Prompt | Cuotas "iguales" con centavos distintos: cómo decirlas en voz |
| 13 | Prompt | Permitir presentar la oferta en el mismo turno que la deuda si el deudor ya planteó su situación |
| 14 | Legal | Obligaciones con deudores en situación vulnerable |
