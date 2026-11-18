# Dudas para el jefe

Preguntas que salieron mientras se construían las respuestas a las observaciones. Cada una dice de dónde salió. Cuando haya respuesta, se anota aquí y en `README.md`.

## Pendientes

### 1. Estado de la cuenta cuando se pagan todas las cuotas

Resolviendo la **observación de negocio N10**, que dice: *"Qué pasa después de que el deudor acepta el acuerdo"* (respuesta del jefe: si 5 días después de la fecha la cuota sigue sin pagar, el acuerdo queda roto y la cuenta vuelve a `NSF`).

Salió una nueva duda: **¿qué estado se le pone a la cuenta cuando el deudor paga todas las cuotas?** Hoy el acuerdo pasa a `completed`, pero la cuenta se queda en `PTP`. ¿Pasa a `PAID`, a `CLOSED` o a otro estado del sistema de la empresa?

**Jefe (2026-11-17):** cuando se paga la cuenta, pasa a `PAID`. Falta que confirme el nombre exacto del estado en su sistema.

Construido el 2026-11-17: al completarse el acuerdo, la cuenta pasa a `PAID` con saldo 0. Si el nombre real es otro, se cambia en un solo lugar.

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

**Jefe (2026-11-17):** todavía no hay número.

### 5. Vaspian: audio en vivo y SMS

Resolviendo la **observación de negocio N15**, que dice: *"Proveedor de telefonía y programa de los cobradores"* (respuesta del jefe: Vaspian es el marcador, recibe las entrantes y envía los SMS; el CRM es Actos Software, en migración a Lariat Software).

Salieron nuevas dudas:

- **¿Vaspian puede enviar el audio de la llamada en vivo al agente** (por ejemplo, por WebSocket o SIP) y recibir su voz de vuelta? Sin esto, el agente de voz no puede atender llamadas por Vaspian.
- ¿Vaspian tiene una API para **enviar SMS** desde el sistema? ¿Quién puede dar la documentación y las credenciales?
- ¿Cómo se **transfiere** una llamada del agente a la cola de los cobradores, y se puede enviar con la llamada el motivo de la transferencia?

**Jefe (2026-11-17):** **sí, Vaspian puede enviar el audio de la llamada en vivo al agente.** Siguen pendientes la API de SMS, la transferencia con el motivo, la documentación y las credenciales.

### 6. Disputas: ¿transferir en la llamada o revisar después?

Resolviendo la **observación técnica B5**, que dice: *"Las disputas se guardan sin detalles"* (hoy solo queda la marca de disputa y el estado `DISPUTE`; quien la revisa no sabe cuándo ni cómo dice el deudor que pagó).

Salió una nueva duda (ligada a la duda 5, la transferencia por Vaspian):

- Cuando alguien disputa la deuda, **¿se le transfiere en la misma llamada a un cobrador, o se registra y alguien la revisa después?**
- **¿Su base ya tiene dónde guardar los detalles de una disputa** (fecha del pago, medio, número de confirmación, notas)? Si no, se propone una tabla `disputes` con esos campos.

Mientras tanto, B5 queda en pausa (2026-11-13). El agente preguntará la fecha del pago y el número de confirmación antes de registrar la disputa, para que queden al menos en el resumen de la llamada.

### 8. El saldo no baja cuota por cuota

Resolviendo la **duda 1** (cuenta pagada), que viene de la **observación de negocio N10**, que dice: *"Qué pasa después de que el deudor acepta el acuerdo"* (respuesta del jefe, 2026-11-17: al pagarse todas las cuotas la cuenta pasa a `PAID`; construido con saldo 0).

Salió una nueva duda: **mientras el deudor va pagando las cuotas, el saldo de la cuenta no baja**. Solo pasa a 0 cuando se paga la última. ¿El saldo lo debe ir actualizando nuestro sistema con cada pago, o lo maneja el CRM de la empresa (Actos Software o Lariat Software) y nosotros solo lo leemos? Importa para que los reportes y lo que dice el agente muestren el saldo real si el deudor vuelve a llamar con un acuerdo a medio pagar.

