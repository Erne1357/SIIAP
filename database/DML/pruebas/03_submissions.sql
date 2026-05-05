-- =============================================================================
-- 03: Submissions para cada caso de prueba
-- =============================================================================
-- Estructura de archives de admision para MII (steps 1,2,3):
--   step 1 (Docs Generales):  CV, Cartas Recomendacion, EXANI III, Solicitud
--   step 2 (Req Maestrias):   Comprobante Ingles, Certificado Lic, Titulo
--   step 3 (Especificos MII): Examen Conocimientos
-- Total uploadables MII: 8 archivos
--
-- Para MANI (steps 1,2,4): mismos generales + step 4 en vez de 3
-- Para DCI  (steps 1,2,5): mismos generales + step 5 (5 archivos)
-- =============================================================================


-- ── A1: NUEVO — sin submissions (no se inserta nada) ────────────────────────
-- (intencionalmente vacio)


-- ── A2: PARCIAL — 3 de 8 docs: 1 aprobado, 1 en revision, 1 rechazado ─────
INSERT INTO submission (file_path, status, user_id, archive_id, program_step_id,
                        semester, upload_date, review_date, reviewer_comment, is_in_extension, updated_at)
SELECT
    'documents/' || u.id || '/admission/doc_' || sub.aid || '.pdf',
    sub.st,
    u.id, sub.aid, sub.psid, NULL,
    NOW() - interval '5 days',
    CASE WHEN sub.st != 'review' THEN NOW() - interval '3 days' ELSE NULL END,
    CASE WHEN sub.st = 'rejected' THEN 'Documento ilegible, resubir en mejor calidad' ELSE NULL END,
    false,
    NOW()
FROM "user" u
CROSS JOIN LATERAL (
    SELECT a.id AS aid, ps.id AS psid,
           CASE ROW_NUMBER() OVER (ORDER BY a.id)
               WHEN 1 THEN 'approved'
               WHEN 2 THEN 'review'
               WHEN 3 THEN 'rejected'
           END AS st
    FROM archive a
    JOIN step s ON a.step_id = s.id JOIN phase ph ON s.phase_id = ph.id
    JOIN program_step ps ON ps.step_id = s.id
         AND ps.program_id = (SELECT program_id FROM user_program WHERE user_id = u.id LIMIT 1)
    WHERE ph.name = 'admission' AND a.is_uploadable = true
    ORDER BY a.id LIMIT 3
) sub
WHERE u.username = 'test_a02_parcial'
AND NOT EXISTS (SELECT 1 FROM submission s2 WHERE s2.user_id = u.id AND s2.archive_id = sub.aid);


-- ── A3: LISTO — TODOS los 8 docs aprobados ─────────────────────────────────
INSERT INTO submission (file_path, status, user_id, archive_id, program_step_id,
                        semester, upload_date, review_date, is_in_extension, updated_at)
SELECT
    'documents/' || u.id || '/admission/doc_' || a.id || '.pdf',
    'approved', u.id, a.id, ps.id, NULL,
    NOW() - interval '15 days', NOW() - interval '10 days', false, NOW()
FROM "user" u
JOIN user_program up ON up.user_id = u.id
JOIN program_step ps ON ps.program_id = up.program_id
JOIN step s ON ps.step_id = s.id JOIN phase ph ON s.phase_id = ph.id
JOIN archive a ON a.step_id = s.id
WHERE u.username = 'test_a03_listo' AND ph.name = 'admission' AND a.is_uploadable = true
AND NOT EXISTS (SELECT 1 FROM submission s2 WHERE s2.user_id = u.id AND s2.archive_id = a.id);


-- ── A4: RECHAZADO PARCIAL — todos aprobados EXCEPTO el 3ro (Titulo) rechazado
INSERT INTO submission (file_path, status, user_id, archive_id, program_step_id,
                        semester, upload_date, review_date, reviewer_comment, is_in_extension, updated_at)
SELECT
    'documents/' || u.id || '/admission/doc_' || sub.aid || '.pdf',
    sub.st, u.id, sub.aid, sub.psid, NULL,
    NOW() - interval '20 days', NOW() - interval '15 days',
    CASE WHEN sub.rn = 3 THEN 'El titulo tiene errores en el nombre, resubir corregido' ELSE NULL END,
    false,
    NOW()
