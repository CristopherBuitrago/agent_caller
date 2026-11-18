# Agente de cobranza NSF: lo que falta y no depende del desarrollo

Actualizado: 2026-11-18. Live Oac Financial.

**Dónde estamos:** el backend del agente está construido y probado (419 pruebas automáticas). Todas las observaciones del informe de simulaciones y de la prueba del 2026-11-11 quedaron resueltas, salvo una legal (L7). Lo que sigue en este documento son respuestas, datos y accesos que solo puede dar la empresa. Sin ellos el agente no puede pasar del chat de prueba a llamadas reales.

**Estado:** **Pendiente** = falta la respuesta o el dato · **Por confirmar** = hay una propuesta, falta aprobarla · **Decidida** = ya está definido, falta el acceso o la integración.

## 1. Lo más urgente

| # | Qué falta | Qué desbloquea | Estado |
| --- | --- | --- | --- |
| 1 | Una cuenta de Anthropic de la empresa, con créditos para el piloto y producción. Ya hay una clave de prueba con USD 5 de créditos, con la que se probó el agente con la API real (2026-11-15) | Repetir las 7 simulaciones con Claude Haiku 5.5, el modelo de producción (el criterio es cero errores en montos, verificación y avisos legales), y después el piloto | **Pendiente** |
| 2 | Documentación y credenciales de Vaspian para el audio en vivo (duda 5). **Jefe (2026-11-17): sí puede enviar el audio de la llamada en vivo al agente** | Que el agente atienda llamadas reales por la telefonía que la empresa ya tiene | **Decidida** |
| 3 | El procesador de pagos y su aviso de pago (duda 2) | El link de pago en los SMS y saber quién pagó. Sin el aviso, la tarea que marca los acuerdos rotos sigue apagada | **Pendiente** |
| 4 | El diagrama EER y el acceso a la base real (Actos Software, en migración a Lariat Software) | Conectar el agente a los datos reales de los deudores. Hoy trabaja con 509 deudores simulados | **Pendiente** |

## 2. Dudas para el jefe

Salieron mientras se resolvían las observaciones. La duda 3 ya quedó resuelta.

| # | Tema | Duda y por qué importa | Estado |
| --- | --- | --- | --- |
| 1 | Cuenta pagada | **¿Qué estado se le pone a la cuenta cuando el deudor paga todas las cuotas?** Hoy el acuerdo pasa a `completed`, pero la cuenta se queda en `PTP`. ¿Pasa a `PAID`, a `CLOSED` o a otro estado del sistema de la empresa? **Jefe (2026-11-17):** pasa a `PAID`; falta confirmar el nombre exacto del estado en su sistema. Ya construido: la cuenta pasa a `PAID` con saldo 0 al pagarse la última cuota. **Por qué importa:** Que la cuenta no siga apareciendo como pendiente después de pagar | **Por confirmar** |
| 2 | Procesador de pagos | ¿Cuál usa la empresa? ¿Tiene una página de pago a la que se pueda enviar al deudor con un link? ¿Avisa en el momento cada pago aprobado o rechazado (*webhook*) o entrega un reporte diario? ¿Quién puede dar la documentación técnica y los accesos? **Por qué importa:** Sin esto no hay link de pago real en los SMS y el sistema no sabe quién pagó | **Pendiente** |
| 4 | Número de la línea de entrada | **Número de la línea de entrada** que atiende el agente, para dárselo a quien no logra verificarse. **Jefe (2026-11-17):** todavía no hay número. **Por qué importa:** Ya está construido; solo falta el número | **Pendiente** |
| 5 | Vaspian | **Jefe (2026-11-17): sí puede enviar el audio de la llamada en vivo al agente.** Falta: ¿tiene una API para enviar SMS desde el sistema? ¿Cómo se transfiere una llamada del agente a la cola de los cobradores, y se puede enviar el motivo con la llamada? ¿Quién da la documentación y las credenciales? **Por qué importa:** Es la telefonía de la empresa: de esto depende que el agente pueda llamar, recibir llamadas, mandar SMS y transferir | **Pendiente** |
| 6 | Disputas | Cuando alguien disputa la deuda, ¿se le transfiere en la misma llamada a un cobrador o se registra y alguien la revisa después? ¿La base de la empresa ya guarda los detalles de una disputa (fecha del pago, medio, número de confirmación, notas)? Si no, se propone una tabla con esos campos **Por qué importa:** Hoy solo queda la marca de disputa y el estado `DISPUTE`. Mientras tanto, el agente pregunta la fecha y el número de confirmación y quedan en el resumen | **Pendiente** |
| 7 | Códigos de rebote | La lista de todos los códigos que maneja la empresa (ACH como R02, R03, R08, R10, y los de cheques y tarjetas). Para cada uno: qué significa, qué dice el agente y cuáles se tratan como disputa (por ejemplo, "pago no autorizado") **Jefe (2026-11-17):** la empresa solo maneja el código `NSF` (*Not Sufficient Funds*). Ya aplicado: el agente dice que no había fondos suficientes en la tarjeta o en la cuenta | **Decidida** |
| 8 | Saldo cuota por cuota | Mientras el deudor va pagando las cuotas, el saldo de la cuenta no baja; solo pasa a 0 al pagarse la última. **¿El saldo lo actualiza nuestro sistema con cada pago, o lo maneja el CRM (Actos Software o Lariat Software) y nosotros solo lo leemos?** **Por qué importa:** Que los reportes y el agente muestren el saldo real si el deudor vuelve a llamar con un acuerdo a medio pagar | **Pendiente** |
| 9 | Confirmar el acuerdo por SMS | **Propuesta (2026-11-18):** al cerrar el acuerdo, el deudor recibe durante el día un SMS con un link para confirmarlo. Al confirmar, queda prueba escrita del acuerdo y su consentimiento para los SMS de aviso y de pago. **¿Qué pasa si nunca confirma?** ¿Se reenvía el SMS? ¿Lo llama un cobrador o el agente? ¿En cuántos días? **Por qué importa:** Sin consentimiento no se le envían avisos ni links, y el acuerdo probablemente se rompa. También la revisa el abogado (ver L7) | **Pendiente** |

