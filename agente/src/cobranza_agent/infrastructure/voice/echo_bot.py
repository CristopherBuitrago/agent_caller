"""Prueba de eco por WebRTC: lo que entra por el micrófono vuelve por el parlante, sin IA.

Sirve para cerrar el riesgo 1 de la capa de voz sin claves de AssemblyAI ni Deepgram: comprueba que
el audio (UDP) de WebRTC llega del navegador al contenedor y vuelve. Si se oye el eco, el transporte
funciona; si el navegador conecta pero no se oye nada, el audio no sale del contenedor.

Uso:
    python -m cobranza_agent.infrastructure.voice.echo_bot --host 0.0.0.0 --port 7860
Abrir http://localhost:7860, permitir el micrófono y hablar. Usar audífonos: con parlantes el eco
se realimenta.
"""

import logging

from pipecat.frames.frames import Frame, InputAudioRawFrame, OutputAudioRawFrame
from pipecat.pipeline.pipeline import Pipeline
from pipecat.pipeline.runner import PipelineRunner
from pipecat.pipeline.task import PipelineTask
from pipecat.processors.frame_processor import FrameDirection, FrameProcessor
from pipecat.runner.types import SmallWebRTCRunnerArguments
from pipecat.transports.base_transport import TransportParams
from pipecat.transports.smallwebrtc.transport import SmallWebRTCTransport

log = logging.getLogger(__name__)


class Echo(FrameProcessor):
    """Devuelve el audio del micrófono como audio de salida y cuenta cuánto pasó."""

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.frames_echoed = 0

    async def process_frame(self, frame: Frame, direction: FrameDirection):
        await super().process_frame(frame, direction)
        if isinstance(frame, InputAudioRawFrame):
            self.frames_echoed += 1
            if self.frames_echoed in (1, 100) or self.frames_echoed % 1000 == 0:
                log.info("Eco: %d pedazos de audio recibidos y devueltos", self.frames_echoed)
            await self.push_frame(OutputAudioRawFrame(audio=frame.audio, sample_rate=frame.sample_rate,
                                                      num_channels=frame.num_channels))
        else:
            await self.push_frame(frame, direction)


async def bot(runner_args: SmallWebRTCRunnerArguments):
    transport = SmallWebRTCTransport(
        runner_args.webrtc_connection,
        TransportParams(audio_in_enabled=True, audio_out_enabled=True),
    )
    echo = Echo()
    task = PipelineTask(Pipeline([transport.input(), echo, transport.output()]))

    @transport.event_handler("on_client_connected")
    async def on_client_connected(_transport, _client):
        log.info("Navegador conectado: hable y debería oírse a sí mismo")

    @transport.event_handler("on_client_disconnected")
    async def on_client_disconnected(_transport, _client):
        log.info("Navegador desconectado. Pedazos de audio devueltos: %d", echo.frames_echoed)
        await task.cancel()

    await PipelineRunner(handle_sigint=False).run(task)


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")
    from pipecat.runner.run import main

    main()
