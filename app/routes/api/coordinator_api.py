# app/routes/api/coordinator_api.py
from flask import Blueprint, request, jsonify, current_app
from flask_login import login_required, current_user
from sqlalchemy import select, and_, or_, func
from datetime import datetime, timezone

from app import db
from app.utils.permissions import permission_required, any_permission_required
from app.utils.files import save_user_doc  # Importar tu función de archivos
from app.services.user_history_service import UserHistoryService
from app.utils.history_formatter import HistoryFormatter
from app.models.user import User
from app.models.role import Role
from app.models.program import Program
from app.models.user_program import UserProgram
from app.models.submission import Submission
from app.models.archive import Archive
from app.models.step import Step
from app.models.phase import Phase
from app.models.program_step import ProgramStep
from app.models.appointment import Appointment
from app.models.semester_enrollment import SemesterEnrollment
from app.models.academic_period import AcademicPeriod
from app.services.admission_service import get_admission_state

api_coordinator = Blueprint('api_coordinator', __name__, url_prefix='/api/v1/coordinator')

@api_coordinator.route('/students', methods=['GET'])
@login_required
@permission_required('coordinator.api.list_students')
def list_students():
    """
    Lista estudiantes que el coordinador puede ver/gestionar.
    Filtros: program_id, phase, status, search, show_other
    """
    program_id = request.args.get('program_id', type=int)
    phase = request.args.get('phase')  # admission, permanence, conclusion
    status = request.args.get('status')  # pending, review, approved, rejected
    search = request.args.get('search', '').strip()
    show_other = request.args.get('show_other') == 'true'
    
    # Base query: usuarios con programas (aspirantes y estudiantes ya inscritos)
    query = db.session.query(User, UserProgram, Program).join(
        UserProgram, User.id == UserProgram.user_id
    ).join(
        Program, UserProgram.program_id == Program.id
    ).filter(
        User.role.has(name='applicant') | User.role.has(name='student')
    )
    
    # Programas que puede gestionar el coordinador (propios + delegados)
    accessible_pids = current_user.get_accessible_program_ids()
    managed_programs = list(accessible_pids) if accessible_pids is not None else None

    if managed_programs is not None:
        if not show_other:
            if not managed_programs:
                return jsonify({"students": []}), 200
            query = query.filter(Program.id.in_(managed_programs))
    
    # Filtros adicionales
    if program_id:
        query = query.filter(Program.id == program_id)
    
    if search:
        search_term = f"%{search}%"
        query = query.filter(
            or_(
                User.first_name.ilike(search_term),
                User.last_name.ilike(search_term),
                User.email.ilike(search_term)
            )
        )
    
    results = query.all()
    students = []

    active_period = AcademicPeriod.get_active_period()
    active_period_id = active_period.id if active_period else None

    for user, user_program, program in results:
        # Calcular estado actual del estudiante
        admission_state = get_admission_state(user.id, program.id, user_program)
        # Métricas de permanencia basadas en SemesterEnrollment + duración del programa
        perm = _compute_permanence_metrics(user_program, program, active_period_id)
        # Determinar fase actual basada en estado
        current_phase = _determine_current_phase(admission_state, user_program, perm)
        
        # Filtro por fase
        if phase and current_phase != phase:
            continue
        
        # Puede gestionar este estudiante?
        # managed_programs None = acceso global (jefe de posgrado)
        if managed_programs is None:
            can_manage = True
        else:
            can_manage = program.id in managed_programs
        
        # Calcular métricas
        student_data = {
            "id": user.id,
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
            # Métricas de conclusión (placeholder)
            "conclusion_stage": "inicial",
            "conclusion_progress": 0,
            "conclusion_status": "pending"
        }
        
        # Filtro por status
        if status and student_data["overall_status"] != status:
            continue
            
        students.append(student_data)
    
    return jsonify({"students": students}), 200

