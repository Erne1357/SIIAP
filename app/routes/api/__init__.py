"""
Registro centralizado de todos los blueprints de la API REST.

Importado por app/__init__.py:
    from app.routes.api import register_api_blueprints
    register_api_blueprints(app)
"""


def register_api_blueprints(app):
    from app.routes.api.auth_api import api_auth_bp
    from app.routes.api.programs_api import api_programs
    from app.routes.api.admission_api import api_admission
    from app.routes.api.submissions_api import api_submissions
    from app.routes.api.files_api import api_files
    from app.routes.api.users_api import api_users
    from app.routes.api.admin.review_api import api_review
    from app.routes.api.extensions_api import api_extensions
    from app.routes.api.events_api import api_events
    from app.routes.api.appointments_api import api_appointments
    from app.routes.api.program_changes_api import api_program_changes
    from app.routes.api.retention_api import api_retention
    from app.routes.api.archives_api import api_archives
    from app.routes.api.coordinator_api import api_coordinator
    from app.routes.api.attendance_api import api_attendance
    from app.routes.api.invitations_api import api_invitations
    from app.routes.api.interviews_api import api_interviews
    from app.routes.api.admin.users_api import api_admin_users
    from app.routes.api.admin.history_api import api_admin_history
    from app.routes.api.notifications_api import api_notifications
    from app.routes.api.emails_api import api_emails
    from app.routes.api.academic_period_api import api_academic_periods
    from app.routes.api.deliberation_api import api_deliberation
    from app.routes.api.acceptance_api import api_acceptance
    from app.routes.api.permanence_api import api_permanence
    from app.routes.api.health_api import api_health
    from app.routes.api.admin.celery_api import api_celery_admin

    blueprints = [
        # Auth
        api_auth_bp,
        # Recursos académicos
        api_programs,
        api_admission,
        api_submissions,
        api_files,
        api_users,
        api_extensions,
        api_events,
        api_appointments,
        api_program_changes,
        api_retention,
        api_archives,
        api_coordinator,
        api_attendance,
        api_invitations,
        api_interviews,
        api_academic_periods,
        api_deliberation,
        api_acceptance,
        api_permanence,
        # Admin
        api_review,
        api_admin_users,
        api_admin_history,
        api_celery_admin,
        # Sistema
        api_notifications,
        api_emails,
        api_health,
    ]

    for bp in blueprints:
        app.register_blueprint(bp)
