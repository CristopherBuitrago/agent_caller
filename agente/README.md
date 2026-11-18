# Agente de cobranza NSF (`cobranza_agent`)

Servicio que conversa con el deudor usando Claude. Arma el prompt, manda cada turno al modelo y ejecuta en el backend las herramientas que el modelo pide. Hoy funciona por texto: un chat en la terminal y una página web. La voz se conectará con Pipecat.

## Qué hace y qué no hace

**Hace:**
- **Arma el prompt** del agente (`application/prompts/agent_system_prompt.md`) con el nombre de la empresa, el aviso FDCPA, las Hardship Questions y la lista de herramientas que entrega el backend.
- **Lleva la conversación de cada llamada:** recibe lo que dice el deudor, se lo pasa a Claude y ejecuta las herramientas que Claude pide (hasta 8 por turno). Devuelve lo que el agente debe decir.
- **Usa un modelo de respaldo y transfiere si todo falla:** si Haiku falla o rechaza, responde Sonnet. Si los dos fallan, la llamada se cierra como transferida a una persona, con el motivo.
- **Avisa al backend de la conversación:** le manda la transcripción para el resumen y le avisa si el deudor colgó.
- **Ofrece un chat de prueba** en la terminal y una página web de demo, con historial de llamadas.

**No hace:**
- **No decide montos, fechas, reglas ni resultados:** todo se lo pide al backend por HTTP. Si el modelo intenta algo que las reglas no permiten, el backend responde con un error y un `next_step`.
- **No toca la base de datos** y no importa el núcleo (`cobranza`).
- **No maneja audio todavía:** voz a texto, texto a voz y telefonía irán en la capa de voz.

