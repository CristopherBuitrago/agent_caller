# Dudas para el jefe

Preguntas que salieron mientras se construían las respuestas a las observaciones. Cada una dice de dónde salió. Cuando haya respuesta, se anota aquí y en `README.md`.

## Pendientes

### 1. Estado de la cuenta cuando se pagan todas las cuotas

Resolviendo la **observación de negocio N10**, que dice: *"Qué pasa después de que el deudor acepta el acuerdo"* (respuesta del jefe: si 5 días después de la fecha la cuota sigue sin pagar, el acuerdo queda roto y la cuenta vuelve a `NSF`).

Salió una nueva duda: **¿qué estado se le pone a la cuenta cuando el deudor paga todas las cuotas?** Hoy el acuerdo pasa a `completed`, pero la cuenta se queda en `PTP`. ¿Pasa a `PAID`, a `CLOSED` o a otro estado del sistema de la empresa?

### 2. Aviso de pago del procesador

Resolviendo la **observación de negocio N10** (y la N1, *"No había forma de que el deudor pagara un pago agendado"*).

Salió una nueva duda: **¿el procesador de pagos puede avisar al sistema cada vez que un pago se aprueba o se rechaza?** Sin ese aviso, el sistema no sabe quién pagó. Mientras tanto, la tarea que marca los acuerdos rotos queda apagada: si corriera, rompería todos los acuerdos. Hace falta saber qué procesador es, si tiene página de pago y si envía ese aviso (*webhook*) o un reporte diario de pagos.

Preguntas concretas (agregadas el 2026-11-13, revisando lo que falta de N10):

- ¿Qué procesador de pagos usa la empresa?
- ¿Tiene una página de pago a la que se pueda enviar al deudor con un link?
- **¿El procesador avisa en el momento cada pago aprobado o rechazado (*webhook*), o entrega un reporte diario de pagos?** Con aviso en el momento, la cuota se marca como pagada al instante; con un reporte diario, se lee el reporte una vez al día.
- ¿Quién puede dar la documentación técnica y los accesos del procesador?

### 4. Número de la línea de entrada

Resolviendo la **observación de negocio N12**, que dice: *"Quien no lograba verificarse se quedaba sin salida"* (respuesta del jefe: el agente le da el número de la línea de entrada que atiende el mismo agente; él entrega el número después).

Falta el dato: **¿cuál es ese número?** Ya está construido: basta con ponerlo en `AGENT_CALLBACK_NUMBER`.

### 5. Vaspian: audio en vivo y SMS

Resolviendo la **observación de negocio N15**, que dice: *"Proveedor de telefonía y programa de los cobradores"* (respuesta del jefe: Vaspian es el marcador, recibe las entrantes y envía los SMS; el CRM es Actos Software, en migración a Lariat Software).

Salieron nuevas dudas:

- **¿Vaspian puede enviar el audio de la llamada en vivo al agente** (por ejemplo, por WebSocket o SIP) y recibir su voz de vuelta? Sin esto, el agente de voz no puede atender llamadas por Vaspian.
- ¿Vaspian tiene una API para **enviar SMS** desde el sistema? ¿Quién puede dar la documentación y las credenciales?
- ¿Cómo se **transfiere** una llamada del agente a la cola de los cobradores, y se puede enviar con la llamada el motivo de la transferencia?

### 6. Disputas: ¿transferir en la llamada o revisar después?

Resolviendo la **observación técnica B5**, que dice: *"Las disputas se guardan sin detalles"* (hoy solo queda la marca de disputa y el estado `DISPUTE`; quien la revisa no sabe cuándo ni cómo dice el deudor que pagó).

Salió una nueva duda (ligada a la duda 5, la transferencia por Vaspian):

- Cuando alguien disputa la deuda, **¿se le transfiere en la misma llamada a un cobrador, o se registra y alguien la revisa después?**
- **¿Su base ya tiene dónde guardar los detalles de una disputa** (fecha del pago, medio, número de confirmación, notas)? Si no, se propone una tabla `disputes` con esos campos.

Mientras tanto, B5 queda en pausa (2026-11-13). El agente preguntará la fecha del pago y el número de confirmación antes de registrar la disputa, para que queden al menos en el resumen de la llamada.

### 7. Todos los códigos de rebote del pago

Resolviendo la **observación técnica B6**, que dice: *"get_account_details no devuelve el motivo del rebote"* (decidido el 2026-11-13: el agente da el motivo solo para R01, fondos insuficientes, y R09, fondos todavía no disponibles; con cualquier otro código dice que un representante puede dar los detalles).

Salió una nueva duda: **necesitamos la lista de todos los códigos de rebote que maneja la empresa** (ACH como R02, R03, R08, R10, y los de cheques y tarjetas, si usan otros). Para cada uno: qué significa y qué debe decir o hacer el agente. Así el agente puede explicarlos todos y no tiene que transferir a un representante solo por eso. Importante saber cuáles se tratan como disputa (por ejemplo, "pago no autorizado").

## Resueltas

### 3. Día de cobro del deudor y fecha del primer pago

Resolviendo la **observación de negocio N8**, que dice: *"El primer pago siempre caía hoy, aunque el deudor pidiera tiempo"* (respuesta del jefe: aprobado hasta fin de mes, y además el agente pregunta cuándo recibe dinero el deudor, por ejemplo "el 5 de cada mes", para poner ahí las fechas).

Salió la duda: **¿qué pasa si el día de cobro cae después del límite del primer pago?** (el 13 de noviembre, el próximo 5 es el 5 de diciembre, pero el primer pago solo puede ir hasta el 30 de noviembre).

**Resuelta por el desarrollador (2026-11-13):** la pregunta por el día de cobro se omite por ahora. Siempre se intenta cobrar hoy; si el deudor pide tiempo, el primer pago va el último día del mes y todas las cuotas siguientes también caen el último día de cada mes (30 nov, 31 dic, 31 ene, 28 feb). Si paga hoy, las cuotas caen el mismo día de cada mes.
