# app/routes/api/coordinator_api.py
from flask import Blueprint, request
from flask_login import login_required, current_user

from app.utils.permissions import (
    permission_required,
    any_permission_required,
    guard_user_scope,
)
from app.routes._public_id import resolved_id
from app.services import program_scope_service as scope_service
from app.services import coordinator_service
from app.services import student_admission_detail_service as student_detail_service
from app.services.errors import DomainError
from app.services.user_history_service import UserHistoryService
from app.utils.history_formatter import HistoryFormatter
from app.models.user import User
from app.models.archive import Archive
from app.schemas.coordinator import (
    ListStudentsQuery,
    StudentHistoryQuery,
    UploadForStudentForm,
)
from app.services.admission_service import get_admission_state
from app.utils.api_response import (
    api_ok, api_error, api_not_found, api_server_error, domain_error_response,
)
from app.utils.validation import parse_form, parse_model

api_coordinator = Blueprint('api_coordinator', __name__, url_prefix='/api/v1/coordinator')


def _scoped_user_program(student_id: int):
    """UserProgram of the student inside the caller's scope, or None."""
    return coordinator_service.scoped_user_program(current_user, student_id)


#: Denial text used by every "no such student here" branch of this blueprint.
#: One string for all causes (unknown UUID, malformed UUID, not an
#: applicant/student account) so none of them is distinguishable.
STUDENT_NOT_FOUND_MESSAGE = 'Estudiante no encontrado'


def _resolve_student(student_uuid):
    """
    Public UUID → the User row, or None.

    None covers a malformed identifier, an unknown one and an account that is
    not an applicant/student — every caller turns all three into the same 404.
    """
    student = User.by_uuid(student_uuid)
    if student is None or not _is_student_account(student):
        return None
    return student


def _is_student_account(user) -> bool:
    """Sólo aspirantes y estudiantes son objetivo de los paneles de coordinación."""
    return getattr(getattr(user, 'role', None), 'name', None) in ('applicant', 'student')


def _summary_of(student, program, user_program=None, admission_state=None) -> dict:
    """
    Nivel reducido entre programas: nombre, correo y progreso/estado.

    Se arma plano y se pasa por `to_cross_program_summary`, que descarta todo lo
    que no esté en la lista blanca — incluido cualquier campo que se agregue
    después. Nunca construyas el payload restringido a mano.
    """
    flat = {
        # Public handle. The key stays `id` because
        # `CROSS_PROGRAM_SUMMARY_FIELDS` allow-lists by key name.
        "id": str(student.uuid) if student.uuid else None,
        "full_name": f"{student.first_name} {student.last_name} {student.mother_last_name or ''}".strip(),
        "email": student.email,
        "program_id": program.id if program else None,
        "program_name": program.name if program else None,
        "program_slug": program.slug if program else None,
        "can_manage": False,
    }
    if user_program is not None:
        flat.update({
            "admission_status": user_program.admission_status,
            "current_semester": user_program.current_semester or 1,
        })
    if admission_state is not None:
        counts = admission_state.get('status_count', {})
        flat.update({
            "progress_percentage": admission_state.get('progress_pct', 0),
            "approved_docs": counts.get('approved', 0),
            "pending_docs": counts.get('pending', 0),
            "rejected_docs": counts.get('rejected', 0),
            "extended_docs": admission_state.get('extended_docs', 0),
        })
    return scope_service.to_cross_program_summary(flat)


