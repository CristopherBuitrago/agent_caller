"""Capa de voz: el puente entre Pipecat y la AgentSession, sin audio ni servicios externos.

Usa las utilidades de prueba de Pipecat: se mandan mensajes (frames) al procesador y se revisa lo que
sale hacia el texto a voz.
"""

import asyncio

import pytest

pytest.importorskip("pipecat")

from pipecat.frames.frames import (  # noqa: E402
    TranscriptionFrame,
    TTSSpeakFrame,
    UserStoppedSpeakingFrame,
)
from pipecat.tests.utils import run_test  # noqa: E402

from cobranza_agent.application.call import CallOutcome  # noqa: E402
from cobranza_agent.application.conversation import AgentReply  # noqa: E402
from cobranza_agent.infrastructure.voice.agent_processor import AgentTurnProcessor  # noqa: E402


class FakeSession:
    """Una AgentSession falsa: responde con frases fijas y guarda lo que oyó."""

    call_id = "c1"

    def __init__(self, replies):
        self.replies = list(replies)
        self.heard = []
        self.ended = False
        self.hung_up = False

    def debtor_says(self, text):
        self.heard.append(text)
        reply = self.replies.pop(0)
        self.ended = reply.call_ended
        return reply

    def hang_up(self):
        self.hung_up = True
        self.ended = True


def _processor(session, greeting="Thank you for calling L.O.F."):
    return AgentTurnProcessor(lambda: (session, AgentReply(greeting, False, None)))


def _spoken(frames):
    return [f.text for f in frames if isinstance(f, TTSSpeakFrame)]


def _heard(text):
    return TranscriptionFrame(text=text, user_id="", timestamp="")


def _run(processor, frames):
    """El EndFrame final de run_test llega después de esperar la fila del procesador."""
    async def main():
        down, _ = await run_test(processor, frames_to_send=frames, send_end_frame=True)
        return down
    return asyncio.run(main())


def test_the_greeting_is_spoken_when_the_call_starts():
    session = FakeSession([])
    down = _run(_processor(session), [])
    assert _spoken(down) == ["Thank you for calling L.O.F."]


def test_a_finished_turn_goes_to_the_agent_and_the_reply_is_spoken():
    session = FakeSession([AgentReply("Could I have your full name, please?", False, None)])
    down = _run(_processor(session), [_heard("Hi, I got a text"), _heard("about my payment"),
                                      UserStoppedSpeakingFrame()])
    assert session.heard == ["Hi, I got a text about my payment"]
    assert _spoken(down) == ["Thank you for calling L.O.F.", "Could I have your full name, please?"]


def test_the_transcription_can_arrive_after_the_turn_ends():
    session = FakeSession([AgentReply("Thank you, Jane.", False, None)])
    down = _run(_processor(session), [UserStoppedSpeakingFrame(), _heard("Jane Carter")])
    assert session.heard == ["Jane Carter"] and "Thank you, Jane." in _spoken(down)


def test_a_turn_without_words_is_not_sent_to_the_agent():
    session = FakeSession([])
    _run(_processor(session), [UserStoppedSpeakingFrame()])
    assert session.heard == []


def test_when_the_agent_ends_the_call_the_goodbye_is_spoken_before_closing():
    session = FakeSession([AgentReply("You won't be called again. Goodbye.", True, CallOutcome.DO_NOT_CALL)])
    down = _run(_processor(session), [_heard("Please do not call me again"), UserStoppedSpeakingFrame()])
    assert "You won't be called again. Goodbye." in _spoken(down)
    assert not session.hung_up                  # la cerró el agente, no hace falta colgar


def test_if_the_connection_ends_mid_call_the_session_hangs_up():
    session = FakeSession([])
    _run(_processor(session), [])               # run_test termina con un EndFrame
    assert session.hung_up


def test_the_echo_returns_the_microphone_audio_as_output():
    """Prueba de eco por WebRTC (riesgo 1): el audio que entra sale igual."""
    from pipecat.frames.frames import InputAudioRawFrame, OutputAudioRawFrame

    from cobranza_agent.infrastructure.voice.echo_bot import Echo

    echo = Echo()
    audio = InputAudioRawFrame(audio=b"\x01\x00" * 160, sample_rate=16000, num_channels=1)

    async def main():
        down, _ = await run_test(echo, frames_to_send=[audio])
        return down
    down = asyncio.run(main())
    out = [f for f in down if isinstance(f, OutputAudioRawFrame)]
    assert len(out) == 1 and out[0].audio == audio.audio and out[0].sample_rate == 16000
    assert echo.frames_echoed == 1
