# app/services/academic_period_service.py
from datetime import date
from app import db
from app.models.academic_period import AcademicPeriod


class AcademicPeriodNotFound(Exception):
    """Se lanza cuando no se encuentra el periodo académico."""
    pass


class InvalidPeriodCode(Exception):
    """Se lanza cuando el código de periodo es inválido."""
    pass


class DuplicatePeriodCode(Exception):
    """Se lanza cuando ya existe un periodo con ese código."""
    pass


class InvalidDateRange(Exception):
    """Se lanza cuando las fechas no son válidas."""
    pass


def list_academic_periods(include_completed=True):
    """
    Lista todos los periodos académicos ordenados por código descendente.

    Args:
        include_completed: Si es False, excluye periodos con status='completed'

    Returns:
        Lista de AcademicPeriod
    """
    query = AcademicPeriod.query

    if not include_completed:
        query = query.filter(AcademicPeriod.status != 'completed')

    return query.order_by(AcademicPeriod.code.desc()).all()


def get_academic_period_by_id(period_id: int):
    """
    Obtiene un periodo académico por su ID.

    Args:
        period_id: ID del periodo

    Returns:
        AcademicPeriod

    Raises:
        AcademicPeriodNotFound: Si no existe el periodo
    """
    period = AcademicPeriod.query.get(period_id)
    if not period:
        raise AcademicPeriodNotFound(f"Periodo académico con ID {period_id} no encontrado")
    return period


def get_academic_period_by_code(code: str):
    """
    Obtiene un periodo académico por su código.

    Args:
        code: Código del periodo (ej: "20253")

    Returns:
        AcademicPeriod

    Raises:
        AcademicPeriodNotFound: Si no existe el periodo
    """
    period = AcademicPeriod.query.filter_by(code=code).first()
    if not period:
        raise AcademicPeriodNotFound(f"Periodo académico con código {code} no encontrado")
    return period


def get_active_period():
    """
    Obtiene el periodo académico activo actual.

    Returns:
        AcademicPeriod o None si no hay ninguno activo
    """
    return AcademicPeriod.get_active_period()


def create_academic_period(data: dict, created_by: int = None):
    """
    Crea un nuevo periodo académico.

    Args:
        data: Diccionario con los campos del periodo:
            - code: Código único (YYYYN)
            - name: Nombre descriptivo
            - start_date: Fecha de inicio de clases
            - end_date: Fecha de fin de clases
            - admission_start_date: Inicio de admisiones
            - admission_end_date: Fin de admisiones
        created_by: ID del usuario que crea el periodo

    Returns:
        AcademicPeriod: El periodo creado

    Raises:
        InvalidPeriodCode: Si el código no tiene formato válido
        DuplicatePeriodCode: Si ya existe un periodo con ese código
        InvalidDateRange: Si las fechas no son válidas
    """
    code = data.get('code', '').strip()

    # Validar código
    if not AcademicPeriod.validate_code(code):
        raise InvalidPeriodCode(
            "El código debe tener formato YYYYN (ej: 20253 para Ago-Dic 2025)"
        )

    # Verificar duplicados
    existing = AcademicPeriod.query.filter_by(code=code).first()
    if existing:
        raise DuplicatePeriodCode(f"Ya existe un periodo con el código {code}")

    # Validar fechas
    start_date = _parse_date(data.get('start_date'))
    end_date = _parse_date(data.get('end_date'))
    admission_start = _parse_date(data.get('admission_start_date'))
    admission_end = _parse_date(data.get('admission_end_date'))

    # Validaciones de rango de fechas
    if admission_start >= admission_end:
        raise InvalidDateRange("La fecha de inicio de admisión debe ser anterior a la de fin")

    if start_date >= end_date:
        raise InvalidDateRange("La fecha de inicio de clases debe ser anterior a la de fin")

    if admission_end > start_date:
        raise InvalidDateRange("El periodo de admisión debe terminar antes de que inicien las clases")

    # Crear periodo
    period = AcademicPeriod(
        code=code,
        name=data.get('name', '').strip(),
        start_date=start_date,
        end_date=end_date,
        admission_start_date=admission_start,
        admission_end_date=admission_end,
        is_active=False,
        status='upcoming',
        created_by=created_by
    )

    db.session.add(period)
    db.session.commit()

    return period


