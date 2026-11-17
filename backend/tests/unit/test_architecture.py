"""Reglas de arquitectura del núcleo (hexagonal) y su independencia de los otros 2 programas.

Núcleo de cobranza (backend/, paquete cobranza): reglas, casos de uso y base de datos.
Agente de voz (agente/, paquete cobranza_agent) y mensajería (messaging/, paquete
cobranza_messaging) usan el núcleo; cada uno vigila sus propias reglas en su carpeta tests/.

- domain no importa nada del proyecto ni librerías de infraestructura.
- application no importa infraestructura.
- El núcleo no conoce al agente ni a la mensajería.
"""

import ast
from pathlib import Path

import pytest

SRC = Path(__file__).resolve().parents[2] / "src" / "cobranza"
LIBS = ("psycopg", "psycopg_pool", "phonenumbers", "anthropic", "fastapi", "uvicorn")
OTHER_PROGRAMS = ("cobranza_agent", "cobranza_messaging")

# Carpeta -> prefijos que no puede importar ("" es todo el paquete).
FORBIDDEN = {
    "": OTHER_PROGRAMS,
    "domain": ("cobranza.application", "cobranza.infrastructure", *LIBS),
    "application": ("cobranza.infrastructure", *LIBS),
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
