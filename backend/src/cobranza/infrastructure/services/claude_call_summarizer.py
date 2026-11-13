"""Implementación de CallSummarizer con Claude (API de Anthropic)."""

import anthropic

from cobranza.application.interfaces.call_summarizer import SummarizationError

PRIMARY_MODEL = "claude-haiku-5-5"   # barato: ~USD 0,00055 por resumen
BACKUP_MODEL = "claude-sonnet-5-5"   # solo si el principal rechaza o falla

SYSTEM_PROMPT = """You write the record of a debt-collection phone call for the collections team.

Summarize the transcript in 2 to 4 sentences of plain English: whether the right person was reached \
and verified, what the debtor said about the debt, any payment or arrangement agreed (amounts and \
dates exactly as stated), and any follow-up the team needs to do. If the call ended early (recording \
refused, wrong party, failed verification), say so and why.

Never include Social Security numbers, dates of birth, card numbers, or any other data used to \
verify identity, even if they appear in the transcript. Report only what the transcript shows; \
do not guess.

If <identity_verified> is false, write one or two sentences saying only who answered and how the \
call ended. Do not mention any debt, creditor, amount, or reason for the call.

If the caller threatened or insulted the agent, say so in one sentence without repeating their \
words."""


class ClaudeCallSummarizer:
    def __init__(self, client: anthropic.Anthropic, model: str = PRIMARY_MODEL):
        self._client = client
        self._model = model

    def summarize(self, transcript: str, identity_verified: bool = True) -> str:
        try:
            response = self._client.messages.create(
                model=self._model,
                max_tokens=2000,
                output_config={"effort": "low"},  # resumir es una tarea simple
                system=SYSTEM_PROMPT,
                messages=[{"role": "user", "content":
                           f"<identity_verified>{str(identity_verified).lower()}</identity_verified>\n"
                           f"<transcript>\n{transcript}\n</transcript>"}],
            )
        except anthropic.APIError as e:
            raise SummarizationError(f"Error de la API de Claude ({self._model}): {e}") from e

        if response.stop_reason == "refusal":
            raise SummarizationError(f"{self._model} rechazó resumir la transcripción")
        text = "".join(block.text for block in response.content if block.type == "text").strip()
        if not text:
            raise SummarizationError(f"Respuesta vacía de {self._model}")
        return text
