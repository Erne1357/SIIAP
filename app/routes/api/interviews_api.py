# app/routes/api/interviews_api.py
from app import db
from flask import Blueprint, current_app, request, jsonify
from flask_login import login_required, current_user
from sqlalchemy import select
from app.utils.auth import roles_required
from app.services.interview_service import InterviewEligibilityService

api_interviews = Blueprint('api_interviews', __name__, url_prefix='/api/v1/interviews')

@api_interviews.route('/eligibility/<int:student_id>/<int:program_id>', methods=['GET'])
@login_required
@roles_required('program_admin', 'postgraduate_admin')
def check_eligibility(student_id: int, program_id: int):
    """
    Verifica si un estudiante específico es elegible para entrevista.
    """
    try:
        eligibility = InterviewEligibilityService.check_student_eligibility(student_id, program_id)
        return jsonify({
            "ok": True,
            "student_id": student_id,
            "program_id": program_id,
            "eligibility": eligibility
        }), 200
    except Exception as e:
        return jsonify({
            "ok": False,
            "error": str(e)
        }), 500

@api_interviews.route('/eligible-students/<int:program_id>', methods=['GET'])
@login_required
@roles_required('program_admin', 'postgraduate_admin')
def list_eligible_students(program_id: int):
    """
    Lista todos los estudiantes elegibles para entrevista en un programa.
    """
    # Verificar permisos del coordinador
    if current_user.role.name == 'program_admin':
        from app.models.program import Program
        program = db.session.get(Program, program_id)
        if not program or program.coordinator_id != current_user.id:
            return jsonify({
                "ok": False,
                "error": "No tienes permiso para gestionar este programa"
            }), 403

    try:
        eligible_students = InterviewEligibilityService.get_eligible_students(program_id)
        current_app.logger.info(f"Usuario {current_user.id} listó estudiantes elegibles para programa {program_id} - Total: {len(eligible_students)} estudiantes elegibles encontrados {eligible_students}")
        return jsonify({
            "ok": True,
            "program_id": program_id,
            "eligible_students": eligible_students,
            "count": len(eligible_students)
        }), 200
    except Exception as e:
        return jsonify({
            "ok": False,
            "error": str(e)
        }), 500

@api_interviews.route('/eligible-students', methods=['GET'])
@login_required
@roles_required('program_admin', 'postgraduate_admin')
def list_all_eligible_students():
    """
    Lista todos los estudiantes elegibles para entrevista en todos los programas.
    Si es coordinador (program_admin), solo muestra sus programas.
    Si es admin de posgrado (postgraduate_admin), muestra todos los programas.
    """
    try:
        from app.models.program import Program
        
        # Determinar qué programas puede ver el usuario
        if current_user.role.name == 'program_admin':
            # Coordinador: solo sus programas
            managed_programs = db.session.execute(
                select(Program).where(Program.coordinator_id == current_user.id)
            ).scalars().all()
            
            if not managed_programs:
                return jsonify({
                    "ok": True,
                    "programs": [],
                    "total_eligible_students": 0,
                    "message": "No tienes programas asignados"
                }), 200
                
        else:
            # Admin de posgrado: todos los programas
            managed_programs = db.session.execute(
                select(Program)
            ).scalars().all()

        # Obtener estudiantes elegibles por programa
        programs_data = []
        total_eligible = 0
        
        for program in managed_programs:
            eligible_students = InterviewEligibilityService.get_eligible_students(program.id)
            
            programs_data.append({
                "program_id": program.id,
                "program_name": program.name,
                "program_slug": program.slug,
                "eligible_students": eligible_students,
                "eligible_count": len(eligible_students)
            })
            
            total_eligible += len(eligible_students)

        current_app.logger.info(f"Usuario {current_user.id} listó estudiantes elegibles de todos sus programas - Total: {total_eligible} estudiantes elegibles")
        
        return jsonify({
            "ok": True,
            "programs": programs_data,
            "total_programs": len(managed_programs),
            "total_eligible_students": total_eligible,
            "user_role": current_user.role.name
        }), 200
        
    except Exception as e:
        current_app.logger.error(f"Error obteniendo estudiantes elegibles para todos los programas: {str(e)}")
        return jsonify({
            "ok": False,
            "error": str(e)
        }), 500

@api_interviews.route('/mark-profile-complete/<int:user_id>', methods=['POST'])
@login_required
@roles_required('program_admin', 'postgraduate_admin')
def mark_profile_complete(user_id: int):
    """
    Marca el perfil de un usuario como completo (uso administrativo).
    """
    try:
        success = InterviewEligibilityService.mark_profile_complete(user_id)
        if success:
            return jsonify({
                "ok": True,
                "message": "Perfil marcado como completo"
            }), 200
        else:
            return jsonify({
                "ok": False,
                "error": "No se pudo completar el perfil - faltan campos requeridos"
            }), 400
    except Exception as e:
        return jsonify({
            "ok": False,
            "error": str(e)
        }), 500