def _restricted_permanence_payload(student, user_program, program) -> dict:
    """
    Respuesta de `/permanence-details` para un estudiante de otro programa.

    Conserva la forma del payload (el modal la consume tal cual) pero cada
    campo prohibido sale en `None` / vacío: foto, número de control, beca
    SECIHTI, periodo, inscripción semestral e historial de semestres.
    """
    s = _summary_of(student, program, user_program=user_program)
    return {
        "restricted": True,
        "student": {
            "id": s.get('id'),
            "full_name": s.get('full_name'),
            "email": s.get('email'),
            "avatar_url": None,
            "control_number": None,
        },
        "user_program": {
            "id": None,
            "current_semester": s.get('current_semester'),
            "has_conacyt_scholarship": None,
            "admission_status": s.get('admission_status'),
        },
        "program": {
            "id": s.get('program_id'),
            "name": s.get('program_name'),
        },
        "active_period": None,
        "current_enrollment": None,
        "pending_admission_count": None,
        "semester_history": [],
        "can_manage": False,
    }


def _restricted_details_payload(student, program, admission_state) -> dict:
    """
    Respuesta de `/details` para un estudiante de otro programa.

    Mismas claves de siempre, pero cada dato prohibido sale en `None`: los
    personales (CURP, RFC, NSS, domicilio, fecha y lugar de nacimiento, contacto
    de emergencia), la foto, los documentos con sus URLs y la elegibilidad de
    entrevista.

    `profile_data` conserva su FORMA con los valores en `None` en lugar de venir
    como `None` entero. El modal del coordinador la recorre campo por campo, y
    un `null` en la raíz reventaba el render con un TypeError que se pintaba
    como «Error al cargar información», dejando inalcanzable el nivel reducido
    que esta función existe para servir. Vaciar los valores comunica lo mismo
    —no hay dato disponible— sin romper al consumidor.
    """
    s = _summary_of(student, program, admission_state=admission_state)
    return {
        "restricted": True,
        "student": {
            "id": s.get('id'),
            "full_name": s.get('full_name'),
            "email": s.get('email'),
            "avatar_url": None,
            "profile_completed": None,
            "registration_date": None,
            "program": {
                "id": s.get('program_id'),
                "name": s.get('program_name'),
                "slug": s.get('program_slug'),
            },
            "profile_data": {
                "phone": None,
                "mobile_phone": None,
                "address": None,
                "curp": None,
                "rfc": None,
                "birth_date": None,
                "birth_place": None,
                "nss": None,
                "emergency_contact": {
                    "name": None,
                    "phone": None,
                    "relationship": None,
                },
            },
        },
        "documents": [],
        "interview": {
            "has_interview": False,
            "appointment": None,
            "eligibility": {"eligible": None, "missing_items": []},
        },
        "metrics": {
            "total_documents": None,
            "approved": s.get('approved_docs'),
            "pending": s.get('pending_docs'),
            "rejected": s.get('rejected_docs'),
            "extended": s.get('extended_docs'),
            "in_review": None,
            "progress_percentage": s.get('progress_percentage'),
        },
        "missing_documents": [],
        "can_manage": False,
    }

