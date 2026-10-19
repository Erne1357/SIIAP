"""Every service error base is a DomainError; every *NotFound is a 404."""
import pytest

from app.services import (
    academic_period_service as aps,
    acceptance_service as acc,
    applicant_archive_service as arch,
    deferral_service as dfr,
    deliberation_service as dlb,
    password_reset_service as pwd,
    permanence_service as prm,
    permission_service as perm,
    profile_photo_service as photo,
    program_transfer_service as xfer,
    programs_service as progs,
    semester_transition_service as sem,
    student_bulk_service as bulk,
    student_record_service as rec,
)
from app.services.errors import DomainError, NotFoundError
from app.utils.validators import InputValidationError

BASES = [
    aps.AcademicPeriodError, aps.InvalidPeriodCode, aps.DuplicatePeriodCode,
    aps.InvalidDateRange, acc.AcceptanceError, acc.InvalidDocumentType,
    acc.InvalidStateTransition, acc.DocumentDebtError, dfr.DeferralError,
    dfr.DeferralNotAllowed, dlb.DeliberationError, dlb.InvalidStateTransition,
    pwd.PasswordResetError, pwd.TokenExpired, pwd.TokenAlreadyUsed, pwd.WeakPassword,
    pwd.MissingEmail, prm.PermanenceError, prm.InvalidStateTransition,
    photo.ProfilePhotoError, photo.PhotoChangeNotAllowed, progs.ProgramsError,
    progs.AlreadyEnrolledError, progs.AdmissionClosedError,
    progs.AdmissionAlreadyOpenError, progs.AlreadyInterestedError,
    xfer.ProgramTransferError, xfer.ProgramTransferNotAllowed,
    sem.TransitionError, sem.InvalidTransition, bulk.StudentBulkError,
    bulk.ValidationError, bulk.StudentCreationError, bulk.ProgramScopeError,
    rec.StudentRecordError, rec.AccessDenied, arch.PurgeError,
    arch.InvalidPurgeState, arch.InvalidPurgeType, perm.PermissionServiceError,
    InputValidationError,
]

NOT_FOUND = [
    aps.AcademicPeriodNotFound, acc.ApplicantNotFound, dfr.DeferralNotFound,
    dlb.ApplicantNotFound, pwd.TokenNotFound, prm.StudentNotFound,
    photo.PhotoRequestNotFound, progs.ProgramNotFound, xfer.ProgramTransferNotFound,
    sem.PeriodNotFound, sem.ProgramNotFound, rec.StudentNotFound,
    arch.PurgeRunNotFound,
]


@pytest.mark.parametrize('cls', BASES, ids=lambda c: f'{c.__module__}.{c.__name__}')
def test_service_errors_are_domain_errors(cls):
    assert issubclass(cls, DomainError)


@pytest.mark.parametrize('cls', NOT_FOUND, ids=lambda c: f'{c.__module__}.{c.__name__}')
def test_not_found_errors_map_to_404(cls):
    assert issubclass(cls, DomainError) and issubclass(cls, NotFoundError)
    assert cls.status_code == 404


def test_permission_service_error_keeps_message():
    err = perm.PermissionServiceError('No puedes delegar a ti mismo')
    assert str(err) == err.message == 'No puedes delegar a ti mismo'
    assert err.status_code == 400
    assert not issubclass(perm.PermissionServiceError, PermissionError)


def test_program_transfer_error_message_set():
    assert xfer.ProgramTransferError('hola').message == 'hola'


def test_input_validation_error_still_a_value_error():
    err = InputValidationError('Nombre inválido', field='name')
    assert isinstance(err, ValueError) and isinstance(err, DomainError)
    assert err.message == 'Nombre inválido' and err.fields == {'name': 'Nombre inválido'}
