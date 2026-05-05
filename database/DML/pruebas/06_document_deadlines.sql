-- =============================================================================
-- 06: Ventanas de entrega (document_deadline) para permanencia
-- =============================================================================
-- Crea ventanas de entrega para el periodo activo (20263) y algunas del periodo
-- anterior (20261) para tener historial. Incluye ventanas CONACyT mensuales.
--
-- Los archives de permanencia uploadables por step:
--   Step  9: Programacion Materias, Boleta Inscripcion, Boleta Calificacion,
--            Solicitud Baja Temporal, Carta Director
--   Step 10: Carta Solicitud, Carta Aceptacion, Carta Terminacion, Informe Final
--   Step 11: Protocolo Investigacion, Plan Actividades, Carta Alta Actividad,
--            Carta Terminacion
--   Step 12: Formato Desempeno
-- =============================================================================


-- ═══════════════════════════════════════════════════════════════════════════════
-- PERIODOS HISTORICOS (20243, 20251, 20253) — generadas en bulk para que TODAS
-- las submissions de permanencia (presentes y pasadas) puedan ligarse a una
-- ventana. Sin esto las inserciones de B1/B2/B3/B5 fallarían bajo el nuevo
-- modelo donde permanencia sólo se entrega vía document_deadline.
-- ═══════════════════════════════════════════════════════════════════════════════
-- 5 archives clave x 3 periodos x 1 programa MII = 15 deadlines
INSERT INTO document_deadline (archive_id, program_id, academic_period_id,
                               sequence, label, opens_at, closes_at, is_open,
                               created_by, created_at, updated_at)
SELECT a.id, p.id, ap.id, 1, a.name,
       (ap.start_date - interval '5 days')::timestamp,
       (ap.end_date - interval '5 days')::timestamp,
       false,
       (SELECT id FROM "user" WHERE username = 'admin'),
       (ap.start_date - interval '10 days')::timestamp,
       NOW()
FROM academic_period ap
CROSS JOIN program p
CROSS JOIN archive a
JOIN step s ON a.step_id = s.id
JOIN phase ph ON s.phase_id = ph.id
WHERE ap.code IN ('20243', '20251', '20253')
  AND p.slug = 'MII'
  AND ph.name = 'permanence'
  AND (a.name ILIKE '%Programacion%Materias%'
       OR a.name ILIKE '%Boleta%Inscripcion%'
       OR a.name ILIKE '%Formato%Desempe%'
       OR a.name ILIKE '%Boleta%Calificacion%'
       OR a.name ILIKE '%Carta%Director%')
  AND a.is_uploadable = true
  AND NOT EXISTS (
      SELECT 1 FROM document_deadline dd
      WHERE dd.archive_id = a.id
        AND dd.program_id = p.id
        AND dd.academic_period_id = ap.id
        AND dd.sequence = 1
  );

-- Mismo bloque para MANI (B5 cursó sem 1 en 20253) — sólo 20253
INSERT INTO document_deadline (archive_id, program_id, academic_period_id,
                               sequence, label, opens_at, closes_at, is_open,
                               created_by, created_at, updated_at)
SELECT a.id, p.id, ap.id, 1, a.name,
       (ap.start_date - interval '5 days')::timestamp,
       (ap.end_date - interval '5 days')::timestamp,
       false,
       (SELECT id FROM "user" WHERE username = 'admin'),
       (ap.start_date - interval '10 days')::timestamp,
       NOW()
FROM academic_period ap
CROSS JOIN program p
CROSS JOIN archive a
JOIN step s ON a.step_id = s.id
JOIN phase ph ON s.phase_id = ph.id
WHERE ap.code = '20253'
  AND p.slug = 'MANI'
  AND ph.name = 'permanence'
  AND (a.name ILIKE '%Programacion%Materias%'
       OR a.name ILIKE '%Boleta%Inscripcion%'
       OR a.name ILIKE '%Formato%Desempe%'
       OR a.name ILIKE '%Boleta%Calificacion%'
       OR a.name ILIKE '%Carta%Director%')
  AND a.is_uploadable = true
  AND NOT EXISTS (
      SELECT 1 FROM document_deadline dd
      WHERE dd.archive_id = a.id
        AND dd.program_id = p.id
        AND dd.academic_period_id = ap.id
        AND dd.sequence = 1
  );


