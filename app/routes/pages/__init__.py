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
    from app.routes.pages.admin.email_pages import pages_emails

    blueprints = [
        pages_auth,
        program_bp,
        pages_user,
        pages_admin,
        pages_emails,
        pages_coordinator,
        pages_events_public,
    ]

    for bp in blueprints:
        app.register_blueprint(bp)
