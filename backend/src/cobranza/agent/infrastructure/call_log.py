"""Historial de llamadas del chat de prueba: un archivo JSON por llamada, para auditarlas después.

Guarda la conversación completa (agente, deudor y avisos del sistema) y cada herramienta que usó el
agente con lo que respondió el sistema. Se escribe después de cada turno, así no se pierde nada si el
servidor se cae. La ruta del archivo queda en calls.transcript_uri.

Los últimos 4 del SSN que dice el deudor se enmascaran en el archivo (****). La fecha de nacimiento
no se puede detectar con seguridad en texto libre: este historial es para pruebas con datos simulados.
"""

import json
import re
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path

_SAFE_ID = re.compile(r"^[A-Za-z0-9-]{1,64}$")


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


@dataclass
class CallLog:
    call_id: str
    scenario: dict
    started_at: str = field(default_factory=_now)
    events: list[dict] = field(default_factory=list)
    outcome: str | None = None
    summary: str | None = None
    ended_at: str | None = None
    _secrets: set[str] = field(default_factory=set)

    def agent(self, text: str) -> None:
        if text:
            self.events.append({"at": _now(), "type": "agent", "text": text})

    def debtor(self, text: str) -> None:
        self.events.append({"at": _now(), "type": "debtor", "text": text})

    def system(self, text: str) -> None:
        self.events.append({"at": _now(), "type": "system", "text": text})

    def tool(self, name: str, tool_input: dict, result: str, error: bool) -> None:
        ssn = tool_input.get("ssn_last4") if name == "verify_identity" else None
        if ssn:
            self._secrets.add(str(ssn).strip())
        shown = {k: v for k, v in tool_input.items() if k not in ("ssn_last4", "date_of_birth")}
        self.events.append({"at": _now(), "type": "tool", "name": name, "input": shown,
                            "result": result, "error": error})

    def end(self, outcome: str | None, summary: str | None) -> None:
        self.outcome, self.summary, self.ended_at = outcome, summary, _now()

    def to_dict(self) -> dict:
        def mask(text: str) -> str:
            for secret in self._secrets:
                if secret:
                    text = re.sub(rf"(?<!\d){re.escape(secret)}(?!\d)", "****", text)
            return text

        events = [{**e, "text": mask(e["text"])} if e["type"] == "debtor" else e for e in self.events]
        return {"call_id": self.call_id, "scenario": self.scenario, "started_at": self.started_at,
                "ended_at": self.ended_at, "outcome": self.outcome, "summary": self.summary,
                "events": events}


class CallLogStore:
    """Carpeta con un archivo <call_id>.json por llamada."""

    def __init__(self, folder: Path):
        self._folder = folder

    def path_for(self, call_id: str) -> Path:
        if not _SAFE_ID.match(call_id):
            raise ValueError("call_id inválido")
        return self._folder / f"{call_id}.json"

    def save(self, log: CallLog) -> Path:
        self._folder.mkdir(parents=True, exist_ok=True)
        path = self.path_for(log.call_id)
        tmp = path.with_suffix(".tmp")
        tmp.write_text(json.dumps(log.to_dict(), ensure_ascii=False, indent=2), encoding="utf-8")
        tmp.replace(path)
        return path

    def get(self, call_id: str) -> dict | None:
        try:
            path = self.path_for(call_id)
        except ValueError:
            return None
        return json.loads(path.read_text(encoding="utf-8")) if path.exists() else None

    def list(self) -> list[dict]:
        if not self._folder.exists():
            return []
        items = []
        for path in self._folder.glob("*.json"):
            try:
                data = json.loads(path.read_text(encoding="utf-8"))
            except (OSError, json.JSONDecodeError):
                continue
            items.append({"call_id": data["call_id"], "scenario": data.get("scenario"),
                          "started_at": data.get("started_at"), "ended_at": data.get("ended_at"),
                          "outcome": data.get("outcome"),
                          "turns": sum(1 for e in data.get("events", []) if e["type"] == "debtor")})
        return sorted(items, key=lambda i: i["started_at"] or "", reverse=True)