-- ═══════════════════════════════════════════════════════════════════════════════
-- PERIODO ANTERIOR (20261 Ene-Jun 2026) — cerradas, para historial
-- ═══════════════════════════════════════════════════════════════════════════════

-- Programacion de Materias (cerrada, periodo anterior)
INSERT INTO document_deadline (archive_id, program_id, academic_period_id,
                               sequence, label, opens_at, closes_at, is_open,
                               created_by, created_at, updated_at)
SELECT a.id,
       (SELECT id FROM program WHERE slug = 'MII'),
       (SELECT id FROM academic_period WHERE code = '20261'),
       1, 'Programacion de Materias',
       '2026-01-12'::timestamp, '2026-02-12'::timestamp, false,
       (SELECT id FROM "user" WHERE username = 'admin'),
       '2026-01-10'::timestamp, NOW()
FROM archive a
JOIN step s ON a.step_id = s.id JOIN phase ph ON s.phase_id = ph.id
WHERE ph.name = 'permanence' AND a.name ILIKE '%Programacion%Materias%'
AND NOT EXISTS (
    SELECT 1 FROM document_deadline dd
    WHERE dd.archive_id = a.id
      AND dd.program_id = (SELECT id FROM program WHERE slug = 'MII')
      AND dd.academic_period_id = (SELECT id FROM academic_period WHERE code = '20261')
      AND dd.sequence = 1
);

-- Boleta de Inscripcion (cerrada, periodo anterior)
INSERT INTO document_deadline (archive_id, program_id, academic_period_id,
                               sequence, label, opens_at, closes_at, is_open,
                               created_by, created_at, updated_at)
SELECT a.id,
       (SELECT id FROM program WHERE slug = 'MII'),
       (SELECT id FROM academic_period WHERE code = '20261'),
       1, 'Boleta de Inscripcion',
       '2026-01-12'::timestamp, '2026-02-28'::timestamp, false,
       (SELECT id FROM "user" WHERE username = 'admin'),
       '2026-01-10'::timestamp, NOW()
FROM archive a
JOIN step s ON a.step_id = s.id JOIN phase ph ON s.phase_id = ph.id
WHERE ph.name = 'permanence' AND a.name ILIKE '%Boleta%Inscripcion%'
AND NOT EXISTS (
    SELECT 1 FROM document_deadline dd
    WHERE dd.archive_id = a.id
      AND dd.program_id = (SELECT id FROM program WHERE slug = 'MII')
      AND dd.academic_period_id = (SELECT id FROM academic_period WHERE code = '20261')
      AND dd.sequence = 1
);

-- 1er Reporte Semestral (Formato Desempeno, cerrado, periodo anterior)
INSERT INTO document_deadline (archive_id, program_id, academic_period_id,
                               sequence, label, opens_at, closes_at, is_open,
                               created_by, created_at, updated_at)
SELECT a.id,
       (SELECT id FROM program WHERE slug = 'MII'),
       (SELECT id FROM academic_period WHERE code = '20261'),
       1, '1er Reporte Semestral',
       '2026-03-01'::timestamp, '2026-04-15'::timestamp, false,
       (SELECT id FROM "user" WHERE username = 'admin'),
       '2026-02-25'::timestamp, NOW()
FROM archive a
JOIN step s ON a.step_id = s.id JOIN phase ph ON s.phase_id = ph.id
WHERE ph.name = 'permanence' AND a.name ILIKE '%Formato%Desempe%'
AND NOT EXISTS (
    SELECT 1 FROM document_deadline dd
    WHERE dd.archive_id = a.id
      AND dd.program_id = (SELECT id FROM program WHERE slug = 'MII')
      AND dd.academic_period_id = (SELECT id FROM academic_period WHERE code = '20261')
      AND dd.sequence = 1
);

-- Boleta de Calificacion (cerrada, periodo anterior)
INSERT INTO document_deadline (archive_id, program_id, academic_period_id,
                               sequence, label, opens_at, closes_at, is_open,
                               created_by, created_at, updated_at)
