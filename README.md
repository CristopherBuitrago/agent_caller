# Agente de voz de cobranza NSF: registro de decisiones

Actualizado: 2026-11-11

Este documento registra cada decisión de negocio, quién la tomó y las palabras con las que se respondió. Las respuestas están citadas tal como se escribieron, con sus errores de tipeo.

Documento de arquitectura: https://claude.ai/artifact/CLGgKwmBLiJpngybRoFjtu

Documento enviado al jefe para revisión (versión 3, 2026-11-10): `docs/Backend_Agente_Cobranza_NSF_v3.pdf`. Diagrama EER del modelo actual: `docs/diagrama_eer_modelo_actual.jpg`. El PDF se escribió antes de terminar el paso 8: donde dice "en construcción" o "sin probar", vale lo de este README.

Cómo leer la columna **Origen**:

- **Jefe:** el desarrollador consultó las preguntas con el jefe y trajo sus respuestas.
- **Desarrollador:** respondió el desarrollador. En el registro no consta si lo consultó con el jefe.
- **Claude:** lo propuso Claude. La columna de respuesta indica si fue aprobado.

## Resumen por función (2026-11-08)

Las funciones 1 a 5 y la 7 tienen sus preguntas respondidas y están construidas. Solo la Función 6 está detenida. Las reglas que nadie confirmó quedaron como supuestos vigentes (sección 4) y no detienen ninguna función.

### Base: modelo de datos

| Pregunta | Respuesta | Origen |
| --- | --- | --- |
| ¿Qué estados de pago se cobran? | Solo NSF. Cualquier otro estado, incluidos `first_attempt` a `fourth_attempt`, pasa a una persona | Jefe; confirmado por el desarrollador el 2026-11-08 |
| ¿Varias deudas por deudor? | "Sí, pueden ser del mismo o diferentes" → tablas `debtors` y `accounts` separadas | Jefe |
| ¿Hay datos del NSF? | "Sí" | Jefe |
| ¿Hay estado o dirección del deudor? | Pueden faltar; después de `fourth_attempt` se usa Skip Tracing | Jefe |
| ¿Los estados de intento van en el mismo campo que NSF? | "Sí, vienen en el mismo campo" | Desarrollador |
| ¿Hay nombres de campos fijos? | "Sí", vendrán en el EER; mientras tanto se usa el modelo actual | Jefe |

**Pendiente (no impide avanzar):** el diagrama EER y la base de datos real, y si el resultado de la llamada se inserta como fila nueva o actualiza un registro existente.

### Función 1: consultar deudor

| Pregunta | Respuesta |
| --- | --- |
| ¿Cómo se identifica a quien llama? | "agente recibe num y busca" (por el teléfono) |
| ¿Cómo entrega el resultado el job de NSF (salientes)? | Primero "Por definir". Respondido el 2026-11-12: no hay job externo; el sistema consulta la base cada día y arma la lista de salientes del día. Si un deudor de la lista llama antes y verifica su identidad, se le saca (ver "Lista diaria de llamadas salientes") |
| Saliente sin ubicación | "Se hace la cobranza normal y se deduce por el codigo de area" |

### Función 2: verificar identidad

| Pregunta | Respuesta |
| --- | --- |
| ¿Qué datos se verifican? | Nombre completo + últimos 4 del SSN + fecha de nacimiento |
| ¿Dónde se cuentan los intentos? | En un campo nuevo, `verification_attempts`, aparte del estado del NSF |
| ¿Bloquear tras 5 fallos en 24 h? | "Listo si" (propuesta de Claude) |
| ¿Pedir deletrear el apellido antes de contar un fallo? | "Perfecto" (propuesta de Claude) |
| ¿Qué pasa si quien llama cambia de nombre entre intentos? (S1, simulación 8: dijo "Paul Carter", falló, y luego "Jane Carter" pasó) | Se cierra la llamada con un resultado nuevo, `identity_mismatch`, sin revisar los datos del segundo nombre, y se le pide llamar de nuevo con sus datos; después se le vuelve a llamar. Decidido por el desarrollador el 2026-11-12 |
| ¿Cuándo se pide deletrear el apellido? (S2, simulación 8: se pedía aunque fallara el nombre de pila y antes de revisar SSN y fecha) | Solo cuando el SSN, la fecha y el nombre de pila coinciden y lo único que no coincide es el apellido (error típico al transcribir la voz). Cualquier otro fallo es un intento fallido normal, sin decir qué dato falló. Opción A, elegida por el desarrollador el 2026-11-12 |
| ¿Quitar el nombre y que el agente lea el SSN y la fecha para que el deudor confirme? (N2, pedido del jefe) | Se deja como está: el deudor dice nombre completo, últimos 4 del SSN y fecha de nacimiento (opción A). "Ya lo dejamos en un punto intermedio, si luego mi jefe pide pasar a la opcion C, se hace porque son ordenes de mi jefe". Alerta: leerle los datos al deudor los revela a quien conteste y no se puede con el diseño actual (datos guardados como hash). **Confirmado por el jefe (2026-11-13):** "Se deja como está: el deudor dice su nombre completo, los últimos 4 del SSN y su fecha de nacimiento porque leerle los datos los revela a quien conteste y no se puede con el diseño actual" | Desarrollador, 2026-11-12; jefe, 2026-11-13 |
| ¿Qué se le ofrece a quien no logra verificarse? (N12, prueba 6) | Opción A, elegida por el desarrollador el 2026-11-12 (por validar con el jefe, "es muy probable que sea la via correcta"): al cerrar por verificación fallida o por cambio de nombre (S1), el agente da el número de la línea de entrada que atiende el mismo agente: "If you'd like, you can call us back at [number] whenever you have your information handy". Si no devuelve la llamada, sigue en la lista diaria. El número se configura con `AGENT_CALLBACK_NUMBER`; mientras no exista, no se ofrece | Desarrollador |

**Supuestos:**
- Máximo 2 fallos por llamada.
- S1 compara solo el nombre de pila: corregir la ortografía del apellido (lo que pide `name_retry`) o agregar un segundo nombre no cuenta como cambio. El intento con el nombre cambiado cuenta como fallido para el bloqueo de 24 horas.

### Función 3: registrar la llamada y resumen

| Pregunta | Respuesta |
| --- | --- |
| ¿Aviso de grabación? | Sí, al inicio de cada llamada |
| ¿Qué pasa si el deudor no acepta la grabación? | "Por ley se tiene que grabar" → se cierra como `recording_refused` sin hablar de la deuda |
| ¿La IA genera el resumen? | "Si, que lo genere la IA" |
| ¿Con qué modelo? | Claude Haiku 5.5, con Claude Sonnet 5.5 como respaldo |
| ¿En qué idioma va el resumen? | Inglés: "todos ahi hablan ingles y el servicio es para estados unidos" (2026-11-08) |
| ¿Cuándo se avisa de la grabación en las salientes? (N3) | Opción A, elegida por el desarrollador el 2026-11-12: el saludo solo pregunta por el deudor ("Hi, may I speak with Jane Carter, please?"); cuando la persona confirma que es el deudor, el agente se identifica y da el aviso; recién con su "sí" se verifica la identidad. La grabación empieza con ese "sí" (`RecordRecordingConsent` llama a `CallRecorder.start`): a un tercero que conteste no se le dice nada ni se le graba. Se pidió avisar después de verificar, pero la verificación pide SSN y fecha, y estados como Florida exigen el consentimiento de todas las partes antes de grabar. En las entrantes el aviso sigue en el saludo |

