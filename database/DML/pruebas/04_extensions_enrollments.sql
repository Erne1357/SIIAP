-- =============================================================================
-- 04: Prorrogas, diferimientos e inscripciones semestrales
-- =============================================================================


-- ═══════════════════════════════════════════════════════════════════════════════
-- EXTENSION REQUESTS (prorrogas)
-- ═══════════════════════════════════════════════════════════════════════════════

-- ── A6: Prorroga ACTIVA (granted, expira en 30 dias) ────────────────────────
INSERT INTO extension_request (user_id, archive_id, program_step_id,
                               requested_by, role, reason, requested_until,
                               status, granted_until, decided_by, decided_at,
                               created_at, updated_at)
SELECT u.id, sub.aid, sub.psid,
       u.id, 'student',
       'Necesito mas tiempo para obtener el comprobante de ingles del centro de lenguas',
       NOW() + interval '30 days',
       'granted',
       NOW() + interval '30 days',
       (SELECT id FROM "user" WHERE username = 'admin'),
       NOW() - interval '5 days',
       NOW() - interval '5 days', NOW()
FROM "user" u
CROSS JOIN LATERAL (
    SELECT a.id AS aid, ps.id AS psid
    FROM archive a
    JOIN step s ON a.step_id = s.id JOIN phase ph ON s.phase_id = ph.id
    JOIN program_step ps ON ps.step_id = s.id
         AND ps.program_id = (SELECT program_id FROM user_program WHERE user_id = u.id LIMIT 1)
    WHERE ph.name = 'admission' AND a.is_uploadable = true
    ORDER BY a.id OFFSET 6 LIMIT 1  -- 7mo archivo = el que tiene is_in_extension
) sub
WHERE u.username = 'test_a06_prorroga'
AND NOT EXISTS (SELECT 1 FROM extension_request er WHERE er.user_id = u.id AND er.archive_id = sub.aid AND er.status = 'granted');


-- ── A7: Prorroga VENCIDA (granted pero granted_until ya paso) ──────────────
INSERT INTO extension_request (user_id, archive_id, program_step_id,
                               requested_by, role, reason, requested_until,
                               status, granted_until, decided_by, decided_at,
                               created_at, updated_at)
SELECT u.id, sub.aid, sub.psid,
       u.id, 'student',
       'Solicito prorroga para el certificado de licenciatura',
       NOW() - interval '10 days',
       'granted',
       NOW() - interval '10 days',  -- YA VENCIDA
       (SELECT id FROM "user" WHERE username = 'admin'),
       NOW() - interval '40 days',
       NOW() - interval '45 days', NOW()
FROM "user" u
CROSS JOIN LATERAL (
    SELECT a.id AS aid, ps.id AS psid
    FROM archive a
    JOIN step s ON a.step_id = s.id JOIN phase ph ON s.phase_id = ph.id
    JOIN program_step ps ON ps.step_id = s.id
         AND ps.program_id = (SELECT program_id FROM user_program WHERE user_id = u.id LIMIT 1)
    WHERE ph.name = 'admission' AND a.is_uploadable = true
    ORDER BY a.id OFFSET 5 LIMIT 1  -- 6to archivo = el que tiene prorroga vencida
) sub
WHERE u.username = 'test_a07_prorr_venc'
AND NOT EXISTS (SELECT 1 FROM extension_request er WHERE er.user_id = u.id AND er.archive_id = sub.aid);


-- ═══════════════════════════════════════════════════════════════════════════════
-- ENROLLMENT DEFERRALS (diferimientos de inscripcion)
-- ═══════════════════════════════════════════════════════════════════════════════

-- ── A11: Diferido 1 vez (aceptado en 20253, difiere a 20261, activo) ────────
INSERT INTO enrollment_deferral (user_program_id, original_period_id, deferred_to_period_id,
                                  deferral_number, status, requested_by,
                                  reason, reviewed_by_id, reviewed_at, created_at)
SELECT up.id,
       (SELECT id FROM academic_period WHERE code = '20253'),
       (SELECT id FROM academic_period WHERE code = '20261'),
       1, 'active', 'coordinator',
       'Motivos laborales, solicita diferir al siguiente periodo',
       (SELECT id FROM "user" WHERE username = 'admin'),
       '2025-11-20'::timestamp,
       '2025-11-15'::timestamp
