"""Tarea programada de la mensajería: confirmaciones de acuerdos nuevos, avisos 3 días antes de cada
cuota (N10) y links de las cuotas que vencen.

Se puede correr varias veces al día sin repetir mensajes (cada SMS se envía una sola vez).

Uso:
    python -m cobranza.messaging.infrastructure.run              # fecha de hoy en hora del este de EE. UU.
    python -m cobranza.messaging.infrastructure.run --fecha 2026-12-11

Necesita DATABASE_URL y PII_HMAC_KEY.
"""

import argparse
import logging
import os
from datetime import date, datetime
from zoneinfo import ZoneInfo

from psycopg_pool import ConnectionPool

from cobranza.infrastructure.config.container import build_use_cases
from cobranza.messaging.infrastructure.container import build_messaging

# Supuesto: la tarea corre una vez en la mañana con la fecha del este de EE. UU.
DEFAULT_TIMEZONE = ZoneInfo("America/New_York")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--fecha", type=date.fromisoformat, default=datetime.now(DEFAULT_TIMEZONE).date(),
                        help="Fecha de las cuotas que vencen (AAAA-MM-DD). Por defecto, hoy.")
    args = parser.parse_args()
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")

    with ConnectionPool(os.environ["DATABASE_URL"], min_size=1, max_size=2) as pool:
        messaging = build_messaging(pool, build_use_cases(pool, os.environ["PII_HMAC_KEY"]))
        confirmations = messaging.send_confirmations.execute()
        reminders = messaging.send_payment_reminders.execute(args.fecha)
        links = messaging.send_due_payment_links.execute(args.fecha)
    print(f"Confirmaciones: {confirmations}")
    print(f"Avisos 3 días antes ({args.fecha}): {reminders}")
    print(f"Links de pago ({args.fecha}): {links}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
