"""Capa de voz: el puente entre Pipecat y la AgentSession, sin audio ni servicios externos.

Usa las utilidades de prueba de Pipecat: se mandan mensajes (frames) al procesador y se revisa lo que
sale hacia el texto a voz.
"""

import asyncio
import time

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
from cobranza_agent.infrastructure.voice.agent_processor import (  # noqa: E402
    FILLERS,
    PATIENCE_FILLER,
    AgentTurnProcessor,
)


class FakeSession:
    """Una AgentSession falsa: responde con frases fijas y guarda lo que oyó."""

    call_id = "c1"

    def __init__(self, replies, thinking_seconds=0.0):
        self.replies = list(replies)
        self.thinking_seconds = thinking_seconds
        self.heard = []
        self.ended = False
        self.hung_up = False

    def debtor_says(self, text):
        self.heard.append(text)
        time.sleep(self.thinking_seconds)
        reply = self.replies.pop(0)
        self.ended = reply.call_ended
        return reply

    def hang_up(self):
        self.hung_up = True
        self.ended = True


def _processor(session, greeting="Thank you for calling L.O.F.", filler_after=10.0, patience_after=20.0):
    return AgentTurnProcessor(lambda: (session, AgentReply(greeting, False, None)),
                              filler_after=filler_after, patience_after=patience_after)


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


# --- relleno y turnos juntos (prueba por celular, 2026-11-19) ---------------------------------

def test_a_quick_answer_has_no_filler():
    session = FakeSession([AgentReply("Could I have your name?", False, None)], thinking_seconds=0.0)
    down = _run(_processor(session, filler_after=0.5), [_heard("Hi"), UserStoppedSpeakingFrame()])
    assert _spoken(down) == ["Thank you for calling L.O.F.", "Could I have your name?"]


def test_a_slow_answer_says_a_filler_first():
    session = FakeSession([AgentReply("Thank you, Mark. You're verified.", False, None)], thinking_seconds=0.3)
    down = _run(_processor(session, filler_after=0.05), [_heard("Mark Holloway, 5678"),
                                                         UserStoppedSpeakingFrame()])
    assert _spoken(down) == ["Thank you for calling L.O.F.", FILLERS[0], "Thank you, Mark. You're verified."]


def test_a_very_slow_answer_also_thanks_for_the_patience():
    session = FakeSession([AgentReply("Here is your balance.", False, None)], thinking_seconds=0.4)
    down = _run(_processor(session, filler_after=0.05, patience_after=0.2),
                [_heard("What do I owe?"), UserStoppedSpeakingFrame()])
    assert _spoken(down)[1:] == [FILLERS[0], PATIENCE_FILLER, "Here is your balance."]


def test_fillers_rotate():
    session = FakeSession([AgentReply("One.", False, None), AgentReply("Two.", False, None)],
                          thinking_seconds=0.2)
    processor = _processor(session, filler_after=0.02)
    down = _run(processor, [_heard("first"), UserStoppedSpeakingFrame()])
    assert FILLERS[0] in _spoken(down)
    assert processor._next_filler() == FILLERS[1]


def test_turns_that_end_before_the_agent_answers_are_joined():
    """El deudor termina dos turnos mientras el agente todavía piensa el saludo: va uno solo."""
    session = FakeSession([AgentReply("Thanks. And your date of birth?", False, None)])
    slow_greeting = AgentTurnProcessor(
        lambda: (time.sleep(0.5), (session, AgentReply("Hello.", False, None)))[1],
        filler_after=10.0, patience_after=20.0)
    down = _run(slow_greeting, [_heard("My Social Security is 5 7"), UserStoppedSpeakingFrame(),
                                _heard("8 9"), UserStoppedSpeakingFrame()])
    assert session.heard == ["My Social Security is 5 7 8 9"]
    assert _spoken(down) == ["Hello.", "Thanks. And your date of birth?"]


def test_turn_strategies_wait_for_silence_and_need_two_words_to_interrupt(monkeypatch):
    from pipecat.turns.user_start.min_words_user_turn_start_strategy import MinWordsUserTurnStartStrategy
    from pipecat.turns.user_stop.speech_timeout_user_turn_stop_strategy import SpeechTimeoutUserTurnStopStrategy

    from cobranza_agent.infrastructure.voice.bot import turn_strategies

    monkeypatch.setenv("TURN_SILENCE_SECONDS", "2.5")
    strategies = turn_strategies()
    (start,), (stop,) = strategies.start, strategies.stop
    assert isinstance(start, MinWordsUserTurnStartStrategy) and start._min_words == 2
    assert isinstance(stop, SpeechTimeoutUserTurnStopStrategy) and stop._user_speech_timeout == 2.5


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