FROM "user" u
CROSS JOIN LATERAL (
    SELECT a.id AS aid, ps.id AS psid, ROW_NUMBER() OVER (ORDER BY a.id) AS rn,
           CASE WHEN ROW_NUMBER() OVER (ORDER BY a.id) = 3 THEN 'rejected' ELSE 'approved' END AS st
    FROM archive a
    JOIN step s ON a.step_id = s.id JOIN phase ph ON s.phase_id = ph.id
    JOIN program_step ps ON ps.step_id = s.id
         AND ps.program_id = (SELECT program_id FROM user_program WHERE user_id = u.id LIMIT 1)
    WHERE ph.name = 'admission' AND a.is_uploadable = true
    ORDER BY a.id
) sub
WHERE u.username = 'test_a04_rech_parcial'
AND NOT EXISTS (SELECT 1 FROM submission s2 WHERE s2.user_id = u.id AND s2.archive_id = sub.aid);


-- ── A5: RECHAZADO TOTAL — todos aprobados (rechazo fue por entrevista, no docs)
INSERT INTO submission (file_path, status, user_id, archive_id, program_step_id,
                        semester, upload_date, review_date, is_in_extension, updated_at)
SELECT
    'documents/' || u.id || '/admission/doc_' || a.id || '.pdf',
    'approved', u.id, a.id, ps.id, NULL,
    NOW() - interval '20 days', NOW() - interval '15 days', false, NOW()
FROM "user" u
JOIN user_program up ON up.user_id = u.id
JOIN program_step ps ON ps.program_id = up.program_id
JOIN step s ON ps.step_id = s.id JOIN phase ph ON s.phase_id = ph.id
JOIN archive a ON a.step_id = s.id
WHERE u.username = 'test_a05_rech_total' AND ph.name = 'admission' AND a.is_uploadable = true
AND NOT EXISTS (SELECT 1 FROM submission s2 WHERE s2.user_id = u.id AND s2.archive_id = a.id);


-- ── A6: PRORROGA ACTIVA — 6 de 8 aprobados, 1 en extension, 1 sin subir ───
INSERT INTO submission (file_path, status, user_id, archive_id, program_step_id,
                        semester, upload_date, review_date, is_in_extension, updated_at)
SELECT
    'documents/' || u.id || '/admission/doc_' || sub.aid || '.pdf',
    sub.st, u.id, sub.aid, sub.psid, NULL,
    NOW() - interval '10 days',
    CASE WHEN sub.st = 'approved' THEN NOW() - interval '7 days' ELSE NULL END,
    sub.ext,
    NOW()
FROM "user" u
CROSS JOIN LATERAL (
    SELECT a.id AS aid, ps.id AS psid, ROW_NUMBER() OVER (ORDER BY a.id) AS rn,
           CASE
               WHEN ROW_NUMBER() OVER (ORDER BY a.id) <= 6 THEN 'approved'
               WHEN ROW_NUMBER() OVER (ORDER BY a.id) = 7 THEN 'review'  -- este tendra extension
               ELSE 'does_not_insert'
           END AS st,
           CASE WHEN ROW_NUMBER() OVER (ORDER BY a.id) = 7 THEN true ELSE false END AS ext
    FROM archive a
    JOIN step s ON a.step_id = s.id JOIN phase ph ON s.phase_id = ph.id
    JOIN program_step ps ON ps.step_id = s.id
         AND ps.program_id = (SELECT program_id FROM user_program WHERE user_id = u.id LIMIT 1)
    WHERE ph.name = 'admission' AND a.is_uploadable = true
    ORDER BY a.id
) sub
WHERE u.username = 'test_a06_prorroga' AND sub.st != 'does_not_insert'
AND NOT EXISTS (SELECT 1 FROM submission s2 WHERE s2.user_id = u.id AND s2.archive_id = sub.aid);


-- ── A7: PRORROGA VENCIDA — 5 aprobados, 1 con prorroga ya expirada, 2 sin subir
INSERT INTO submission (file_path, status, user_id, archive_id, program_step_id,
                        semester, upload_date, review_date, is_in_extension, updated_at)
SELECT
    'documents/' || u.id || '/admission/doc_' || sub.aid || '.pdf',
    sub.st, u.id, sub.aid, sub.psid, NULL,
    NOW() - interval '60 days',
    CASE WHEN sub.st = 'approved' THEN NOW() - interval '55 days' ELSE NULL END,
    sub.ext,
    NOW()
