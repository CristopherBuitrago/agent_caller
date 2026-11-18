# Agente de voz de cobranza NSF: pendientes

Actualizado: 2026-11-17. Solo lo que falta. Lo hecho está en `CONTEXTO.md` y en el historial de git.

## Esperando a la empresa

Para mandárselo al jefe están `docs/para_el_jefe/pendientes_externos.md` y `docs/para_el_jefe/preguntas_proveedores.md`.

- [x] Las 7 simulaciones con Haiku 5.5 corridas el 2026-11-18 (`agente/docs/simulaciones/2026-11-18/informe.md`). Cumplió el nivel 1 salvo detalles; el error grave (datos inventados en la verificación) quedó corregido. Para producción, la cuenta de Anthropic tiene que ser de la empresa
- [x] Hallazgo 2 de las simulaciones: frases fijas antes de verificar y revisión automática en el script (2026-11-18). La opción C (un filtro que revise cada respuesta antes de decirla) queda para cuando esté la capa de voz
- [ ] Corregir los hallazgos 3 a 7 de las simulaciones (Hardship Questions en orden, dudas sobre quién contesta, cómo se paga, detalles menores) y volver a correrlas
- [ ] Cuentas de AssemblyAI y Deepgram
- [ ] Vaspian: documentación y credenciales:
  - audio en vivo (ya se sabe que lo envía);
  - llamadas salientes;
  - transferencia a los cobradores con el motivo;
  - API de SMS;
  - líneas simultáneas;
  - ambiente de prueba
- [ ] Procesador de pagos: cuál es, link de pago por cuota, aviso de pago (*webhook* o reporte diario), devoluciones de ACH y ambiente de prueba
- [ ] Proveedor del IVR PCI. Bloquea la Función 6: pagar con tarjeta en la llamada
- [ ] Lariat (o Actos): diagrama EER, forma de conexión (API o base), qué se lee y qué se escribe, y ambiente de prueba. Incluye si el resultado de la llamada es una fila nueva o actualiza un registro
- [ ] Cuenta y región de AWS
- [ ] Resultados actuales de los cobradores con cuentas NSF, para comparar el piloto
- [ ] Dudas del jefe (`docs/para_el_jefe/dudas_para_el_jefe.md`):
  - 1: nombre exacto del estado `PAID`;
  - 2: procesador;
  - 4: número de la línea de entrada;
  - 5: el resto de Vaspian;
  - 6: disputas (desbloquea B5);
  - 8: quién actualiza el saldo cuota por cuota
- [ ] Revisión legal: L7 (deudores vulnerables y SMS), fuente de la grabación obligatoria, y guion y avisos
- [ ] Confirmar el volumen: ¿800 llamadas diarias?
- [ ] ¿Las entrantes de deudores en NSF pasan directo al agente? El jefe lo iba a proponer al dueño

## Desarrollo que se puede hacer ya

En el orden propuesto el 2026-11-17. El detalle técnico de cada uno está en el `docs/en_construccion.md` de su servicio (`backend/`, `agente/` o `messaging/`):

- [ ] Capa de voz con Pipecat (AssemblyAI y Deepgram), probada con el micrófono. Necesita las claves
- [ ] Endpoint para recibir el aviso de pago en la API (llama a `RecordPaymentResult`) y lector de reporte diario, probados con avisos falsos. Al conectarlo, activar `break_overdue_arrangements` (`PAYMENT_RESULTS_CONNECTED=true`)
- [ ] Marcador de salientes: toma la lista diaria, respeta el horario y tiene un máximo de llamadas simultáneas (por ejemplo, 5 al inicio). Se prueba con una telefonía falsa
- [ ] Sincronización con el CRM: trae las cuentas NSF y las llamadas de los cobradores (cuentan para la Reg F) y devuelve los resultados. Primero con una fuente falsa (CSV)
- [ ] Reporte del piloto y reporte mensual: llamadas, acuerdos por cada 100, transferencias, fallas, latencia por turno y revisión de los avisos legales
- [ ] Prueba de carga: unas 20 llamadas simuladas al mismo tiempo, con otra IA haciendo de deudor
- [ ] Preparar la instalación: pruebas automáticas en GitHub, manejo de claves y logs
- [ ] Ajustes vistos con la API real:
  - decir los montos en palabras ("four hundred fifty dollars");
  - no decir "I'm calling from" en las entrantes
- [ ] Historial de la página web: no guardar la fecha de nacimiento en el texto antes de usar datos reales
- [ ] Criterios de éxito del piloto: documento listo (`docs/para_el_jefe/criterios_exito_piloto.md` y su PDF, 2026-11-18), pedido por el jefe como documento aparte. Falta acordar los valores con él

## En pausa

- [ ] B5: detalles de la disputa (fecha del pago, medio, número de confirmación). Espera la duda 6
- [ ] N11: alerta al equipo y búsqueda del pago durante la llamada. Espera la base real