**Pendiente:** falta `ANTHROPIC_API_KEY` para probar el resumen con la API real.
**Alerta:** ninguna ley federal obliga a grabar, hasta donde sabe Claude; falta confirmar de dónde sale esa regla (alerta 2).

### Función 4: negociar el acuerdo

| Pregunta | Respuesta |
| --- | --- |
| ¿Descuentos? | "JAMÁS… siempre se le cobra todo" |
| ¿Mínimo del pago parcial? | Al menos el 10%; también aplica a la primera cuota |
| Orden de las ofertas | "intentar todo de una, si no, a dos cuotas, despues si dice que le queda complejo a 3, pero siempre por lo más rapido" |
| ¿Cómo son las cuotas? | "el deudor no propone, acepta, tienen que ser iguales y con frecuencia fija" |
| ¿Cada cuánto se paga? | "Cuotas mensuales fecha establecida" (Jefe; reemplazó la quincenal) |
| Plazo máximo del plan | 1 año |
| ¿Cuándo es el primer pago? | Primero: en unos días, máximo 8 ("Si, se puede pagar a 8 dias", Jefe). Cambiado el 2026-11-12 (N8, por confirmar con el jefe): siempre se intenta hoy; si el deudor pide tiempo, hasta fin de este mes, "teniendo en cuenta que ahi es donde le pagan a casi todas las personas". Si faltan menos de 8 días para fin de mes, el agente pregunta primero si puede pagar el último día de este mes y, si no, hasta fin del mes siguiente. La herramienta le dice al agente la fecha límite (resuelve también B7). **Cambiado el 2026-11-13 (desarrollador):** la pregunta del jefe por el día de cobro del deudor se omite por ahora; si el deudor pide tiempo, el primer pago va el último día del mes y todas las cuotas siguientes también caen el último día de cada mes (30 nov, 31 dic, 31 ene, 28 feb). Si paga hoy, las cuotas caen el mismo día de cada mes |
| ¿Cuándo se paga el resto de un parcial? | "normalmente es al mes" → 30 días |
| ¿Se acepta menos del 10%? | "en cos muy específicos" → piso de 5%, como último recurso |
| ¿Qué estado queda tras el acuerdo? | `PTP`; `RCC` queda fuera del alcance |
| ¿Qué pasa después de `PTP`? | Primero: la llamada de recordatorio la hace un cobrador. Cambiado el 2026-11-12 (N10, opción A con condiciones del desarrollador): un SMS solo de aviso 3 días antes de cada cuota y el link de pago el día de la cuota (N1); los cobradores ya no hacen recordatorios. Si 5 días después de la fecha la cuota sigue sin pagar, el acuerdo pasa a `broken`. **Jefe (2026-11-12):** la cuenta vuelve a `NSF` (entra de nuevo a la lista diaria) y sin alerta por Teams, porque la empresa revisa los acuerdos rotos con reportes semanales y mensuales. Construido el 2026-11-13: `RecordPaymentResult` registra cada pago (cuota `paid`; con todas pagadas, acuerdo `completed`) y `BreakOverdueArrangements` rompe los vencidos (cuotas pendientes `cancelled`, cuenta `NSF`). La tarea diaria `break_overdue_arrangements` solo corre con `PAYMENT_RESULTS_CONNECTED=true`, porque sin el aviso del procesador ninguna cuota aparece pagada. Pendiente: el estado de la cuenta cuando se pagan todas las cuotas (hoy no se cambia) |
| ¿Hay que recorrer ofertas que el deudor ya descartó? (N4) | Opción A', elegida por el desarrollador el 2026-11-12: si el deudor dice cuánto puede pagar por cuota, el sistema salta las ofertas con cuotas mayores y lo deja en el registro de la llamada con el motivo. Nunca salta la oferta de 3 cuotas antes de las Hardship Questions ni la última después (desde N5, el pago inicial más 12 cuotas): decir "solo puedo 30" no evita las preguntas. El agente presenta esas ofertas como "la opción más baja disponible ahora", sin mencionar mínimos |
| ¿El agente puede decir que "la normativa exige al menos el 20%" para presionar? | No. Lo propuso el desarrollador para que nadie se escude en un monto bajo. Se descartó porque afirmar una regla que no existe es una práctica engañosa que prohíbe la FDCPA (sección 1692e) y contradice la decisión inicial de negociar sin presionar. La opción A' logra el mismo efecto diciendo la verdad. La idea de "10% en el primer pago y luego cuotas normales" se verá con N5 y N6 |
| ¿Qué pasa si lo que puede pagar el deudor no alcanza ni para 10 cuotas? (N5) | Opción A, la idea del desarrollador dentro de las reglas vigentes (plazo de 1 año y mínimo del 10%), elegida el 2026-11-12: después de las Hardship Questions, la última oferta es un primer pago del 10% y el resto en 12 cuotas mensuales iguales (13 pagos en 1 año). Con USD 485: 48,50 hoy, 36,43 y luego 11 de 36,37. Si tampoco puede, el agente ofrece el parcial de último recurso (N6) y, si no, transfiere a una persona. Reemplaza el supuesto de "máximo 10 cuotas" |
| ¿Cómo se paga el resto de un parcial? (N6, prueba 1: USD 90 hoy y USD 395 a 30 días para alguien con USD 300 al mes) | Opción A, elegida por el desarrollador el 2026-11-12: si el deudor dice cuánto puede pagar al mes y el resto no cabe en un pago, se reparte en el menor número de cuotas mensuales iguales que quepa, dentro del año. Sin un monto dicho, el resto sigue en un solo pago a 30 días. Con más de 3 pagos en total se exigen antes las Hardship Questions, igual que en los planes, para que no sea un atajo |
| ¿Quién ofrece el parcial de último recurso (5% a 10%)? (N6) | El agente, antes de transferir (opción b): "la idea es reducir trabajo a cobradores para que se enfoquen solo en los estados que les corresponden" |
| ¿Qué hace el agente si el deudor acepta con duda? (N7, prueba 1: "I'll give it a try") | Opción A, elegida por el desarrollador el 2026-11-12: antes de cerrar pregunta cuánto puede pagar cómodo al mes ("Just to make sure this works for you: how much could you comfortably pay each month?"), vuelve a pedir la oferta con ese monto (N4 y N6) y solo cierra cuando el deudor dice que puede cumplir. Aplicada el 2026-11-13 en el prompt (paso 7): la oferta con duda se registra como no aceptada y se pide otra con `max_payment_dollars`; la herramienta `record_offer_response` aclara que solo se acepta con un sí claro |

