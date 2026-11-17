# Agente de cobranza NSF: lo que necesitamos y preguntas para los proveedores

Actualizado: 2026-11-17. Live Oac Financial.

**Para qué sirve:** el agente ya tiene todas las reglas de cobranza construidas y probadas. Para pasar a llamadas reales hay que conectarlo con Vaspian, el procesador de pagos y Lariat Software. Si cada proveedor responde estas preguntas desde el principio, los accesos llegan completos y la conexión se hace en días, no en semanas.

**Estado:** **Pendiente** = falta el dato o el acceso · **Por confirmar** = hay una respuesta parcial.

## 1. Lo que necesitamos de la empresa

| # | Qué | Para qué | Estado |
| --- | --- | --- | --- |
| 1 | Cuenta de Anthropic de la empresa y su clave de API | Probar el agente con Claude Haiku 5.5 antes del piloto (las 7 simulaciones) | **Pendiente** |
| 2 | Cuentas de AssemblyAI y Deepgram a nombre de la empresa | La voz del agente: AssemblyAI entiende lo que dice el deudor y Deepgram habla. Se pagan por uso | **Pendiente** |
| 3 | Un contacto técnico en Vaspian, en el procesador de pagos y en Lariat, y permiso para hablar con ellos | Resolver las preguntas de las secciones 2, 3 y 4 sin intermediarios | **Pendiente** |
| 4 | Cuenta y región de AWS, con un usuario que tenga solo los permisos necesarios | Instalar el agente en los servidores de la empresa | **Pendiente** |
| 5 | Resultados actuales de los cobradores con cuentas NSF: acuerdos por cada 100 llamadas contestadas, porcentaje de acuerdos cumplidos y duración promedio de la llamada | Comparar el piloto contra los cobradores y decidir si pasa a producción | **Pendiente** |
| 6 | Número de la línea de entrada que atiende el agente (duda 4) | Dárselo a quien no logra verificarse | **Pendiente** |
| 7 | Respuestas a las dudas 1, 6 y 8 (ver *Lo que falta y no depende del desarrollo*) | Nombre exacto del estado `PAID`, manejo de las disputas y quién actualiza el saldo | **Por confirmar** |
| 8 | Revisión del abogado (L7) | Deudores vulnerables y reglas de los SMS de cobranza | **Pendiente** |

## 2. Vaspian: telefonía y SMS

Ya se sabe que Vaspian puede enviar el audio de la llamada en vivo al agente. Falta saber cómo:

- **Audio en vivo:** ¿lo entrega por WebSocket, por SIP o de otra forma? ¿En qué formato (por ejemplo, G.711 mu-law a 8 kHz)? ¿Cómo recibe de vuelta la voz del agente?
- **Llamadas entrantes:** ¿cómo se dirige una llamada al agente? ¿Envía el número de quien llama?
- **Llamadas salientes:** ¿el sistema puede iniciar una llamada por API? ¿Cómo avisa el resultado (contestó, ocupado, no contestó)? ¿Detecta buzones de voz? El agente nunca deja mensajes.
- **Transferencia a los cobradores:** ¿cómo se pasa una llamada del agente a la cola de los cobradores? ¿Se puede enviar con la llamada el motivo y la cuenta, para que el cobrador los vea al contestar?
- **Grabación:** ¿Vaspian graba las llamadas? ¿Se puede iniciar la grabación desde el sistema? ¿Dónde quedan las grabaciones y cómo se consultan?
- **SMS:** ¿tiene una API para enviar SMS? ¿Avisa si el mensaje se entregó? ¿Cómo maneja las respuestas "STOP" para darse de baja? ¿El número está registrado para SMS comerciales en EE. UU. (10DLC)?
- **Capacidad y costos:** ¿cuántas llamadas simultáneas permite el contrato? ¿Cuánto cuestan los minutos y los SMS adicionales del agente?
- **Pruebas:** ¿hay un ambiente o números de prueba? ¿Quién entrega la documentación técnica y las credenciales?

## 3. Procesador de pagos

- **Cuál es:** nombre del procesador y si es el mismo para tarjeta, ACH y cheque.
- **Link de pago:** ¿se puede crear un link para una cuota, con el monto fijo? ¿Vence? ¿Se le puede agregar una referencia nuestra (el id de la cuota) para saber qué cuota se pagó?
- **Aviso de pago:** ¿avisa en el momento cada pago aprobado o rechazado (*webhook*), o entrega un reporte diario? ¿Qué datos trae (referencia, monto, estado, fecha)? ¿Cómo se verifica que el aviso es auténtico? ¿Lo reintenta si nuestro sistema no responde?
- **Devoluciones:** un pago por ACH puede aprobarse y devolverse días después por falta de fondos. ¿Cómo avisa ese caso?
- **Pago con tarjeta en la llamada:** ¿ofrece un sistema certificado PCI donde el deudor teclea la tarjeta (IVR), o se conecta con Vaspian? La IA nunca debe escuchar ni guardar los datos de la tarjeta.
- **Pruebas y costos:** ¿hay un ambiente de prueba? ¿Cuánto cobra por transacción? ¿Quién entrega la documentación y las credenciales?

## 4. Lariat Software (CRM)

- **Cuál se conecta:** ¿el agente se conecta a Actos Software o a Lariat Software? ¿Cuándo termina la migración?
- **Forma de conexión:** ¿Lariat tiene una API, o se da acceso a su base de datos? ¿Hay documentación o un diagrama de la base (EER)?
- **Leer deudores:** nombre, teléfonos, fecha de nacimiento, últimos 4 dígitos del SSN, estado de EE. UU. y zona horaria.
- **Leer cuentas:** acreedor, saldo, monto y fecha del pago devuelto, estado, disputa y "no llamar".
- **Leer las llamadas de los cobradores:** se suman a las del agente para el límite de 7 llamadas en 7 días (Reg F).
- **Escribir:** resultado y resumen de cada llamada, acuerdos y cuotas, cambios de estado (`PTP`, `PAID`, `DISPUTE`, `NSF`), "no llamar" y disputas.
- **Actualización:** ¿los datos se leen en tiempo real o hay una copia diaria? ¿Quién actualiza el saldo cuando entra un pago (duda 8)?
- **Seguridad:** ¿cómo se accede (VPN, direcciones IP permitidas)? Se pide un usuario solo con los permisos necesarios, porque hay datos sensibles (SSN y fecha de nacimiento).
- **Pruebas:** ¿hay un ambiente de prueba con datos ficticios?

## 5. Anthropic, AssemblyAI y Deepgram

- **Límites de uso:** ¿cuántos pedidos por minuto permite la cuenta? Las cuentas nuevas empiezan con límites bajos que suben con el uso; hay que confirmarlo antes de pasar de 50 llamadas diarias.
- **Datos de los deudores:** ¿cuánto tiempo guarda cada proveedor el audio y el texto de las llamadas? ¿Hay una opción para que no se guarden y no se usen para entrenar modelos?
