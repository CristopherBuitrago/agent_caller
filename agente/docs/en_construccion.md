# En construcción: agente

Lo técnico que falta en este servicio. Lo que espera respuesta de la empresa está en el [`PENDIENTES.md` de la raíz](../../PENDIENTES.md).

| Qué | Estado | Depende de |
| --- | --- | --- |
| **Capa de voz con Pipecat:** voz a texto con AssemblyAI, texto a voz con Deepgram Aura-2, turnos e interrupciones. Usa la misma `AgentSession` de hoy; solo cambian la entrada y la salida | Por hacer; se puede probar con el micrófono antes de tener Vaspian | Las claves de AssemblyAI y Deepgram |
| **Conexión con Vaspian:** recibir y hacer llamadas con el audio en vivo, y transferir a la cola de los cobradores con el motivo | Por hacer | Documentación y credenciales de Vaspian (formato del audio, transferencia) |
| **Marcador de salientes:** toma la lista diaria del backend, respeta el horario y tiene un máximo de llamadas simultáneas (por ejemplo, 5 al inicio) | Por hacer; se puede probar con una telefonía falsa | — |
| **Latencia:** medir el tiempo de cada turno (voz a texto, Claude y texto a voz) y registrarlo para el reporte del piloto | Por hacer | Capa de voz |
| **Prueba de carga:** unas 20 llamadas simuladas al mismo tiempo, con otra IA haciendo de deudor | Por hacer | Capa de voz o telefonía falsa |
| **Hallazgos de las simulaciones con Haiku (2026-11-18):** frases antes de verificar, Hardship Questions en orden, dudas sobre quién contesta, cómo se paga y detalles menores (ver `simulaciones/2026-11-18/informe.md`) | Por decidir, uno a la vez | — |
| **Ajustes vistos con la API real:** decir los montos en palabras ("four hundred fifty dollars") y no decir "I'm calling from" en las entrantes | Por hacer | — |
| **Historial sin la fecha de nacimiento** (ver `seguridad.md`) | Por hacer | Antes de usar datos reales |
| **Llamadas abiertas en memoria:** hoy un solo proceso atiende todas. Con voz, cada llamada correrá en su propia sesión de Pipecat | Por definir con la capa de voz | — |
