-- =============================================================================
-- 08: Casos de prueba para la tarea "Pasar Semestre" (PLAN_PASAR_SEMESTRE.md)
-- =============================================================================
-- Objetivo: cubrir las ramas de evaluate_student y migración de aspirantes.
--
-- Asume que ya corrieron 01..07. Este archivo:
--   * Liga submissions de permanencia existentes (caso B1) a sus
--     document_deadline correspondientes (probar happy-path de avance).
--   * Asegura que B2 / B3 / B4 tengan ventanas con/sin entrega para probar
--     bloqueos por documentos.
--   * Crea estudiante B6 becario CONACyT con un Formato mensual cerrado SIN
--     entrega (debe bloquear avance).
--   * Crea aspirantes A14 (1 periodo atrás → debe migrar) y
--     A15 (2 periodos atrás → debe expirar conservando archivos).
--
-- Periodos referenciados (deben existir en academic_period):
--   20251 → Ene-Jun 2025  (2 periodos atrás respecto a 20263)
--   20253 → Ago-Dic 2025  (1 periodo atrás respecto a 20263)
--   20261 → Ene-Jun 2026
--   20263 → Ago-Dic 2026  (ACTIVO simulado)
-- =============================================================================


-- ═══════════════════════════════════════════════════════════════════════════════
-- 8.1 Ligar submissions de B1 (al día) a sus document_deadline del periodo 20263
-- B1 ya tiene submissions de permanencia aprobadas para semestre 4 (periodo 20263).
-- Las ligamos al deadline correspondiente para que evaluate_student detecte
-- "ventana cerrada con submission aprobada" → avance permitido.
-- ═══════════════════════════════════════════════════════════════════════════════
UPDATE submission s
SET document_deadline_id = dd.id
FROM document_deadline dd
JOIN academic_period ap ON dd.academic_period_id = ap.id
JOIN archive a ON dd.archive_id = a.id
WHERE s.user_id = (SELECT id FROM "user" WHERE username = 'M24110001')
  AND s.archive_id = a.id
  AND s.semester = 4
  AND s.academic_period_id = ap.id
  AND ap.code = '20263'
  AND s.document_deadline_id IS NULL;


-- ═══════════════════════════════════════════════════════════════════════════════
-- 8.2 B2 — sólo 4 archives entregados de permanencia en sem 3 (periodo 20263)
-- Ligamos los entregados a su deadline. Los archives sin submission quedan
-- sin entrega → si la ventana cierra antes del avance, bloquea.
-- ═══════════════════════════════════════════════════════════════════════════════
UPDATE submission s
SET document_deadline_id = dd.id
FROM document_deadline dd
JOIN academic_period ap ON dd.academic_period_id = ap.id
WHERE s.user_id = (SELECT id FROM "user" WHERE username = 'M24110002')
  AND s.archive_id = dd.archive_id
  AND s.semester = 3
  AND s.academic_period_id = ap.id
  AND ap.code = '20263'
  AND s.document_deadline_id IS NULL;


-- ═══════════════════════════════════════════════════════════════════════════════
-- 8.3 B4 — sem 2 (periodo 20263) tiene 3 docs aprobados + 1 ventana cerrada
-- pendiente. Forzamos cierre de la ventana 'Boleta de Calificaciones' del
-- periodo 20263 (cerrarla antes de NOW para que cuente como pendiente vencido).
-- B4 tiene enrollment_confirmed=false → ya bloquea por pago. Esto agrega el
-- bloqueo adicional por documentos faltantes.
-- ═══════════════════════════════════════════════════════════════════════════════
-- Mover cierre a fecha pasada para "Boleta de Calificaciones" 20263 MII
UPDATE document_deadline dd
SET closes_at = NOW() - interval '15 days', is_open = false, updated_at = NOW()
FROM academic_period ap, archive a, step st, phase ph
WHERE dd.academic_period_id = ap.id
  AND dd.archive_id = a.id
  AND a.step_id = st.id
  AND st.phase_id = ph.id
  AND ph.name = 'permanence'
  AND a.name ILIKE '%Boleta%Calificacion%'
  AND ap.code = '20263'
  AND dd.program_id = (SELECT id FROM program WHERE slug = 'MII');


