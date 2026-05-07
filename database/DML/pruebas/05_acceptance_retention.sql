-- =============================================================================
-- 05: Documentos de aceptacion y politicas de retencion
-- =============================================================================


-- ═══════════════════════════════════════════════════════════════════════════════
-- ACCEPTANCE DOCUMENTS
-- ═══════════════════════════════════════════════════════════════════════════════

-- ── A9: Aceptado NO PAGA — tiene carta y tira, pero NO sube boleta ─────────
-- Carta de aceptacion (subida por coordinador)
INSERT INTO acceptance_document (user_program_id, document_type, file_path,
                                 uploaded_by_id, uploaded_at, status, created_at, updated_at)
SELECT up.id, 'acceptance_letter',
       'documents/' || u.id || '/acceptance/acceptance_letter.pdf',
       (SELECT id FROM "user" WHERE username = 'admin'),
       NOW() - interval '15 days', 'uploaded', NOW() - interval '15 days', NOW()
FROM user_program up JOIN "user" u ON up.user_id = u.id
WHERE u.username = 'test_a09_acept_nopaga'
AND NOT EXISTS (SELECT 1 FROM acceptance_document ad WHERE ad.user_program_id = up.id AND ad.document_type = 'acceptance_letter');

-- Tira de materias (subida por coordinador)
INSERT INTO acceptance_document (user_program_id, document_type, file_path,
                                 uploaded_by_id, uploaded_at, status, created_at, updated_at)
SELECT up.id, 'course_schedule',
       'documents/' || u.id || '/acceptance/course_schedule.pdf',
       (SELECT id FROM "user" WHERE username = 'admin'),
       NOW() - interval '15 days', 'uploaded', NOW() - interval '15 days', NOW()
FROM user_program up JOIN "user" u ON up.user_id = u.id
WHERE u.username = 'test_a09_acept_nopaga'
AND NOT EXISTS (SELECT 1 FROM acceptance_document ad WHERE ad.user_program_id = up.id AND ad.document_type = 'course_schedule');

-- Boleta: PENDIENTE (nunca la subio)
INSERT INTO acceptance_document (user_program_id, document_type, status, created_at, updated_at)
SELECT up.id, 'enrollment_receipt', 'pending', NOW(), NOW()
FROM user_program up JOIN "user" u ON up.user_id = u.id
WHERE u.username = 'test_a09_acept_nopaga'
AND NOT EXISTS (SELECT 1 FROM acceptance_document ad WHERE ad.user_program_id = up.id AND ad.document_type = 'enrollment_receipt');


-- ── A10: Aceptado LISTO — carta, tira Y boleta aprobada ────────────────────
INSERT INTO acceptance_document (user_program_id, document_type, file_path,
                                 uploaded_by_id, uploaded_at, status, created_at, updated_at)
SELECT up.id, 'acceptance_letter',
       'documents/' || u.id || '/acceptance/acceptance_letter.pdf',
       (SELECT id FROM "user" WHERE username = 'admin'),
       NOW() - interval '20 days', 'uploaded', NOW() - interval '20 days', NOW()
FROM user_program up JOIN "user" u ON up.user_id = u.id
WHERE u.username = 'test_a10_acept_listo'
AND NOT EXISTS (SELECT 1 FROM acceptance_document ad WHERE ad.user_program_id = up.id AND ad.document_type = 'acceptance_letter');

INSERT INTO acceptance_document (user_program_id, document_type, file_path,
                                 uploaded_by_id, uploaded_at, status, created_at, updated_at)
SELECT up.id, 'course_schedule',
       'documents/' || u.id || '/acceptance/course_schedule.pdf',
       (SELECT id FROM "user" WHERE username = 'admin'),
       NOW() - interval '20 days', 'uploaded', NOW() - interval '20 days', NOW()
FROM user_program up JOIN "user" u ON up.user_id = u.id
WHERE u.username = 'test_a10_acept_listo'
AND NOT EXISTS (SELECT 1 FROM acceptance_document ad WHERE ad.user_program_id = up.id AND ad.document_type = 'course_schedule');

