# Contexto del proyecto: agente de voz de cobranza NSF

Resumen de lo que se hizo entre el 2026-10-28 y el 2026-11-17, para que cualquier sesión nueva sepa de dónde viene cada decisión. El estado actual está en `README.md` y lo que falta, en `PENDIENTES.md`.

## Quiénes y para qué

- **Desarrollador:** dueño de este repositorio. Construye el agente para una empresa de cobranza de EE. UU.: Live Oac Financial, con C; antes de verificar al deudor se dice "L.O.F.".
- **Jefe:** la persona de la empresa con la que se consultan las reglas de negocio. Sus respuestas se anotan como "Jefe (fecha)". Tiene un abogado en EE. UU. para los temas legales.
- **Propuesta entregada (2026-11-16):** piloto por USD 500, una sola vez; producción por USD 2.000 al mes (auditoría, mantenimiento y reporte mensual); USD 1.000 por cada estado de cuenta nuevo. Los proveedores los paga la empresa directamente.
- **Herramientas de la empresa:** Vaspian (marcador, llamadas entrantes y SMS), Actos Software (CRM, en migración a Lariat Software) y AWS.

## Forma de trabajo (la pidió el desarrollador)

1. Una observación o decisión a la vez. Se explica en 2 o 3 líneas, se dan opciones con una recomendada y se espera la respuesta.
2. Las preguntas al desarrollador van en español. Lo que dice el agente va en inglés.
3. Si un cambio toca el modelo de datos, primero se presentan los campos.
4. Después de cada decisión:
   - se aplica el cambio, con pruebas, y se corren todas las pruebas;
   - se anota la decisión con fecha y origen en `README.md` (regla vigente) y en `PENDIENTES.md` (si deja algo abierto);
   - se regeneran los PDF que cambien.
5. Antes de cada commit y push se muestra el cambio y se espera el OK.
6. Las dudas nuevas para el jefe van en `docs/para_el_jefe/dudas_para_el_jefe.md`, diciendo de qué observación salieron.
7. Los documentos que lee el jefe no le atribuyen pedidos al "desarrollador".
8. Nunca se le piden credenciales al desarrollador. El push usa las credenciales guardadas; si el proxy da error 407, se reintenta.

**Entorno local (Windows):** se usa Podman en lugar de Docker.
- Los contenedores corren con `--pids-limit=0`.
- La base es el contenedor `cobranza-db`, en la red `cobranza-net`. Si las pruebas se quedan colgadas, la base está apagada.
- Los PDF se generan en el contenedor `pdfgen` (reportlab), con `docs/` montado en `/docs`.

## Cronología

| Fecha | Qué pasó |
| --- | --- |
| 2026-10-28 | **Decisiones iniciales del desarrollador:** pago con tarjeta por un IVR PCI con teclado; verificación con nombre, últimos 4 del SSN y fecha de nacimiento; aviso de grabación; negociar sin presionar; inglés; datos simulados en PostgreSQL detrás de interfaces; arquitectura hexagonal; **jamás descuentos** |
| 2026-10-29 | **Respuestas del jefe:** solo se cobra NSF y cualquier otro estado pasa a una persona; varias deudas por deudor; *Skip Tracing* después de `fourth_attempt`; parcial con fecha para el resto; mínimo del 10%; Hardship Questions. **Del desarrollador:** plan de máximo 1 año, campo `verification_attempts`, bloqueo con 5 fallos en 24 h y deletrear el apellido |
| 2026-11-01 | Grabación obligatoria ("por ley se tiene que grabar"). Resumen con IA: Haiku, con Sonnet de respaldo |
| 2026-11-02 | **Negociación:** primero todo, luego 2 y 3 cuotas, "siempre por lo más rápido"; cuotas iguales que el deudor acepta y no propone; cuotas mensuales en fecha fija (jefe); primer pago en máximo 8 días; resto del parcial a 30 días; la cuenta pasa a `PTP` (`RCC` queda fuera); menos del 10%, con piso del 5%, solo como último recurso |
| 2026-11-04 | El jefe entrega las 5 Hardship Questions (texto original más abajo) |
| 2026-11-08 | Solo NSF confirmado; traducción de las Hardship Questions aprobada; descartadas frases como "venda su carro" o "pida dinero prestado" por verse como presión; resumen en inglés; el IVR PCI queda como bloqueante; lo no confirmado pasa a supuestos vigentes |
| 2026-11-10 | Chat de prueba con Claude (el sistema elige la oferta y la IA solo la presenta). Documento del backend (v3) entregado al jefe. Primera estimación de proveedores (Telnyx y Deepgram) |
| 2026-11-11 | 7 simulaciones con Claude Opus haciendo de agente con las herramientas reales, más una simulación del jefe (la 8). Informe con las observaciones E, S, N, B, P y L. El jefe dice que serían unas 800 llamadas diarias, no 2.000, y que la empresa ya tiene una campaña de SMS |
| 2026-11-12 | Se corrigen E1, E2, S1 y S2. Separación en 3 módulos. SMS de confirmación y link de pago (N1). Lista diaria de salientes. Decisiones de N2 a N14, L2, L3 y P3 |
| 2026-11-13 | Se aplican N7 a N14, todas las B (B5 queda en pausa) y el lote de instrucciones del agente (P). El jefe confirma N2 |
| 2026-11-15 | **Proveedores aprobados:** AssemblyAI, Deepgram Aura-2, Pipecat y Vaspian (Telnyx sale). Clave de Anthropic con USD 5 de créditos, probada con la API real. Página web de chat con historial. `wrong_party` y `debtor_unavailable` quedan solo para salientes sin verificar. Documento de pendientes externos |
| 2026-11-16 | Propuesta en español e inglés (PDF y Word). El agente y la mensajería pasan a carpetas propias. Las herramientas del agente se publican por HTTP con `X-API-Key` |
| 2026-11-17 | Prueba de contrato entre el agente y el backend. **Respuestas del jefe:** Vaspian envía el audio en vivo; el único código de rebote es `NSF`; la cuenta pagada pasa a `PAID`; todavía no hay número de la línea de entrada. Duda 8 (saldo cuota por cuota). PDF de preguntas para los proveedores. Criterios de éxito del piloto propuestos (sin acordar). Limpieza de los documentos ya entregados |