**Supuestos:**
- Planes: de 2 a 10 cuotas iguales, o (después de las Hardship Questions) un primer pago del 10% más 12 cuotas mensuales iguales. El 10% se redondea hacia arriba al centavo; los centavos que sobran de la división van en la primera de las 12 cuotas.
- "Máximo un año" se mide en meses del calendario: el último pago cae, como mucho, el mismo día del mes 12 meses después del primero (antes eran 365 días, que fallaba con años bisiestos).
- Los 30 días del resto se cuentan desde el primer pago.
- Si el mes no tiene el día fijado, se usa su último día.
- Un solo acuerdo activo por cuenta.
- El pago total también pasa a `PTP`.

### Función 5: Hardship Questions

| Pregunta | Respuesta |
| --- | --- |
| ¿Cuándo se hacen? | Si el deudor no puede con 3 cuotas, antes de ofrecer de 4 a 10 cuotas |
| ¿Qué preguntas se hacen? | Las 5 que entregó el jefe el 2026-11-04 (sección 8) |
| ¿Traducción al inglés? | Aprobada: "confirmo la conversion a ingles" (2026-11-08) |
| ¿Frases como "vender el carro" o "pedir plata prestada"? | Descartadas por poder verse como presión. Si hace falta preguntar más, se sigue el tono de las 5 preguntas del jefe (2026-11-08) |
| ¿Se aprueban los campos y el orden? | "Sí, apruebo los campos y el orden, constrúyelo" |
| ¿Y si después sigue sin poder pagar? | "Se transfiere a un agente" |
| ¿Cómo se registra una promesa de pago? | Se anota, con fecha y monto en `scheduled_payments` |

Sin pendientes.

### Función 6: IVR PCI ⛔

| Pregunta | Respuesta |
| --- | --- |
| ¿Cómo se paga con tarjeta? | Transferencia a un IVR PCI que captura los dígitos por teclado; la IA nunca ve la tarjeta |
| ¿Qué proveedor? | Por elegir. Queda como bloqueante; primero se terminan las demás funciones (2026-11-08) |

**Bloqueante:** elegir el proveedor y saber cómo devuelve el resultado del pago.
**Supuesto:** el NSF puede venir de ACH, cheque o tarjeta.

### Función 7: disputas y "no llamar"

| Pregunta | Respuesta |
| --- | --- |
| ¿"Yo sí pagué" o "fue error del banco" cuenta como disputa? | "Sí, cuenta como disputa, constrúyelo así" → se marca la cuenta, se cierra como `dispute` y pasa a una persona |
| ¿Quién revisa la disputa y cómo? (N11) | Opción A, elegida por el desarrollador el 2026-11-12: al registrarse la disputa, la cuenta pasa al estado de disputa que defina el jefe y se envía una alerta por el canal de la empresa (Teams u otro, por confirmar) con los detalles; un cobrador la analiza y marca si es válida o no. Además, parte de la opción B: el agente dice "One moment while I check that for you" y busca en la base el pago que menciona el deudor. Sin construir todavía: depende del estado, del canal y del acceso a los pagos de la base real |
| ¿Qué pasa si el agente no encuentra el pago? (N11) | Supuesto vigente (opción A), porque el desarrollador no tenía claro qué hacer: el agente no acusa al deudor ("I wasn't able to find a payment matching that information in our records"), pide fecha o número de confirmación y vuelve a buscar; si sigue sin aparecer, registra la disputa igual con la nota "pago no encontrado" y deja de cobrar en esa llamada. Si encuentra el pago, se lo dice y la alerta sale como "pago encontrado"; el agente no cambia el saldo. Seguir cobrando una deuda que el deudor acaba de disputar no se hace sin aprobación del abogado |

**Supuestos:**
- Una disputa o "no llamar" impide cobrar.
- En entrantes, "no llamar" exige verificar identidad; en salientes no.
- Una disputa no cancela un acuerdo que ya está en `PTP`.
- Si el deudor rechazó la grabación y pide "no llamar", se guarda la marca y la llamada se cierra como `recording_refused`.

### Paso 8: chat de prueba con Claude (2026-11-10)

Una persona escribe en la terminal como si fuera el deudor y Claude responde como el agente. Es el mismo "cerebro" que tendrá la llamada de voz: Claude solo conversa y pide herramientas, y cada herramienta llama a un caso de uso que aplica las reglas.

| Pregunta | Respuesta | Origen |
| --- | --- | --- |
| ¿Qué modelo conversa? | Claude Haiku 5.5; si un turno falla o se rechaza, lo responde Claude Sonnet 5.5 | Desarrollador |
| ¿Aviso legal de cobranza? | Sí, justo después de verificar la identidad ("This is an attempt to collect a debt...") | Desarrollador |
| ¿Herramientas nuevas y quitar `all_offers_rejected`? | "Aprobado": el sistema elige la oferta (`ProposeNextOffer`) y el acuerdo se crea con la propuesta guardada (`RecordOfferResponse`), nunca con montos que envíe la IA | Desarrollador |

Herramientas: `record_recording_consent`, `verify_identity`, `get_account_details`, `propose_offer`, `record_offer_response`, `propose_partial_payment`, `record_hardship_answers`, `record_dispute`, `mark_do_not_call`, `transfer_to_human` y `end_call`. Cada respuesta trae `next_step`, una instrucción corta de qué hacer después.

**Cómo correrlo** (desde `backend/`, con la base levantada y la key en la terminal o en `backend/.env`):

```
docker compose run --rm app python -m cobranza.agent.infrastructure.chat_cli --entrante +13055550001
docker compose run --rm app python -m cobranza.agent.infrastructure.chat_cli --saliente ACC-T001
```

Datos para verificar a TEST-001: Jane Carter, últimos 4 del SSN 1234, nacida el 14 de marzo de 1985 (saldo USD 485, ACC-T001). Los demás casos están en `backend/db/init/002_seed_mock.sql`. El chat muestra en gris cada herramienta que pide Claude y lo que respondió el backend; `--sin-herramientas` las oculta y `--debug` muestra los avisos internos. `/colgar` termina la llamada.

**Supuestos:**
- La empresa es Live Oak Financial. Antes de verificar al deudor solo se dice "L.O.F." (L3, jefe, 2026-11-12). Se cambian con `--empresa` y `--siglas`.
- La grabación solo se informa, sin preguntar ni esperar respuesta (L2, jefe, 2026-11-12). Si el deudor dice que no quiere ser grabado, se le explica que es un requisito y, si insiste, se cierra la llamada como `recording_refused` sin hablar de la deuda (desarrollador, 2026-11-12).
- A un tercero solo se le dice "It's a personal matter" o "Legally, I can only share this information with [deudor]", sin dejar recados (P3, jefe, 2026-11-12).
- Si preguntan si es un robot, el agente dice que es un asistente virtual de L.O.F. y ofrece pasar a una persona. El desarrollador pidió una respuesta que no confirmara ni negara; Claude no la construyó: el saludo ya dice "virtual assistant" y la FCC (TCPA) y leyes de California y Utah exigen decirlo si se pregunta. Si el jefe quiere otra respuesta, va como pregunta para su abogado (2026-11-12).
- Claude responde con esfuerzo bajo (`effort: low`) para que sea rápido; el flujo y las reglas los fijan el prompt y las herramientas.
- Si Claude no responde, o pide más de 8 herramientas en un solo turno, la llamada pasa a una persona.
- Si el deudor cuelga y Claude no elige un resultado, la llamada se cierra como `callback_requested`.
- Las ofertas presentadas en cada llamada se guardan en memoria. Si se necesita auditarlas después, se guardan en una tabla (requiere aprobar el modelo de datos).
- Con un teléfono compartido, se verifica a quien coincide con el nombre que dijo el deudor.

