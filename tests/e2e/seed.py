"""
Seed synthetic data for the browser suite. Idempotent: safe to re-run.

    python -m tests.e2e.seed        (runs inside the `app` container, after
                                     tests.support.build_schema)

The real permission catalog lives in `database/` (never in git), so every role
here is granted exactly the codenames the E2E flows need. They were derived
from the @permission_required decorators of the pages the flows visit and from
the XHRs those pages fire.
"""

import sys

from werkzeug.security import generate_password_hash

from tests.e2e import accounts as acc

# ── Permission sets ──────────────────────────────────────────────────────────

#: What every logged-in account needs for the shared shell (base.html):
#: /api/v1/auth/me, notifications bell, events badge, avatar, profile page.
SHELL = {
    'users.api.me', 'users.api.profile_completion', 'users.api.history',
    'users.api.change_password',
    'notifications.api.list', 'notifications.api.unread_count',
    'notifications.api.mark_all_read', 'notifications.api.delete',
    'files.api.view_doc', 'files.api.view_template',
    'profile.api.upload_photo', 'profile.api.request_photo_change',
    'programs.page.view', 'programs.api.list', 'programs.api.detail',
    'events.api.list', 'academic_periods.api.view_active',
    'invitations.api.respond',
}


def _codes(resource, *names):
    """_codes('events', 'api.list', 'page.view') -> {'events.api.list', 'events.page.view'}"""
    return {f'{resource}.{name}' for name in names}


#: Own-profile widgets (the profile page and dashboards fetch these on load).
OWN_PROFILE = _codes('profile', 'api.view_own_activity', 'api.view_own_documents',
                     'api.view_own_upcoming_events')

#: Staff capabilities reachable from the coordinator sidebar. Every codename is a
#: @permission_required in app/routes/{pages,api}: page decorators for the nav
#: links, api decorators for the XHRs those pages fire on load.
STAFF = (
    _codes('coordinator', 'page.view', 'api.list_students', 'api.upload_for_student')
    | _codes('deliberation', 'page.view', 'api.decide', 'api.force_reset', 'api.list_applicants')
    | _codes('acceptance', 'page.view', 'api.assign_control_number', 'api.defer_applicant',
             'api.list_applicants', 'api.review_doc', 'api.upload_doc')
    | _codes('permanence', 'page.view', 'api.advance_bulk', 'api.confirm_enrollment',
             'api.list_students', 'api.manage_deadlines', 'api.manage_students', 'api.review_doc')
    | _codes('admin_review', 'page.view', 'api.decide', 'api.detail_submission',
             'api.list_submissions')
    | _codes('admin_templates', 'page.view', 'api.create', 'api.delete', 'api.generate',
             'api.list', 'api.manage')
    | _codes('admin_users', 'page.view', 'api.assign_control_number',
             'api.create_social_service', 'api.delete', 'api.list', 'api.reset_password',
             'api.update')
    | _codes('admin_emails', 'api.manage')
    | _codes('archives', 'api.create', 'api.delete', 'api.list', 'api.manage_template',
             'api.update')
    | _codes('events', 'page.view', 'api.archive', 'api.conclude', 'api.create',
             'api.create_window', 'api.generate_slots', 'api.list', 'api.manage',
             'api.manage_hosts', 'api.manage_images')
    | _codes('interviews', 'api.check_eligibility', 'api.list_eligible', 'api.manage')
    | _codes('invitations', 'api.list', 'api.manage', 'api.send')
    | _codes('attendance', 'api.list_registrations', 'api.mark')
    | _codes('appointments', 'api.assign')
    | _codes('extensions', 'api.decide', 'api.list_for_review')
    | _codes('program_changes', 'api.decide')
    | _codes('student_bulk', 'page.view', 'api.create_one', 'api.csv_execute', 'api.csv_preview')
    | _codes('students', 'api.edit_personal_info', 'api.export_record_pdf', 'api.view_record',
             'page.view_record')
    | _codes('profile', 'api.enable_photo_change', 'api.list_photo_requests',
             'api.upload_photo_for_student')
    | _codes('programs', 'api.update')
    # The archives settings page also loads the retention policies panel.
    | _codes('admin_retention', 'api.manage')
    | _codes('academic_periods', 'api.list')
    # Phase 6B1: study plans, academic load and the teacher view.
    | _codes('curriculum', 'page.manage')
    | _codes('course_groups', 'page.manage')
    | _codes('teachers', 'page.create')
    | _codes('teaching', 'page.my_groups')
    | _codes('grades', 'page.capture', 'page.request_correction', 'page.import_history',
             'page.export_acta')
    | _codes('kardex', 'page.export_pdf')
)

