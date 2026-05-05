-- =============================================================================
-- 01: Usuarios de prueba — 18 casos cubriendo todo el ciclo de vida
-- =============================================================================
-- Password: misma que usuario 'admin' existente
-- Prefijo test_ para aspirantes, M2x para estudiantes
-- =============================================================================

-- ── BLOQUE A: ASPIRANTES (role = applicant) ─────────────────────────────────
INSERT INTO "user" (first_name, last_name, mother_last_name, username, password, email,
                    is_internal, role_id, must_change_password, registration_date, last_login,
                    is_active, profile_completed, updated_at,
                    phone, address, curp, birth_date,
                    emergency_contact_name, emergency_contact_phone, emergency_contact_relationship,
                    photo_change_allowed)
SELECT
    v.first_name, v.last_name, v.mother_last_name, v.username,
    'scrypt:32768:8:1$ZshV34gGFmJl1s8G$a675f0c4117ce077f4b3320561c431b84726a615327cae96ec1e23e2ebc97e06b898b9a7d6faea1b055ede7bdaaed1f1086f4cb9c8b7482c5d9f22ca2dc88835',
    v.email, false,
    (SELECT id FROM role WHERE name = 'applicant' LIMIT 1),
    false, v.reg_date, v.reg_date, true, true, NOW(),
    '656' || (1000000 + ROW_NUMBER() OVER ())::text,
    'Calle Prueba ' || ROW_NUMBER() OVER (),
    'TEST' || LPAD((ROW_NUMBER() OVER ())::text, 2, '0') || '0101HJCXXX' || LPAD((ROW_NUMBER() OVER ())::text, 2, '0'),
    ('1993-01-01'::date + (ROW_NUMBER() OVER () * interval '73 days'))::date,
    'Contacto ' || v.last_name, '656' || (2000000 + ROW_NUMBER() OVER ())::text, 'Padre',
    false
FROM (VALUES
    -- A1: Aspirante recién registrado, sin documentos
    ('Laura',   'Soto',     'Mendez',  'test_a01_nuevo',      'test.a01@test.com', '2026-06-15'::timestamp),
    -- A2: Aspirante con documentos parciales (en proceso normal)
    ('Ana',     'Garcia',   'Lopez',   'test_a02_parcial',    'test.a02@test.com', '2026-06-01'::timestamp),
    -- A3: Aspirante con TODOS los docs aprobados, listo para entrevista
    ('Carlos',  'Martinez', 'Ruiz',    'test_a03_listo',      'test.a03@test.com', '2026-05-15'::timestamp),
    -- A4: Aspirante rechazado PARCIAL (un documento malo)
    ('Diana',   'Hernandez','Torres',  'test_a04_rech_parcial','test.a04@test.com','2026-05-20'::timestamp),
    -- A5: Aspirante rechazado TOTAL
    ('Eduardo', 'Flores',   'Luna',    'test_a05_rech_total', 'test.a05@test.com', '2026-05-10'::timestamp),
    -- A6: Aspirante con prorroga ACTIVA en un documento
    ('Fernanda','Lopez',    'Reyes',   'test_a06_prorroga',   'test.a06@test.com', '2026-05-10'::timestamp),
    -- A7: Aspirante con prorroga VENCIDA (nunca subio el doc)
    ('Gabriel', 'Perez',    'Diaz',    'test_a07_prorr_venc', 'test.a07@test.com', '2026-04-01'::timestamp),
    -- A8: Aspirante VIEJO sin terminar (periodo 20241, +2 periodos = debe expirar)
    ('Hugo',    'Ramirez',  'Sanchez', 'test_a08_viejo',      'test.a08@test.com', '2024-01-20'::timestamp),
    -- A9: Aspirante ACEPTADO con carta+tira, pendiente de pagar boleta
    ('Irene',   'Castillo', 'Vargas',  'test_a09_acept_nopaga','test.a09@test.com','2026-04-01'::timestamp),
    -- A10: Aspirante ACEPTADO que ya tiene todo listo para inscribirse
    ('Jorge',   'Morales',  'Gutierrez','test_a10_acept_listo','test.a10@test.com','2026-03-15'::timestamp),
    -- A11: Aspirante DIFERIDO 1 vez (aceptado, difiere al siguiente periodo)
    ('Karen',   'Navarro',  'Reyes',   'test_a11_diferido1',  'test.a11@test.com', '2025-09-01'::timestamp),
    -- A12: Aspirante con 2 DIFERIMIENTOS agotados (debe expirar si no se inscribe)
    ('Luis',    'Dominguez','Ortiz',   'test_a12_diferido2',  'test.a12@test.com', '2025-03-01'::timestamp),
    -- A13: Aspirante con doc de VIGENCIA VENCIDA (validity_months expirado)
    ('Monica',  'Rios',     'Campos',  'test_a13_doc_vencido','test.a13@test.com', '2025-01-10'::timestamp)
) AS v(first_name, last_name, mother_last_name, username, email, reg_date)
WHERE NOT EXISTS (SELECT 1 FROM "user" WHERE username = v.username);


