"""Agente de voz por el navegador (WebRTC), para probar y hacer demos sin Vaspian.

Une: navegador → detección de voz (Silero) → voz a texto (AssemblyAI) → turno del usuario →
AgentSession (Haiku + backend) → texto a voz (Deepgram Aura-2) → navegador.
Cuando llegue Vaspian, solo cambia el transporte (el navegador por la llamada).

Uso (con la API del backend corriendo):
    python -m cobranza_agent.infrastructure.voice.bot          # abre http://localhost:7860

Necesita ANTHROPIC_API_KEY, ASSEMBLYAI_API_KEY, DEEPGRAM_API_KEY, BACKEND_URL y AGENT_API_KEY.
VOICE_DEMO_PHONE: el teléfono desde el que "llama" el deudor (por defecto, Jane Carter de los datos
simulados). DEEPGRAM_VOICE: la voz del agente. TURN_SILENCE_SECONDS: silencio que cierra el turno
(por defecto 1,5 s).
"""

import logging
import os

from pipecat.audio.vad.silero import SileroVADAnalyzer
from pipecat.pipeline.pipeline import Pipeline
from pipecat.pipeline.runner import PipelineRunner
from pipecat.pipeline.task import PipelineParams, PipelineTask
from pipecat.processors.audio.vad_processor import VADProcessor
from pipecat.runner.types import SmallWebRTCRunnerArguments
from pipecat.services.assemblyai.stt import AssemblyAISTTService
from pipecat.services.deepgram.tts import DeepgramTTSService
from pipecat.transports.base_transport import TransportParams
from pipecat.transports.smallwebrtc.transport import SmallWebRTCTransport
from pipecat.turns.user_start.min_words_user_turn_start_strategy import MinWordsUserTurnStartStrategy
from pipecat.turns.user_stop.speech_timeout_user_turn_stop_strategy import SpeechTimeoutUserTurnStopStrategy
from pipecat.turns.user_turn_processor import UserTurnProcessor
from pipecat.turns.user_turn_strategies import UserTurnStrategies

from cobranza_agent.application.call import CallDirection
from cobranza_agent.infrastructure.container import build_agent
from cobranza_agent.infrastructure.voice.agent_processor import AgentTurnProcessor

log = logging.getLogger(__name__)

DEFAULT_DEMO_PHONE = "+13055550001"      # Jane Carter (TEST-001) en los datos simulados
# VOICE_DEMO_PHONE=any: llama desde un número sin deudor; con DEMO_LOOKUP_BY_NAME=true en la API, el
# deudor se busca por el nombre que diga quien llama (demo con cualquier deudor de prueba).
ANY_DEBTOR_PHONE = "+10000000000"
DEFAULT_VOICE = "aura-2-helena-en"       # la voz por defecto de Pipecat; se elige en las pruebas
# Silencio que confirma que el deudor terminó de hablar. Prueba por celular (2026-11-19): con 0,2 s
# contestaba a pedazos mientras dictaba el SSN y con 3 s se sentía lento. Se cambia con TURN_SILENCE_SECONDS.
DEFAULT_TURN_SILENCE_SECONDS = 1.5
# Mientras el agente habla, hacen falta estas palabras para interrumpirlo ("um" o "yeah" no cortan).
WORDS_TO_INTERRUPT = 2


def turn_strategies() -> UserTurnStrategies:
    silence = float(os.environ.get("TURN_SILENCE_SECONDS", DEFAULT_TURN_SILENCE_SECONDS))
    return UserTurnStrategies(
        start=[MinWordsUserTurnStartStrategy(min_words=WORDS_TO_INTERRUPT)],
        stop=[SpeechTimeoutUserTurnStopStrategy(user_speech_timeout=silence)],
    )


def build_pipeline(transport, agent_processor: AgentTurnProcessor) -> Pipeline:
    stt = AssemblyAISTTService(api_key=os.environ["ASSEMBLYAI_API_KEY"])
    tts = DeepgramTTSService(api_key=os.environ["DEEPGRAM_API_KEY"],
                             settings=DeepgramTTSService.Settings(
                                 voice=os.environ.get("DEEPGRAM_VOICE", DEFAULT_VOICE)))
    return Pipeline([
        transport.input(),
        VADProcessor(vad_analyzer=SileroVADAnalyzer()),
        stt,
        UserTurnProcessor(user_turn_strategies=turn_strategies()),
        agent_processor,
        tts,
        transport.output(),
    ])


async def bot(runner_args: SmallWebRTCRunnerArguments):
    transport = SmallWebRTCTransport(
        runner_args.webrtc_connection,
        TransportParams(audio_in_enabled=True, audio_out_enabled=True),
    )
    agent = build_agent()
    phone = os.environ.get("VOICE_DEMO_PHONE") or DEFAULT_DEMO_PHONE
    if phone.lower() == "any":
        phone = ANY_DEBTOR_PHONE
    agent_processor = AgentTurnProcessor(lambda: agent.execute(CallDirection.INBOUND, phone))
    task = PipelineTask(build_pipeline(transport, agent_processor),
                        params=PipelineParams(enable_metrics=True))

    @transport.event_handler("on_client_disconnected")
    async def on_client_disconnected(_transport, _client):
        # El deudor colgó: la llamada se cierra en el backend (EndFrame/CancelFrame en el procesador).
        await task.cancel()

    await PipelineRunner(handle_sigint=False).run(task)


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")
    from pipecat.runner.run import main

    main()
