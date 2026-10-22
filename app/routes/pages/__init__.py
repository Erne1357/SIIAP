"""
Registro centralizado de todos los blueprints de páginas (server-side rendered).

Importado por app/__init__.py:
    from app.routes.pages import register_page_blueprints
    register_page_blueprints(app)
"""


def register_page_blueprints(app):
    from app.routes.pages.auth import pages_auth
    from app.routes.pages.programs_pages import program_bp
    from app.routes.pages.users_pages import pages_user
    from app.routes.pages.admin.admin_pages import pages_admin
    from app.routes.pages.coordinator_pages import pages_coordinator
    from app.routes.pages.event_pages import pages_events_public
    from app.routes.pages.student_record_pages import pages_student_record
    from app.routes.pages.curriculum_pages import pages_curriculum
    from app.routes.pages.course_groups_pages import pages_course_groups
    from app.routes.pages.teaching_pages import pages_teaching
    from app.routes.pages.kardex_pages import pages_kardex
    from app.routes.pages.grade_corrections_pages import pages_grade_corrections
    from app.routes.pages.grade_import_pages import pages_grade_import
    from app.routes.pages.academic_documents_pages import pages_academic_documents

    blueprints = [
        pages_auth,
        program_bp,
        pages_user,
        pages_admin,
        pages_coordinator,
        pages_events_public,
        pages_student_record,
        pages_curriculum,
        pages_course_groups,
        pages_teaching,
        pages_kardex,
        pages_grade_corrections,
        pages_grade_import,
        pages_academic_documents,
    ]

    for bp in blueprints:
        app.register_blueprint(bp)