@api_coordinator.route('/students', methods=['GET'])
@login_required
@permission_required('coordinator.api.list_students')
def list_students():
    """
    Lista estudiantes que el coordinador puede ver/gestionar.
    Filtros: program_id, phase, status, search, show_other

    Alcance: las filas de programas ajenos existen por decisión del dueño, pero
    se proyectan al nivel reducido (nombre / correo / progreso) con
    `to_cross_program_summary`. Ningún dato personal, foto ni documento sale de
    aquí para un programa fuera del alcance del llamador.
    """
    q = parse_model(ListStudentsQuery, request.args.to_dict())
    program_id = q.program_id
    phase = q.phase  # admission, permanence, conclusion
    status = q.status  # pending, review, approved, rejected
    search = q.search
    show_other = q.show_other

    # El toggle "ver otros programas" es exactamente el nivel reducido.
    if show_other and not scope_service.may_view_cross_program_summary(current_user):
        show_other = False

    # Programas que puede gestionar el coordinador (propios + delegados).
    # None = alcance global (jefe de posgrado); set() vacío = sin alcance.
    scope = scope_service.accessible_program_ids(current_user)

    if scope is not None and not show_other and not scope:
        return api_ok({"students": []})

    # La población del panel (cuentas activas) y la búsqueda restringida a
    # campos del nivel reducido viven en el servicio.
    results = coordinator_service.list_panel_rows(
        scope, show_other=show_other, program_id=program_id, search=search,
    )
    students = []

    active_period_id = coordinator_service.get_active_period_id()

    # Una sola resolución de alcance para toda la página.
    manageable_pids = scope_service.programs_in_scope(
        current_user, {program.id for _, _, program in results}
    )

    for user, user_program, program in results:
        # Calcular estado actual del estudiante
        admission_state = get_admission_state(user.id, program.id, user_program)
        # Métricas de permanencia basadas en SemesterEnrollment + duración del programa
        perm = coordinator_service.compute_permanence_metrics(user_program, program, active_period_id)
        # Determinar fase actual basada en estado
        current_phase = _determine_current_phase(admission_state, user_program, perm)
        
        # Filtro por fase
        if phase and current_phase != phase:
            continue
        
        # ¿Puede gestionar este estudiante? (el programa de la fila está dentro
        # del alcance del llamador — el jefe de posgrado siempre pasa)
        can_manage = program.id in manageable_pids

        # Calcular métricas
        student_data = {
            "id": str(user.uuid) if user.uuid else None,
            "full_name": f"{user.first_name} {user.last_name}",
            "email": user.email,
            "avatar_url": user.avatar_url,
            "program_id": program.id,
            "program_name": program.name,
            "current_phase": current_phase,
            "can_manage": can_manage,
            
            # Métricas de admisión
            "progress_percentage": admission_state.get("progress_pct", 0),
            "approved_docs": admission_state["status_count"].get("approved", 0),
            "pending_docs": admission_state["status_count"].get("pending", 0),
            "rejected_docs": admission_state["status_count"].get("rejected", 0),
            "extended_docs": admission_state.get("extended_docs", 0),
            "overall_status": _determine_overall_status(admission_state),
            "ready_for_interview": _check_ready_for_interview(admission_state),
            
            # Métricas de permanencia (basadas en SemesterEnrollment real)
            "current_semester": perm["current_semester"],
            "completed_semesters": perm["completed_semesters"],
            "total_semesters": perm["total_semesters"],
            "academic_progress": perm["academic_progress"],
            "in_progress_segment": perm["in_progress_segment"],
            "academic_status": perm["academic_status"],
            # Métricas de conclusión reales (conclusion_service.progress).
            # Sólo para egresados/titulados o con tesis registrada (no por
            # current_phase). NOTE: se calcula por fila (N+1 acotado);
            # optimizar con carga por lotes si la lista crece.
            **coordinator_service.conclusion_summary(user_program),
        }

        # Fuera de alcance: sólo nombre, correo y progreso/estado. La proyección
        # elimina la foto de perfil y cualquier campo que se añada después.
        if not can_manage:
            student_data = scope_service.to_cross_program_summary(student_data)

        # Filtro por status
        if status and student_data.get("overall_status") != status:
            continue

        students.append(student_data)
    
    return api_ok({"students": students})

@api_coordinator.route('/manageable-students', methods=['GET'])
@login_required
@permission_required('coordinator.api.list_students')
def manageable_students():
    """
    Lista solo estudiantes que el coordinador puede gestionar (para selects)
    """
    scope = scope_service.accessible_program_ids(current_user)
    if scope is not None and not scope:
        return api_ok({"students": []})

    results = coordinator_service.list_manageable_applicants(scope)
    students = []

    for user, program in results:
        students.append({
            "id": str(user.uuid) if user.uuid else None,
            "full_name": f"{user.first_name} {user.last_name}",
            "email": user.email,
            "program_name": program.name
        })
    
    return api_ok({"students": students})

