# En construcción: mensajería

Lo técnico que falta en este servicio. Lo que espera respuesta de la empresa está en el [`PENDIENTES.md` de la raíz](../../PENDIENTES.md).

| Qué | Estado | Depende de |
| --- | --- | --- |
| **Proveedor real de SMS:** un adaptador de `SmsSender` con la API de Vaspian | Por hacer | API de SMS, credenciales y registro 10DLC de Vaspian |
| **Link de pago real:** un adaptador de `PaymentLinkProvider` con la página de pago del procesador, con la referencia de la cuota para saber cuál se pagó | Por hacer | Procesador de pagos |
| **Confirmación de entrega:** guardar si el SMS llegó, si el proveedor lo informa | Por hacer | Vaspian |
| **Bajas ("STOP"):** guardar quién se dio de baja y no volver a enviarle | Por definir | El abogado (L7) y cómo lo informa Vaspian |
| **Horario por zona horaria:** enviar a cada deudor dentro de su horario permitido, no solo con la hora del este | Por hacer | — |
| **Logs:** no escribir el texto ni el teléfono en el log cuando haya proveedor real | Por hacer | Proveedor real |
| **Dejar de importar el núcleo** (ver `separacion.md`) | Por decidir | — |