**Pendiente:** probar con la API real (falta `ANTHROPIC_API_KEY`) y ajustar el prompt con lo que salga de esas pruebas.

### Arquitectura: 3 módulos (2026-11-12)

| Pregunta | Respuesta | Origen |
| --- | --- | --- |
| ¿Separar las reglas de negocio, el agente y la campaña de SMS? | Un solo repositorio con 3 módulos y 3 programas que arrancan por su cuenta, compartiendo la base. Opción A, elegida por el desarrollador ("veo que todo queda demasiado amontonado") | Desarrollador |

| Módulo | Carpeta | Qué hace | Cómo corre |
| --- | --- | --- | --- |
| Núcleo de cobranza | `domain/`, `application/`, `infrastructure/` | Reglas, casos de uso, base de datos y avisos de pago | Servidor siempre encendido (API, pendiente) |
| Agente de voz | `agent/` | Conversación con Claude, prompt (`agent/application/prompts/`) y herramientas | Un proceso por llamada |
| Mensajería | `messaging/` | SMS de confirmación y links de pago | Tarea programada diaria |

Reglas (las vigila `tests/unit/test_architecture.py`): el núcleo no conoce al agente ni a la mensajería; el agente y la mensajería no se conocen entre sí y usan los casos de uso del núcleo, nunca sus repositorios. Si algún día hacen falta servicios separados, ya están divididos.

### N1: cómo paga el deudor un pago agendado (2026-11-12)

| Pregunta | Respuesta | Origen |
| --- | --- | --- |
| ¿Cómo paga el deudor un pago a futuro? | Link de pago por SMS (opción A): al crear el acuerdo se envía un SMS de confirmación con montos y fechas, y el día de cada cuota otro SMS con un link a la página de pago segura del procesador | Desarrollador |
| ¿Se aprueba la tabla `sms_messages`? | "Si, la apruebo" | Desarrollador |
| ¿Se envían los SMS si el deudor está marcado "no llamar"? | "Si, obligatoriamente, una llamada es diferente a mensajes de texto y además el mismo aceptó el acuerdo" | Desarrollador |
| ¿Qué proveedor de SMS usa la empresa? | "Empieza por V" (por confirmar con el jefe) | Jefe, contado por el desarrollador |
| ¿La empresa tiene página o link de pago con su procesador? | "Muy probablemente"; por confirmar con el jefe | Desarrollador |

Cómo quedó construido:
- Módulo `messaging/`: `SendArrangementConfirmations` (acuerdos de los últimos 7 días sin confirmación) y `SendDuePaymentLinks` (cuotas pendientes que vencen hasta la fecha dada). Tarea programada: `python -m cobranza.messaging.infrastructure.run [--fecha AAAA-MM-DD]`; se puede correr varias veces sin repetir mensajes.
- Tabla `sms_messages`: una confirmación por acuerdo y un link por cuota (índices únicos). Un envío fallido se reintenta en la siguiente corrida.
- Mientras no se conecten el proveedor ni el procesador, el SMS solo queda en el log (`LoggingSmsSender`) y el link es de prueba (`PlaceholderPaymentLinkProvider`).
- El agente ahora dice que el deudor recibirá un SMS con los detalles y un link de pago en cada fecha (antes prometía "payment instructions" que no existían).

Ejemplo de confirmación: *"L.O.F.: your payment arrangement is set: $90.00 on Nov 11 and $395.00 on Dec 11. We'll text you a secure payment link on each date. Reply STOP to opt out."*

**Supuestos:**
- La tarea corre en la mañana con la fecha del este de EE. UU. (dentro del horario permitido para contactar).
- Darse de baja con "STOP" lo maneja el proveedor de SMS; el sistema no lo guarda todavía.
- Los SMS no dicen "debt" ni el acreedor, por si otra persona ve el teléfono.
- Legal: enviar SMS a deudores requiere su consentimiento y una forma de darse de baja; el texto de los SMS lo debe revisar el abogado.

**Pendiente de N1:** conectar el proveedor de SMS ("V") y el link del procesador; recibir el aviso de pago del procesador (`RecordPaymentResult` y `payment_results`) y definir el estado de la cuenta cuando se pagan todas las cuotas o una no se paga.

### Lista diaria de llamadas salientes (2026-11-12)

| Pregunta | Respuesta | Origen |
| --- | --- | --- |
| ¿Cómo se sabe a quién llamar cada día? | "Es mejor que nosotros consultemos a la base de manera diaria para saber cuales son las llamadas salientes del dia y si hay una entrante que corresponde a la lista de saliente removerlo" | Jefe, contado por el desarrollador |
| ¿Cuándo se saca de la lista al deudor que llama? | Cuando la llamada entrante verifica su identidad (opción A). Si alguien llama desde su teléfono y no se verifica, el deudor sigue en la lista: un impostor no puede evitar que lo llamen | Desarrollador |
| ¿Se aprueba la tabla `outbound_call_list` y sus criterios? | "Si, me parece bien la lista" | Desarrollador |
| ¿Qué llamadas entrantes atiende el agente? | El jefe propondrá al dueño de la empresa que las entrantes de deudores en NSF pasen directo al agente; el agente solo llama y contesta. Las de otros estados ya se transfieren a una persona | Jefe (por confirmar con el dueño) |
| ¿Quién vuelve a llamar si la llamada termina sin acuerdo? (N9) | Opción A, elegida por el desarrollador el 2026-11-12: la lista diaria. Sin una hora pedida, el deudor vuelve solo a la lista cuando la Reg F lo permite (7 días después de una conversación; al día siguiente si contestó un tercero o nadie). Si el deudor pide que lo llamen en un día y una hora, ese día entra a la lista para esa hora (necesita B2: guardar la hora pedida). Si llama antes y verifica su identidad, sale de la lista | Desarrollador |