## Códigos de las observaciones (2026-11-11)

El código y los documentos todavía mencionan estos códigos.

| Código | Tema | Cómo quedó |
| --- | --- | --- |
| E1 | Al colgar, un pedido de "no llamar" o una disputa se podían perder | Corregido |
| E2 | Guardar las Hardship Questions de a una borraba las anteriores | Corregido |
| S1 | Quien llama cambia de nombre entre intentos de verificación | Resultado `identity_mismatch` |
| S2 | Se pedía deletrear el apellido aunque fallara otro dato | Solo si lo único que falla es el apellido |
| N1 | Cómo paga el deudor un pago agendado | SMS con link de pago (proveedor de prueba) |
| N2 | Verificar leyendo los datos al deudor | Se deja como está (jefe) |
| N3 | Saludo y aviso de grabación en salientes | Aviso cuando confirma que es el deudor |
| N4 | Se ofrecían opciones ya descartadas | Se saltan, salvo la de 3 cuotas y la última (A') |
| N5 | Lo que podía pagar no alcanzaba para 10 cuotas | Oferta del 10% más 12 cuotas |
| N6 | Parcial con un resto imposible | El resto se reparte en cuotas |
| N7 | Acuerdo aceptado con duda | Se pregunta cuánto puede pagar y se pide otra oferta |
| N8 | Primer pago siempre hoy | Si pide tiempo, fin de mes, y las cuotas a fin de cada mes |
| N9 | Nadie volvía a llamar | La lista diaria y `schedule_callback` |
| N10 | Qué pasa después de `PTP` | SMS de aviso; acuerdo `broken` a los 5 días y la cuenta a `NSF`; `PAID` al pagar todo |
| N11 | Revisión de disputas | Estado `DISPUTE`; el resto en pausa |
| N12 | Quien no logra verificarse | Se le da el número de la línea de entrada (falta el número) |
| N13 | "No llamar" y quejas | Solo con pedido explícito; `get_last_contact` |
| N14 | Angustia y amenazas | Calma, y nunca colgar ni transferir por eso |
| N15 | Telefonía y CRM | Vaspian y Actos/Lariat |
| B1 | Continuidad entre llamadas | Las Hardship Questions valen 30 días |
| B2 | Hora para volver a llamar | `calls.callback_at` |
| B3 y B4 | Resultado y motivo de la transferencia | `calls.transfer_reason` y `debtor_unavailable` |
| B5 | Disputas sin detalles | **En pausa** (duda 6) |
| B6 | Motivo del rebote | Solo `NSF`, dicho como un hecho |
| B7 | Fecha límite del primer pago | La da la herramienta |
| B8 | Intentos de verificación restantes | `attempts_left` |
| B9 | `next_step` incompletos | Corregidos |
| B10 | Link de pago | Con N1 |
| B11 | Grabar después del "sí" | Con N3 |
| B12 | Resumen de llamadas delicadas | Sin verificar, no menciona la deuda |
| B13 | Un impostor puede bloquear a la deudora | Sin cambios |
| B14 | `recommended_plan` | Lo llena el sistema |
| B15 | Propuesta rechazada | No se reacepta; se arma otra igual |
| P1–P12 | Frases e instrucciones del agente | Aplicadas el 2026-11-13. P2 se resolvió con L2 y P11 con B8 y N12 |
| L1 | Volver a llamar a quien pidió no ser llamado | Solo cuenta el pedido explícito |
| L2 | Consentimiento de grabación | Solo se informa, sin preguntar |
| L3 | Qué se le dice a un tercero | "L.O.F." y frases fijas |
| L4 | Límite de 7 en 7 días | Cuentan todas las llamadas: las del agente y las de los cobradores |
| L5 | Disputas | Con N11 (en pausa) |
| L6 | Aviso "debt collector" | Se deja como está |
| L7 | Deudores vulnerables y SMS | **Pendiente** con el abogado |

## Decisiones que cambiaron o se descartaron

- **Frecuencia de las cuotas:** primero quincenal; el jefe la cambió a mensual.
- **Primer pago:** primero en máximo 7 días, luego 8, y desde N8 hasta fin de mes.
- **Recordatorios después de `PTP`:** primero los hacía un cobrador; desde N10 son SMS.
- **"La normativa exige al menos el 20%":** se descartó. Afirmar una regla que no existe es una práctica engañosa (FDCPA 1692e). La opción A' de N4 logra el mismo efecto diciendo la verdad.
- **Respuesta a "¿eres un robot?":** se pidió una que no confirmara ni negara. No se construyó: la TCPA y leyes de California y Utah exigen decir que es una IA si se pregunta.
- **Códigos de rebote:** primero R01 y R09 (códigos ACH); el jefe aclaró que solo existe `NSF`.
- **Volumen:** 2.000 llamadas diarias pasaron a unas 800 (sin confirmar).
- **Proveedores:** Telnyx (telefonía e IVR) y Deepgram Nova-3 (voz a texto) se cambiaron por Vaspian y AssemblyAI. AWS sale del costo porque la empresa ya lo tiene.

## Hardship Questions (texto original del jefe, 2026-11-04)

1. «¿Puede contarme un poco qué fue lo que pasó y cuándo empezó esta situación?»
2. «¿Es algo que espera que sea temporal o un cambio a largo plazo en sus ingresos?»
3. «¿Hay alguien más en el hogar que pueda colaborar mientras se estabiliza?»
4. «Entiendo que la situación está difícil, pero ¿hay alguna cantidad parcial que pueda aportar hoy o en su próxima fecha de pago?»
5. «¿Qué acuerdo realista podemos fijar para los próximos 30 o 60 días que le permita cumplir sin ahogarse?»

## Documentos borrados el 2026-11-17

Ya se entregaron o ya se resolvieron. Están en el historial de git; para recuperarlos, `git show 3818a67:<ruta>`:

- `docs/simulacion_2…7_2026-11-11.md` y `docs/notas_simulacion_2026-11-11.md`: las simulaciones.
- `docs/Informe_Simulaciones_Agente_Cobranza_NSF.pdf` y `docs/generar_informe_simulaciones.py`: el informe con las observaciones.
- `docs/respuestas_observaciones.md`, su PDF y su generador: las respuestas a las observaciones. Sus funciones de PDF pasaron a `docs/scripts/pdf_desde_md.py`.
- `docs/Backend_Agente_Cobranza_NSF_v3.pdf`: el documento del backend entregado el 2026-11-10.
- `docs/diagrama_eer_modelo_actual.jpg`: el diagrama de nuestra base, ya desactualizado. La fuente real es `backend/db/init/001_schema.sql`.
- La versión larga de `README.md` y de `PENDIENTES.md`, con cada respuesta textual del jefe y del desarrollador.

## Orden de `docs/` (2026-11-17)

`docs/` se ordenó por tema: `para_el_jefe/` (lo que espera respuesta), `propuesta/` (lo entregado al cliente) y `scripts/` (cómo se generan los PDF y los Word). Los dos generadores casi iguales se unieron en `scripts/generar_pdf.py`, que deja cada PDF al lado de su `.md`. Los archivos pasaron a nombres cortos en minúsculas (por ejemplo, `Propuesta_Agente_Cobranza_NSF_ES.pdf` → `propuesta/propuesta_es.pdf`). El detalle está en `docs/README.md`.
