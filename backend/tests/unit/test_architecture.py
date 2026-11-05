"""Regla hexagonal: dominio y aplicación no dependen de la infraestructura.

domain       -> no importa nada del proyecto ni librerías externas de infraestructura
application  -> solo importa domain (y sus propias interfaces)
infrastructure -> puede importar todo
"""

import ast
from pathlib import Path

import pytest

SRC = Path(__file__).resolve().parents[2] / "src" / "cobranza"

# Qué no puede importar cada capa.
FORBIDDEN = {
    "domain": ("cobranza.application", "cobranza.infrastructure",
               "psycopg", "psycopg_pool", "phonenumbers", "anthropic"),
    "application": ("cobranza.infrastructure",
                    "psycopg", "psycopg_pool", "phonenumbers", "anthropic"),
}


def _imports(path: Path) -> set[str]:
    names = set()
    for node in ast.walk(ast.parse(path.read_text(encoding="utf-8"))):
        if isinstance(node, ast.Import):
            names.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            names.add(node.module)
    return names


@pytest.mark.parametrize("layer", FORBIDDEN)
def test_layer_does_not_import_outer_layers(layer):
    violations = [
        f"{py.relative_to(SRC)} importa {name}"
        for py in (SRC / layer).rglob("*.py")
        for name in _imports(py)
        if name.startswith(FORBIDDEN[layer])
    ]
    assert violations == []
