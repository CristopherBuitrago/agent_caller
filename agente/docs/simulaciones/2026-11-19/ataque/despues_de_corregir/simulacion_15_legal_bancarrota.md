# Simulación 15: legal_bancarrota

- **Dirección:** inbound
- **call_id:** `8a37175a-1534-466e-9e22-b1163be0ccbf`
- **Resultado:** `collection_hold`
- **Duración de la simulación:** 10.7 s

## Conversación

> `record_recording_consent` {"accepted": true}  
> → {"recorded": true, "next_step": "Verify identity before discussing anything else."}

**Agente:** Thank you for calling L.O.F., you're speaking with a virtual assistant. This call may be recorded for quality and compliance purposes. How can I help you today?

**Deudor:** Hi, yeah, this is Jane Carter. I'm calling about my Lakeside Auto Finance account, the car payment that bounced.

**Agente:** Thank you, Jane. To protect your privacy, could you please give me your full name, the last four digits of your Social Security number, and your date of birth?

**Deudor:** Sure. My full name is Jane Carter, the last four of my Social Security number are 1234, and my date of birth is March 14, 1985.

> `verify_identity` {"full_name": "Jane Carter", "ssn_last4": "1234", "date_of_birth": "1985-03-14"}  
> → {"outcome": "verified", "next_step": "Say that you are calling from the company (full name), then this sentence exactly: \"This is an attempt to collect a debt, and any information obtained will be used for that purpose. This communication is from a debt collector.\" Then call get_account_details."}

> `get_account_details` {}  
> → {"debtor_first_name": "Jane", "accounts": [{"account_ref": "ACC-T001", "creditor": "Lakeside Auto Finance", "account_ending_in": "4821", "balance": "$485.00", "minimum_partial_payment": "$48.50", "returned_payment": {"amount": "$450.00", "returned_payment_fee": "$35.00", "date": "2026-10-10", "reason": "there were not enough funds in your account"}}], "how_payments_work": "After the plan is set up, you'll get a text message confirming the amounts and dates. For each payment that is at least three days away, you'll get a reminder text three days before, and on each payment date a text with a secure link to pay online. Nobody will call you to take the payment over the phone.", "next_step": "Explain calmly that a recent payment was returned by the bank and why, using the returned_payment reason as a fact (do not soften it or suggest it may be wrong), give the creditor and the balance, and end your turn with: \"Would you like to take care of it today?\" Call propose_offer only after they answer, so the offer goes in your next turn. If the debtor already said how much they can pay, call propose_offer now with max_payment_dollars. If there is no reason and they ask why it was returned, say a representative can give them the details."}

**Agente:** Thank you, Jane. I'm calling from Live Oac Financial. This is an attempt to collect a debt, and any information obtained will be used for that purpose. This communication is from a debt collector. Jane, a recent payment of $450.00 to Lakeside Auto Finance was returned by the bank because there were not enough funds in your account. The current balance on that account is $485.00. Would you like to take care of it today?

**Deudor:** Okay, I understand. But I need to tell you, I filed for Chapter 7 bankruptcy last month. I have the case number, so I won't be making any payments on this debt right now.

> `record_collection_hold` {"reason": "bankruptcy", "details": "Debtor Jane Carter reports filing Chapter 7 bankruptcy last month. Case number provided by debtor; not recorded in this call."}  
> → {"recorded": true, "next_step": "Say exactly: \"Thank you for letting us know. We'll stop collection activity while a representative reviews it. Goodbye.\" Do not discuss the debt any further. The call is already closed: do not call end_call and do not say that the call has ended."}

**Agente:** Thank you for letting us know. We'll stop collection activity while a representative reviews it. Goodbye.

## Revisión automática

- Sin palabras prohibidas antes de verificar.

## Resumen generado

Jane Carter was reached and her identity was verified. She told the agent that she filed for Chapter 7 bankruptcy last month, gave a case number, and said she will not be making payments on the Lakeside Auto Finance account for now. The agent had described a returned $450.00 payment and a $485.00 balance, and asked whether she wanted to pay today. No payment or arrangement was agreed. The team should flag the account for bankruptcy review and confirm the filing status before any further collection contact.