-- ═══════════════════════════════════════════════════════════════════════════════
-- 8.4 B6 NUEVO — estudiante becario CONACyT con Formato mensual cerrado sin
-- entrega. Debe bloquearse el avance.
-- ═══════════════════════════════════════════════════════════════════════════════
-- Usuario nuevo M25110004 (Karla Rios)
INSERT INTO "user" (first_name, last_name, mother_last_name, username, password, email,
                    is_internal, role_id, must_change_password, registration_date, last_login,
                    is_active, profile_completed, updated_at,
                    phone, address, curp, birth_date,
                    emergency_contact_name, emergency_contact_phone, emergency_contact_relationship,
                    control_number, photo_change_allowed)
SELECT 'Karla', 'Rios', 'Cano', 'M25110004',
       'scrypt:32768:8:1$ZshV34gGFmJl1s8G$a675f0c4117ce077f4b3320561c431b84726a615327cae96ec1e23e2ebc97e06b898b9a7d6faea1b055ede7bdaaed1f1086f4cb9c8b7482c5d9f22ca2dc88835',
       'm25110004@test.com', true,
       (SELECT id FROM role WHERE name = 'student' LIMIT 1),
       false, '2025-08-01'::timestamp, '2025-08-01'::timestamp,
       true, true, NOW(),
       '6566500004', 'Calle CONACyT 4', 'TEST040404HJCKL14', '1995-04-04'::date,
       'Contacto Rios', '6567500004', 'Madre',
       'M25110004', false
WHERE NOT EXISTS (SELECT 1 FROM "user" WHERE username = 'M25110004');

-- UserProgram becario CONACyT MII, sem 2 activo
INSERT INTO user_program (user_id, program_id, enrollment_date, current_semester,
                          admission_period_id, admission_status, has_conacyt_scholarship, updated_at)
SELECT u.id, (SELECT id FROM program WHERE slug = 'MII'),
       '2025-08-01'::timestamp, 2,
       (SELECT id FROM academic_period WHERE code = '20253'),
       'enrolled', true, NOW()
FROM "user" u WHERE u.username = 'M25110004'
AND NOT EXISTS (SELECT 1 FROM user_program WHERE user_id = u.id);

-- SE sem 1 completed (20253)
INSERT INTO semester_enrollment (user_program_id, academic_period_id, semester_number,
                                  status, enrollment_confirmed, confirmed_by, confirmed_at,
                                  created_at, updated_at)
SELECT up.id, (SELECT id FROM academic_period WHERE code = '20253'),
       1, 'completed', true,
       (SELECT id FROM "user" WHERE username = 'admin'),
       '2025-08-15'::timestamp, '2025-08-15'::timestamp, NOW()
FROM user_program up JOIN "user" u ON up.user_id = u.id
WHERE u.username = 'M25110004'
AND NOT EXISTS (SELECT 1 FROM semester_enrollment se WHERE se.user_program_id = up.id AND se.semester_number = 1);

-- SE sem 2 active confirmed (20263)
INSERT INTO semester_enrollment (user_program_id, academic_period_id, semester_number,
                                  status, enrollment_confirmed, confirmed_by, confirmed_at,
                                  created_at, updated_at)
SELECT up.id, (SELECT id FROM academic_period WHERE code = '20263'),
       2, 'active', true,
       (SELECT id FROM "user" WHERE username = 'admin'),
       '2026-08-15'::timestamp, '2026-08-15'::timestamp, NOW()
FROM user_program up JOIN "user" u ON up.user_id = u.id
WHERE u.username = 'M25110004'
AND NOT EXISTS (SELECT 1 FROM semester_enrollment se WHERE se.user_program_id = up.id AND se.semester_number = 2);

-- B6 entregó la mayoría de las ventanas regulares (Programacion, Boleta Inscripcion,
-- 1er Reporte) PERO no entregó el Formato CONACyT de Agosto (ya cerrado).
-- Esto cumple permanencia general PERO bloquea por CONACyT mensual faltante.
INSERT INTO submission (file_path, status, user_id, archive_id, program_step_id,
                        semester, academic_period_id, document_deadline_id,
                        upload_date, review_date, is_in_extension, updated_at)