FROM "user" u
CROSS JOIN LATERAL (
    SELECT a.id AS aid, ps.id AS psid, ROW_NUMBER() OVER (ORDER BY a.id) AS rn,
           CASE
               WHEN ROW_NUMBER() OVER (ORDER BY a.id) <= 5 THEN 'approved'
               WHEN ROW_NUMBER() OVER (ORDER BY a.id) = 6 THEN 'review'  -- este tiene prorroga vencida
               ELSE 'skip'
           END AS st,
           CASE WHEN ROW_NUMBER() OVER (ORDER BY a.id) = 6 THEN true ELSE false END AS ext
    FROM archive a
    JOIN step s ON a.step_id = s.id JOIN phase ph ON s.phase_id = ph.id
    JOIN program_step ps ON ps.step_id = s.id
         AND ps.program_id = (SELECT program_id FROM user_program WHERE user_id = u.id LIMIT 1)
    WHERE ph.name = 'admission' AND a.is_uploadable = true
    ORDER BY a.id
) sub
WHERE u.username = 'test_a07_prorr_venc' AND sub.st != 'skip'
AND NOT EXISTS (SELECT 1 FROM submission s2 WHERE s2.user_id = u.id AND s2.archive_id = sub.aid);


-- ── A8: VIEJO — 3 docs subidos hace mucho (review), resto sin subir ────────
INSERT INTO submission (file_path, status, user_id, archive_id, program_step_id,
                        semester, upload_date, is_in_extension, updated_at)
SELECT
    'documents/' || u.id || '/admission/doc_' || sub.aid || '.pdf',
    'review', u.id, sub.aid, sub.psid, NULL,
    '2024-01-25'::timestamp, false, '2024-01-25'::timestamp
FROM "user" u
CROSS JOIN LATERAL (
    SELECT a.id AS aid, ps.id AS psid
    FROM archive a
    JOIN step s ON a.step_id = s.id JOIN phase ph ON s.phase_id = ph.id
    JOIN program_step ps ON ps.step_id = s.id
         AND ps.program_id = (SELECT program_id FROM user_program WHERE user_id = u.id LIMIT 1)
    WHERE ph.name = 'admission' AND a.is_uploadable = true
    ORDER BY a.id LIMIT 3
) sub
WHERE u.username = 'test_a08_viejo'
AND NOT EXISTS (SELECT 1 FROM submission s2 WHERE s2.user_id = u.id AND s2.archive_id = sub.aid);


-- ── A9: ACEPTADO NO PAGA — todos docs admision aprobados ───────────────────
INSERT INTO submission (file_path, status, user_id, archive_id, program_step_id,
                        semester, upload_date, review_date, is_in_extension, updated_at)
SELECT
    'documents/' || u.id || '/admission/doc_' || a.id || '.pdf',
    'approved', u.id, a.id, ps.id, NULL,
    NOW() - interval '30 days', NOW() - interval '25 days', false, NOW()
FROM "user" u
JOIN user_program up ON up.user_id = u.id
JOIN program_step ps ON ps.program_id = up.program_id
JOIN step s ON ps.step_id = s.id JOIN phase ph ON s.phase_id = ph.id
JOIN archive a ON a.step_id = s.id
WHERE u.username = 'test_a09_acept_nopaga' AND ph.name = 'admission' AND a.is_uploadable = true
AND NOT EXISTS (SELECT 1 FROM submission s2 WHERE s2.user_id = u.id AND s2.archive_id = a.id);


-- ── A10: ACEPTADO LISTO — todos docs admision aprobados ────────────────────
INSERT INTO submission (file_path, status, user_id, archive_id, program_step_id,
                        semester, upload_date, review_date, is_in_extension, updated_at)
SELECT
    'documents/' || u.id || '/admission/doc_' || a.id || '.pdf',
    'approved', u.id, a.id, ps.id, NULL,
    NOW() - interval '35 days', NOW() - interval '30 days', false, NOW()
FROM "user" u
JOIN user_program up ON up.user_id = u.id
JOIN program_step ps ON ps.program_id = up.program_id
JOIN step s ON ps.step_id = s.id JOIN phase ph ON s.phase_id = ph.id
JOIN archive a ON a.step_id = s.id
WHERE u.username = 'test_a10_acept_listo' AND ph.name = 'admission' AND a.is_uploadable = true
AND NOT EXISTS (SELECT 1 FROM submission s2 WHERE s2.user_id = u.id AND s2.archive_id = a.id);


