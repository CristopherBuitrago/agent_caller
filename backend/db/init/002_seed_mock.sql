-- Datos SIMULADOS para desarrollo. Nada aquí es real.
-- Teléfonos: rango 555-01XX / 555-000X, reservado para ficción en EE. UU.
-- Clave HMAC de desarrollo: 'dev-only-pii-key' (la app debe usar la misma en PII_HMAC_KEY en dev).

CREATE FUNCTION pg_temp.pii(t text) RETURNS bytea AS $$
    SELECT hmac(t, 'dev-only-pii-key', 'sha256')
$$ LANGUAGE sql;

-- Solo en desarrollo: los valores en claro de DOB y SSN para poder probar la verificación.
-- Esta tabla NO existe en producción.
CREATE TABLE dev_mock_secrets (
    debtor_id uuid PRIMARY KEY REFERENCES debtors (id),
    dob       date NOT NULL,
    ssn_last4 char(4) NOT NULL
);

-- ---------------------------------------------------------------------------
-- 1. Casos de prueba fijos (external_id TEST-xxx), uno por situación a probar
-- ---------------------------------------------------------------------------
CREATE TEMP TABLE test_cases (
    ext text, first_name text, last_name text, dob date, ssn char(4),
    phone text, state char(2), tz text, dnc boolean
);
INSERT INTO test_cases VALUES
    ('TEST-001', 'Jane',  'Carter',   '1985-03-14', '1234', '+13055550001', 'FL', 'America/New_York',    false), -- NSF simple
    ('TEST-002', 'Mark',  'Holloway', '1979-11-02', '5678', '+15125550002', 'TX', 'America/Chicago',     false), -- varias cuentas
    ('TEST-003', 'Lucy',  'Bennett',  '1992-07-21', '4321', '+12125550003', NULL, NULL,                  false), -- sin ubicación (212 = NY)
    ('TEST-004', 'Carl',  'Dawson',   '1988-01-30', '1111', '+13125550004', 'IL', 'America/Chicago',     false), -- en disputa
    ('TEST-005', 'Rosa',  'Medina',   '1975-05-05', '2222', '+14155550005', 'CA', 'America/Los_Angeles', true),  -- no llamar
    ('TEST-006', 'Tom',   'Fischer',  '1966-09-09', '3333', '+12065550006', 'WA', 'America/Los_Angeles', false), -- estado PAID
    ('TEST-007', 'Ana',   'Reyes',    '1990-12-12', '4444', '+16025550007', 'AZ', 'America/Phoenix',     false), -- teléfono compartido
    ('TEST-008', 'Luis',  'Reyes',    '1989-02-28', '5555', '+16025550007', 'AZ', 'America/Phoenix',     false), -- teléfono compartido
    ('TEST-009', 'Grace', 'Liu',      '1995-04-18', '6666', '+16175550009', NULL, NULL,                  false); -- fourth_attempt sin ubicación (617 = MA)

WITH ins AS (
    INSERT INTO debtors (external_id, first_name, last_name, dob_hmac, ssn_last4_hmac,
                         phone_primary, us_state, timezone, do_not_call)
    SELECT ext, first_name, last_name, pg_temp.pii(to_char(dob, 'YYYY-MM-DD')), pg_temp.pii(ssn),
           phone, state, tz, dnc
    FROM test_cases
    RETURNING id, external_id
)
INSERT INTO dev_mock_secrets (debtor_id, dob, ssn_last4)
SELECT ins.id, t.dob, t.ssn FROM ins JOIN test_cases t ON t.ext = ins.external_id;

-- Mark también se puede encontrar por su teléfono secundario
UPDATE debtors SET phone_secondary = '+15125550012' WHERE external_id = 'TEST-002';

INSERT INTO accounts (external_id, debtor_id, creditor_name, account_number_masked,
                      original_amount_cents, nsf_amount_cents, nsf_fee_cents, current_balance_cents,
                      payment_method, status, nsf_date, nsf_return_code, is_disputed)
SELECT a.ext, d.id, a.creditor, a.masked, a.orig, a.orig, a.fee, a.balance,
       a.method, a.status, a.nsf_date::date, a.code, a.disputed
FROM (VALUES
    ('ACC-T001',  'TEST-001', 'Lakeside Auto Finance',   '****4821', 45000,  3500, 48500,  'ACH',   'NSF',            '2026-10-10', 'R01', false),
    ('ACC-T002a', 'TEST-002', 'Brightwater Utilities',   '****1190', 18000,  2500, 20500,  'CHECK', 'NSF',            '2026-10-01', 'R01', false),
    ('ACC-T002b', 'TEST-002', 'Summit Health Partners',  '****7734', 92000,  3500, 95500,  'ACH',   'second_attempt', '2026-09-15', 'R01', false),
    ('ACC-T003',  'TEST-003', 'Pinecrest Wireless',      '****3008', 12000,  2500, 14500,  'CARD',  'first_attempt',  '2026-10-05', 'R01', false),
    ('ACC-T004',  'TEST-004', 'Northgate Property Mgmt', '****5512', 150000, 3900, 153900, 'ACH',   'NSF',            '2026-09-28', 'R01', true),
    ('ACC-T005',  'TEST-005', 'Lakeside Auto Finance',   '****6620', 38000,  3500, 41500,  'ACH',   'NSF',            '2026-10-12', 'R01', false),
    ('ACC-T006',  'TEST-006', 'Brightwater Utilities',   '****8841', 9000,   2500, 0,      'CHECK', 'PAID',           '2026-08-20', 'R01', false),
    ('ACC-T007',  'TEST-007', 'Pinecrest Wireless',      '****2201', 15000,  2500, 17500,  'ACH',   'NSF',            '2026-10-08', 'R01', false),
    ('ACC-T008',  'TEST-008', 'Summit Health Partners',  '****9017', 64000,  3500, 67500,  'ACH',   'third_attempt',  '2026-09-02', 'R09', false),
    ('ACC-T009',  'TEST-009', 'Northgate Property Mgmt', '****4470', 110000, 3900, 113900, 'ACH',   'fourth_attempt', '2026-08-25', 'R01', false)
) AS a (ext, debtor_ext, creditor, masked, orig, fee, balance, method, status, nsf_date, code, disputed)
JOIN debtors d ON d.external_id = a.debtor_ext;

