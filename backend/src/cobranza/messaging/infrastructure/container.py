"""Contenedor de la mensajería: conecta los casos de uso de SMS con sus implementaciones."""

from dataclasses import dataclass

from psycopg_pool import ConnectionPool

from cobranza.infrastructure.config.container import UseCases
from cobranza.infrastructure.services.system_clock import SystemClock
from cobranza.messaging.application.ports import PaymentLinkProvider, SmsSender
from cobranza.messaging.application.send_sms import SendArrangementConfirmations, SendDuePaymentLinks
from cobranza.messaging.infrastructure.dev_services import LoggingSmsSender, PlaceholderPaymentLinkProvider
from cobranza.messaging.infrastructure.postgres_sms_repository import PostgresSmsRepository

DEFAULT_COMPANY_NAME = "Lakeside Recovery Services"  # nombre ficticio, igual que en el agente


@dataclass(frozen=True)
class Messaging:
    send_confirmations: SendArrangementConfirmations
    send_due_payment_links: SendDuePaymentLinks


def build_messaging(pool: ConnectionPool, use_cases: UseCases, sender: SmsSender | None = None,
                    links: PaymentLinkProvider | None = None,
                    company_name: str = DEFAULT_COMPANY_NAME) -> Messaging:
    """Por ahora, sin proveedor real: el SMS queda en el log y el link es de prueba."""
    sms = PostgresSmsRepository(pool)
    sender = sender or LoggingSmsSender()
    clock = SystemClock()
    return Messaging(
        send_confirmations=SendArrangementConfirmations(
            use_cases.list_new_arrangements, sms, sender, clock, company_name),
        send_due_payment_links=SendDuePaymentLinks(
            use_cases.list_payments_due, sms, sender, links or PlaceholderPaymentLinkProvider(), clock,
            company_name),
    )
