-- =============================================================================
-- 07: Eventos de entrevista, ventanas, slots y appointments
-- =============================================================================
-- Estructura:
--   Event (tipo interview, capacity_type=single, 1 por programa)
--     → EventWindow (fecha + rango horario)
--       → EventSlot (slots individuales de 30 min)
--         → Appointment (asignacion aspirante ↔ slot)
--
-- Eventos creados:
--   HISTORICOS (periodos anteriores, status=completed):
--     - MII  periodo 20243: para B1 y B2 (entrevistas done)
--     - MII  periodo 20253: para B3 y B4 (entrevistas done)
--     - MANI periodo 20253: para B5 (entrevista done)
--   ACTUALES (periodo 20263, status=published):
--     - MII  periodo 20263: para A3(sin asignar), A4, A5-equiv, A9, A10, A11
--     - MANI periodo 20263: para A5, A12
--
-- Aspirantes con entrevista completada (done):
--   A4 (rechazado parcial), A5 (rechazado total), A9 (aceptado no paga),
--   A10 (aceptado listo), A11 (diferido 1x), A12 (diferido 2x)
--   B1, B2, B3, B4, B5 (estudiantes — historico)
--
-- Aspirantes SIN entrevista:
--   A1 (nuevo), A2 (parcial), A3 (listo, elegible pero sin asignar),
--   A6 (prorroga), A7 (prorroga vencida), A8 (viejo), A13 (doc vencido)
-- =============================================================================


-- ═══════════════════════════════════════════════════════════════════════════════
-- EVENTO HISTORICO MII — Periodo 20243 (Ago-Dic 2024)
-- Para B1 (Nicolas Torres) y B2 (Olivia Salazar)
-- ═══════════════════════════════════════════════════════════════════════════════

INSERT INTO event (program_id, academic_period_id, type, title, description, location,
                   created_by, visible_to_students, capacity_type,
                   requires_registration, allows_attendance_tracking, status, created_at, updated_at)
SELECT
    (SELECT id FROM program WHERE slug = 'MII'),
    (SELECT id FROM academic_period WHERE code = '20243'),
    'interview',
    'Entrevistas Admision MII — Ago-Dic 2024',
    'Entrevistas individuales para aspirantes al programa MII periodo 20243',
    'Edificio de Posgrado, Sala 101',
    (SELECT id FROM "user" WHERE username = 'admin'),
    false, 'single', true, false, 'completed',
    '2024-07-01'::timestamp, '2024-08-01'::timestamp
WHERE NOT EXISTS (
    SELECT 1 FROM event WHERE title = 'Entrevistas Admision MII — Ago-Dic 2024'
);

-- Window: 25 julio 2024, 09:00-17:00, slots de 30 min
INSERT INTO event_window (event_id, date, start_time, end_time, slot_minutes,
                          slots_generated, current_capacity, created_at, updated_at)
SELECT e.id, '2024-07-25'::date, '09:00'::time, '17:00'::time, 30,
       true, 16, '2024-07-01'::timestamp, '2024-07-25'::timestamp
FROM event e WHERE e.title = 'Entrevistas Admision MII — Ago-Dic 2024'
AND NOT EXISTS (
    SELECT 1 FROM event_window ew WHERE ew.event_id = e.id AND ew.date = '2024-07-25'
);

-- Slots para B1 y B2 (solo 2 slots booked de los 16 posibles)
-- Slot 1: 09:00-09:30 → B1
INSERT INTO event_slot (event_window_id, starts_at, ends_at, status, created_at, updated_at)
SELECT ew.id,
       '2024-07-25 09:00'::timestamp, '2024-07-25 09:30'::timestamp,
       'booked', '2024-07-01'::timestamp, '2024-07-25'::timestamp
FROM event_window ew
JOIN event e ON ew.event_id = e.id
WHERE e.title = 'Entrevistas Admision MII — Ago-Dic 2024' AND ew.date = '2024-07-25'
AND NOT EXISTS (
    SELECT 1 FROM event_slot es WHERE es.event_window_id = ew.id
        AND es.starts_at = '2024-07-25 09:00'::timestamp
);

