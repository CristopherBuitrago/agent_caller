"""Textos de los SMS (en inglés: el servicio es para EE. UU.).

No dicen "debt" ni el acreedor, por si otra persona ve el teléfono. El texto final lo debe
revisar el abogado (supuesto legal de N1).
"""

from datetime import date

_MONTHS = ("Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec")
OPT_OUT = "Reply STOP to opt out."


def money(cents: int) -> str:
    return f"${cents // 100:,}.{cents % 100:02d}"


def short_date(value: date) -> str:
    return f"{_MONTHS[value.month - 1]} {value.day}"


def _payments_summary(payments: list[tuple[int, date]]) -> str:
    """[(centavos, fecha)] -> "$90.00 on Nov 11 and $395.00 on Dec 11", o resumen si son más de 3."""
    if len(payments) <= 3:
        parts = [f"{money(amount)} on {short_date(due)}" for amount, due in payments]
        return parts[0] if len(parts) == 1 else ", ".join(parts[:-1]) + " and " + parts[-1]
    first, *rest = [amount for amount, _ in payments]
    start = short_date(payments[0][1])
    if all(amount == first for amount in rest):
        return f"{len(payments)} monthly payments of {money(first)} starting {start}"
    # En los planes, la primera cuota lleva los centavos que sobran de la división.
    return f"{len(payments)} monthly payments starting {start}: {money(first)}, then {money(rest[0])} each"


def confirmation_text(company: str, payments: list[tuple[int, date]]) -> str:
    return (f"{company}: your payment arrangement is set: {_payments_summary(payments)}. "
            f"We'll text you a secure payment link on each date. {OPT_OUT}")


def payment_link_text(company: str, amount_cents: int, due: date, today: date, link: str) -> str:
    when = "today" if due == today else f"on {short_date(due)}"
    verb = "is due" if due >= today else "was due"
    return f"{company}: your payment of {money(amount_cents)} {verb} {when}. Pay securely here: {link} {OPT_OUT}"


def payment_reminder_text(company: str, amount_cents: int, due: date) -> str:
    """N10: aviso 3 días antes de la cuota. Solo avisa; el link llega el día del pago."""
    return (f"{company}: reminder: your payment of {money(amount_cents)} is due on {short_date(due)}. "
            f"We'll text you a secure payment link that day. {OPT_OUT}")