-- ── A11: DIFERIDO — todos docs admision aprobados (ya fue aceptado antes) ──
INSERT INTO submission (file_path, status, user_id, archive_id, program_step_id,
                        semester, upload_date, review_date, is_in_extension, updated_at)
SELECT
    'documents/' || u.id || '/admission/doc_' || a.id || '.pdf',
    'approved', u.id, a.id, ps.id, NULL,
    '2025-09-15'::timestamp, '2025-09-20'::timestamp, false, NOW()
FROM "user" u
JOIN user_program up ON up.user_id = u.id
JOIN program_step ps ON ps.program_id = up.program_id
JOIN step s ON ps.step_id = s.id JOIN phase ph ON s.phase_id = ph.id
JOIN archive a ON a.step_id = s.id
WHERE u.username = 'test_a11_diferido1' AND ph.name = 'admission' AND a.is_uploadable = true
AND NOT EXISTS (SELECT 1 FROM submission s2 WHERE s2.user_id = u.id AND s2.archive_id = a.id);


-- ── A12: 2 DIFERIMIENTOS — todos docs aprobados ────────────────────────────
INSERT INTO submission (file_path, status, user_id, archive_id, program_step_id,
                        semester, upload_date, review_date, is_in_extension, updated_at)
SELECT
    'documents/' || u.id || '/admission/doc_' || a.id || '.pdf',
    'approved', u.id, a.id, ps.id, NULL,
    '2025-03-15'::timestamp, '2025-03-20'::timestamp, false, NOW()
FROM "user" u
JOIN user_program up ON up.user_id = u.id
JOIN program_step ps ON ps.program_id = up.program_id
JOIN step s ON ps.step_id = s.id JOIN phase ph ON s.phase_id = ph.id
JOIN archive a ON a.step_id = s.id
WHERE u.username = 'test_a12_diferido2' AND ph.name = 'admission' AND a.is_uploadable = true
AND NOT EXISTS (SELECT 1 FROM submission s2 WHERE s2.user_id = u.id AND s2.archive_id = a.id);


-- ── A13: DOC VENCIDO — todos aprobados pero subidos hace >12 meses ─────────
-- El Comprobante Ingles (archive con validity_months) expira
INSERT INTO submission (file_path, status, user_id, archive_id, program_step_id,
                        semester, upload_date, review_date, is_in_extension, updated_at)
SELECT
    'documents/' || u.id || '/admission/doc_' || a.id || '.pdf',
    'approved', u.id, a.id, ps.id, NULL,
    '2025-01-15'::timestamp, '2025-01-20'::timestamp, false, '2025-01-20'::timestamp
FROM "user" u
JOIN user_program up ON up.user_id = u.id
JOIN program_step ps ON ps.program_id = up.program_id
JOIN step s ON ps.step_id = s.id JOIN phase ph ON s.phase_id = ph.id
JOIN archive a ON a.step_id = s.id
WHERE u.username = 'test_a13_doc_vencido' AND ph.name = 'admission' AND a.is_uploadable = true
AND NOT EXISTS (SELECT 1 FROM submission s2 WHERE s2.user_id = u.id AND s2.archive_id = a.id);


-- ── B1: AL DIA — todos docs admision aprobados ─────────────────────────────
INSERT INTO submission (file_path, status, user_id, archive_id, program_step_id,
                        semester, upload_date, review_date, is_in_extension, updated_at)
SELECT
    'documents/' || u.id || '/admission/doc_' || a.id || '.pdf',
    'approved', u.id, a.id, ps.id, NULL,
    '2024-07-15'::timestamp, '2024-07-20'::timestamp, false, '2024-07-20'::timestamp
FROM "user" u
JOIN user_program up ON up.user_id = u.id
JOIN program_step ps ON ps.program_id = up.program_id
JOIN step s ON ps.step_id = s.id JOIN phase ph ON s.phase_id = ph.id
JOIN archive a ON a.step_id = s.id
WHERE u.username = 'M24110001' AND ph.name = 'admission' AND a.is_uploadable = true
AND NOT EXISTS (SELECT 1 FROM submission s2 WHERE s2.user_id = u.id AND s2.archive_id = a.id);


-- ── B2: DEBE DOCS ADMISION — solo primeros 3 de 8 aprobados, el resto NADA ─
INSERT INTO submission (file_path, status, user_id, archive_id, program_step_id,
                        semester, upload_date, review_date, is_in_extension, updated_at)
