"""Backfill of migration o0j1k2l3m4n5 (curriculum plan v1 from curriculum_structure)."""

import importlib.util
from pathlib import Path

import pytest

from app import db
from app.models.curriculum_plan import CurriculumPlan
from app.models.subject import Subject
from app.models.user_program import UserProgram
from tests.support.factories import enroll, make_program, make_user

MIGRATION = (Path(__file__).resolve().parents[2] / 'migrations' / 'versions'
             / 'o0j1k2l3m4n5_curriculum_groups_enrollment.py')

LEGACY = {'type': 'semestral', 'semesters': [
    {'number': 1, 'name': 'Primer Semestre', 'subjects': ['Matemáticas', 'Metodología']},
    {'number': 2, 'name': 'Segundo Semestre', 'subjects': ['Algoritmos', 'Optativa I']},
]}
CANONICAL = {'semesters': [
    {'semester': 1, 'courses': [{'code': 'MC-01', 'name': 'Cómputo', 'credits': 5},
                                {'code': 'MC-01', 'name': 'Duplicada', 'credits': 5}]},
    {'semester': 3, 'courses': [{'name': 'Optativa II'}]},
]}


@pytest.fixture
def migration():
    spec = importlib.util.spec_from_file_location('mig_o0j1', MIGRATION)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _subjects(program):
    plan = CurriculumPlan.query.filter_by(program_id=program.id).one()
    return plan, Subject.query.filter_by(plan_id=plan.id).order_by(Subject.sequence).all()


def test_backfill_reads_the_legacy_shape(app, migration):
    program = make_program(curriculum_structure=LEGACY)
    up = enroll(make_user('student'), program, admission_status='enrolled')
    applicant = enroll(make_user('applicant'), program)

    counts = migration.backfill_curriculum_plans(db.session.connection())
    db.session.expire_all()

    plan, subjects = _subjects(program)
    assert plan.version == 1 and plan.is_current
    assert [(s.name, s.suggested_semester, s.kind) for s in subjects] == [
        ('Matemáticas', 1, 'required'), ('Metodología', 1, 'required'),
        ('Algoritmos', 2, 'required'), ('Optativa I', 2, 'elective_slot'),
    ]
    assert all(s.key is None and s.credits is None for s in subjects)
    assert db.session.get(UserProgram, up.id).curriculum_plan_id == plan.id
    assert db.session.get(UserProgram, applicant.id).curriculum_plan_id == plan.id
    assert counts == {'programs': 1, 'subjects': 4, 'slots': 1, 'user_programs': 2}


def test_backfill_reads_the_canonical_shape_and_drops_duplicate_keys(app, migration):
    program = make_program(curriculum_structure=CANONICAL)

    migration.backfill_curriculum_plans(db.session.connection())
    db.session.expire_all()

    _, subjects = _subjects(program)
    assert [(s.key, s.name, s.credits, s.suggested_semester, s.kind) for s in subjects] == [
        ('MC-01', 'Cómputo', 5, 1, 'required'),
        (None, 'Duplicada', 5, 1, 'required'),
        (None, 'Optativa II', None, 3, 'elective_slot'),
    ]


def test_program_without_structure_gets_an_empty_plan_and_rerun_is_a_noop(app, migration):
    program = make_program()

    migration.backfill_curriculum_plans(db.session.connection())
    again = migration.backfill_curriculum_plans(db.session.connection())

    plan, subjects = _subjects(program)
    assert subjects == []
    assert again['programs'] == 0
