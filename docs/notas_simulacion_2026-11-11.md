# Notas de la simulación del agente (2026-11-11)

Prueba sin API: Claude Code hizo de agente siguiendo `agent_system_prompt.md` y llamando las herramientas reales contra PostgreSQL. El desarrollador hizo de deudor (Jane Carter, TEST-001). Estas notas son propuestas: nada se ha cambiado todavía en el prompt ni en el código.

## Pedidos del jefe y del desarrollador

| # | Pedido | Origen | Estado |
| --- | --- | --- | --- |
| J1 | Verificar sin nombre completo. El agente lee los últimos 4 del SSN y la fecha de nacimiento y el deudor responde sí o no: "Para asegurarme que estoy hablando con Jane Carter, por favor confirmeme si los ultimos digitos de su SSN son xxx y su fecha de nacimiento es xxx" | Jefe | **Por revisar con el jefe.** Claude advierte: revela datos personales a quien conteste (puede ser un tercero), cualquiera puede decir "sí", y el diseño actual guarda SSN y fecha como hash (no se pueden leer) y no deja que la IA los vea. Propuesta: quitar el nombre, pero que el deudor siga diciendo los dos datos |
| D1 | Quitar la frase "This communication is from a debt collector" del aviso legal, porque se siente repetida | Desarrollador | **Por revisar.** El saludo no dice "debt collector", así que esa frase no se había dicho antes en la llamada. La FDCPA pide el aviso completo en la primera comunicación y "communication from a debt collector" en las siguientes; que lo confirme el abogado antes de quitarla |

## Ajustes propuestos al prompt

1. **Presentarse como asistente virtual desde el saludo.** Si el deudor pregunta "who am I speaking with?" antes de aceptar la grabación, el prompt no dice qué hacer.
2. **Frase fija para "¿por qué me llaman?" antes de verificar:** "I can share the reason once I confirm I'm speaking with the right person." Sin mencionar deuda ni cobranza. Cubre también al que devuelve una llamada perdida en una entrante.
3. **Saludo saliente en una sola frase:** preguntar por el deudor y pedir permiso de grabación juntos ("May I speak with Jane Carter? This call is recorded for quality and compliance purposes, is that okay?"). Si solo se avisa, hay que volver a preguntar.
4. **Turno demasiado largo tras verificar:** aviso legal + deuda + oferta no caben en "una o dos frases". Propuesta: aviso y deuda en un turno, terminar con "Would you like to take care of it today?", y la oferta en el siguiente.
5. **Preguntas sobre el cargo de USD 35:** el prompt no dice cómo explicarlo. El agente solo sabe que es el "returned payment fee"; no debe inventar quién lo cobra ni por qué. Propuesta: frase fija ("That is the returned payment fee on your account; I'm not able to remove it") y ofrecer a una persona si insiste.
6. **Disputa o confusión:** "I tried to pay that day, I'm not sure what happened" no es "ya pagué" ni "error del banco". Hace falta decir en el prompt dónde está el límite, o que el agente pregunte ("Are you saying the payment went through?") antes de marcar disputa.
7. **El orden de las ofertas choca con un parcial que propone el deudor.** Al decir "puedo dar 90", el sistema arma el parcial (USD 90 hoy y USD 395 en 30 días) aunque no se han ofrecido 2 ni 3 cuotas. Para alguien con USD 300 al mes, el resto de USD 395 en un solo pago probablemente no se cumpla. Preguntas para el jefe: ¿se ofrece primero el plan de cuotas antes de aceptar el parcial que propone el deudor? ¿El resto de un parcial puede ir en cuotas en vez de un solo pago?
8. **`next_step` tras rechazar un parcial dice "Call propose_offer"**, aunque el deudor acabe de proponer otro monto. Debería decir que, si el deudor ya dio un monto, se use `propose_partial_payment`.
9. **El deudor ya dijo su límite ("máximo 4 cuotas") y el sistema exige recorrer 2 y 3 cuotas una por una.** Es lo que decidió el jefe (el deudor no propone el plan), pero alarga la llamada y puede sonar a que el agente no escucha. Opciones: (a) mantenerlo; (b) dejar que el agente presente 2 y 3 en un mismo turno ("two payments of X or three of Y"); (c) si el deudor dice que no puede con un monto, saltar las ofertas cuya primera cuota es mayor. El agente no debe marcar como rechazada una oferta que el deudor no escuchó.
10. **Un parcial rechazado no se puede aceptar después, aunque el deudor cambie de opinión.** El agente tuvo que armar otra vez el mismo parcial de USD 90 (nuevo `proposal_id`). Funciona, pero el registro queda con dos propuestas iguales, una rechazada. Es aceptable; solo se anota.
11. **Confirmar montos y fechas antes de aceptar.** El agente repite el acuerdo exacto y espera un "sí" antes de `record_offer_response(accepted=true)`. Conviene ponerlo explícito en el prompt.
12. **"Sí, pero con descuento" no es un sí.** El agente no registra la aceptación cuando el deudor la condiciona; niega el descuento, corrige el monto (el deudor dijo USD 370, el resto real es USD 395) y vuelve a pedir confirmación. Conviene decir en el prompt que un "sí" con condiciones no cuenta y que siempre se corrigen las cifras equivocadas del deudor.
13. **Aceptación tibia.** "I'll give it a try" se tomó como un sí, después de repetir montos y fechas. Pero la deudora dijo antes que tiene USD 300 para todo el mes, y el segundo pago es de USD 395: el acuerdo tiene riesgo alto de incumplirse. Pregunta para el jefe: ¿el agente debe aceptar un acuerdo que el deudor duda poder cumplir, o insistir en cuotas o en las Hardship Questions?
14. **"You will receive the payment instructions"** lo dice el `next_step`, pero hoy no existe ese envío: el pago con tarjeta (Función 6) está bloqueado y no hay canal definido (SMS, correo). Hay que definir qué recibe el deudor y por dónde.

## Resultado de la llamada de prueba

Llamada saliente a Jane Carter (ACC-T001). Consentimiento de grabación, 1 fallo de verificación (SSN mal dicho) y verificación correcta en el segundo intento. Rechazó: pago total, parcial de USD 450, parcial de USD 90 y 2 cuotas. Aceptó un parcial de USD 90 hoy y USD 395 el 2026-12-11. Lo guardado en la base: cuenta en `PTP`, acuerdo `partial` por USD 485 con 2 pagos (9.000 y 39.500 centavos), llamada cerrada como `arrangement_made` con `verification_attempts = 2`. Todas las reglas las aplicó el backend; ninguna herramienta devolvió error.
