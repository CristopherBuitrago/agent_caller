"""Reglas de arquitectura: hexagonal dentro de cada módulo y 3 módulos independientes.

Núcleo de cobranza (domain, application, infrastructure): reglas, casos de uso y base de datos.
Agente de voz (agent): conversación con Claude, prompt y herramientas.
Mensajería (messaging): SMS de confirmación y links de pago.

- domain no importa nada del proyecto ni librerías de infraestructura.
- application (de cualquier módulo) no importa infraestructura.
- El núcleo no conoce al agente ni a la mensajería; el agente y la mensajería no se conocen entre sí.
  Ambos usan los casos de uso del núcleo, nunca sus repositorios directamente.
"""

import ast
from pathlib import Path

import pytest

SRC = Path(__file__).resolve().parents[2] / "src" / "cobranza"
LIBS = ("psycopg", "psycopg_pool", "phonenumbers", "anthropic")
MODULES = ("cobranza.agent", "cobranza.messaging")

# Carpeta -> prefijos que no puede importar.
FORBIDDEN = {
    "domain": ("cobranza.application", "cobranza.infrastructure", *MODULES, *LIBS),
    "application": ("cobranza.infrastructure", *MODULES, *LIBS),
    "infrastructure": MODULES,
    "agent/application": ("cobranza.infrastructure", "cobranza.agent.infrastructure",
                          "cobranza.messaging", *LIBS),
    "agent": ("cobranza.messaging", "cobranza.infrastructure.repositories"),
    "messaging/application": ("cobranza.infrastructure", "cobranza.messaging.infrastructure",
                              "cobranza.agent", *LIBS),
    "messaging": ("cobranza.agent", "cobranza.infrastructure.repositories"),
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
