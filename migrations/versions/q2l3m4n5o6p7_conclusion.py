"""conclusion

Revision ID: q2l3m4n5o6p7
Revises: p1k2l3m4n5o6
Create Date: 2026-10-22

Phase 6C: thesis and its committees, admission conditions, grade exam and
titling.

Schema (expand-only — the previous color keeps working against it):
- tables `thesis`, `thesis_member`, `admission_condition`, `grade_exam`;
- `user_program.titled_at` and 'titled' in `ck_user_program_academic_status`
  (the previous color never writes it);
- `archive.issued_by_institution` (server default false, so inserts from the
  previous color stay valid).

Data (idempotent, by phase + step name + archive name; a match that is
missing or not unique is skipped silently):
- `archive_key` on the conclusion requirements and on the admission
  documents a conclusion requirement can reuse;
- `issued_by_institution` + `allow_coordinator_upload` on the documents the
  institution issues;
- the "Carta de Originalidad" description said "Similitud >30%": it is "<30%".

Downgrade drops what the upgrade created and refuses to run while a
`titled` row exists. The data keys are left in place.
"""
import sqlalchemy as sa
from alembic import op


# revision identifiers, used by Alembic.
revision = 'q2l3m4n5o6p7'
down_revision = 'p1k2l3m4n5o6'
branch_labels = None
depends_on = None


OLD_ACADEMIC_STATUSES = ('active', 'on_leave', 'withdrawn', 'graduated')
NEW_ACADEMIC_STATUSES = OLD_ACADEMIC_STATUSES + ('titled',)

#: (phase, step name, archive names accepted, archive_key)
ARCHIVE_KEYS = (
    # Conclusion: general requirements (step 13).
    ('conclusion', 'Requisitos Generales', ('Título del Grado Anterior',), 'conclusion_previous_degree'),
    ('conclusion', 'Requisitos Generales', ('Solicitud del Examen de Grado',), 'conclusion_exam_request'),
    ('conclusion', 'Requisitos Generales', ('Constancia de Aprobación',), 'conclusion_approval_certificate'),
    ('conclusion', 'Requisitos Generales', ('Constancia de Segundo Idioma',), 'conclusion_second_language'),
    ('conclusion', 'Requisitos Generales', ('Carta de Autorización',), 'conclusion_committee_authorization'),
    ('conclusion', 'Requisitos Generales', ('Autorización de Impresión',), 'conclusion_print_authorization'),
    ('conclusion', 'Requisitos Generales', ('Documento de Tesis Final',), 'conclusion_thesis_document'),
    ('conclusion', 'Requisitos Generales', ('Carta de Cesión de Derechos',), 'conclusion_rights_assignment'),
    ('conclusion', 'Requisitos Generales', ('Carta de Originalidad',), 'conclusion_originality_letter'),
    ('conclusion', 'Requisitos Generales', ('Constancia de No Inconveniencia',), 'conclusion_no_objection'),
    ('conclusion', 'Requisitos Generales', ('Cobertura de los Derechos de Examen',), 'conclusion_exam_fees'),
    ('conclusion', 'Requisitos Generales', ('No Adeudos',), 'conclusion_no_debts'),
    ('conclusion', 'Requisitos Generales', ('Oficio Autorización (Dispensa)',), 'conclusion_dispensation'),
    ('conclusion', 'Requisitos Generales', ('Comprobante Actividades de Retribución',), 'conclusion_social_retribution'),
    # Conclusion: master's (step 14) and doctorate (step 15) requirements.
    ('conclusion', 'Requisitos de Maestrías', ('Carta de Usuario',), 'conclusion_user_letter'),
    ('conclusion', 'Requisitos de Maestrías', ('Producto Académico Original',), 'conclusion_academic_product'),
    ('conclusion', 'Requisitos de Doctorados', ('Estancia Académica',), 'conclusion_academic_stay'),
    ('conclusion', 'Requisitos de Doctorados', ('Artículo Publicado',), 'conclusion_published_article'),
    # Admission documents a conclusion requirement can reuse.
    ('admission', 'Requisitos de Maestrías', ('Título',), 'admission_degree_title_ms'),
    ('admission', 'Requisitos de Maestrías', ('Comprobante Inglés', 'Comprobante de Inglés'), 'admission_english_ms'),
    ('admission', 'Documentos Específicos DCI', ('Título',), 'admission_degree_title_phd'),
    ('admission', 'Documentos Específicos DCI', ('Comprobante de Inglés', 'Comprobante Inglés'), 'admission_english_phd'),
)

