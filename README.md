# Agente de voz de cobranza NSF

Actualizado: 2026-11-17. Cliente: Live Oac Financial.

Agente de IA que llama y atiende a deudores con pagos devueltos por falta de fondos (NSF) y negocia el pago del saldo completo, sin descuentos. Las reglas de negocio viven en el backend. Claude solo conversa y pide herramientas: nunca decide montos, fechas ni resultados.

**Dónde estamos:**
- **Construido y probado (398 pruebas del backend, 77 del agente y 19 de mensajería):** las reglas, la conversación en texto (chat y página web) y los SMS con un proveedor de prueba.
- **Falta:**
  - la capa de voz (Pipecat, AssemblyAI y Deepgram);
  - conectar Vaspian, el procesador de pagos y Lariat;
  - instalar en AWS;
  - el piloto.
- **Lo que espera respuesta de la empresa:** `docs/para_el_jefe/pendientes_externos.md` y `docs/para_el_jefe/preguntas_proveedores.md`.
- **Historia del proyecto:** cómo llegamos aquí y quién decidió qué está en `CONTEXTO.md`. Lo que falta hacer está en `PENDIENTES.md`.

## Cómo correrlo

Todo se corre desde la raíz del repositorio. La clave de Anthropic va en `.env` como `ANTHROPIC_API_KEY`; ese archivo no se sube al repositorio.

