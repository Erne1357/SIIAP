-- =============================================================================
-- 02: user_program — vincula cada usuario con un programa y estado
-- =============================================================================
-- Usamos el primer programa con steps de admision (MII) como programa base.
-- Para variedad, algunos van a MANI o DCI.
-- =============================================================================

-- Variable helper: programa MII
-- (SELECT id FROM program WHERE slug = 'MII')

-- ── A1: Aspirante nuevo, sin docs, periodo actual ───────────────────────────
INSERT INTO user_program (user_id, program_id, enrollment_date, current_semester,
                          admission_period_id, admission_status, updated_at)
SELECT u.id, (SELECT id FROM program WHERE slug = 'MII'),
       u.registration_date, NULL,
       (SELECT id FROM academic_period WHERE code = '20263'),
       'in_progress', NOW()
FROM "user" u WHERE u.username = 'test_a01_nuevo'
AND NOT EXISTS (SELECT 1 FROM user_program WHERE user_id = u.id);

-- ── A2: Aspirante con docs parciales, periodo actual ────────────────────────
INSERT INTO user_program (user_id, program_id, enrollment_date, current_semester,
                          admission_period_id, admission_status, updated_at)
SELECT u.id, (SELECT id FROM program WHERE slug = 'MII'),
       u.registration_date, NULL,
       (SELECT id FROM academic_period WHERE code = '20263'),
       'in_progress', NOW()
FROM "user" u WHERE u.username = 'test_a02_parcial'
AND NOT EXISTS (SELECT 1 FROM user_program WHERE user_id = u.id);

-- ── A3: Aspirante listo para entrevista (todos docs aprobados) ──────────────
INSERT INTO user_program (user_id, program_id, enrollment_date, current_semester,
                          admission_period_id, admission_status, updated_at)
SELECT u.id, (SELECT id FROM program WHERE slug = 'MII'),
       u.registration_date, NULL,
       (SELECT id FROM academic_period WHERE code = '20263'),
       'in_progress', NOW()
FROM "user" u WHERE u.username = 'test_a03_listo'
AND NOT EXISTS (SELECT 1 FROM user_program WHERE user_id = u.id);

-- ── A4: Rechazado parcial (1 doc) ──────────────────────────────────────────
INSERT INTO user_program (user_id, program_id, enrollment_date, current_semester,
                          admission_period_id, admission_status,
                          rejection_type, decision_notes, correction_required,
                          decision_at, decision_by, deliberation_started_at, updated_at)
SELECT u.id, (SELECT id FROM program WHERE slug = 'MII'),
       u.registration_date, NULL,
       (SELECT id FROM academic_period WHERE code = '20263'),
       'rejected', 'partial',
       'El titulo tiene errores, favor de resubir',
       -- correction_required con JSON del primer archive uploadable de admision
       (SELECT '{"archive_id": ' || a.id || ', "archive_name": "' || a.name || '", "notes": "El titulo tiene errores en el nombre, resubir corregido"}'
        FROM archive a JOIN step s ON a.step_id = s.id JOIN phase ph ON s.phase_id = ph.id
        WHERE ph.name = 'admission' AND a.is_uploadable = true
        ORDER BY a.id OFFSET 2 LIMIT 1),  -- 3er archivo (Titulo)
       NOW() - interval '3 days',
       (SELECT id FROM "user" WHERE username = 'admin'),
       NOW() - interval '5 days',
       NOW()
FROM "user" u WHERE u.username = 'test_a04_rech_parcial'
AND NOT EXISTS (SELECT 1 FROM user_program WHERE user_id = u.id);

-- ── A5: Rechazado total ────────────────────────────────────────────────────
INSERT INTO user_program (user_id, program_id, enrollment_date, current_semester,
                          admission_period_id, admission_status,
                          rejection_type, decision_notes,
                          decision_at, decision_by, deliberation_started_at, updated_at)
SELECT u.id, (SELECT id FROM program WHERE slug = 'MANI'),
       u.registration_date, NULL,
       (SELECT id FROM academic_period WHERE code = '20263'),
       'rejected', 'full',
       'No cumple con el perfil requerido para el programa',
       NOW() - interval '2 days',
       (SELECT id FROM "user" WHERE username = 'admin'),
       NOW() - interval '4 days',
       NOW()
FROM "user" u WHERE u.username = 'test_a05_rech_total'
AND NOT EXISTS (SELECT 1 FROM user_program WHERE user_id = u.id);