-- ── BLOQUE B: ESTUDIANTES (role = student) ──────────────────────────────────
INSERT INTO "user" (first_name, last_name, mother_last_name, username, password, email,
                    is_internal, role_id, must_change_password, registration_date, last_login,
                    is_active, profile_completed, updated_at, control_number,
                    control_number_assigned_at,
                    phone, address, curp, birth_date,
                    emergency_contact_name, emergency_contact_phone, emergency_contact_relationship,
                    photo_change_allowed)
SELECT
    v.first_name, v.last_name, v.mother_last_name, v.ctrl,
    'scrypt:32768:8:1$ZshV34gGFmJl1s8G$a675f0c4117ce077f4b3320561c431b84726a615327cae96ec1e23e2ebc97e06b898b9a7d6faea1b055ede7bdaaed1f1086f4cb9c8b7482c5d9f22ca2dc88835',
    v.email, false,
    (SELECT id FROM role WHERE name = 'student' LIMIT 1),
    false, v.reg_date, v.reg_date, true, true, NOW(), v.ctrl, v.reg_date,
    '656' || (3000000 + ROW_NUMBER() OVER ())::text,
    'Av. Estudiante ' || ROW_NUMBER() OVER (),
    'ESTD' || LPAD((ROW_NUMBER() OVER ())::text, 2, '0') || '0101HJCXXX' || LPAD((ROW_NUMBER() OVER ())::text, 2, '0'),
    ('1992-06-01'::date + (ROW_NUMBER() OVER () * interval '97 days'))::date,
    'Familiar ' || v.last_name, '656' || (4000000 + ROW_NUMBER() OVER ())::text, 'Madre',
    false
FROM (VALUES
    -- B1: Estudiante AL DIA — semestre 4, todo aprobado, todo confirmado
    ('Nicolas', 'Torres',   'Avila',   'M24110001', 'test.b01@test.com', '2024-07-20'::timestamp),
    -- B2: Estudiante que DEBE docs de admision (inscrito pero le faltan docs)
    ('Olivia',  'Salazar',  'Pena',    'M24110002', 'test.b02@test.com', '2024-07-20'::timestamp),
    -- B3: Estudiante con docs de PERMANENCIA PENDIENTES
    ('Pablo',   'Cruz',     'Mejia',   'M25110001', 'test.b03@test.com', '2025-01-10'::timestamp),
    -- B4: Estudiante PENDIENTE DE PAGO (semestre actual sin confirmar)
    ('Raquel',  'Vega',     'Ibarra',  'M25110002', 'test.b04@test.com', '2025-01-10'::timestamp),
    -- B5: Estudiante con BAJA TEMPORAL (on_leave) un semestre
    ('Samuel',  'Luna',     'Espinoza','M25110003', 'test.b05@test.com', '2025-01-10'::timestamp)
) AS v(first_name, last_name, mother_last_name, ctrl, email, reg_date)
WHERE NOT EXISTS (SELECT 1 FROM "user" WHERE username = v.ctrl);
