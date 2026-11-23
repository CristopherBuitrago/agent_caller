# Pruebas de voz del padrastro: 2026-11-22

Pruebas por celular en la red local, con el modo demo (cualquier deudor de prueba, `DEMO_LOOKUP_BY_NAME=true`, `VOICE_DEMO_PHONE=any`). Versión probada: verificación con los últimos 4 del SSN, después la fecha de nacimiento y después "Am I speaking with [nombre]?"; 3 intentos; nombres sin letras dobles (Ana/Anna); el agente se llama Lucy.

Antes de esta versión hubo otras pruebas el mismo día (Ana Reyes con "Anna", Jane Carter sin modo demo, y un acuerdo de Jane Carter de USD 250 + 235). No están aquí; sus hallazgos ya se corrigieron.

**Para analizar mañana, caso por caso.** Las horas son UTC (restar 5 para Colombia). Cada línea con _herramienta_ es una llamada de Lucy al backend; _(turno)_ es lo que tardó en responder sin contar el texto a voz.

## Resumen

| # | Hora | Deudor | Resultado | Qué revisar |
| --- | --- | --- | --- | --- |
| 1 | 23:06 | Lucy Bennett | Llamada agendada (miércoles 10:00) | Duda: ¿agendar o primero ofrecer un pago tentativo cuando el deudor debe revisar con su banco? (en PENDIENTES) |
| 2 | 23:08 | Ana Reyes | Acuerdo: USD 175 el jueves 26 | Salió bien. El acuerdo quedó en la base de pruebas (se limpia antes del commit) |
| 3 | 23:15 | Sin verificar | Nadie habló | Corte de conexión; volvió a llamar al minuto |
| 4 | 23:16 | Sin verificar | Cerrada como "no quiere ser grabado" | **Error de Lucy, corregido:** tomó "What the hell is this?" como rechazo de la grabación y dijo "I made an error and the system closed this call". Ahora la negativa solo se guarda si la repite después de "May we continue?" |
| 5 | 23:22 | Mark Holloway | Llamada agendada (viernes 9:00) | Duda: la regla N8 no dejó poner el primer pago el 1 de diciembre (en PENDIENTES) |

## Llamada 1: Lucy Bennett (23:06)

    _herramienta: record_recording_consent_
    23:06:08.104 **Lucy:** Hello, I'm Lucy from L.O.F. This call may be recorded for quality and compliance purposes. How can I help you today?
    23:06:19.097 **Deudor:** Hello, Lucy, how you doing today?
    _(turno: 0.93 s)_
    23:06:21.377 **Lucy:** I'm doing well, thank you for asking. To protect your privacy, could you please give me the last four digits of your Social Security number?
    23:06:38.600 **Deudor:** Yeah, my last, uh, for my Social Security are 4321.
    _(turno: 0.91 s)_
    23:06:40.806 **Lucy:** And your date of birth?
    23:06:46.762 **Deudor:** My date of birth is July 21st,
    23:06:48.774 **Deudor:** 1992.
    _herramienta: verify_identity_
    23:06:51.395 **Lucy:** Let me check our records, please.
    _(turno: 1.45 s)_
    23:06:52.542 **Lucy:** Thank you. Am I speaking with Lucy Bennett?
    23:06:58.351 **Deudor:** Yeah, that's me.
    _herramienta: confirm_identity_
    23:07:00.954 **Lucy:** One moment, please.
    _herramienta: get_account_details_
    _(turno: 2.25 s)_
    23:07:01.957 **Lucy:** Thank you, Lucy. This is Live Oac Financial. This is an attempt to collect a debt, and any information obtained will be used for that purpose. This communication is from a debt collector. Lucy, a payment of $120.00 to Pinecrest Wireless, ending in 3008, was returned by your bank on October 5th, 2026, because there were not enough funds on your card. The current balance is $145.00. Would you like to take care of it today?
    23:07:36.059 **Deudor:** Oh my God, are you sure about that?
    _(turno: 1.01 s)_
    23:07:38.434 **Lucy:** I understand this is surprising. The bank returned the payment on October 5th because there were not enough funds on the card. Would you like to take care of it today?
    23:07:50.509 **Deudor:** Well, um,
    23:07:52.937 **Deudor:** you know, I'm really surprised.
    23:07:54.288 **Deudor:** So, um,
    23:07:58.751 **Deudor:** okay, so what I can do is I'm going to double-check with my bank
    23:08:04.084 **Deudor:** and you could call me please on this coming Wednesday and
    23:08:07.278 **Deudor:** you know, if I, if I
    23:08:10.606 **Deudor:** can get enough funds that I could pay it
    23:08:13.815 **Deudor:** the full amount this coming Wednesday. Okay.
    23:08:16.455 **Lucy:** Okay...
    _(turno: 1.65 s)_
    23:08:17.072 **Lucy:** I can call you back on Wednesday, November 25th. What time works best for you?
    23:08:24.595 **Deudor:** In the morning,
    23:08:27.236 **Lucy:** Let me check our records, please.
    _herramienta: schedule_callback_
    _(turno: 3.52 s)_
    23:08:29.502 **Lucy:** We'll call back on Wednesday, November 25, 2026 at 10:00 AM. Thank you, Lucy, and have a good day.
    23:08:39.100 **Deudor:** Thank you. Thank you for calling.
    23:08:39.736 **Deudor:** Bye.
    

