# app/services/payment_reference_service.py
"""
Servicio de referencia bancaria para pago semestral.

ESTADO: Stub (Módulo A pendiente de integración).
El método generate() devuelve siempre None en todos los campos.
Cuando se integre el algoritmo bancario, únicamente este archivo cambia.
"""


class PaymentReferenceService:
    """Servicio para generar referencias bancarias de inscripción semestral."""

    @staticmethod
    def generate(user_program_id: int, period_id: int) -> dict:
        """
        Genera la referencia bancaria para la inscripción semestral.

        Stub: Devuelve siempre None en todos los campos hasta que se integre
        el algoritmo de generación del número de referencia (Módulo A).

        Args:
            user_program_id: ID del UserProgram del estudiante.
            period_id: ID del AcademicPeriod de destino.

        Returns:
            {
                'reference': None,   # Número de referencia bancaria
                'amount': None,      # Monto a pagar
                'due_date': None,    # Fecha límite de pago
            }
        """
        return {
            'reference': None,
            'amount': None,
            'due_date': None,
        }


def get_payment_reference_for_student(user_program_id: int) -> dict:
    """
    Retorna la información de referencia bancaria para el estudiante.

    Compatibilidad con la llamada existente en permanence_api.py.
    Delega al stub de PaymentReferenceService.

    Returns:
        {
          'configured': bool,
          'file_url': str | None,
          'template_name': str | None,
          'error': str | None
        }
    """
    from app.models.user_program import UserProgram

    up = UserProgram.query.get(user_program_id)
    if not up:
        return {
            'configured': False,
            'file_url': None,
            'template_name': None,
            'error': 'UserProgram no encontrado',
        }

    ref = PaymentReferenceService.generate(up.id, None)

    return {
        'configured': False,
        'file_url': None,
        'template_name': None,
        'reference': ref.get('reference'),
        'amount': ref.get('amount'),
        'due_date': ref.get('due_date'),
        'error': (
            'La generación automática de referencias bancarias estará disponible próximamente.'
        ),
    }