def update_academic_period(period_id: int, data: dict):
    """
    Actualiza un periodo académico existente.

    Args:
        period_id: ID del periodo a actualizar
        data: Diccionario con los campos a actualizar

    Returns:
        AcademicPeriod: El periodo actualizado

    Raises:
        AcademicPeriodNotFound: Si no existe el periodo
        InvalidPeriodCode: Si el nuevo código no es válido
        DuplicatePeriodCode: Si el nuevo código ya está en uso
        InvalidDateRange: Si las fechas no son válidas
    """
    period = get_academic_period_by_id(period_id)

    # Si cambia el código, validar
    new_code = data.get('code')
    if new_code and new_code != period.code:
        if not AcademicPeriod.validate_code(new_code):
            raise InvalidPeriodCode(
                "El código debe tener formato YYYYN (ej: 20253 para Ago-Dic 2025)"
            )

        existing = AcademicPeriod.query.filter_by(code=new_code).first()
        if existing:
            raise DuplicatePeriodCode(f"Ya existe un periodo con el código {new_code}")

        period.code = new_code

    # Actualizar campos simples
    if 'name' in data:
        period.name = data['name'].strip()

    # Actualizar fechas si vienen
    if 'start_date' in data:
        period.start_date = _parse_date(data['start_date'])

    if 'end_date' in data:
        period.end_date = _parse_date(data['end_date'])

    if 'admission_start_date' in data:
        period.admission_start_date = _parse_date(data['admission_start_date'])

    if 'admission_end_date' in data:
        period.admission_end_date = _parse_date(data['admission_end_date'])

    # Validar rangos de fechas después de actualizar
    if period.admission_start_date >= period.admission_end_date:
        raise InvalidDateRange("La fecha de inicio de admisión debe ser anterior a la de fin")

    if period.start_date >= period.end_date:
        raise InvalidDateRange("La fecha de inicio de clases debe ser anterior a la de fin")

    if period.admission_end_date > period.start_date:
        raise InvalidDateRange("El periodo de admisión debe terminar antes de que inicien las clases")

    # Actualizar status si viene
    if 'status' in data:
        valid_statuses = ['upcoming', 'active', 'admission_closed', 'completed']
        if data['status'] in valid_statuses:
            period.status = data['status']

    db.session.commit()

    return period


def activate_period(period_id: int):
    """
    Activa un periodo académico, desactivando automáticamente cualquier otro activo.

    Args:
        period_id: ID del periodo a activar

    Returns:
        AcademicPeriod: El periodo activado

    Raises:
        AcademicPeriodNotFound: Si no existe el periodo
    """
    period = get_academic_period_by_id(period_id)
    period.activate()
    db.session.commit()

    return period


def deactivate_period(period_id: int):
    """
    Desactiva un periodo académico.

    Args:
        period_id: ID del periodo a desactivar

    Returns:
        AcademicPeriod: El periodo desactivado

    Raises:
        AcademicPeriodNotFound: Si no existe el periodo
    """
    period = get_academic_period_by_id(period_id)
    period.is_active = False
    db.session.commit()

    return period


def delete_academic_period(period_id: int):
    """
    Elimina un periodo académico.

    Args:
        period_id: ID del periodo a eliminar

    Returns:
        bool: True si se eliminó correctamente

    Raises:
        AcademicPeriodNotFound: Si no existe el periodo
    """
    period = get_academic_period_by_id(period_id)

    # TODO: En Fase 2, verificar que no tenga submissions o inscripciones asociadas

    db.session.delete(period)
    db.session.commit()

    return True


def _parse_date(value):
    """
    Convierte un valor a objeto date.

    Args:
        value: Puede ser string (YYYY-MM-DD) o date

    Returns:
        date object
    """
    if isinstance(value, date):
        return value

    if isinstance(value, str):
        return date.fromisoformat(value)

    raise ValueError(f"Formato de fecha inválido: {value}")
