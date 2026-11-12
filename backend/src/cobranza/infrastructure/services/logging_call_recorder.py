"""CallRecorder de desarrollo: no graba nada, solo deja constancia en el log.

Se reemplaza por el proveedor de telefonía cuando se conecte (la orden de empezar a grabar
de su API, sobre la llamada en curso).
"""

import logging

log = logging.getLogger(__name__)


class LoggingCallRecorder:
    def start(self, call_id: str) -> None:
        log.info("Grabación (simulada) iniciada para la llamada %s", call_id)