-- Boleta: subida por aspirante y APROBADA por coordinador
INSERT INTO acceptance_document (user_program_id, document_type, file_path,
                                 uploaded_by_id, uploaded_at, status,
                                 reviewed_by_id, reviewed_at, review_notes,
                                 created_at, updated_at)
SELECT up.id, 'enrollment_receipt',
       'documents/' || u.id || '/acceptance/enrollment_receipt.pdf',
       u.id,  -- subida por el aspirante
       NOW() - interval '10 days', 'approved',
       (SELECT id FROM "user" WHERE username = 'admin'),
       NOW() - interval '8 days',
       'Boleta verificada correctamente',
       NOW() - interval '10 days', NOW()
FROM user_program up JOIN "user" u ON up.user_id = u.id
WHERE u.username = 'test_a10_acept_listo'
AND NOT EXISTS (SELECT 1 FROM acceptance_document ad WHERE ad.user_program_id = up.id AND ad.document_type = 'enrollment_receipt');


-- ── A11: Diferido — carta conservada, tira y boleta eliminados por deferral ─
INSERT INTO acceptance_document (user_program_id, document_type, file_path,
                                 uploaded_by_id, uploaded_at, status, created_at, updated_at)
SELECT up.id, 'acceptance_letter',
       'documents/' || u.id || '/acceptance/acceptance_letter.pdf',
       (SELECT id FROM "user" WHERE username = 'admin'),
       '2025-11-10'::timestamp, 'uploaded', '2025-11-10'::timestamp, NOW()
FROM user_program up JOIN "user" u ON up.user_id = u.id
WHERE u.username = 'test_a11_diferido1'
AND NOT EXISTS (SELECT 1 FROM acceptance_document ad WHERE ad.user_program_id = up.id AND ad.document_type = 'acceptance_letter');

-- Tira: pending (fue eliminada al diferir)
INSERT INTO acceptance_document (user_program_id, document_type, status, created_at, updated_at)
SELECT up.id, 'course_schedule', 'pending', NOW(), NOW()
FROM user_program up JOIN "user" u ON up.user_id = u.id
WHERE u.username = 'test_a11_diferido1'
AND NOT EXISTS (SELECT 1 FROM acceptance_document ad WHERE ad.user_program_id = up.id AND ad.document_type = 'course_schedule');

-- Boleta: pending (fue eliminada al diferir)
INSERT INTO acceptance_document (user_program_id, document_type, status, created_at, updated_at)
SELECT up.id, 'enrollment_receipt', 'pending', NOW(), NOW()
FROM user_program up JOIN "user" u ON up.user_id = u.id
WHERE u.username = 'test_a11_diferido1'
AND NOT EXISTS (SELECT 1 FROM acceptance_document ad WHERE ad.user_program_id = up.id AND ad.document_type = 'enrollment_receipt');


-- ═══════════════════════════════════════════════════════════════════════════════
-- ACCEPTANCE DOCUMENTS PARA ESTUDIANTES (B1-B5)
-- Todo estudiante inscrito paso por el flujo de aceptacion completo:
-- carta de aceptacion + tira de materias + boleta aprobada
-- ═══════════════════════════════════════════════════════════════════════════════

-- ── B1: AL DIA — los 3 docs de aceptacion completos ────────────────────────
INSERT INTO acceptance_document (user_program_id, document_type, file_path,
                                 uploaded_by_id, uploaded_at, status,
                                 reviewed_by_id, reviewed_at, review_notes,
                                 created_at, updated_at)
SELECT up.id, v.dtype,
       'documents/' || u.id || '/acceptance/' || v.fname,
       CASE WHEN v.dtype = 'enrollment_receipt' THEN u.id
            ELSE (SELECT id FROM "user" WHERE username = 'admin') END,
       '2024-07-25'::timestamp, 'approved',
       (SELECT id FROM "user" WHERE username = 'admin'),
       '2024-07-28'::timestamp,
       'Documento verificado',
       '2024-07-25'::timestamp, NOW()
