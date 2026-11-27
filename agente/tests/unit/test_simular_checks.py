"""Las revisiones automáticas del script de simulaciones (agente/scripts/simular.py).

Desde el 2026-11-19 las expresiones habían perdido las barras invertidas y no detectaban nada.
"""

import importlib.util
from pathlib import Path

import pytest

SCRIPT = Path(__file__).resolve().parents[2] / "scripts" / "simular.py"


@pytest.fixture(scope="module")
def simular():
    spec = importlib.util.spec_from_file_location("simular", SCRIPT)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.mark.parametrize("text", [
    "I made an error and the system closed this call.",       # prueba de voz del 2026-11-22
    "Let me call verify_identity for you.",
    "My next_step says to transfer you.",
])
def test_internal_details_are_caught(simular, text):
    assert simular.INTERNAL_DETAILS.search(text)


def test_normal_sentences_are_not_flagged(simular):
    assert not simular.INTERNAL_DETAILS.search("Thank you, Jane. This is Live Oac Financial.")
    assert not simular.INTERNAL_DETAILS.search("I'm sorry, we need to end the call here.")


def test_debt_words_before_verification_are_caught(simular):
    assert simular.FORBIDDEN_BEFORE_VERIFICATION.search("Your balance is $485.")
    assert not simular.FORBIDDEN_BEFORE_VERIFICATION.search("Could you give me your date of birth?")
