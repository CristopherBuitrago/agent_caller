from typing import Protocol


class SummarizationError(Exception):
    """El resumen no se pudo generar (red, API, rechazo del modelo). La llamada se cierra igual."""


class CallSummarizer(Protocol):
    """Interfaz. Implementación: infrastructure/services/claude_call_summarizer.py"""

    def summarize(self, transcript: str) -> str:
        """Resumen breve de la llamada, sin datos de verificación. Lanza SummarizationError si falla."""
        ...
