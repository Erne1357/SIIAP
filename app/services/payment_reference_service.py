# app/services/payment_reference_service.py
"""
Servicio para generar referencias bancarias de pago semestral.

PENDIENTE: Integrar el algoritmo de generación del número de referencia
del sistema existente. Hasta entonces, el stub retorna un estado controlado
que permite mostrar la UI al estudiante aunque la funcionalidad no esté activa.
"""

from app.models.document_template import DocumentTemplate
from app.models.user_program import UserProgram


def get_payment_reference_for_student(user_program_id: int) -> dict:
    """
    Retorna la información de referencia bancaria para el estudiante.

    Returns:
        {
          'configured': bool,       # True si existe plantilla para el programa
          'file_url': str | None,   # URL del PDF generado (None hasta integrar algoritmo)
          'template_name': str | None,
          'error': str | None       # Mensaje informativo (no es error HTTP)
        }
    """
    up = UserProgram.query.get(user_program_id)
    if not up:
        return {
            'configured': False,
            'file_url': None,
            'template_name': None,
            'error': 'UserProgram no encontrado',
        }

    template = DocumentTemplate.get_for_program(
        program_id=up.program_id,
        document_type='payment_reference',
    )

    if not template:
        return {
            'configured': False,
            'file_url': None,
            'template_name': None,
            'error': (
                'La referencia bancaria no está configurada para tu programa. '
                'Contacta al coordinador.'
            ),
        }

    # TODO: Cuando el algoritmo esté disponible, descomentar y completar:
    # from app.models.academic_period import AcademicPeriod
    # active_period = AcademicPeriod.get_active_period()
    # ref_number = _generate_reference_number(
    #     user_id=up.user_id,
    #     program_id=up.program_id,
    #     period_code=active_period.code,
    # )
    # file_path = _render_pdf(template, up, ref_number, active_period)
    # return {
    #     'configured': True,
    #     'file_url': f'/files/doc/{file_path}',
    #     'template_name': template.name,
    #     'error': None,
    # }

    return {
        'configured': True,
        'file_url': None,
        'template_name': template.name,
        'error': (
            'La generación automática de referencias bancarias estará disponible próximamente.'
        ),
    }