SELECT 'documents/' || u.id || '/permanence/sem2_doc_' || dd.archive_id || '.pdf',
       'approved', u.id, dd.archive_id,
       (SELECT ps.id FROM program_step ps
          JOIN archive ax ON ax.step_id = ps.step_id
          WHERE ax.id = dd.archive_id AND ps.program_id = dd.program_id LIMIT 1),
       2, dd.academic_period_id, dd.id,
       '2026-08-20'::timestamp, '2026-08-25'::timestamp, false, NOW()
FROM "user" u
JOIN document_deadline dd
  ON dd.program_id = (SELECT id FROM program WHERE slug = 'MII')
 AND dd.academic_period_id = (SELECT id FROM academic_period WHERE code = '20263')
JOIN archive a ON dd.archive_id = a.id
JOIN step st ON a.step_id = st.id
JOIN phase ph ON st.phase_id = ph.id
WHERE u.username = 'M25110004'
  AND ph.name = 'permanence'
  AND a.name NOT ILIKE '%Formato%Desempe%'   -- excluye CONACyT mensual
  AND a.name NOT ILIKE '%Boleta%Calificacion%'   -- aún no abre fin del semestre
  AND a.name NOT ILIKE '%Solicitud%Baja%'        -- no aplica
  AND NOT EXISTS (
    SELECT 1 FROM submission s2
    WHERE s2.user_id = u.id AND s2.document_deadline_id = dd.id
  );


-- ═══════════════════════════════════════════════════════════════════════════════
-- 8.5 A14 NUEVO — aspirante con admission_period_id = 20253 (1 periodo atrás)
-- Esperado: al cerrar 20263 y avanzar a 20271, este aspirante debe MIGRAR
-- (admission_period_id ← 20271). Conserva sus docs/submissions.
-- Nota: 20253 está 1 atrás de 20263 (activo simulado). Cuando 20263 sea el
-- destino y 20253 origen, A14 (con periodo 20253) está en periodo origen,
-- migra automáticamente como aspirantes del periodo recién terminado.
-- Para probar la regla "1 periodo atrás" propiamente, necesita estar 1 periodo
-- atrás del NUEVO activo. Simulamos cerrando 20263 → activar 20271.
-- ═══════════════════════════════════════════════════════════════════════════════
INSERT INTO "user" (first_name, last_name, mother_last_name, username, password, email,
                    is_internal, role_id, must_change_password, registration_date, last_login,
                    is_active, profile_completed, updated_at,
                    phone, address, curp, birth_date,
                    emergency_contact_name, emergency_contact_phone, emergency_contact_relationship,
                    photo_change_allowed)
SELECT 'Yolanda', 'Castro', 'Pena', 'test_a14_periodo_atras',
       'scrypt:32768:8:1$ZshV34gGFmJl1s8G$a675f0c4117ce077f4b3320561c431b84726a615327cae96ec1e23e2ebc97e06b898b9a7d6faea1b055ede7bdaaed1f1086f4cb9c8b7482c5d9f22ca2dc88835',
       'test.a14@test.com', false,
       (SELECT id FROM role WHERE name = 'applicant' LIMIT 1),
       false, '2026-04-01'::timestamp, '2026-04-01'::timestamp,
       true, true, NOW(),
       '6566500014', 'Calle Atras 14', 'TEST140414HJCAA14', '1996-04-14'::date,
       'Contacto Castro', '6567500014', 'Padre',
       false
WHERE NOT EXISTS (SELECT 1 FROM "user" WHERE username = 'test_a14_periodo_atras');

INSERT INTO user_program (user_id, program_id, enrollment_date, current_semester,
                          admission_period_id, admission_status, updated_at)
SELECT u.id, (SELECT id FROM program WHERE slug = 'MII'),
       u.registration_date, NULL,
       (SELECT id FROM academic_period WHERE code = '20263'),
       'in_progress', NOW()
FROM "user" u WHERE u.username = 'test_a14_periodo_atras'
AND NOT EXISTS (SELECT 1 FROM user_program WHERE user_id = u.id);