SELECT a.id,
       (SELECT id FROM program WHERE slug = 'MII'),
       (SELECT id FROM academic_period WHERE code = '20261'),
       1, 'Boleta de Calificaciones',
       '2026-05-15'::timestamp, '2026-06-12'::timestamp, false,
       (SELECT id FROM "user" WHERE username = 'admin'),
       '2026-05-10'::timestamp, NOW()
FROM archive a
JOIN step s ON a.step_id = s.id JOIN phase ph ON s.phase_id = ph.id
WHERE ph.name = 'permanence' AND a.name ILIKE '%Boleta%Calificacion%'
AND NOT EXISTS (
    SELECT 1 FROM document_deadline dd
    WHERE dd.archive_id = a.id
      AND dd.program_id = (SELECT id FROM program WHERE slug = 'MII')
      AND dd.academic_period_id = (SELECT id FROM academic_period WHERE code = '20261')
      AND dd.sequence = 1
);


-- ═══════════════════════════════════════════════════════════════════════════════
-- PERIODO ACTIVO (20263 Ago-Dic 2026) — ventanas principales
-- ═══════════════════════════════════════════════════════════════════════════════

-- Programacion de Materias (abierta, cierra 1 mes despues del inicio)
INSERT INTO document_deadline (archive_id, program_id, academic_period_id,
                               sequence, label, opens_at, closes_at, is_open,
                               created_by, created_at, updated_at)
SELECT a.id,
       (SELECT id FROM program WHERE slug = 'MII'),
       (SELECT id FROM academic_period WHERE code = '20263'),
       1, 'Programacion de Materias',
       '2026-08-10'::timestamp, '2026-09-10'::timestamp, true,
       (SELECT id FROM "user" WHERE username = 'admin'),
       '2026-08-05'::timestamp, NOW()
FROM archive a
JOIN step s ON a.step_id = s.id JOIN phase ph ON s.phase_id = ph.id
WHERE ph.name = 'permanence' AND a.name ILIKE '%Programacion%Materias%'
AND NOT EXISTS (
    SELECT 1 FROM document_deadline dd
    WHERE dd.archive_id = a.id
      AND dd.program_id = (SELECT id FROM program WHERE slug = 'MII')
      AND dd.academic_period_id = (SELECT id FROM academic_period WHERE code = '20263')
      AND dd.sequence = 1
);

-- Boleta de Inscripcion (abierta, cierra 2 meses despues del inicio)
INSERT INTO document_deadline (archive_id, program_id, academic_period_id,
                               sequence, label, opens_at, closes_at, is_open,
                               created_by, created_at, updated_at)
SELECT a.id,
       (SELECT id FROM program WHERE slug = 'MII'),
       (SELECT id FROM academic_period WHERE code = '20263'),
       1, 'Boleta de Inscripcion',
       '2026-08-10'::timestamp, '2026-10-10'::timestamp, true,
       (SELECT id FROM "user" WHERE username = 'admin'),
       '2026-08-05'::timestamp, NOW()
FROM archive a
JOIN step s ON a.step_id = s.id JOIN phase ph ON s.phase_id = ph.id
WHERE ph.name = 'permanence' AND a.name ILIKE '%Boleta%Inscripcion%'
AND NOT EXISTS (
    SELECT 1 FROM document_deadline dd
    WHERE dd.archive_id = a.id
      AND dd.program_id = (SELECT id FROM program WHERE slug = 'MII')
      AND dd.academic_period_id = (SELECT id FROM academic_period WHERE code = '20263')
      AND dd.sequence = 1
);

-- 1er Reporte Semestral (Formato Desempeno, abierta a mitad de semestre)
INSERT INTO document_deadline (archive_id, program_id, academic_period_id,
                               sequence, label, opens_at, closes_at, is_open,
                               created_by, created_at, updated_at)
SELECT a.id,
       (SELECT id FROM program WHERE slug = 'MII'),
       (SELECT id FROM academic_period WHERE code = '20263'),
       1, '1er Reporte Semestral',
       '2026-10-01'::timestamp, '2026-11-15'::timestamp, true,
       (SELECT id FROM "user" WHERE username = 'admin'),
       '2026-09-25'::timestamp, NOW()
