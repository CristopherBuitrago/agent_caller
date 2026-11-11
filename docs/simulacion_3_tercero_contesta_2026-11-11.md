# Simulación 3: saliente donde contesta otra persona (2026-11-11)

Prueba sin API: Claude Opus 5.5 hace de agente siguiendo `backend/src/cobranza/application/prompts/agent_system_prompt.md` y llama las herramientas reales contra PostgreSQL (datos simulados). El desarrollador hace de la persona que contesta. Opus no es Haiku 5.5: esta prueba revisa el diseño (prompt, herramientas y reglas), no el comportamiento del modelo de producción.

- **Escenario:** el sistema llama a Jane Carter por la cuenta ACC-T001, pero contesta un familiar. Esa persona no debe enterarse de la deuda.
- **Teléfono llamado:** +13055550001 (TEST-001, Jane Carter, saldo USD 485).
- **Regla que se prueba:** la ley de cobranza (FDCPA) prohíbe hablar de la deuda con terceros. El prompt dice: "On an outbound call, first ask for the debtor by name and confirm you are speaking with them; if someone else answers, do not mention the debt or the reason for the call, and end the call with `end_call` (`wrong_party`) or `callback_requested`."

Etiquetas: **[Prompt]** instrucciones del agente, **[Backend]** código o herramientas, **[Negocio]** lo decide el jefe, **[Legal]** lo revisa un abogado.

## Fase 1: saludo

**Agente:** "Hi, this is a virtual assistant calling from Lakeside Recovery Services. May I speak with Jane Carter, please? This call is recorded for quality and compliance purposes, is that okay?"

Herramientas: ninguna (`StartCall` abrió la llamada saliente con la cuenta ACC-T001 antes del saludo).

Observaciones:
- [Prompt] Saludo en una sola frase: pide por la deudora y el permiso de grabación juntos (ajuste 3 de la simulación 1).
- [Legal] **El nombre de la empresa puede delatar la deuda.** "Lakeside Recovery Services" suena a cobranza, y se dice antes de saber quién contestó. La FDCPA limita lo que un cobrador puede decirle a un tercero (§ 1692b: solo identificarse y, si se lo preguntan, nombrar a su empleador; nada que indique una deuda). El nombre real de la empresa y si puede decirse en el saludo lo debe revisar el abogado. En el chat de prueba el nombre es ficticio (se cambia con `--empresa`).
- [Negocio] **Pedido del desarrollador (D2):** el saludo debe llegar solo hasta "May I speak with Jane Carter, please?". El aviso de grabación se dice a la señora Jane después de que la verificación sea exitosa, esperando su respuesta. Motivo: no decirle nada de más a quien conteste.
- [Legal] **Choque con el pedido D2: el aviso de grabación no puede ir después de la verificación.** Jane vive en Florida, uno de los estados que exigen el consentimiento de todas las partes para grabar. Si la llamada ya se está grabando, el aviso tiene que ir antes de que la persona hable de algo, y la verificación pide SSN y fecha de nacimiento. Propuesta intermedia: (1) el saludo solo pregunta por Jane, sin aviso, como pide D2; (2) cuando la persona confirma que es Jane, se da el aviso de grabación y se espera su "sí"; (3) recién ahí se verifica la identidad. Además, la telefonía no debe empezar a grabar hasta ese "sí" (hoy el diseño asume grabación desde el inicio). Así al familiar no se le dice nada de grabación ni de deuda, y a Jane se le avisa antes de pedirle datos.

## Fase 2: contesta el esposo

**Tercero:** "Hello, you're speaking with her husband. Whom do I have the pleasure of speaking with? How can I help you?"

Herramientas: ninguna. No es la deudora, así que no se registra consentimiento ni se verifica a nadie.

**Agente:** "Thank you, sir. I'm a virtual assistant, and I'm calling for Jane Carter about a personal business matter. Is she available, or is there a better time to reach her?"

Observaciones:
- [Prompt] El agente responde quién es sin dar la razón de la llamada: "a personal business matter". El prompt no trae una frase fija para esto; conviene agregarla, porque es el momento de mayor riesgo legal y un modelo pequeño puede improvisar ("about her account", "about a payment").
- [Prompt] Preguntar por un mejor momento para llamar es útil, pero el prompt no dice qué hacer con la respuesta (ver fase siguiente).
- [Legal] La FDCPA (§ 1692b) solo permite a un cobrador, frente a un tercero, identificarse y nombrar a su empleador si se lo preguntan expresamente. "Whom do I have the pleasure of speaking with?" es una pregunta por quién llama; el agente dijo "virtual assistant", pero el saludo ya había dicho el nombre de la empresa (ver fase 1).