Cómo quedó construido:
- Tabla `outbound_call_list`: una fila por cuenta y día (`pending`, `called` o `removed`, con el motivo y la llamada que la sacó).
- Tarea diaria: `python -m cobranza.infrastructure.controllers.build_outbound_list [--fecha AAAA-MM-DD]`. Se puede correr varias veces sin repetir cuentas. En la base simulada agrega 323 de las 329 cuentas en NSF.
- Entran las cuentas en NSF, sin disputa, de deudores sin "no llamar", sin acuerdo activo y con teléfono.
- Reg F: quedan fuera las cuentas con 7 llamadas salientes en los últimos 7 días y los deudores con una conversación (identidad verificada) en los últimos 7 días.
- `VerifyIdentity` saca de la lista las cuentas pendientes del deudor cuando una entrante lo verifica. `GetOutboundCalls` y `MarkOutboundCalled` quedan para quien marque las salientes.

**Supuestos:**
- La lista se arma en la mañana con la fecha del este de EE. UU.
- Solo se cuentan las llamadas de esta base; las de los cobradores se sumarán cuando se conozca la base real. La regla de no llamar 7 días después de una conversación sale de la Reg F; se agregó al filtro de 7 en 7 aprobado.
- La consulta se hace sobre la base de prueba; con la base real y su EER solo cambia esa consulta.

### Para todo el proyecto

- Revisión legal del guion y de los avisos.
- Cómo cuentan las llamadas del agente y de los cobradores para el límite de 7 intentos en 7 días (Reg F).

### Bloqueantes reales

1. El proveedor del IVR PCI: detiene la Función 6.
2. La `ANTHROPIC_API_KEY`: hace falta para probar el resumen y el chat de prueba con Claude (paso 8, ya construido).
3. El EER y la base de datos real: no detienen el desarrollo, pero se necesitan antes de conectar con el sistema real (por ejemplo, para la consulta de la lista diaria de salientes).

## 1. Decisiones iniciales (2026-10-28)

| Tema | Decisión | Respuesta textual | Origen |
| --- | --- | --- | --- |
| Pago con tarjeta | Transferir a un IVR PCI con captura por teclado (DTMF) | "Transferir a un IVR PCI con captura por teclado (DTMF). Eligo esta opcion" | Desarrollador |
| Verificación de identidad | Nombre completo + últimos 4 del SSN + fecha de nacimiento | "verificar nombre completo + últimos 4 del SSN [...] junto con fecha de nacimiento" | Desarrollador |
| Grabación | Aviso de grabación al inicio de la llamada | "aviso de grabación al inicio de la llamada, porque varios estados exigen consentimiento de ambas partes." | Desarrollador |
| Estilo de negociación | Negociar sin presionar ni amenazar | "negociar, sin presionar ni amenazar." | Desarrollador |
| Idioma | Inglés | "Ingles" | Desarrollador |
| Datos | Simular datos detrás de una interfaz, con implementación en PostgreSQL por ahora | "hay que simularlos y dejar solo la interfaz con una implementacion en postgres (por ahora) despues nos dan razon de la bd utilizada." | Desarrollador |
| Registro del resultado | Insertar los datos del deudor en una tabla o en un registro existente; por definir | "Es insertar esos datos del deudor en una tabla quizas es insertarlas en un registro existente (Por definir)" | Desarrollador |
| Volumen | 2.000 llamadas diarias previstas | "son 2000 llamadas diarias que se tienen previstas" | Desarrollador |
| Tipos de llamada | Entrantes y salientes; las salientes, después del resultado del job | "eso solo aplica para las llamadas salientes despues de que el job nos da el resultado, si es entrante no siempre será NSF" | Desarrollador |
| **Descuentos** | **Nunca.** Se cobra el saldo completo; el pago parcial no perdona el resto | "al deudor JAMÁS se le hara descuento JAMÁS JAMÁS siempre se le cobra todo, si puede pagar el 70% mejor pero nada descuentos NADA" | Desarrollador |
| Arquitectura | Hexagonal | "utiliza arq hexagonal" | Desarrollador |

## 2. Preguntas consultadas con el jefe (respuestas traídas el 2026-10-29)

| # | Pregunta | Respuesta textual | Cómo se aplicó |
| --- | --- | --- | --- |
| 1 | ¿Qué estados de pago existen además de NSF? | "Manejaremos solo nfc, cualquier otra llamada que tenga un deudor en un estado distinto es remitido a un personal" | Se entendió "nfc" como NSF. Otro estado, incluidos `first_attempt` a `fourth_attempt`, se transfiere a una persona (confirmado el 2026-11-08) |
| 2 | ¿Un deudor puede tener varias deudas? | "Si, pueden ser del mismo o diferentes" | Tablas `debtors` y `accounts` separadas |
| 3 | ¿Qué datos del NSF hay? ¿ACH, cheque o tarjeta? | "Si" | Se modelaron todos los campos. Falta confirmar el medio de pago |
| 4 | ¿Cómo entrega el resultado el job? | "Por definir" | Abierto |
| 5 | ¿Cómo se identifica a quien llama? | "agente recibe num y busca" | Búsqueda por el número desde el que llaman |
| 6 | ¿Hay estado o dirección del deudor? | "despues del siguiente estado \"fourth_attempt\" la compañia usa un software que se llama Skip Traicing Cuando no se encuentran o n otienen estado o direccion" | Estado y zona horaria opcionales |
| 7 | ¿Hay nombres de campos fijos? | "Si" | Se esperan en el diagrama EER |
| 8 | Pago parcial: ¿qué pasa con el resto? | "Agendar una fecha de pago" | Se guarda como pago agendado |
| 9 | ¿Hay un mínimo de pago parcial? | "No hay un minimo aceptable pagar por lo menos el 10%; intentar sacar la mayor ccantidad posible; si no, el plan despues se opta por la metodologia HardShip Questions (se verifica ingresos y se hace recomendaciones: \"Señor, le recomiendo entonces que venda su carro...\")" | Mínimo de 10%; luego plan; luego Hardship Questions |
| - | ¿Con qué modelo trabajamos sin el EER? | "Me dijeron que lo hicieramos con el modelo que teniammos por ahroa, mientras nos dan el EER" | Se usa el modelo provisional |

## 3. Reglas de cobro y llamadas

