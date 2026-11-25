# Decisiones pendientes de las pruebas de voz (22 de noviembre)

Lo que se repitió en las 5 pruebas o afectó la conversación. Responder una por una debajo de cada punto.

## 1. "What is L.O.F.?" sin respuesta (pruebas 2, 4 y 5)
**Qué pasa:** antes de verificar, Lucy no dice qué es L.O.F. La persona no sabe quién la llama. La FDCPA exige que el cobrador se identifique.
**Opciones:**
- A (recomendada): *"L.O.F. is the company that sent you the message. I can share the details once I confirm I'm speaking with the right person."* El texto lo valida el abogado.
- B: dejarlo como está hasta que el abogado responda.

**Respuesta:** Escojo la opcion A

## 2. Lucy inventa la hora al agendar (pruebas 1 y 5)
**Qué pasa:** el deudor dice "in the morning" y Lucy agenda a las 10:00 o a las 9:00 sin preguntar.
**Opciones:**
- A (recomendada): si el deudor no dice una hora exacta, Lucy pregunta: *"What time in the morning works for you?"*. La herramienta no acepta una hora que el deudor no dijo.
- B: tomar una hora fija por franja: mañana 10:00, tarde 2:00 y noche 6:00.

**Respuesta:** No pasa nada si Lucy inventó la hora, es correcto ya que la persona solo dijo "En la mañana". Si el deudor elige una hora en especifico, pues se agenda a esa hora, de resto, que lucy lo haga.

## 3. Agenda sin un sí claro (prueba 5)
**Qué pasa:** Mark dijo "si no es en diciembre, no me llamen", Lucy le preguntó si quería la llamada y él no contestó eso. Lucy agendó igual.
**Opciones:**
- A (recomendada): solo agendar con un sí claro. Si no lo hay, cerrar sin agendar; la lista diaria lo vuelve a llamar según la Reg F.
- B: dejarlo como está.

**Respuesta:** En este caso, vimos que el deudor queria el pago el 1 dediciembre cuando solo se aceptan los fines de mes, en ese caso dejemos un poco de flexibiidad, maximo dos dias despues del fin de mes

## 4. Turnos demasiado largos (pruebas 2 y 5)
**Qué pasa:** después de verificar habla unos 50 s seguidos (aviso legal más dos deudas), y al cerrar el acuerdo unos 28 s.
**Opciones:**
- A (recomendada): partirlo. En el primer turno, el aviso legal y cuántas deudas son; en el siguiente, la primera deuda. El cierre del acuerdo, en una frase: *"You'll get a text confirming it, and a secure link to pay on the payment date."*
- B: dejarlo como está.

**Respuesta:** Escojo la A, es mejor partirlos y que el deudor no quede loco

## 5. Quejas por los SMS (pruebas 4 y 5)
**Qué pasa:** "Me llegan muchos mensajes, ¿por qué no paran?" Lucy no hace nada. Hoy no hay forma de pausar los SMS de un deudor ni de un número equivocado. Según la TCPA, se puede revocar el consentimiento de palabra, y los SMS a números equivocados son causa frecuente de demandas.
**Opciones:**
- A (recomendada): herramienta para pausar los SMS. Si la persona verificada lo pide, se pausan los SMS de ese deudor. Si alguien sin verificar dice que el número no es del deudor, ese teléfono queda "para revisar" y se pausan sus SMS. Cambia el modelo de datos: los campos se presentan antes de construir.
- B: solo anotarlo en el resumen para que un cobrador lo revise.

**Respuesta:** Primero, si la persona dice que le llegan muchos mensajes, no hacer nada por ahora, seguir igual. Segundo, si alguien sin verificar dice que el numero no es del deudor, no marcar el telefono como "para revisar" en vez de eso, dile que para confirmar le deje hacer unas preguntas de verificacion de identidad, en caso de que no sea el deudor pues simplemente cuelga y ahi si se marca, de resto no.

## 6. Lucy dice el nombre antes de terminar de verificar (pruebas 1, 2 y 5)
**Qué pasa:** después del SSN y la fecha, Lucy pregunta *"Am I speaking with [nombre]?"*. Quien tenga el SSN y la fecha robados recibe el nombre y solo tiene que decir "yes". Esto contradice N2 (jefe, 2026-11-13: el deudor dice su nombre).
**Opciones:**
- A: mantenerlo (es más cómodo para el deudor) y aceptar el riesgo por escrito.
- B (recomendada): volver a pedir el nombre completo. El deudor lo dice; Lucy no lo lee.

**Respuesta:** Es muy incomodo tener a cada rato que decir el nombre, aparte eso no fe decision de mi jefe, lo coloque así porque estabas jodiendome constantemente para que cambiaramos esa opcion para más seguridad y privacidad, eso de edecir el nombre al final vale mrd.

## 7. La regla N8 hizo perder un pago (prueba 5)
**Qué pasa:** Mark podía pagar el 1 de diciembre y el límite era el 30 de noviembre. No hubo acuerdo.
**Opciones:**
- A (recomendada): si faltan 10 días o menos para fin de mes, el primer pago puede ir hasta el día 5 del mes siguiente.
- B: dejar la regla como está.