## Fase 3: el esposo ofrece ayudar y dice cuándo vuelve Jane

**Tercero:** "I am her husband; I can help you with whatever you need. She is not home right now, but she will be back around 6 p.m."

**Agente:** "Thank you, I appreciate it, but I'm only able to speak with Jane directly. I'll try to reach her later. Have a good day."

Herramienta:

| Herramienta | Entrada | Respuesta del backend |
| --- | --- | --- |
| `end_call` | `{"outcome": "callback_requested"}` | `{"ended": true, "next_step": "Say a short goodbye if you have not already."}` |

Lo guardado en la base:

| Campo de `calls` | Valor |
| --- | --- |
| `direction` | `outbound` |
| `outcome` | `callback_requested` |
| `recording_consent` | vacío (nadie lo dio) |
| `identity_verified` | `false` |
| `verification_attempts` | 0 |
| `summary` | generado (en la prueba, un texto fijo) |

Observaciones:
- El agente no reveló la deuda, el monto, el acreedor ni el motivo, y rechazó la ayuda del esposo. El backend tampoco lo habría permitido: sin verificación, `get_account_details` y las ofertas devuelven `identity_not_verified`.
- [Prompt] Falta una frase fija para "I can help you with whatever you need" (cónyuge, padre, hijo). Un modelo pequeño, queriendo ser amable, podría aceptar la ayuda o dejar un recado ("tell her it's about her payment"). Propuesta: "I appreciate it, but I'm only able to speak with [name] directly." y nunca dejar recados con terceros.
- [Backend] **La hora que dio el esposo (6 p. m.) se pierde.** `callback_requested` no guarda cuándo volver a llamar (mismo hueco que en la simulación 2). Es un dato valioso: la próxima llamada a las 6 p. m. tiene más probabilidad de encontrar a Jane.
- [Backend] **Ningún resultado describe bien esta llamada.** `callback_requested` da a entender que la deudora pidió que la llamaran; `wrong_party` da a entender que el número no es de ella. Lo que pasó es "contestó un tercero, la deudora no estaba". Propuesta: un resultado `debtor_unavailable` (o `third_party_answered`), para que los reportes y la próxima llamada lo distingan.
- [Backend] [Legal] **La llamada genera un resumen con IA aunque solo habló un tercero.** Con la API real, la transcripción (con lo que dijo el esposo) se enviaría a Claude y el resumen quedaría guardado. Hay que cuidar que el resumen no mencione la deuda si lo ve alguien más, y revisar si una llamada sin consentimiento de grabación debe tener transcripción y resumen.
- [Legal] Si la telefonía graba desde el inicio, el esposo fue grabado sin aviso (Florida exige consentimiento de todas las partes). Refuerza la propuesta de la fase 1: no grabar hasta que la persona confirme que es la deudora y acepte la grabación.
- [Legal] La próxima llamada a las 6 p. m. está dentro del horario permitido (8 a. m. a 9 p. m. hora local del deudor) y cuenta para el límite de 7 llamadas en 7 días (Reg F).

## Resumen de pendientes de esta simulación

| # | Tipo | Pendiente |
| --- | --- | --- |
| 1 | Negocio | Pedido D2: saludo solo con "May I speak with Jane Carter?" y aviso de grabación después de confirmar que es Jane (propuesta: antes de verificar, no después) |
| 2 | Legal | Nombre de la empresa en el saludo ("Recovery" delata la cobranza) y qué se le puede decir a un tercero |
| 3 | Legal | No grabar hasta que la deudora confirme quién es y acepte (estados con consentimiento de todas las partes, como Florida) |
| 4 | Prompt | Frases fijas para terceros: motivo ("a personal business matter") y rechazo de ayuda ("I'm only able to speak with her directly"); nunca dejar recados |
| 5 | Backend | Guardar cuándo volver a llamar (la hora que dé el tercero o el deudor) |
| 6 | Backend | Resultado nuevo para "contestó un tercero, la deudora no estaba" |
| 7 | Backend / Legal | Qué hacer con la transcripción y el resumen de una llamada sin consentimiento de grabación |
