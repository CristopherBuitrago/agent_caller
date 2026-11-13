"""Tarea diaria (N10): rompe los acuerdos con una cuota sin pagar 5 días después de su fecha y
devuelve la cuenta a NSF (entra de nuevo a la lista diaria de salientes).

PROTECCIÓN: solo corre con PAYMENT_RESULTS_CONNECTED=true. Mientras no esté conectado el aviso de
pago del procesador, ninguna cuota aparece como pagada y la tarea rompería todos los acuerdos.

Uso:
    PAYMENT_RESULTS_CONNECTED=true python -m cobranza.infrastructure.controllers.break_overdue_arrangements
    PAYMENT_RESULTS_CONNECTED=true python -m cobranza.infrastructure.controllers.break_overdue_arrangements --fecha 2026-12-20

Necesita DATABASE_URL y PII_HMAC_KEY.
"""

import argparse
import os
from datetime import date, datetime
from zoneinfo import ZoneInfo

from psycopg_pool import ConnectionPool

from cobranza.infrastructure.config.container import build_use_cases

DEFAULT_TIMEZONE = ZoneInfo("America/New_York")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--fecha", type=date.fromisoformat, default=datetime.now(DEFAULT_TIMEZONE).date(),
                        help="Día de la revisión (AAAA-MM-DD). Por defecto, hoy.")
    args = parser.parse_args()
    if os.environ.get("PAYMENT_RESULTS_CONNECTED", "").lower() != "true":
        print("No se ejecutó: el aviso de pago del procesador no está conectado "
              "(PAYMENT_RESULTS_CONNECTED=true). Sin él, se romperían todos los acuerdos.")
        return 1
    with ConnectionPool(os.environ["DATABASE_URL"], min_size=1, max_size=2) as pool:
        broken = build_use_cases(pool, os.environ["PII_HMAC_KEY"]).break_overdue_arrangements.execute(args.fecha)
    print(f"Acuerdos rotos ({args.fecha}): {len(broken)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
