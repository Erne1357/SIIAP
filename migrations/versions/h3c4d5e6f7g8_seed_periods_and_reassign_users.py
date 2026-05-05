"""seed_periods_and_reassign_users

Migración de datos (limpieza histórica) que:

  1. Crea los periodos académicos faltantes (20243, 20251, 20261, 20263, 20271)
     siguiendo el calendario típico del TecNM. El periodo 20253 ya existe;
     se conserva pero se marca como `completed` (no activo).
  2. Marca 20261 como ACTIVO (Ene-Jun 2026).
  3. Reasigna `user_program.admission_period_id` según fecha de registro:
       - Reg < 2026-01-01            → 20261, sin diferimiento
       - 2026-01-01 <= Reg < 2026-03-01 → 20263 + EnrollmentDeferral histórico
                                         (intentaron 20261 pero la admisión
                                          ya estaba cerrada → diferidos a 20263)
       - Reg >= 2026-03-01            → 20263 directo, sin diferimiento
  4. Caso especial Laura Edith Ibarra (username/control_number M19110043):
       - Cambia role_id a `student`
       - admission_status='enrolled'
       - control_number_assigned_at = registration_date
       - current_semester=4
       - 4 `SemesterEnrollment` backfill (20243, 20251, 20253 completed; 20261 active)

Idempotente: re-ejecutar es no-op (chequea is-already-applied antes de actuar).
Reversible parcialmente con `downgrade()`: revierte lo que esta migración insertó
sin tocar datos pre-existentes (no devuelve los user_programs a su periodo viejo).

Revision ID: h3c4d5e6f7g8
Revises: g2b3c4d5e6f7
Create Date: 2026-05-05 00:00:00.000000
"""
from datetime import datetime, date
from alembic import op
import sqlalchemy as sa


revision = 'h3c4d5e6f7g8'
down_revision = 'g2b3c4d5e6f7'
branch_labels = None
depends_on = None


# ── Definición de periodos ──────────────────────────────────────────────────
PERIODS = [
    # (code, name, start, end, admission_start, admission_end, is_active, status)
    ('20243', 'Agosto-Diciembre 2024', date(2024, 8, 12), date(2024, 12, 13),
     date(2024, 5, 1),  date(2024, 7, 31), False, 'completed'),
    ('20251', 'Enero-Junio 2025', date(2025, 1, 13), date(2025, 6, 13),
     date(2024, 10, 1), date(2024, 12, 31), False, 'completed'),
    ('20261', 'Enero-Junio 2026', date(2026, 1, 12), date(2026, 6, 12),
     date(2025, 10, 1), date(2025, 12, 31), True,  'active'),
    ('20263', 'Agosto-Diciembre 2026', date(2026, 8, 10), date(2026, 12, 11),
     date(2026, 3, 1),  date(2026, 7, 31), False, 'upcoming'),
    ('20271', 'Enero-Junio 2027', date(2027, 1, 11), date(2027, 6, 11),
     date(2026, 10, 1), date(2026, 12, 31), False, 'upcoming'),
]


