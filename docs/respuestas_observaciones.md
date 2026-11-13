# Agente de cobranza NSF: respuestas a las observaciones

Actualizado: 2026-11-13. Referencia: `docs/Informe_Simulaciones_Agente_Cobranza_NSF.pdf` (códigos N, B, P y L) y la simulación 8 (S1 y S2). Las respuestas del jefe del 2026-11-12 las trajo el desarrollador.

**Estado:** **Aplicada** = construida y probada · **Decidida** = el jefe respondió, falta construirla · **Por confirmar** = aplicada o decidida, pero falta validarla · **Pendiente** = falta decidir.

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
| N1 | No había forma de que el deudor pagara un pago agendado | Al cerrar el acuerdo se envía un SMS de confirmación; el día de cada cuota, otro SMS con el link de pago. Se envían aunque el deudor esté marcado "no llamar" (aceptó el acuerdo). **Jefe (2026-11-12):** el proveedor de SMS es **Vaspian** | Aplicada con proveedor de prueba. **Por confirmar:** si hay página de pago del procesador |
| N2 | Verificar leyendo el SSN y la fecha para que el deudor diga sí o no | Se deja como está: el deudor dice su nombre completo, los últimos 4 del SSN y su fecha de nacimiento. Leerle los datos los revela a quien conteste y no se puede con el diseño actual (los datos están cifrados). **Jefe (2026-11-13):** confirmado, "porque leerle los datos los revela a quien conteste y no se puede con el diseño actual" | Aplicada (confirmada) |
| N3 | Saludo y aviso de grabación en las salientes | El saludo solo pregunta por el deudor ("May I speak with Jane Carter?"). Cuando confirma que es él, el agente se identifica y avisa de la grabación. **Cambia con L2:** ya no se pregunta ni se espera un "sí"; solo se informa | Aplicada (con L2) |
| N4 | Se ofrecían opciones que el deudor ya había descartado | Si el deudor dice cuánto puede pagar, se saltan las ofertas mayores, pero nunca la de 3 cuotas (antes de las Hardship Questions) ni la última. Esas se presentan como "la opción más baja disponible ahora", sin mencionar mínimos ni reglas | Aplicada |
| N5 | Lo que podía pagar el deudor no alcanzaba ni para 10 cuotas | Después de las Hardship Questions, la última oferta es un primer pago del 10% y el resto en 12 cuotas mensuales iguales (1 año). Con USD 485: 48,50 hoy y 12 cuotas de unos 36,40 | Aplicada |
| N6 | Un parcial dejaba un resto imposible (USD 395 en un solo pago) | Si el deudor dice cuánto puede pagar al mes, el resto se reparte en cuotas mensuales iguales (dentro del año). Con más de 3 pagos se hacen antes las Hardship Questions. El parcial de último recurso (5% a 10%) lo sigue ofreciendo el agente antes de transferir | Aplicada |
| N7 | Se aceptó un acuerdo con duda ("I'll give it a try") | Ante una aceptación con duda, el agente pregunta cuánto puede pagar cómodo al mes y vuelve a ofrecer con ese monto; solo cierra si el deudor dice que puede cumplir | Decidida; va en el ajuste de instrucciones del agente |
| N8 | El primer pago siempre caía hoy, aunque el deudor pidiera tiempo | Siempre se intenta hoy. Si pide tiempo, el primer pago puede ir hasta fin de mes (si faltan menos de 8 días, fin del mes siguiente). **Jefe (2026-11-12):** aprobado. Además, el agente pregunta cuándo recibe dinero el deudor (p. ej. "el 5 de cada mes") para poner ahí las fechas | Aplicada. **Decidida:** la pregunta por la fecha de ingreso |
| N9 | Nadie volvía a llamar si la llamada terminaba sin acuerdo | La lista diaria de salientes: el deudor vuelve a ella cuando la ley lo permite (7 días después de una conversación). Si pidió que lo llamen un día y una hora, se le llama entonces (falta guardar esa hora). **Jefe (2026-11-12):** la cuenta sigue en `NSF`, aunque el deudor pida no ser llamado | Aplicada en parte |
| N10 | Qué pasa después de que el deudor acepta el acuerdo | SMS solo de aviso 3 días antes de cada cuota y el link de pago el día de la cuota. Los cobradores ya no hacen recordatorios. **Jefe (2026-11-12):** si 5 días después de la fecha la cuota sigue sin pagar, el acuerdo queda roto y la cuenta **vuelve a `NSF`** (entra de nuevo a la lista de salientes). Sin alerta por Teams: pueden ser muchísimos casos, y la empresa ya revisa los acuerdos rotos con reportes semanales y mensuales | Aplicada (2026-11-13). **Por confirmar:** conectar el aviso de pago del procesador y el estado de la cuenta al pagar todo (ver `docs/dudas_para_el_jefe.md`) |
| N11 | Nadie revisaba las disputas | Al registrarse una disputa, la cuenta pasa a un **estado nuevo `DISPUTE`**. **Jefe (2026-11-12):** el resto (alerta, revisión, búsqueda del pago) queda en pausa hasta tener la base real, el esquema o el diagrama EER | Decidida en parte; en pausa |
| N12 | Quien no lograba verificarse se quedaba sin salida | El agente le da un número para devolver la llamada: la línea de entrada que atiende el mismo agente. **Jefe (2026-11-12):** él entrega el número después | Aplicada. **Por confirmar:** el número |
| N13 | "No llamar" y quejas por las llamadas | **Jefe (2026-11-12):** solo se marca "no llamar" si el deudor lo pide de forma explícita ("registren en el sistema que no me llamen"); si no, se sigue cobrando. La cuenta sigue en `NSF`. Si el deudor se queja de que lo llaman mucho, el agente revisa en el sistema la última fecha de contacto y se la dice con la información real: "According to our records, our last call was on [day] at [time]...", y solo si en esa llamada hubo un acuerdo, que por eso se le vuelve a llamar. Si no hubo acuerdo, solo la fecha y la hora. El dato debe salir del sistema, nunca inventarse (confirmado por el desarrollador, 2026-11-12) | Aplicada (herramienta `get_last_contact`, 2026-11-13) |
| N14 | Deudores vulnerables y amenazas: no había protocolo ni dónde registrarlas | **Jefe (2026-11-12):** ante angustia, el agente le pide con calma que se tranquilice, le dice que es solo una deuda y que la empresa quiere ayudarle de la mejor manera evaluando las opciones, y sigue. **Desarrollador (2026-11-12):** si el deudor dice sentirse mal, el agente mantiene la calma, le dice que es solo una deuda y que hay solución; si quiere terminar, es el deudor quien cuelga. Ante una amenaza, el agente no lo toma personal, dice que se está buscando una solución y sigue la llamada: nunca cuelga ni transfiere por eso | Decidida |
| N15 | Proveedor de telefonía y programa de los cobradores | **Jefe (2026-11-12):** todas las llamadas van por el mismo proveedor. **Vaspian** es el marcador y recibe las entrantes (la negociación para cambiar a Zoom está en pausa). Una transferencia va al número principal, que hace una cola de hasta 10 minutos con música y la pasa al cobrador 1, 2 o 3, o al agente de IA. El CRM es **Actos Software**, en migración a **Lariat Software**; ahí está toda la información de los deudores | Decidida. **Por confirmar:** que Vaspian pueda enviar el audio de la llamada en vivo al agente |