FROM archive a
JOIN step s ON a.step_id = s.id JOIN phase ph ON s.phase_id = ph.id
WHERE ph.name = 'permanence' AND a.name ILIKE '%Formato%Desempe%'
AND NOT EXISTS (
    SELECT 1 FROM document_deadline dd
    WHERE dd.archive_id = a.id
      AND dd.program_id = (SELECT id FROM program WHERE slug = 'MII')
      AND dd.academic_period_id = (SELECT id FROM academic_period WHERE code = '20263')
      AND dd.sequence = 1
);

-- Boleta de Calificacion (abierta al final del semestre)
INSERT INTO document_deadline (archive_id, program_id, academic_period_id,
                               sequence, label, opens_at, closes_at, is_open,
                               created_by, created_at, updated_at)
SELECT a.id,
       (SELECT id FROM program WHERE slug = 'MII'),
       (SELECT id FROM academic_period WHERE code = '20263'),
       1, 'Boleta de Calificaciones',
       '2026-11-15'::timestamp, '2026-12-11'::timestamp, true,
       (SELECT id FROM "user" WHERE username = 'admin'),
       '2026-11-10'::timestamp, NOW()
FROM archive a
JOIN step s ON a.step_id = s.id JOIN phase ph ON s.phase_id = ph.id
WHERE ph.name = 'permanence' AND a.name ILIKE '%Boleta%Calificacion%'
AND NOT EXISTS (
    SELECT 1 FROM document_deadline dd
    WHERE dd.archive_id = a.id
      AND dd.program_id = (SELECT id FROM program WHERE slug = 'MII')
      AND dd.academic_period_id = (SELECT id FROM academic_period WHERE code = '20263')
      AND dd.sequence = 1
);

-- Carta Director (abierta todo el semestre, sin fecha limite)
INSERT INTO document_deadline (archive_id, program_id, academic_period_id,
                               sequence, label, opens_at, closes_at, is_open,
                               created_by, created_at, updated_at)
SELECT a.id,
       (SELECT id FROM program WHERE slug = 'MII'),
       (SELECT id FROM academic_period WHERE code = '20263'),
       1, 'Carta de Director de Tesis',
       '2026-08-10'::timestamp, NULL, true,
       (SELECT id FROM "user" WHERE username = 'admin'),
       '2026-08-05'::timestamp, NOW()
FROM archive a
JOIN step s ON a.step_id = s.id JOIN phase ph ON s.phase_id = ph.id
WHERE ph.name = 'permanence' AND a.name ILIKE '%Carta%Director%'
AND NOT EXISTS (
    SELECT 1 FROM document_deadline dd
    WHERE dd.archive_id = a.id
      AND dd.program_id = (SELECT id FROM program WHERE slug = 'MII')
      AND dd.academic_period_id = (SELECT id FROM academic_period WHERE code = '20263')
      AND dd.sequence = 1
);


-- ═══════════════════════════════════════════════════════════════════════════════
-- VENTANAS CONACyT MENSUALES (periodo activo 20263)
-- ═══════════════════════════════════════════════════════════════════════════════
-- Para becarios CONACyT se requiere un reporte mensual (Formato Desempeno).
-- Cada mes tiene su propia ventana con sequence = mes (8=Ago, 9=Sep, etc.)

-- Agosto 2026 (ya cerrada, para probar historial)
INSERT INTO document_deadline (archive_id, program_id, academic_period_id,
                               sequence, label, opens_at, closes_at, is_open,
                               created_by, created_at, updated_at)
SELECT a.id,
       (SELECT id FROM program WHERE slug = 'MII'),
       (SELECT id FROM academic_period WHERE code = '20263'),
       8, 'Formato CONACyT - Agosto',
       '2026-08-01'::timestamp, '2026-08-31'::timestamp, false,
       (SELECT id FROM "user" WHERE username = 'admin'),
       '2026-08-01'::timestamp, NOW()
FROM archive a
JOIN step s ON a.step_id = s.id JOIN phase ph ON s.phase_id = ph.id
WHERE ph.name = 'permanence' AND a.name ILIKE '%Formato%Desempe%'
AND NOT EXISTS (
    SELECT 1 FROM document_deadline dd
    WHERE dd.archive_id = a.id
      AND dd.program_id = (SELECT id FROM program WHERE slug = 'MII')
      AND dd.academic_period_id = (SELECT id FROM academic_period WHERE code = '20263')
      AND dd.sequence = 8
);

