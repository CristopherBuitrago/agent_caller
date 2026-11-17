# Separar la mensajería a su propio repositorio

La mensajería es la más atada de los tres servicios: instala el núcleo como librería y comparte su base de datos.

## Qué la ata hoy a este repositorio

| Atadura | Por qué existe | Cómo se resuelve al separarla |
| --- | --- | --- |
| **Instala el núcleo (`cobranza`) como librería** y usa `ListNewArrangements`, `ListPaymentsDue` y `ListPaymentsDueOn`. Por eso arma todos los casos de uso del núcleo y pide `PII_HMAC_KEY` | Era lo más simple con una sola base | **Recomendado:** que el backend publique esas consultas en su API y la mensajería las pida por HTTP, como el agente. Así deja de necesitar `PII_HMAC_KEY` y la base del núcleo. La alternativa es publicar `cobranza` como paquete privado con versión fija |
| **Escribe la tabla `sms_messages` en la base del núcleo** | Una sola base | Mover `sms_messages` a una base o un esquema propio. Para evitar duplicados le basta su propia tabla |
| **Usa `SystemClock` y el `UseCases` del núcleo** en su contenedor | Reutilizar el reloj | Su propio reloj; es una clase de 3 líneas |
| **Las pruebas de integración** crean acuerdos con los casos de uso del núcleo y usan `cobranza.testing.postgres_fixtures` | Probar con acuerdos reales | Con la API: usar un backend levantado o un doble del cliente HTTP. Con datos: sus propias fixtures |
| **El `docker-compose.yml` de la raíz** | Desarrollo local | Su propio compose |

## Pasos

1. Primero, cambiar el uso de la librería por llamadas a la API del backend. Ese cambio se hace dentro de este repositorio.
2. Mover `sms_messages` fuera del esquema del núcleo.
3. Mover `messaging/` a un repositorio nuevo, conservando su historial (`git filter-repo --subdirectory-filter messaging`).
4. Quitar `cobranza` de su `pyproject.toml` y del `Dockerfile`, agregar las pruebas automáticas y publicar la imagen con versión.