@api_coordinator.route('/manageable-students', methods=['GET'])
@login_required
@permission_required('coordinator.api.list_students')
def manageable_students():
    """
    Lista solo estudiantes que el coordinador puede gestionar (para selects)
    """
    accessible_pids = current_user.get_accessible_program_ids()
    if accessible_pids is None:
        program_filter = True  # acceso global
    else:
        if not accessible_pids:
            return jsonify({"students": []}), 200
        program_filter = Program.id.in_(accessible_pids)
    
    query = db.session.query(User, Program).join(
        UserProgram, User.id == UserProgram.user_id
    ).join(
        Program, UserProgram.program_id == Program.id
    ).filter(
        (User.role.has(name='applicant') | User.role.has(name='student')),
        program_filter
    ).order_by(User.first_name, User.last_name)
    
    results = query.all()
    students = []
    
    for user, program in results:
        students.append({
            "id": user.id,
            "full_name": f"{user.first_name} {user.last_name}",
            "email": user.email,
            "program_name": program.name
        })
    
    return jsonify({"students": students}), 200

@api_coordinator.route('/student/<int:student_id>/uploadable-archives', methods=['GET'])
@login_required
@permission_required('coordinator.api.upload_for_student')
def student_uploadable_archives(student_id: int):
    """
    Lista archivos que el coordinador puede subir para un estudiante específico
    """
    # Verificar que puede gestionar este estudiante
    student = db.session.get(User, student_id)
    if not student:
        return jsonify({"error": "Estudiante no encontrado"}), 404
    
    user_program = UserProgram.query.filter_by(user_id=student_id).first()
    if not user_program:
        return jsonify({"error": "Estudiante no inscrito en programa"}), 404
    
    # Verificar permisos
    accessible_pids = current_user.get_accessible_program_ids()
    if accessible_pids is not None and user_program.program_id not in accessible_pids:
        return jsonify({"error": "No tienes permiso para gestionar este estudiante"}), 403

    # Obtener archivos que permiten subida por coordinador
    query = db.session.query(Archive, Step, Phase).join(
        Step, Archive.step_id == Step.id
    ).join(
        Phase, Step.phase_id == Phase.id
    ).join(
        ProgramStep, and_(
            ProgramStep.step_id == Step.id,
            ProgramStep.program_id == user_program.program_id
        )
    ).filter(
        Archive.allow_coordinator_upload == True,
        Archive.is_uploadable == True
    ).order_by(Phase.id, ProgramStep.sequence)
    
    archives = []
    for archive, step, phase in query:
        # Verificar si ya existe submission
        existing = Submission.query.filter_by(
            user_id=student_id,
            archive_id=archive.id
        ).first()
        
        archives.append({
            "id": archive.id,
            "name": archive.name,
            "description": archive.description,
            "step_name": step.name,
            "phase_name": phase.name,
            "has_existing": bool(existing),
            "existing_status": existing.status if existing else None
        })
    
    return jsonify({"archives": archives}), 200