#: Institution-wide administration, on top of STAFF. academic_periods.api.create
#: is also the marker of global program scope (User.has_global_program_scope).
POSTGRAD_ONLY = (
    _codes('academic_periods', 'api.activate', 'api.create', 'api.delete', 'api.update')
    | _codes('admin_celery', 'api.list_tasks', 'api.manage', 'api.run_task', 'api.status')
    | _codes('admin_cleanup', 'api.expired_candidates', 'api.inactive_students')
    | _codes('admin_history', 'api.cleanup_execute', 'api.cleanup_preview',
             'api.critical_actions', 'api.statistics', 'api.view')
    | _codes('permissions', 'page.manage_roles', 'api.delegate', 'api.list_role_permissions',
             'api.list_user_permissions', 'api.override_role_permission', 'api.revert_override',
             'api.revoke_delegation', 'api.view_audit')
    | _codes('grades', 'page.decide_correction', 'page.extend_capture')
    | _codes('admin', 'page.purge', 'api.purge_archive', 'api.purge_confirm', 'api.purge_view')
)


def permission_sets() -> dict:
    # The applicant / student base set, as declared by the app itself.
    from app.models.user import SELF_SERVICE_PERMISSIONS
    self_service = set(SELF_SERVICE_PERMISSIONS)

    # Dashboard dispatch (user/dashboard/dashboard.html) checks
    # programs.api.enroll first, then permanence.api.view_status: an applicant
    # must NOT hold the latter and a student must NOT hold the former.
    applicant = (self_service | SHELL | OWN_PROFILE) - {
        'permanence.api.view_status', 'extensions.api.view_archive_status',
    }
    student = (self_service | SHELL | OWN_PROFILE
               | _codes('permanence', 'api.upload_my_payment', 'api.view_my_enrollment')
               | _codes('course_enrollment', 'page.view_own')
               | _codes('kardex', 'page.view_own', 'page.export_own_pdf')
               ) - {'programs.api.enroll'}

    coordinator = SHELL | OWN_PROFILE | STAFF
    postgrad = coordinator | POSTGRAD_ONLY

    # Servicio social: reviews documents only, no delegation => no scope.
    social = SHELL | OWN_PROFILE | {'admin_review.page.view'}

    return {
        'applicant': applicant,
        'student': student,
        'program_admin': coordinator,
        'postgraduate_admin': postgrad,
        'social_service': social,
    }


# ── Helpers ──────────────────────────────────────────────────────────────────

def _upsert_user(db, User, role, account, *, must_change_password=False,
                 is_active=True, first_name='Prueba', last_name='E2E', **extra):
    user = User.query.filter_by(username=account.username).first()
    if user is None:
        user = User(
            first_name=first_name, last_name=last_name, mother_last_name='',
            username=account.username, password=account.password,
            email=f'{account.username}@siiap.test',
            is_internal=account.role != 'applicant', role_id=role.id,
            must_change_password=must_change_password,
        )
        db.session.add(user)
    else:
        # Re-seeding restores the known state (a test may have changed it).
        user.password = generate_password_hash(account.password)
        user.must_change_password = must_change_password
        user.role_id = role.id
    user.is_active = is_active
    for key, value in extra.items():
        setattr(user, key, value)
    db.session.flush()
    return user


def _upsert_program(db, Program, *, slug, name, coordinator, **fields):
    program = Program.query.filter_by(slug=slug).first()
    if program is None:
        program = Program(name=name, description=f'Descripción de {name}.',
                          coordinator_id=coordinator.id, slug=slug, is_active=True,
                          **fields)
        db.session.add(program)
    else:
        program.coordinator_id = coordinator.id
    db.session.flush()
    return program


