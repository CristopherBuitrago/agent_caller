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
| N14 | Deudores vulnerables y amenazas: no había protocolo ni dónde registrarlas | Ante angustia fuerte (llanto, "estoy desesperado"): (A) pausar la cobranza y pasar a una persona, o (B) seguir con empatía y ofrecer una persona. Si menciona hacerse daño: siempre pasar a una persona y dar la línea de crisis 988. Ante una amenaza de violencia: (A) cerrar con calma, registrarla (resultado nuevo `threat`), alertar a un supervisor y no volver a llamar hasta que una persona lo revise, o (B) solo dejarla en el resumen. Recomendada: A en ambos casos | **Pendiente** de decidir |
| N15 | Proveedor de telefonía y programa de los cobradores | Si el proveedor de SMS de la empresa ("empieza por V") también da llamadas de voz con audio en vivo, se usa ese en vez de Telnyx (ya tiene contrato y números). Preguntas: ¿cuál es el proveedor? ¿Las llamadas de los cobradores van por el mismo? ¿Qué programa usan para recibir llamadas (marcador o CRM)? De eso depende cómo se transfiere la llamada y cómo le llega el motivo al cobrador | **Pendiente** de información |

## Otras decisiones

| Tema | Respuesta | Estado |
| --- | --- | --- |
| Organización del sistema | Tres partes separadas en el mismo proyecto: reglas de cobranza, agente de voz y mensajería por SMS | Aplicada |
| Lista diaria de salientes | Cada día se consulta la base y se arma la lista de cuentas a llamar: NSF, sin disputa, sin "no llamar", sin acuerdo activo y con teléfono. Respeta el límite de 7 llamadas en 7 días y no llama durante 7 días después de una conversación. Si el deudor llama antes y verifica su identidad, sale de la lista | Aplicada |
| Llamadas entrantes | Las entrantes de deudores en NSF pasarían directo al agente; las de otros estados, a una persona | **Por confirmar** |

## Para revisar antes del piloto

### Con el jefe

Temas técnicos o de las instrucciones del agente que cambian lo que ve el equipo o cómo se trata a las personas.

| # | Tema | Propuesta | Estado |
| --- | --- | --- | --- |
| B12 | Resumen con IA de llamadas delicadas | Hoy se genera resumen aunque solo haya hablado un tercero o alguien no verificado, y en llamadas con amenazas o insultos. Propuesta: si no hubo verificación, el resumen solo dice quién contestó y cómo terminó, sin mencionar la deuda; con amenazas o insultos, el resumen lo dice en una línea sin repetir las palabras | **Pendiente** |
| B13 | Un impostor puede bloquear a la verdadera deudora | Con 5 fallos de verificación en 24 horas, entre varias llamadas, la cuenta se bloquea y pasa a una persona. Un impostor puede provocarlo a propósito y la deudora real no podría resolver con el agente ese día. Propuesta: mantener el bloqueo y enviar una alerta al equipo cuando ocurra, para que una persona contacte a la deudora | **Pendiente** |
| P3 | Qué se le dice a un tercero que contesta | Propuesta de frases fijas: "I'm calling about a personal business matter" y "I'm only able to speak with her directly". El agente nunca deja recados, no dice el nombre de la empresa si delata la cobranza (ver L3) y no acepta que el tercero pague o ayude | **Pendiente** |
| P7 | Quejas, insultos y "no llamar" | "Me llaman todo el tiempo" es una queja; "no me llamen más" es un pedido de "no llamar". Propuesta ante insultos: mantener la calma sin comentarlos y, si siguen, ofrecer una persona o cerrar la llamada con amabilidad. Depende de N13 | **Pendiente** |

### Con el abogado en EE. UU. (por medio del jefe)

Nadie los ha revisado todavía. Conviene resolverlos antes de llamar a deudores reales, porque algunos cambian cómo se diseña la llamada.

| # | Tema | Qué hay que revisar | Estado |
| --- | --- | --- | --- |
| L1 | Volver a llamar a quien pidió no ser llamado | El error E1 ya está corregido: el pedido se guarda aunque el deudor cuelgue. Falta confirmar qué exige la ley cuando el deudor lo pide (por qué medio se puede seguir contactando, si vale el pedido por teléfono). Prioritario | **Pendiente** |
| L2 | Consentimiento de grabación | Florida y otros estados exigen el consentimiento de todas las partes. Ya se aplicó que la grabación empiece con el "sí" del deudor (N3). Falta confirmar que eso basta, y si una llamada sin consentimiento puede tener transcripción y resumen con IA | **Pendiente** |
| L3 | Qué se le dice a un tercero | El nombre de la empresa ("Recovery Services") delata la cobranza. Definir qué nombre se dice, a quién y en qué momento | **Pendiente** |
| L4 | Límite de 7 llamadas en 7 días (Reg F) | La lista diaria ya respeta el límite y espera 7 días después de una conversación. Falta confirmar qué cuenta: devoluciones de llamada, llamadas fallidas, SMS, y las llamadas del agente sumadas a las de los cobradores | **Pendiente** |
| L5 | Disputas | Plazos y formato para verificar una deuda disputada, y si basta una disputa por teléfono (relacionado con N11) | **Pendiente** |
| L6 | Aviso "This communication is from a debt collector" | Se propuso quitarlo por repetido; la frase no se había dicho antes en la llamada. Confirmar el texto exacto del aviso legal | **Pendiente** |
| L7 | Deudores vulnerables y SMS | Obligaciones con deudores en situación vulnerable (relacionado con N14). Además: el consentimiento para enviar SMS de cobranza, la forma de darse de baja y el texto de los SMS (N1 y N10) | **Pendiente** |

## Siguen sin revisar

- **Técnicas:** 10 de backend (B1–B6, B8, B9, B14, B15).
- **Instrucciones del agente:** P1, P2, P4–P6 y P8–P12, en un solo ajuste al final.