| Fecha | Pregunta | Respuesta textual | Origen |
| --- | --- | --- | --- |
| 2026-10-29 | ¿Los estados de intento van en el mismo campo que NSF? | "Si, vienen en el mismo campo" | Desarrollador |
| 2026-10-29 | Saliente sin estado ni zona horaria | "Se hace la cobranza normal y se deduce por el codigo de area" | Desarrollador |
| 2026-10-29 | ¿El 10% aplica a la primera cuota? | "Sì aplica para la primera cuota tambien" | Desarrollador |
| 2026-10-29 | Plazo máximo del plan | "Maximo un año" | Desarrollador |
| 2026-10-29 | Campos de Hardship y alerta de cumplimiento | "Si, sirven y no pasa nada sobre la alerta, la idea es recomendar amablemente y hacerle entender de que se metio en una deuda que solo hace el trabajo" | Desarrollador |
| 2026-10-29 | ¿Dónde se cuentan los intentos? | "agrega otro campo que se llame verification_attempts, porque el del estado del nsf cuenta las veces que se le ha intentado cobrar al deudor" | Desarrollador |
| 2026-10-29 | Bloqueo tras 5 fallos de verificación en 24 horas | "Listo si" | Propuesto por Claude; aprobado por el desarrollador |
| 2026-10-29 | Pedir deletrear el apellido antes de contar un fallo | "Perfecto" | Propuesto por Claude; aprobado por el desarrollador |
| 2026-11-01 | ¿Qué pasa si el deudor no acepta la grabación? | "Por ley se tiene que grabar" | Desarrollador (ver alerta 2) |
| 2026-11-01 | ¿La IA genera el resumen de la llamada? | "Si, que lo genere la IA" | Desarrollador |
| 2026-11-01 | Modelo de IA del resumen | "Sí, implementalo así con Haiku" y pidió un respaldo más barato que Opus | Desarrollador; Claude eligió Sonnet 5.5 como respaldo |
| 2026-11-02 | Plazo del resto en el pago parcial | "si, el plazo maximo dejalo en 30 dias" | Desarrollador |
| 2026-11-02 | Orden de las ofertas | "intentar todo de una, si no, a dos cuotas, despues si dice que le queda complejo a 3, pero siempre por lo más rapido." | Desarrollador |
| 2026-11-02 | Cuotas | "No, el deudor no propone, acepta, tienen que ser iguales y con frecuencia fija." | Desarrollador |
| 2026-11-02 | ¿El primer pago puede ser otro día? | "Dejemos que sea en unos días, y cuando lo llamemos es para recordarle el pago" | Desarrollador |
| 2026-11-02 | Frecuencia de las cuotas | "quincenal" (**reemplazada por el jefe: ver sección 3.1**) | Propuesto por Claude; aprobado por el desarrollador |
| 2026-11-02 | Plazo del primer pago | "7 dias, dejemoslo en 7 días" (**reemplazado: ahora son 8 días, ver sección 3.1**) | Propuesto por Claude; aprobado por el desarrollador |
| 2026-11-02 | ¿Cada cuota se cobra en una llamada, por el IVR PCI? | "Sí" (**reemplazada: el recordatorio lo hace un cobrador, ver sección 3.1**) | Propuesto por Claude; aprobado por el desarrollador |
| 2026-11-02 | Monto del pago parcial | "EL monto seria lo unico que el propone, pero si es bajo al 10% entonces aceptar con la condicion de que las otras cuotas son mayores" | Desarrollador (ver sección 6) |
| 2026-11-02 | Límites del pago menor al 10% | "constrúyela con el 10% como mínimo, el piso minimo el 5% y el resto en 30 dias" | Propuesto por Claude; aprobado por el desarrollador (ver sección 6) |

## 3.1 Respuestas del jefe sobre la negociación (traídas el 2026-11-02)

La relación entre cada respuesta y su tema es una lectura de Claude, porque llegaron como una lista corta.

| Tema | Respuesta textual | Cómo se aplicó |
| --- | --- | --- |
| Frecuencia de las cuotas | "Cuotas mensuales fecha establecida" | Cuotas mensuales, el mismo día del mes que el primer pago |
| Fecha del resto en un pago parcial | "normalmente es al mes" | El resto se agenda por defecto a los 30 días |
| Estado de la cuenta al crear un acuerdo | "cambiar estado a PTP o si hay una tarjeta de crédito puesta RCC" | Pasa a `PTP`. `RCC` queda fuera del alcance |
| Qué se busca en las Hardship Questions | "En las hardship questilns buscar colo puede pagar, \"vendiendo el carro\", \"pedir plata prestada\"" | La lista que entregó el jefe después no incluye esas frases (ver secciones 5 y 8) |
| Quién escribe las recomendaciones | "Me las pasa el jefe, son sugerencias \"colaboración de familiares\" sugerencias, sugerencias" | Entregada el 2026-11-04 (sección 8) |
| Aceptar menos del 10% | "Si, pero en cos muy específicos ya cuando no hay opción" | Solo después de las Hardship Questions y de rechazar todas las ofertas, con un mínimo de 5% |
| Contexto de las llamadas | "Entrante lo normal es para un cliente que recibió un mensaje de texto que el pago rebotó. Si es saliente: si es nsf llamar para que le de el dato de que el pago rebotó y saber que se hace si se llama en 8 días por ejemplo" | El guion debe partir de que el deudor intentó pagar. Los 8 días son el plazo que el deudor puede prometer |
| Estado tras negociar | "de nsf se pasaria a PTP" | Ya construido |
| Si tras las Hardship Questions sigue sin poder pagar | "Se transfiere a un agente" | Está en el flujo aprobado; se construye con la capa de conversación |

Estas cuatro respuestas son apuntes del desarrollador sobre lo que respondió el jefe.

Aclaraciones posteriores del desarrollador:

| Tema | Respuesta textual | Cómo se aplica |
| --- | --- | --- |
| Pago en 8 días | "Si el deudor dice que paga en ocho dias se cambia el estado a PTP y ahi se en el summary se dice que el deudor dijo que pagaba en ocho días, ahorita lo ocnfirmo con el jefe de todas formas" | Confirmado: "Si, se puede pagar a 8 dias". El máximo del primer pago subió a 8 días |
| `RCC` | "Significa Registered Credit Card, es un estado, pero como manejamos NSF pues no nos corresponde, entonces olvidarlo" | Fuera del alcance |
| Después de `PTP` | "Despues se hace una llamada recordando que tienen que pagar, pero eso lo hace un cobrador (una persona) nuestro trabajo es que el flujo NSF quede perfecto" | El trabajo del agente termina al pasar la cuenta a `PTP`. No se construyen llamadas de recordatorio |
| Flujos de entrantes y salientes | "mi jefe aprobo" | Quedan como en el diagrama del documento de arquitectura |
| Campos de Hardship y orden de la negociación | "Sí, apruebo los campos y el orden, constrúyelo" (propuestos por Claude) | Todo, 2 cuotas, 3 cuotas, Hardship Questions, de 4 a 10 cuotas, parcial menor al 10% y, si nada funciona, transferir a un agente |
| "Yo sí pagué" o "fue error del banco" | "Sí, cuenta como disputa, constrúyelo así" | Se marca la cuenta en disputa, se cierra la llamada como `dispute` y se transfiere a un agente |

Decisiones del desarrollador del 2026-11-08:

| Tema | Respuesta textual | Cómo se aplica |
| --- | --- | --- |
| Estados que cobra el agente | "Solo NSF, si ese estado no encaja en el nuestro descartemoslo" | `COLLECTABLE_STATUSES` = solo `NSF`. Los intentos pasan a una persona. Se ajustaron pruebas y datos simulados (`ACC-T002b` y `ACC-T003` pasan a NSF) |
| Traducción de las Hardship Questions | "confirmo la conversion a ingles" | Aprobada la versión de `domain/hardship.py` |
| Frases de presión en Hardship | "correcto ya no incluir esas preguntas que puedan verse como presion, usa las frases que dio el jefe y guiate de ellas en caso de necesitar hacer más preguntas" | Descartadas "vender el carro" y "pedir dinero prestado". Si hace falta preguntar más, se sigue el tono de las 5 preguntas del jefe |
| Idioma del resumen | "Esto si está confirmado, en ingles, porque todos ahi hablan ingles y el servicio es para estados unidos" | El resumen se genera en inglés |
| Proveedor del IVR PCI | "igual dejalo como bloqueante por ahroa" | Sigue bloqueando la Función 6; primero se terminan las demás funciones |
| Reglas sin confirmar | "Tdoas las demas que queden por confirmar dejalas como supuestos excepto las que no tienen respuesta temporal alemnos" | Pasan a la sección 4 como supuestos; las que no tienen respuesta siguen en la sección 6 |