### 9. Confirmar el acuerdo con un link por SMS

Resolviendo el **hallazgo 5 de las simulaciones con Haiku** (2026-11-18), que dice: *"El agente no sabía explicar cómo se paga"* (ya corregido: el agente explica que llega un SMS de confirmación, un aviso 3 días antes y un link de pago seguro el día de cada cuota).

Salió una propuesta nueva (2026-11-18). Al cerrar el acuerdo, el agente diría: *"Today you'll get a text with a link to confirm your arrangement. Once you confirm it, we'll send you a reminder three days before each payment and a secure payment link on each payment date."*

Durante el día llega un SMS con un link a una página de la empresa. Ahí el deudor ve sus montos y fechas y toca "Confirmar". Con eso:

- queda prueba escrita de que aceptó el acuerdo;
- da su consentimiento para recibir los SMS de aviso y de pago;
- se confirma que su número recibe SMS.

No hace falta que el SMS llegue al instante: basta con que Vaspian tenga una API para enviar SMS (duda 5).

Preguntas:

- **Para el jefe: ¿qué pasa si el deudor nunca confirma?** Sin su consentimiento no se le enviarían los avisos ni los links, y el acuerdo probablemente se rompería a los 5 días. ¿Se le reenvía el SMS una vez? ¿Lo llama un cobrador o el agente? ¿En cuántos días?
- **Para el abogado (con L7): qué muestra la página y qué texto de consentimiento usa.** Si otra persona abre el link en el teléfono del deudor, ver montos y un acreedor puede revelar la deuda. Se propone pedir un dato antes de mostrarla (por ejemplo, los últimos 4 del SSN).

Se construye cuando el jefe y el abogado respondan y Vaspian confirme su API de SMS. Es una página web nueva y toca el modelo de datos (el link, su vencimiento, la fecha de confirmación y el consentimiento): los campos se presentan antes de construir.

## Resueltas

### 7. Todos los códigos de rebote del pago

Resolviendo la **observación técnica B6**, que dice: *"get_account_details no devuelve el motivo del rebote"* (decidido el 2026-11-13: el agente da el motivo solo para R01, fondos insuficientes, y R09, fondos todavía no disponibles; con cualquier otro código dice que un representante puede dar los detalles).

Salió una nueva duda: **necesitamos la lista de todos los códigos de rebote que maneja la empresa** (ACH como R02, R03, R08, R10, y los de cheques y tarjetas, si usan otros). Para cada uno: qué significa y qué debe decir o hacer el agente. Así el agente puede explicarlos todos y no tiene que transferir a un representante solo por eso. Importante saber cuáles se tratan como disputa (por ejemplo, "pago no autorizado").

**Jefe (2026-11-17):** la empresa solo maneja un código: `NSF` (*Not Sufficient Funds*, fondos insuficientes). No usa los códigos ACH (R01, R09, etc.).

### 3. Día de cobro del deudor y fecha del primer pago

Resolviendo la **observación de negocio N8**, que dice: *"El primer pago siempre caía hoy, aunque el deudor pidiera tiempo"* (respuesta del jefe: aprobado hasta fin de mes, y además el agente pregunta cuándo recibe dinero el deudor, por ejemplo "el 5 de cada mes", para poner ahí las fechas).

Salió la duda: **¿qué pasa si el día de cobro cae después del límite del primer pago?** (el 13 de noviembre, el próximo 5 es el 5 de diciembre, pero el primer pago solo puede ir hasta el 30 de noviembre).

**Resuelta por el desarrollador (2026-11-13):** la pregunta por el día de cobro se omite por ahora. Siempre se intenta cobrar hoy; si el deudor pide tiempo, el primer pago va el último día del mes y todas las cuotas siguientes también caen el último día de cada mes (30 nov, 31 dic, 31 ene, 28 feb). Si paga hoy, las cuotas caen el mismo día de cada mes.
