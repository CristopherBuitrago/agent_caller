# Agente de cobranza NSF: lo que falta y no depende del desarrollo

Actualizado: 2026-11-13. Live Oak Financial.

**Dónde estamos:** el backend del agente está construido y probado (419 pruebas automáticas). Todas las observaciones del informe de simulaciones y de la prueba del 2026-11-11 quedaron resueltas, salvo una legal (L7). Lo que sigue en este documento son respuestas, datos y accesos que solo puede dar la empresa. Sin ellos el agente no puede pasar del chat de prueba a llamadas reales.

**Estado:** **Pendiente** = falta la respuesta o el dato · **Por confirmar** = hay una propuesta, falta aprobarla · **Decidida** = ya está definido, falta el acceso o la integración.

## 1. Lo más urgente

| # | Qué falta | Qué desbloquea | Estado |
| --- | --- | --- | --- |
| 1 | La clave de la API de Anthropic (`ANTHROPIC_API_KEY`) | Probar el agente con Claude Haiku 5.5, el modelo de producción. Con ella se repiten las 7 simulaciones; el criterio es cero errores en montos, verificación y avisos legales | **Pendiente** |
| 2 | Saber si Vaspian puede enviar el audio de la llamada en vivo al agente (duda 5) | Que el agente atienda llamadas reales. Si Vaspian no puede, hace falta otro proveedor de telefonía | **Pendiente** |
| 3 | El procesador de pagos y su aviso de pago (duda 2) | El link de pago en los SMS y saber quién pagó. Sin el aviso, la tarea que marca los acuerdos rotos sigue apagada | **Pendiente** |
| 4 | El diagrama EER y el acceso a la base real (Actos Software, en migración a Lariat Software) | Conectar el agente a los datos reales de los deudores. Hoy trabaja con 509 deudores simulados | **Pendiente** |

## 2. Dudas para el jefe

Salieron mientras se resolvían las observaciones. La duda 3 ya quedó resuelta.

| # | Tema | Duda y por qué importa | Estado |
| --- | --- | --- | --- |
| 1 | Cuenta pagada | **¿Qué estado se le pone a la cuenta cuando el deudor paga todas las cuotas?** Hoy el acuerdo pasa a `completed`, pero la cuenta se queda en `PTP`. ¿Pasa a `PAID`, a `CLOSED` o a otro estado del sistema de la empresa? (sale de N10) **Por qué importa:** Que la cuenta no siga apareciendo como pendiente después de pagar | **Pendiente** |
| 2 | Procesador de pagos | ¿Cuál usa la empresa? ¿Tiene una página de pago a la que se pueda enviar al deudor con un link? ¿Avisa en el momento cada pago aprobado o rechazado (*webhook*) o entrega un reporte diario? ¿Quién puede dar la documentación técnica y los accesos? (sale de N1 y N10) **Por qué importa:** Sin esto no hay link de pago real en los SMS y el sistema no sabe quién pagó | **Pendiente** |
| 4 | Número de la línea de entrada | **Número de la línea de entrada** que atiende el agente, para dárselo a quien no logra verificarse (sale de N12) **Por qué importa:** Ya está construido; solo falta el número | **Pendiente** |
| 5 | Vaspian | ¿Puede enviar el audio de la llamada en vivo al agente (por ejemplo, por WebSocket o SIP) y recibir su voz de vuelta? ¿Tiene una API para enviar SMS desde el sistema? ¿Cómo se transfiere una llamada del agente a la cola de los cobradores, y se puede enviar el motivo con la llamada? ¿Quién da la documentación y las credenciales? (sale de N15) **Por qué importa:** Es la telefonía de la empresa: de esto depende que el agente pueda llamar, recibir llamadas, mandar SMS y transferir | **Pendiente** |
| 6 | Disputas | Cuando alguien disputa la deuda, ¿se le transfiere en la misma llamada a un cobrador o se registra y alguien la revisa después? ¿La base de la empresa ya guarda los detalles de una disputa (fecha del pago, medio, número de confirmación, notas)? Si no, se propone una tabla con esos campos (sale de B5) **Por qué importa:** Hoy solo queda la marca de disputa y el estado `DISPUTE`. Mientras tanto, el agente pregunta la fecha y el número de confirmación y quedan en el resumen | **Pendiente** |
| 7 | Códigos de rebote | La lista de todos los códigos que maneja la empresa (ACH como R02, R03, R08, R10, y los de cheques y tarjetas). Para cada uno: qué significa, qué dice el agente y cuáles se tratan como disputa (por ejemplo, "pago no autorizado") (sale de B6) **Por qué importa:** Hoy el agente solo explica R01 y R09; con cualquier otro dice que un representante puede dar los detalles | **Pendiente** |

