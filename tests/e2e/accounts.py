"""
Synthetic accounts shared by the seed (app container) and the browser tests
(playwright container). Pure data: no imports from the app or from playwright,
so both sides can load it.

All passwords satisfy the app's strength rule (8+, upper, lower, digit, special).
"""

from dataclasses import dataclass

PASSWORD = 'E2e-Passw0rd!'
NEW_PASSWORD = 'E2e-Nuev0Pass!'


@dataclass(frozen=True)
class Account:
    username: str
    password: str
    role: str
    #: Text of the role badge rendered in the sidebar user card (role_label).
    role_label: str


APPLICANT = Account('e2e_aspirante', PASSWORD, 'applicant', 'Aspirante')
#: Applicant that is NOT enrolled in any program: the only one that sees the
#: "Postularme" call to action (an enrolled applicant sees "Ir a mi proceso").
APPLICANT_NEW = Account('e2e_aspirante_nuevo', PASSWORD, 'applicant', 'Aspirante')
STUDENT = Account('e2e_estudiante', PASSWORD, 'student', 'Estudiante')
COORDINATOR = Account('e2e_coordinador', PASSWORD, 'program_admin', 'Admin. Programa')
POSTGRAD = Account('e2e_posgrado', PASSWORD, 'postgraduate_admin', 'Admin. Posgrado')
SOCIAL = Account('e2e_servicio_social', PASSWORD, 'social_service', 'Servicio Social')
#: Users flagged must_change_password. The test that actually changes the
#: password consumes one for good (until the app container is re-seeded), so
#: there is a small pool and each test takes the first one that is still flagged.
FORCED_POOL = tuple(
    Account(f'e2e_cambio_forzado_{n}', PASSWORD, 'applicant', 'Aspirante')
    for n in range(1, 4)
)
FORCED = FORCED_POOL[0]
#: Disabled accounts, used only by the login-failure tests. Two of them because the
#: login throttle counts attempts per username (5 per 15 minutes, no way to clear
#: a failure for an account that can never sign in), so each test spends its own.
INACTIVE = Account('e2e_inactivo', PASSWORD, 'applicant', 'Aspirante')
INACTIVE_API = Account('e2e_inactivo_api', PASSWORD, 'applicant', 'Aspirante')

#: Accounts that log in without side effects (everything except FORCED).
ROLE_ACCOUNTS = (APPLICANT, STUDENT, COORDINATOR, POSTGRAD, SOCIAL)

PROGRAM_SLUG = 'e2e-maestria-ingenieria'
PROGRAM_NAME = 'Maestría en Ingeniería E2E'
PROGRAM_SLUG_2 = 'e2e-doctorado-ciencias'
PROGRAM_NAME_2 = 'Doctorado en Ciencias E2E'
ARCHIVE_NAME = 'Acta de nacimiento E2E'
STEP_NAME = 'Documentos personales E2E'