FROM user_program up JOIN "user" u ON up.user_id = u.id
CROSS JOIN (VALUES
    ('acceptance_letter', 'acceptance_letter.pdf'),
    ('course_schedule', 'course_schedule.pdf'),
    ('enrollment_receipt', 'enrollment_receipt.pdf')
) AS v(dtype, fname)
WHERE u.username = 'M24110001'
AND NOT EXISTS (SELECT 1 FROM acceptance_document ad WHERE ad.user_program_id = up.id AND ad.document_type = v.dtype);

-- ── B2: DEBE DOCS — los 3 docs de aceptacion completos ─────────────────────
INSERT INTO acceptance_document (user_program_id, document_type, file_path,
                                 uploaded_by_id, uploaded_at, status,
                                 reviewed_by_id, reviewed_at, review_notes,
                                 created_at, updated_at)
SELECT up.id, v.dtype,
       'documents/' || u.id || '/acceptance/' || v.fname,
       CASE WHEN v.dtype = 'enrollment_receipt' THEN u.id
            ELSE (SELECT id FROM "user" WHERE username = 'admin') END,
       '2024-07-25'::timestamp, 'approved',
       (SELECT id FROM "user" WHERE username = 'admin'),
       '2024-07-28'::timestamp,
       'Documento verificado',
       '2024-07-25'::timestamp, NOW()
FROM user_program up JOIN "user" u ON up.user_id = u.id
CROSS JOIN (VALUES
    ('acceptance_letter', 'acceptance_letter.pdf'),
    ('course_schedule', 'course_schedule.pdf'),
    ('enrollment_receipt', 'enrollment_receipt.pdf')
) AS v(dtype, fname)
WHERE u.username = 'M24110002'
AND NOT EXISTS (SELECT 1 FROM acceptance_document ad WHERE ad.user_program_id = up.id AND ad.document_type = v.dtype);

-- ── B3: PERMANENCIA PENDIENTE — los 3 docs de aceptacion completos ─────────
INSERT INTO acceptance_document (user_program_id, document_type, file_path,
                                 uploaded_by_id, uploaded_at, status,
                                 reviewed_by_id, reviewed_at, review_notes,
                                 created_at, updated_at)
SELECT up.id, v.dtype,
       'documents/' || u.id || '/acceptance/' || v.fname,
       CASE WHEN v.dtype = 'enrollment_receipt' THEN u.id
            ELSE (SELECT id FROM "user" WHERE username = 'admin') END,
       '2025-01-15'::timestamp, 'approved',
       (SELECT id FROM "user" WHERE username = 'admin'),
       '2025-01-18'::timestamp,
       'Documento verificado',
       '2025-01-15'::timestamp, NOW()
FROM user_program up JOIN "user" u ON up.user_id = u.id
CROSS JOIN (VALUES
    ('acceptance_letter', 'acceptance_letter.pdf'),
    ('course_schedule', 'course_schedule.pdf'),
    ('enrollment_receipt', 'enrollment_receipt.pdf')
) AS v(dtype, fname)
WHERE u.username = 'M25110001'
AND NOT EXISTS (SELECT 1 FROM acceptance_document ad WHERE ad.user_program_id = up.id AND ad.document_type = v.dtype);

-- ── B4: PAGO PENDIENTE — los 3 docs de aceptacion completos ────────────────
INSERT INTO acceptance_document (user_program_id, document_type, file_path,
                                 uploaded_by_id, uploaded_at, status,
                                 reviewed_by_id, reviewed_at, review_notes,
                                 created_at, updated_at)
SELECT up.id, v.dtype,
       'documents/' || u.id || '/acceptance/' || v.fname,
       CASE WHEN v.dtype = 'enrollment_receipt' THEN u.id
            ELSE (SELECT id FROM "user" WHERE username = 'admin') END,
       '2025-01-15'::timestamp, 'approved',
       (SELECT id FROM "user" WHERE username = 'admin'),
       '2025-01-18'::timestamp,
       'Documento verificado',
       '2025-01-15'::timestamp, NOW()