-- ── A6: Aspirante con prorroga ACTIVA ──────────────────────────────────────
INSERT INTO user_program (user_id, program_id, enrollment_date, current_semester,
                          admission_period_id, admission_status, updated_at)
SELECT u.id, (SELECT id FROM program WHERE slug = 'MII'),
       u.registration_date, NULL,
       (SELECT id FROM academic_period WHERE code = '20263'),
       'in_progress', NOW()
FROM "user" u WHERE u.username = 'test_a06_prorroga'
AND NOT EXISTS (SELECT 1 FROM user_program WHERE user_id = u.id);

-- ── A7: Aspirante con prorroga VENCIDA (deuda documental) ──────────────────
INSERT INTO user_program (user_id, program_id, enrollment_date, current_semester,
                          admission_period_id, admission_status, updated_at)
SELECT u.id, (SELECT id FROM program WHERE slug = 'MII'),
       u.registration_date, NULL,
       (SELECT id FROM academic_period WHERE code = '20263'),
       'in_progress', NOW()
FROM "user" u WHERE u.username = 'test_a07_prorr_venc'
AND NOT EXISTS (SELECT 1 FROM user_program WHERE user_id = u.id);

-- ── A8: Aspirante VIEJO (periodo 20241 = hace +4 periodos, debe expirar) ───
INSERT INTO user_program (user_id, program_id, enrollment_date, current_semester,
                          admission_period_id, admission_status, updated_at)
SELECT u.id, (SELECT id FROM program WHERE slug = 'DCI'),
       u.registration_date, NULL,
       (SELECT id FROM academic_period WHERE code = '20241'),
       'in_progress', '2024-01-20'::timestamp
FROM "user" u WHERE u.username = 'test_a08_viejo'
AND NOT EXISTS (SELECT 1 FROM user_program WHERE user_id = u.id);

-- ── A9: Aceptado que NO PAGA boleta (tiene carta+tira pero no sube recibo) ─
INSERT INTO user_program (user_id, program_id, enrollment_date, current_semester,
                          admission_period_id, admission_status,
                          decision_at, decision_by, decision_notes, updated_at)
SELECT u.id, (SELECT id FROM program WHERE slug = 'MII'),
       u.registration_date, NULL,
       (SELECT id FROM academic_period WHERE code = '20263'),
       'accepted',
       NOW() - interval '20 days',
       (SELECT id FROM "user" WHERE username = 'admin'),
       'Aspirante cumple todos los requisitos',
       NOW()
FROM "user" u WHERE u.username = 'test_a09_acept_nopaga'
AND NOT EXISTS (SELECT 1 FROM user_program WHERE user_id = u.id);

-- ── A10: Aceptado LISTO para inscribirse (boleta aprobada, falta asignar ctrl) ─
INSERT INTO user_program (user_id, program_id, enrollment_date, current_semester,
                          admission_period_id, admission_status,
                          decision_at, decision_by, decision_notes, updated_at)
SELECT u.id, (SELECT id FROM program WHERE slug = 'MII'),
       u.registration_date, NULL,
       (SELECT id FROM academic_period WHERE code = '20263'),
       'accepted',
       NOW() - interval '25 days',
       (SELECT id FROM "user" WHERE username = 'admin'),
       'Excelente perfil academico',
       NOW()
FROM "user" u WHERE u.username = 'test_a10_acept_listo'
AND NOT EXISTS (SELECT 1 FROM user_program WHERE user_id = u.id);

-- ── A11: DIFERIDO 1 vez (aceptado en 20253, difiere a 20261) ───────────────
INSERT INTO user_program (user_id, program_id, enrollment_date, current_semester,
                          admission_period_id, admission_status,
                          decision_at, decision_by, decision_notes, updated_at)
SELECT u.id, (SELECT id FROM program WHERE slug = 'MII'),
       u.registration_date, NULL,
       (SELECT id FROM academic_period WHERE code = '20261'),
       'deferred',
       '2025-11-15'::timestamp,
       (SELECT id FROM "user" WHERE username = 'admin'),
       'Aceptada, pero solicita diferimiento por motivos laborales',
       NOW()
FROM "user" u WHERE u.username = 'test_a11_diferido1'
AND NOT EXISTS (SELECT 1 FROM user_program WHERE user_id = u.id);

