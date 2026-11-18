"""Puente entre Pipecat y la conversación del agente (AgentSession).

Pipecat maneja el audio: detecta cuándo habla la persona, pasa la voz a texto y el texto a voz.
La conversación es la misma AgentSession del chat y de las simulaciones: este procesador junta lo que
dijo el deudor en su turno, se lo pasa al agente y manda la respuesta al texto a voz.

Mensajes de Pipecat que usa:
- StartFrame: abre la llamada en el backend y dice el saludo.
- TranscriptionFrame: lo que dijo el deudor (puede llegar en varios pedazos).
- UserStoppedSpeakingFrame: el deudor terminó su turno. La transcripción puede llegar antes o después;
  el turno se contesta cuando están las dos cosas.
- EndFrame / CancelFrame: la llamada terminó o se cortó la conexión.

Abrir la llamada, cada turno y colgar van a una fila y se hacen en el orden en que llegan: la
conversación es una sola y el backend no admite dos turnos a la vez.
"""

import asyncio
import logging
import time
from collections.abc import Awaitable, Callable

from pipecat.frames.frames import (
    CancelFrame,
    EndFrame,
    Frame,
    StartFrame,
    TranscriptionFrame,
    TTSSpeakFrame,
    UserStoppedSpeakingFrame,
)
from pipecat.processors.frame_processor import FrameDirection, FrameProcessor

from cobranza_agent.application.conversation import AgentReply, AgentSession

log = logging.getLogger(__name__)

StartCall = Callable[[], tuple[AgentSession, AgentReply]]
Job = Callable[[], Awaitable[None]]

# Al terminar el turno, se esperan pedazos de transcripción que lleguen un poco tarde. Es parte de la
# demora de cada turno: se mide en el piloto (meta: 1,5 s o menos por turno).
TRANSCRIPT_GRACE_SECONDS = 0.25


class AgentTurnProcessor(FrameProcessor):
    def __init__(self, start_call: StartCall, on_turn_latency: Callable[[float], None] | None = None,
                 **kwargs):
        super().__init__(**kwargs)
        self._start_call = start_call
        self._on_turn_latency = on_turn_latency
        self._session: AgentSession | None = None
        self._heard: list[str] = []
        self._turn_finished = False
        self._turn_finished_at = 0.0
        self._jobs: asyncio.Queue[tuple[Job, asyncio.Future]] | None = None
        self._worker: asyncio.Task | None = None
        self._grace: asyncio.Task | None = None

    @property
    def session(self) -> AgentSession | None:
        return self._session

    async def process_frame(self, frame: Frame, direction: FrameDirection):
        await super().process_frame(frame, direction)

        if isinstance(frame, StartFrame):
            await self.push_frame(frame, direction)
            self._enqueue(self._open_call)
        elif isinstance(frame, TranscriptionFrame):
            # No sigue hacia el texto a voz: lo que dijo el deudor solo lo lee el agente.
            if frame.text.strip():
                self._heard.append(frame.text.strip())
                self._answer_if_ready()
        elif isinstance(frame, UserStoppedSpeakingFrame):
            await self.push_frame(frame, direction)
            self._turn_finished = True
            self._turn_finished_at = time.monotonic()
            self._answer_if_ready()
        elif isinstance(frame, (EndFrame, CancelFrame)):
            if self._grace is not None:
                await self._grace                      # el último turno entra a la fila antes de colgar
            if self._worker is not None:
                await self._enqueue(self._hang_up)   # espera lo que estaba en la fila
                self._worker.cancel()
            await self.push_frame(frame, direction)
        else:
            await self.push_frame(frame, direction)

    # --- fila de trabajo ----------------------------------------------------------------------

    def _enqueue(self, job: Job) -> asyncio.Future:
        loop = asyncio.get_running_loop()
        if self._jobs is None:
            self._jobs = asyncio.Queue()
            self._worker = loop.create_task(self._work())
        done = loop.create_future()
        self._jobs.put_nowait((job, done))
        return done

    async def _work(self) -> None:
        while True:
            job, done = await self._jobs.get()
            try:
                await job()
            except Exception:   # un turno fallido no debe tumbar la llamada
                log.exception("Falló un turno de voz")
            finally:
                if not done.done():
                    done.set_result(None)

    # --- llamada ------------------------------------------------------------------------------

    async def _open_call(self) -> None:
        self._session, reply = await asyncio.to_thread(self._start_call)
        await self._say(reply)

    def _answer_if_ready(self) -> None:
        if self._turn_finished and self._heard and self._grace is None:
            self._grace = asyncio.get_running_loop().create_task(self._close_turn())

    async def _close_turn(self) -> None:
        await asyncio.sleep(TRANSCRIPT_GRACE_SECONDS)
        text = " ".join(self._heard)
        finished_at = self._turn_finished_at
        self._heard, self._turn_finished, self._grace = [], False, None
        self._enqueue(lambda: self._answer(text, finished_at))

    async def _answer(self, text: str, turn_finished_at: float) -> None:
        if self._session is None or self._session.ended:
            return
        reply = await asyncio.to_thread(self._session.debtor_says, text)
        latency = time.monotonic() - turn_finished_at
        log.info("Turno del agente en %.2f s (sin contar el texto a voz)", latency)
        if self._on_turn_latency:
            self._on_turn_latency(latency)
        await self._say(reply)

    async def _say(self, reply: AgentReply) -> None:
        if reply.text:
            await self.push_frame(TTSSpeakFrame(reply.text))
        if reply.call_ended:
            # EndFrame va en orden: se dice la despedida y después se cierra la conexión.
            await self.push_frame(EndFrame())

    async def _hang_up(self) -> None:
        session = self._session
        if session is not None and not session.ended:
            await asyncio.to_thread(session.hang_up)