def upgrade():
    bind = op.get_bind()

    # ── 1. Insertar periodos faltantes ─────────────────────────────────────
    for code, name, sd, ed, asd, aed, is_active, status in PERIODS:
        exists = bind.execute(sa.text(
            "SELECT id FROM academic_period WHERE code = :code"
        ), {'code': code}).first()
        if exists:
            continue
        bind.execute(sa.text("""
            INSERT INTO academic_period
                (code, name, start_date, end_date,
                 admission_start_date, admission_end_date,
                 is_active, status, created_at, updated_at)
            VALUES (:code, :name, :sd, :ed, :asd, :aed,
                    :is_active, :status, NOW(), NOW())
        """), {
            'code': code, 'name': name,
            'sd': sd, 'ed': ed,
            'asd': asd, 'aed': aed,
            'is_active': is_active, 'status': status,
        })

    # ── 2. Desactivar periodos que NO sean 20261 (queremos 20261 único activo)
    bind.execute(sa.text("""
        UPDATE academic_period
        SET is_active = false,
            status = CASE
                WHEN end_date < CURRENT_DATE THEN 'completed'
                ELSE 'upcoming'
            END,
            updated_at = NOW()
        WHERE code <> '20261'
    """))
    bind.execute(sa.text("""
        UPDATE academic_period
        SET is_active = true, status = 'active', updated_at = NOW()
        WHERE code = '20261'
    """))

    # Recolectar IDs después de inserts
    p_20261 = bind.execute(sa.text(
        "SELECT id FROM academic_period WHERE code='20261'"
    )).scalar()
    p_20263 = bind.execute(sa.text(
        "SELECT id FROM academic_period WHERE code='20263'"
    )).scalar()

    # ── 3. Reasignar user_program.admission_period_id por fecha registro ──
    # Buckets:
    #   A) reg < 2026-01-01            → 20261, sin defer
    #   B) 2026-01 <= reg < 2026-03    → 20263 + EnrollmentDeferral 20261→20263
    #   C) reg >= 2026-03-01           → 20263, sin defer

    # A) → 20261
    bind.execute(sa.text("""
        UPDATE user_program up
        SET admission_period_id = :p20261, updated_at = NOW()
        FROM "user" u
        WHERE up.user_id = u.id
          AND u.registration_date < TIMESTAMP '2026-01-01 00:00:00'
    """), {'p20261': p_20261})

    # C) → 20263 (registros desde marzo 2026 — ya estaba abierta admisión 20263)
    bind.execute(sa.text("""
        UPDATE user_program up
        SET admission_period_id = :p20263, updated_at = NOW()
        FROM "user" u
        WHERE up.user_id = u.id
          AND u.registration_date >= TIMESTAMP '2026-03-01 00:00:00'
    """), {'p20263': p_20263})

    # B) Diferidos: registros Ene-Feb 2026 (admisión 20261 cerrada)
    # 1) Crear EnrollmentDeferral histórico (status='used' = ya consumido)
    # 2) Apuntar admission_period_id al destino (20263)
    rows_b = bind.execute(sa.text("""
        SELECT up.id, up.user_id, u.registration_date
        FROM user_program up
        JOIN "user" u ON up.user_id = u.id
        WHERE u.registration_date >= TIMESTAMP '2026-01-01 00:00:00'
          AND u.registration_date <  TIMESTAMP '2026-03-01 00:00:00'
    """)).fetchall()

    admin_id = bind.execute(sa.text(
        "SELECT id FROM \"user\" WHERE username='admin' LIMIT 1"
    )).scalar()

    for up_id, user_id, reg_date in rows_b:
        # Idempotencia: si ya hay un deferral histórico con la misma razón, saltar.
        existing = bind.execute(sa.text("""
            SELECT id FROM enrollment_deferral
            WHERE user_program_id = :up_id
              AND reason LIKE 'Migración:%'
            LIMIT 1
        """), {'up_id': up_id}).first()
        if not existing:
            bind.execute(sa.text("""
                INSERT INTO enrollment_deferral
                    (user_program_id, original_period_id, deferred_to_period_id,
                     deferral_number, status, requested_by, reason,
                     reviewed_by_id, reviewed_at, created_at)
                VALUES
                    (:up_id, :orig, :dest, 1, 'used', 'coordinator',
                     'Migración: registro posterior al cierre de admisión 20261',
                     :admin, NOW(), :reg)
            """), {
                'up_id': up_id,
                'orig': p_20261,
                'dest': p_20263,
                'admin': admin_id,
                'reg': reg_date,
            })
        # Apuntar al periodo destino
        bind.execute(sa.text("""
            UPDATE user_program
            SET admission_period_id = :dest, updated_at = NOW()
            WHERE id = :up_id
        """), {'dest': p_20263, 'up_id': up_id})

    # ── 4. Caso Laura: M19110043 → student enrolled con backfill ──────────
    laura_id = bind.execute(sa.text(
        "SELECT id FROM \"user\" WHERE control_number = 'M19110043' LIMIT 1"
    )).scalar()

    if laura_id is not None:
        student_role_id = bind.execute(sa.text(
            "SELECT id FROM role WHERE name='student' LIMIT 1"
        )).scalar()

        # Update user
        bind.execute(sa.text("""
            UPDATE "user"
            SET role_id = :role,
                control_number_assigned_at = COALESCE(control_number_assigned_at, registration_date),
                updated_at = NOW()
            WHERE id = :uid
        """), {'role': student_role_id, 'uid': laura_id})

        # Update user_program
        laura_up_id = bind.execute(sa.text(
            "SELECT id FROM user_program WHERE user_id = :uid LIMIT 1"
        ), {'uid': laura_id}).scalar()

        if laura_up_id is not None:
            bind.execute(sa.text("""
                UPDATE user_program
                SET admission_status = 'enrolled',
                    current_semester = 4,
                    updated_at = NOW()
                WHERE id = :up_id
            """), {'up_id': laura_up_id})

            # Backfill 4 SemesterEnrollments
            # sem 1→20243, sem 2→20251, sem 3→20253, sem 4→20261(active)
            sem_map = [
                (1, '20243', 'completed', True),
                (2, '20251', 'completed', True),
                (3, '20253', 'completed', True),
                (4, '20261', 'active',    True),
            ]
            for sem_num, code, status, confirmed in sem_map:
                period_id = bind.execute(sa.text(
                    "SELECT id FROM academic_period WHERE code = :c"
                ), {'c': code}).scalar()
                if not period_id:
                    continue
                already = bind.execute(sa.text("""
                    SELECT id FROM semester_enrollment
                    WHERE user_program_id = :up AND semester_number = :n
                """), {'up': laura_up_id, 'n': sem_num}).first()
                if already:
                    continue
                bind.execute(sa.text("""
                    INSERT INTO semester_enrollment
                        (user_program_id, academic_period_id, semester_number,
                         status, enrollment_confirmed,
                         confirmed_by, confirmed_at,
                         created_at, updated_at)
                    VALUES
                        (:up, :pid, :n, :st, :conf,
                         :admin, NOW(), NOW(), NOW())
                """), {
                    'up': laura_up_id, 'pid': period_id, 'n': sem_num,
                    'st': status, 'conf': confirmed, 'admin': admin_id,
                })


