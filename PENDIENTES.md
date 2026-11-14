# Agente de voz de cobranza NSF: pendientes

Actualizado: 2026-11-11
Documento de arquitectura: https://claude.ai/artifact/CLGgKwmBLiJpngybRoFjtu

## Siguientes pasos

- [ ] Revisar con el jefe el documento `docs/Backend_Agente_Cobranza_NSF_v3.pdf` y aplicar sus correcciones
- [ ] Conseguir la `ANTHROPIC_API_KEY` y probar el chat de prueba y el resumen con la API real
- [ ] Aprobar los proveedores (README, sección 9); Telnyx Pay over Voice desbloquea la Función 6
- [ ] Traer el diagrama EER de la base de datos real (del jefe)

## Decisiones ya tomadas

| Tema | Decisión |
| --- | --- |
| Tipos de llamada | Entrantes y salientes. Las salientes son solo NSF, después de que el job entrega su resultado. En las entrantes el deudor puede estar en cualquier estado de pago |
| Pago con tarjeta | Transferencia a un IVR PCI con captura por teclado (DTMF); la IA nunca ve la tarjeta |
| Verificación | Nombre completo + últimos 4 del SSN + fecha de nacimiento |
| Grabación | Aviso de grabación al inicio de cada llamada |
| Negociación | Sin presionar ni amenazar |
| **Descuentos** | **NUNCA.** Siempre se cobra el saldo completo. Se acepta pago parcial, pero el resto se sigue debiendo |
| Idioma del agente | Inglés |
| Idioma del resumen | Inglés: todo el equipo habla inglés y el servicio es para EE. UU. (2026-11-08) |
| Estados que cobra el agente | Solo `NSF`. Cualquier otro, incluidos `first_attempt` a `fourth_attempt`, pasa a una persona (2026-11-08) |
| Hardship Questions | Traducción al inglés aprobada. Sin frases que puedan verse como presión; si hace falta preguntar más, se sigue el tono de las 5 del jefe (2026-11-08) |
| Reglas sin confirmar | Quedan como supuestos vigentes (`README.md`, sección 4), salvo las que no tienen respuesta provisional (sección 6) |
| Datos | Interfaz `DebtorRepository` + implementación en PostgreSQL con datos simulados, hasta conocer la base real |
| Forma de trabajo | Antes de cada función o tabla, Claude presenta la propuesta y se aprueban los campos |

## Respuestas del jefe (2026-10-29)

1. **Estados de pago:** el agente solo maneja NSF. Si el deudor está en cualquier otro estado, la llamada pasa a una persona.
2. **Varias deudas:** sí, con el mismo acreedor o con acreedores distintos → `debtors` y `accounts` quedan separadas.
3. **Datos del NSF:** sí, están disponibles.
4. **El job:** por definir.
5. **Entrantes:** el agente recibe el número desde el que llaman y busca al deudor con él.
6. **Ubicación:** puede faltar. Después del estado `fourth_attempt`, la empresa usa un software de Skip Tracing para encontrar a los deudores sin estado o dirección.
7. **Nombres de campos:** sí, hay nombres fijos; vendrán en el EER. Mientras tanto se trabaja con el modelo actual.
8. **Pago parcial:** se agenda una fecha para pagar el resto.
9. **Mínimo:** al menos el 10%, buscando cobrar lo más posible. Si no alcanza → plan de pagos → si tampoco, preguntas de dificultad económica (Hardship Questions: se verifican ingresos y se hacen recomendaciones).

## Respuestas ronda 2 (2026-10-29)

1. Los estados de intento (`first_attempt` … `fourth_attempt`) van en el mismo campo que NSF (`accounts.status`).
2. Saliente sin ubicación: se cobra normal y la zona horaria se deduce del código de área.
3. El 10% mínimo aplica también a la primera cuota de un plan.
4. Plan de pagos: máximo 1 año.
5. Campos de Hardship aprobados. Se recomienda amablemente; la empresa asume la alerta de cumplimiento.

## Avance