## Otras decisiones

| Tema | Respuesta | Estado |
| --- | --- | --- |
| Organización del sistema | Tres partes separadas en el mismo proyecto: reglas de cobranza, agente de voz y mensajería por SMS | Aplicada |
| Lista diaria de salientes | Cada día se consulta la base y se arma la lista de cuentas a llamar: NSF, sin disputa, sin "no llamar", sin acuerdo activo y con teléfono. Respeta el límite de 7 llamadas en 7 días y no llama durante 7 días después de una conversación. Si el deudor llama antes y verifica su identidad, sale de la lista | Aplicada |
| Llamadas entrantes | Las entrantes de deudores en NSF pasan directo al agente; las de otros estados, a una persona. **Confirmada por el jefe (2026-11-12)** | Aplicada |

## Revisadas con el jefe antes del piloto

| # | Tema | Respuesta | Estado |
| --- | --- | --- | --- |
| B12 | Resumen con IA de llamadas delicadas | **Confirmada:** si no hubo verificación, el resumen solo dice quién contestó y cómo terminó, sin mencionar la deuda; con amenazas o insultos, el resumen lo dice en una línea sin repetir las palabras | Decidida |
| B13 | Un impostor puede bloquear a la verdadera deudora | **Jefe:** es muy poco probable que alguien intente pagar la deuda de otra persona. Se deja como está, sin alerta | Decidida (sin cambios) |
| P3 | Qué se le dice a un tercero que contesta | Solo se dice que es un asunto personal, o que legalmente la información solo se le puede dar a la persona: "It's a personal matter" / "Legally, I can only share this information with Jane Carter". Nunca se dejan recados | Aplicada |
| P7 | Quejas, insultos y "no llamar" | Sigue lo decidido en N13: "no llamar" solo si el deudor lo pide de forma explícita; si no, se sigue | Decidida |

## Respuestas legales (abogado del jefe)

| # | Tema | Respuesta | Estado |
| --- | --- | --- | --- |
| L1 | Volver a llamar a quien pidió no ser llamado | Sigue lo decidido en N13: solo cuenta el pedido explícito | Decidida |
| L2 | Consentimiento de grabación | Solo se **informa** que la llamada puede ser grabada, sin preguntar ni esperar respuesta: "This call may be recorded for quality and compliance purposes." Cambia N3 y la Función 3 (hoy se pregunta). Si el deudor dice que no quiere ser grabado, el agente le explica que es un requisito y, si insiste, cierra la llamada sin hablar de la deuda (`recording_refused`; opción b, desarrollador, 2026-11-12) | Aplicada |
| L3 | Qué se le dice a un tercero | La empresa es **Live Oak Financial**. El nombre completo solo se dice cuando la persona ya está verificada. Antes de verificar, lo máximo que se dice son las siglas **"L.O.F."** | Aplicada |
| L4 | Límite de 7 llamadas en 7 días (Reg F) | **Sí:** cuentan las devoluciones de llamada, las llamadas fallidas y las llamadas del agente sumadas a las de los cobradores | Decidida |
| L5 | Disputas | Sigue lo decidido en N11 (en pausa) | En pausa |
| L6 | Aviso "This communication is from a debt collector" | Es totalmente legal: se deja el aviso como está | Decidida (sin cambios) |
| L7 | Deudores vulnerables y SMS | Obligaciones con deudores en situación vulnerable (N14) y el consentimiento, la baja y el texto de los SMS de cobranza (N1 y N10) | **Pendiente** |

## Siguen sin revisar

- **Con el abogado:** L7.
- **Técnicas:** 10 de backend (B1–B6, B8, B9, B14, B15).
- **Instrucciones del agente:** P1, P2, P4–P6 y P8–P12, en un solo ajuste al final.