| Para qué | Comando |
| --- | --- |
| Levantar la base y la API | `docker compose up -d` (API en http://localhost:8001/docs; base en el puerto 5433, usuario `cobranza`, clave `cobranza_dev`) |
| Recrear la base desde cero | `docker compose down -v && docker compose up -d` |
| Pruebas | `docker compose run --rm --build backend`, `... agente` y `... messaging` |
| Chat de prueba, llamada entrante | `docker compose run --rm agente python -m cobranza_agent.infrastructure.chat_cli --entrante +13055550001` |
| Chat de prueba, llamada saliente | `docker compose run --rm agente python -m cobranza_agent.infrastructure.chat_cli --saliente ACC-T001` |
| Página web de chat (demo) | `docker compose up web` → http://localhost:8000 (historial en `/historial`) |
| Tarea diaria: lista de salientes | `docker compose run --rm backend python -m cobranza.infrastructure.controllers.build_outbound_list [--fecha AAAA-MM-DD]` |
| Tarea diaria: SMS | `docker compose run --rm messaging python -m cobranza_messaging.infrastructure.run [--fecha AAAA-MM-DD]` |
| Tarea diaria: acuerdos rotos | `PAYMENT_RESULTS_CONNECTED=true python -m cobranza.infrastructure.controllers.break_overdue_arrangements`. Solo se debe activar cuando esté conectado el aviso de pago |

**Datos de prueba:** 509 deudores y 747 cuentas simuladas, más 9 casos `TEST-xxx` (`backend/db/init/002_seed_mock.sql`). Para verificarse como TEST-001 (Jane Carter, cuenta `ACC-T001`, saldo USD 485): últimos 4 del SSN 1234, nacida el 14 de marzo de 1985.

**Opciones del chat:** `--sin-herramientas` oculta las herramientas, `--debug` muestra los avisos internos y `/colgar` termina la llamada.

## Arquitectura

Es hexagonal: `domain`, `application` (`interfaces` y `use_cases`) e `infrastructure`. Hay un solo repositorio con tres programas:

| Programa | Carpeta (paquete) | Qué hace | Cómo corre |
| --- | --- | --- | --- |
| Núcleo de cobranza | `backend/` (`cobranza`) | Reglas, casos de uso, base de datos (`backend/db/init/`), herramientas del agente (`application/agent_tools.py`) y su API | Servidor siempre encendido (`api`, puerto 8001) |
| Agente | `agente/` (`cobranza_agent`) | Conversación con Claude, prompt (`application/prompts/agent_system_prompt.md`), chat y página web. Las herramientas se las pide a la API | Un proceso por llamada |
| Mensajería | `messaging/` (`cobranza_messaging`) | SMS de confirmación, aviso 3 días antes y link de pago | Tarea programada diaria |

Cada programa correrá en su propio contenedor y tiene su README técnico, que explica qué es, su stack, su arquitectura, qué expone, su configuración y cómo probarlo: [`backend/README.md`](backend/README.md), [`agente/README.md`](agente/README.md) y [`messaging/README.md`](messaging/README.md). En la carpeta `docs/` de cada uno están su seguridad, lo que falta y cómo separarlo a su propio repositorio.

**Reglas de arquitectura** (cada programa las revisa en `tests/unit/test_architecture.py`):
- El núcleo no conoce al agente ni a la mensajería.
- El agente no importa el núcleo: todo lo pide por HTTP. Su copia de `CallDirection` y `CallOutcome` la revisa `test_backend_contract.py`.
- La mensajería usa los casos de uso del núcleo, nunca sus repositorios.
- El agente y la mensajería no se conocen entre sí.

**API de las herramientas del agente** (`cobranza.infrastructure.api.app`): todos los endpoints piden el encabezado `X-API-Key` (`AGENT_API_KEY`); sin la clave correcta responden 401. Cualquier plataforma de voz puede usar los mismos endpoints. JWT queda para un futuro panel con usuarios.

| Endpoint | Para qué |
| --- | --- |
| `GET /api/agent/tools` | Las herramientas con sus campos, el aviso FDCPA y las Hardship Questions (el agente arma su prompt con esto) |
| `POST /api/agent/calls` | Abre una llamada: entrante con `phone`, saliente con `account` |
| `POST /api/agent/calls/{call_id}/tools/{nombre}` | Ejecuta una herramienta. Devuelve `result` (con `next_step`), `is_error` y el estado de la llamada |
| `GET /api/agent/calls/{call_id}` | Estado de la llamada: si terminó, el resultado, el resumen y si se transfirió |
| `PUT /api/agent/calls/{call_id}/transcript` | La conversación hasta ahora y la ruta del historial |
| `POST /api/agent/calls/{call_id}/hangup` | El deudor colgó |
| `POST /api/agent/calls/{call_id}/close` | Cierra sin el modelo (`transferred_to_human` o `callback_requested`) |

- Los errores de una herramienta responden 200 con `is_error` y un `next_step`: son instrucciones para el modelo.
- Las llamadas abiertas viven en memoria del servidor; por ahora alcanza con un solo servidor.

**Herramientas:** `record_recording_consent`, `verify_identity`, `get_account_details`, `propose_offer`, `record_offer_response`, `propose_partial_payment`, `record_hardship_answers`, `record_dispute`, `mark_do_not_call`, `record_collection_hold`, `get_last_contact`, `schedule_callback`, `transfer_to_human` y `end_call`. Cada respuesta trae un `next_step`: la instrucción corta de qué hacer después.

## Reglas de negocio vigentes

Entre paréntesis va quién lo decidió y cuándo. El detalle y las palabras exactas de cada decisión están en `CONTEXTO.md`.

### Qué cobra el agente
- **Solo cuentas en `NSF`.** Cualquier otro estado, incluidos `first_attempt` a `fourth_attempt`, pasa a una persona (jefe, 2026-10-29 y 2026-11-08).
- **Nunca hay descuentos.** Se cobra el saldo completo; un pago parcial no perdona el resto (desarrollador, 2026-10-28).
- **Se negocia sin presionar ni amenazar.** Nunca menciona acciones legales, reportes de crédito ni consecuencias.
- **Un deudor puede tener varias cuentas** (tablas `debtors` y `accounts`).
- **El único código de rebote es `NSF`.** El agente dice el motivo como un hecho: *"there were not enough funds on your card"* (tarjeta) o *"in your account"* (ACH o cheque). Nunca dice el código (jefe, 2026-11-17).

### Saludo, grabación e identidad
- **Llamada entrante:** el saludo incluye el aviso de grabación.
- **Llamada saliente:** primero solo pregunta por el deudor. Si no queda claro quién contestó, pregunta *"Am I speaking with [nombre]?"*; solo lo trata como otra persona cuando dice claramente que no es el deudor. Si ya le dio el aviso de grabación, el sistema rechaza el primer intento de cerrar como "otra persona" y le pide confirmar (hallazgo 4; desarrollador, opción A, 2026-11-18). Cuando la persona confirma que es él, el agente se identifica y da el aviso de grabación. La grabación empieza ahí, así que a un tercero no se le graba ni se le dice nada (N3).
- **Grabación:** solo se informa, sin preguntar (L2, jefe). Si el deudor no quiere ser grabado, se le explica que es un requisito. Si insiste, la llamada se cierra como `recording_refused` sin hablar de la deuda.
- **Nombre de la empresa:** antes de verificar solo se dice "L.O.F."; después, "Live Oac Financial" (L3, jefe).
- **Verificación:** el deudor dice su nombre completo, los últimos 4 del SSN y su fecha de nacimiento (N2, confirmado por el jefe el 2026-11-13).
  - Máximo 2 fallos por llamada. Con 5 fallos en 24 horas se bloquea y pasa a una persona.
  - Solo se pide deletrear el apellido si lo único que no coincide es el apellido (S2). Nunca se dice qué dato falló.
  - Si quien llama cambia el nombre de pila entre intentos, la llamada se cierra como `identity_mismatch` (S1).
  - Después de un fallo, `attempts_left` dice cuántos intentos quedan. Si queda 1, el agente avisa que es el último (B8).
  - Si los datos no los pudo haber dicho una persona (nombre sin apellido o de relleno, SSN 0000, fecha de nacimiento futura o de hace más de 120 años), la herramienta responde `invalid_input` y no cuenta como intento. Viene de la simulación con Haiku, que llamó con datos inventados antes de preguntarlos (desarrollador, opción A, 2026-11-18).
- **Antes de verificar,** el agente nunca dice "account", "balance", "payment", "debt", "collection" ni el acreedor, ni siquiera para decir que no puede hablar de eso. Solo usa frases fijas: al no poder verificar, *"I'm sorry, I wasn't able to verify your identity, so I can't continue with this call."*; a un tercero, *"Thank you for your time. Goodbye."* o *"Thank you, we'll try again on [fecha]. Goodbye."* (hallazgo 2 de las simulaciones con Haiku; desarrollador, opción A, 2026-11-18).
  - Al que no logra verificarse se le da el número de la línea de entrada (`AGENT_CALLBACK_NUMBER`), si está configurado (N12).
- **Aviso de cobrador:** justo después de verificar: *"This is an attempt to collect a debt... This communication is from a debt collector."* (L6).
- **Terceros:** solo se les dice "It's a personal matter" o "Legally, I can only share this information with [deudor]". Nunca se deja recado (P3, jefe).
- **Si preguntan si es un robot:** el agente dice que es un asistente virtual y ofrece pasar a una persona.

### Negociación
- **Orden de las ofertas** (las elige el sistema con `ProposeNextOffer`, nunca la IA):
  1. todo hoy;
  2. 2 cuotas;
  3. 3 cuotas;
  4. Hardship Questions;
  5. de 4 a 10 cuotas;
  6. primer pago del 10% más 12 cuotas mensuales (N5);
  7. parcial de último recurso;
  8. si nada funciona, se transfiere a una persona.
- **Cuotas:** iguales y mensuales, en fecha fija. El deudor acepta o rechaza; nunca diseña el plan. El plan dura como máximo 1 año, medido en meses del calendario.
- **Primer pago:** siempre se intenta hoy. Si el deudor pide tiempo, el primer pago y todas las cuotas caen el último día de cada mes. La herramienta da la fecha límite (N8 y B7).
- **Pago parcial:** desde el 10% en cualquier momento. El resto se paga a los 30 días o, si el deudor dice cuánto puede pagar al mes, en cuotas mensuales. Con más de 3 pagos, primero van las Hardship Questions (N6).
- **Menos del 10% (piso del 5%):** solo después de las Hardship Questions y de rechazar todas las ofertas.
- **Si el deudor dice cuánto puede pagar,** el sistema salta las ofertas con cuotas mayores. Nunca salta la de 3 cuotas ni la última (N4, opción A').
- **Aceptación:** solo vale un sí claro. Con duda ("I'll try"), el agente pregunta cuánto puede pagar cómodo y pide otra oferta (N7).
- **Cómo se paga:** si el deudor pregunta, el agente usa el texto `how_payments_work` del sistema: SMS de confirmación, aviso 3 días antes de cada cuota, link seguro el día del pago, y nadie llama para cobrar por teléfono (hallazgo 5; desarrollador, opción A, 2026-11-18). **Condición para el piloto:** Vaspian (SMS) y el procesador (link) conectados; si no, el agente estaría prometiendo algo que no pasa.
- **Al aceptar:** el acuerdo se crea con la propuesta guardada, nunca con montos que envíe la IA. La cuenta pasa a `PTP`. Solo puede haber un acuerdo activo por cuenta. Una propuesta rechazada no se puede aceptar después (B15).

### Hardship Questions
- Son las 5 preguntas del jefe (2026-11-04), traducidas al inglés en `backend/src/cobranza/domain/hardship.py`. No se usan frases que puedan verse como presión.
- Se hacen las 5, en orden y una por turno: el sistema le da al agente cada pregunta exacta y no habilita las ofertas que las exigen hasta tener las 5. Si el deudor ya respondió una por su cuenta, el agente la guarda sin repetirla. La respuesta 5 se guarda en `arrangement_answer` (hallazgo 3 de las simulaciones con Haiku; desarrollador, opción A, 2026-11-18).
- Valen 30 días por deudor, en cualquier llamada, pero solo si están completas (B1 y hallazgo 3). El sistema guarda en `recommended_plan` el acuerdo al que se llegó (B14).

### Disputas, "no llamar" y otros momentos
- **Disputa:** si el deudor dice que ya pagó, que el banco se equivocó o que la deuda no es suya, el agente pregunta la fecha y el número de confirmación y llama a `record_dispute`. La cuenta queda `is_disputed` y en estado `DISPUTE`, y se deja de cobrar (N11). Los detalles quedan en el resumen; guardarlos en campos propios está en pausa (B5, duda 6).
- **Abogado, bancarrota o fallecido:** el agente registra un bloqueo (`debtors.collection_hold`) que frena toda la cobranza del deudor (no entra a la lista diaria y el agente no cobra) y cierra la llamada como `collection_hold` con una frase fija. Igual que "no llamar": en salientes vale sin verificar; en entrantes exige verificación (prueba de ataque; desarrollador, opción A, 2026-11-19; lo que sigue después está en la duda 10).
- **"No llamar":** solo si el deudor lo pide de forma explícita (N13). En salientes vale sin verificar; en entrantes exige verificación.
- **Queja por las llamadas:** el agente dice la fecha y hora real de la última llamada (`get_last_contact`) y sigue (N13).
- **Angustia, amenazas o insultos:** el agente mantiene la calma y sigue. Nunca cuelga ni transfiere por eso (N14); negarse a pagar o insultar no es "nada funciona": primero presenta las ofertas (prueba de ataque, 2026-11-19).
- **Volver a llamar:** `schedule_callback` guarda el día y la hora que pidió la persona (en el futuro, entre 8 a. m. y 9 p. m. hora del deudor y a menos de 30 días). La lista diaria la llama a esa hora (N9 y B2).
- **Transferencia:** se guarda el motivo en `calls.transfer_reason`. Si ya había un acuerdo, la llamada queda como `arrangement_made` (B3 y B4).
- **Resultados de una saliente antes de verificar:** `wrong_party` si el número no es del deudor y `debtor_unavailable` si vive ahí pero no está. Si no aplica ninguno, `callback_requested`.

### Modelo y resumen
- **Modelos:** conversa Claude Haiku 5.5 con esfuerzo bajo. Si un turno falla, responde Claude Sonnet 5.5. Si ninguno responde, o pide más de 8 herramientas en un turno, la llamada pasa a una persona con el motivo.
- **Resumen:** en inglés, generado por la IA. Si la persona no se verificó, no menciona la deuda (B12).

### Después del acuerdo
- **SMS (N1 y N10):** confirmación del acuerdo, aviso 3 días antes de cada cuota y link de pago el día de la cuota.
  - No dicen "debt" ni el acreedor.
  - Se envían aunque el deudor haya pedido "no llamar".
  - Mientras no se conecte el proveedor, solo quedan en el log.
- **Pagos:** el aviso del procesador se registra con `RecordPaymentResult`.
  - Al pagarse todas las cuotas, el acuerdo queda `completed` y la cuenta pasa a `PAID` con saldo 0 (jefe, 2026-11-17; falta confirmar el nombre exacto del estado).
  - Si una cuota sigue sin pagar 5 días después de su fecha, el acuerdo queda `broken`, las cuotas pendientes `cancelled` y la cuenta vuelve a `NSF`, sin alerta (jefe, 2026-11-12).

### Lista diaria de salientes
- **Quiénes entran:** cada mañana se arma con las cuentas en `NSF`, sin disputa, sin "no llamar", sin acuerdo activo y con teléfono.
- **Reg F:** no se llama a quien ya tuvo 7 llamadas en 7 días, ni a quien tuvo una conversación en los últimos 7 días. Las llamadas de los cobradores también cuentan (L4, jefe), pero falta leerlas de la base real.
- **Quiénes salen:** si un deudor de la lista llama y se verifica, sale de la lista. Un impostor no puede sacarlo.

## Supuestos vigentes

Son reglas sin confirmar que ya están en el código:
- La zona horaria, si no se conoce, es la del este de EE. UU. Las tareas diarias corren en la mañana con esa fecha.
- La baja con "STOP" de los SMS la maneja el proveedor.
- Una disputa no cancela un acuerdo que ya está en `PTP`.
- Si el deudor rechazó la grabación y pide "no llamar", se guarda la marca y la llamada se cierra como `recording_refused`.
- Con un teléfono compartido, se verifica a quien coincide con el nombre que dijo el deudor.
- Las ofertas de cada llamada se guardan en memoria. Si hace falta auditarlas, irían a una tabla, lo que requiere aprobar el modelo de datos.
- **Historial de la página web:** guarda la fecha de nacimiento en el texto. Hay que resolverlo antes de usar datos reales.

## Alertas legales abiertas

Ninguna fue revisada por un abogado:
- **L7:** deudores vulnerables (el agente no tiene excepción si alguien menciona hacerse daño) y SMS de cobranza (consentimiento, baja y texto).
- **Fuente de la grabación obligatoria:** ninguna ley federal la exige; puede ser una política de la empresa.
- **Revisión legal general** del guion y de los avisos.

## Proveedores (aprobados el 2026-11-15)

| Para qué | Proveedor | Costo estimado con 800 llamadas diarias (USD/mes) |
| --- | --- | --- |
| Conversación, resumen y respaldo | Anthropic: Claude Haiku 5.5, con Sonnet 5.5 de respaldo | ~166 |
| Voz a texto | AssemblyAI Universal-Streaming. Si entiende mal el audio telefónico, se cambia a Deepgram Nova-3 | ~240 |
| Texto a voz | Deepgram Aura-2 | ~1.080 |
| Orquestación de voz | Pipecat (código abierto) | 0 |
| Telefonía y SMS | Vaspian, que la empresa ya tiene. Envía el audio en vivo (jefe, 2026-11-17) | Según su contrato |
| Pago con tarjeta (IVR PCI) | Por elegir | ~480 (estimado) |
| Servidores | AWS de la empresa | Fuera del cálculo |
| CRM | Actos Software, en migración a Lariat Software | — |

**Total:** ~USD 1.966 al mes más Vaspian. Los precios son de lista y hay que confirmarlos antes de contratar. El volumen de 800 llamadas diarias no está confirmado.

## Documentos (`docs/`)

| Carpeta | Qué tiene |
| --- | --- |
| `docs/para_el_jefe/` | Lo que espera respuesta de la empresa: pendientes externos y preguntas para los proveedores (cada `.md` con su PDF al lado), y las dudas para el jefe |
| `docs/propuesta/` | La propuesta entregada a la empresa, en español e inglés, en PDF y Word |
| `docs/scripts/` | Los scripts que generan los PDF y los Word |

Cómo regenerar cada documento: `docs/README.md`.
