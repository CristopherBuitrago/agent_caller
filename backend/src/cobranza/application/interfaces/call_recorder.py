from typing import Protocol


class CallRecorder(Protocol):
    """Le pide a la telefonía que empiece a grabar la llamada (N3, 2026-11-12).

    La grabación empieza recién cuando el deudor acepta el aviso: antes, quien contesta (que puede
    ser un tercero) no queda grabado. La hace el proveedor de telefonía; cuando termina la llamada,
    el proveedor avisa dónde quedó el audio y se guarda en calls.recording_uri.

    Implementación: hoy infrastructure/services/logging_call_recorder.py (de desarrollo); después,
    el proveedor de telefonía.
    """

    def start(self, call_id: str) -> None: ...
