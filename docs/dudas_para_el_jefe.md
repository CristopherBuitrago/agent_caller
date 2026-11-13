# Dudas para el jefe

Preguntas que salieron mientras se construían las respuestas a las observaciones. Cada una dice de dónde salió. Cuando haya respuesta, se anota aquí y en `README.md`.

## Pendientes

### 1. Estado de la cuenta cuando se pagan todas las cuotas

Resolviendo la **observación de negocio N10**, que dice: *"Qué pasa después de que el deudor acepta el acuerdo"* (respuesta del jefe: si 5 días después de la fecha la cuota sigue sin pagar, el acuerdo queda roto y la cuenta vuelve a `NSF`).

Salió una nueva duda: **¿qué estado se le pone a la cuenta cuando el deudor paga todas las cuotas?** Hoy el acuerdo pasa a `completed`, pero la cuenta se queda en `PTP`. ¿Pasa a `PAID`, a `CLOSED` o a otro estado del sistema de la empresa?

### 2. Aviso de pago del procesador

Resolviendo la **observación de negocio N10** (y la N1, *"No había forma de que el deudor pagara un pago agendado"*).

Salió una nueva duda: **¿el procesador de pagos puede avisar al sistema cada vez que un pago se aprueba o se rechaza?** Sin ese aviso, el sistema no sabe quién pagó. Mientras tanto, la tarea que marca los acuerdos rotos queda apagada: si corriera, rompería todos los acuerdos. Hace falta saber qué procesador es, si tiene página de pago y si envía ese aviso (*webhook*) o un reporte diario de pagos.

### 3. Día de cobro del deudor y fecha del primer pago

Resolviendo la **observación de negocio N8**, que dice: *"El primer pago siempre caía hoy, aunque el deudor pidiera tiempo"* (respuesta del jefe: aprobado hasta fin de mes, y además el agente pregunta cuándo recibe dinero el deudor, por ejemplo "el 5 de cada mes", para poner ahí las fechas).

Salió una nueva duda: **¿qué pasa si el día de cobro cae después del límite del primer pago?** Por ejemplo, el 13 de noviembre el próximo 5 es el 5 de diciembre, pero el primer pago solo puede ir hasta el 30 de noviembre.

- **A (recomendada):** el primer pago respeta el límite (hoy o hasta fin de mes) y las cuotas siguientes caen el día de cobro del deudor (por ejemplo, un pago hoy y las demás cuotas el 5 de cada mes).
- **B:** si el día de cobro cae después del límite, el primer pago se pasa a ese día (el 5 de diciembre). Más cómodo para el deudor, pero rompe la regla de fin de mes.
