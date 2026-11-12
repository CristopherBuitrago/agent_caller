# Agente de cobranza NSF: respuestas a las observaciones

Actualizado: 2026-11-12. Referencia: `docs/Informe_Simulaciones_Agente_Cobranza_NSF.pdf` (códigos N, B, P y L) y la simulación 8 (S1 y S2).

**Estado:** **Aplicada** = construida y probada · **Por confirmar** = aplicada o decidida, pero falta validarla · **Pendiente** = falta decidir.

## Errores y seguridad

| # | Observación | Respuesta | Estado |
| --- | --- | --- | --- |
| E1 | Si el deudor pide "no llamar" o disputa y cuelga, el pedido se podía perder | Al colgar, el agente guarda primero el "no llamar" o la disputa y después cierra la llamada | Aplicada |
| E2 | Guardar las Hardship Questions de a una borraba las respuestas anteriores | Cada respuesta se agrega sin borrar las anteriores | Aplicada |
| S1 | Quien llamó dijo "Paul Carter", falló, y luego dijo "Jane Carter" y pasó (verificación por tanteo) | Si quien llama cambia de nombre entre intentos, la llamada se cierra (resultado `identity_mismatch`) sin revisar sus datos, y se le pide llamar de nuevo con sus propios datos | Aplicada |
| S2 | Se pedía deletrear el apellido aunque fallara el nombre y antes de revisar el SSN y la fecha | Solo se pide deletrear si el SSN, la fecha y el nombre coinciden y lo único que no coincide es el apellido. Cualquier otro fallo cuenta como intento fallido, sin decir qué dato falló | Aplicada |

## Negocio

| # | Observación | Respuesta | Estado |
| --- | --- | --- | --- |
| N1 | No había forma de que el deudor pagara un pago agendado | Al cerrar el acuerdo se envía un SMS de confirmación; el día de cada cuota, otro SMS con el link de pago. Se envían aunque el deudor esté marcado "no llamar" (aceptó el acuerdo) | Aplicada con proveedor de prueba. **Por confirmar:** qué proveedor de SMS usa la empresa (empieza por "V") y si hay página de pago del procesador |
| N2 | Verificar leyendo el SSN y la fecha para que el deudor diga sí o no | Se deja como está: el deudor dice su nombre completo, los últimos 4 del SSN y su fecha de nacimiento. Leerle los datos los revela a quien conteste y no se puede con el diseño actual (los datos están cifrados). Si se prefiere la otra forma, se hace | **Por confirmar** |
| N3 | Saludo y aviso de grabación en las salientes | El saludo solo pregunta por el deudor ("May I speak with Jane Carter?"). Cuando confirma que es él, el agente se identifica y avisa de la grabación, y con su "sí" verifica. La grabación empieza con ese "sí": a un familiar que conteste no se le dice ni se le graba nada | Aplicada |
| N4 | Se ofrecían opciones que el deudor ya había descartado | Si el deudor dice cuánto puede pagar, se saltan las ofertas mayores, pero nunca la de 3 cuotas (antes de las Hardship Questions) ni la última. Esas se presentan como "la opción más baja disponible ahora", sin mencionar mínimos ni reglas | Aplicada |
| N5 | Lo que podía pagar el deudor no alcanzaba ni para 10 cuotas | Después de las Hardship Questions, la última oferta es un primer pago del 10% y el resto en 12 cuotas mensuales iguales (1 año). Con USD 485: 48,50 hoy y 12 cuotas de unos 36,40 | Aplicada |
| N6 | Un parcial dejaba un resto imposible (USD 395 en un solo pago) | Si el deudor dice cuánto puede pagar al mes, el resto se reparte en cuotas mensuales iguales (dentro del año). Con más de 3 pagos se hacen antes las Hardship Questions. El parcial de último recurso (5% a 10%) lo sigue ofreciendo el agente antes de transferir | Aplicada |
| N7 | Se aceptó un acuerdo con duda ("I'll give it a try") | Ante una aceptación con duda, el agente pregunta cuánto puede pagar cómodo al mes y vuelve a ofrecer con ese monto; solo cierra si el deudor dice que puede cumplir | Decidida; va en el ajuste de instrucciones del agente |
| N8 | El primer pago siempre caía hoy, aunque el deudor pidiera tiempo | Siempre se intenta hoy. Si pide tiempo, el primer pago puede ir hasta fin de mes. Si faltan menos de 8 días, primero se ofrece fin de este mes y, si no puede, fin del mes siguiente. Reemplaza el límite de 8 días | Aplicada. **Por confirmar** el cambio de 8 días a fin de mes |
| N9 | Nadie volvía a llamar si la llamada terminaba sin acuerdo | La lista diaria de salientes: el deudor vuelve a ella cuando la ley lo permite (7 días después de una conversación). Si pidió que lo llamen un día y una hora, se le llama entonces (falta guardar esa hora) | Aplicada en parte |
| N10 | Qué pasa después de que el deudor acepta el acuerdo | SMS solo de aviso 3 días antes de cada cuota y el link de pago el día de la cuota. Los cobradores ya no hacen recordatorios | Aviso aplicado. **Por confirmar:** si a los 5 días sin pago el acuerdo se marca roto y se avisa al equipo por Teams (u otro canal) sin cambiar el estado de la cuenta |
| N11 | Nadie revisaba las disputas | Al registrarse una disputa: la cuenta pasa a estado de disputa, sale una alerta al equipo y un cobrador decide si es válida o no. El agente busca en la base el pago que dice el deudor ("One moment while I check that for you"). Si no lo encuentra, no acusa a nadie: pide más datos y registra la disputa igual | Decidida, sin construir. **Por confirmar:** qué estado se le pone a la cuenta, qué se hace con el resultado y si se puede consultar en la base si un pago entró |
| N12 | Quien no lograba verificarse se quedaba sin salida | El agente le da un número para devolver la llamada: la línea de entrada que atiende el mismo agente | Aplicada. **Por confirmar:** la opción y el número |
| N13 | "No llamar" y quejas por las llamadas | Ante una queja: (A) disculparse y ofrecer otro horario o SMS; (B) solo disculparse; o (C) ofrecer "no llamar". Después de "no llamar": (A) solo se dejan las llamadas (la deuda sigue por SMS o cartas de la empresa) o (B) se detiene toda la cobranza hasta que la revise una persona | **Pendiente** de decidir |

## Otras decisiones

| Tema | Respuesta | Estado |
| --- | --- | --- |
| Organización del sistema | Tres partes separadas en el mismo proyecto: reglas de cobranza, agente de voz y mensajería por SMS | Aplicada |
| Lista diaria de salientes | Cada día se consulta la base y se arma la lista de cuentas a llamar: NSF, sin disputa, sin "no llamar", sin acuerdo activo y con teléfono. Respeta el límite de 7 llamadas en 7 días y no llama durante 7 días después de una conversación. Si el deudor llama antes y verifica su identidad, sale de la lista | Aplicada |
| Llamadas entrantes | Las entrantes de deudores en NSF pasarían directo al agente; las de otros estados, a una persona | **Por confirmar** |

## Siguen sin revisar

- **Negocio:** N14 (deudores vulnerables y amenazas) y N15 (proveedor de telefonía y programa de los cobradores).
- **Técnicas:** 12 de backend (B1–B6, B8, B9, B12–B15).
- **Instrucciones del agente:** P1–P12, en un solo ajuste al final.
- **Legales:** L1–L7, para revisar con un abogado.
