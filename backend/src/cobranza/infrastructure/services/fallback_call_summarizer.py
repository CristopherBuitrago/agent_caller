"""Respaldo propio: si el resumidor principal rechaza o falla, se usa el de respaldo.

Funciona con cualquier par de resumidores (cualquier proveedor), porque ambos
cumplen la interfaz CallSummarizer.
"""

import logging

from cobranza.application.interfaces.call_summarizer import CallSummarizer, SummarizationError

log = logging.getLogger(__name__)


class FallbackCallSummarizer:
    def __init__(self, primary: CallSummarizer, backup: CallSummarizer):
        self._primary = primary
        self._backup = backup

    def summarize(self, transcript: str, identity_verified: bool = True) -> str:
        try:
            return self._primary.summarize(transcript, identity_verified)
        except SummarizationError:
            log.warning("Falló el resumidor principal; se usa el de respaldo", exc_info=True)
            # Si el respaldo también falla, su SummarizationError sube y EndCall cierra sin resumen.
            return self._backup.summarize(transcript, identity_verified)