@api_coordinator.route('/student/<uuid:student_uuid>/uploadable-archives', methods=['GET'])
@login_required
@permission_required('coordinator.api.upload_for_student')
def student_uploadable_archives(student_uuid):
    """
    Lista archivos que el coordinador puede subir para un estudiante específico.

    El alcance es la MISMA regla que aplicaba `@program_scope_required`, ahora
    imperativa porque el URL trae un UUID y no un id. `guard_user_scope(None)`
    falla cerrado, así que un identificador desconocido y uno de otro programa
    devuelven exactamente el mismo 403.
    """
    student = _resolve_student(student_uuid)
    denied = guard_user_scope(resolved_id(student), allow_self=False)
    if denied:
        return denied
    student_id = student.id

    user_program = _scoped_user_program(student_id)
    if not user_program:
        return api_not_found("Estudiante no inscrito en programa")

    archives = []
    for archive, step, phase, existing in coordinator_service.uploadable_archives_for(
            student_id, user_program.program_id):
        archives.append({
            # Public handle — the browser posts it back as `archive_id`.
            "id": str(archive.uuid) if archive.uuid else None,
            "name": archive.name,
            "description": archive.description,
            "step_name": step.name,
            "phase_name": phase.name,
            "has_existing": bool(existing),
            "existing_status": existing.status if existing else None
        })

    return api_ok({"archives": archives})

@api_coordinator.route('/upload-for-student', methods=['POST'])
@login_required
@permission_required('coordinator.api.upload_for_student')
def upload_for_student():
    """
    Permite al coordinador subir un archivo por un estudiante usando el sistema de archivos
    """
    # `student_id` y `archive_id` viajan en el FORM, no en el URL, pero son la
    # misma clase de identificador: UUID público. `type=int` los habría leído
    # como None en silencio y el 400 siguiente lo habría tapado como "campo
    # faltante", así que se leen como texto y se resuelven aquí.
    form = parse_form(UploadForStudentForm)
    student = User.by_uuid(form.student_id)
    archive = Archive.by_uuid(form.archive_id)
    notes = form.notes
    decision = form.decision

    # Un identificador que no resuelve NO se distingue aquí de uno fuera de
    # alcance: los dos caen al mismo 403 de la guarda de abajo, que con None
    # falla cerrado. Contestar 400 "campos requeridos" cuando el UUID
    # simplemente no existe convertía el par en un oráculo — quien tuviera un
    # UUID ajeno sabría si señala a alguien real antes de que el alcance
    # llegara a opinar. El 400 se reserva para lo que de verdad es un campo
    # ausente.
    if not form.student_id or not form.archive_id:
        return api_error("VALIDATION_ERROR", "El estudiante y el archivo son requeridos.", status=400)

    if student is not None and not _is_student_account(student):
        student = None

    # Alcance ANTES de tocar nada: subir un documento es una escritura y una
    # escritura nunca cruza programas. El id viene en el form, no en el URL,
    # así que se usa la guarda imperativa; con None falla cerrado.
    denied = guard_user_scope(resolved_id(student), allow_self=False)
    if denied:
        return denied

    student_id = student.id
    if archive is None:
        return api_not_found("Archivo no encontrado")

    # Archivo opcional: si no se proporciona, el coordinador valida sin documento
    # (caso típico: examen presencial). Aspirantes/estudiantes siempre suben file.
    file = request.files.get('file') if 'file' in request.files else None
    if file and not file.filename:
        file = None
    if not file and not notes:
        return api_error(
            "VALIDATION_ERROR",
            "Si no subes un archivo debes proporcionar al menos un comentario justificativo",
            status=400,
        )
    
    # Inscripción sobre la que se escribe: siempre una que el llamador gestiona.
    user_program = _scoped_user_program(student_id)
    if not user_program:
        return api_not_found("Estudiante no inscrito")

    # Verificar que el archivo permite subida por coordinador
    if not archive.allow_coordinator_upload:
        return api_error("FORBIDDEN", "Este archivo no permite subida por coordinador", status=403)

    try:
        submission = coordinator_service.upload_for_student(
            student_id=student_id,
            user_program=user_program,
            archive=archive,
            file=file,
            decision=decision,
            notes=notes,
            uploader_id=current_user.id,
        )
    except DomainError as e:
        return domain_error_response(e)
    except Exception as e:
        return api_server_error(e, message="Error al guardar el documento.",
                                context="coordinator.upload_for_student")

    msg = (
        f"Documento {'aprobado' if decision == 'approve' else 'rechazado'} exitosamente por coordinador"
        + ('' if file else ' (sin archivo adjunto)')
    )
    return api_ok({
        # Handle público de la entrega recién creada.
        "submission_id": str(submission.uuid) if submission.uuid else None,
        "message": msg,
    }, status=201)


