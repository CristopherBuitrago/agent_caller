-- Modelo provisional del agente de cobranza NSF.
-- Se reemplazará/ajustará cuando llegue el EER de la base real.
-- Montos en centavos (bigint) para evitar errores de redondeo.
-- Regla de negocio: NUNCA hay descuentos; siempre se cobra el saldo completo.

CREATE EXTENSION IF NOT EXISTS pgcrypto;

CREATE OR REPLACE FUNCTION set_updated_at() RETURNS trigger AS $$
BEGIN
    NEW.updated_at = now();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

-- ---------------------------------------------------------------------------
-- debtors: la persona
-- ---------------------------------------------------------------------------
CREATE TABLE debtors (
    id                uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    external_id       text UNIQUE,                 -- ID en el sistema real
    first_name        text NOT NULL,
    last_name         text NOT NULL,
    -- Fecha de nacimiento y últimos 4 del SSN guardados como HMAC-SHA256 con una
    -- clave de la aplicación (PII_HMAC_KEY). Nunca se pueden leer en claro; la
    -- verificación compara el HMAC de lo que dice el deudor con lo guardado.
    -- Formato antes del HMAC: dob = 'YYYY-MM-DD', ssn_last4 = '1234'.
    dob_hmac          bytea NOT NULL,
    ssn_last4_hmac    bytea NOT NULL,
    phone_primary     text NOT NULL,               -- formato E.164: +13055550123
    phone_secondary   text,
    us_state          char(2),                     -- puede faltar
    timezone          text,                        -- IANA, p. ej. America/New_York; si falta se deduce del código de área
    do_not_call       boolean NOT NULL DEFAULT false,
    skip_trace_status text,                        -- p. ej. pending / found / not_found (por definir)
    created_at        timestamptz NOT NULL DEFAULT now(),
    updated_at        timestamptz NOT NULL DEFAULT now(),
    CONSTRAINT phone_primary_e164 CHECK (phone_primary ~ '^\+1[0-9]{10}$'),
    CONSTRAINT phone_secondary_e164 CHECK (phone_secondary IS NULL OR phone_secondary ~ '^\+1[0-9]{10}$')
);

CREATE INDEX debtors_phone_primary_idx   ON debtors (phone_primary);
CREATE INDEX debtors_phone_secondary_idx ON debtors (phone_secondary);

CREATE TRIGGER debtors_updated_at BEFORE UPDATE ON debtors
    FOR EACH ROW EXECUTE FUNCTION set_updated_at();

-- ---------------------------------------------------------------------------
-- accounts: cada deuda (un deudor puede tener varias, del mismo o de distintos acreedores)
-- ---------------------------------------------------------------------------
CREATE TABLE accounts (
    id                     uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    external_id            text UNIQUE,
    debtor_id              uuid NOT NULL REFERENCES debtors (id),
    creditor_name          text NOT NULL,
    account_number_masked  text NOT NULL,          -- ****4821
    original_amount_cents  bigint NOT NULL CHECK (original_amount_cents >= 0),
    nsf_amount_cents       bigint CHECK (nsf_amount_cents >= 0),   -- monto que rebotó
    nsf_fee_cents          bigint NOT NULL DEFAULT 0 CHECK (nsf_fee_cents >= 0),
    current_balance_cents  bigint NOT NULL CHECK (current_balance_cents >= 0),
    payment_method         text CHECK (payment_method IN ('ACH', 'CHECK', 'CARD')),
    -- Un solo campo para el estado de pago y los intentos de contacto.
    -- El agente solo cobra NSF; cualquier otro valor, incluidos los intentos,
    -- se transfiere a una persona. Texto libre hasta conocer el catálogo real.
    status                 text NOT NULL,
    status_updated_at      timestamptz NOT NULL DEFAULT now(),
    nsf_date               date,
    nsf_return_code        text,                   -- p. ej. R01
    is_disputed            boolean NOT NULL DEFAULT false,
    created_at             timestamptz NOT NULL DEFAULT now(),
    updated_at             timestamptz NOT NULL DEFAULT now()
);

