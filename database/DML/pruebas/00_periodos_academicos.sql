-- =============================================================================
-- 00: Periodos academicos (historicos + activo)
-- =============================================================================
-- Formato YYYYN: 1=Ene-Jun, 2=Verano, 3=Ago-Dic
-- Necesitamos periodos viejos para simular historial de estudiantes avanzados,
-- diferimientos, expiraciones y transiciones de periodo.
-- =============================================================================

-- Periodo 1: Ene-Jun 2024  (muy viejo, para probar expiracion de 2+ periodos)
INSERT INTO academic_period (code, name, start_date, end_date,
                             admission_start_date, admission_end_date,
                             is_active, status, created_at, updated_at)
VALUES ('20241', 'Enero-Junio 2024',
        '2024-01-15', '2024-06-14',
        '2023-10-01', '2023-12-15',
        false, 'completed', '2024-01-01'::timestamp, NOW())
ON CONFLICT (code) DO NOTHING;

-- Periodo 2: Ago-Dic 2024
INSERT INTO academic_period (code, name, start_date, end_date,
                             admission_start_date, admission_end_date,
                             is_active, status, created_at, updated_at)
VALUES ('20243', 'Agosto-Diciembre 2024',
        '2024-08-12', '2024-12-13',
        '2024-05-01', '2024-07-31',
        false, 'completed', '2024-05-01'::timestamp, NOW())
ON CONFLICT (code) DO NOTHING;

-- Periodo 3: Ene-Jun 2025
INSERT INTO academic_period (code, name, start_date, end_date,
                             admission_start_date, admission_end_date,
                             is_active, status, created_at, updated_at)
VALUES ('20251', 'Enero-Junio 2025',
        '2025-01-13', '2025-06-13',
        '2024-10-01', '2024-12-31',
        false, 'completed', '2024-10-01'::timestamp, NOW())
ON CONFLICT (code) DO NOTHING;

-- Periodo 4: Ago-Dic 2025
INSERT INTO academic_period (code, name, start_date, end_date,
                             admission_start_date, admission_end_date,
                             is_active, status, created_at, updated_at)
VALUES ('20253', 'Agosto-Diciembre 2025',
        '2025-08-11', '2025-12-12',
        '2025-05-01', '2025-07-31',
        false, 'completed', '2025-05-01'::timestamp, NOW())
ON CONFLICT (code) DO NOTHING;

-- Periodo 5: Ene-Jun 2026
INSERT INTO academic_period (code, name, start_date, end_date,
                             admission_start_date, admission_end_date,
                             is_active, status, created_at, updated_at)
VALUES ('20261', 'Enero-Junio 2026',
        '2026-01-12', '2026-06-12',
        '2025-10-01', '2025-12-31',
        false, 'completed', '2025-10-01'::timestamp, NOW())
ON CONFLICT (code) DO NOTHING;

-- Desactivar TODOS los periodos antes de activar el de prueba
UPDATE academic_period SET is_active = false, status = 'completed'
WHERE is_active = true;

-- Periodo 6 (ACTIVO): Ago-Dic 2026
INSERT INTO academic_period (code, name, start_date, end_date,
                             admission_start_date, admission_end_date,
                             is_active, status, created_at, updated_at)
VALUES ('20263', 'Agosto-Diciembre 2026',
        '2026-08-10', '2026-12-11',
        '2026-05-01', '2026-07-31',
        true, 'active', '2026-05-01'::timestamp, NOW())
ON CONFLICT (code) DO UPDATE SET is_active = true, status = 'active';

-- Periodo 7 (FUTURO): Ene-Jun 2027 (para diferimientos)
INSERT INTO academic_period (code, name, start_date, end_date,
                             admission_start_date, admission_end_date,
                             is_active, status, created_at, updated_at)
VALUES ('20271', 'Enero-Junio 2027',
        '2027-01-11', '2027-06-11',
        '2026-10-01', '2026-12-31',
        false, 'upcoming', NOW(), NOW())
ON CONFLICT (code) DO NOTHING;