-- Slot 2: 09:30-10:00 → B2
INSERT INTO event_slot (event_window_id, starts_at, ends_at, status, created_at, updated_at)
SELECT ew.id,
       '2024-07-25 09:30'::timestamp, '2024-07-25 10:00'::timestamp,
       'booked', '2024-07-01'::timestamp, '2024-07-25'::timestamp
FROM event_window ew
JOIN event e ON ew.event_id = e.id
WHERE e.title = 'Entrevistas Admision MII — Ago-Dic 2024' AND ew.date = '2024-07-25'
AND NOT EXISTS (
    SELECT 1 FROM event_slot es WHERE es.event_window_id = ew.id
        AND es.starts_at = '2024-07-25 09:30'::timestamp
);

-- Appointment B1: done
INSERT INTO appointment (event_id, slot_id, applicant_id, assigned_by, status, notes,
                         created_at, updated_at)
SELECT e.id, es.id,
       (SELECT id FROM "user" WHERE username = 'M24110001'),
       (SELECT id FROM "user" WHERE username = 'admin'),
       'done', 'Entrevista completada satisfactoriamente. Excelente perfil academico.',
       '2024-07-20'::timestamp, '2024-07-25'::timestamp
FROM event e
JOIN event_window ew ON ew.event_id = e.id
JOIN event_slot es ON es.event_window_id = ew.id
WHERE e.title = 'Entrevistas Admision MII — Ago-Dic 2024'
  AND es.starts_at = '2024-07-25 09:00'::timestamp
AND NOT EXISTS (
    SELECT 1 FROM appointment a WHERE a.slot_id = es.id
);

-- Appointment B2: done
INSERT INTO appointment (event_id, slot_id, applicant_id, assigned_by, status, notes,
                         created_at, updated_at)
SELECT e.id, es.id,
       (SELECT id FROM "user" WHERE username = 'M24110002'),
       (SELECT id FROM "user" WHERE username = 'admin'),
       'done', 'Entrevista completada. Buen candidato, aceptada con observaciones sobre documentacion pendiente.',
       '2024-07-20'::timestamp, '2024-07-25'::timestamp
FROM event e
JOIN event_window ew ON ew.event_id = e.id
JOIN event_slot es ON es.event_window_id = ew.id
WHERE e.title = 'Entrevistas Admision MII — Ago-Dic 2024'
  AND es.starts_at = '2024-07-25 09:30'::timestamp
AND NOT EXISTS (
    SELECT 1 FROM appointment a WHERE a.slot_id = es.id
);


-- ═══════════════════════════════════════════════════════════════════════════════
-- EVENTO HISTORICO MII — Periodo 20253 (Ago-Dic 2025)
-- Para B3 (Pablo Cruz) y B4 (Raquel Vega)
-- ═══════════════════════════════════════════════════════════════════════════════

INSERT INTO event (program_id, academic_period_id, type, title, description, location,
                   created_by, visible_to_students, capacity_type,
                   requires_registration, allows_attendance_tracking, status, created_at, updated_at)
SELECT
    (SELECT id FROM program WHERE slug = 'MII'),
    (SELECT id FROM academic_period WHERE code = '20253'),
    'interview',
    'Entrevistas Admision MII — Ago-Dic 2025',
    'Entrevistas individuales para aspirantes al programa MII periodo 20253',
    'Edificio de Posgrado, Sala 101',
    (SELECT id FROM "user" WHERE username = 'admin'),
    false, 'single', true, false, 'completed',
    '2025-07-01'::timestamp, '2025-08-01'::timestamp
WHERE NOT EXISTS (
    SELECT 1 FROM event WHERE title = 'Entrevistas Admision MII — Ago-Dic 2025'
);

-- Window: 28 julio 2025, 09:00-17:00
INSERT INTO event_window (event_id, date, start_time, end_time, slot_minutes,
                          slots_generated, current_capacity, created_at, updated_at)
SELECT e.id, '2025-07-28'::date, '09:00'::time, '17:00'::time, 30,
       true, 16, '2025-07-01'::timestamp, '2025-07-28'::timestamp
FROM event e WHERE e.title = 'Entrevistas Admision MII — Ago-Dic 2025'
AND NOT EXISTS (
    SELECT 1 FROM event_window ew WHERE ew.event_id = e.id AND ew.date = '2025-07-28'
);