@api_coordinator.route('/programs', methods=['GET'])
@login_required
@permission_required('coordinator.api.list_students')
def list_coordinator_programs():
    """Lista programas que el coordinador puede gestionar"""
    scope = scope_service.accessible_program_ids(current_user)
    programs = coordinator_service.list_programs_in_scope(scope)

    items = [{
        "id": p.id,
        "name": p.name,
        "slug": p.slug,
        "description": p.description
    } for p in programs]
    
    return api_ok({"programs": items})

@api_coordinator.route('/student/<uuid:student_uuid>/permanence-details', methods=['GET'])
@login_required
@permission_required('coordinator.api.list_students')
def get_student_permanence_details(student_uuid):
    """
    Detalles de permanencia de un estudiante inscrito:
    semestre actual, periodo activo, confirmación semestral,
    beca CONACyT, documentos de admisión pendientes e historial semestral.
    """
    student = _resolve_student(student_uuid)
    if student is None:
        return api_not_found(STUDENT_NOT_FOUND_MESSAGE)
    student_id = student.id

    # La inscripción que se muestra es la del programa que el llamador gestiona;
    # sólo si no gestiona ninguna se cae al nivel reducido.
    user_program = _scoped_user_program(student_id)
    can_manage = user_program is not None
    if user_program is None:
        user_program = coordinator_service.first_user_program(student_id)
    if not user_program:
        return api_not_found("Sin programa")

    program = coordinator_service.get_program(user_program.program_id)

    # Fuera de alcance: nivel reducido (nombre / correo / progreso). Ni número
    # de control, ni foto, ni beca, ni historial semestral cruzan de programa.
    if not can_manage:
        if not scope_service.may_view_cross_program_summary(current_user):
            return api_error("FORBIDDEN", "No tienes acceso a la información de este estudiante",
                             status=403)
        return api_ok(_restricted_permanence_payload(student, user_program, program))

    # Periodo activo, confirmación del periodo actual e historial semestral
    active_period, current_enrollment, history = (
        coordinator_service.permanence_enrollment_context(user_program)
    )

    # Documentos de admisión pendientes/rechazados
    admission_state = get_admission_state(student_id, program.id, user_program)
    pending_admission = (
        admission_state['status_count'].get('pending', 0) +
        admission_state['status_count'].get('rejected', 0)
    )

    return api_ok({
        "student": {
            "id": str(student.uuid) if student.uuid else None,
            "full_name": f"{student.first_name} {student.last_name} {student.mother_last_name or ''}".strip(),
            "email": student.email,
            "avatar_url": student.avatar_url,
            "control_number": student.control_number,
        },
        "user_program": {
            "id": user_program.id,
            "current_semester": user_program.current_semester or 1,
            "has_conacyt_scholarship": user_program.has_conacyt_scholarship,
            "admission_status": user_program.admission_status,
        },
        "program": {
            "id": program.id,
            "name": program.name,
        },
        "active_period": {
            "id": active_period.id,
            "name": active_period.name,
            "code": active_period.code,
        } if active_period else None,
        "current_enrollment": {
            "id": current_enrollment.id,
            "semester_number": current_enrollment.semester_number,
            "status": current_enrollment.status,
            "enrollment_confirmed": current_enrollment.enrollment_confirmed,
            "confirmed_at": current_enrollment.confirmed_at.isoformat() if current_enrollment.confirmed_at else None,
            "notes": current_enrollment.notes,
        } if current_enrollment else None,
        "pending_admission_count": pending_admission,
        "semester_history": [
            {
                "id": se.id,
                "semester_number": se.semester_number,
                "period_name": se.academic_period.name if se.academic_period else "—",
                "period_code": se.academic_period.code if se.academic_period else "—",
                "status": se.status,
                "enrollment_confirmed": se.enrollment_confirmed,
                "confirmed_at": se.confirmed_at.isoformat() if se.confirmed_at else None,
                "notes": se.notes,
            }
            for se in history
        ],
        "can_manage": can_manage,
    })