FROM user_program up JOIN "user" u ON up.user_id = u.id
WHERE u.username = 'test_a11_diferido1'
AND NOT EXISTS (SELECT 1 FROM enrollment_deferral ed WHERE ed.user_program_id = up.id AND ed.deferral_number = 1);


-- ── A12: 2 diferimientos — 1ro usado, 2do activo ───────────────────────────
-- Diferimiento 1: aceptado en 20251, diferido a 20253, USADO (se reactivo)
INSERT INTO enrollment_deferral (user_program_id, original_period_id, deferred_to_period_id,
                                  deferral_number, status, requested_by,
                                  reason, reviewed_by_id, reviewed_at, created_at)
SELECT up.id,
       (SELECT id FROM academic_period WHERE code = '20251'),
       (SELECT id FROM academic_period WHERE code = '20253'),
       1, 'used', 'applicant',
       'Situacion economica no permite inscribirse este semestre',
       (SELECT id FROM "user" WHERE username = 'admin'),
       '2025-06-01'::timestamp,
       '2025-05-15'::timestamp
FROM user_program up JOIN "user" u ON up.user_id = u.id
WHERE u.username = 'test_a12_diferido2'
AND NOT EXISTS (SELECT 1 FROM enrollment_deferral ed WHERE ed.user_program_id = up.id AND ed.deferral_number = 1);

-- Diferimiento 2: diferido de nuevo de 20253 a 20261, activo
INSERT INTO enrollment_deferral (user_program_id, original_period_id, deferred_to_period_id,
                                  deferral_number, status, requested_by,
                                  reason, reviewed_by_id, reviewed_at, created_at)
SELECT up.id,
       (SELECT id FROM academic_period WHERE code = '20253'),
       (SELECT id FROM academic_period WHERE code = '20263'),
       2, 'active', 'applicant',
       'Continua sin poder inscribirse por temas personales',
       (SELECT id FROM "user" WHERE username = 'admin'),
       '2025-12-01'::timestamp,
       '2025-11-20'::timestamp
FROM user_program up JOIN "user" u ON up.user_id = u.id
WHERE u.username = 'test_a12_diferido2'
AND NOT EXISTS (SELECT 1 FROM enrollment_deferral ed WHERE ed.user_program_id = up.id AND ed.deferral_number = 2);


-- ═══════════════════════════════════════════════════════════════════════════════
-- SEMESTER ENROLLMENTS (inscripciones semestrales para estudiantes)
-- ═══════════════════════════════════════════════════════════════════════════════

-- ── B1: AL DIA — 4 semestres (3 completados + 1 activo confirmado) ─────────
INSERT INTO semester_enrollment (user_program_id, academic_period_id, semester_number,
                                  status, enrollment_confirmed, confirmed_by, confirmed_at,
                                  created_at, updated_at)
SELECT up.id, (SELECT id FROM academic_period WHERE code = v.code),
       v.sem, v.st, true,
       (SELECT id FROM "user" WHERE username = 'admin'),
       v.conf::timestamp, v.conf::timestamp, NOW()
FROM user_program up JOIN "user" u ON up.user_id = u.id
CROSS JOIN (VALUES
    ('20243', 1, 'completed', '2024-08-15'),
    ('20251', 2, 'completed', '2025-01-20'),
    ('20253', 3, 'completed', '2025-08-18'),
    ('20263', 4, 'active',    '2026-08-15')
) AS v(code, sem, st, conf)
WHERE u.username = 'M24110001'
AND NOT EXISTS (SELECT 1 FROM semester_enrollment se WHERE se.user_program_id = up.id AND se.semester_number = v.sem);


-- ── B2: DEBE DOCS ADMISION — 3 semestres (2 completados + 1 activo) ────────
INSERT INTO semester_enrollment (user_program_id, academic_period_id, semester_number,
                                  status, enrollment_confirmed, confirmed_by, confirmed_at,
                                  created_at, updated_at)
SELECT up.id, (SELECT id FROM academic_period WHERE code = v.code),
       v.sem, v.st, true,
       (SELECT id FROM "user" WHERE username = 'admin'),
       v.conf::timestamp, v.conf::timestamp, NOW()
FROM user_program up JOIN "user" u ON up.user_id = u.id
CROSS JOIN (VALUES
    ('20243', 1, 'completed', '2024-08-15'),
    ('20253', 2, 'completed', '2025-08-18'),
    ('20263', 3, 'active',    '2026-08-15')
) AS v(code, sem, st, conf)
WHERE u.username = 'M24110002'
AND NOT EXISTS (SELECT 1 FROM semester_enrollment se WHERE se.user_program_id = up.id AND se.semester_number = v.sem);