-- ── A12: 2 DIFERIMIENTOS agotados (aceptado en 20251, diferido 2 veces) ────
INSERT INTO user_program (user_id, program_id, enrollment_date, current_semester,
                          admission_period_id, admission_status,
                          decision_at, decision_by, decision_notes, updated_at)
SELECT u.id, (SELECT id FROM program WHERE slug = 'MANI'),
       u.registration_date, NULL,
       (SELECT id FROM academic_period WHERE code = '20263'),
       'deferred',
       '2025-05-01'::timestamp,
       (SELECT id FROM "user" WHERE username = 'admin'),
       'Aceptado, segundo diferimiento',
       NOW()
FROM "user" u WHERE u.username = 'test_a12_diferido2'
AND NOT EXISTS (SELECT 1 FROM user_program WHERE user_id = u.id);

-- ── A13: Aspirante con doc de VIGENCIA VENCIDA ─────────────────────────────
-- Aplico en 20251, certificado aprobado pero ya expiro (validity_months)
INSERT INTO user_program (user_id, program_id, enrollment_date, current_semester,
                          admission_period_id, admission_status, updated_at)
SELECT u.id, (SELECT id FROM program WHERE slug = 'MII'),
       u.registration_date, NULL,
       (SELECT id FROM academic_period WHERE code = '20251'),
       'in_progress', NOW()
FROM "user" u WHERE u.username = 'test_a13_doc_vencido'
AND NOT EXISTS (SELECT 1 FROM user_program WHERE user_id = u.id);


-- ── B1: Estudiante AL DIA (enrolled, semestre 4, desde 20243, becario CONACyT)
INSERT INTO user_program (user_id, program_id, enrollment_date, current_semester,
                          admission_period_id, admission_status, has_conacyt_scholarship, updated_at)
SELECT u.id, (SELECT id FROM program WHERE slug = 'MII'),
       u.registration_date, 4,
       (SELECT id FROM academic_period WHERE code = '20243'),
       'enrolled', true, NOW()
FROM "user" u WHERE u.username = 'M24110001'
AND NOT EXISTS (SELECT 1 FROM user_program WHERE user_id = u.id);

-- ── B2: Estudiante que DEBE docs admision (enrolled, semestre 3, becario CONACyT)
INSERT INTO user_program (user_id, program_id, enrollment_date, current_semester,
                          admission_period_id, admission_status, has_conacyt_scholarship, updated_at)
SELECT u.id, (SELECT id FROM program WHERE slug = 'MII'),
       u.registration_date, 3,
       (SELECT id FROM academic_period WHERE code = '20243'),
       'enrolled', true, NOW()
FROM "user" u WHERE u.username = 'M24110002'
AND NOT EXISTS (SELECT 1 FROM user_program WHERE user_id = u.id);

-- ── B3: Estudiante con docs PERMANENCIA pendientes (enrolled, semestre 2) ──
INSERT INTO user_program (user_id, program_id, enrollment_date, current_semester,
                          admission_period_id, admission_status, updated_at)
SELECT u.id, (SELECT id FROM program WHERE slug = 'MII'),
       u.registration_date, 2,
       (SELECT id FROM academic_period WHERE code = '20253'),
       'enrolled', NOW()
FROM "user" u WHERE u.username = 'M25110001'
AND NOT EXISTS (SELECT 1 FROM user_program WHERE user_id = u.id);

-- ── B4: Estudiante PENDIENTE DE PAGO (enrolled, semestre 2, no confirmado) ─
INSERT INTO user_program (user_id, program_id, enrollment_date, current_semester,
                          admission_period_id, admission_status, updated_at)
SELECT u.id, (SELECT id FROM program WHERE slug = 'MII'),
       u.registration_date, 2,
       (SELECT id FROM academic_period WHERE code = '20253'),
       'enrolled', NOW()
FROM "user" u WHERE u.username = 'M25110002'
AND NOT EXISTS (SELECT 1 FROM user_program WHERE user_id = u.id);

-- ── B5: Estudiante con BAJA TEMPORAL (enrolled, semestre 2) ────────────────
INSERT INTO user_program (user_id, program_id, enrollment_date, current_semester,
                          admission_period_id, admission_status, updated_at)
SELECT u.id, (SELECT id FROM program WHERE slug = 'MANI'),
       u.registration_date, 2,
       (SELECT id FROM academic_period WHERE code = '20253'),
       'enrolled', NOW()
FROM "user" u WHERE u.username = 'M25110003'
AND NOT EXISTS (SELECT 1 FROM user_program WHERE user_id = u.id);
