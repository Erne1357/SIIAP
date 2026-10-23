"""
Request payload validation with pydantic.

    class CreateWindowIn(BaseModel):
        date: date
        start_time: time
        slot_minutes: int = Field(ge=5, le=240)

    payload = parse_json(CreateWindowIn)        # raises ValidationFailed

A malformed payload raises `ValidationFailed` (a DomainError): the app-level
handler answers 400 VALIDATION_ERROR with a Spanish message and a per-field
map, so the route keeps only the happy path. pydantic's own messages are
English and never reach the UI.
"""
from __future__ import annotations

from typing import Any, Optional, TypeVar

from flask import request
from pydantic import BaseModel, ValidationError

from app.services.errors import ValidationFailed

M = TypeVar('M', bound=BaseModel)

GENERIC_MESSAGE = 'Revisa los datos enviados: hay campos faltantes o inválidos.'

# pydantic error type -> Spanish message (ctx values are interpolated).
_MESSAGES_ES = {
    'missing': 'Este campo es obligatorio.',
    'string_type': 'Debe ser texto.',
    'string_too_short': 'Debe tener al menos {min_length} caracteres.',
    'string_too_long': 'Debe tener como máximo {max_length} caracteres.',
    'string_pattern_mismatch': 'El formato no es válido.',
    'int_type': 'Debe ser un número entero.',
    'int_parsing': 'Debe ser un número entero.',
    'float_type': 'Debe ser un número.',
    'float_parsing': 'Debe ser un número.',
    'bool_type': 'Debe ser verdadero o falso.',
    'bool_parsing': 'Debe ser verdadero o falso.',
    'greater_than': 'Debe ser mayor que {gt}.',
    'greater_than_equal': 'Debe ser mayor o igual que {ge}.',
    'less_than': 'Debe ser menor que {lt}.',
    'less_than_equal': 'Debe ser menor o igual que {le}.',
    'date_type': 'Debe ser una fecha (AAAA-MM-DD).',
    'date_parsing': 'Debe ser una fecha (AAAA-MM-DD).',
    'date_from_datetime_parsing': 'Debe ser una fecha (AAAA-MM-DD).',
    'datetime_type': 'Debe ser una fecha y hora.',
    'datetime_parsing': 'Debe ser una fecha y hora.',
    'time_type': 'Debe ser una hora (HH:MM).',
    'time_parsing': 'Debe ser una hora (HH:MM).',
    'uuid_type': 'Identificador inválido.',
    'uuid_parsing': 'Identificador inválido.',
    'literal_error': 'Valor no permitido.',
    'enum': 'Valor no permitido.',
    'list_type': 'Debe ser una lista.',
    'too_short': 'Debe tener al menos {min_length} elementos.',
    'too_long': 'Debe tener como máximo {max_length} elementos.',
    'extra_forbidden': 'Campo no permitido.',
    'model_type': 'Formato inválido.',
    'dict_type': 'Formato inválido.',
    'value_error': 'Valor inválido.',
}


def _field_name(loc: tuple) -> str:
    return '.'.join(str(part) for part in loc) or '_body'


def _message_es(err: dict) -> str:
    # A custom validator raising ValueError("...") in Spanish keeps its text.
    if err.get('type') == 'value_error':
        ctx_error = (err.get('ctx') or {}).get('error')
        if ctx_error is not None and str(ctx_error):
            return str(ctx_error)
    template = _MESSAGES_ES.get(err.get('type', ''), 'Valor inválido.')
    try:
        return template.format(**(err.get('ctx') or {}))
    except (KeyError, IndexError):
        return template


def validation_fields(exc: ValidationError) -> dict[str, str]:
    """{"field.path": "mensaje en español"} for each error (first one wins)."""
    fields: dict[str, str] = {}
    for err in exc.errors():
        fields.setdefault(_field_name(tuple(err.get('loc', ()))), _message_es(err))
    return fields


def parse_model(model: type[M], data: Any) -> M:
    """Validate `data` against `model` or raise ValidationFailed."""
    try:
        return model.model_validate(data if data is not None else {})
    except ValidationError as exc:
        raise ValidationFailed(GENERIC_MESSAGE, fields=validation_fields(exc)) from exc


def parse_json(model: type[M], data: Optional[Any] = None) -> M:
    """Validate the request's JSON body (or `data`) against `model`."""
    if data is None:
        data = request.get_json(silent=True)
    if data is not None and not isinstance(data, dict):
        raise ValidationFailed('El cuerpo de la petición debe ser un objeto JSON.')
    return parse_model(model, data)


def parse_form(model: type[M]) -> M:
    """Validate `request.form` (multipart or urlencoded) against `model`."""
    return parse_model(model, request.form.to_dict(flat=True))