def downgrade():
    """
    Reversa parcial: borra los EnrollmentDeferral creados por esta migración
    y quita los SemesterEnrollments de Laura. NO restaura admission_period_id
    al valor previo (información perdida) ni borra los periodos creados.
    """
    bind = op.get_bind()

    # Borrar deferrals de migración
    bind.execute(sa.text("""
        DELETE FROM enrollment_deferral
        WHERE reason LIKE 'Migración:%'
    """))

    # Borrar SEs de Laura (y revertir flag de student)
    laura_id = bind.execute(sa.text(
        "SELECT id FROM \"user\" WHERE control_number = 'M19110043' LIMIT 1"
    )).scalar()
    if laura_id is not None:
        applicant_role_id = bind.execute(sa.text(
            "SELECT id FROM role WHERE name='applicant' LIMIT 1"
        )).scalar()
        bind.execute(sa.text("""
            UPDATE "user" SET role_id = :r WHERE id = :uid
        """), {'r': applicant_role_id, 'uid': laura_id})
        bind.execute(sa.text("""
            DELETE FROM semester_enrollment WHERE user_program_id IN (
                SELECT id FROM user_program WHERE user_id = :uid
            )
        """), {'uid': laura_id})
        bind.execute(sa.text("""
            UPDATE user_program
            SET admission_status='in_progress', current_semester=NULL
            WHERE user_id = :uid
        """), {'uid': laura_id})
