# Núcleo de cobranza NSF (`cobranza`)

Servicio que guarda todas las reglas de negocio de la cobranza NSF, su base de datos y la API con la que el agente de voz ejecuta sus herramientas.

## Qué hace y qué no hace

**Hace:**
- **Busca al deudor:** por teléfono en las llamadas entrantes, o por cuenta en las salientes.
- **Verifica su identidad:** nombre, últimos 4 del SSN y fecha de nacimiento, con límite de intentos y bloqueo.
- **Arma cada oferta de pago,** valida los acuerdos y los guarda con sus cuotas. La IA nunca decide montos ni fechas.
- **Registra cada llamada:** consentimiento de grabación, resultado, motivo de transferencia, hora pedida para volver a llamar y resumen con IA.
- **Registra las Hardship Questions,** las disputas y los pedidos de "no llamar".
- **Arma la lista diaria de llamadas salientes,** respetando la Reg F.
- **Registra los resultados de pago y rompe los acuerdos vencidos.** La cuenta pasa a `PAID` o vuelve a `NSF`.
- **Publica las herramientas del agente en una API HTTP** con `X-API-Key`.

**No hace:**
- **No conversa con el deudor:** eso es del agente (`agente/`).
- **No envía SMS:** eso es de la mensajería (`messaging/`).
- **No marca llamadas ni maneja audio:** eso lo harán la telefonía y la capa de voz.
- **No ve datos de tarjeta:** el pago con tarjeta irá por un IVR PCI externo.

