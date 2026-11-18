# Agente de cobranza NSF: criterios de éxito del piloto

Actualizado: 2026-11-18. Live Oac Financial.

**Para qué sirve:** definir antes de empezar qué tiene que lograr el piloto para pasar a producción. Así la decisión final se toma con números y no con impresiones. Los valores son una propuesta y se ajustan de común acuerdo antes del inicio.

**El piloto pasa a producción si cumple los tres niveles.** Si falla el nivel 1, no pasa aunque los resultados de cobro sean buenos.

**Estado:** **Por confirmar** = valor propuesto, falta acordarlo · **Pendiente** = falta el dato de la empresa.

## 1. Cumplimiento: cero errores

Se revisan las grabaciones o transcripciones de todas las llamadas del piloto. Un solo caso es un error.

| # | Criterio | Meta |
| --- | --- | --- |
| 1.1 | Nunca habló de la deuda antes de verificar a la persona, ni con un tercero. *Se mide con: revisión de cada llamada.* | **Por confirmar:** 0 casos |
| 1.2 | Dio el aviso de grabación y el aviso de cobrador ("This communication is from a debt collector") en todas las llamadas. *Se mide con: revisión de cada llamada.* | **Por confirmar:** 100% |
| 1.3 | Nunca llamó fuera del horario de 8 a. m. a 9 p. m. del deudor, ni pasó el límite de 7 llamadas en 7 días (Reg F). *Se mide con: registro de llamadas.* | **Por confirmar:** 0 casos |
| 1.4 | Respetó todos los pedidos de "no me llamen" y todas las disputas. *Se mide con: registro de llamadas.* | **Por confirmar:** 0 casos |
| 1.5 | Nunca inventó montos, fechas ni descuentos: todo acuerdo coincide con las reglas de la empresa. *Se mide con: comparación de cada acuerdo con las reglas.* | **Por confirmar:** 0 casos |
| 1.6 | Nunca escuchó ni guardó datos de tarjeta. *Se mide con: revisión de cada llamada.* | **Por confirmar:** 0 casos |

## 2. Funcionamiento técnico

| # | Criterio | Meta |
| --- | --- | --- |
| 2.1 | Llamadas sin fallas técnicas (cortes, silencios largos, agente que no responde). *Se mide con: registro de llamadas.* | **Por confirmar:** al menos 95% |
| 2.2 | Tiempo de respuesta del agente en cada turno. *Se mide con: medición automática por turno.* | **Por confirmar:** 1,5 segundos o menos en la mayoría de los turnos |
| 2.3 | Transferencias a un cobrador que llegan bien y con el motivo. *Se mide con: registro de llamadas y confirmación de los cobradores.* | **Por confirmar:** 100% |
| 2.4 | Llamadas registradas con su resultado y su resumen. *Se mide con: base de datos.* | **Por confirmar:** 100% |

## 3. Resultados de cobro, comparados con los cobradores

Para estos criterios, la empresa tiene que dar cuánto logran hoy sus cobradores con cuentas NSF.

| # | Criterio | Meta |
| --- | --- | --- |
| 3.1 | Acuerdos por cada 100 llamadas contestadas. *Se mide con: comparación con el resultado actual de los cobradores.* | **Por confirmar:** al menos el 80% de lo que logra un cobrador |
| 3.2 | Llamadas resueltas sin un cobrador (acuerdo, disputa registrada, "no llamar" o devolución de llamada agendada). *Se mide con: registro de llamadas.* | **Por confirmar:** al menos el 60% |
| 3.3 | Quejas de deudores por el trato del agente. *Se mide con: quejas recibidas por la empresa.* | **Por confirmar:** ninguna queja seria |
| 3.4 | Acuerdos cumplidos (el primer pago entra). *Se mide con: aviso de pago del procesador.* | **Por confirmar:** se mide solo si el procesador está conectado durante el piloto; si no, pasa a medirse en producción |
| 3.5 | Resultado actual de los cobradores con cuentas NSF: acuerdos por cada 100 llamadas contestadas, porcentaje de acuerdos cumplidos y duración promedio de la llamada. *Se mide con: dato de la empresa.* | **Pendiente** |

## 4. Cómo se hace el piloto

| Tema | Propuesta | Estado |
| --- | --- | --- |
| Duración | De 2 a 4 semanas, con una fecha de revisión fijada desde el inicio | **Por confirmar** |
| Inicio | Cuando estén los accesos que necesita el agente: Vaspian, la base de deudores (Lariat o Actos), la cuenta de Anthropic y la de AWS | **Por confirmar** |
| Volumen | Se empieza con 5 llamadas diarias. Si se cumplen los niveles 1 y 2, se sube a 50, después a 200 y luego al volumen normal (unas 800 diarias) | **Por confirmar** |
| Cuentas | Solo cuentas en estado NSF | **Por confirmar** |
| Revisión | Durante la primera semana se revisan todas las llamadas; después, una muestra. El nivel 1 se revisa siempre en todas | **Por confirmar** |
| Si algo falla | Si se encuentra un error de cumplimiento, el agente se detiene hasta corregirlo y volver a probarlo | **Por confirmar** |
| Decisión final | Reunión al terminar, con el reporte de los tres niveles. Si se cumplen, el agente pasa a producción | **Por confirmar** |

## 5. Reporte del piloto

Al final del piloto (y cada semana mientras dure) se entrega un reporte con:

- llamadas hechas y contestadas, y cuántas fueron entrantes y salientes;
- acuerdos logrados por cada 100 llamadas contestadas y el total de dinero acordado;
- transferencias a cobradores y sus motivos;
- disputas, pedidos de "no llamar" y devoluciones de llamada agendadas;
- fallas técnicas y tiempo de respuesta por turno;
- el resultado de la revisión de cumplimiento, con cada caso encontrado y cómo se corrigió.
