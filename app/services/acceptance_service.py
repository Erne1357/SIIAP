# app/services/acceptance_service.py
"""
Servicio para gestionar los documentos de aceptacion e inscripcion.

Flujo:
1. Coordinador acepta aspirante (deliberation_service.accept_applicant)
2. Coordinador sube carta de aceptacion y tira de materias
3. Aspirante descarga sus documentos
4. Aspirante sube boleta de servicios escolares
5. Coordinador revisa y aprueba/rechaza la boleta
6. Una vez aprobada, se puede proceder a la transicion a estudiante (Fase 5)
"""

from app import db
from app.models import UserProgram, User, Program
from app.models.acceptance_document import AcceptanceDocument
from app.services.notification_service import NotificationService
from app.services.user_history_service import UserHistoryService
from app.utils.files import save_user_doc
from app.utils.datetime_utils import now_local
from sqlalchemy import and_


VALID_DOC_TYPES = {'acceptance_letter', 'course_schedule', 'enrollment_receipt'}
COORDINATOR_DOC_TYPES = {'acceptance_letter', 'course_schedule'}
APPLICANT_DOC_TYPES = {'enrollment_receipt'}

DOC_TYPE_LABELS = {
    'acceptance_letter': 'Carta de Aceptacion',
    'course_schedule': 'Tira de Materias',
    'enrollment_receipt': 'Boleta de Servicios Escolares',
}


class AcceptanceError(Exception):
    """Error base para operaciones de aceptacion."""
    pass


class ApplicantNotFound(AcceptanceError):
    pass


class InvalidDocumentType(AcceptanceError):
    pass


class InvalidStateTransition(AcceptanceError):
    pass


def _get_user_program(user_id: int, program_id: int) -> UserProgram:
    up = UserProgram.query.filter_by(user_id=user_id, program_id=program_id).first()
    if not up:
        raise ApplicantNotFound(f"No se encontro al aspirante {user_id} en el programa {program_id}")
    return up


def _get_user_program_by_id(user_program_id: int) -> UserProgram:
    up = UserProgram.query.get(user_program_id)
    if not up:
        raise ApplicantNotFound(f"No se encontro UserProgram {user_program_id}")
    return up


def _get_or_create_doc(user_program_id: int, document_type: str) -> AcceptanceDocument:
    """Obtiene o crea un AcceptanceDocument para un user_program y tipo de documento."""
    doc = AcceptanceDocument.query.filter_by(
        user_program_id=user_program_id,
        document_type=document_type
    ).first()

    if not doc:
        doc = AcceptanceDocument(
            user_program_id=user_program_id,
            document_type=document_type,
            status='pending'
        )
        db.session.add(doc)

    return doc


def get_acceptance_status(user_program_id: int) -> dict:
    """
    Retorna el estado de los 3 documentos de aceptacion para un UserProgram.

    Returns:
        Dict con doc_type -> {doc_id, status, file_path, uploaded_at, review_notes}
    """
    up = _get_user_program_by_id(user_program_id)

    result = {}
    for doc_type in VALID_DOC_TYPES:
        doc = AcceptanceDocument.query.filter_by(
            user_program_id=user_program_id,
            document_type=doc_type
        ).first()

        if doc:
            result[doc_type] = doc.to_dict()
        else:
            result[doc_type] = {
                'id': None,
                'document_type': doc_type,
                'status': 'pending',
                'file_path': None,
                'uploaded_at': None,
                'review_notes': None,
            }

    return result


def get_accepted_applicants(program_id: int):
    """
    Obtiene todos los aspirantes aceptados de un programa con su estado de documentos.

    Returns:
        Lista de dicts con user, user_program y acceptance_docs
    """
    user_programs = UserProgram.query.join(
        User, UserProgram.user_id == User.id
    ).filter(
        and_(
            UserProgram.program_id == program_id,
            UserProgram.admission_status == 'accepted'
        )
    ).order_by(UserProgram.decision_at.desc()).all()

    result = []
    for up in user_programs:
        user = up.user
        docs = {}
        for doc_type in VALID_DOC_TYPES:
            doc = AcceptanceDocument.query.filter_by(
                user_program_id=up.id,
                document_type=doc_type
            ).first()
            docs[doc_type] = doc.to_dict() if doc else {
                'id': None, 'document_type': doc_type, 'status': 'pending',
                'file_path': None, 'uploaded_at': None, 'review_notes': None
            }

        result.append({
            'user_program': up.to_dict(include_deliberation=True),
            'user': {
                'id': user.id,
                'full_name': f"{user.first_name} {user.last_name} {user.mother_last_name or ''}".strip(),
                'email': user.email,
                'curp': user.curp,
            },
            'acceptance_docs': docs,
        })

    return result