El comportamiento esperado del agente (saludo, verificación, negociación, disputas) está en el [README de la raíz](../README.md#reglas-de-negocio-vigentes).

## Dónde encaja

```
  deudor ──texto──► chat_cli / web.py ──► AgentSession ──► Claude (Haiku; Sonnet de respaldo)
  (más adelante: voz por Pipecat)              │
                                               └── herramientas (HTTP + X-API-Key) ──► API del backend (:8001)
```

## Stack tecnológico

| Qué | Tecnología |
| --- | --- |
| Lenguaje | Python 3.12 o superior |
| Modelo | SDK de Anthropic: Claude Haiku 5.5 (`effort: low`, con caché del prompt) y Claude Sonnet 5.5 de respaldo |
| Cliente HTTP del backend | httpx |
| Página web de demo | FastAPI y Uvicorn, con HTML estático (`infrastructure/static/`) |
| Voz (opcional, grupo `voz`) | Pipecat 1.16.0: detección de voz Silero, AssemblyAI (voz a texto), Deepgram Aura-2 (texto a voz) y WebRTC para el navegador |
| Pruebas | pytest. Las pruebas de punta a punta levantan en memoria la API del backend, con su base |

## Arquitectura

Es hexagonal. La lógica de la conversación (`application/`) no sabe de Claude ni de HTTP: los usa a través de dos puertos.

```
src/cobranza_agent/
├── application/
│   ├── conversation.py         AgentSession (una por llamada), StartAgentConversation y el armado del prompt
│   ├── conversation_model.py   puerto ConversationModel: turnos, llamadas a herramientas y resultados
│   ├── call_backend.py         puerto CallBackend: abrir la llamada, catálogo de herramientas, ejecutarlas
│   ├── call.py                 copia de CallDirection y CallOutcome del backend (llegan por HTTP como texto)
│   └── prompts/agent_system_prompt.md   instrucciones del agente, en inglés
└── infrastructure/
    ├── claude_conversation_model.py   adaptador de ConversationModel con la API de Anthropic
    ├── http_call_backend.py           adaptador de CallBackend con la API del backend
    ├── container.py                   arma el agente; nombre de la empresa y siglas por defecto
    ├── voice/                         capa de voz: agent_processor.py (puente Pipecat ↔ AgentSession) y bot.py (WebRTC)
    ├── chat_cli.py                    chat de prueba en la terminal
    ├── web.py y static/               página web de demo e historial
    └── call_log.py                    historial: un JSON por llamada
```

**Reglas de dependencia** (las revisa `tests/unit/test_architecture.py`):
- `application` no importa `infrastructure` ni librerías externas (anthropic, httpx, fastapi...).
- El agente no importa el núcleo (`cobranza`) ni conoce a la mensajería.
- `test_backend_contract.py` revisa que la copia de `CallDirection` y `CallOutcome` tenga los mismos valores que el backend.

**Puertos y adaptadores**

| Puerto | Adaptador de hoy | Adaptador por conectar |
| --- | --- | --- |
| `ConversationModel` | `ClaudeConversationModel` (Haiku y, si falla, Sonnet) | Igual |
| `CallBackend` | `HttpCallBackend`, contra la API del backend | Igual |
| Entrada y salida con el deudor | `chat_cli.py` y `web.py` (texto) | Pipecat: telefonía de Vaspian, voz a texto con AssemblyAI y texto a voz con Deepgram |

**Una llamada, paso a paso:**
1. Se abre la llamada en el backend.
2. Se pide el catálogo de herramientas y se arma el prompt.
3. En cada turno, el texto del deudor va a Claude. Si Claude pide herramientas, se ejecutan en el backend y sus resultados vuelven a Claude, hasta que responde con texto.
4. Se guarda la transcripción en el backend.
5. La llamada termina cuando una herramienta la cierra, cuando el deudor cuelga o por un fallo (en ese caso se transfiere).

## Qué expone y qué consume

**Comandos**

| Comando | Para qué |
| --- | --- |
| `python -m cobranza_agent.infrastructure.chat_cli --entrante +13055550001` | Chat de prueba: el deudor llama desde ese teléfono |
| `python -m cobranza_agent.infrastructure.chat_cli --saliente ACC-T001` | Chat de prueba: el agente llama por esa cuenta |

Opciones del chat:
- `--sin-herramientas` oculta las herramientas;
- `--debug` muestra los avisos internos;
- `--empresa` y `--siglas` cambian el nombre de la empresa (por defecto "Live Oac Financial" y "L.O.F.");
- `/colgar` termina la llamada.

**Página web de demo** (`uvicorn cobranza_agent.infrastructure.web:app`, puerto 8000)

| Ruta | Para qué |
| --- | --- |
| `GET /` | Chat, con 5 casos de prueba y los datos para verificarse a la vista |
| `GET /historial` | Historial de llamadas |
| `POST /api/calls` | Abre una llamada |
| `POST /api/calls/{id}/messages` | Envía lo que dice el deudor y devuelve la respuesta del agente |
| `POST /api/calls/{id}/hangup` | El deudor cuelga |
| `GET /api/history` y `GET /api/history/{id}` | Lista de llamadas guardadas y el detalle de una |

**Consume:**
- **La API del backend:** todos los endpoints `/api/agent/...` (ver el [README del backend](../backend/README.md#qué-expone-y-qué-consume)).
- **La API de Anthropic.**

## Configuración

| Variable | Obligatoria | Por defecto | Para qué |
| --- | --- | --- | --- |
| `ANTHROPIC_API_KEY` | Sí | — | Credencial de Claude |
| `BACKEND_URL` | No | `http://localhost:8001` | Dónde está la API del backend |
| `AGENT_API_KEY` | Sí | vacía | La misma clave que espera el backend en `X-API-Key` |
| `CALL_LOG_DIR` | No | `call_logs` | Carpeta del historial de la página web (no se sube al repositorio) |
| `ASSEMBLYAI_API_KEY` y `DEEPGRAM_API_KEY` | Solo para la voz | — | Voz a texto y texto a voz |
| `DEEPGRAM_VOICE` | No | `aura-2-helena-en` | La voz del agente |
| `VOICE_DEMO_PHONE` | No | `+13055550001` | Desde qué teléfono "llama" el deudor en la demo de voz |

## Correr y probar en local

Todo se corre desde la raíz del repositorio, con el `docker-compose.yml` compartido. La API del backend arranca sola.

| Para qué | Comando |
| --- | --- |
| Chat de prueba | `docker compose run --rm agente python -m cobranza_agent.infrastructure.chat_cli --entrante +13055550001` |
| Página web | `docker compose up web` → http://localhost:8000. Desde el celular: la IP del PC en la misma red, puerto 8000 |
| Voz en el navegador (en construcción) | `docker compose up voz` → http://localhost:7860, permitir el micrófono. Necesita las claves de AssemblyAI y Deepgram |
| Pruebas | `docker compose run --rm --build agente` |

**Pruebas (77):**
- **Unitarias:** la conversación con un modelo guionado (sin llamar a Claude), el cliente HTTP, la página web, el historial, la arquitectura y el contrato con el backend.
- **De integración** (`tests/integration/test_agent_chat_postgres.py`): llamadas completas que pasan por la API real del backend, en memoria, y por PostgreSQL.

Para verificarse en el chat como TEST-001: Jane Carter, SSN 1234, nacida el 14 de marzo de 1985.

## Más documentación

- **[`docs/seguridad.md`](docs/seguridad.md):** qué datos ve el modelo y qué guarda el historial.
- **[`docs/en_construccion.md`](docs/en_construccion.md):** capa de voz y pendientes de este servicio.
- **[`docs/separacion.md`](docs/separacion.md):** qué lo ata a este repositorio y cómo separarlo.
- **[`docs/simulaciones/`](docs/simulaciones/):** simulaciones con Claude (informe y transcripciones). Se corren con `python scripts/simular.py --salida docs/simulaciones/AAAA-MM-DD`.