SELECT
    'documents/' || u.id || '/admission/doc_' || sub.aid || '.pdf',
    'approved', u.id, sub.aid, sub.psid, NULL,
    '2024-07-10'::timestamp, '2024-07-15'::timestamp, false, '2024-07-15'::timestamp
FROM "user" u
CROSS JOIN LATERAL (
    SELECT a.id AS aid, ps.id AS psid
    FROM archive a
    JOIN step s ON a.step_id = s.id JOIN phase ph ON s.phase_id = ph.id
    JOIN program_step ps ON ps.step_id = s.id
         AND ps.program_id = (SELECT program_id FROM user_program WHERE user_id = u.id LIMIT 1)
    WHERE ph.name = 'admission' AND a.is_uploadable = true
    ORDER BY a.id LIMIT 3
) sub
WHERE u.username = 'M24110002'
AND NOT EXISTS (SELECT 1 FROM submission s2 WHERE s2.user_id = u.id AND s2.archive_id = sub.aid);


-- ── B3: PERMANENCIA PENDIENTE — admision OK, permanencia sin docs ──────────
-- Todos docs admision aprobados
INSERT INTO submission (file_path, status, user_id, archive_id, program_step_id,
                        semester, upload_date, review_date, is_in_extension, updated_at)
SELECT
    'documents/' || u.id || '/admission/doc_' || a.id || '.pdf',
    'approved', u.id, a.id, ps.id, NULL,
    '2025-01-10'::timestamp, '2025-01-15'::timestamp, false, '2025-01-15'::timestamp
FROM "user" u
JOIN user_program up ON up.user_id = u.id
JOIN program_step ps ON ps.program_id = up.program_id
JOIN step s ON ps.step_id = s.id JOIN phase ph ON s.phase_id = ph.id
JOIN archive a ON a.step_id = s.id
WHERE u.username = 'M25110001' AND ph.name = 'admission' AND a.is_uploadable = true
AND NOT EXISTS (SELECT 1 FROM submission s2 WHERE s2.user_id = u.id AND s2.archive_id = a.id);
-- (Docs de permanencia quedan SIN submission = pendientes → alerta roja)


-- ── B4: PENDIENTE PAGO — admision OK ───────────────────────────────────────
INSERT INTO submission (file_path, status, user_id, archive_id, program_step_id,
                        semester, upload_date, review_date, is_in_extension, updated_at)
SELECT
    'documents/' || u.id || '/admission/doc_' || a.id || '.pdf',
    'approved', u.id, a.id, ps.id, NULL,
    '2025-01-10'::timestamp, '2025-01-15'::timestamp, false, '2025-01-15'::timestamp
FROM "user" u
JOIN user_program up ON up.user_id = u.id
JOIN program_step ps ON ps.program_id = up.program_id
JOIN step s ON ps.step_id = s.id JOIN phase ph ON s.phase_id = ph.id
JOIN archive a ON a.step_id = s.id
WHERE u.username = 'M25110002' AND ph.name = 'admission' AND a.is_uploadable = true
AND NOT EXISTS (SELECT 1 FROM submission s2 WHERE s2.user_id = u.id AND s2.archive_id = a.id);


-- ── B5: BAJA TEMPORAL — admision OK ────────────────────────────────────────
INSERT INTO submission (file_path, status, user_id, archive_id, program_step_id,
                        semester, upload_date, review_date, is_in_extension, updated_at)
SELECT
    'documents/' || u.id || '/admission/doc_' || a.id || '.pdf',
    'approved', u.id, a.id, ps.id, NULL,
    '2025-01-10'::timestamp, '2025-01-15'::timestamp, false, '2025-01-15'::timestamp
FROM "user" u
JOIN user_program up ON up.user_id = u.id
JOIN program_step ps ON ps.program_id = up.program_id
JOIN step s ON ps.step_id = s.id JOIN phase ph ON s.phase_id = ph.id
JOIN archive a ON a.step_id = s.id
WHERE u.username = 'M25110003' AND ph.name = 'admission' AND a.is_uploadable = true
AND NOT EXISTS (SELECT 1 FROM submission s2 WHERE s2.user_id = u.id AND s2.archive_id = a.id);


