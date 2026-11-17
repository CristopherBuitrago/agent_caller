# Mensajería de cobranza NSF (`cobranza_messaging`)

Tarea programada que envía los SMS de cada acuerdo de pago: la confirmación del acuerdo, un aviso 3 días antes de cada cuota y el link de pago el día de la cuota.

## Qué hace y qué no hace

**Hace:**
- **Confirma los acuerdos nuevos:** a cada acuerdo de los últimos 7 días que no tenga confirmación le envía un SMS con sus montos y fechas.
- **Avisa antes de cada cuota:** 3 días antes manda un SMS sin link, que solo recuerda el pago.
- **Envía el link de pago:** el día de la cuota, y también para cuotas vencidas que siguen pendientes, manda un SMS con el link a la página de pago del procesador.
- **No repite mensajes:** cada SMS se reserva en `sms_messages` antes de enviarse. Si la tarea corre varias veces el mismo día, no duplica nada. Un envío que falló se reintenta en la siguiente corrida.

**No hace:**
- **No decide quién debe pagar ni cuánto:** eso lo saca de los casos de uso del núcleo.
- **No recibe pagos ni sabe si el deudor pagó:** el aviso de pago lo registra el backend.
- **No maneja las respuestas "STOP":** las maneja el proveedor de SMS.
- **No conversa:** eso es del agente.

## Dónde encaja

```
  tarea diaria (run.py)
        │
        ├── casos de uso del núcleo (como librería) ──► PostgreSQL: acuerdos y cuotas
        ├── PostgresSmsRepository ────────────────────► PostgreSQL: sms_messages
        ├── SmsSender ──► hoy, el log; después, la API de SMS de Vaspian
        └── PaymentLinkProvider ──► hoy, un link de prueba; después, el procesador de pagos
```

## Stack tecnológico

| Qué | Tecnología |
| --- | --- |
| Lenguaje | Python 3.12 o superior |
| Núcleo | El paquete `cobranza` (carpeta `backend/`), instalado como librería |
| Base de datos | PostgreSQL 16, con psycopg 3 y su pool de conexiones |
| Pruebas | pytest |

## Arquitectura

Es hexagonal. Los casos de uso de SMS no saben quién envía el mensaje ni quién genera el link: los usan a través de puertos.

```
src/cobranza_messaging/
├── application/
│   ├── ports.py         puertos: SmsSender, PaymentLinkProvider, SmsRepository; tipos de SMS (SmsKind)
│   ├── send_sms.py      SendArrangementConfirmations, SendPaymentReminders y SendDuePaymentLinks
│   └── texts.py         el texto de cada SMS, en inglés, firmado con las siglas "L.O.F."
└── infrastructure/
    ├── container.py                arma los casos de uso con sus implementaciones
    ├── postgres_sms_repository.py  tabla sms_messages: reservar, marcar enviado o fallido
    ├── dev_services.py             LoggingSmsSender y PlaceholderPaymentLinkProvider (desarrollo)
    └── run.py                      la tarea programada
```

**Reglas de dependencia** (las revisa `tests/unit/test_architecture.py`):
- `application` no importa infraestructura (ni la propia ni la del núcleo) ni librerías externas.
- Usa los casos de uso del núcleo, nunca sus repositorios.
- No conoce al agente (`cobranza_agent`).

**Puertos y adaptadores**

| Puerto | Adaptador de hoy | Adaptador por conectar |
| --- | --- | --- |
| `SmsSender` | `LoggingSmsSender`: el SMS solo queda en el log | La API de SMS de Vaspian |
| `PaymentLinkProvider` | `PlaceholderPaymentLinkProvider`: link de prueba | La página de pago del procesador |
| `SmsRepository` | `PostgresSmsRepository` | Igual |

**Textos de ejemplo:**
- **Confirmación:** *"L.O.F.: your payment arrangement is set: $90.00 on Nov 11 and $395.00 on Dec 11. We'll text you a secure payment link on each date. Reply STOP to opt out."*
- **Aviso:** *"L.O.F.: reminder: your payment of $36.43 is due on Dec 31. We'll text you a secure payment link that day. Reply STOP to opt out."*
- **Link:** *"L.O.F.: your payment of $36.43 is due today. Pay securely here: <link> Reply STOP to opt out."*

Los SMS no dicen "debt" ni el acreedor, porque otra persona puede ver el teléfono. Se envían aunque el deudor haya pedido "no llamar": un SMS no es una llamada, y el deudor aceptó el acuerdo.

## Qué expone y qué consume

**Tarea programada:** `python -m cobranza_messaging.infrastructure.run [--fecha AAAA-MM-DD]`.
- Sin `--fecha`, usa la fecha de hoy en la hora del este de EE. UU.
- Imprime cuántas confirmaciones, avisos y links envió.
- Se corre una vez en la mañana, dentro del horario permitido para contactar. Se puede repetir sin duplicar mensajes.

**Consume:**
- **Casos de uso del núcleo:** `ListNewArrangements`, `ListPaymentsDue` y `ListPaymentsDueOn`.
- **Tabla `sms_messages`:** como máximo una confirmación por acuerdo, un aviso por cuota y un link por cuota (índices únicos).

## Configuración

| Variable | Obligatoria | Para qué |
| --- | --- | --- |
| `DATABASE_URL` | Sí | Conexión a PostgreSQL (la misma base del núcleo) |
| `PII_HMAC_KEY` | Sí | La pide el contenedor del núcleo al armar sus casos de uso. La mensajería no verifica a nadie, pero hoy la necesita para arrancar |

## Correr y probar en local

Todo se corre desde la raíz del repositorio, con el `docker-compose.yml` compartido.

| Para qué | Comando |
| --- | --- |
| La tarea | `docker compose run --rm messaging python -m cobranza_messaging.infrastructure.run` |
| La tarea en otra fecha | `docker compose run --rm messaging python -m cobranza_messaging.infrastructure.run --fecha 2026-12-11` |
| Pruebas | `docker compose run --rm --build messaging` |

**Pruebas (19):**
- **Unitarias:** textos, cuándo se envía cada SMS, que no se repitan y que se reintenten. También la arquitectura.
- **De integración:** contra PostgreSQL, con acuerdos creados por los casos de uso del núcleo.

## Más documentación

- **[`docs/seguridad.md`](docs/seguridad.md):** qué datos van en los SMS y qué falta legalmente.
- **[`docs/en_construccion.md`](docs/en_construccion.md):** proveedor real, link de pago y pendientes.
- **[`docs/separacion.md`](docs/separacion.md):** qué lo ata al núcleo y cómo separarlo.