def get_acceptance_stats(program_id: int) -> dict:
    """
    Estadisticas de documentos de aceptacion para un programa.

    Returns:
        Dict con conteos: pending_docs, receipt_submitted, completed
    """
    accepted = UserProgram.query.filter_by(
        program_id=program_id,
        admission_status='accepted'
    ).all()

    pending_docs = 0
    receipt_submitted = 0
    completed = 0

    for up in accepted:
        letter = AcceptanceDocument.query.filter_by(
            user_program_id=up.id, document_type='acceptance_letter'
        ).first()
        schedule = AcceptanceDocument.query.filter_by(
            user_program_id=up.id, document_type='course_schedule'
        ).first()
        receipt = AcceptanceDocument.query.filter_by(
            user_program_id=up.id, document_type='enrollment_receipt'
        ).first()

        letter_ok = letter and letter.status in ('uploaded', 'approved')
        schedule_ok = schedule and schedule.status in ('uploaded', 'approved')
        receipt_uploaded = receipt and receipt.status in ('uploaded',)
        receipt_approved = receipt and receipt.status == 'approved'

        if not letter_ok or not schedule_ok:
            pending_docs += 1
        elif receipt_uploaded:
            receipt_submitted += 1
        elif receipt_approved:
            completed += 1
        else:
            # Tiene carta y tira pero no ha subido boleta
            pending_docs += 1

    return {
        'total_accepted': len(accepted),
        'pending_docs': pending_docs,
        'receipt_submitted': receipt_submitted,
        'completed': completed,
    }


def upload_coordinator_doc(user_id: int, program_id: int, document_type: str,
                           file_storage, coordinator_id: int) -> AcceptanceDocument:
    """
    El coordinador sube un documento de aceptacion (carta o tira de materias) para el aspirante.

    Args:
        user_id: ID del aspirante
        program_id: ID del programa
        document_type: 'acceptance_letter' o 'course_schedule'
        file_storage: Objeto FileStorage de Flask
        coordinator_id: ID del coordinador que sube el documento

    Returns:
        AcceptanceDocument actualizado
    """
    if document_type not in COORDINATOR_DOC_TYPES:
        raise InvalidDocumentType(
            f"Tipo invalido para coordinador: {document_type}. "
            f"Use: {', '.join(COORDINATOR_DOC_TYPES)}"
        )

    up = _get_user_program(user_id, program_id)

    if up.admission_status != 'accepted':
        raise InvalidStateTransition(
            f"El aspirante debe estar en estado 'accepted', estado actual: '{up.admission_status}'"
        )

    # Guardar archivo
    doc_label = DOC_TYPE_LABELS[document_type].replace(' ', '_').lower()
    file_path = save_user_doc(file_storage, user_id, 'acceptance', doc_label)

    # Crear o actualizar el registro del documento
    doc = _get_or_create_doc(up.id, document_type)
    doc.file_path = file_path
    doc.uploaded_by_id = coordinator_id
    doc.uploaded_at = now_local()
    doc.status = 'uploaded'

    db.session.commit()

    # Notificar al aspirante cuando ambos documentos esten disponibles
    letter = AcceptanceDocument.query.filter_by(user_program_id=up.id, document_type='acceptance_letter').first()
    schedule = AcceptanceDocument.query.filter_by(user_program_id=up.id, document_type='course_schedule').first()

    if letter and letter.status == 'uploaded' and schedule and schedule.status == 'uploaded':
        program = Program.query.get(program_id)
        NotificationService.send(
            user_id=user_id,
            title='Tus documentos de aceptacion estan disponibles',
            message=f'Tu carta de aceptacion y tira de materias para {program.name} ya estan disponibles. '
                    f'Ingresa al portal y sube tu boleta de servicios escolares.'
        )
        UserHistoryService.log_action(
            user_id=user_id,
            admin_id=coordinator_id,
            action='acceptance_docs_uploaded',
            details=f'Carta de aceptacion y tira de materias subidas para {program.name}'
        )

    return doc