#: Conclusion documents the institution issues (the coordination uploads them).
INSTITUTION_ISSUED = (
    'Autorización de Impresión',
    'Carta de Originalidad',
    'Constancia de Aprobación',
    'Constancia de No Inconveniencia',
    'Oficio Autorización (Dispensa)',
    'Carta de Autorización',
)


def _tables():
    return set(sa.inspect(op.get_bind()).get_table_names())


def _columns(table):
    return {c['name'] for c in sa.inspect(op.get_bind()).get_columns(table)}


def _checks(table):
    return {c['name'] for c in sa.inspect(op.get_bind()).get_check_constraints(table)}


def _replace_academic_status_check(statuses):
    allowed = ', '.join(f"'{s}'" for s in statuses)
    checks = _checks('user_program')
    with op.batch_alter_table('user_program') as batch:
        if 'ck_user_program_academic_status' in checks:
            batch.drop_constraint('ck_user_program_academic_status', type_='check')
        batch.create_check_constraint('ck_user_program_academic_status',
                                      f'academic_status IN ({allowed})')


def backfill_conclusion_archives(conn) -> dict:
    """Idempotent data part. Returns counts of what it changed."""
    keyed = 0
    for phase, step_name, names, key in ARCHIVE_KEYS:
        taken = conn.execute(sa.text(
            'SELECT COUNT(*) FROM archive WHERE archive_key = :key'), {'key': key}).scalar()
        if taken:
            continue
        params = {'phase': phase, 'step': step_name}
        placeholders = []
        for i, name in enumerate(names):
            params[f'n{i}'] = name
            placeholders.append(f':n{i}')
        rows = conn.execute(sa.text(
            'SELECT a.id, a.archive_key FROM archive a '
            'JOIN step s ON s.id = a.step_id '
            'JOIN phase p ON p.id = s.phase_id '
            f"WHERE p.name = :phase AND s.name = :step AND a.name IN ({', '.join(placeholders)})"
        ), params).fetchall()
        if len(rows) != 1 or rows[0][1] is not None:
            continue
        conn.execute(sa.text('UPDATE archive SET archive_key = :key WHERE id = :id'),
                     {'key': key, 'id': rows[0][0]})
        keyed += 1

    params = {f'i{i}': name for i, name in enumerate(INSTITUTION_ISSUED)}
    flagged = conn.execute(sa.text(
        'UPDATE archive SET issued_by_institution = :yes, allow_coordinator_upload = :yes '
        'WHERE step_id IN (SELECT s.id FROM step s JOIN phase p ON p.id = s.phase_id '
        "                  WHERE p.name = 'conclusion') "
        f"AND name IN ({', '.join(':' + k for k in params)}) "
        'AND (issued_by_institution = :no OR allow_coordinator_upload = :no)'
    ), {**params, 'yes': True, 'no': False}).rowcount

    fixed = conn.execute(sa.text(
        "UPDATE archive SET description = REPLACE(description, 'Similitud >30%', 'Similitud <30%') "
        "WHERE description LIKE '%Similitud >30\\%%' ESCAPE '\\'"
    )).rowcount
    return {'archive_key': keyed, 'issued_by_institution': flagged, 'description': fixed}