@api_coordinator.route('/student/<uuid:student_uuid>/details', methods=['GET'])
@login_required
@permission_required('coordinator.api.list_students')
def get_student_details(student_uuid):
    """
    Obtiene detalles completos de un estudiante para el modal del coordinador.
    Incluye: perfil, documentos, entrevista, métricas
    """
    # 1. Obtener estudiante
    student = _resolve_student(student_uuid)
    if student is None:
        return api_not_found(STUDENT_NOT_FOUND_MESSAGE)
    student_id = student.id

    # 2. Resolver la inscripción dentro del alcance del llamador
    user_program = _scoped_user_program(student_id)
    can_manage = user_program is not None
    if user_program is None:
        user_program = coordinator_service.first_user_program(student_id)
    if not user_program:
        return api_not_found("Estudiante no inscrito")

    program = coordinator_service.get_program(user_program.program_id)

    # 3. Obtener estado de admisión completo
    admission_state = get_admission_state(student_id, program.id, user_program)

    # Fuera de alcance: nivel reducido. Los datos personales, los documentos y
    # sus URLs nunca cruzan de programa, aunque el llamador tenga el permiso.
    if not can_manage:
        if not scope_service.may_view_cross_program_summary(current_user):
            return api_error("FORBIDDEN", "No tienes acceso a la información de este estudiante",
                             status=403)
        return api_ok(_restricted_details_payload(student, program, admission_state))

    # 4-6. Documentos por paso, entrevista, elegibilidad y métricas: un solo
    # constructor compartido con la ficha de admisión del expediente.
    detail = student_detail_service.build_admission_detail(student, user_program, program)

    # 7. Construir respuesta
    return api_ok({
        "student": {
            "id": str(student.uuid) if student.uuid else None,
            "full_name": f"{student.first_name} {student.last_name} {student.mother_last_name or ''}".strip(),
            "email": student.email,
            "avatar_url": student.avatar_url,
            "profile_completed": student.profile_completed,
            "registration_date": student.registration_date.isoformat() if student.registration_date else None,
            "program": {
                "id": program.id,
                "name": program.name,
                "slug": program.slug
            },
            "profile_data": {
                "phone": student.phone,
                "mobile_phone": student.mobile_phone,
                "address": student.address,
                "curp": student.curp,
                "rfc": student.rfc,
                "birth_date": student.birth_date.isoformat() if student.birth_date else None,
                "birth_place": student.birth_place,
                "nss": student.nss,
                "emergency_contact": {
                    "name": student.emergency_contact_name,
                    "phone": student.emergency_contact_phone,
                    "relationship": student.emergency_contact_relationship
                }
            }
        },
        "documents": detail["documents"],
        "interview": detail["interview"],
        "metrics": detail["metrics"],
        "missing_documents": detail["missing_documents"],
        "can_manage": can_manage
    })

# ==================== FUNCIONES AUXILIARES ====================

