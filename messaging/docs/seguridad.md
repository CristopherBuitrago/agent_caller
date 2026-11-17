# Seguridad de la mensajería

## Qué datos van en un SMS

- **Sí van:** las siglas de la empresa ("L.O.F."), los montos, las fechas y el link de pago.
- **Nunca van:** la palabra "debt", el acreedor, el número de cuenta, el SSN ni la fecha de nacimiento. Otra persona puede ver el teléfono del deudor; decir que es una deuda a un tercero lo prohíbe la FDCPA.
- **El link de pago:** lleva a la página segura del procesador. El sistema nunca ve ni guarda los datos de tarjeta.

## Qué guarda

- **La tabla `sms_messages`:** el texto completo, el teléfono, el tipo de SMS, el estado (reservado, enviado o fallido), el id del proveedor y el error si falló.
- **Los logs:** mientras se usa `LoggingSmsSender`, el texto del SMS y el teléfono quedan en el log. Antes de conectar el proveedor real, el log solo debe guardar el id del mensaje.

## Cumplimiento (pendiente con el abogado, L7)

- **Consentimiento:** enviar SMS de cobranza requiere el consentimiento del deudor y una forma de darse de baja. Hoy cada SMS termina con "Reply STOP to opt out" y el proveedor maneja la baja, pero este sistema no guarda quién se dio de baja.
- **Horario:** la tarea corre en la mañana, hora del este de EE. UU. Con deudores en otras zonas horarias, hay que revisar que el envío caiga dentro del horario permitido de cada uno.
- **Registro del número:** en EE. UU. los SMS comerciales exigen registrar el número (10DLC); está en las preguntas para Vaspian.
- **Revisión legal:** el texto de los SMS lo tiene que revisar el abogado.

## Claves

`DATABASE_URL` y `PII_HMAC_KEY` se leen del entorno. Cuando se conecte Vaspian, su credencial irá en un gestor de secretos, nunca en el repositorio.