-- Slots para B3 y B4
INSERT INTO event_slot (event_window_id, starts_at, ends_at, status, created_at, updated_at)
SELECT ew.id,
       ('2025-07-28 ' || v.st)::timestamp, ('2025-07-28 ' || v.et)::timestamp,
       'booked', '2025-07-01'::timestamp, '2025-07-28'::timestamp
FROM event_window ew
JOIN event e ON ew.event_id = e.id
CROSS JOIN (VALUES ('09:00', '09:30'), ('09:30', '10:00')) AS v(st, et)
WHERE e.title = 'Entrevistas Admision MII — Ago-Dic 2025' AND ew.date = '2025-07-28'
AND NOT EXISTS (
    SELECT 1 FROM event_slot es WHERE es.event_window_id = ew.id
        AND es.starts_at = ('2025-07-28 ' || v.st)::timestamp
);

-- Appointment B3: done
INSERT INTO appointment (event_id, slot_id, applicant_id, assigned_by, status, notes,
                         created_at, updated_at)
SELECT e.id, es.id,
       (SELECT id FROM "user" WHERE username = 'M25110001'),
       (SELECT id FROM "user" WHERE username = 'admin'),
       'done', 'Entrevista completada. Candidato aceptado.',
       '2025-07-22'::timestamp, '2025-07-28'::timestamp
FROM event e
JOIN event_window ew ON ew.event_id = e.id
JOIN event_slot es ON es.event_window_id = ew.id
WHERE e.title = 'Entrevistas Admision MII — Ago-Dic 2025'
  AND es.starts_at = '2025-07-28 09:00'::timestamp
AND NOT EXISTS (SELECT 1 FROM appointment a WHERE a.slot_id = es.id);

-- Appointment B4: done
INSERT INTO appointment (event_id, slot_id, applicant_id, assigned_by, status, notes,
                         created_at, updated_at)
SELECT e.id, es.id,
       (SELECT id FROM "user" WHERE username = 'M25110002'),
       (SELECT id FROM "user" WHERE username = 'admin'),
       'done', 'Entrevista completada. Candidata aceptada.',
       '2025-07-22'::timestamp, '2025-07-28'::timestamp
FROM event e
JOIN event_window ew ON ew.event_id = e.id
JOIN event_slot es ON es.event_window_id = ew.id
WHERE e.title = 'Entrevistas Admision MII — Ago-Dic 2025'
  AND es.starts_at = '2025-07-28 09:30'::timestamp
AND NOT EXISTS (SELECT 1 FROM appointment a WHERE a.slot_id = es.id);


-- ═══════════════════════════════════════════════════════════════════════════════
-- EVENTO HISTORICO MANI — Periodo 20253 (Ago-Dic 2025)
-- Para B5 (Samuel Luna)
-- ═══════════════════════════════════════════════════════════════════════════════

INSERT INTO event (program_id, academic_period_id, type, title, description, location,
                   created_by, visible_to_students, capacity_type,
                   requires_registration, allows_attendance_tracking, status, created_at, updated_at)
SELECT
    (SELECT id FROM program WHERE slug = 'MANI'),
    (SELECT id FROM academic_period WHERE code = '20253'),
    'interview',
    'Entrevistas Admision MANI — Ago-Dic 2025',
    'Entrevistas individuales para aspirantes al programa MANI periodo 20253',
    'Edificio de Posgrado, Sala 203',
    (SELECT id FROM "user" WHERE username = 'admin'),
    false, 'single', true, false, 'completed',
    '2025-07-01'::timestamp, '2025-08-01'::timestamp
WHERE NOT EXISTS (
    SELECT 1 FROM event WHERE title = 'Entrevistas Admision MANI — Ago-Dic 2025'
);

-- Window: 30 julio 2025
INSERT INTO event_window (event_id, date, start_time, end_time, slot_minutes,
                          slots_generated, current_capacity, created_at, updated_at)
SELECT e.id, '2025-07-30'::date, '09:00'::time, '13:00'::time, 30,
       true, 8, '2025-07-01'::timestamp, '2025-07-30'::timestamp