## Llamada 2: Ana Reyes (23:08)

    _herramienta: record_recording_consent_
    23:08:59.219 **Lucy:** Hello, I'm Lucy from L.O.F. This call may be recorded for quality and compliance purposes. How can I help you today?
    23:09:10.719 **Deudor:** Hey Lucy, uh, what is LOF?
    _(turno: 1.04 s)_
    23:09:13.099 **Lucy:** I'm happy to help. I can share more once I confirm I'm speaking with the right person. To protect your privacy, could you please give me the last four digits of your Social Security number?
    23:09:29.700 **Deudor:** Well, the thing is I got a message from you guys, but I don't know what LOF is, so I
    23:09:32.024 **Deudor:** you know, I want to know what
    23:09:33.661 **Deudor:** is this about.
    _(turno: 0.94 s)_
    23:09:35.967 **Lucy:** I can share the reason once I confirm I'm speaking with the right person. To protect your privacy, could you please give me the last four digits of your Social Security number?
    23:09:47.508 **Deudor:** Yes, sure.
    23:09:50.055 **Deudor:** They are 4444.
    _(turno: 0.96 s)_
    23:09:52.422 **Lucy:** And your date of birth?
    23:09:57.740 **Deudor:** December 12th, 1998.
    23:09:59.684 **Deudor:** Sorry, 1990.
    _herramienta: verify_identity_
    23:10:02.323 **Lucy:** Let me check our records, please.
    _(turno: 1.48 s)_
    23:10:03.414 **Lucy:** Thank you. Am I speaking with Ana Reyes?
    23:10:08.280 **Deudor:** Yeah.
    _herramienta: confirm_identity_
    23:10:10.921 **Lucy:** One moment, please.
    _herramienta: get_account_details_
    _(turno: 2.28 s)_
    23:10:11.949 **Lucy:** Thank you, Ana. This is Live Oac Financial. This is an attempt to collect a debt, and any information obtained will be used for that purpose. This communication is from a debt collector. Ana, a recent payment of $150.00 to Pinecrest Wireless, ending in 2201, was returned by the bank because there were not enough funds in your account. The current balance is $175.00. Would you like to take care of it today?
    23:10:42.534 **Deudor:** Oh wow.
    23:10:44.841 **Deudor:** I'm really surprised about that. So
    23:10:47.074 **Deudor:** I tell you what,
    23:10:50.841 **Deudor:** I can pay for that and it's next Thursday.
    23:10:53.418 **Lucy:** Okay...
    _(turno: 1.89 s)_
    23:10:54.061 **Lucy:** Just to confirm, do you mean Thursday, November 26th?
    23:10:59.292 **Deudor:** Yeah, that's right.
    _herramienta: propose_offer_
    23:11:01.896 **Lucy:** Let me check our records, please.
    _(turno: 1.72 s)_
    23:11:02.967 **Lucy:** Here's the option: one payment of $175.00, the full balance, on Thursday, November 26, 2026. You'll get a text with a secure link to pay on that date. Would you like to set that up?
    23:11:19.141 **Deudor:** Yeah, sounds good.
    _herramienta: record_offer_response_
    23:11:21.753 **Lucy:** One moment, please.
    _herramienta: end_call_
    _(turno: 3.70 s)_
    23:11:24.201 **Lucy:** Thank you, Ana. Your arrangement is set: one payment of $175.00 on Thursday, November 26, 2026. You'll get a text message confirming the amounts and dates. For each payment that is at least three days away, you'll get a reminder text three days before, and on each payment date a text with a secure link to pay online. Nobody will call you to take the payment over the phone. Have a good day, Ana.
    23:11:52.830 **Deudor:** Uh, thank you, YouTube. Bye-bye.
    

