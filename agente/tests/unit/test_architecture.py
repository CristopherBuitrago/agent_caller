"""Reglas de arquitectura del agente de voz (cobranza_agent).

- application no importa su infraestructura ni librerías externas.
- No conoce al otro programa (cobranza_messaging).
- No importa el núcleo (paquete cobranza): todo se lo pide a la API del backend por HTTP.
"""

import ast
from pathlib import Path

import pytest

SRC = Path(__file__).resolve().parents[2] / "src" / "cobranza_agent"
LIBS = ("psycopg", "psycopg_pool", "phonenumbers", "anthropic", "fastapi", "uvicorn", "pipecat")

# Carpeta -> prefijos que no puede importar ("" es todo el paquete).
FORBIDDEN = {
    "": ("cobranza_messaging", "cobranza."),
    "application": ("cobranza_agent.infrastructure", "cobranza_messaging", "httpx", *LIBS),
}


def _imports(path: Path) -> set[str]:
    names = set()
    for node in ast.walk(ast.parse(path.read_text(encoding="utf-8"))):
        if isinstance(node, ast.Import):
            names.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            names.add(node.module)
    return names


@pytest.mark.parametrize("folder", FORBIDDEN)
def test_folder_does_not_import_what_it_must_not(folder):
    violations = [
        f"{py.relative_to(SRC)} importa {name}"
        for py in (SRC / folder).rglob("*.py")
        for name in _imports(py)
        if name.startswith(FORBIDDEN[folder]) or name == "cobranza"
    ]
    assert violations == []
