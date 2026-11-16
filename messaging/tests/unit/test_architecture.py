"""Reglas de arquitectura de la mensajería (cobranza_messaging).

- application no importa infraestructura (ni la del núcleo ni la propia) ni librerías externas.
- No conoce al otro programa (cobranza_agent).
- Usa los casos de uso del núcleo (paquete cobranza), nunca sus repositorios directamente.
"""

import ast
from pathlib import Path

import pytest

SRC = Path(__file__).resolve().parents[2] / "src" / "cobranza_messaging"
LIBS = ("psycopg", "psycopg_pool", "phonenumbers", "anthropic", "fastapi", "uvicorn")

# Carpeta -> prefijos que no puede importar ("" es todo el paquete).
FORBIDDEN = {
    "": ("cobranza_agent", "cobranza.infrastructure.repositories"),
    "application": ("cobranza.infrastructure", "cobranza_messaging.infrastructure", "cobranza_agent", *LIBS),
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
        if name.startswith(FORBIDDEN[folder])
    ]
    assert violations == []
