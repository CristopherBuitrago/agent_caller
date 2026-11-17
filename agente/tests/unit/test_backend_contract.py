"""El agente tiene su propia copia de los valores de una llamada (application/call.py), porque le
llegan por HTTP como texto y su código no puede importar el núcleo. Esta prueba sí lo importa (el
Dockerfile lo instala para las pruebas) y revisa que las dos copias no se separen: si el backend
agrega o cambia un valor, falla hasta que se actualice la copia del agente.
"""

import pytest

from cobranza.domain import call as backend_call
from cobranza_agent.application import call as agent_call


@pytest.mark.parametrize("name", ["CallDirection", "CallOutcome"])
def test_agent_copy_has_the_same_values_as_the_backend(name):
    backend = {member.name: member.value for member in getattr(backend_call, name)}
    agent = {member.name: member.value for member in getattr(agent_call, name)}
    assert agent == backend, (
        f"{name} del agente no coincide con cobranza.domain.call.{name}: "
        f"faltan {sorted(backend.keys() - agent.keys())}, sobran {sorted(agent.keys() - backend.keys())}"
    )