## 4. Supuestos vigentes

Desde el 2026-11-08 estas reglas se dan por buenas mientras nadie diga lo contrario. Las propuso Claude y ya están en el código.

| Supuesto | De dónde sale |
| --- | --- |
| Máximo 2 fallos de verificación por llamada | Propuesta de Claude en el diseño |
| Una disputa o "no llamar" impide cobrar | Propuesta de Claude por la ley de cobranza |
| Máximo de 10 cuotas | Consecuencia de cuotas iguales con la primera ≥ 10% |
| Los 30 días del resto se cuentan desde el primer pago, no desde la llamada | Claude lo eligió; el jefe no lo respondió explícitamente |
| En todo pago parcial, también entre 5% y 10%, el resto va en un solo pago | Con cuotas mensuales no caben 2 pagos en 30 días |
| "Fecha establecida" es el día del mes del primer pago; si un mes no tiene ese día, se usa su último día | Lectura de Claude |
| Una cuenta solo puede tener un acuerdo activo | Propuesta de Claude para evitar cobros duplicados |
| Todo acuerdo pasa la cuenta a `PTP`, incluso el pago total | La respuesta del jefe no distingue por tipo de acuerdo |
| "No llamar" se respeta sin verificación en salientes, pero en entrantes la exige | En una saliente se llamó al deudor del job; en una entrante, otra persona podría bloquear sus llamadas |
| Una disputa no cambia el estado ni cancela un acuerdo activo de la cuenta | Claude no quiso asumir qué hace el cobrador en ese caso |
| La grabación es obligatoria; si el deudor no acepta, se cierra como `recording_refused` | Respuesta "Por ley se tiene que grabar". Falta saber qué ley o política lo exige (alerta 2) |
| El NSF puede venir de ACH, cheque o tarjeta | El modelo acepta los tres. Falta saber cuál usa realmente el sistema |

## 5. Alertas de cumplimiento

Ninguna de estas alertas fue revisada por un abogado.

1. **Recomendaciones de Hardship.** Claude advirtió que frases como "le recomiendo que venda su carro" o hacerle entender al deudor que se endeudó pueden considerarse presión o una práctica injusta (FDCPA, CFPB). Además chocan con la decisión inicial de negociar sin presionar. El desarrollador respondió que no hay problema, y el jefe confirmó que se busque cómo puede pagar el deudor con sugerencias como vender el carro, pedir dinero prestado o la colaboración de familiares. Claude recomendó revisión legal antes del piloto. Sugerir la ayuda de familiares no permite contactarlos ni hablarles de la deuda. **Resuelta el 2026-11-08:** el desarrollador confirmó que esas frases quedan descartadas. El agente usa las 5 preguntas del jefe y, si necesita preguntar más, sigue su tono.
2. **Grabación obligatoria.** La respuesta fue que la ley obliga a grabar. Claude señaló que, hasta donde sabe, ninguna ley federal lo exige y que quizá sea una política de la empresa o un requisito del cliente. Falta confirmar la fuente. Como varios estados exigen consentimiento, si el deudor no acepta se cierra la llamada sin mencionar la deuda (`recording_refused`).
3. **Límites de llamadas.** Las llamadas del agente y las de los cobradores suman contactos. Falta confirmar con un abogado cómo cuentan para el límite de 7 intentos en 7 días (Reg F).

## 6. Pendientes de decidir

Estos temas no tienen ni una respuesta provisional.

| Tema | Estado |
| --- | --- |
| Insertar o actualizar el resultado de la llamada | Por definir |
| Diagrama EER y base de datos real | Pendiente de entrega |
| Proveedor del IVR PCI y cómo devuelve el resultado del pago | Por elegir; **bloquea la Función 6** |
| Cómo cuentan las llamadas del agente y de los cobradores para el límite de 7 en 7 días (Reg F) | Falta un abogado (alerta 3) |
| Revisión legal del guion y de los avisos | Pendiente |

## 7. Datos que deben tomarse como estimaciones

Estas cifras son estimaciones de Claude, todavía sin medir en un piloto:

- ~0,95 segundos de respuesta por turno de conversación.
- ~USD 309 diarios (~USD 9.256 mensuales) de costo de la operación, calculado con precios de lista el 2026-11-10 (sección 9). Reemplaza la estimación anterior de USD 600–1.000 diarios.
- ~USD 24 mensuales por los resúmenes con Claude Haiku 5.5. El resumen aún no se ha probado contra la API real.

## 8. Preguntas de Hardship entregadas por el jefe (2026-11-04)

Texto tal como lo entregó. La traducción al inglés de `backend/src/cobranza/domain/hardship.py` se aprobó el 2026-11-08.

1. «¿Puede contarme un poco qué fue lo que pasó y cuándo empezó esta situación?»
2. «¿Es algo que espera que sea temporal o un cambio a largo plazo en sus ingresos?»
3. «¿Hay alguien más en el hogar que pueda colaborar mientras se estabiliza?»
4. «Entiendo que la situación está difícil, pero ¿hay alguna cantidad parcial que pueda aportar hoy o en su próxima fecha de pago?»
5. «¿Qué acuerdo realista podemos fijar para los próximos 30 o 60 días que le permita cumplir sin ahogarse?»

Registro de una promesa de pago: "Si, basta con anotarla, y que la fecha y el monto queden tambien en scheduled_payments".

## 9. Proveedores y costos (2026-11-10)

Recuperado del documento enviado al jefe (`docs/Backend_Agente_Cobranza_NSF_v3.pdf`, sección 6). Son los servicios externos que necesita el agente para una llamada real. En cada uno se eligió la opción más económica que cumple con lo que pide una llamada en vivo: baja demora y certificación PCI donde aplica. Todos quedan detrás de una interfaz, así que cambiar de proveedor solo cambia la implementación.

**Base del cálculo:** 2.000 llamadas diarias × 30 días = 60.000 llamadas al mes, de 4 minutos en promedio = 240.000 minutos al mes. Precios de lista en dólares, pago por uso, consultados el 2026-11-10.

