# Seguridad del agente

## Qué datos ve el modelo (Claude)

- **Lo que dice el deudor, palabra por palabra.** Eso incluye su fecha de nacimiento y los últimos 4 del SSN cuando se verifica. El agente se los pasa al backend con `verify_identity`, pero no los guarda.
- **Lo que devuelven las herramientas del backend.** Antes de verificar, solo datos que no revelan la deuda. Después de verificar, el acreedor, el saldo, las ofertas y las fechas. El backend nunca le manda la fecha de nacimiento ni el SSN guardados.
- **Lo que nunca ve:** datos de tarjeta. El pago con tarjeta irá por un IVR PCI externo.

Las instrucciones del prompt prohíben repetir el SSN o la fecha de nacimiento, pedir datos de tarjeta y hablar de la deuda con alguien que no sea el deudor verificado. Las reglas que importan no dependen del prompt: las aplica el backend.

## Qué guarda este servicio

- **El historial de la página web:** un JSON por llamada en `CALL_LOG_DIR`, con la conversación completa, las herramientas y lo que respondió el sistema.
  - Los últimos 4 del SSN se enmascaran (`****`).
  - **La fecha de nacimiento queda en el texto,** porque en texto libre no se detecta con seguridad. Por eso el historial es solo para pruebas con datos simulados.
- **Las llamadas abiertas:** viven en la memoria del proceso; al terminar no queda nada en él.

## Claves

- **`ANTHROPIC_API_KEY`** y **`AGENT_API_KEY`:** se leen del entorno. En local van en `.env`, que no se sube al repositorio. En AWS irían en un gestor de secretos.
- **La conexión con el backend:** usa HTTP en local. En AWS debe ir por HTTPS (lo pone el balanceador) o por una red privada.

## Proveedores de IA y datos de los deudores

Hay que confirmar cuánto tiempo guarda Anthropic los pedidos y si se pueden excluir del entrenamiento. Lo mismo, cuando se conecten, con AssemblyAI y Deepgram (está en `docs/para_el_jefe/preguntas_proveedores.md`, sección 5).

## Falta antes de usar datos reales

- **Historial:** no guardar la fecha de nacimiento ni el SSN en el texto. Por ejemplo, reemplazar en la transcripción lo que el deudor dijo justo antes de `verify_identity`. Otra opción: guardar solo lo que llega al backend, sin el texto del deudor en ese turno.
- **Grabaciones de voz:** definir dónde se guardan y por cuánto tiempo (lo maneja Vaspian).
- **Página web:** es solo para la demo, no tiene usuarios ni contraseña. No debe publicarse.