-- ── B3: PERMANENCIA PENDIENTE — 2 semestres (1 completado + 1 activo) ──────
INSERT INTO semester_enrollment (user_program_id, academic_period_id, semester_number,
                                  status, enrollment_confirmed, confirmed_by, confirmed_at,
                                  created_at, updated_at)
SELECT up.id, (SELECT id FROM academic_period WHERE code = v.code),
       v.sem, v.st, true,
       (SELECT id FROM "user" WHERE username = 'admin'),
       v.conf::timestamp, v.conf::timestamp, NOW()
FROM user_program up JOIN "user" u ON up.user_id = u.id
CROSS JOIN (VALUES
    ('20253', 1, 'completed', '2025-08-18'),
    ('20263', 2, 'active',    '2026-08-15')
) AS v(code, sem, st, conf)
WHERE u.username = 'M25110001'
AND NOT EXISTS (SELECT 1 FROM semester_enrollment se WHERE se.user_program_id = up.id AND se.semester_number = v.sem);


-- ── B4: PENDIENTE PAGO — sem 1 completado, sem 2 pendiente SIN confirmar ───
INSERT INTO semester_enrollment (user_program_id, academic_period_id, semester_number,
                                  status, enrollment_confirmed, confirmed_by, confirmed_at,
                                  created_at, updated_at)
SELECT up.id, (SELECT id FROM academic_period WHERE code = '20253'),
       1, 'completed', true,
       (SELECT id FROM "user" WHERE username = 'admin'),
       '2025-08-18'::timestamp, '2025-08-18'::timestamp, NOW()
FROM user_program up JOIN "user" u ON up.user_id = u.id
WHERE u.username = 'M25110002'
AND NOT EXISTS (SELECT 1 FROM semester_enrollment se WHERE se.user_program_id = up.id AND se.semester_number = 1);

-- Semestre 2: existe pero NO confirmado (pendiente de pago)
INSERT INTO semester_enrollment (user_program_id, academic_period_id, semester_number,
                                  status, enrollment_confirmed,
                                  created_at, updated_at)
SELECT up.id, (SELECT id FROM academic_period WHERE code = '20263'),
       2, 'pending', false,
       NOW(), NOW()
FROM user_program up JOIN "user" u ON up.user_id = u.id
WHERE u.username = 'M25110002'
AND NOT EXISTS (SELECT 1 FROM semester_enrollment se WHERE se.user_program_id = up.id AND se.semester_number = 2);


-- ── B5: BAJA TEMPORAL — sem 1 completado, sem 2 on_leave ───────────────────
INSERT INTO semester_enrollment (user_program_id, academic_period_id, semester_number,
                                  status, enrollment_confirmed, confirmed_by, confirmed_at,
                                  created_at, updated_at)
SELECT up.id, (SELECT id FROM academic_period WHERE code = '20253'),
       1, 'completed', true,
       (SELECT id FROM "user" WHERE username = 'admin'),
       '2025-08-18'::timestamp, '2025-08-18'::timestamp, NOW()
FROM user_program up JOIN "user" u ON up.user_id = u.id
WHERE u.username = 'M25110003'
AND NOT EXISTS (SELECT 1 FROM semester_enrollment se WHERE se.user_program_id = up.id AND se.semester_number = 1);

-- Semestre 2: on_leave (baja temporal autorizada)
INSERT INTO semester_enrollment (user_program_id, academic_period_id, semester_number,
                                  status, enrollment_confirmed, confirmed_by, confirmed_at,
                                  notes, created_at, updated_at)
SELECT up.id, (SELECT id FROM academic_period WHERE code = '20263'),
       2, 'on_leave', true,
       (SELECT id FROM "user" WHERE username = 'admin'),
       '2026-08-20'::timestamp,
       'Baja temporal autorizada por motivos de salud. Puede reincorporarse en 20271.',
       '2026-08-20'::timestamp, NOW()
FROM user_program up JOIN "user" u ON up.user_id = u.id
WHERE u.username = 'M25110003'
AND NOT EXISTS (SELECT 1 FROM semester_enrollment se WHERE se.user_program_id = up.id AND se.semester_number = 2);