## Llamadas 3 y 4: sin verificar (23:15 y 23:16)

La de las 23:15 se conectó y nadie habló; la de las 23:16 es la del error de la grabación.

    _herramienta: record_recording_consent_
    23:15:41.536 **Lucy:** Hello, I'm Lucy from L.O.F. This call may be recorded for quality and compliance purposes. How can I help you today?
    23:16:44.968 **Lucy:** Hello, I'm Lucy from L.O.F. This call may be recorded for quality and compliance purposes. How can I help you today?
    23:17:00.711 **Deudor:** Well, Lucy, I keep on getting some messages from you guys and I don't understand why because I don't
    23:17:02.943 **Deudor:** have any debts. So
    23:17:05.681 **Deudor:** what is, what is this about? What the hell is this?
    23:17:08.287 **Lucy:** Let me check our records, please.
    _herramienta: record_recording_consent_
    _herramienta: end_call_
    _(turno: 3.90 s)_
    23:17:10.933 **Lucy:** I'm sorry, I made an error and the system closed this call before we could finish. You can call us back, and I'll be glad to help you then. Have a good day.
    
    _herramienta: end_call_
    

## Llamada 5: Mark Holloway (23:22)

    _herramienta: record_recording_consent_
    23:22:06.844 **Lucy:** Hello, I'm Lucy from L.O.F. This call may be recorded for quality and compliance purposes. How can I help you today?
    23:22:21.028 **Deudor:** Hey Lucy, listen, I've been receiving many, many messages from you guys
    23:22:22.981 **Deudor:** LOF. I don't know
    23:22:25.799 **Deudor:** who is LOF or what is LOF.
    23:22:30.541 **Deudor:** And I don't understand why you keep on sending me messages. Why don't you stop that?
    _(turno: 0.94 s)_
    23:22:32.788 **Lucy:** I'm sorry for the frustration. Before I can discuss anything, I need to verify your identity. Could you please give me the last four digits of your Social Security number?
    23:22:48.858 **Deudor:** Okay, but why don't you first tell me what LOF is, what LOF means,
    23:22:50.813 **Deudor:** you know, what, what do you need?
    _(turno: 0.93 s)_
    23:22:52.815 **Lucy:** I can share the reason once I confirm I'm speaking with the right person. Could you please give me the last four digits of your Social Security number?
    23:23:03.276 **Deudor:** Okay, okay.
    23:23:04.351 **Deudor:** Um,
    23:23:04.819 **Deudor:** um,
    23:23:10.951 **Deudor:** okay, I'm going to do that even though, you know, I, I don't like the— I don't like the fact that
    23:23:12.604 **Deudor:** I don't
    23:23:14.890 **Deudor:** know what this is about, but
    23:23:18.875 **Deudor:** my Social Security number is 5678.
    _(turno: 1.00 s)_
    23:23:21.093 **Lucy:** Thank you. And your date of birth?
    23:23:26.313 **Deudor:** Oh, you also need my date of birth.
    23:23:27.451 **Deudor:** Really?
    _(turno: 0.94 s)_
    23:23:29.692 **Lucy:** Yes, I need your date of birth to complete verification. Could you please tell me your date of birth?
    23:23:40.362 **Deudor:** Okay, it is November 2nd, 1979.
    _herramienta: verify_identity_
    23:23:42.924 **Lucy:** Let me check our records, please.
    _(turno: 1.47 s)_
    23:23:43.985 **Lucy:** Thank you. Am I speaking with Mark Holloway?
    23:23:49.979 **Deudor:** Yeah, that's me.
    _herramienta: confirm_identity_
    23:23:52.441 **Lucy:** One moment, please.
    _herramienta: get_account_details_
    _(turno: 2.51 s)_
    23:23:53.699 **Lucy:** Thank you, Mark. This is Live Oac Financial. This is an attempt to collect a debt, and any information obtained will be used for that purpose. This communication is from a debt collector. Mark, two payments were returned by your bank because there were not enough funds in your account. The first is a $920.00 payment to Summit Health Partners, ending in 7734, with a current balance of $955.00. The second is a $180.00 payment to Brightwater Utilities, ending in 1190, with a balance of $205.00. I'll start with the Summit Health Partners balance, and then we can look at Brightwater Utilities. Would you like to take care of the Summit Health Partners balance today?
    23:24:44.352 **Deudor:** Oh wow, that's a lot of money.
    23:24:46.032 **Deudor:** Uh, well,
    23:24:51.862 **Deudor:** today I don't think I can because I don't have funds right now in the bank.
    23:24:53.703 **Deudor:** So I'm gonna have to
    23:24:59.603 **Deudor:** tell you, you know, that if you can call me like next Friday, that will be good.
    23:25:02.104 **Lucy:** Okay...
    _(turno: 1.70 s)_
    23:25:02.622 **Lucy:** I understand. If it helps, we can set your first payment for when you'll have the money. When would that be?
    23:25:15.343 **Deudor:** Yeah, well, I need to check with my bank, but
    23:25:20.156 **Deudor:** like I said, you can call me, you can call me next week, like at the end of the week, like Friday.
    23:25:27.741 **Deudor:** And I think then following Monday, I believe is like what, like December 1st.
    23:25:30.045 **Deudor:** Probably I could pay.
    23:25:32.606 **Lucy:** Let me check our records, please.
    _herramienta: propose_offer_
    _(turno: 3.00 s)_
    23:25:34.352 **Lucy:** I'm sorry, December 1st isn't available for the first payment. The latest date I can set is Monday, November 30, 2026. Would that work for you?
    23:25:48.481 **Deudor:** No, it has to be the first week of December.
    23:25:51.005 **Lucy:** One moment, please.
    _(turno: 2.28 s)_
    23:25:52.039 **Lucy:** I'm sorry, I can't set the first payment for December. The latest I can set is Monday, November 30. I can call you back this Friday, as you asked, though. What time would work for you?
    23:26:04.430 **Deudor:** In the morning.
    23:26:07.742 **Deudor:** But like I said, in November I cannot pay. So
    23:26:11.341 **Deudor:** if you cannot set the payment for December, then don't call me.
    23:26:13.925 **Lucy:** Okay...
    _(turno: 1.82 s)_
    23:26:14.493 **Lucy:** Just to be sure I understand: would you like me to schedule a call for Friday morning, or do you want us to stop calling you altogether?
    23:26:30.639 **Deudor:** Well, like I said, I am able to pay, but I cannot pay in November. I can pay only
    23:26:31.820 **Deudor:** until December.
    23:26:34.425 **Lucy:** Let me check our records, please.
    _herramienta: schedule_callback_
    _(turno: 4.15 s)_
    23:26:37.323 **Lucy:** We'll call back on Friday, November 27, 2026 at 9:00 AM. Thank you, Mark, and have a good day.
    23:26:45.526 **Deudor:** Right.
    
