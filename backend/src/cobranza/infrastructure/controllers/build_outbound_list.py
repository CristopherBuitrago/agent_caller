"""Tarea diaria: arma la lista de llamadas salientes del día consultando la base.

Se puede correr varias veces el mismo día: no repite cuentas.

Uso:
    python -m cobranza.infrastructure.controllers.build_outbound_list              # hoy (este de EE. UU.)
    python -m cobranza.infrastructure.controllers.build_outbound_list --fecha 2026-11-13

Necesita DATABASE_URL y PII_HMAC_KEY.
"""

import argparse
import os
from datetime import date, datetime
from zoneinfo import ZoneInfo

from psycopg_pool import ConnectionPool

from cobranza.infrastructure.config.container import build_use_cases

# Supuesto: la lista se arma en la mañana con la fecha del este de EE. UU.
DEFAULT_TIMEZONE = ZoneInfo("America/New_York")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--fecha", type=date.fromisoformat, default=datetime.now(DEFAULT_TIMEZONE).date(),
                        help="Día de la lista (AAAA-MM-DD). Por defecto, hoy.")
    args = parser.parse_args()
    with ConnectionPool(os.environ["DATABASE_URL"], min_size=1, max_size=2) as pool:
        use_cases = build_use_cases(pool, os.environ["PII_HMAC_KEY"])
        added = use_cases.build_daily_outbound_list.execute(args.fecha)
        pending = use_cases.get_outbound_calls.execute(args.fecha)
    print(f"Lista del {args.fecha}: {added} cuentas agregadas, {len(pending)} pendientes de llamar")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