- [x] Modelo de datos en PostgreSQL (`backend/db/init/001_schema.sql`)
- [x] Datos simulados: 509 deudores, 747 cuentas, 9 casos de prueba `TEST-xxx` (`backend/db/init/002_seed_mock.sql`)
- [x] Docker funcionando (se activó la virtualización en Windows)
- [x] Función 1: consultar deudor (`FindDebtorsByPhone`, `GetDebtorByAccount`)
- [x] Backend en arquitectura hexagonal con carpetas `domain/`, `application/` (`interfaces/`, `use_cases/`) e `infrastructure/` (`repositories/`, `services/`, `controllers/`, `config/container.py`). 25 pruebas: unitarias sin BD, integración con PostgreSQL y una prueba que impide que el dominio o la aplicación importen infraestructura
- [x] Función 2: verificar identidad (`VerifyIdentity`). Intentos de verificación en `calls.verification_attempts` (los de cobro siguen en `accounts.status`). Máx. 2 fallos por llamada; 5 fallos en 24 h → bloqueo y pasa a una persona; nombre mal → pedir deletrear el apellido sin contar intento. 54 pruebas
- [x] Función 3: registrar la llamada (`StartCall`, `RecordRecordingConsent`, `EndCall`). Toda llamada se graba: si el deudor no acepta, se cierra como `recording_refused` sin hablar de la deuda. Resumen con IA: Claude Haiku 5.5 (~USD 24/mes para 2.000 llamadas/día) y, si rechaza o falla, Claude Sonnet 5.5 como respaldo propio (`FallbackCallSummarizer`, sirve con cualquier proveedor). Si ambos fallan, la llamada se cierra igual sin resumen. 72 pruebas
- [ ] Probar el resumen con la API real (falta `ANTHROPIC_API_KEY`)
- [x] Función 4: negociar el acuerdo (`ProposeArrangement`, `ProposePartialPayment`, `CreateArrangement`), 128 pruebas. Definido el 2026-11-02: sin descuentos; el agente ofrece primero todo de una, luego 2 cuotas, luego 3, siempre lo más rápido; el deudor acepta, no propone; cuotas iguales y de frecuencia fija; parcial con el resto en máximo 30 días; primer pago ≥ 10% y puede ser en unos días; plan de máximo 1 año. Cuotas mensuales en fecha fija (decisión del jefe), primer pago en máximo 8 días y resto del parcial a 30 días por defecto. Al crear un acuerdo la cuenta pasa a `PTP` y ahí termina el trabajo del agente; `RCC` queda fuera del alcance. Entre 5% y 10% solo como último recurso. Decisiones y origen: `README.md`
- [x] Función 5: Hardship Questions (`RecordHardshipAssessment`) y orden de la negociación. Flujos de entrantes y salientes aprobados por el jefe; las llamadas de recordatorio las hace un cobrador. 149 pruebas
- [x] Aprobar la traducción al inglés de las Hardship Questions (2026-11-08)
- [ ] Función 6: transferir al IVR PCI y registrar el resultado del pago. **Bloqueada:** falta elegir proveedor; se deja para después de las demás funciones
- [x] Función 7: disputas y "no llamar" (`RecordDispute`, `MarkDoNotCall`). 166 pruebas
- [x] Cambio a solo NSF probado (2026-11-08): 166 pruebas pasan
- [x] Paso 8: chat de prueba con Claude (2026-11-10). El sistema elige cada oferta (`ProposeNextOffer`) y el acuerdo se crea con la propuesta guardada (`RecordOfferResponse`). 11 herramientas, prompt del agente y respaldo con Sonnet. 197 pruebas, incluida una llamada completa contra PostgreSQL con un modelo guionado
- [x] Pruebas de casos borde de `ProposeNextOffer`, `ProposePartialPayment` y `RecordOfferResponse`, y 5 llamadas más por chat contra PostgreSQL: Hardship → 4 cuotas, pago parcial, disputa, "no llamar" y saliente (2026-11-11). 228 pruebas pasan
- [x] 7 simulaciones del agente sin API (Claude hizo de agente con las herramientas reales). Informe para el jefe: `docs/Informe_Simulaciones_Agente_Cobranza_NSF.pdf`; detalle en `docs/` (2026-11-11)
- [x] Error E1 corregido: al colgar, el aviso al modelo indica usar `mark_do_not_call` o `record_dispute` si el deudor lo pidió; antes solo mandaba `end_call` y el pedido se podía perder (2026-11-11)
- [x] Error E2 corregido: guardar las Hardship Questions de a una ya no borra las respuestas anteriores (`COALESCE` en el repositorio). 233 pruebas pasan (2026-11-11)
- [x] S1 (simulación 8, verificación por tanteo): si quien llama cambia el nombre de pila entre intentos, `VerifyIdentity` devuelve `identity_mismatch` sin revisar los datos, cuenta un intento fallido y la llamada se cierra con el resultado nuevo `identity_mismatch` (agregado al CHECK de `calls.outcome`). 242 pruebas pasan (2026-11-12)
- [x] S2 (simulación 8): se pide deletrear el apellido solo si el SSN, la fecha y el nombre de pila coinciden y solo falla el apellido; si no, es un intento fallido normal (`only_last_name_differs`). 251 pruebas pasan (2026-11-12)
- [x] Arquitectura en 3 módulos (núcleo, `agent/`, `messaging/`) en el mismo repositorio, con reglas en `test_architecture.py`. Sin cambios de comportamiento; 256 pruebas pasan (2026-11-12)
- [x] N1: SMS de confirmación del acuerdo y link de pago en cada fecha (módulo `messaging/`, tabla `sms_messages`, tarea `cobranza.messaging.infrastructure.run`). Proveedor y link de prueba hasta que el jefe confirme el proveedor ("empieza por V") y la página de pago. 269 pruebas pasan (2026-11-12)
- [x] Lista diaria de salientes (pedido del jefe): tabla `outbound_call_list`, tarea `cobranza.infrastructure.controllers.build_outbound_list`, filtros de Reg F (7 llamadas en 7 días y 7 días tras una conversación). El deudor que llama y verifica su identidad sale de la lista. 279 pruebas pasan (2026-11-12)
- [x] N2: la verificación queda como está (nombre completo + últimos 4 del SSN + fecha, dichos por el deudor). Confirmado por el jefe el 2026-11-13 (2026-11-12)
- [x] N3: en salientes, el saludo solo pregunta por el deudor; el aviso de grabación va cuando confirma que es él y antes de verificar; la grabación empieza con su "sí" (`CallRecorder`, hoy de desarrollo). El texto del saludo va en el cambio de prompt (P1–P12). 281 pruebas pasan (2026-11-12)
- [x] N4 (opción A'): `propose_offer` recibe lo que el deudor dice poder pagar; se saltan las ofertas mayores (quedan en el registro con el motivo), nunca la de 3 cuotas ni la de 10. 288 pruebas pasan (2026-11-12)
- [x] N5: después de las Hardship Questions, la última oferta es un primer pago del 10% y el resto en 12 cuotas mensuales iguales (oferta 11); si tampoco puede, pasa a una persona. El plazo de 1 año se mide en meses del calendario. 299 pruebas pasan (2026-11-12)
- [x] N6: el resto de un parcial se reparte en cuotas mensuales si el deudor dice su límite (con más de 3 pagos, primero Hardship); el agente sigue ofreciendo el parcial de último recurso antes de transferir. 311 pruebas pasan (2026-11-12)
- [x] N7: ante una aceptación con duda, el agente pregunta cuánto puede pagar cómodo al mes y vuelve a pedir la oferta; solo cierra si el deudor dice que puede cumplir. Aplicada en el prompt el 2026-11-13; 347 pruebas pasan (2026-11-12)
- [x] N8: el primer pago puede ir hasta fin de este mes (si faltan menos de 8 días, primero se ofrece fin de este mes y después fin del mes siguiente); siempre se intenta hoy. `propose_offer` devuelve la fecha límite (también resuelve B7). 319 pruebas pasan (2026-11-12). Ajuste del 2026-11-13: si pide tiempo, primer pago y cuotas el último día de cada mes (`monthly_due_date`); la pregunta por el día de cobro se omite por ahora. 355 pruebas pasan
- [x] N9: el seguimiento sin acuerdo lo hace la lista diaria (con las reglas de Reg F); una hora pedida por el deudor se respeta cuando se construya B2 (2026-11-12). Construido el 2026-11-13 con B2: `schedule_callback`, `calls.callback_at` y `outbound_call_list.call_at`. 368 pruebas pasan
- [x] N10: SMS solo de aviso 3 días antes de cada cuota (`SendPaymentReminders`, tipo `payment_reminder` en `sms_messages`), además del link el día de la cuota. 323 pruebas pasan (2026-11-12)
- [x] N10: a los 5 días sin pago, acuerdo `broken` y cuenta de vuelta a `NSF`, sin alerta (respuesta del jefe). `RecordPaymentResult` y `BreakOverdueArrangements`; la tarea `break_overdue_arrangements` está protegida hasta conectar el aviso de pago (`PAYMENT_RESULTS_CONNECTED=true`). 339 pruebas pasan (2026-11-13)
- [ ] Conectar el aviso de pago del procesador (webhook) a `RecordPaymentResult` y activar `break_overdue_arrangements`
- [x] N13: herramienta `get_last_contact` (caso de uso `GetLastContact`): ante una queja por las llamadas, el agente dice la fecha y hora reales de la última llamada saliente, en la hora local del deudor, y si en ella hubo acuerdo. "No llamar" solo con pedido explícito (prompt). Solo cuenta las llamadas de esta base. 344 pruebas pasan (2026-11-13)
- [ ] Preguntar al jefe: estado de la cuenta cuando se pagan todas las cuotas
- [x] N11 (decisión, sin construir): disputa con alerta al equipo y revisión de un cobrador; el agente busca el pago en la llamada; si no lo encuentra, no acusa y registra la disputa igual (supuesto vigente) (2026-11-12). Estado `DISPUTE` construido el 2026-11-13 (los datos simulados pasaron de `DISPUTED` a `DISPUTE`); 368 pruebas pasan
- [x] N14: ante angustia o amenazas, el agente mantiene la calma y sigue cobrando; nunca cuelga ni transfiere por eso, ni siquiera si el deudor menciona hacerse daño (decisión del desarrollador, queda para L7). Aplicado en el prompt; 369 pruebas pasan (2026-11-13)
- [x] B12: el resumen sabe si hubo verificación; sin verificación solo dice quién contestó y cómo terminó, sin mencionar la deuda; con amenazas o insultos, una línea sin repetir las palabras (respuesta del jefe). 373 pruebas pasan (2026-11-13)
- [x] B1: las Hardship Questions valen 30 días por deudor en cualquier llamada (`exists_for_debtor_since`); las ofertas empiezan de nuevo en cada llamada. 375 pruebas pasan (2026-11-13)
- [x] B3 y B4: campo `calls.transfer_reason` y resultado `debtor_unavailable` (aprobados). Con acuerdo y transferencia, la llamada queda `arrangement_made` y guarda el motivo; si el modelo falla, el motivo lo dice. 381 pruebas pasan (2026-11-13)
- [ ] B5 en pausa (2026-11-13): detalles de la disputa. Esperar al jefe (duda 6 en `docs/dudas_para_el_jefe.md`). En el lote de prompt: preguntar fecha del pago y número de confirmación antes de `record_dispute`
- [x] B6: `get_account_details` da el motivo del rebote en palabras sencillas solo para R01 y R09; con otro código no da motivo y nunca dice el código (opción A). 386 pruebas pasan (2026-11-13)
- [x] B8: `verify_identity` devuelve `attempts_left` tras un intento fallido; si queda 1, el agente avisa que es el último intento (opción A). 398 pruebas pasan (2026-11-13)
- [x] B9: `next_step` corregidos: otro monto tras un rechazo → `propose_partial_payment`; la oferta va en el turno siguiente a la deuda; tras colgar, ninguna herramienta pide hablar (opción A). 403 pruebas pasan (2026-11-13)
- [x] B14: al crear un acuerdo, el sistema llena `recommended_plan` en las Hardship más recientes del deudor (últimos 30 días) con un resumen corto (opción A). 406 pruebas pasan (2026-11-13)
- [x] B15: informativa; una propuesta rechazada no se reacepta, se arma otra igual. Se deja como está y se documenta (opción A, 2026-11-13)
- [ ] Preguntar al jefe (B6, duda 7): lista de todos los códigos de rebote, qué significa cada uno, qué dice el agente y cuáles son disputa
- [x] N12: al cerrar por verificación fallida o cambio de nombre, el agente da el número para devolver la llamada (`AGENT_CALLBACK_NUMBER`; si no está configurado, no se ofrece). 330 pruebas pasan (2026-11-12)
- [ ] Preguntar al jefe (N12): confirmar la opción y cuál es el número de la línea de entrada que atiende el agente
- [x] L2, L3 y P3: aviso de grabación sin pregunta, "L.O.F." antes de verificar y "Live Oak Financial" después, frases fijas para terceros. Los SMS dicen "L.O.F.". 330 pruebas pasan (2026-11-12)
- [ ] Preguntar al jefe: proveedor de SMS ("empieza por V"), página de pago del procesador, estado de la cuenta cuando se pagan todas las cuotas, si aprueba que el primer pago vaya hasta fin de mes en vez de 8 días (N8), y si a los 5 días sin pago se puede marcar `broken` y avisar por Teams (u otro canal) sin cambiar el estado (N10)
- [ ] Preguntar al jefe (N11): qué estado se le pone a la cuenta al marcarse en disputa, qué se hace con el resultado de la revisión (válida o no) y si se puede consultar en su base si un pago entró
- [ ] Resolver una por una las observaciones del informe: S2, después negocio (N1–N15), backend (B1–B15) y prompt (P1–P12, en un solo cambio). Lo legal (L1–L7) se anota como supuesto
- [ ] Probar el chat con la API real y ajustar el prompt (falta `ANTHROPIC_API_KEY`)

Correr las pruebas: `cd backend && docker compose run --rm --build app`

Chat de prueba: `cd backend && docker compose run --rm app python -m cobranza.agent.infrastructure.chat_cli --entrante +13055550001` (necesita `ANTHROPIC_API_KEY`; ver README, paso 8)

Levantar la base: `cd backend && docker compose up -d` (puerto 5433, usuario `cobranza`, clave `cobranza_dev`).
Recrear desde cero: `docker compose down -v && docker compose up -d`.

## Borrador del modelo de datos (por ajustar)

**`debtors`** (la persona)
- `id`, `external_id`, `first_name`, `last_name`
- `dob` (fecha de nacimiento, cifrada) y `ssn_last4` (cifrado); nunca se le pasan a la IA
- `phone_primary`, `phone_secondary`
- `us_state`, `timezone`
- `do_not_call` (el deudor pidió no ser llamado)
- `created_at`, `updated_at`

**`accounts`** (la deuda)
- `id`, `debtor_id`, `creditor_name` (a quién se le debe), `account_number_masked` (`****4821`)
- `original_amount`, `nsf_fee` (cargo por el rebote), `current_balance` (total que debe hoy), en centavos
- `payment_status`, `status_updated_at`
- `nsf_date` (fecha del rebote), `nsf_return_code` (código del banco, p. ej. R01)
- `is_disputed` (el deudor disputa la deuda; no se cobra mientras siga abierta)

**`calls`** (cada llamada)
- `id`, `account_id`, `direction` (inbound / outbound), `caller_phone`
- `started_at`, `ended_at`
- `recording_consent`, `identity_verified`, `verification_attempts`
- `outcome`, `summary`
- `recording_uri`, `transcript_uri` (ubicación de los archivos de audio y de texto)

**`payment_arrangements`** (el acuerdo)
- `id`, `call_id`, `account_id`
- `type`: `full` (todo hoy) | `partial` (una parte hoy, el resto sigue debiéndose) | `plan` (en cuotas)
- `total_amount`, `installments` (número de cuotas), `first_payment_date`, `status`
- Sin campos de descuento

**`payment_results`** (respuesta del IVR PCI)
- `id`, `arrangement_id`, `ivr_reference` (número de confirmación del pago), `amount`, `status`, `processed_at`
- Sin datos de tarjeta

## Borrador de la Función 1: consultar deudor (por aprobar)

| Función | Cuándo | Busca por |
| --- | --- | --- |
| `find_by_phone(phone)` | Entrante | El número desde el que llama |
| `get_by_account(account_id)` | Saliente (job NSF) | El ID de la cuenta |

- **Devuelve:** nombre, cuenta enmascarada, acreedor, `current_balance`, `payment_status`, datos del NSF, `is_disputed`, `do_not_call`, estado de EE. UU. y zona horaria
- **No devuelve:** SSN ni fecha de nacimiento
- **No encuentra el teléfono:** el agente pide el número de cuenta (por confirmar)
- **Varias cuentas con el mismo teléfono:** las devuelve todas y el agente pregunta cuál es (por confirmar)
- **Con disputa o "no llamar":** no cobra; registra la llamada y ofrece pasar a un humano

**Estados de pago propuestos (por confirmar con la pregunta 1):**

| Estado | Qué hace el agente en una llamada entrante |
| --- | --- |
| `NSF` | Cobra: total, parcial o plan |
| `PAYMENT_PLAN` | Informa la próxima cuota y ofrece adelantar el pago |
| `CURRENT` | Informa que no debe nada y cierra |
| `PAID` | Confirma que la deuda está saldada y cierra |
| `DISPUTED` | No cobra, registra y pasa a un humano |
| `CLOSED` | Informa y pasa a un humano |

## Otros pendientes del proyecto

- [ ] Insertar una fila nueva por resultado de llamada o actualizar el registro del deudor
- [ ] Qué base de datos usa el sistema real y acceso a ella
- [ ] Proveedor del IVR PCI y cómo devuelve el resultado del pago
- [ ] Revisión legal del guion y de los avisos
