# Seguridad del núcleo

## Datos sensibles que maneja

| Dato | Dónde está | Cómo se protege |
| --- | --- | --- |
| Fecha de nacimiento y últimos 4 del SSN | `debtors.dob_hmac` y `debtors.ssn_last4_hmac` | Solo se guarda su HMAC-SHA256 con `PII_HMAC_KEY`. No se pueden leer en claro: la verificación calcula el HMAC de lo que dice el deudor y lo compara con lo guardado. Nunca se le pasan a la IA ni salen por la API |
| Nombre, teléfonos, estado, saldo | `debtors` y `accounts` | En claro. La API solo los muestra después de verificar la identidad, y solo los del dueño de la cuenta |
| Resumen y transcripción de la llamada | `calls.summary` y `calls.transcript_uri` | Si la persona no se verificó, el resumen no menciona la deuda (B12). La transcripción es un archivo aparte (ver el historial del agente) |
| Datos de tarjeta | En ningún lado | El pago con tarjeta irá por un IVR PCI externo; ni la IA ni el sistema ven el número |

## Claves

- **`PII_HMAC_KEY`:** si se pierde o se cambia, ningún deudor puede verificarse, porque los HMAC guardados dejan de coincidir. Debe vivir en un gestor de secretos (por ejemplo, AWS Secrets Manager), nunca en el repositorio. La clave de desarrollo `dev-only-pii-key` del compose solo sirve con datos simulados.
- **`AGENT_API_KEY`:** se compara en tiempo constante (`hmac.compare_digest`). Si está vacía, toda llamada a la API responde 401. Hay que rotarla si se filtra.
- **`ANTHROPIC_API_KEY`:** la lee el SDK de Anthropic desde el entorno.

## API

- Todos los endpoints exigen `X-API-Key`. Solo hablan programas (el agente o la plataforma de voz), no personas. Si algún día hay un panel con usuarios, se usaría JWT.
- La API no maneja HTTPS por sí misma: en AWS lo pone el balanceador. Nunca debe quedar expuesta en HTTP sin cifrar.
- Las herramientas exigen el orden correcto: sin consentimiento de grabación no hay acuerdo, y sin identidad verificada no se habla de la deuda.

## Reglas de cumplimiento que aplica el código

- **Reg F:** máximo 7 llamadas en 7 días, y nada de llamadas en los 7 días siguientes a una conversación (lista diaria). Las horas pedidas para volver a llamar tienen que caer entre 8 a. m. y 9 p. m., hora del deudor.
- **Disputas y "no llamar":** impiden cobrar.
- **Bloqueo de verificación:** 5 fallos en 24 horas.

## Falta antes de usar datos reales

- Mover las claves a un gestor de secretos y definir cómo se rotan.
- Revisar qué escriben los logs. Hoy pueden incluir ids de llamada y de cuenta, no datos sensibles; hay que confirmarlo con logs reales.
- Definir con la empresa cuánto tiempo se guardan las llamadas, los resúmenes y las grabaciones.
- Conectar con la base real usando un usuario con los permisos mínimos y acceso por red privada o VPN.
- Revisión legal de los avisos y del guion (L7 y revisión general).