CREATE INDEX accounts_debtor_id_idx ON accounts (debtor_id);
CREATE INDEX accounts_status_idx    ON accounts (status);

CREATE TRIGGER accounts_updated_at BEFORE UPDATE ON accounts
    FOR EACH ROW EXECUTE FUNCTION set_updated_at();

-- ---------------------------------------------------------------------------
-- calls: cada llamada, entrante o saliente
-- ---------------------------------------------------------------------------
CREATE TABLE calls (
    id                    uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    debtor_id             uuid REFERENCES debtors (id),    -- null si no se identificó
    account_id            uuid REFERENCES accounts (id),
    direction             text NOT NULL CHECK (direction IN ('inbound', 'outbound')),
    caller_phone          text NOT NULL,
    started_at            timestamptz NOT NULL DEFAULT now(),
    ended_at              timestamptz,
    recording_consent     boolean,
    identity_verified     boolean NOT NULL DEFAULT false,
    verification_attempts smallint NOT NULL DEFAULT 0 CHECK (verification_attempts >= 0),
    outcome               text CHECK (outcome IN (
                              'payment_taken',          -- pagó en el IVR PCI
                              'arrangement_made',       -- parcial o plan agendado
                              'transferred_to_human',   -- estado distinto de NSF, disputa, pedido del deudor
                              'dispute',
                              'do_not_call',
                              'verification_failed',
                              'wrong_party',            -- contestó un tercero
                              'callback_requested',
                              'no_answer',
                              'recording_refused',      -- no aceptó la grabación: se cierra sin hablar de la deuda
                              'identity_mismatch'       -- cambió de nombre entre intentos de verificación
                          )),
    summary               text,                     -- generado por IA al cerrar; nunca incluye SSN ni fecha de nacimiento
    recording_uri         text,                     -- ruta del audio en el almacenamiento
    transcript_uri        text                      -- ruta del texto de la conversación
);

CREATE INDEX calls_debtor_id_idx  ON calls (debtor_id);
CREATE INDEX calls_account_id_idx ON calls (account_id);

-- ---------------------------------------------------------------------------
-- payment_arrangements: el acuerdo negociado (sin descuentos)
--   full    = paga todo hoy
--   partial = monto que dice el deudor (mínimo 5%); el resto en una fecha, máximo a 30 días
--   plan    = hasta 10 cuotas mensuales iguales, en fecha fija
-- El primer pago es en máximo 8 días. Estas reglas se validan en domain/arrangement.py.
-- Al crear un acuerdo, accounts.status pasa a PTP.
-- ---------------------------------------------------------------------------
CREATE TABLE payment_arrangements (
    id                 uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    call_id            uuid REFERENCES calls (id),
    account_id         uuid NOT NULL REFERENCES accounts (id),
    type               text NOT NULL CHECK (type IN ('full', 'partial', 'plan')),
    total_amount_cents bigint NOT NULL CHECK (total_amount_cents > 0),  -- siempre el saldo completo
    status             text NOT NULL DEFAULT 'active'
                           CHECK (status IN ('active', 'completed', 'broken', 'cancelled')),
    created_at         timestamptz NOT NULL DEFAULT now()
);

CREATE INDEX payment_arrangements_account_id_idx ON payment_arrangements (account_id);
-- Una cuenta solo puede tener un acuerdo activo.
CREATE UNIQUE INDEX payment_arrangements_one_active_idx ON payment_arrangements (account_id)
    WHERE status = 'active';

