"""Request models for study plans, course groups and teachers (phase 6B1).

Shape and type checks only; business rules stay in the services.
"""
from __future__ import annotations

from typing import Annotated, Any, Literal, Optional

from pydantic import BaseModel, BeforeValidator, Field


def _text_or_none(value: Any):
    if value is None:
        return None
    return str(value).strip() or None


def _int_or_none(value: Any):
    if value is None or (isinstance(value, str) and not value.strip()):
        return None
    return value


Text = Annotated[Optional[str], BeforeValidator(_text_or_none)]
OptionalInt = Annotated[Optional[int], BeforeValidator(_int_or_none)]


class SubjectIn(BaseModel):
    """A subject of a plan version."""

    name: Annotated[str, BeforeValidator(_text_or_none), Field(min_length=1, max_length=200)]
    key: Annotated[Optional[str], BeforeValidator(_text_or_none), Field(max_length=20)] = None
    credits: Annotated[Optional[int], BeforeValidator(_int_or_none), Field(ge=0, le=99)] = None
    suggested_semester: Annotated[Optional[int], BeforeValidator(_int_or_none),
                                  Field(ge=1, le=20)] = None
    kind: Literal['required', 'elective_slot', 'elective'] = 'required'
    sequence: OptionalInt = None


class CourseGroupIn(BaseModel):
    """A group of a subject in a period."""

    subject_id: int
    academic_period_id: int
    group_code: Annotated[str, BeforeValidator(_text_or_none), Field(min_length=1, max_length=10)]
    capacity: Annotated[int, Field(ge=1, le=500)]
    teacher_id: OptionalInt = None
    location: Annotated[Optional[str], BeforeValidator(_text_or_none), Field(max_length=120)] = None
    schedule: Text = None


class TeacherIn(BaseModel):
    """A new teacher account."""

    first_name: Annotated[str, BeforeValidator(_text_or_none), Field(min_length=1, max_length=100)]
    last_name: Annotated[str, BeforeValidator(_text_or_none), Field(min_length=1, max_length=100)]
    email: Annotated[str, BeforeValidator(_text_or_none), Field(min_length=3, max_length=120)]
