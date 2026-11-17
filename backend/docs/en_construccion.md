# En construcción: núcleo

Lo técnico que falta en este servicio. Lo que espera respuesta de la empresa está en el [`PENDIENTES.md` de la raíz](../../PENDIENTES.md).

| Qué | Estado | Depende de |
| --- | --- | --- |
| **Endpoint para el aviso de pago:** recibir el aviso del procesador, verificar que es auténtico y llamar a `RecordPaymentResult`. Además, un lector del reporte diario, por si el procesador no tiene *webhook* | Por hacer; se puede probar con avisos falsos | Formato real del procesador |
| **Activar la tarea de acuerdos rotos** (`PAYMENT_RESULTS_CONNECTED=true`) | Construida y apagada | El aviso de pago conectado |
| **Conexión con la base real:** reemplazar los repositorios PostgreSQL de datos simulados | Por hacer | Diagrama EER y acceso a Lariat (o Actos) |
| **Sincronización con el CRM:** traer las cuentas NSF y las llamadas de los cobradores (cuentan para la Reg F) y devolver los resultados de las llamadas | Por hacer; se puede empezar con una fuente falsa (CSV) | Lariat |
| **Saldo cuota por cuota:** hoy el saldo solo pasa a 0 al pagarse la última cuota | En espera | Duda 8: ¿lo actualiza este sistema o el CRM? |
| **Nombre del estado de cuenta pagada:** hoy es `PAID`, en la constante `ACCOUNT_STATUS_PAID` | Construido; falta confirmarlo | Duda 1 |
| **Detalles de la disputa:** fecha del pago, medio, número de confirmación | En pausa (B5) | Duda 6 |
| **Alerta de disputa al equipo y búsqueda del pago en la llamada** (N11) | En pausa | La base real |
| **Grabación real:** reemplazar `LoggingCallRecorder` | Por hacer | Vaspian |
| **Llamadas abiertas en memoria:** la API guarda las llamadas abiertas y el registro de ofertas en el proceso. Con más de un servidor habría que moverlos a una base compartida (por ejemplo, Redis o PostgreSQL) | Alcanza con un solo servidor | El volumen del piloto |
| **Reporte del piloto y reporte mensual:** llamadas, acuerdos por cada 100, transferencias y cumplimiento | Por hacer | — |
