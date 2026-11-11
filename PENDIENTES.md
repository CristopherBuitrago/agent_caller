# Agente de voz de cobranza NSF: pendientes

Actualizado: 2026-11-08
Documento de arquitectura: https://claude.ai/artifact/CLGgKwmBLiJpngybRoFjtu

## Para mañana

- [ ] Traer las respuestas a las preguntas 1 a 9 (abajo)
- [ ] Traer el diagrama EER de la base de datos real (del jefe)
- [ ] Ajustar el modelo de datos con las respuestas y el EER, y aprobarlo
- [ ] Aprobar la Función 1 (consultar deudor) antes de escribir código
- [ ] Empezar el backend: modelo en PostgreSQL + interfaz `DebtorRepository` + datos simulados

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
- [ ] Probar el chat con la API real y ajustar el prompt (falta `ANTHROPIC_API_KEY`)

Correr las pruebas: `cd agente-cobranza/backend && docker compose run --rm --build app`

Chat de prueba: `cd agente-cobranza/backend && docker compose run --rm app python -m cobranza.infrastructure.controllers.chat_cli --entrante +13055550001` (necesita `ANTHROPIC_API_KEY`; ver README, paso 8)

Levantar la base: `cd agente-cobranza/backend && docker compose up -d` (puerto 5433, usuario `cobranza`, clave `cobranza_dev`).
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