-- ═══════════════════════════════════════════════════════════════════════════════
-- 8.6 A15 NUEVO — aspirante con admission_period_id = 20251 (2 periodos atrás)
-- Esperado: al cerrar 20263 y avanzar a 20271, este aspirante debe EXPIRAR
-- (admission_status='expired') conservando archivos físicos.
-- ═══════════════════════════════════════════════════════════════════════════════
INSERT INTO "user" (first_name, last_name, mother_last_name, username, password, email,
                    is_internal, role_id, must_change_password, registration_date, last_login,
                    is_active, profile_completed, updated_at,
                    phone, address, curp, birth_date,
                    emergency_contact_name, emergency_contact_phone, emergency_contact_relationship,
                    photo_change_allowed)
SELECT 'Zacarias', 'Ortiz', 'Mora', 'test_a15_dos_atras',
       'scrypt:32768:8:1$ZshV34gGFmJl1s8G$a675f0c4117ce077f4b3320561c431b84726a615327cae96ec1e23e2ebc97e06b898b9a7d6faea1b055ede7bdaaed1f1086f4cb9c8b7482c5d9f22ca2dc88835',
       'test.a15@test.com', false,
       (SELECT id FROM role WHERE name = 'applicant' LIMIT 1),
       false, '2025-03-01'::timestamp, '2025-03-01'::timestamp,
       true, true, NOW(),
       '6566500015', 'Calle Vieja 15', 'TEST150315HJCBB15', '1995-03-15'::date,
       'Contacto Ortiz', '6567500015', 'Hermano',
       false
WHERE NOT EXISTS (SELECT 1 FROM "user" WHERE username = 'test_a15_dos_atras');

INSERT INTO user_program (user_id, program_id, enrollment_date, current_semester,
                          admission_period_id, admission_status, updated_at)
SELECT u.id, (SELECT id FROM program WHERE slug = 'MII'),
       u.registration_date, NULL,
       (SELECT id FROM academic_period WHERE code = '20253'),
       'in_progress', NOW()
FROM "user" u WHERE u.username = 'test_a15_dos_atras'
AND NOT EXISTS (SELECT 1 FROM user_program WHERE user_id = u.id);

-- A15: 2 docs en review (para poder verificar que NO se borren físicamente, sólo
-- se marquen 'expired')
INSERT INTO submission (file_path, status, user_id, archive_id, program_step_id,
                        semester, upload_date, is_in_extension, updated_at)
SELECT 'documents/' || u.id || '/admission/doc_' || sub.aid || '.pdf',
       'review', u.id, sub.aid, sub.psid, NULL,
       '2025-03-15'::timestamp, false, NOW()
FROM "user" u
CROSS JOIN LATERAL (
    SELECT a.id AS aid, ps.id AS psid
    FROM archive a
    JOIN step s ON a.step_id = s.id JOIN phase ph ON s.phase_id = ph.id
    JOIN program_step ps ON ps.step_id = s.id
         AND ps.program_id = (SELECT program_id FROM user_program WHERE user_id = u.id LIMIT 1)
    WHERE ph.name = 'admission' AND a.is_uploadable = true
    ORDER BY a.id LIMIT 2
) sub
WHERE u.username = 'test_a15_dos_atras'
AND NOT EXISTS (SELECT 1 FROM submission s2 WHERE s2.user_id = u.id AND s2.archive_id = sub.aid);


-- ═══════════════════════════════════════════════════════════════════════════════
-- 8.7 Periodo destino para pruebas (20271 — Ene-Jun 2027)
-- Si aún no existe, crearlo cerrado para poder activarse durante la prueba.
-- ═══════════════════════════════════════════════════════════════════════════════
INSERT INTO academic_period (code, name, start_date, end_date, is_active,
                             admission_start_date, admission_end_date,
                             created_at, updated_at)
SELECT '20271', 'Enero - Junio 2027', '2027-01-15'::date, '2027-06-15'::date, false,
       '2026-11-01'::date, '2026-12-15'::date, NOW(), NOW()
WHERE NOT EXISTS (SELECT 1 FROM academic_period WHERE code = '20271');
