from typing import Protocol


class SummarizationError(Exception):
    """El resumen no se pudo generar (red, API, rechazo del modelo). La llamada se cierra igual."""


class CallSummarizer(Protocol):
    """Interfaz. Implementación: infrastructure/services/claude_call_summarizer.py"""

    def summarize(self, transcript: str, identity_verified: bool = True) -> str:
        """Resumen breve de la llamada, sin datos de verificación. Lanza SummarizationError si falla.

        B12: sin identidad verificada, el resumen solo dice quién contestó y cómo terminó.
        """
        ...
