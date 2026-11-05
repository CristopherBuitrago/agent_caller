from datetime import datetime
from typing import Protocol


class Clock(Protocol):
    """Interfaz. Implementación: infrastructure/services/system_clock.py"""

    def now(self) -> datetime: ...
