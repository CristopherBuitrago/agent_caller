"""Chat de prueba en la terminal: una persona escribe como si fuera el deudor y Claude responde
como el agente, con las mismas reglas (las del backend, por su API) que tendrá la llamada de voz.

Uso (desde la raíz; levanta también la base y la API del backend):
    docker compose run --rm agente python -m cobranza_agent.infrastructure.chat_cli --entrante +13055550001
    docker compose run --rm agente python -m cobranza_agent.infrastructure.chat_cli --saliente ACC-T001

Comandos durante el chat: /colgar (el deudor cuelga) y /salir.
Necesita ANTHROPIC_API_KEY, BACKEND_URL y AGENT_API_KEY.
"""

import argparse
import json
import logging
import os
import sys
import textwrap

from cobranza_agent.application.call import CallDirection
from cobranza_agent.application.conversation_model import ToolCall, ToolResult
from cobranza_agent.infrastructure.container import DEFAULT_COMPANY_NAME, DEFAULT_COMPANY_SHORT, build_agent

GREY, CYAN, YELLOW, RESET = "\033[90m", "\033[36m", "\033[33m", "\033[0m"


def _print_agent(text: str) -> None:
    if text:
        print(f"\n{CYAN}Agente:{RESET} " + textwrap.fill(text, 100, subsequent_indent="        "))


def _show_tool(call: ToolCall, result: ToolResult) -> None:
    """Muestra qué pidió la IA y qué respondió el backend (para ver que las reglas las aplica el sistema)."""
    args = json.dumps(call.input, ensure_ascii=False)
    try:
        answer = json.loads(result.content)
        answer.pop("next_step", None)
        answer = json.dumps(answer, ensure_ascii=False)
    except ValueError:
        answer = result.content
    mark = "✗" if result.is_error else "→"
    print(f"{GREY}  [herramienta] {call.name} {args}\n  {mark} {answer}{RESET}")


def main() -> int:
    parser = argparse.ArgumentParser(description="Chat de prueba del agente de cobranza NSF")
    who = parser.add_mutually_exclusive_group(required=True)
    who.add_argument("--entrante", metavar="TELEFONO", help="Llamada entrante desde este teléfono")
    who.add_argument("--saliente", metavar="CUENTA", help="Llamada saliente por esta cuenta del job")
    parser.add_argument("--sin-herramientas", action="store_true",
                        help="No mostrar las herramientas que pide el agente")
    parser.add_argument("--empresa", default=DEFAULT_COMPANY_NAME, help="Nombre completo (solo tras verificar)")
    parser.add_argument("--siglas", default=DEFAULT_COMPANY_SHORT, help="Lo que se dice antes de verificar")
    parser.add_argument("--debug", action="store_true",
                        help="Mostrar los avisos internos (fallos de la API, respaldo con Sonnet)")
    args = parser.parse_args()
    logging.basicConfig(level=logging.WARNING if args.debug else logging.ERROR,
                        format="%(levelname)s %(name)s: %(message)s")

    if not os.environ.get("ANTHROPIC_API_KEY"):
        print("Falta ANTHROPIC_API_KEY.", file=sys.stderr)
        return 2

    agent = build_agent(company_name=args.empresa, company_short=args.siglas)
    on_tool = None if args.sin_herramientas else _show_tool
    if args.entrante:
        session, reply = agent.execute(CallDirection.INBOUND, args.entrante, on_tool=on_tool)
    else:
        try:
            session, reply = agent.execute(CallDirection.OUTBOUND, None, args.saliente,
                                           on_tool=on_tool)
        except LookupError:
            print(f"No existe la cuenta {args.saliente}.", file=sys.stderr)
            return 2

    print(f"{GREY}Llamada {session.call_id}. Escribe como el deudor; /colgar o /salir para terminar.{RESET}")
    _print_agent(reply.text)
    while not session.ended:
        try:
            text = input(f"\n{YELLOW}Deudor:{RESET} ").strip()
        except (EOFError, KeyboardInterrupt):
            text = "/colgar"
        if not text:
            continue
        if text in ("/colgar", "/salir"):
            session.hang_up()
            break
        _print_agent(session.debtor_says(text).text)

    outcome = session.outcome
    print(f"\n{GREY}Llamada terminada. Resultado: {outcome.value if outcome else 'sin resultado'}")
    if session.summary:
        print("Resumen: " + textwrap.fill(session.summary, 100, subsequent_indent="         "))
    print(RESET, end="")
    return 0


if __name__ == "__main__":
    sys.exit(main())
