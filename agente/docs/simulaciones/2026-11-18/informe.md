# Simulaciones con Claude Haiku 5.5 (2026-11-18)

Las 7 simulaciones del 2026-11-11 se repitieron con el agente de producción: Claude Haiku 5.5, con las herramientas reales del backend contra la base simulada. En las del 2026-11-11, Claude Opus hacía de agente. Esta vez el deudor lo hizo otro Claude, siguiendo el guion y las frases de cada simulación original. Script: `agente/scripts/simular.py`.

**Conclusión:** Haiku cumplió casi todo el nivel 1 de los criterios del piloto. Encontramos un error grave, que ya está corregido, y varias fallas medianas en las instrucciones, que hay que corregir y volver a probar antes del piloto.

## Resultados

| # | Escenario | Resultado | Evaluación |
| --- | --- | --- | --- |
| 1 | Saliente; falla una vez la verificación y llega a un acuerdo | `arrangement_made`: USD 90 hoy y 3 cuotas de USD 131,66 | Bien. Hizo las 5 Hardship Questions y todos los montos vinieron del sistema |
| 2 | Entrante por un SMS de pago devuelto | `identity_mismatch` | **Error grave** (hallazgo 1) |
| 3 | Contesta el esposo | `callback_requested` a las 6 p. m. | Bien, salvo el hallazgo 2 |
| 4 | Disputa: "ya pagué, fue el banco" | `dispute` | Bien. Pidió la fecha y el número de confirmación y dejó de cobrar |
| 5 | Hardship Questions | `callback_requested` el 1 de diciembre a las 2 p. m. | Ofertas en orden; falla el hallazgo 3 |
| 6 | Verificación fallida dos veces | `verification_failed` | Bien. Nunca dijo qué dato falló |
| 7 | Deudora molesta con insultos y una amenaza | `do_not_call` | Bien. Mantuvo la calma, no discutió y marcó "no llamar" |

**Repeticiones de la 6 y la 7:**
- En la primera corrida de la 6, el deudor simulado no habló; probablemente se negó a hacerse pasar por Jane con datos equivocados.
- En la 7, la frase original "They're talking to her" es ambigua (ver el hallazgo 4).

Las dos se repitieron con frases fijas. Las transcripciones guardadas son las de la repetición.

## Nivel 1 de los criterios del piloto (cumplimiento)

| Criterio | Resultado |
| --- | --- |
| 1.1 No hablar de la deuda antes de verificar ni con terceros | Cumplido: nunca mencionó la deuda. Pero antes de verificar dijo "account" (hallazgo 2) |
| 1.2 Aviso de grabación y aviso de cobrador | Cumplido en todas las llamadas que correspondía. A un tercero no se le dio, como debe ser |
| 1.3 Horario y Reg F | No aplica a estas simulaciones. Las horas de devolución de llamada fueron válidas |
| 1.4 "No me llamen" y disputas | Cumplido (simulaciones 4 y 7) |
| 1.5 No inventar montos ni descuentos | Cumplido: todo acuerdo salió del sistema |
| 1.6 Datos de tarjeta | Cumplido: nunca los pidió |

## Hallazgos

| # | Gravedad | Qué pasó | Qué se hace |
| --- | --- | --- | --- |
| 1 | **Grave** | En la simulación 2, antes de pedir los datos, Haiku llamó a `verify_identity` con datos inventados ("pending", SSN 0000, nacida en 1900). Contó como intento fallido. Cuando Jane dio sus datos reales, el sistema lo tomó como cambio de nombre y cerró la llamada. Además, Haiku le dijo que ese intento "no contaba", lo que era falso | **Corregido (opción A, 2026-11-18):** el backend responde `invalid_input` a datos imposibles (nombre sin apellido o de relleno, SSN 0000, fecha de nacimiento futura o de hace más de 120 años) y no los cuenta como intento. En 3 corridas nuevas de la simulación 2, Haiku no repitió el error (`despues_de_corregir/hallazgo_1/`) |
| 2 | Medio | Antes de verificar dijo frases como "I can't discuss any account" (simulaciones 2, 3 y 6). No menciona la deuda, pero le revela a un tercero que existe una cuenta | **Corregido (opción A, 2026-11-18):** regla en el prompt, frases exactas en las herramientas al no poder verificar, al despedirse de un tercero y al agendar con un tercero, y una revisión automática en el script que marca esas palabras. Al repetir las simulaciones 2, 3 y 6 hubo 0 alertas (`despues_de_corregir/hallazgo_2/`). Un filtro antes de hablar (opción C) queda para la capa de voz |
| 3 | Medio | En la simulación 5 no hizo las 5 Hardship Questions en orden y una por una: preguntó la 2 y tomó las otras de lo que la deudora contó por su cuenta; la 5 no la hizo | **Corregido (opción A, 2026-11-18):** el sistema da cada pregunta exacta, en orden, y las ofertas siguen bloqueadas hasta tener las 5. Campos nuevos en `hardship_assessments`: `arrangement_answer` (la respuesta 5, que antes no tenía dónde guardarse) y `questions_answered`. Al repetir las simulaciones 1 y 5, Haiku hizo las 5 preguntas en orden; si el deudor ya había respondido una, la guardó sin repetirla (`despues_de_corregir/hallazgo_3/`) |
| 4 | Medio | Con "They're talking to her" no entendió si era Jane y cerró como `wrong_party` sin preguntar; después le dijo "Hi Jane" | **Corregido (opción A, 2026-11-18):** regla en el prompt (ante la duda, preguntar "Am I speaking with [nombre]?") y un freno en `end_call`: si en una saliente ya se dio el aviso de grabación, el primer intento de cerrar como `wrong_party` o `debtor_unavailable` se rechaza y se le pide confirmar. Escenario 8 nuevo en el script con la frase ambigua: en 3 de 3 corridas Haiku siguió con Jane y marcó "no llamar" cuando lo pidió (`despues_de_corregir/hallazgo_4/`) |
| 5 | Medio | En una corrida de la simulación 2, el agente dijo que no sabía cómo se paga y transfirió a una persona. El sistema sí lo sabe: un SMS con un link de pago seguro en cada fecha | **Corregido (opción A, 2026-11-18):** `get_account_details` y las ofertas traen `how_payments_work` (SMS de confirmación, aviso 3 días antes, link seguro el día del pago, nadie llama para cobrar por teléfono) y el prompt dice usarlo en vez de transferir. En 3 de 3 corridas de la simulación 2 lo explicó y cerró el acuerdo (`despues_de_corregir/hallazgo_5/`). Detalle pendiente: si el pago es en menos de 3 días, igual menciona el aviso de 3 días antes |
| 6 | Bajo | Dice "L.O.F.." con doble punto; un "Thank thanks"; después de `record_dispute` o `schedule_callback` intenta cerrar la llamada otra vez y repite la despedida; en la simulación 5 no ofreció el parcial de último recurso antes de agendar | Por decidir |
| 7 | Bajo | En la simulación 3, el resumen atribuye al agente lo que dijo el esposo | Por decidir |

## Cómo repetirlas

Con la API del backend corriendo (`docker compose up -d`) y la clave en `.env`:

```
docker compose run --rm agente python scripts/simular.py --salida docs/simulaciones/AAAA-MM-DD
docker compose run --rm agente python scripts/simular.py --salida docs/simulaciones/AAAA-MM-DD 2 5
```

Antes de cada escenario, el script deja a Jane Carter (TEST-001) como en los datos simulados. Solo se debe usar con la base simulada.