@api_coordinator.route('/upload-for-student', methods=['POST'])
@login_required
@permission_required('coordinator.api.upload_for_student')
def upload_for_student():
    """
    Permite al coordinador subir un archivo por un estudiante usando el sistema de archivos
    """
    student_id = request.form.get('student_id', type=int)
    archive_id = request.form.get('archive_id', type=int)
    notes = request.form.get('notes', '').strip()
    
    if not student_id or not archive_id:
        return jsonify({"error": "student_id y archive_id son requeridos"}), 400
    
    if 'file' not in request.files:
        return jsonify({"error": "No se proporcionó archivo"}), 400
    
    file = request.files['file']
    if not file.filename:
        return jsonify({"error": "Archivo inválido"}), 400
    
    # Verificar permisos sobre el estudiante
    user_program = UserProgram.query.filter_by(user_id=student_id).first()
    if not user_program:
        return jsonify({"error": "Estudiante no inscrito"}), 404
    
    accessible_pids = current_user.get_accessible_program_ids()
    if accessible_pids is not None and user_program.program_id not in accessible_pids:
        return jsonify({"error": "No tienes permiso para este estudiante"}), 403

    # Verificar que el archivo permite subida por coordinador
    archive = db.session.get(Archive, archive_id)
    if not archive or not archive.allow_coordinator_upload:
        return jsonify({"error": "Este archivo no permite subida por coordinador"}), 403
    
    try:
        # USAR TU FUNCIÓN DE ARCHIVOS PARA GUARDAR
        # Esto creará un nombre consistente y manejará las validaciones
        file_relative_path = save_user_doc(
            file_storage=file,
            user_id=student_id,
            phase='admission',  # Por ahora todo es admisión
            name=archive.name  # Usar el nombre del archivo como base
        )
        
        # Buscar ProgramStep
        program_step = ProgramStep.query.filter_by(
            program_id=user_program.program_id,
            step_id=archive.step_id
        ).first()
        
        if not program_step:
            return jsonify({"error": "Configuración de programa incompleta"}), 400
        
        # Eliminar submission anterior si existe (tu función ya reemplaza el archivo)
        existing = Submission.query.filter_by(
            user_id=student_id,
            archive_id=archive_id
        ).first()
        
        if existing:
            db.session.delete(existing)
        
        # Crear nueva submission
        submission = Submission(
            file_path=file_relative_path,
            status='approved',  # Coordinador aprueba directamente
            review_date=datetime.now(),
            reviewer_comment="[Coordinador] Documento subido y aprobado",
            user_id=student_id,
            archive_id=archive_id,
            program_step_id=program_step.id,
            semester=None,
            uploaded_by=current_user.id,
            uploaded_by_role='program_admin'
        )
        
        if notes:
            submission.reviewer_comment = f"[Coordinador] {notes}"
        
        db.session.add(submission)
        db.session.commit()
        
        # Registrar en el historial
        try:
            UserHistoryService.log_document_upload(
                user_id=student_id,
                archive_name=archive.name,
                program_name=user_program.program.name,
                uploaded_by_admin=True,
                admin_id=current_user.id
            )
            db.session.commit()
        except Exception as e:
            current_app.logger.error(f"Error al registrar subida por coordinador en historial: {e}")
        
        return jsonify({
            "ok": True, 
            "submission_id": submission.id,
            "message": "Documento subido correctamente por coordinador"
        }), 201
        
    except Exception as e:
        db.session.rollback()
        # Tu función save_user_doc ya maneja la limpieza de archivos en caso de error
        return jsonify({"error": f"Error al guardar: {str(e)}"}), 500


@api_coordinator.route('/programs', methods=['GET'])
@login_required
@permission_required('coordinator.api.list_students')
def list_coordinator_programs():
    """Lista programas que el coordinador puede gestionar"""
    accessible_pids = current_user.get_accessible_program_ids()
    if accessible_pids is None:
        programs = Program.query.all()
    elif not accessible_pids:
        programs = []
    else:
        programs = Program.query.filter(Program.id.in_(accessible_pids)).all()
    
    items = [{
        "id": p.id,
        "name": p.name,
        "slug": p.slug,
        "description": p.description
    } for p in programs]
    
    return jsonify({"ok": True, "programs": items}), 200