def main() -> int:
    from datetime import date, timedelta

    from app import create_app, db
    from app.models.academic_period import AcademicPeriod
    from app.models.archive import Archive
    from app.models.phase import Phase
    from app.models.program import Program
    from app.models.program_step import ProgramStep
    from app.models.step import Step
    from app.models.user import User
    from app.models.user_program import UserProgram
    from app.models.permission import Permission
    from app.models.role_permission import RolePermission
    from tests.support.factories import get_or_create_role

    def grant(role, *codenames):
        # Local on purpose: tests.support.factories.get_or_create_permission
        # passes is_active= to Permission(), whose __init__ does not take it
        # (reported; fixing it is outside tests/e2e).
        for codename in codenames:
            perm = Permission.query.filter_by(codename=codename).first()
            if perm is None:
                parts = codename.split('.')
                perm = Permission(codename=codename, display_name=codename,
                                  resource=parts[0], perm_type=parts[1],
                                  action='.'.join(parts[2:]))
                db.session.add(perm)
                db.session.flush()
            if RolePermission.query.filter_by(role_id=role.id,
                                              permission_id=perm.id).first() is None:
                db.session.add(RolePermission(role_id=role.id, permission_id=perm.id))
        db.session.flush()

    application = create_app()
    with application.app_context():
        # Roles + permissions
        roles = {}
        for role_name, codenames in permission_sets().items():
            role = get_or_create_role(role_name)
            grant(role, *sorted(codenames))
            roles[role_name] = role

        # Users
        coord = _upsert_user(db, User, roles['program_admin'], acc.COORDINATOR,
                             first_name='Carla', last_name='Coordinadora')
        _upsert_user(db, User, roles['postgraduate_admin'], acc.POSTGRAD,
                     first_name='Pablo', last_name='Posgrado')
        _upsert_user(db, User, roles['social_service'], acc.SOCIAL,
                     first_name='Sofia', last_name='Social')
        applicant = _upsert_user(db, User, roles['applicant'], acc.APPLICANT,
                                 first_name='Ana', last_name='Aspirante')
        _upsert_user(db, User, roles['applicant'], acc.APPLICANT_NEW,
                     first_name='Nora', last_name='Nueva')
        student = _upsert_user(db, User, roles['student'], acc.STUDENT,
                               first_name='Esteban', last_name='Estudiante',
                               control_number='E2E00001')
        for forced in acc.FORCED_POOL:
            _upsert_user(db, User, roles['applicant'], forced,
                         must_change_password=True, first_name='Fabiola', last_name='Forzada')
        for inactive in (acc.INACTIVE, acc.INACTIVE_API):
            _upsert_user(db, User, roles['applicant'], inactive,
                         is_active=False, first_name='Ines', last_name='Inactiva')

        # Programs
        program = _upsert_program(
            db, Program, slug=acc.PROGRAM_SLUG, name=acc.PROGRAM_NAME,
            coordinator=coord, program_level='Maestría', academic_area='Ingeniería',
            duration_semesters=4, duration_years=2, modality='Escolarizada',
            introduction_text='Programa sintético para pruebas de extremo a extremo.',
        )
        _upsert_program(
            db, Program, slug=acc.PROGRAM_SLUG_2, name=acc.PROGRAM_NAME_2,
            coordinator=coord, program_level='Doctorado', academic_area='Ciencias',
        )

        # Admission window open today => the CTA opens the enrollment modal.
        today = date.today()
        period = AcademicPeriod.query.filter_by(code='20991').first()
        if period is None:
            period = AcademicPeriod(
                code='20991', name='Periodo E2E',
                start_date=today - timedelta(days=30), end_date=today + timedelta(days=150),
                admission_start_date=today - timedelta(days=60),
                admission_end_date=today + timedelta(days=60),
                is_active=True, status='active',
            )
            db.session.add(period)
        else:
            period.admission_start_date = today - timedelta(days=60)
            period.admission_end_date = today + timedelta(days=60)
        db.session.flush()

        # One admission phase / step / uploadable archive on the first program
        phase = Phase.query.filter_by(name='admission').first()
        if phase is None:
            phase = Phase(name='admission', description='Fase de admisión')
            db.session.add(phase)
            db.session.flush()
        step = Step.query.filter_by(name=acc.STEP_NAME).first()
        if step is None:
            step = Step(name=acc.STEP_NAME, description='Paso de prueba', phase_id=phase.id)
            db.session.add(step)
            db.session.flush()
        if ProgramStep.query.filter_by(program_id=program.id, step_id=step.id).first() is None:
            db.session.add(ProgramStep(program_id=program.id, step_id=step.id, sequence=1))
        if Archive.query.filter_by(name=acc.ARCHIVE_NAME).first() is None:
            db.session.add(Archive(name=acc.ARCHIVE_NAME,
                                   description='Documento de prueba (PDF).',
                                   file_path=None, step_id=step.id))
        db.session.flush()

        # Enrollments
        if UserProgram.query.filter_by(user_id=applicant.id, program_id=program.id).first() is None:
            db.session.add(UserProgram(user_id=applicant.id, program_id=program.id,
                                       admission_status='in_progress',
                                       admission_period_id=period.id))
        if UserProgram.query.filter_by(user_id=student.id, program_id=program.id).first() is None:
            db.session.add(UserProgram(user_id=student.id, program_id=program.id,
                                       admission_status='enrolled',
                                       admission_period_id=period.id, current_semester=1))

        db.session.commit()

        print('e2e seed: cuentas creadas (usuario / contrasena / rol)')
        for a in (acc.APPLICANT, acc.APPLICANT_NEW, acc.STUDENT, acc.COORDINATOR,
                  acc.POSTGRAD, acc.SOCIAL, *acc.FORCED_POOL, acc.INACTIVE, acc.INACTIVE_API):
            print(f'  {a.username:<22} {a.password:<16} {a.role}')
        print(f'  programas: {acc.PROGRAM_SLUG}, {acc.PROGRAM_SLUG_2}')
    return 0


if __name__ == '__main__':
    sys.exit(main())