## 3. Proveedores

Lo que se sabe de cada servicio que necesita una llamada real. Ya están elegidos Claude, la voz a texto, el texto a voz y la orquestación; lo demás espera la respuesta sobre Vaspian y el procesador de pagos.

| Servicio | Proveedor | Qué falta | Estado |
| --- | --- | --- | --- |
| Conversación, resumen y respaldo de la IA | Anthropic: Claude Haiku 5.5, con Claude Sonnet 5.5 de respaldo | Una cuenta de la empresa con créditos (hoy hay una clave de prueba con USD 5) | **Decidida** |
| Telefonía: marcador, llamadas entrantes y grabación | Vaspian (la que ya usa la empresa). La negociación para pasar a Zoom está en pausa | Ya se confirmó que envía el audio en vivo al agente (jefe, 2026-11-17). Falta cómo transfiere a los cobradores (duda 5), y cuánto cuestan los minutos y SMS adicionales del agente según el contrato de la empresa | **Por confirmar** |
| SMS: confirmación, aviso y link de pago | Vaspian | Su API para enviar SMS y las credenciales (duda 5). Hoy los SMS quedan en un registro de prueba | **Por confirmar** |
| Pago con tarjeta (IVR PCI) | Por elegir. Depende de lo que ofrezcan Vaspian y el procesador de pagos | Elegir proveedor y procesador (duda 2). Bloquea la Función 6: el deudor teclea la tarjeta en un sistema certificado y la IA nunca la ve | **Pendiente** |
| Procesador de pagos | Desconocido | Cuál es, página de pago y aviso de pago (duda 2) | **Pendiente** |
| Voz a texto | AssemblyAI Universal-Streaming (~USD 0,0025 por minuto) | Nada. Se eligió por ser unas 3 veces más barato que Deepgram Nova-3 (~USD 240 frente a ~USD 739 al mes) y estar hecho para agentes de voz. Si en el piloto entiende peor el audio telefónico, se cambia a Deepgram sin tocar el resto | **Decidida** |
| Texto a voz | Deepgram Aura-2 (USD 30 por millón de caracteres) | Nada. Es la voz natural más barata encontrada; Amazon Polly Neural (~USD 576) y Deepgram Aura-1 (~USD 540) son más baratos pero suenan más robóticos, y ElevenLabs cuesta entre USD 1.440 y 3.600 al mes | **Decidida** |
| Orquestación de voz | Pipecat (código abierto, sin licencia) | Nada. Une telefonía, voz a texto, Claude y texto a voz, y maneja turnos e interrupciones | **Decidida** |
| Servidores | AWS de la empresa (ya lo usa) | Saber en qué cuenta y región se instala el agente. Sale del cálculo de costos: lo paga la cuenta que la empresa ya tiene | **Decidida** |
| CRM con los datos de los deudores | Actos Software, en migración a Lariat Software | El diagrama EER, el acceso y saber a cuál de los dos se conecta el agente | **Pendiente** |

**Costo estimado con 800 llamadas diarias** (24.000 llamadas y 96.000 minutos al mes; precios de lista del 2026-11-10 y 2026-11-15; el volumen de 800 está sin confirmar):

| Para qué | USD al mes |
| --- | --- |
| Claude: conversación, resúmenes y respaldo | ~166 |
| Telefonía y SMS (Vaspian, ya contratado por la empresa) | Según su contrato (por confirmar) |
| Pago con tarjeta (IVR PCI; estimado con USD 0,20 por pago, proveedor por elegir) | ~480 |
| Voz a texto (AssemblyAI) | ~240 |
| Texto a voz (Deepgram Aura-2) | ~1.080 |
| Orquestación (Pipecat) | 0 |
| **Total** | **~1.966 más Vaspian (~USD 0,08 por llamada más Vaspian)** |

Antes: ~USD 3.789 al mes. Cambia porque la voz a texto pasa a AssemblyAI (~USD 499 menos), los servidores van en el AWS de la empresa (~USD 200 menos) y la telefonía va por Vaspian, que la empresa ya tiene contratado (sale la estimación de ~USD 1.124 de otro proveedor). Falta sumar lo que cobre Vaspian por los minutos y SMS del agente. Los precios de AssemblyAI y Deepgram salen de comparadores y algunas fuentes no coinciden: hay que confirmarlos en sus páginas oficiales antes de contratar. Las comisiones del procesador de pagos no están incluidas: se cobran sobre el dinero recaudado.

## 4. Legal

| # | Tema | Qué hay que revisar | Estado |
| --- | --- | --- | --- |
| L7 | Deudores vulnerables y SMS | Las obligaciones con deudores en situación vulnerable, y el consentimiento, la forma de darse de baja y el texto de los SMS de cobranza. También qué muestra la página de confirmación del acuerdo por SMS y su texto de consentimiento (duda 9). Lo revisa el abogado de la empresa en EE. UU. | **Pendiente** |