FROM user_program up JOIN "user" u ON up.user_id = u.id
CROSS JOIN (VALUES
    ('acceptance_letter', 'acceptance_letter.pdf'),
    ('course_schedule', 'course_schedule.pdf'),
    ('enrollment_receipt', 'enrollment_receipt.pdf')
) AS v(dtype, fname)
WHERE u.username = 'M25110002'
AND NOT EXISTS (SELECT 1 FROM acceptance_document ad WHERE ad.user_program_id = up.id AND ad.document_type = v.dtype);

-- ── B5: BAJA TEMPORAL — los 3 docs de aceptacion completos ─────────────────
INSERT INTO acceptance_document (user_program_id, document_type, file_path,
                                 uploaded_by_id, uploaded_at, status,
                                 reviewed_by_id, reviewed_at, review_notes,
                                 created_at, updated_at)
SELECT up.id, v.dtype,
       'documents/' || u.id || '/acceptance/' || v.fname,
       CASE WHEN v.dtype = 'enrollment_receipt' THEN u.id
            ELSE (SELECT id FROM "user" WHERE username = 'admin') END,
       '2025-01-15'::timestamp, 'approved',
       (SELECT id FROM "user" WHERE username = 'admin'),
       '2025-01-18'::timestamp,
       'Documento verificado',
       '2025-01-15'::timestamp, NOW()
FROM user_program up JOIN "user" u ON up.user_id = u.id
CROSS JOIN (VALUES
    ('acceptance_letter', 'acceptance_letter.pdf'),
    ('course_schedule', 'course_schedule.pdf'),
    ('enrollment_receipt', 'enrollment_receipt.pdf')
) AS v(dtype, fname)
WHERE u.username = 'M25110003'
AND NOT EXISTS (SELECT 1 FROM acceptance_document ad WHERE ad.user_program_id = up.id AND ad.document_type = v.dtype);


-- ═══════════════════════════════════════════════════════════════════════════════
-- RETENTION POLICIES (para probar la tarea de limpieza automatica)
-- ═══════════════════════════════════════════════════════════════════════════════

-- Politica: docs de admision se conservan 4 anos despues de graduarse
INSERT INTO retention_policy (archive_id, keep_years, keep_forever, apply_after)
SELECT a.id, 4, false, 'graduated'
FROM archive a
JOIN step s ON a.step_id = s.id JOIN phase ph ON s.phase_id = ph.id
WHERE ph.name = 'admission' AND a.is_uploadable = true
AND NOT EXISTS (SELECT 1 FROM retention_policy rp WHERE rp.archive_id = a.id)
ORDER BY a.id LIMIT 3;

-- Politica: titulo se conserva para siempre
INSERT INTO retention_policy (archive_id, keep_years, keep_forever, apply_after)
SELECT a.id, NULL, true, 'enrolled'
FROM archive a
JOIN step s ON a.step_id = s.id JOIN phase ph ON s.phase_id = ph.id
WHERE ph.name = 'admission' AND a.is_uploadable = true
AND a.name ILIKE '%tulo%'
AND NOT EXISTS (SELECT 1 FROM retention_policy rp WHERE rp.archive_id = a.id)
LIMIT 1;


-- ═══════════════════════════════════════════════════════════════════════════════
-- VALIDITY_MONTHS — configurar vigencia para probar A13 (doc vencido)
-- ═══════════════════════════════════════════════════════════════════════════════
-- El Comprobante de Ingles expira a los 12 meses
UPDATE archive SET validity_months = 12
WHERE name ILIKE '%Comprobante Ingl%' AND step_id IN (
    SELECT s.id FROM step s JOIN phase ph ON s.phase_id = ph.id WHERE ph.name = 'admission'
)
AND validity_months IS NULL;
