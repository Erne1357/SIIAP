"""Jinja context processors and Spanish display filters."""
from flask import g, has_request_context, request
from flask_login import current_user

from app.navigation import Navigation
from app.utils.csrf import generate_csrf_token
from app.utils.datetime_utils import (
    format_date_es, format_datetime_es, format_time_es, now_local,
)


def register_template_context(app):
    def _viewer_is_authenticated():
        """
        True only when there is a real logged-in viewer.

        This context processor runs on EVERY render_template, including the
        email templates that Celery tasks render with no request context. There
        current_user resolves to None, so touching .is_authenticated raised
        AttributeError and killed the render.
        """
        if not has_request_context():
            return False
        return bool(current_user and current_user.is_authenticated)

    @app.context_processor
    def inject_tokens_and_version():
        def has_perm(codename):
            """
            Helper de Jinja2 para comprobar permisos en templates.

            Uso en plantillas:
                {% if has_perm('coordinator.page.view') %}

            Responde SÓLO "¿qué puede hacer?" — nunca "¿sobre qué programa?".
            Una plantilla no debe decidir alcance: eso lo resuelve la ruta con
            `program_scope_required` antes de renderizar.
            """
            # Fuera de una petición (p. ej. una plantilla de correo renderizada
            # desde una tarea de Celery) current_user resuelve a None y
            # .is_authenticated revienta con AttributeError.
            if not _viewer_is_authenticated():
                return False
            return current_user.has_permission(codename)

        def _role_info():
            """
            (label, badge_class) para el rol visible del usuario.
            Centraliza la lógica que antes vivía duplicada en base.html, profile.html, dashboard.html.
            """
            if not _viewer_is_authenticated():
                return (None, None)
            if current_user.has_global_program_scope():
                return ('Admin. Posgrado', 'bg-danger')
            if current_user.has_permission('coordinator.page.view'):
                return ('Admin. Programa', 'bg-success')
            if current_user.has_permission('admin_review.page.view'):
                return ('Servicio Social', 'bg-warning text-dark')
            if current_user.has_permission('permanence.api.view_status'):
                return ('Estudiante', 'bg-primary')
            if current_user.has_permission('programs.api.enroll'):
                return ('Aspirante', 'bg-info text-dark')
            return (None, None)

        role_label, role_badge_class = _role_info()

        def page_nav():
            """
            Menu, active link and breadcrumb for this request (see app/navigation.py).

            Resolved once per request and shared by the desktop sidebar, the
            offcanvas and the page header. Anonymous visitors and renders with
            no request (Celery emails) get an empty menu.
            """
            if not _viewer_is_authenticated():
                return Navigation.empty()
            nav = getattr(g, '_page_nav', None)
            if nav is None:
                nav = Navigation.for_user(current_user, request.endpoint)
                g._page_nav = nav
            return nav

        def review_pending_count():
            """Pending "Por revisar" items for the sidebar badge (once per request)."""
            if not _viewer_is_authenticated():
                return 0
            count = getattr(g, '_review_pending_count', None)
            if count is None:
                from app.services import review_inbox_service
                count = review_inbox_service.pending_total(current_user)
                g._review_pending_count = count
            return count

        return {
            "static_version": app.config.get("STATIC_VERSION", "1.0.0"),
            "csrf_token": generate_csrf_token,
            # Expuesto para que las plantillas no escriban el año a mano
            # (pie de página de base.html / auth_base.html).
            "now_local": now_local,
            "has_perm": has_perm,
            "page_nav": page_nav,
            "review_pending_count": review_pending_count,
            "role_label": role_label,
            "role_badge_class": role_badge_class,
        }

    _ES_STATUS = {
        'in_progress': 'En Proceso',
        'interview_completed': 'Entrevista Completada',
        'deliberation': 'En Deliberación',
        'accepted': 'Aceptado',
        'rejected': 'Rechazado',
        'deferred': 'Diferido',
        'enrolled': 'Inscrito',
        'pending': 'Pendiente',
        'active': 'Activo',
        'completed': 'Completado',
        'on_leave': 'Baja Temporal',
        'dropped': 'Baja Definitiva',
        'approved': 'Aprobado',
        'used': 'Usado',
        'expired': 'Expirado',
        'registered': 'Inscrito',
        'attended': 'Asistió',
        'absent': 'Ausente',
        'cancelled': 'Cancelado',
        'confirmed': 'Confirmado',
        'scheduled': 'Programado',
    }
    _ES_ROLE = {
        'applicant': 'Aspirante',
        'program_admin': 'Coord. de Programa',
        'postgraduate_admin': 'Admin. de Posgrado',
        'social_service': 'Servicio Social',
        'student': 'Estudiante',
    }
    _ES_ACCEPTANCE_DOC = {
        'acceptance_letter': 'Carta de Aceptación',
        'course_schedule': 'Tira de Materias',
        'enrollment_receipt': 'Boleta de Servicios Escolares',
        'acceptance_opinion': 'Dictamen de Aceptación',
    }

    @app.template_filter('es_status')
    def _es_status_filter(value):
        if not value:
            return '—'
        return _ES_STATUS.get(value, str(value).replace('_', ' '))

    @app.template_filter('es_role')
    def _es_role_filter(value):
        if not value:
            return '—'
        return _ES_ROLE.get(value, value)

    @app.template_filter('es_doc_type')
    def _es_doc_type_filter(value):
        if not value:
            return '—'
        return _ES_ACCEPTANCE_DOC.get(value, value)

    @app.template_filter('fecha_es')
    def _fecha_es_filter(value, style='long'):
        """Render a date in Spanish: 'long' | 'short' | 'numeric'."""
        return format_date_es(value, style)

    @app.template_filter('hora_es')
    def _hora_es_filter(value):
        """Render the time of a datetime as 24h 'HH:MM' (empty when absent)."""
        return format_time_es(value)

    @app.template_filter('fechahora_es')
    def _fechahora_es_filter(value, style='long', include_time=True):
        """Render a datetime in Spanish wrapped in a semantic <time> element."""
        return format_datetime_es(value, style, include_time)