-- Septiembre 2026 (ya cerrada)
INSERT INTO document_deadline (archive_id, program_id, academic_period_id,
                               sequence, label, opens_at, closes_at, is_open,
                               created_by, created_at, updated_at)
SELECT a.id,
       (SELECT id FROM program WHERE slug = 'MII'),
       (SELECT id FROM academic_period WHERE code = '20263'),
       9, 'Formato CONACyT - Septiembre',
       '2026-09-01'::timestamp, '2026-09-30'::timestamp, false,
       (SELECT id FROM "user" WHERE username = 'admin'),
       '2026-09-01'::timestamp, NOW()
FROM archive a
JOIN step s ON a.step_id = s.id JOIN phase ph ON s.phase_id = ph.id
WHERE ph.name = 'permanence' AND a.name ILIKE '%Formato%Desempe%'
AND NOT EXISTS (
    SELECT 1 FROM document_deadline dd
    WHERE dd.archive_id = a.id
      AND dd.program_id = (SELECT id FROM program WHERE slug = 'MII')
      AND dd.academic_period_id = (SELECT id FROM academic_period WHERE code = '20263')
      AND dd.sequence = 9
);

-- Octubre 2026 (abierta actualmente — hoy es abril 2026 en datos, pero
-- la simulamos como abierta para probar el flujo)
INSERT INTO document_deadline (archive_id, program_id, academic_period_id,
                               sequence, label, opens_at, closes_at, is_open,
                               created_by, created_at, updated_at)
SELECT a.id,
       (SELECT id FROM program WHERE slug = 'MII'),
       (SELECT id FROM academic_period WHERE code = '20263'),
       10, 'Formato CONACyT - Octubre',
       '2026-10-01'::timestamp, '2026-10-31'::timestamp, true,
       (SELECT id FROM "user" WHERE username = 'admin'),
       '2026-10-01'::timestamp, NOW()
FROM archive a
JOIN step s ON a.step_id = s.id JOIN phase ph ON s.phase_id = ph.id
WHERE ph.name = 'permanence' AND a.name ILIKE '%Formato%Desempe%'
AND NOT EXISTS (
    SELECT 1 FROM document_deadline dd
    WHERE dd.archive_id = a.id
      AND dd.program_id = (SELECT id FROM program WHERE slug = 'MII')
      AND dd.academic_period_id = (SELECT id FROM academic_period WHERE code = '20263')
      AND dd.sequence = 10
);

-- Noviembre 2026 (futura, abierta)
INSERT INTO document_deadline (archive_id, program_id, academic_period_id,
                               sequence, label, opens_at, closes_at, is_open,
                               created_by, created_at, updated_at)
SELECT a.id,
       (SELECT id FROM program WHERE slug = 'MII'),
       (SELECT id FROM academic_period WHERE code = '20263'),
       11, 'Formato CONACyT - Noviembre',
       '2026-11-01'::timestamp, '2026-11-30'::timestamp, true,
       (SELECT id FROM "user" WHERE username = 'admin'),
       '2026-11-01'::timestamp, NOW()
FROM archive a
JOIN step s ON a.step_id = s.id JOIN phase ph ON s.phase_id = ph.id
WHERE ph.name = 'permanence' AND a.name ILIKE '%Formato%Desempe%'
AND NOT EXISTS (
    SELECT 1 FROM document_deadline dd
    WHERE dd.archive_id = a.id
      AND dd.program_id = (SELECT id FROM program WHERE slug = 'MII')
      AND dd.academic_period_id = (SELECT id FROM academic_period WHERE code = '20263')
      AND dd.sequence = 11
);

-- Diciembre 2026 (futura, abierta)
INSERT INTO document_deadline (archive_id, program_id, academic_period_id,
                               sequence, label, opens_at, closes_at, is_open,
                               created_by, created_at, updated_at)
SELECT a.id,
       (SELECT id FROM program WHERE slug = 'MII'),
       (SELECT id FROM academic_period WHERE code = '20263'),
       12, 'Formato CONACyT - Diciembre',
       '2026-12-01'::timestamp, '2026-12-11'::timestamp, true,
       (SELECT id FROM "user" WHERE username = 'admin'),
       '2026-12-01'::timestamp, NOW()