-- =============================================================================
-- SUBMISSIONS DE PERMANENCIA
-- =============================================================================
-- Archives de permanencia uploadables por step:
--   Step  9 (Seguimiento Semestral):  Programacion Materias, Boleta Inscripcion,
--           Boleta Calificacion, Solicitud Baja Temporal, Carta Director = 5 uploadables
--   Step 10 (Servicio Social):        Carta Solicitud, Carta Aceptacion,
--           Carta Terminacion, Informe Final = 4 uploadables
--   Step 11 (Retribucion Social):     Protocolo Investigacion, Plan Actividades,
--           Carta Alta Actividad, Carta Terminacion = 4 uploadables
--   Step 12 (Evaluacion Desempeno):   Formato Desempeno = 1 uploadable
-- Total uploadables permanencia: 14 archivos
-- =============================================================================


-- ── B1: AL DIA — TODOS los docs de permanencia entregados via VENTANAS ──
-- B1 tiene 4 semestres (20243, 20251, 20253, 20263). Cada submission queda
-- ligada a su document_deadline correspondiente. Sólo se generan submissions
-- para archives con ventana configurada en ese (programa, periodo).
INSERT INTO submission (file_path, status, user_id, archive_id, program_step_id,
                        semester, academic_period_id, document_deadline_id,
                        upload_date, review_date, is_in_extension, updated_at)
SELECT
    'documents/' || u.id || '/permanence/sem' || v.sem || '_doc_' || dd.archive_id || '.pdf',
    'approved', u.id, dd.archive_id, ps.id, v.sem,
    dd.academic_period_id, dd.id,
    v.udate::timestamp, (v.udate::timestamp + interval '5 days'),
    false, (v.udate::timestamp + interval '5 days')
FROM "user" u
JOIN user_program up ON up.user_id = u.id
CROSS JOIN (VALUES
    (1, '20243', '2024-09-15'),
    (2, '20251', '2025-02-15'),
    (3, '20253', '2025-09-15'),
    (4, '20263', '2026-09-15')
) AS v(sem, pcode, udate)
JOIN academic_period ap ON ap.code = v.pcode
JOIN document_deadline dd ON dd.program_id = up.program_id
                          AND dd.academic_period_id = ap.id
                          AND dd.sequence = 1
JOIN archive a ON dd.archive_id = a.id
JOIN step s ON a.step_id = s.id
JOIN phase ph ON s.phase_id = ph.id
JOIN program_step ps ON ps.step_id = s.id AND ps.program_id = up.program_id
WHERE u.username = 'M24110001'
  AND ph.name = 'permanence'
AND NOT EXISTS (SELECT 1 FROM submission s2
    WHERE s2.user_id = u.id AND s2.document_deadline_id = dd.id);


-- ── B2: DEBE DOCS — semestres 1-2 entregados via VENTANAS, semestre 3 parcial
INSERT INTO submission (file_path, status, user_id, archive_id, program_step_id,
                        semester, academic_period_id, document_deadline_id,
                        upload_date, review_date, is_in_extension, updated_at)
SELECT
    'documents/' || u.id || '/permanence/sem' || v.sem || '_doc_' || dd.archive_id || '.pdf',
    'approved', u.id, dd.archive_id, ps.id, v.sem,
    dd.academic_period_id, dd.id,
    v.udate::timestamp, (v.udate::timestamp + interval '5 days'),
    false, (v.udate::timestamp + interval '5 days')
FROM "user" u
JOIN user_program up ON up.user_id = u.id
CROSS JOIN (VALUES
    (1, '20243', '2024-09-10'),
    (2, '20253', '2025-09-10')
) AS v(sem, pcode, udate)
JOIN academic_period ap ON ap.code = v.pcode
JOIN document_deadline dd ON dd.program_id = up.program_id
                          AND dd.academic_period_id = ap.id
                          AND dd.sequence = 1
JOIN archive a ON dd.archive_id = a.id
JOIN step s ON a.step_id = s.id
JOIN phase ph ON s.phase_id = ph.id
JOIN program_step ps ON ps.step_id = s.id AND ps.program_id = up.program_id
WHERE u.username = 'M24110002'
  AND ph.name = 'permanence'
AND NOT EXISTS (SELECT 1 FROM submission s2
    WHERE s2.user_id = u.id AND s2.document_deadline_id = dd.id);

-- Semestre actual (3) en 20263: sólo primeras 3 ventanas entregadas, resto
-- queda como faltante para probar bloqueo por documentos pendientes.
INSERT INTO submission (file_path, status, user_id, archive_id, program_step_id,
                        semester, academic_period_id, document_deadline_id,
                        upload_date, review_date, is_in_extension, updated_at)
