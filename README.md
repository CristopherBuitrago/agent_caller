# Agente de voz de cobranza NSF: registro de decisiones

Actualizado: 2026-11-08

Este documento registra cada decisión de negocio, quién la tomó y las palabras con las que se respondió. Las respuestas están citadas tal como se escribieron, con sus errores de tipeo.

Documento de arquitectura: https://claude.ai/artifact/CLGgKwmBLiJpngybRoFjtu

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
| ¿Cómo entrega el resultado el job de NSF (salientes)? | "Por definir" |
| Saliente sin ubicación | "Se hace la cobranza normal y se deduce por el codigo de area" |

**Pendiente (no impide avanzar):** cómo entrega el job sus resultados. Hoy se busca por ID de cuenta.

### Función 2: verificar identidad

| Pregunta | Respuesta |
| --- | --- |
| ¿Qué datos se verifican? | Nombre completo + últimos 4 del SSN + fecha de nacimiento |
| ¿Dónde se cuentan los intentos? | En un campo nuevo, `verification_attempts`, aparte del estado del NSF |
| ¿Bloquear tras 5 fallos en 24 h? | "Listo si" (propuesta de Claude) |
| ¿Pedir deletrear el apellido antes de contar un fallo? | "Perfecto" (propuesta de Claude) |

**Supuesto:** máximo 2 fallos por llamada.

### Función 3: registrar la llamada y resumen

| Pregunta | Respuesta |
| --- | --- |
| ¿Aviso de grabación? | Sí, al inicio de cada llamada |
| ¿Qué pasa si el deudor no acepta la grabación? | "Por ley se tiene que grabar" → se cierra como `recording_refused` sin hablar de la deuda |
| ¿La IA genera el resumen? | "Si, que lo genere la IA" |
| ¿Con qué modelo? | Claude Haiku 5.5, con Claude Sonnet 5.5 como respaldo |
| ¿En qué idioma va el resumen? | Inglés: "todos ahi hablan ingles y el servicio es para estados unidos" (2026-11-08) |

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
| ¿Cuándo es el primer pago? | En unos días, máximo 8 ("Si, se puede pagar a 8 dias", Jefe) |
| ¿Cuándo se paga el resto de un parcial? | "normalmente es al mes" → 30 días |
| ¿Se acepta menos del 10%? | "en cos muy específicos" → piso de 5%, como último recurso |
| ¿Qué estado queda tras el acuerdo? | `PTP`; `RCC` queda fuera del alcance |
| ¿Qué pasa después de `PTP`? | La llamada de recordatorio la hace un cobrador; ahí termina el trabajo del agente |

**Supuestos:**
- Máximo de 10 cuotas.
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

**Supuestos:**
- Una disputa o "no llamar" impide cobrar.
- En entrantes, "no llamar" exige verificar identidad; en salientes no.
- Una disputa no cancela un acuerdo que ya está en `PTP`.
- Si el deudor rechazó la grabación y pide "no llamar", se guarda la marca y la llamada se cierra como `recording_refused`.

### Para todo el proyecto

- Revisión legal del guion y de los avisos.
- Cómo cuentan las llamadas del agente y de los cobradores para el límite de 7 intentos en 7 días (Reg F).

### Bloqueantes reales

1. El proveedor del IVR PCI: detiene la Función 6.
2. La `ANTHROPIC_API_KEY`: hace falta para probar el resumen y la conversación con Claude (paso 8).
3. El EER, la base de datos real y cómo entrega el job sus resultados: no detienen el desarrollo, pero se necesitan antes de conectar con el sistema real.

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

| Tema | Estado |
| --- | --- |
Estos temas no tienen ni una respuesta provisional.

| Tema | Estado |
| --- | --- |
| Cómo entrega el resultado el job de NSF | Por definir |
| Insertar o actualizar el resultado de la llamada | Por definir |
| Diagrama EER y base de datos real | Pendiente de entrega |
| Proveedor del IVR PCI y cómo devuelve el resultado del pago | Por elegir; **bloquea la Función 6** |
| Cómo cuentan las llamadas del agente y de los cobradores para el límite de 7 en 7 días (Reg F) | Falta un abogado (alerta 3) |
| Revisión legal del guion y de los avisos | Pendiente |

## 7. Datos que deben tomarse como estimaciones

Estas cifras son estimaciones de Claude, todavía sin medir en un piloto:

- ~0,95 segundos de respuesta por turno de conversación.
- ~USD 600–1.000 diarios de costo variable de la operación.
- ~USD 24 mensuales por los resúmenes con Claude Haiku 5.5. El resumen aún no se ha probado contra la API real.

## 8. Preguntas de Hardship entregadas por el jefe (2026-11-04)

Texto tal como lo entregó. La traducción al inglés de `backend/src/cobranza/domain/hardship.py` se aprobó el 2026-11-08.

1. «¿Puede contarme un poco qué fue lo que pasó y cuándo empezó esta situación?»
2. «¿Es algo que espera que sea temporal o un cambio a largo plazo en sus ingresos?»
3. «¿Hay alguien más en el hogar que pueda colaborar mientras se estabiliza?»
4. «Entiendo que la situación está difícil, pero ¿hay alguna cantidad parcial que pueda aportar hoy o en su próxima fecha de pago?»
5. «¿Qué acuerdo realista podemos fijar para los próximos 30 o 60 días que le permita cumplir sin ahogarse?»

Registro de una promesa de pago: "Si, basta con anotarla, y que la fecha y el monto queden tambien en scheduled_payments".