FROM event e WHERE e.title = 'Entrevistas Admision MANI — Ago-Dic 2025'
AND NOT EXISTS (
    SELECT 1 FROM event_window ew WHERE ew.event_id = e.id AND ew.date = '2025-07-30'
);

-- Slot para B5
INSERT INTO event_slot (event_window_id, starts_at, ends_at, status, created_at, updated_at)
SELECT ew.id,
       '2025-07-30 09:00'::timestamp, '2025-07-30 09:30'::timestamp,
       'booked', '2025-07-01'::timestamp, '2025-07-30'::timestamp
FROM event_window ew
JOIN event e ON ew.event_id = e.id
WHERE e.title = 'Entrevistas Admision MANI — Ago-Dic 2025' AND ew.date = '2025-07-30'
AND NOT EXISTS (
    SELECT 1 FROM event_slot es WHERE es.event_window_id = ew.id
        AND es.starts_at = '2025-07-30 09:00'::timestamp
);

-- Appointment B5: done
INSERT INTO appointment (event_id, slot_id, applicant_id, assigned_by, status, notes,
                         created_at, updated_at)
SELECT e.id, es.id,
       (SELECT id FROM "user" WHERE username = 'M25110003'),
       (SELECT id FROM "user" WHERE username = 'admin'),
       'done', 'Entrevista completada. Candidato aceptado al programa MANI.',
       '2025-07-25'::timestamp, '2025-07-30'::timestamp
FROM event e
JOIN event_window ew ON ew.event_id = e.id
JOIN event_slot es ON es.event_window_id = ew.id
WHERE e.title = 'Entrevistas Admision MANI — Ago-Dic 2025'
  AND es.starts_at = '2025-07-30 09:00'::timestamp
AND NOT EXISTS (SELECT 1 FROM appointment a WHERE a.slot_id = es.id);


-- ═══════════════════════════════════════════════════════════════════════════════
-- EVENTO ACTUAL MII — Periodo 20263 (Ago-Dic 2026)
-- Aspirantes: A3 (elegible sin asignar), A4, A9, A10, A11
-- ═══════════════════════════════════════════════════════════════════════════════

INSERT INTO event (program_id, academic_period_id, type, title, description, location,
                   created_by, visible_to_students, capacity_type,
                   requires_registration, allows_attendance_tracking, status, created_at, updated_at)
SELECT
    (SELECT id FROM program WHERE slug = 'MII'),
    (SELECT id FROM academic_period WHERE code = '20263'),
    'interview',
    'Entrevistas Admision MII — Ago-Dic 2026',
    'Entrevistas individuales para aspirantes al programa MII periodo 20263. Presentarse 10 minutos antes con identificacion oficial.',
    'Edificio de Posgrado, Sala 101',
    (SELECT id FROM "user" WHERE username = 'admin'),
    true, 'single', true, false, 'published',
    '2026-06-15'::timestamp, NOW()
WHERE NOT EXISTS (
    SELECT 1 FROM event WHERE title = 'Entrevistas Admision MII — Ago-Dic 2026'
);

-- Window 1: 20 julio 2026, 09:00-17:00 (dia completo, 16 slots)
INSERT INTO event_window (event_id, date, start_time, end_time, slot_minutes,
                          slots_generated, current_capacity, created_at, updated_at)
SELECT e.id, '2026-07-20'::date, '09:00'::time, '17:00'::time, 30,
       true, 16, '2026-06-15'::timestamp, NOW()
FROM event e WHERE e.title = 'Entrevistas Admision MII — Ago-Dic 2026'
AND NOT EXISTS (
    SELECT 1 FROM event_window ew WHERE ew.event_id = e.id AND ew.date = '2026-07-20'
);

-- Window 2: 21 julio 2026 (dia extra si se necesitan mas slots)
INSERT INTO event_window (event_id, date, start_time, end_time, slot_minutes,
                          slots_generated, current_capacity, created_at, updated_at)
SELECT e.id, '2026-07-21'::date, '09:00'::time, '13:00'::time, 30,
       true, 8, '2026-06-15'::timestamp, NOW()