**Respuesta:** Maximo dos dias despues de fin de mes

## 8. No siempre ofrece el pago con fecha antes de agendar (prueba 1)
**Qué pasa:** la regla P9 dice que, si el deudor no tiene el dinero todavía, primero se le ofrece poner el pago para cuando lo tenga. En la prueba 1 Lucy no lo hizo; en la 5 sí.
**Opciones:**
- A (recomendada): que el backend lo exija. Si el deudor verificado pide que lo llamen y no se le ofreció nada, la herramienta le recuerda a Lucy ofrecer primero el pago con fecha.
- B: solo reforzar el prompt.

**Respuesta:** Elijo la A

## 9. Silencio sin manejo (prueba 3)
**Qué pasa:** nadie habló durante un minuto y Lucy no dijo nada. En una llamada real, la línea queda abierta gastando minutos.
**Opciones:**
- A (recomendada): a los 10 s de silencio, *"Are you still there?"*; a los 30 s, se despide y cierra como `callback_requested`.
- B: otros tiempos (indicar cuáles).

**Respuesta:** Elijo la A

## 10. Lucy habla de "error" y de "system" (prueba 4)
**Qué pasa:** dijo *"I made an error and the system closed this call"*.
**Opciones:**
- A (recomendada): una frase fija para cierres inesperados, y agregar "system" y "error" a la revisión automática de las simulaciones.
- B: dejarlo, porque la causa ya se corrigió.

**Respuesta:** A

## 11. Demora por turno (todas)
**Qué pasa:** mediana de 1,65 s y máximo de 4,15 s, más el 1,5 s de silencio que cierra el turno. Lo que percibe el deudor son unos 3,4 s; la meta del piloto es 1,5 s.
**Opciones:**
- A (recomendada): respuesta por partes. Deepgram empieza a hablar con la primera frase, sin esperar la respuesta completa de Claude.
- B: bajar el silencio a 1 s (con 0,2 s contestaba a pedazos).
- C: A y B.

**Respuesta:** Pues mi padrastro dijo que lo sentia bien de velocidad, pero si hagamos lo de respuestas por partes a ver que tal. Una ultima cosa, los comodines que utilizamos para rellenar los silencios como "Let me check our records", si lo revisas, vas a observar que hay momentos en los uqe esas frases no tienen sentido segun el contexto, claude deberia ser inteligente y utilizar comodines que se ajusten al contexto actual

---

# Plan de implementación (aprobado el 2026-11-24, sin construir)

Rama: `capa_de_voz`. Orden: 7, 8, 1, 10, 9, 4, 5, 11. Al terminar cada punto: pruebas, anotarlo en `README.md` y `PENDIENTES.md`, y repetir la simulación o la prueba de voz que corresponda.

**Decisiones sin cambios:**
- **2:** Lucy elige la hora si el deudor no da una exacta.
- **3:** se deja como está. La respuesta escrita en ese punto era la de la regla N8.
- **6:** Lucy sigue diciendo el nombre después del SSN y la fecha. Es decisión del desarrollador del 2026-11-24, no del jefe. Riesgo aceptado: quien tenga el SSN y la fecha recibe el nombre. Hay que actualizar la fila de N2 en `README.md`, que todavía describe el flujo viejo.

## 7. Regla N8: hasta 2 días después de fin de mes
- **Dónde:** `backend/src/cobranza/domain/arrangement.py`, función `latest_first_payment_date`. Se suman 2 días al fin de mes que da hoy la función, también cuando salta al mes siguiente (`DAYS_AFTER_MONTH_END = 2`).
- **Cuotas siguientes:** si el primer pago cae el 1 o el 2 del mes, van el mismo día de cada mes (`monthly_due_date` ya lo hace); si cae el último día, van a fin de cada mes.
- **Texto de la herramienta:** revisar `first_payment_date_rule` en `agent_tools.py` (`_first_payment_window`).
- **Pruebas:** 22 nov → 2 dic; 27 ene → 2 mar; el 3 de diciembre se rechaza.

## 8. Ofrecer el pago con fecha antes de agendar (regla P9)
- **Dónde:** `_tool_schedule_callback` en `agent_tools.py`.
- **Regla:** si el deudor está verificado, tiene cuentas cobrables y en la llamada no se presentó ninguna oferta (`self._proposals` vacío), el primer intento no agenda. Responde `error: offer_first` con el `next_step` de P9 (*"If it helps, we can set your first payment for when you'll have the money…"*). El segundo intento sí agenda, como en el freno del hallazgo 4.
- **Pruebas:** primer intento rechazado; segundo, agendado; sin verificar o con una oferta ya presentada, agenda de una vez.

## 1. "What is L.O.F.?"
- **Dónde:** el prompt (`agent_system_prompt.md`, paso 2).
- **Frase:** *"L.O.F. is the company that sent you the message. I can share the details once I confirm I'm speaking with the right person."*
- **Pendiente con el abogado:** validar el texto. Anotarlo en L7 de `docs/para_el_jefe/pendientes_externos.md`.

