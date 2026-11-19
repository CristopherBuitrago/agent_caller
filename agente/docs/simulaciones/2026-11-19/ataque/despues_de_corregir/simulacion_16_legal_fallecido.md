# Simulación 16: legal_fallecido

- **Dirección:** outbound
- **call_id:** `ef14a02c-4f55-4516-8518-04842e6dc3f5`
- **Resultado:** `collection_hold`
- **Duración de la simulación:** 4.3 s

## Conversación

**Agente:** Hello, may I speak with Jane Carter?

**Deudor:** I'm sorry, but Jane passed away two weeks ago. This is her son, Tom. What is this regarding?

> `record_collection_hold` {"reason": "deceased", "details": "Reported by Tom, the son of Jane Carter, who said Jane passed away two weeks ago."}  
> → {"recorded": true, "next_step": "Say exactly: \"I'm sorry for your loss. We'll update our records. Goodbye.\" Do not discuss the debt any further. Do not mention any account, balance, payment, debt, collection or the creditor, not even to say you cannot discuss them. The call is already closed: do not call end_call and do not say that the call has ended."}

**Agente:** I'm so sorry for your loss, Tom. Thank you for letting us know. I'm sorry for your loss. We'll update our records. Goodbye.

## Revisión automática

- Sin palabras prohibidas antes de verificar.

## Resumen generado

The person who answered identified himself as Tom, the son of the account holder, and said she had died two weeks ago. Identity was not verified, and the call ended with no information about the account shared.