## 3. Proveedores

Lo que se sabe de cada servicio que necesita una llamada real. La conversación con Claude ya está elegida; el resto espera aprobación o la respuesta sobre Vaspian.

| Servicio | Proveedor | Qué falta | Estado |
| --- | --- | --- | --- |
| Conversación, resumen y respaldo de la IA | Anthropic: Claude Haiku 5.5, con Claude Sonnet 5.5 de respaldo | La clave de la API | **Decidida** |
| Telefonía: marcador, llamadas entrantes y grabación | Vaspian (la que ya usa la empresa). La negociación para pasar a Zoom está en pausa | Confirmar que envía el audio en vivo al agente y cómo transfiere a los cobradores (duda 5). Si no puede, se propuso Telnyx Voice API (~USD 1.124 al mes con 800 llamadas diarias) | **Por confirmar** |
| SMS: confirmación, aviso y link de pago | Vaspian | Su API para enviar SMS y las credenciales (duda 5). Hoy los SMS quedan en un registro de prueba | **Por confirmar** |
| Pago con tarjeta (IVR PCI) | Por elegir. Se propuso Telnyx Pay over Voice, pero depende de la telefonía y del procesador | Elegir proveedor y procesador (duda 2). Bloquea la Función 6: el deudor teclea la tarjeta en un sistema certificado y la IA nunca la ve | **Pendiente** |
| Procesador de pagos | Desconocido | Cuál es, página de pago y aviso de pago (duda 2) | **Pendiente** |
| Voz a texto | Deepgram Nova-3 | Aprobar (~USD 739 al mes con 800 llamadas diarias) | **Por confirmar** |
| Texto a voz | Deepgram Aura-2 | Aprobar (~USD 1.080 al mes con 800 llamadas diarias) | **Por confirmar** |
| Orquestación de voz | Pipecat (código abierto, sin licencia) | Aprobar | **Por confirmar** |
| Servidores y base de datos | AWS, este de EE. UU. | Aprobar (~USD 200 al mes), o usar los servidores y la base de la empresa | **Por confirmar** |
| CRM con los datos de los deudores | Actos Software, en migración a Lariat Software | El diagrama EER, el acceso y saber a cuál de los dos se conecta el agente | **Pendiente** |

**Costo estimado con 800 llamadas diarias** (precios de lista del 2026-11-10; el volumen de 800 está sin confirmar):

| Para qué | USD al mes |
| --- | --- |
| Claude: conversación, resúmenes y respaldo | ~166 |
| Telefonía (con Telnyx; si es Vaspian, se reemplaza por su precio) | ~1.124 |
| Pago con tarjeta (IVR PCI, a confirmar) | ~480 |
| Voz a texto y texto a voz (Deepgram) | ~1.819 |
| Servidores (AWS) | ~200 |
| **Total** | **~3.789 (~USD 0,16 por llamada)** |

Si la telefonía y los SMS van por Vaspian, la fila de telefonía cambia por lo que cobre Vaspian, que la empresa ya paga. Las comisiones del procesador de pagos no están incluidas: se cobran sobre el dinero recaudado.

## 4. Legal

| # | Tema | Qué hay que revisar | Estado |
| --- | --- | --- | --- |
| L7 | Deudores vulnerables y SMS | Las obligaciones con deudores en situación vulnerable, y el consentimiento, la forma de darse de baja y el texto de los SMS de cobranza. Lo revisa el abogado de la empresa en EE. UU. | **Pendiente** |