SELECT
    'documents/' || u.id || '/permanence/sem3_doc_' || sub.archive_id || '.pdf',
    'approved', u.id, sub.archive_id, sub.psid, 3,
    sub.academic_period_id, sub.id,
    '2026-09-10'::timestamp, '2026-09-15'::timestamp, false, '2026-09-15'::timestamp
FROM "user" u
JOIN user_program up ON up.user_id = u.id
JOIN LATERAL (
    SELECT dd.id, dd.archive_id, dd.academic_period_id, ps.id AS psid
    FROM document_deadline dd
    JOIN archive a ON dd.archive_id = a.id
    JOIN step s ON a.step_id = s.id
    JOIN phase ph ON s.phase_id = ph.id
    JOIN program_step ps ON ps.step_id = s.id AND ps.program_id = up.program_id
    WHERE dd.program_id = up.program_id
      AND dd.academic_period_id = (SELECT id FROM academic_period WHERE code = '20263')
      AND dd.sequence = 1
      AND ph.name = 'permanence'
    ORDER BY dd.id
    LIMIT 3
) sub ON TRUE
WHERE u.username = 'M24110002'
AND NOT EXISTS (SELECT 1 FROM submission s2
    WHERE s2.user_id = u.id AND s2.document_deadline_id = sub.id);


-- ── B3: PERMANENCIA PENDIENTE — semestre 1 entregado via ventanas, sem 2 SIN
-- Semestre 1 (20253): todos los docs aprobados via document_deadline
INSERT INTO submission (file_path, status, user_id, archive_id, program_step_id,
                        semester, academic_period_id, document_deadline_id,
                        upload_date, review_date, is_in_extension, updated_at)
SELECT
    'documents/' || u.id || '/permanence/sem1_doc_' || dd.archive_id || '.pdf',
    'approved', u.id, dd.archive_id, ps.id, 1,
    dd.academic_period_id, dd.id,
    '2025-09-15'::timestamp, '2025-09-20'::timestamp, false, '2025-09-20'::timestamp
FROM "user" u
JOIN user_program up ON up.user_id = u.id
JOIN document_deadline dd ON dd.program_id = up.program_id
                          AND dd.academic_period_id = (SELECT id FROM academic_period WHERE code = '20253')
                          AND dd.sequence = 1
JOIN archive a ON dd.archive_id = a.id
JOIN step s ON a.step_id = s.id
JOIN phase ph ON s.phase_id = ph.id
JOIN program_step ps ON ps.step_id = s.id AND ps.program_id = up.program_id
WHERE u.username = 'M25110001' AND ph.name = 'permanence'
AND NOT EXISTS (SELECT 1 FROM submission s2
    WHERE s2.user_id = u.id AND s2.document_deadline_id = dd.id);
-- Semestre 2 (activo, 20263): SIN submissions de permanencia → alerta roja


-- ── B4: PAGO PENDIENTE — sem 1 entregado via ventanas, sem 2 parcial (3) ───
-- Semestre 1 (20253): todos los docs aprobados via document_deadline
INSERT INTO submission (file_path, status, user_id, archive_id, program_step_id,
                        semester, academic_period_id, document_deadline_id,
                        upload_date, review_date, is_in_extension, updated_at)
SELECT
    'documents/' || u.id || '/permanence/sem1_doc_' || dd.archive_id || '.pdf',
    'approved', u.id, dd.archive_id, ps.id, 1,
    dd.academic_period_id, dd.id,
    '2025-09-10'::timestamp, '2025-09-15'::timestamp, false, '2025-09-15'::timestamp
FROM "user" u
JOIN user_program up ON up.user_id = u.id
JOIN document_deadline dd ON dd.program_id = up.program_id
                          AND dd.academic_period_id = (SELECT id FROM academic_period WHERE code = '20253')
                          AND dd.sequence = 1
JOIN archive a ON dd.archive_id = a.id
JOIN step s ON a.step_id = s.id
JOIN phase ph ON s.phase_id = ph.id
JOIN program_step ps ON ps.step_id = s.id AND ps.program_id = up.program_id
WHERE u.username = 'M25110002' AND ph.name = 'permanence'
AND NOT EXISTS (SELECT 1 FROM submission s2
    WHERE s2.user_id = u.id AND s2.document_deadline_id = dd.id);

-- Semestre 2 (activo 20263): sólo primeras 3 ventanas entregadas
INSERT INTO submission (file_path, status, user_id, archive_id, program_step_id,
                        semester, academic_period_id, document_deadline_id,
                        upload_date, review_date, is_in_extension, updated_at)