Las reglas de negocio vigentes (qué se cobra, el orden de las ofertas, la verificación, etc.) están en el [README de la raíz](../README.md#reglas-de-negocio-vigentes).

## Dónde encaja

```
                 X-API-Key / HTTP
  agente/  ─────────────────────────►  API (FastAPI, :8001)
                                          │
  messaging/ ── usa los casos de uso ─►  casos de uso ──► PostgreSQL
                (como librería)            │
  tareas diarias (lista de salientes, ─────┘
  acuerdos rotos)                          └──► Claude (resumen de cada llamada)
```

## Stack tecnológico

| Qué | Tecnología |
| --- | --- |
| Lenguaje | Python 3.12 o superior |
| API | FastAPI (0.115 o superior), servida con Uvicorn |
| Base de datos | PostgreSQL 16, con la extensión `pgcrypto`; acceso con psycopg 3 y su pool de conexiones |
| Teléfonos | `phonenumbers`, para normalizar a E.164 y deducir el estado por el código de área |
| IA (resumen) | SDK de Anthropic: Claude Haiku 5.5 y, si falla, Claude Sonnet 5.5 |
| Zonas horarias | `zoneinfo` con `tzdata` |
| Pruebas | pytest; httpx para la API |

## Arquitectura

Es hexagonal: las reglas no dependen de la base, de la API ni de Claude. Cada dependencia externa está detrás de una interfaz (puerto) y se conecta en `infrastructure/config/container.py`.

```
src/cobranza/
├── domain/                 reglas puras, sin librerías externas
│   ├── arrangement.py      ofertas, cuotas, mínimos, plazos y validación de acuerdos
│   ├── call.py             resultados de llamada y horario permitido para volver a llamar
│   ├── debtor.py           deudor, cuentas, estados que se cobran (NSF), DISPUTE y PAID
│   ├── hardship.py         las 5 Hardship Questions y sus respuestas
│   └── identity.py         intentos de verificación, bloqueo y comparación de nombres
├── application/
│   ├── interfaces/         puertos: repositorios, reloj, resumen, grabación, teléfonos, hash
│   ├── use_cases/          un archivo por función (verificar, negociar, registrar llamada...)
│   └── agent_tools.py      las 13 herramientas del agente: esquemas, next_step y errores
├── infrastructure/
│   ├── api/app.py          API HTTP de las herramientas
│   ├── config/container.py arma los casos de uso con sus implementaciones
│   ├── controllers/        tareas programadas (lista de salientes, acuerdos rotos)
│   ├── repositories/       implementaciones en PostgreSQL (y el registro de ofertas en memoria)
│   └── services/           Claude, HMAC, teléfonos, reloj y grabación
└── testing/                fixtures de PostgreSQL para las pruebas de integración (las usan los 3 servicios)
db/init/                    001_schema.sql (modelo) y 002_seed_mock.sql (datos simulados)
```

**Reglas de dependencia** (las revisa `tests/unit/test_architecture.py`):
- `domain` no importa nada del proyecto ni librerías externas.
- `application` no importa `infrastructure` ni librerías externas.
- El núcleo no conoce al agente (`cobranza_agent`) ni a la mensajería (`cobranza_messaging`).

**Puertos y adaptadores**

| Puerto (`application/interfaces/`) | Adaptador de hoy | Adaptador real por conectar |
| --- | --- | --- |
| `DebtorRepository` | `PostgresDebtorRepository`, sobre datos simulados | La base o la API de Lariat (o Actos) |
| `CallRepository`, `ArrangementRepository`, `HardshipRepository`, `IdentityRepository`, `OutboundListRepository`, `PaymentLedger`, `PaymentScheduleReader` | Repositorios PostgreSQL | Según el diagrama EER de la base real |
| `NegotiationLog` | `InMemoryNegotiationLog`: vive mientras dure la llamada en el proceso | Una tabla, si hace falta auditar las ofertas |
| `CallSummarizer` | `FallbackCallSummarizer` (Haiku y, si falla, Sonnet) | Igual |
| `CallRecorder` | `LoggingCallRecorder`: solo deja un registro en el log | Grabación de Vaspian |
| `PiiHasher` | `HmacSha256PiiHasher` | Igual |
| `PhoneService` | `PhonenumbersPhoneService` | Igual |
| `Clock` | `SystemClock` | Igual |

## Qué expone y qué consume

**API de las herramientas del agente.** Documentación interactiva en http://localhost:8001/docs. Todos los endpoints piden el encabezado `X-API-Key`; sin la clave correcta responden 401.

| Endpoint | Para qué |
| --- | --- |
| `GET /api/agent/tools` | Las 13 herramientas con sus campos, el aviso FDCPA y las Hardship Questions |
| `POST /api/agent/calls` | Abre una llamada: entrante con `phone`, saliente con `account` |
| `POST /api/agent/calls/{call_id}/tools/{nombre}` | Ejecuta una herramienta. Devuelve `result` (con `next_step`), `is_error` y el estado de la llamada |
| `GET /api/agent/calls/{call_id}` | Estado de la llamada: si terminó, el resultado, el resumen y si se transfirió |
| `PUT /api/agent/calls/{call_id}/transcript` | La conversación hasta ahora (para el resumen) y la ruta del historial |
| `POST /api/agent/calls/{call_id}/hangup` | El deudor colgó: desde ahí ninguna herramienta pide hablar |
| `POST /api/agent/calls/{call_id}/close` | Cierra sin el modelo (`transferred_to_human` o `callback_requested`) |

Si una herramienta falla (regla incumplida, dato mal formado, llamada terminada), la respuesta es 200 con `is_error` y un `next_step`: son instrucciones para el modelo, no errores HTTP.

**Herramientas:** `record_recording_consent`, `verify_identity`, `get_account_details`, `propose_offer`, `record_offer_response`, `propose_partial_payment`, `record_hardship_answers`, `record_dispute`, `mark_do_not_call`, `get_last_contact`, `schedule_callback`, `transfer_to_human` y `end_call`.

**Tareas programadas**

| Tarea | Comando | Cuándo |
| --- | --- | --- |
| Lista diaria de salientes | `python -m cobranza.infrastructure.controllers.build_outbound_list [--fecha AAAA-MM-DD]` | Cada mañana. Se puede repetir sin duplicar cuentas |
| Acuerdos rotos (5 días sin pago) | `python -m cobranza.infrastructure.controllers.break_overdue_arrangements [--fecha AAAA-MM-DD]` | A diario, **solo** con `PAYMENT_RESULTS_CONNECTED=true` |

**Casos de uso que usa la mensajería** (como librería): `ListNewArrangements`, `ListPaymentsDue` y `ListPaymentsDueOn`.

**Tablas** (`db/init/001_schema.sql`)

| Tabla | Qué guarda |
| --- | --- |
| `debtors` | La persona. La fecha de nacimiento y los últimos 4 del SSN se guardan solo como HMAC |
| `accounts` | Cada deuda: acreedor, saldo, estado, datos del NSF, disputa |
| `calls` | Cada llamada: dirección, consentimiento, verificación, resultado, resumen, motivo de transferencia y hora pedida para volver a llamar |
| `payment_arrangements` y `scheduled_payments` | El acuerdo y sus cuotas |
| `payment_results` | Cada aviso de pago del procesador |
| `hardship_assessments` | Las respuestas a las Hardship Questions y el plan al que se llegó |
| `outbound_call_list` | La lista diaria de salientes |
| `sms_messages` | Los SMS enviados. La escribe la mensajería; está aquí porque comparten la base |

**Servicios externos:** PostgreSQL y la API de Anthropic.

## Configuración

| Variable | Obligatoria | Por defecto | Para qué |
| --- | --- | --- | --- |
| `DATABASE_URL` | Sí | — | Conexión a PostgreSQL |
| `PII_HMAC_KEY` | Sí | — | Clave del HMAC de la fecha de nacimiento y el SSN. Si cambia, nadie se puede verificar |
| `ANTHROPIC_API_KEY` | Sí, para los resúmenes | — | Credencial de Claude (la lee el SDK de Anthropic) |
| `AGENT_API_KEY` | Sí, para la API | vacía (en local, `dev-only-agent-key` desde el compose) | Clave que debe mandar el agente en `X-API-Key` |
| `AGENT_CALLBACK_NUMBER` | No | vacía | Número que se le da a quien no logra verificarse. Si está vacía, no se ofrece |
| `PAYMENT_RESULTS_CONNECTED` | No | `false` | Permite correr la tarea de acuerdos rotos. Solo se activa con el aviso de pago conectado |

## Correr y probar en local

Todo se corre desde la raíz del repositorio, con el `docker-compose.yml` compartido.

| Para qué | Comando |
| --- | --- |
| Base y API | `docker compose up -d` (API en http://localhost:8001/docs; base en el puerto 5433) |
| Recrear la base desde cero | `docker compose down -v && docker compose up -d` |
| Pruebas | `docker compose run --rm --build backend` |
| Una tarea diaria | `docker compose run --rm backend python -m cobranza.infrastructure.controllers.build_outbound_list` |

**Pruebas (398):**
- **Unitarias** (`tests/unit/`): reglas y casos de uso con dobles en memoria, más la API con un cliente HTTP.
- **De integración** (`tests/integration/`): contra PostgreSQL real, con los casos `TEST-xxx` de los datos simulados.
- **De arquitectura** (`test_architecture.py`): revisan las reglas de dependencia.

**Datos simulados:** 509 deudores, 747 cuentas y 9 casos de prueba (`db/init/002_seed_mock.sql`). TEST-001 es Jane Carter: SSN 1234, nacida el 1985-03-14, cuenta `ACC-T001`.

## Más documentación

- **[`docs/seguridad.md`](docs/seguridad.md):** datos sensibles y cómo se protegen.
- **[`docs/en_construccion.md`](docs/en_construccion.md):** lo que falta en este servicio.
- **[`docs/separacion.md`](docs/separacion.md):** qué lo ata a este repositorio y cómo separarlo.
