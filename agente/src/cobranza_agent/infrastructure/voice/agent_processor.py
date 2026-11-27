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
conversación es una sola y el backend no admite dos turnos a la vez. Si el deudor termina otro turno
mientras el agente todavía no contesta el anterior, los dos se juntan en uno (no se apilan respuestas).

Relleno (pedido en la prueba por celular, 2026-11-19): si la respuesta no está lista en
FILLER_AFTER_SECONDS, el agente dice una frase corta ("One moment, please.") para no dejar silencio;
si pasa de PATIENCE_AFTER_SECONDS, una segunda. El relleno no entra a la conversación del modelo.

Silencio (decisión 9 del 2026-11-24): cuando Lucy termina de hablar y nadie dice nada, a los
IDLE_PROMPT_AFTER_SECONDS pregunta "Are you still there?" y a los IDLE_CLOSE_AFTER_SECONDS se
despide y cuelga (la llamada queda como volver a llamar). Cualquier palabra del deudor reinicia la cuenta.
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
    BotStoppedSpeakingFrame,
    TranscriptionFrame,
    TTSSpeakFrame,
    UserStartedSpeakingFrame,
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
# Relleno mientras el agente piensa. En la prueba, los turnos sin herramientas tardaron ~1,1 s y los
# que verifican o buscan la cuenta, ~2,8 s.
FILLER_AFTER_SECONDS = 1.0
PATIENCE_AFTER_SECONDS = 4.0
FILLERS = ("Let me check our records, please.", "One moment, please.", "Okay...")
PATIENCE_FILLER = "Thanks for your patience, I'm almost done."
IDLE_PROMPT_AFTER_SECONDS = 10.0
IDLE_CLOSE_AFTER_SECONDS = 30.0
IDLE_PROMPT = "Are you still there?"
IDLE_GOODBYE = "I'll end the call now. You can call us back anytime. Goodbye."


class AgentTurnProcessor(FrameProcessor):
    def __init__(self, start_call: StartCall, on_turn_latency: Callable[[float], None] | None = None,
                 filler_after: float = FILLER_AFTER_SECONDS,
                 patience_after: float = PATIENCE_AFTER_SECONDS,
                 idle_prompt_after: float = IDLE_PROMPT_AFTER_SECONDS,
                 idle_close_after: float = IDLE_CLOSE_AFTER_SECONDS, **kwargs):
        super().__init__(**kwargs)
        self._idle_prompt_after = idle_prompt_after
        self._idle_close_after = idle_close_after
        self._idle: asyncio.Task | None = None    # cuenta del silencio desde que Lucy terminó de hablar
        self._start_call = start_call
        self._on_turn_latency = on_turn_latency
        self._filler_after = filler_after
        self._patience_after = patience_after
        self._fillers_said = 0
        self._waiting: list[str] = []        # turnos terminados que el agente todavía no contesta
        self._waiting_since = 0.0
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
        elif isinstance(frame, BotStoppedSpeakingFrame):
            await self.push_frame(frame, direction)
            self._start_idle_count()
        elif isinstance(frame, UserStartedSpeakingFrame):
            await self.push_frame(frame, direction)
            self._stop_idle_count()
        elif isinstance(frame, TranscriptionFrame):
            # No sigue hacia el texto a voz: lo que dijo el deudor solo lo lee el agente.
            self._stop_idle_count()
            if frame.text.strip():
                self._heard.append(frame.text.strip())
                self._answer_if_ready()
        elif isinstance(frame, UserStoppedSpeakingFrame):
            await self.push_frame(frame, direction)
            self._turn_finished = True
            self._turn_finished_at = time.monotonic()
            self._answer_if_ready()
        elif isinstance(frame, (EndFrame, CancelFrame)):
            self._stop_idle_count()
            if self._grace is not None:
                await self._grace                      # el último turno entra a la fila antes de colgar
            if self._worker is not None:
                await self._enqueue(self._hang_up)   # espera lo que estaba en la fila
                self._worker.cancel()
            await self.push_frame(frame, direction)
        else:
            await self.push_frame(frame, direction)

    # --- silencio -----------------------------------------------------------------------------

    def _start_idle_count(self) -> None:
        """Lucy terminó de hablar. Si ya había una cuenta (por ejemplo, tras "Are you still there?"),
        sigue la misma: no se reinicia con lo que dice Lucy, solo con lo que dice el deudor."""
        if self._idle is None and self._session is not None and not self._session.ended:
            self._idle = asyncio.get_running_loop().create_task(self._count_silence())

    def _stop_idle_count(self) -> None:
        if self._idle is not None:
            self._idle.cancel()
            self._idle = None

    async def _count_silence(self) -> None:
        await asyncio.sleep(self._idle_prompt_after)
        await self.push_frame(TTSSpeakFrame(IDLE_PROMPT))
        await asyncio.sleep(self._idle_close_after - self._idle_prompt_after)
        self._idle = None
        log.info("Llamada sin respuesta por %.0f s: se cierra", self._idle_close_after)
        await self.push_frame(TTSSpeakFrame(IDLE_GOODBYE))
        await self._enqueue(self._hang_up)
        await self.push_frame(EndFrame())

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
        if not self._waiting:
            # Un solo turno en la fila: lo que el deudor diga antes de que se conteste se le suma.
            self._waiting_since = self._turn_finished_at
            self._enqueue(self._answer_waiting)
        self._waiting.append(text)
        self._heard, self._turn_finished, self._grace = [], False, None

    async def _answer_waiting(self) -> None:
        text, turn_finished_at = " ".join(self._waiting), self._waiting_since
        self._waiting = []
        await self._answer(text, turn_finished_at)

    async def _answer(self, text: str, turn_finished_at: float) -> None:
        if self._session is None or self._session.ended:
            return
        thinking = asyncio.ensure_future(asyncio.to_thread(self._session.debtor_says, text))
        reply = await self._while_thinking(thinking)
        latency = time.monotonic() - turn_finished_at
        log.info("Turno del agente en %.2f s (sin contar el texto a voz)", latency)
        if self._on_turn_latency:
            self._on_turn_latency(latency)
        await self._say(reply)

    async def _while_thinking(self, thinking: asyncio.Future) -> AgentReply:
        """Espera la respuesta; si tarda, dice un relleno para no dejar silencio."""
        started = time.monotonic()
        plan = ((self._filler_after, self._next_filler), (self._patience_after, lambda: PATIENCE_FILLER))
        for after, phrase in plan:
            await asyncio.wait({thinking}, timeout=max(0.0, after - (time.monotonic() - started)))
            if thinking.done():
                break
            await self.push_frame(TTSSpeakFrame(phrase()))
        return await thinking

    def _next_filler(self) -> str:
        """Los rellenos rotan para que no repita siempre el mismo."""
        phrase = FILLERS[self._fillers_said % len(FILLERS)]
        self._fillers_said += 1
        return phrase

    async def _say(self, reply: AgentReply) -> None:
        self._stop_idle_count()
        if reply.text:
            await self.push_frame(TTSSpeakFrame(reply.text))
        if reply.call_ended:
            # EndFrame va en orden: se dice la despedida y después se cierra la conexión.
            await self.push_frame(EndFrame())

    async def _hang_up(self) -> None:
        session = self._session
        if session is not None and not session.ended:
            await asyncio.to_thread(session.hang_up)