| Para qué | Proveedor | Estado | Costo mensual (USD) | Por qué se necesita |
| --- | --- | --- | --- | --- |
| Conversación con el deudor | Anthropic: Claude Haiku 5.5 | Elegido | ~330 (USD 0,10 / 0,50 por millón de tokens de entrada / salida, con caché del prompt) | Es el cerebro de la llamada: entiende al deudor, responde y pide las herramientas del backend. Haiku es el más rápido y barato, y en voz la rapidez importa |
| Resumen de cada llamada | Anthropic: Claude Haiku 5.5 | Elegido | ~24 (~USD 0,0004 por resumen) | Resume la transcripción en inglés para el equipo |
| Respaldo de la IA | Anthropic: Claude Sonnet 5.5 | Elegido | ~60 (USD 2 / 10 por millón de tokens; solo si Haiku falla, ~1% de las llamadas) | Si Haiku falla o rechaza, responde Sonnet y la llamada no se cae |
| Telefonía, grabación y números | Telnyx Voice API | Recomendado, sin aprobar | ~2.794 (USD 0,0116 por minuto: control 0,002 + línea 0,0041 + audio en vivo 0,0035 + grabación 0,002; y 10 números a USD 1) | Da los números, conecta la llamada, graba (obligatorio) y envía el audio en vivo al agente. Twilio costaría ~USD 4.260 por lo mismo |
| Pago con tarjeta (IVR PCI) | Telnyx Pay over Voice | Recomendado, sin aprobar. **Bloquea la Función 6** | ~1.200 (USD 0,20 por pago, precio de Twilio Pay; el de Telnyx está por confirmar; 6.000 pagos al mes) | El deudor teclea la tarjeta en un sistema certificado PCI DSS; la IA y las grabaciones nunca ven el número. Al ser el mismo proveedor de la telefonía, no hace falta transferir a otra empresa |
| Voz a texto (STT) | Deepgram Nova-3 (streaming) | Recomendado, sin aprobar | ~1.848 (USD 0,0077 por minuto) | Convierte lo que dice el deudor en texto para Claude, en tiempo real |
| Texto a voz (TTS) | Deepgram Aura-2 | Recomendado, sin aprobar | ~2.700 (USD 30 por millón de caracteres; ~1.500 caracteres por llamada) | Convierte la respuesta de Claude en voz natural en inglés. Más barato que Cartesia (~USD 3.400) y ElevenLabs (~USD 3.600), y es el mismo proveedor del STT |
| Orquestación de voz | Pipecat (código abierto) | Recomendado, sin aprobar | 0 (sin licencia; corre en los servidores) | Une telefonía, STT, Claude y TTS, y maneja turnos e interrupciones |
| Servidores y base de datos | AWS, región este de EE. UU. (Fargate ARM + PostgreSQL) | Recomendado, sin aprobar | ~300 (4 contenedores de voz de 2 vCPU, 1 de backend, base de datos y balanceador) | Donde corren el backend y la voz, cerca de los deudores para tener menos demora. Si se usa la base real de la empresa, la base no suma costo |
| **Total mensual estimado** | | | **~9.256** | ~USD 309 diarios, ~USD 0,15 por llamada, ~USD 0,04 por minuto |

**Supuestos del costo:**
- Los USD 24 de Haiku son solo los resúmenes. Que Haiku converse en la llamada cuesta más (~USD 330), porque en cada turno vuelve a leer las instrucciones y lo que va de la llamada; con caché del prompt esa relectura cuesta la décima parte.
- Conversación: ~20 pedidos al modelo por llamada, ~6.500 tokens de entrada y ~300 de salida por pedido. Sin caché costaría ~USD 960 al mes.
- Llamadas mitad entrantes y mitad salientes. Si todas fueran salientes, la telefonía sube ~USD 220.
- Pagos con tarjeta en el 10% de las llamadas. Las comisiones del procesador de pagos (Stripe u otro) no están incluidas: se cobran sobre el dinero recaudado.
- Voz a texto con la tarifa normal de Deepgram; con la promoción actual (USD 0,0048 por minuto) bajaría a ~USD 1.152.
- Si en la prueba suena bien Deepgram Aura-1 (USD 15 por millón de caracteres), el texto a voz baja a ~USD 1.350.
- Son precios de lista. Con 2.000 llamadas diarias se pueden negociar descuentos con Telnyx y Deepgram.

Precios de referencia: twilio.com/voice/pricing/us, telnyx.com/pricing/call-control, twilio.com/en-us/voice/pay-connectors/pricing, deepgram.com/pricing, aws.amazon.com/fargate/pricing y la tabla de precios de Anthropic.

**Bloqueantes por proveedor:**
- Aprobar Telnyx Pay over Voice y confirmar su precio por pago: bloquea la Función 6.
- Aprobar telefonía, voz y servidores: no detiene el desarrollo, pero hace falta antes de pasar del chat de prueba a llamadas reales.

### 9.1 Novedades del jefe (2026-11-11, contadas por el desarrollador)

| Tema | Lo que dijo el jefe | Origen |
| --- | --- | --- |
| Volumen | "probablemente" 800 llamadas diarias, ya no 2.000 | Jefe (sin confirmar) |
| SMS | La empresa ya tiene una campaña de SMS: consulta una lista de deudores y les envía mensajes. Por lo tanto ya tiene un proveedor de telefonía y SMS | Jefe |

**Recálculo con 800 llamadas diarias** (24.000 llamadas y 96.000 minutos al mes, mismos supuestos y precios de la tabla anterior). Lo que se paga por uso baja en la misma proporción (40%); los números y los servidores bajan menos.

| Para qué | Con 2.000 diarias (USD/mes) | Con 800 diarias (USD/mes) |
| --- | --- | --- |
| Conversación (Claude Haiku 5.5) | ~330 | ~132 |
| Resúmenes (Claude Haiku 5.5) | ~24 | ~10 |
| Respaldo (Claude Sonnet 5.5) | ~60 | ~24 |
| Telefonía (Telnyx) | ~2.794 | ~1.124 |
| Pago con tarjeta (IVR PCI) | ~1.200 | ~480 |
| Voz a texto (Deepgram Nova-3) | ~1.848 | ~739 |
| Texto a voz (Deepgram Aura-2) | ~2.700 | ~1.080 |
| Servidores (AWS) | ~300 | ~200 (2 contenedores de voz en vez de 4; estimado) |
| **Total** | **~9.256** | **~3.789** |

Por llamada sigue costando ~USD 0,16 (antes ~0,15): los costos fijos se reparten entre menos llamadas, y con menos volumen hay menos margen para negociar descuentos.

**Lo que cambia con el proveedor de SMS que ya tiene la empresa:**
- Si ese proveedor también da llamadas de voz con audio en vivo (necesario para el agente), conviene usarlo en vez de Telnyx: ya tiene contrato, números y la lista de deudores. Su precio reemplaza la fila de telefonía.
- Puede servir para enviar el link o las instrucciones de pago por SMS (pendiente de negocio de la simulación 2).
- **Preguntas para el jefe:** ¿qué proveedor es (Twilio, Telnyx, Vonage, otro)? ¿Las llamadas de los cobradores van por el mismo proveedor? ¿Qué programa usan los cobradores para recibir llamadas (marcador o CRM)? De eso depende cómo se transfiere la llamada y cómo le llega al cobrador el motivo.