SELECT
    'documents/' || u.id || '/permanence/sem2_doc_' || sub.archive_id || '.pdf',
    'approved', u.id, sub.archive_id, sub.psid, 2,
    sub.academic_period_id, sub.id,
    '2026-08-20'::timestamp, '2026-08-25'::timestamp, false, '2026-08-25'::timestamp
FROM "user" u
JOIN user_program up ON up.user_id = u.id
JOIN LATERAL (
    SELECT dd.id, dd.archive_id, dd.academic_period_id, ps.id AS psid
    FROM document_deadline dd
    JOIN archive a ON dd.archive_id = a.id
    JOIN step s ON a.step_id = s.id
    JOIN phase ph ON s.phase_id = ph.id
    JOIN program_step ps ON ps.step_id = s.id AND ps.program_id = up.program_id
    WHERE dd.program_id = up.program_id
      AND dd.academic_period_id = (SELECT id FROM academic_period WHERE code = '20263')
      AND dd.sequence = 1
      AND ph.name = 'permanence'
    ORDER BY dd.id
    LIMIT 3
) sub ON TRUE
WHERE u.username = 'M25110002'
AND NOT EXISTS (SELECT 1 FROM submission s2
    WHERE s2.user_id = u.id AND s2.document_deadline_id = sub.id);


-- ── B5: BAJA TEMPORAL (MANI) — sem 1 entregado via ventanas, sem 2 parcial (2)
-- Semestre 1 (20253) MANI: todos los docs aprobados via document_deadline
INSERT INTO submission (file_path, status, user_id, archive_id, program_step_id,
                        semester, academic_period_id, document_deadline_id,
                        upload_date, review_date, is_in_extension, updated_at)
SELECT
    'documents/' || u.id || '/permanence/sem1_doc_' || dd.archive_id || '.pdf',
    'approved', u.id, dd.archive_id, ps.id, 1,
    dd.academic_period_id, dd.id,
    '2025-09-05'::timestamp, '2025-09-10'::timestamp, false, '2025-09-10'::timestamp
FROM "user" u
JOIN user_program up ON up.user_id = u.id
JOIN document_deadline dd ON dd.program_id = up.program_id
                          AND dd.academic_period_id = (SELECT id FROM academic_period WHERE code = '20253')
                          AND dd.sequence = 1
JOIN archive a ON dd.archive_id = a.id
JOIN step s ON a.step_id = s.id
JOIN phase ph ON s.phase_id = ph.id
JOIN program_step ps ON ps.step_id = s.id AND ps.program_id = up.program_id
WHERE u.username = 'M25110003' AND ph.name = 'permanence'
AND NOT EXISTS (SELECT 1 FROM submission s2
    WHERE s2.user_id = u.id AND s2.document_deadline_id = dd.id);

-- Semestre 2 (20263) MANI: sólo 2 docs entregados antes de la baja temporal
INSERT INTO submission (file_path, status, user_id, archive_id, program_step_id,
                        semester, academic_period_id, document_deadline_id,
                        upload_date, review_date, is_in_extension, updated_at)
SELECT
    'documents/' || u.id || '/permanence/sem2_doc_' || sub.archive_id || '.pdf',
    'approved', u.id, sub.archive_id, sub.psid, 2,
    sub.academic_period_id, sub.id,
    '2026-08-15'::timestamp, '2026-08-18'::timestamp, false, '2026-08-18'::timestamp
FROM "user" u
JOIN user_program up ON up.user_id = u.id
JOIN LATERAL (
    SELECT dd.id, dd.archive_id, dd.academic_period_id, ps.id AS psid
    FROM document_deadline dd
    JOIN archive a ON dd.archive_id = a.id
    JOIN step s ON a.step_id = s.id
    JOIN phase ph ON s.phase_id = ph.id
    JOIN program_step ps ON ps.step_id = s.id AND ps.program_id = up.program_id
    WHERE dd.program_id = up.program_id
      AND dd.academic_period_id = (SELECT id FROM academic_period WHERE code = '20263')
      AND dd.sequence = 1
      AND ph.name = 'permanence'
    ORDER BY dd.id
    LIMIT 2
) sub ON TRUE
WHERE u.username = 'M25110003'
AND NOT EXISTS (SELECT 1 FROM submission s2
    WHERE s2.user_id = u.id AND s2.document_deadline_id = sub.id);
