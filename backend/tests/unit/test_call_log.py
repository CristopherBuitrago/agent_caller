"""Historial de llamadas del chat de prueba (archivos JSON)."""

import pytest

from cobranza.agent.infrastructure.call_log import CallLog, CallLogStore


def _log():
    log = CallLog("call-1", {"direction": "inbound", "phone": "+13055550001", "label": "Jane"})
    log.system("Llamada entrante")
    log.agent("Thank you for calling L.O.F.")
    log.debtor("Jane Carter, 1234, March 14 1985")
    log.tool("verify_identity", {"full_name": "Jane Carter", "ssn_last4": "1234",
                                 "date_of_birth": "1985-03-14"}, '{"outcome": "verified"}', False)
    log.debtor("My balance is 12345 dollars? and 1234")
    return log


def test_ssn_is_masked_and_never_kept_in_tool_input():
    data = _log().to_dict()
    debtor_lines = [e["text"] for e in data["events"] if e["type"] == "debtor"]
    assert debtor_lines == ["Jane Carter, ****, March 14 1985", "My balance is 12345 dollars? and ****"]
    tool = next(e for e in data["events"] if e["type"] == "tool")
    assert tool["input"] == {"full_name": "Jane Carter"}       # sin SSN ni fecha de nacimiento
    assert tool["result"] == '{"outcome": "verified"}'


def test_store_saves_lists_and_reads_calls(tmp_path):
    store = CallLogStore(tmp_path / "logs")
    assert store.list() == []
    log = _log()
    path = store.save(log)
    assert path.name == "call-1.json"
    listed = store.list()
    assert listed[0]["call_id"] == "call-1" and listed[0]["turns"] == 2 and listed[0]["outcome"] is None
    log.end("callback_requested", "Short call.")
    store.save(log)
    full = store.get("call-1")
    assert full["outcome"] == "callback_requested" and full["summary"] == "Short call."
    assert [e["type"] for e in full["events"]][:3] == ["system", "agent", "debtor"]


@pytest.mark.parametrize("bad", ["../etc/passwd", "a/b", "", "x" * 65])
def test_store_rejects_unsafe_ids(tmp_path, bad):
    store = CallLogStore(tmp_path)
    assert store.get(bad) is None