FROM archive a
JOIN step s ON a.step_id = s.id JOIN phase ph ON s.phase_id = ph.id
WHERE ph.name = 'permanence' AND a.name ILIKE '%Formato%Desempe%'
AND NOT EXISTS (
    SELECT 1 FROM document_deadline dd
    WHERE dd.archive_id = a.id
      AND dd.program_id = (SELECT id FROM program WHERE slug = 'MII')
      AND dd.academic_period_id = (SELECT id FROM academic_period WHERE code = '20263')
      AND dd.sequence = 12
);


-- ═══════════════════════════════════════════════════════════════════════════════
-- VENTANAS PARA PROGRAMA MANI (B5 esta en MANI)
-- ═��═════════════════════════════════════════════════════════════════════════════

-- Programacion de Materias MANI (periodo activo)
INSERT INTO document_deadline (archive_id, program_id, academic_period_id,
                               sequence, label, opens_at, closes_at, is_open,
                               created_by, created_at, updated_at)
SELECT a.id,
       (SELECT id FROM program WHERE slug = 'MANI'),
       (SELECT id FROM academic_period WHERE code = '20263'),
       1, 'Programacion de Materias',
       '2026-08-10'::timestamp, '2026-09-10'::timestamp, true,
       (SELECT id FROM "user" WHERE username = 'admin'),
       '2026-08-05'::timestamp, NOW()
FROM archive a
JOIN step s ON a.step_id = s.id JOIN phase ph ON s.phase_id = ph.id
WHERE ph.name = 'permanence' AND a.name ILIKE '%Programacion%Materias%'
AND NOT EXISTS (
    SELECT 1 FROM document_deadline dd
    WHERE dd.archive_id = a.id
      AND dd.program_id = (SELECT id FROM program WHERE slug = 'MANI')
      AND dd.academic_period_id = (SELECT id FROM academic_period WHERE code = '20263')
      AND dd.sequence = 1
);

-- Boleta de Inscripcion MANI (periodo activo)
INSERT INTO document_deadline (archive_id, program_id, academic_period_id,
                               sequence, label, opens_at, closes_at, is_open,
                               created_by, created_at, updated_at)
SELECT a.id,
       (SELECT id FROM program WHERE slug = 'MANI'),
       (SELECT id FROM academic_period WHERE code = '20263'),
       1, 'Boleta de Inscripcion',
       '2026-08-10'::timestamp, '2026-10-10'::timestamp, true,
       (SELECT id FROM "user" WHERE username = 'admin'),
       '2026-08-05'::timestamp, NOW()
FROM archive a
JOIN step s ON a.step_id = s.id JOIN phase ph ON s.phase_id = ph.id
WHERE ph.name = 'permanence' AND a.name ILIKE '%Boleta%Inscripcion%'
AND NOT EXISTS (
    SELECT 1 FROM document_deadline dd
    WHERE dd.archive_id = a.id
      AND dd.program_id = (SELECT id FROM program WHERE slug = 'MANI')
      AND dd.academic_period_id = (SELECT id FROM academic_period WHERE code = '20263')
      AND dd.sequence = 1
);

-- 1er Reporte MANI (periodo activo)
INSERT INTO document_deadline (archive_id, program_id, academic_period_id,
                               sequence, label, opens_at, closes_at, is_open,
                               created_by, created_at, updated_at)
SELECT a.id,
       (SELECT id FROM program WHERE slug = 'MANI'),
       (SELECT id FROM academic_period WHERE code = '20263'),
       1, '1er Reporte Semestral',
       '2026-10-01'::timestamp, '2026-11-15'::timestamp, true,
       (SELECT id FROM "user" WHERE username = 'admin'),
       '2026-09-25'::timestamp, NOW()
FROM archive a
JOIN step s ON a.step_id = s.id JOIN phase ph ON s.phase_id = ph.id
WHERE ph.name = 'permanence' AND a.name ILIKE '%Formato%Desempe%'
AND NOT EXISTS (
    SELECT 1 FROM document_deadline dd
    WHERE dd.archive_id = a.id
      AND dd.program_id = (SELECT id FROM program WHERE slug = 'MANI')
      AND dd.academic_period_id = (SELECT id FROM academic_period WHERE code = '20263')
      AND dd.sequence = 1
);