-- ---------------------------------------------------------------------------
-- 2. 500 deudores aleatorios (semilla fija: siempre los mismos datos)
-- ---------------------------------------------------------------------------
SELECT setseed(0.42);

CREATE TEMP TABLE gen AS
SELECT g,
       (ARRAY['James','Mary','Robert','Patricia','Michael','Linda','David','Barbara','William','Susan',
              'Richard','Jessica','Joseph','Sarah','Thomas','Karen','Charles','Nancy','Daniel','Lisa'])[1 + (g * 7) % 20] AS first_name,
       (ARRAY['Smith','Johnson','Williams','Brown','Jones','Garcia','Miller','Davis','Rodriguez','Martinez',
              'Hernandez','Lopez','Wilson','Anderson','Taylor','Thomas','Moore','Jackson','Martin','Lee'])[1 + (g * 13) % 20] AS last_name,
       (ARRAY['212','305','312','415','512','602','206','617','303','404'])[1 + g % 10] AS area,
       (ARRAY['NY','FL','IL','CA','TX','AZ','WA','MA','CO','GA'])[1 + g % 10] AS state,
       (ARRAY['America/New_York','America/New_York','America/Chicago','America/Los_Angeles','America/Chicago',
              'America/Phoenix','America/Los_Angeles','America/New_York','America/Denver','America/New_York'])[1 + g % 10] AS tz,
       date '1950-01-01' + (random() * 18000)::int AS dob,
       lpad((random() * 9999)::int::text, 4, '0') AS ssn
FROM generate_series(1, 500) AS g;

WITH ins AS (
    INSERT INTO debtors (external_id, first_name, last_name, dob_hmac, ssn_last4_hmac,
                         phone_primary, us_state, timezone, do_not_call)
    SELECT 'DEB-' || lpad(g::text, 6, '0'), first_name, last_name,
           pg_temp.pii(to_char(dob, 'YYYY-MM-DD')), pg_temp.pii(ssn),
           '+1' || area || '5550' || (100 + g / 10)::text,
           CASE WHEN g % 12 = 0 THEN NULL ELSE state END,      -- ~8% sin ubicación
           CASE WHEN g % 12 = 0 THEN NULL ELSE tz END,
           g % 40 = 0                                          -- ~2.5% no llamar
    FROM gen
    RETURNING id, external_id
)
INSERT INTO dev_mock_secrets (debtor_id, dob, ssn_last4)
SELECT ins.id, gen.dob, gen.ssn
FROM ins JOIN gen ON ins.external_id = 'DEB-' || lpad(gen.g::text, 6, '0');

-- 1 a 3 cuentas por deudor; ~75% en estados que atiende el agente
INSERT INTO accounts (external_id, debtor_id, creditor_name, account_number_masked,
                      original_amount_cents, nsf_amount_cents, nsf_fee_cents, current_balance_cents,
                      payment_method, status, nsf_date, nsf_return_code, is_disputed)
SELECT 'ACC-' || lpad(gen.g::text, 6, '0') || '-' || n,
       d.id,
       (ARRAY['Lakeside Auto Finance','Brightwater Utilities','Summit Health Partners',
              'Northgate Property Mgmt','Pinecrest Wireless'])[1 + (gen.g + n) % 5],
       '****' || lpad((random() * 9999)::int::text, 4, '0'),
       r.orig, r.orig, r.fee,
       CASE WHEN r.status = 'PAID' THEN 0 ELSE r.orig + r.fee END,
       (ARRAY['ACH','CHECK','CARD'])[1 + (gen.g + n) % 3],
       r.status,
       date '2026-10-28' - (random() * 90)::int,
       CASE WHEN random() < 0.85 THEN 'R01' ELSE 'R09' END,
       r.status = 'DISPUTED'
FROM gen
JOIN debtors d ON d.external_id = 'DEB-' || lpad(gen.g::text, 6, '0')
CROSS JOIN LATERAL generate_series(1, 1 + (gen.g % 3 = 0)::int + (gen.g % 7 = 0)::int) AS n
CROSS JOIN LATERAL (
    SELECT (5000 + random() * 145000)::bigint AS orig,
           (ARRAY[2500, 3000, 3500, 3900])[1 + (random() * 3)::int] AS fee,
           CASE
               WHEN x < 0.45 THEN 'NSF'
               WHEN x < 0.55 THEN 'first_attempt'
               WHEN x < 0.63 THEN 'second_attempt'
               WHEN x < 0.70 THEN 'third_attempt'
               WHEN x < 0.75 THEN 'fourth_attempt'
               WHEN x < 0.82 THEN 'PAYMENT_PLAN'
               WHEN x < 0.89 THEN 'PAID'
               WHEN x < 0.94 THEN 'DISPUTED'
               ELSE 'CLOSED'
           END AS status
    FROM (SELECT random() AS x, n AS dep) s   -- dep fuerza un valor aleatorio por fila
) AS r;