def _determine_current_phase(admission_state, user_program, perm):
    """Determina la fase actual del estudiante."""
    # Egresados y titulados están en conclusión, sin importar los semestres
    # contados (el egreso se registra en academic_status).
    if user_program.academic_status in ('graduated', 'titled'):
        return "conclusion"
    # Estudiantes con número de control = ya están en permanencia o conclusión
    if user_program.admission_status == 'enrolled':
        if perm["completed_semesters"] >= perm["total_semesters"]:
            return "conclusion"
        return "permanence"

    # Si no ha completado admisión, está en admisión
    return "admission"

def _determine_overall_status(admission_state):
    """Determina el estado general del estudiante"""
    status_count = admission_state.get("status_count", {})
    
    if status_count.get("rejected", 0) > 0:
        return "rejected"
    elif status_count.get("review", 0) > 0:
        return "review"
    elif status_count.get("pending", 0) > 0:
        return "pending"
    elif status_count.get("approved", 0) > 0:
        return "approved"
    
    return "pending"


@api_coordinator.route('/students/<uuid:student_uuid>/history', methods=['GET'])
@login_required
@permission_required('coordinator.api.list_students')
def get_student_history(student_uuid):
    """
    Obtiene el historial formateado de un estudiante específico.
    Solo coordinadores y administradores pueden ver el historial de estudiantes.
    """
    try:
        # Verificar que el estudiante existe y el coordinador tiene acceso
        student = _resolve_student(student_uuid)
        if student is None:
            return api_not_found(STUDENT_NOT_FOUND_MESSAGE)
        student_id = student.id
        
        # El historial es información prohibida entre programas: aquí no hay
        # nivel reducido, o el estudiante está en tu alcance o no lo ves.
        #
        # Misma respuesta que el UUID irresoluble de arriba, a propósito. Con
        # un 404 para "no existe" y un 403 para "existe pero no es tuyo", el
        # par contesta la pregunta que no le corresponde: quien tiene un UUID
        # ajeno averigua si señala a alguien real. Aquí no cuesta nada
        # colapsarlos y es la regla que ya sigue el resto del módulo.
        if not scope_service.user_in_scope(current_user, student, allow_self=False):
            return api_not_found(STUDENT_NOT_FOUND_MESSAGE)


        # Parámetros de consulta
        q = parse_model(StudentHistoryQuery, request.args.to_dict())
        format_type = q.format
        limit = q.limit
        
        # Obtener el historial del estudiante
        history_entries = UserHistoryService.get_user_history(
            user_id=student_id,
            limit=limit,
            order_by='desc'
        )
        
        # Formatear las entradas si se solicita
        formatted_history = []
        formatter = HistoryFormatter()
        
        for entry in history_entries:
            entry_dict = entry.to_dict()
            
            # Agregar información del coordinador que realizó la acción
            if entry.performed_by_id:
                entry_dict['performed_by_name'] = f"{entry.performed_by.first_name} {entry.performed_by.last_name}"
                entry_dict['performed_by_role'] = entry.performed_by.role.name if entry.performed_by.role else None
            
            # Agregar descripción formateada si se solicita
            if format_type == 'formatted':
                entry_dict['formatted_description'] = formatter.format_history_entry(entry)
            
            formatted_history.append(entry_dict)
        
        return api_ok(
            {
                'student': {
                    'id': str(student.uuid) if student.uuid else None,
                    'name': f"{student.first_name} {student.last_name}",
                    'control_number': student.control_number,
                    'email': student.email
                },
                'history': formatted_history,
                'total_count': len(history_entries),
                'format_type': format_type
            },
            meta={
                'viewed_by': str(current_user.uuid) if current_user.uuid else None,
                'ordered_by': 'timestamp_desc',
                'limit_applied': limit
            },
        )
        
    except DomainError:
        raise  # validation errors are rendered by the app-level handler
    except Exception as e:
        return api_server_error(e, message='Error al obtener el historial del estudiante.',
                                context='coordinator.get_student_history')

def _check_ready_for_interview(admission_state):
    """Verifica si el estudiante está listo para entrevista"""
    # Lógica simplificada: si tiene >80% de progreso
    return admission_state.get("progress_pct", 0) >= 80