FROM event e WHERE e.title = 'Entrevistas Admision MII — Ago-Dic 2026'
AND NOT EXISTS (
    SELECT 1 FROM event_window ew WHERE ew.event_id = e.id AND ew.date = '2026-07-21'
);

-- Generar slots para window 1 (dia 20): 16 slots de 30 min cada uno
-- Solo generamos los que se necesitan (5 booked + algunos free para A3)
INSERT INTO event_slot (event_window_id, starts_at, ends_at, status, created_at, updated_at)
SELECT ew.id,
       ('2026-07-20 ' || v.st)::timestamp,
       ('2026-07-20 ' || v.et)::timestamp,
       v.slot_status,
       '2026-06-15'::timestamp, NOW()
FROM event_window ew
JOIN event e ON ew.event_id = e.id
CROSS JOIN (VALUES
    -- Slots booked (asignados a aspirantes)
    ('09:00', '09:30', 'booked'),   -- A4
    ('09:30', '10:00', 'booked'),   -- A9
    ('10:00', '10:30', 'booked'),   -- A10
    ('10:30', '11:00', 'booked'),   -- A11
    -- Slots libres (A3 puede ser asignado a uno de estos)
    ('11:00', '11:30', 'free'),
    ('11:30', '12:00', 'free'),
    ('12:00', '12:30', 'free'),
    ('12:30', '13:00', 'free'),
    ('14:00', '14:30', 'free'),
    ('14:30', '15:00', 'free'),
    ('15:00', '15:30', 'free'),
    ('15:30', '16:00', 'free'),
    ('16:00', '16:30', 'free'),
    ('16:30', '17:00', 'free')
) AS v(st, et, slot_status)
WHERE e.title = 'Entrevistas Admision MII — Ago-Dic 2026' AND ew.date = '2026-07-20'
AND NOT EXISTS (
    SELECT 1 FROM event_slot es WHERE es.event_window_id = ew.id
        AND es.starts_at = ('2026-07-20 ' || v.st)::timestamp
);

-- Generar slots para window 2 (dia 21): 8 slots free
INSERT INTO event_slot (event_window_id, starts_at, ends_at, status, created_at, updated_at)
SELECT ew.id,
       ('2026-07-21 ' || v.st)::timestamp,
       ('2026-07-21 ' || v.et)::timestamp,
       'free',
       '2026-06-15'::timestamp, NOW()
FROM event_window ew
JOIN event e ON ew.event_id = e.id
CROSS JOIN (VALUES
    ('09:00', '09:30'), ('09:30', '10:00'), ('10:00', '10:30'), ('10:30', '11:00'),
    ('11:00', '11:30'), ('11:30', '12:00'), ('12:00', '12:30'), ('12:30', '13:00')
) AS v(st, et)
WHERE e.title = 'Entrevistas Admision MII — Ago-Dic 2026' AND ew.date = '2026-07-21'
AND NOT EXISTS (
    SELECT 1 FROM event_slot es WHERE es.event_window_id = ew.id
        AND es.starts_at = ('2026-07-21 ' || v.st)::timestamp
);

-- ── Appointments MII periodo actual ────────────────────────────────────────

-- A4 (rechazado parcial): entrevista done
INSERT INTO appointment (event_id, slot_id, applicant_id, assigned_by, status, notes,
                         created_at, updated_at)
SELECT e.id, es.id,
       (SELECT id FROM "user" WHERE username = 'test_a04_rech_parcial'),
       (SELECT id FROM "user" WHERE username = 'admin'),
       'done', 'Entrevista realizada. Documentacion incompleta, se requiere correccion del titulo.',
       '2026-07-15'::timestamp, '2026-07-20'::timestamp
FROM event e
JOIN event_window ew ON ew.event_id = e.id
JOIN event_slot es ON es.event_window_id = ew.id
WHERE e.title = 'Entrevistas Admision MII — Ago-Dic 2026'
  AND es.starts_at = '2026-07-20 09:00'::timestamp
AND NOT EXISTS (SELECT 1 FROM appointment a WHERE a.slot_id = es.id);

-- A9 (aceptado no paga): entrevista done
INSERT INTO appointment (event_id, slot_id, applicant_id, assigned_by, status, notes,
                         created_at, updated_at)
