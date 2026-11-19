# En construcción: agente

Lo técnico que falta en este servicio. Lo que espera respuesta de la empresa está en el [`PENDIENTES.md` de la raíz](../../PENDIENTES.md).

| Qué | Estado | Depende de |
| --- | --- | --- |
| **Capa de voz con Pipecat 1.16:** detección de voz (Silero), AssemblyAI, turnos (`UserTurnProcessor`), la misma `AgentSession` (`voice/agent_processor.py`), Deepgram Aura-2 y WebRTC en el navegador (`voice/bot.py`, servicio `voz` del compose, puerto 7860) | **Estructura construida y probada sin audio (2026-11-18):** 6 pruebas del puente y el flujo completo arma con las piezas reales. **Falta escucharla.** Riesgo: el audio de WebRTC usa puertos UDP que quizás no salgan del contenedor (Podman en Windows); si falla, correr el bot fuera del contenedor o pasar a un transporte por WebSocket | Nada: las claves de AssemblyAI y Deepgram están en el `.env` desde el 2026-11-18 |
| **Conexión con Vaspian:** recibir y hacer llamadas con el audio en vivo, y transferir a la cola de los cobradores con el motivo | Por hacer | Documentación y credenciales de Vaspian (formato del audio, transferencia) |
| **Marcador de salientes:** toma la lista diaria del backend, respeta el horario y tiene un máximo de llamadas simultáneas (por ejemplo, 5 al inicio) | Por hacer; se puede probar con una telefonía falsa | — |
| **Latencia:** medir el tiempo de cada turno (voz a texto, Claude y texto a voz) y registrarlo para el reporte del piloto | Por hacer | Capa de voz |
| **Prueba de carga:** unas 20 llamadas simuladas al mismo tiempo, con otra IA haciendo de deudor | Por hacer | Capa de voz o telefonía falsa |
| **Filtro antes de hablar (opción C del hallazgo 2):** revisar cada respuesta del agente antes de decirla y frenarla si trae palabras prohibidas sin verificación | Para después | La capa de voz (para medir cuánta demora agrega) |
| **Ajustes vistos con la API real:** decir los montos en palabras ("four hundred fifty dollars") y no decir "I'm calling from" en las entrantes | Por hacer | — |
| **Historial sin la fecha de nacimiento** (ver `seguridad.md`) | Por hacer | Antes de usar datos reales |
| **Llamadas abiertas en memoria:** hoy un solo proceso atiende todas. Con voz, cada llamada correrá en su propia sesión de Pipecat | Por definir con la capa de voz | — |

## Riesgos de la capa de voz (2026-11-18)

| # | Riesgo | Qué pasa si se da | Qué hacer |
| --- | --- | --- | --- |
| 1 | **WebRTC dentro del contenedor.** El audio usa puertos UDP aleatorios y con Podman en Windows quizás no salgan del contenedor | El navegador conecta pero no hay audio | Correr el bot fuera del contenedor, directo en Windows, o cambiar a un transporte por WebSocket (más parecido a como Vaspian enviaría el audio) |
| 2 | **Demora por turno.** El agente no empieza a hablar hasta que Claude termina toda la respuesta, incluidas las herramientas; se suma la espera de 0,25 s por la transcripción y el inicio del texto a voz | Se pasa la meta de 1,5 s del piloto (criterio 2.2) y la conversación se siente lenta | Medir con los logs del puente y las métricas de Pipecat. Si se pasa: que Claude envíe la respuesta por partes y el texto a voz arranque con la primera frase, bajar la espera de 0,25 s, o usar un detector de fin de turno más rápido |
| 3 | **Interrupciones.** Si el deudor interrumpe, Pipecat corta el audio, pero la transcripción del agente guarda la frase completa | El resumen y el historial dicen cosas que el deudor no alcanzó a oír | Registrar en la AgentSession hasta dónde se dijo la respuesta cuando hay una interrupción |
| 4 | **El orden de los mensajes con audio real.** Las pruebas cubren que la transcripción llegue antes o después del fin del turno, pero con audio real puede haber turnos sin texto, textos sin fin de turno o pausas largas | El agente no contesta, o contesta a medias | Probarlo con las claves: frases cortas, largas, con pausas y con interrupciones |
| 5 | **Calidad de voz a texto con audio telefónico** (8 kHz por Vaspian, peor que el micrófono del navegador) | AssemblyAI entiende mal nombres, números del SSN o fechas, y la verificación falla aunque los datos estén bien | Probar con audio telefónico real. Si falla, cambiar a Deepgram Nova-3 (está detrás de la misma interfaz) |
| 6 | **Pipecat cambia seguido.** Ya marca piezas que se eliminan en la versión 2.0 | Una actualización rompe el bot | Mantener la versión fija (1.16.0) y actualizar a propósito, con las pruebas del puente |
| 7 | **Costo real por llamada sin medir** (voz a texto y texto a voz se cobran por minuto y por carácter) | El costo estimado (~USD 1.966 al mes con 800 llamadas diarias) no se cumple | Medir en las primeras pruebas y en el piloto |
| 8 | **La voz del agente no está elegida** (`aura-2-helena-en` por defecto) | La voz puede no gustarle a la empresa o sonar poco natural por teléfono | Probar 2 o 3 voces de Aura-2 y que el jefe elija |

### Cómo probar el riesgo 1 (eco por WebRTC, sin claves)

`voice/echo_bot.py` devuelve por el parlante lo que entra por el micrófono, sin IA. Usar audífonos.

1. Levantarlo:
   - **Docker:** `docker compose run --rm --service-ports voz python -m cobranza_agent.infrastructure.voice.echo_bot --host 0.0.0.0 --port 7860` y abrir http://localhost:7860/client/
   - **Podman en Windows (PC de la oficina, 2026-11-18):** `localhost` no llega al contenedor. Hay que correrlo con `--network host` y entrar por la IP de la máquina de Podman (`wsl -d podman-machine-default -u root -- ip -4 addr show eth0`). Esa IP cambia al reiniciar.
2. Si la página no está en `localhost`, el navegador bloquea el micrófono. En `chrome://flags/#unsafely-treat-insecure-origin-as-secure` (o en `edge://flags`), agregar la dirección y reiniciar el navegador.
3. Conectarse, permitir el micrófono y hablar. Los logs del bot dicen cuántos pedazos de audio entraron y volvieron.

Cómo leer el resultado:
- **Se oye el eco:** el transporte funciona.
- **Conecta pero no se oye nada:** el audio UDP no sale del contenedor. Primero probar con la red del host (`network_mode: host` en el servicio `voz`). Si sigue sin funcionar, correr el bot fuera del contenedor o cambiar a WebSocket.
