# Separar el núcleo a su propio repositorio

El núcleo es el centro del sistema: no depende de los otros dos servicios, pero ellos sí dependen de él.

## Qué lo ata hoy a este repositorio

| Atadura | Por qué existe | Cómo se resuelve al separarlo |
| --- | --- | --- |
| **La mensajería lo instala como librería** (`cobranza` en su `pyproject.toml`) y usa sus casos de uso `ListNewArrangements`, `ListPaymentsDue` y `ListPaymentsDueOn` | Comparten la base y era lo más simple | Recomendado: publicar esos casos de uso en la API (por ejemplo, `GET /api/messaging/...`) para que la mensajería los pida por HTTP, como ya hace el agente. La alternativa es publicar `cobranza` como paquete privado (por ejemplo, en AWS CodeArtifact) con versión fija |
| **`cobranza.testing.postgres_fixtures`** lo usan las pruebas de integración de los 3 servicios | Una sola forma de preparar y limpiar los datos de prueba | Cada servicio se queda con sus propias fixtures, o se publican como paquete de pruebas |
| **La tabla `sms_messages`** está en este esquema, pero la escribe la mensajería | Comparten una sola base | Moverla a una base o un esquema de la mensajería |
| **El `docker-compose.yml` de la raíz** levanta la base, la API y los demás servicios juntos | Desarrollo local | Cada repositorio con su compose (base más servicio). Para las pruebas de punta a punta, un compose que use las imágenes publicadas |
| **El agente tiene una copia de `CallDirection` y `CallOutcome`**, y su prueba de contrato importa `cobranza.domain.call` | Revisar que las dos copias no se separen | Revisar contra `GET /api/agent/tools`, o publicar un esquema de la API (OpenAPI) con versión |

## Pasos

1. Mover `backend/` (con `db/`, `tests/` y su `Dockerfile`) a un repositorio nuevo, conservando su historial (`git filter-repo --subdirectory-filter backend`).
2. Agregar las pruebas automáticas en el repositorio nuevo.
3. Publicar la imagen del contenedor (por ejemplo, en AWS ECR) con versión.
4. Resolver la atadura con la mensajería antes de mover la mensajería.
5. Versionar la API (`/api/v1/...`) para poder cambiarla sin romper al agente.