SELECT e.id, es.id,
       (SELECT id FROM "user" WHERE username = 'test_a09_acept_nopaga'),
       (SELECT id FROM "user" WHERE username = 'admin'),
       'done', 'Entrevista satisfactoria. Candidata aceptada, pendiente boleta de inscripcion.',
       '2026-07-15'::timestamp, '2026-07-20'::timestamp
FROM event e
JOIN event_window ew ON ew.event_id = e.id
JOIN event_slot es ON es.event_window_id = ew.id
WHERE e.title = 'Entrevistas Admision MII — Ago-Dic 2026'
  AND es.starts_at = '2026-07-20 09:30'::timestamp
AND NOT EXISTS (SELECT 1 FROM appointment a WHERE a.slot_id = es.id);

-- A10 (aceptado listo): entrevista done
INSERT INTO appointment (event_id, slot_id, applicant_id, assigned_by, status, notes,
                         created_at, updated_at)
SELECT e.id, es.id,
       (SELECT id FROM "user" WHERE username = 'test_a10_acept_listo'),
       (SELECT id FROM "user" WHERE username = 'admin'),
       'done', 'Excelente entrevista. Perfil sobresaliente, aceptado inmediatamente.',
       '2026-07-15'::timestamp, '2026-07-20'::timestamp
FROM event e
JOIN event_window ew ON ew.event_id = e.id
JOIN event_slot es ON es.event_window_id = ew.id
WHERE e.title = 'Entrevistas Admision MII — Ago-Dic 2026'
  AND es.starts_at = '2026-07-20 10:00'::timestamp
AND NOT EXISTS (SELECT 1 FROM appointment a WHERE a.slot_id = es.id);

-- A11 (diferido 1x): entrevista done (fue entrevistada antes de diferir)
INSERT INTO appointment (event_id, slot_id, applicant_id, assigned_by, status, notes,
                         created_at, updated_at)
SELECT e.id, es.id,
       (SELECT id FROM "user" WHERE username = 'test_a11_diferido1'),
       (SELECT id FROM "user" WHERE username = 'admin'),
       'done', 'Entrevista completada. Candidata aceptada pero solicita diferimiento por motivos laborales.',
       '2026-07-15'::timestamp, '2026-07-20'::timestamp
FROM event e
JOIN event_window ew ON ew.event_id = e.id
JOIN event_slot es ON es.event_window_id = ew.id
WHERE e.title = 'Entrevistas Admision MII — Ago-Dic 2026'
  AND es.starts_at = '2026-07-20 10:30'::timestamp
AND NOT EXISTS (SELECT 1 FROM appointment a WHERE a.slot_id = es.id);

-- NOTA: A3 (test_a03_listo) es ELEGIBLE pero NO tiene entrevista asignada.
-- Esto permite probar el flujo completo: elegibilidad → asignar slot → done → deliberar


-- ═══════════════════════════════════════════════════════════════════════════════
-- EVENTO ACTUAL MANI — Periodo 20263 (Ago-Dic 2026)
-- Aspirantes: A5 (rechazado total), A12 (diferido 2x)
-- ═══════════════════════════════════════════════════════════════════════════════

INSERT INTO event (program_id, academic_period_id, type, title, description, location,
                   created_by, visible_to_students, capacity_type,
                   requires_registration, allows_attendance_tracking, status, created_at, updated_at)
SELECT
    (SELECT id FROM program WHERE slug = 'MANI'),
    (SELECT id FROM academic_period WHERE code = '20263'),
    'interview',
    'Entrevistas Admision MANI — Ago-Dic 2026',
    'Entrevistas individuales para aspirantes al programa MANI periodo 20263.',
    'Edificio de Posgrado, Sala 203',
    (SELECT id FROM "user" WHERE username = 'admin'),
    true, 'single', true, false, 'published',
    '2026-06-20'::timestamp, NOW()
WHERE NOT EXISTS (
    SELECT 1 FROM event WHERE title = 'Entrevistas Admision MANI — Ago-Dic 2026'
);

-- Window: 22 julio 2026, 10:00-14:00 (8 slots)
INSERT INTO event_window (event_id, date, start_time, end_time, slot_minutes,
                          slots_generated, current_capacity, created_at, updated_at)