-- ---------------------------------------------------------------------------
-- scheduled_payments: cada pago agendado de un acuerdo
--   partial = 2 filas (hoy + el resto); plan = una fila por cuota
-- ---------------------------------------------------------------------------
CREATE TABLE scheduled_payments (
    id             uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    arrangement_id uuid NOT NULL REFERENCES payment_arrangements (id),
    sequence       smallint NOT NULL CHECK (sequence >= 1),
    amount_cents   bigint NOT NULL CHECK (amount_cents > 0),
    due_date       date NOT NULL,
    status         text NOT NULL DEFAULT 'pending'
                       CHECK (status IN ('pending', 'paid', 'failed', 'cancelled')),
    paid_at        timestamptz,
    UNIQUE (arrangement_id, sequence)
);

-- ---------------------------------------------------------------------------
-- payment_results: lo que devuelve el IVR PCI (nunca datos de tarjeta)
-- ---------------------------------------------------------------------------
CREATE TABLE payment_results (
    id                   uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    arrangement_id       uuid NOT NULL REFERENCES payment_arrangements (id),
    scheduled_payment_id uuid REFERENCES scheduled_payments (id),
    ivr_reference        text NOT NULL UNIQUE,      -- número de confirmación del IVR
    amount_cents         bigint NOT NULL CHECK (amount_cents > 0),
    status               text NOT NULL CHECK (status IN ('approved', 'declined', 'error')),
    processed_at         timestamptz NOT NULL DEFAULT now()
);

-- ---------------------------------------------------------------------------
-- hardship_assessments: respuestas de las Hardship Questions
-- ---------------------------------------------------------------------------
CREATE TABLE hardship_assessments (
    id                     uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    call_id                uuid NOT NULL UNIQUE REFERENCES calls (id),
    debtor_id              uuid NOT NULL REFERENCES debtors (id),
    situation_description  text,                       -- qué pasó
    situation_started      text,                       -- cuándo empezó, en palabras del deudor
    duration_type          text CHECK (duration_type IN ('temporary', 'long_term')),
    household_support      boolean,                    -- si alguien en el hogar puede colaborar
    offered_amount_cents   bigint CHECK (offered_amount_cents >= 0),
    notes                  text,
    recommended_plan       text,                       -- lo que el agente termina ofreciendo
    created_at             timestamptz NOT NULL DEFAULT now()
);

-- ---------------------------------------------------------------------------
-- sms_messages: cada SMS enviado al deudor (N1, aprobada el 2026-11-12).
-- Confirmación del acuerdo y link de pago de cada cuota. Nunca lleva SSN ni fecha
-- de nacimiento. Se envía aunque el deudor esté marcado do_not_call (decisión del
-- desarrollador): una llamada no es un SMS y el deudor aceptó el acuerdo.
-- ---------------------------------------------------------------------------
CREATE TABLE sms_messages (
    id                   uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    debtor_id            uuid NOT NULL REFERENCES debtors (id),
    arrangement_id       uuid NOT NULL REFERENCES payment_arrangements (id),
    scheduled_payment_id uuid REFERENCES scheduled_payments (id),   -- vacío en la confirmación
    kind                 text NOT NULL CHECK (kind IN ('arrangement_confirmation', 'payment_link')),
    to_phone             text NOT NULL,
    body                 text NOT NULL,
    status               text NOT NULL DEFAULT 'pending' CHECK (status IN ('pending', 'sent', 'failed')),
    provider_message_id  text,                                       -- id que devuelve el proveedor de SMS
    error                text,                                       -- motivo, si falló
    created_at           timestamptz NOT NULL DEFAULT now(),
    sent_at              timestamptz,
    CHECK ((kind = 'payment_link') = (scheduled_payment_id IS NOT NULL))
);

-- Nunca dos veces el mismo mensaje: una confirmación por acuerdo y un link por cuota.
CREATE UNIQUE INDEX sms_messages_one_confirmation_idx ON sms_messages (arrangement_id)
    WHERE kind = 'arrangement_confirmation';
CREATE UNIQUE INDEX sms_messages_one_link_per_payment_idx ON sms_messages (scheduled_payment_id)
    WHERE kind = 'payment_link';
