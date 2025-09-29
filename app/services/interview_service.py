# app/services/interview_service.py
from sqlalchemy import select, and_
from flask import current_app
from app import db
from app.models.user import User
from app.models.program_step import ProgramStep
from app.models.step import Step
from app.models.phase import Phase
from app.models.submission import Submission
from app.models.archive import Archive
from app.models.user_program import UserProgram
from typing import Dict, List, Tuple
import logging

class InterviewEligibilityService:
    
    @staticmethod
    def check_student_eligibility(student_id: int, program_id: int) -> Dict:
        """
        Verifica si un estudiante es elegible para entrevista.
        
        Criterios:
        1. Perfil completo
        2. Todos los archivos de pasos anteriores en estado 'approved' o 'extension'
        3. Solo considerar pasos de la fase de admisión
        4. No incluir el último paso (entrevista)
        
        Returns:
            Dict con 'eligible', 'reason', 'missing_items', 'profile_status', 'documents_status'
        """
        user = db.session.get(User, student_id)
        if not user:
            return {"eligible": False, "reason": "Estudiante no encontrado"}
        
        # 1. Verificar perfil completo (ahora usa el método del modelo)
        profile_complete = user.profile_completed
        
        # 2. Obtener todos los pasos del programa que pertenezcan a la fase de admisión
        program_steps = db.session.execute(
            select(ProgramStep, Step).join(
                Step, ProgramStep.step_id == Step.id
            ).join(
                Phase, Step.phase_id == Phase.id
            ).where(
                and_(
                    ProgramStep.program_id == program_id,
                    Phase.name == 'admission'
                )
            ).order_by(ProgramStep.sequence)
        ).all()
        
        current_app.logger.warning(f"Program steps for program_id {program_id}: {program_steps}")

        if not program_steps:
            return {"eligible": False, "reason": "Programa sin pasos configurados"}
        
        # Excluir el último paso (presumiblemente la entrevista)
        steps_to_check = program_steps[1:-1] if len(program_steps) > 1 else []
        
        # 3. Verificar estado de documentos en cada paso
        missing_items = []
        documents_status = []
        
        for program_step, step in steps_to_check:
            # Obtener archivos requeridos para este paso
            archives = db.session.execute(
                select(Archive).where(
                    Archive.step_id == step.id,
                    Archive.is_uploadable == True
                )
            ).scalars().all()
            
            step_status = {
                "step_name": step.name,
                "step_id": step.id,
                "sequence": program_step.sequence,
                "archives": []
            }
            
            for archive in archives:
                # Buscar submission del estudiante para este archivo
                submission = db.session.execute(
                    select(Submission).where(
                        and_(
                            Submission.user_id == student_id,
                            Submission.archive_id == archive.id
                        )
                    )
                ).scalar_one_or_none()
                
                archive_status = {
                    "archive_name": archive.name,
                    "archive_id": archive.id,
                    "has_submission": bool(submission),
                    "status": submission.status if submission else "missing",
                    "is_valid": False
                }
                
                # Determinar si el archivo está en estado válido
                if submission and submission.status in ['approved', 'extension']:
                    archive_status["is_valid"] = True
                else:
                    missing_items.append({
                        "type": "document",
                        "step": step.name,
                        "archive": archive.name,
                        "current_status": submission.status if submission else "missing"
                    })
                
                step_status["archives"].append(archive_status)
            
            documents_status.append(step_status)
        
        # 4. Verificar si faltan elementos
        if not profile_complete:
            missing_items.append({
                "type": "profile",
                "description": "Perfil de usuario incompleto"
            })
        
        # 5. Determinar elegibilidad
        eligible = len(missing_items) == 0
        
        return {
            "eligible": eligible,
            "reason": "Cumple todos los requisitos" if eligible else "Faltan requisitos",
            "missing_items": missing_items,
            "profile_status": {
                "complete": profile_complete,
                "required": True
            },
            "documents_status": documents_status,
            "total_steps_checked": len(steps_to_check),
            "last_step_excluded": program_steps[-1][1].name if program_steps else None
        }
    
    @staticmethod
    def get_eligible_students(program_id: int) -> List[Dict]:
        """
        Obtiene todos los estudiantes elegibles para entrevista en un programa.
        """
        # Obtener todos los estudiantes del programa
        user_programs = db.session.execute(
            select(UserProgram, User).join(
                User, UserProgram.user_id == User.id
            ).where(
                UserProgram.program_id == program_id,
                User.role.has(name='applicant')
            )
        ).all()
        
        eligible_students = []
        
        for user_program, user in user_programs:
            eligibility = InterviewEligibilityService.check_student_eligibility(
                user.id, program_id
            )
            
            if eligibility["eligible"]:
                eligible_students.append({
                    "id": user.id,
                    "full_name": f"{user.first_name} {user.last_name}",
                    "email": user.email,
                    "eligibility": eligibility
                })
        
        return eligible_students
    
    @staticmethod
    def mark_profile_complete(user_id: int) -> bool:
        """
        Marca el perfil de un usuario como completo.
        Esta función se puede llamar desde la API de perfil cuando se completen todos los campos.
        """
        user = db.session.get(User, user_id)
        if not user:
            return False
        
        # Verificar que tenga los campos mínimos requeridos
        required_fields = [
            user.first_name, 
            user.last_name, 
            user.email
        ]
        
        if all(field and str(field).strip() for field in required_fields):
            user.profile_completed = True
            db.session.commit()
            return True
        
        return False