@api_coordinator.route('/student/<int:student_id>/permanence-details', methods=['GET'])
@login_required
@permission_required('coordinator.api.list_students')
def get_student_permanence_details(student_id: int):
    """
    Detalles de permanencia de un estudiante inscrito:
    semestre actual, periodo activo, confirmación semestral,
    beca CONACyT, documentos de admisión pendientes e historial semestral.
    """
    from app.models.semester_enrollment import SemesterEnrollment
    from app.models.academic_period import AcademicPeriod

    student = db.session.get(User, student_id)
    if not student:
        return jsonify({"ok": False, "error": "Estudiante no encontrado"}), 404

    user_program = UserProgram.query.filter_by(user_id=student_id).first()
    if not user_program:
        return jsonify({"ok": False, "error": "Sin programa"}), 404

    program = db.session.get(Program, user_program.program_id)

    accessible_pids = current_user.get_accessible_program_ids()
    can_manage = accessible_pids is None or program.id in accessible_pids

    # Periodo activo y enrollment del periodo actual
    active_period = AcademicPeriod.get_active_period()
    current_enrollment = None
    if active_period:
        current_enrollment = SemesterEnrollment.query.filter_by(
            user_program_id=user_program.id,
            academic_period_id=active_period.id
        ).first()

    # Historial semestral (todos los periodos)
    history = SemesterEnrollment.query.filter_by(
        user_program_id=user_program.id
    ).order_by(SemesterEnrollment.semester_number.asc()).all()

    # Documentos de admisión pendientes/rechazados
    admission_state = get_admission_state(student_id, program.id, user_program)
    pending_admission = (
        admission_state['status_count'].get('pending', 0) +
        admission_state['status_count'].get('rejected', 0)
    )

    return jsonify({
        "ok": True,
        "student": {
            "id": student.id,
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
    }), 200


@api_coordinator.route('/student/<int:student_id>/details', methods=['GET'])
@login_required
@permission_required('coordinator.api.list_students')
def get_student_details(student_id: int):
    """
    Obtiene detalles completos de un estudiante para el modal del coordinador.
    Incluye: perfil, documentos, entrevista, métricas
    """
    from app.models.event import Event, EventSlot, EventWindow
    from app.services.interview_service import InterviewEligibilityService
    
    # 1. Obtener estudiante
    student = db.session.get(User, student_id)
    if not student:
        return jsonify({"ok": False, "error": "Estudiante no encontrado"}), 404
    
    # 2. Verificar permisos
    user_program = UserProgram.query.filter_by(user_id=student_id).first()
    if not user_program:
        return jsonify({"ok": False, "error": "Estudiante no inscrito"}), 404
    
    program = db.session.get(Program, user_program.program_id)
    
    # Determinar si el coordinador puede gestionar este estudiante
    accessible_pids = current_user.get_accessible_program_ids()
    can_manage = accessible_pids is None or program.id in accessible_pids

    # 3. Obtener estado de admisión completo
    admission_state = get_admission_state(student_id, program.id, user_program)
    
    # 4. Organizar documentos por paso
    documents_by_step = []
    for item in admission_state['processed_steps']:
        if item['sequence'] == 0:
            continue
        if item['is_combined']:
            # Paso combinado
            step_data = {
                "step_id": item['id'],
                "step_name": item['name'],
                "sequence": item['sequence'],
                "is_combined": True,
                "locked": item['locked'],
                "state": item['state'],
                "archives": []
            }
            
            # Archivos del step1
            for arch in item['step1'].archives:
                step_data['archives'].append(_format_archive_status(
                    arch, 
                    admission_state['subs'], 
                    admission_state['all_extensions']
                ))
            
            # Archivos del step2
            for arch in item['step2'].archives:
                step_data['archives'].append(_format_archive_status(
                    arch, 
                    admission_state['subs'], 
                    admission_state['all_extensions']
                ))
            
            documents_by_step.append(step_data)
        else:
            # Paso normal
            step = item['step']
            step_data = {
                "step_id": step.id,
                "step_name": step.name,
                "sequence": item['sequence'],
                "is_combined": False,
                "locked": item['locked'],
                "state": item['state'],
                "archives": []
            }
            
            for arch in step.archives:
                step_data['archives'].append(_format_archive_status(
                    arch, 
                    admission_state['subs'], 
                    admission_state['all_extensions']
                ))
            
            documents_by_step.append(step_data)
    
    # 5. Estado de entrevista
    interview_status = _get_interview_status(student_id, program.id)
    
    # 6. Verificar elegibilidad
    eligibility = InterviewEligibilityService.check_student_eligibility(student_id, program.id)
    
    # 7. Construir respuesta
    return jsonify({
        "ok": True,
        "student": {
            "id": student.id,
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
        "documents": documents_by_step,
        "interview": {
            **interview_status,
            "eligibility": eligibility
        },
        "metrics": {
            "total_documents": len([a for step in documents_by_step for a in step['archives']]),
            "approved": admission_state['status_count'].get('approved', 0),
            "pending": admission_state['status_count'].get('pending', 0),
            "rejected": admission_state['status_count'].get('rejected', 0),
            "extended": admission_state['status_count'].get('extended', 0),
            "in_review": admission_state['status_count'].get('review', 0),
            "progress_percentage": admission_state['progress_pct']
        },
        "missing_documents": _get_missing_documents(documents_by_step),
        "can_manage": can_manage
    }), 200

def _format_archive_status(archive, subs, all_extensions):
    """Formatea el estado de un archivo para el modal"""
    sub = subs.get(archive.id)
    ext = all_extensions.get(archive.id)
    
    return {
        "id": archive.id,
        "name": archive.name,
        "description": archive.description,
        "has_submission": bool(sub),
        "status": sub.status if sub else "pending",
        "uploaded_at": sub.upload_date.isoformat() if sub and sub.upload_date else None,
        "uploaded_by_role": sub.uploaded_by_role if sub else None,
        "reviewer_comment": sub.reviewer_comment if sub else None,
        "review_date": sub.review_date.isoformat() if sub and sub.review_date else None,
        "file_url": f"/files/doc/{sub.user_id}/admission/{sub.file_path.split('/')[-1]}" if sub else None,
        "has_extension": bool(ext),
        "extension_status": ext.status if ext else None,
        "extension_until": ext.granted_until.isoformat() if ext and ext.granted_until else None,
        "is_uploadable": archive.is_uploadable,
        "allow_coordinator_upload": archive.allow_coordinator_upload
    }

def _get_interview_status(student_id, program_id):
    """Obtiene el estado de entrevista del estudiante"""
    from app.models.event import Event, EventSlot, EventWindow

    # Buscar cualquier cita no cancelada: scheduled (pendiente), done (realizada), no_show
    appointment = db.session.execute(
        select(Appointment)
        .join(EventSlot, Appointment.slot_id == EventSlot.id)
        .join(EventWindow, EventSlot.event_window_id == EventWindow.id)
        .join(Event, EventWindow.event_id == Event.id)
        .where(
            Appointment.applicant_id == student_id,
            Appointment.status.in_(['scheduled', 'done', 'no_show']),
            or_(Event.program_id == program_id, Event.program_id.is_(None)),
            Event.type == 'interview'
        )
    ).scalar_one_or_none()

    if not appointment:
        return {
            "has_interview": False,
            "appointment": None
        }
    
    # Obtener detalles completos
    slot = db.session.get(EventSlot, appointment.slot_id)
    window = db.session.get(EventWindow, slot.event_window_id)
    event = db.session.get(Event, window.event_id)
    
    return {
        "has_interview": True,
        "appointment": {
            "id": appointment.id,
            "status": appointment.status,
            "notes": appointment.notes,
            "created_at": appointment.created_at.isoformat(),
            "event": {
                "id": event.id,
                "title": event.title,
                "location": event.location,
                "description": event.description
            },
            "slot": {
                "starts_at": slot.starts_at.isoformat(),
                "ends_at": slot.ends_at.isoformat()
            }
        }
    }

def _get_missing_documents(documents_by_step):
    """Lista de documentos faltantes o rechazados"""
    missing = []
    for step in documents_by_step:
        for arch in step['archives']:
            if arch['status'] in ['pending', 'rejected']:
                missing.append({
                    "step": step['step_name'],
                    "archive": arch['name'],
                    "status": arch['status']
                })
    return missing
# ==================== FUNCIONES AUXILIARES ====================

def _compute_permanence_metrics(user_program, program, active_period_id):
    """
    Calcula métricas reales de permanencia para un UserProgram.

    Returns dict con:
      - current_semester: número de semestre actual del UserProgram
      - completed_semesters: cantidad de SemesterEnrollment con status='completed'
      - total_semesters: duración del programa (Program.duration_semesters; default 4)
      - academic_progress: % de semestres completados sobre el total
      - in_progress_segment: % adicional que corresponde al semestre en curso
        (sólo cuando hay enrollment en estado 'active' en el periodo activo)
      - academic_status: estado funcional para el coordinador
        ('active' | 'on_leave' | 'completed' | 'dropped' | 'pending')
    """
    total = max(int(program.duration_semesters or 4), 1)
    current_semester = user_program.current_semester or 1

    completed = (
        SemesterEnrollment.query
        .filter_by(user_program_id=user_program.id, status='completed')
        .count()
    )
    completed = min(completed, total)

    # Enrollment del periodo activo (si existe) define el estado funcional + segmento parpadeante
    current_enrollment = None
    if active_period_id is not None:
        current_enrollment = (
            SemesterEnrollment.query
            .filter_by(user_program_id=user_program.id, academic_period_id=active_period_id)
            .first()
        )

    if current_enrollment is not None:
        academic_status = current_enrollment.status
    elif completed >= total:
        academic_status = 'completed'
    else:
        academic_status = 'pending'

    progress_pct = round((completed / total) * 100, 2)
    segment_pct = round((1 / total) * 100, 2)

    # Sólo parpadea si hay un semestre activamente en curso y queda espacio en la barra
    in_progress_segment = 0
    if academic_status == 'active' and (progress_pct + segment_pct) <= 100.001:
        in_progress_segment = segment_pct

    return {
        "current_semester": current_semester,
        "completed_semesters": completed,
        "total_semesters": total,
        "academic_progress": progress_pct,
        "in_progress_segment": in_progress_segment,
        "academic_status": academic_status,
    }


def _determine_current_phase(admission_state, user_program, perm):
    """Determina la fase actual del estudiante."""
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


@api_coordinator.route('/students/<int:student_id>/history', methods=['GET'])
@login_required
@permission_required('coordinator.api.list_students')
def get_student_history(student_id):
    """
    Obtiene el historial formateado de un estudiante específico.
    Solo coordinadores y administradores pueden ver el historial de estudiantes.
    """
    try:
        # Verificar que el estudiante existe y el coordinador tiene acceso
        student = User.query.filter_by(id=student_id).first()
        if not student or student.role.name not in ('applicant', 'student'):
            return jsonify({
                'success': False,
                'message': 'Estudiante no encontrado'
            }), 404
        
        # Verificar permisos: programas accesibles del coordinador (propios + delegados)
        accessible_pids = current_user.get_accessible_program_ids()
        if accessible_pids is not None:
            user_programs = UserProgram.query.filter_by(user_id=student_id).all()
            if not any(up.program_id in accessible_pids for up in user_programs):
                return jsonify({
                    'success': False,
                    'message': 'No tienes permisos para ver el historial de este estudiante'
                }), 403
        
        # Parámetros de consulta
        format_type = request.args.get('format', 'formatted')
        limit = min(int(request.args.get('limit', 50)), 100)
        
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
        
        return jsonify({
            'success': True,
            'data': {
                'student': {
                    'id': student.id,
                    'name': f"{student.first_name} {student.last_name}",
                    'control_number': student.control_number,
                    'email': student.email
                },
                'history': formatted_history,
                'total_count': len(history_entries),
                'format_type': format_type
            },
            'meta': {
                'viewed_by': current_user.id,
                'ordered_by': 'timestamp_desc',
                'limit_applied': limit
            }
        }), 200
        
    except Exception as e:
        return jsonify({
            'success': False,
            'message': f'Error al obtener historial del estudiante: {str(e)}'
        }), 500

def _check_ready_for_interview(admission_state):
    """Verifica si el estudiante está listo para entrevista"""
    # Lógica simplificada: si tiene >80% de progreso
    return admission_state.get("progress_pct", 0) >= 80