def upgrade():
    tables = _tables()

    if 'titled_at' not in _columns('user_program'):
        with op.batch_alter_table('user_program') as batch:
            batch.add_column(sa.Column('titled_at', sa.Date(), nullable=True))
    _replace_academic_status_check(NEW_ACADEMIC_STATUSES)

    if 'issued_by_institution' not in _columns('archive'):
        with op.batch_alter_table('archive') as batch:
            batch.add_column(sa.Column('issued_by_institution', sa.Boolean(), nullable=False,
                                       server_default=sa.false()))

    if 'thesis' not in tables:
        op.create_table(
            'thesis',
            sa.Column('id', sa.Integer(), primary_key=True),
            sa.Column('uuid', sa.Uuid(as_uuid=True), nullable=False),
            sa.Column('user_program_id', sa.Integer(),
                      sa.ForeignKey('user_program.id', ondelete='CASCADE'), nullable=False),
            sa.Column('title', sa.String(500), nullable=False),
            sa.Column('research_line', sa.String(255), nullable=True),
            sa.Column('registered_at', sa.Date(), nullable=False),
            sa.Column('created_by', sa.Integer(),
                      sa.ForeignKey('user.id', ondelete='SET NULL'), nullable=True),
            sa.Column('created_at', sa.DateTime(), nullable=False),
            sa.Column('updated_at', sa.DateTime(), nullable=False),
            sa.UniqueConstraint('user_program_id', name='uq_thesis_user_program_id'),
        )
        op.create_index('ix_thesis_uuid', 'thesis', ['uuid'], unique=True)

    if 'thesis_member' not in tables:
        op.create_table(
            'thesis_member',
            sa.Column('id', sa.Integer(), primary_key=True),
            sa.Column('thesis_id', sa.Integer(),
                      sa.ForeignKey('thesis.id', ondelete='CASCADE'), nullable=False),
            sa.Column('body', sa.String(10), nullable=False),
            sa.Column('role', sa.String(12), nullable=False),
            sa.Column('user_id', sa.Integer(),
                      sa.ForeignKey('user.id', ondelete='RESTRICT'), nullable=True),
            sa.Column('external_name', sa.String(200), nullable=True),
            sa.Column('external_institution', sa.String(200), nullable=True),
            sa.Column('created_at', sa.DateTime(), nullable=False),
            sa.CheckConstraint("body IN ('tutorial', 'exam')", name='ck_thesis_member_body'),
            sa.CheckConstraint(
                "(body = 'tutorial' AND role IN ('director', 'codirector', 'advisor')) OR "
                "(body = 'exam' AND role IN ('president', 'secretary', 'vocal', 'substitute'))",
                name='ck_thesis_member_role'),
            sa.CheckConstraint('(user_id IS NULL) <> (external_name IS NULL)',
                               name='ck_thesis_member_person'),
        )
        op.create_index('ix_thesis_member_thesis_id', 'thesis_member', ['thesis_id'])
        op.create_index('ix_thesis_member_user_id', 'thesis_member', ['user_id'])
        op.create_index('uq_thesis_member_director', 'thesis_member', ['thesis_id'], unique=True,
                        postgresql_where=sa.text("body = 'tutorial' AND role = 'director'"),
                        sqlite_where=sa.text("body = 'tutorial' AND role = 'director'"))
        op.create_index('uq_thesis_member_exam_chair', 'thesis_member', ['thesis_id', 'role'],
                        unique=True,
                        postgresql_where=sa.text("body = 'exam' AND role IN ('president', 'secretary')"),
                        sqlite_where=sa.text("body = 'exam' AND role IN ('president', 'secretary')"))

    if 'admission_condition' not in tables:
        op.create_table(
            'admission_condition',
            sa.Column('id', sa.Integer(), primary_key=True),
            sa.Column('uuid', sa.Uuid(as_uuid=True), nullable=False),
            sa.Column('user_program_id', sa.Integer(),
                      sa.ForeignKey('user_program.id', ondelete='CASCADE'), nullable=False),
            sa.Column('description', sa.Text(), nullable=False),
            sa.Column('archive_id', sa.Integer(),
                      sa.ForeignKey('archive.id', ondelete='SET NULL'), nullable=True),
            sa.Column('due_date', sa.Date(), nullable=True),
            sa.Column('status', sa.String(10), nullable=False),
            sa.Column('resolved_at', sa.DateTime(), nullable=True),
            sa.Column('resolved_by', sa.Integer(),
                      sa.ForeignKey('user.id', ondelete='SET NULL'), nullable=True),
            sa.Column('resolution_note', sa.Text(), nullable=True),
            sa.Column('created_by', sa.Integer(),
                      sa.ForeignKey('user.id', ondelete='SET NULL'), nullable=True),
            sa.Column('created_at', sa.DateTime(), nullable=False),
            sa.CheckConstraint("status IN ('pending', 'met', 'waived')",
                               name='ck_admission_condition_status'),
        )
        op.create_index('ix_admission_condition_uuid', 'admission_condition', ['uuid'], unique=True)
        op.create_index('ix_admission_condition_user_program_id', 'admission_condition',
                        ['user_program_id'])
        op.create_index('ix_admission_condition_archive_id', 'admission_condition', ['archive_id'])

    if 'grade_exam' not in tables:
        op.create_table(
            'grade_exam',
            sa.Column('id', sa.Integer(), primary_key=True),
            sa.Column('uuid', sa.Uuid(as_uuid=True), nullable=False),
            sa.Column('user_program_id', sa.Integer(),
                      sa.ForeignKey('user_program.id', ondelete='CASCADE'), nullable=False),
            sa.Column('scheduled_at', sa.DateTime(), nullable=False),
            sa.Column('place', sa.String(255), nullable=False),
            sa.Column('status', sa.String(10), nullable=False),
            sa.Column('verdict', sa.String(10), nullable=True),
            sa.Column('honorific_mention', sa.Boolean(), nullable=False,
                      server_default=sa.false()),
            sa.Column('acta_folio', sa.String(50), nullable=True),
            sa.Column('held_on', sa.Date(), nullable=True),
            sa.Column('notes', sa.Text(), nullable=True),
            sa.Column('scheduled_by', sa.Integer(),
                      sa.ForeignKey('user.id', ondelete='SET NULL'), nullable=True),
            sa.Column('recorded_by', sa.Integer(),
                      sa.ForeignKey('user.id', ondelete='SET NULL'), nullable=True),
            sa.Column('created_at', sa.DateTime(), nullable=False),
            sa.Column('updated_at', sa.DateTime(), nullable=False),
            sa.CheckConstraint("status IN ('scheduled', 'approved', 'suspended', 'cancelled')",
                               name='ck_grade_exam_status'),
            sa.CheckConstraint("verdict IS NULL OR verdict IN ('unanimous', 'majority')",
                               name='ck_grade_exam_verdict'),
        )
        op.create_index('ix_grade_exam_uuid', 'grade_exam', ['uuid'], unique=True)
        op.create_index('ix_grade_exam_user_program_id', 'grade_exam', ['user_program_id'])
        op.create_index('uq_grade_exam_scheduled', 'grade_exam', ['user_program_id'], unique=True,
                        postgresql_where=sa.text("status = 'scheduled'"),
                        sqlite_where=sa.text("status = 'scheduled'"))

    counts = backfill_conclusion_archives(op.get_bind())
    print(f'conclusion archives: {counts}')


def downgrade():
    conn = op.get_bind()
    titled = conn.execute(sa.text(
        "SELECT COUNT(*) FROM user_program WHERE academic_status = 'titled'")).scalar()
    if titled:
        raise RuntimeError(
            f'{titled} user_program row(s) have academic_status = \'titled\'; the previous '
            'schema cannot hold them. Revert them to \'graduated\' first, then downgrade.')

    tables = _tables()
    for table in ('grade_exam', 'admission_condition', 'thesis_member', 'thesis'):
        if table in tables:
            op.drop_table(table)

    _replace_academic_status_check(OLD_ACADEMIC_STATUSES)
    if 'titled_at' in _columns('user_program'):
        with op.batch_alter_table('user_program') as batch:
            batch.drop_column('titled_at')
    if 'issued_by_institution' in _columns('archive'):
        with op.batch_alter_table('archive') as batch:
            batch.drop_column('issued_by_institution')