SELECT e.id, '2026-07-22'::date, '10:00'::time, '14:00'::time, 30,
       true, 8, '2026-06-20'::timestamp, NOW()
FROM event e WHERE e.title = 'Entrevistas Admision MANI — Ago-Dic 2026'
AND NOT EXISTS (
    SELECT 1 FROM event_window ew WHERE ew.event_id = e.id AND ew.date = '2026-07-22'
);

-- Slots MANI
INSERT INTO event_slot (event_window_id, starts_at, ends_at, status, created_at, updated_at)
SELECT ew.id,
       ('2026-07-22 ' || v.st)::timestamp,
       ('2026-07-22 ' || v.et)::timestamp,
       v.slot_status,
       '2026-06-20'::timestamp, NOW()
FROM event_window ew
JOIN event e ON ew.event_id = e.id
CROSS JOIN (VALUES
    ('10:00', '10:30', 'booked'),   -- A5
    ('10:30', '11:00', 'booked'),   -- A12
    ('11:00', '11:30', 'free'),
    ('11:30', '12:00', 'free'),
    ('12:00', '12:30', 'free'),
    ('12:30', '13:00', 'free'),
    ('13:00', '13:30', 'free'),
    ('13:30', '14:00', 'free')
) AS v(st, et, slot_status)
WHERE e.title = 'Entrevistas Admision MANI — Ago-Dic 2026' AND ew.date = '2026-07-22'
AND NOT EXISTS (
    SELECT 1 FROM event_slot es WHERE es.event_window_id = ew.id
        AND es.starts_at = ('2026-07-22 ' || v.st)::timestamp
);

-- A5 (rechazado total): entrevista done
INSERT INTO appointment (event_id, slot_id, applicant_id, assigned_by, status, notes,
                         created_at, updated_at)
SELECT e.id, es.id,
       (SELECT id FROM "user" WHERE username = 'test_a05_rech_total'),
       (SELECT id FROM "user" WHERE username = 'admin'),
       'done', 'Entrevista realizada. El aspirante no cumple el perfil requerido para el programa.',
       '2026-07-18'::timestamp, '2026-07-22'::timestamp
FROM event e
JOIN event_window ew ON ew.event_id = e.id
JOIN event_slot es ON es.event_window_id = ew.id
WHERE e.title = 'Entrevistas Admision MANI — Ago-Dic 2026'
  AND es.starts_at = '2026-07-22 10:00'::timestamp
AND NOT EXISTS (SELECT 1 FROM appointment a WHERE a.slot_id = es.id);

-- A12 (diferido 2x): entrevista done (fue entrevistado y aceptado, luego dirio 2 veces)
INSERT INTO appointment (event_id, slot_id, applicant_id, assigned_by, status, notes,
                         created_at, updated_at)
SELECT e.id, es.id,
       (SELECT id FROM "user" WHERE username = 'test_a12_diferido2'),
       (SELECT id FROM "user" WHERE username = 'admin'),
       'done', 'Entrevista completada. Candidato aceptado pero con situacion economica complicada.',
       '2026-07-18'::timestamp, '2026-07-22'::timestamp
FROM event e
JOIN event_window ew ON ew.event_id = e.id
JOIN event_slot es ON es.event_window_id = ew.id
WHERE e.title = 'Entrevistas Admision MANI — Ago-Dic 2026'
  AND es.starts_at = '2026-07-22 10:30'::timestamp
AND NOT EXISTS (SELECT 1 FROM appointment a WHERE a.slot_id = es.id);


-- ═══════════════════════════════════════════════════════════════════════════════
-- ACTUALIZAR admission_status de aspirantes que ya pasaron entrevista
-- ═══════════════════════════════════════════════════════════════════════════════
-- Los que tienen appointment.status='done' deberian tener
-- user_program.admission_status='interview_completed' o posterior.
-- A4, A5 ya estan en 'rejected' (paso posterior).
-- A9, A10 ya estan en 'accepted' (paso posterior).
-- A11, A12 ya estan en 'deferred' (paso posterior).
-- Solo A3 no tiene entrevista (sigue en 'in_progress').
-- No se necesita actualizar nada — los status ya estan correctos.