def submit_enrollment_receipt(user_id: int, program_id: int,
                               file_storage, aspirant_id: int) -> AcceptanceDocument:
    """
    El aspirante sube su boleta de servicios escolares.

    Args:
        user_id: ID del aspirante (debe coincidir con aspirant_id)
        program_id: ID del programa
        file_storage: Objeto FileStorage de Flask
        aspirant_id: ID del usuario que hace la peticion (debe ser el mismo aspirante)

    Returns:
        AcceptanceDocument actualizado
    """
    up = _get_user_program(user_id, program_id)

    if up.admission_status != 'accepted':
        raise InvalidStateTransition(
            f"Solo aspirantes aceptados pueden subir boleta, estado actual: '{up.admission_status}'"
        )

    # Verificar que el coordinador ya subio los documentos previos
    letter = AcceptanceDocument.query.filter_by(user_program_id=up.id, document_type='acceptance_letter').first()
    schedule = AcceptanceDocument.query.filter_by(user_program_id=up.id, document_type='course_schedule').first()

    if not (letter and letter.status == 'uploaded') or not (schedule and schedule.status == 'uploaded'):
        raise InvalidStateTransition(
            "El coordinador aun no ha subido la carta de aceptacion y tira de materias"
        )

    # Guardar archivo
    file_path = save_user_doc(file_storage, user_id, 'acceptance', 'boleta_servicios_escolares')

    doc = _get_or_create_doc(up.id, 'enrollment_receipt')

    # Si ya habia una boleta rechazada, permite resubir
    if doc.status not in ('pending', 'rejected'):
        raise InvalidStateTransition(
            f"Ya hay una boleta en estado '{doc.status}'. No se puede reemplazar."
        )

    doc.file_path = file_path
    doc.uploaded_by_id = aspirant_id
    doc.uploaded_at = now_local()
    doc.status = 'uploaded'
    doc.reviewed_by_id = None
    doc.reviewed_at = None
    doc.review_notes = None

    db.session.commit()

    # Notificar al coordinador
    program = Program.query.get(program_id)
    # (Notificacion al coordinador queda pendiente de implementar cuando haya sistema de notif por rol)

    UserHistoryService.log_action(
        user_id=user_id,
        admin_id=aspirant_id,
        action='enrollment_receipt_submitted',
        details=f'Boleta de servicios escolares subida para {program.name}'
    )

    return doc


def review_enrollment_receipt(doc_id: int, coordinator_id: int,
                               status: str, notes: str = None) -> AcceptanceDocument:
    """
    El coordinador revisa y aprueba o rechaza la boleta del aspirante.

    Args:
        doc_id: ID del AcceptanceDocument de tipo enrollment_receipt
        coordinator_id: ID del coordinador
        status: 'approved' o 'rejected'
        notes: Notas de revision (requerido si es rejected)

    Returns:
        AcceptanceDocument actualizado
    """
    if status not in ('approved', 'rejected'):
        raise ValueError("status debe ser 'approved' o 'rejected'")

    doc = AcceptanceDocument.query.get(doc_id)
    if not doc:
        raise ApplicantNotFound(f"Documento {doc_id} no encontrado")

    if doc.document_type != 'enrollment_receipt':
        raise InvalidDocumentType("Solo se puede revisar documentos de tipo enrollment_receipt")

    if doc.status != 'uploaded':
        raise InvalidStateTransition(
            f"Solo se pueden revisar documentos en estado 'uploaded', estado actual: '{doc.status}'"
        )

    doc.status = status
    doc.reviewed_by_id = coordinator_id
    doc.reviewed_at = now_local()
    doc.review_notes = notes

    up = doc.user_program
    user_id = up.user_id
    program = up.program

    db.session.commit()

    # Notificar al aspirante
    if status == 'approved':
        NotificationService.send(
            user_id=user_id,
            title='Boleta de inscripcion aprobada',
            message=f'Tu boleta de servicios escolares para {program.name} fue aprobada. '
                    f'Pronto recibiras instrucciones para completar tu inscripcion.'
        )
        UserHistoryService.log_action(
            user_id=user_id,
            admin_id=coordinator_id,
            action='enrollment_receipt_approved',
            details=f'Boleta aprobada para {program.name}. {notes or ""}'
        )
    else:
        NotificationService.send(
            user_id=user_id,
            title='Boleta de inscripcion rechazada',
            message=f'Tu boleta de servicios escolares para {program.name} fue rechazada. '
                    f'Motivo: {notes or "Sin especificar"}. Por favor vuelve a subirla.'
        )
        UserHistoryService.log_action(
            user_id=user_id,
            admin_id=coordinator_id,
            action='enrollment_receipt_rejected',
            details=f'Boleta rechazada para {program.name}. {notes or ""}'
        )

    return doc


def delete_coordinator_doc(doc_id: int, coordinator_id: int) -> None:
    """
    Elimina un documento de aceptacion subido por el coordinador (carta o tira).
    Util para reemplazar un documento incorrecto.
    """
    doc = AcceptanceDocument.query.get(doc_id)
    if not doc:
        raise ApplicantNotFound(f"Documento {doc_id} no encontrado")

    if doc.document_type not in COORDINATOR_DOC_TYPES:
        raise InvalidDocumentType("Solo se pueden eliminar carta de aceptacion o tira de materias")

    user_id = doc.user_program.user_id
    program = doc.user_program.program

    db.session.delete(doc)
    db.session.commit()

    UserHistoryService.log_action(
        user_id=user_id,
        admin_id=coordinator_id,
        action='acceptance_doc_deleted',
        details=f'{DOC_TYPE_LABELS[doc.document_type]} eliminado de {program.name}'
    )
