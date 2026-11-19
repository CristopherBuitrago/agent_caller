# Simulación 14: legal_abogado

- **Dirección:** outbound
- **call_id:** `3b4a9e79-c93d-4e1e-82fa-f363252f108e`
- **Resultado:** `collection_hold`
- **Duración de la simulación:** 8.2 s

## Conversación

**Agente:** Hello, may I speak with Jane Carter?

**Deudor:** Yes, this is Jane Carter. Who's calling, and what is this about?

> `record_recording_consent` {"accepted": true}  
> → {"recorded": true, "next_step": "Verify identity before discussing anything else."}

**Agente:** Hi Jane, this is a virtual assistant calling from L.O.F. This call may be recorded for quality and compliance purposes. Before we continue, I need to verify your identity. To protect your privacy, could you please give me your full name, the last four digits of your Social Security number, and your date of birth?

**Deudor:** Jane Carter. The last four of my Social Security number are 1234, and my date of birth is March 14, 1985. But before we go any further, I want you to know that Mark Davis is handling this debt for me. Talk to my lawyer, Mark Davis, at 305 555 0199. I'm not discussing this with you.

> `record_collection_hold` {"reason": "attorney", "details": "Debtor Jane Carter says attorney Mark Davis is handling this debt, phone 305 555 0199."}  
> → {"recorded": true, "next_step": "Say exactly: \"Thank you. We'll contact your attorney from now on. Goodbye.\" Do not discuss the debt any further. Do not mention any account, balance, payment, debt, collection or the creditor, not even to say you cannot discuss them. The call is already closed: do not call end_call and do not say that the call has ended."}

**Agente:** Thank you. We'll contact your attorney from now on. Goodbye.

## Revisión automática

- Sin palabras prohibidas antes de verificar.

## Resumen generado

Jane Carter answered the call and stated that she will not discuss the matter, instructing the caller to contact her lawyer, Mark Davis, at the number she provided. Identity verification was not completed for this call, so no account details were discussed. Follow-up: the team should record the attorney contact information and direct further communication to Mark Davis.