## 10. "error" y "system"
- **Dónde:** el prompt (nunca decir "error", "system" ni que la llamada "se cerró sola") y `agente/scripts/simular.py`, donde se agrega `\bsystem\b` y `\berror\b` a `INTERNAL_DETAILS`.
- **Frase fija** si la llamada termina de forma inesperada: *"I'm sorry, we need to end the call here. You can call us back anytime. Goodbye."*

## 9. Silencio
- **Dónde:** `agente/.../voice/bot.py` (`UserTurnProcessor(user_idle_timeout=...)` y su evento `on_user_turn_idle`) y `voice/agent_processor.py`.
- **Regla:** a los 10 s sin voz, Lucy dice *"Are you still there?"*; a los 30 s dice *"I'll end the call now. You can call us back anytime. Goodbye."* y llama a `session.hang_up()`, que cierra como `callback_requested`. El contador vuelve a 0 cuando la persona habla.
- **Antes de usarlos, revisar en Pipecat 1.16** cómo se llaman de verdad `user_idle_timeout` y `on_user_turn_idle` (están en la documentación de `turns/user_turn_processor.py`).
- **Pruebas:** con frames, sin voz por 10 s y por 30 s (tiempos cortos en la prueba).

## 4. Turnos más cortos
- **Dónde:** el `next_step` de `confirm_identity` y `get_account_details` en `agent_tools.py`, y el cierre del acuerdo (`record_offer_response`).
- **Primer turno después de verificar:** el aviso legal y *"I see [N] payments that were returned. Let's start with the oldest one."* Termina ahí.
- **Siguiente turno:** solo la primera deuda (acreedor, monto, motivo, saldo) y *"Would you like to take care of it today?"*
- **Cierre del acuerdo:** *"You'll get a text confirming it, and a secure link to pay on the payment date."* El texto completo de `how_payments_work` se usa solo si el deudor pregunta.
- **Pruebas:** que el `next_step` pida partir el turno, y repetir la simulación 1 y la prueba de voz con dos deudas (Mark Holloway).

## 5. Número equivocado
**Tabla nueva `phone_reports` (campos aprobados el 2026-11-24):**

| Campo | Tipo | Para qué |
| --- | --- | --- |
| `id` | uuid | Identificador |
| `phone` | texto E.164 | Número reportado como equivocado |
| `call_id` | uuid → `calls` | Llamada donde se reportó |
| `reported_at` | timestamptz | Cuándo se reportó |
| `reviewed_at` | timestamptz (vacío hasta que se revise) | Cuándo lo revisó un cobrador |

- **Flujo:** si alguien sin verificar dice que el número no es del deudor, Lucy le pide verificarse (*"To confirm, may I ask you a few identity questions?"*).
  - Si verifica, sigue la llamada normal.
  - Si la verificación falla, o si dice que no es el deudor y no quiere verificarse, Lucy llama a la herramienta nueva `report_wrong_number`, se despide con *"Thank you for letting us know. Goodbye."* y cierra como `wrong_party`.
- **Las quejas por muchos mensajes no hacen nada** (decisión del 2026-11-24).
- **Efecto:** mientras el reporte no esté revisado, ese teléfono no recibe SMS (`messaging`: la consulta de envíos excluye esos teléfonos) ni entra a la lista diaria (`postgres_outbound_list_repository.py`).
- **Piezas:** dominio, interfaz del repositorio, implementación en PostgreSQL, caso de uso `ReportWrongNumber`, herramienta, prompt, `ALTER` en `001_schema.sql`, `ALTER` en la base local y validación con una base nueva.
- **Pruebas:** unitarias, de integración (el teléfono queda fuera de la lista diaria y de los SMS) y una simulación nueva.

## 11. Respuesta por partes y relleno según el contexto
- **Dónde:** `agente/.../infrastructure/claude_conversation_model.py` (pasar de `messages.create` a `messages.stream`), el puerto `ConversationModel`/`ModelConversation` (una forma de entregar el texto por partes) y `voice/agent_processor.py`.
- **Cómo:**
  1. Mientras Claude escribe, cada frase completa (termina en `.`, `?` o `!`) se manda a Deepgram como `TTSSpeakFrame`.
  2. El texto que Claude escribe antes de pedir una herramienta ("Let me pull up your account.") se dice de una vez. Ese es el relleno según el contexto.
  3. En el prompt: *"Before calling a tool, say one short natural phrase that fits what you are doing"*.
  4. Los rellenos fijos (`FILLERS` en `agent_processor.py`) quedan solo de respaldo si no hay texto en 1 s, con una frase neutra (*"Mm-hmm."*). Quitar *"Let me check our records"*.
- **Cuidado:**
  - el chat y las simulaciones usan el mismo puerto: deben seguir funcionando sin partes;
  - la transcripción guarda la frase completa;
  - si hay una interrupción, se deja de enviar texto a Deepgram.
- **Medir:** la demora hasta la primera palabra, antes y después, con la misma prueba de voz.
