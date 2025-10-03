# app/services/program_transfer_service.py
from datetime import datetime, timezone
from typing import Dict, List, Tuple
from app import db
from app.models.user_program import UserProgram
from app.models.submission import Submission
from app.models.archive import Archive
from app.models.program_step import ProgramStep
from app.models.step import Step
from app.models.appointment import Appointment
from app.models.event import Event, EventSlot, EventWindow
from sqlalchemy import select
import os
from flask import current_app

class ProgramTransferService:
    
    @staticmethod
    def analyze_transfer(user_id: int, from_program_id: int, to_program_id: int) -> Dict:
        """
        Analiza qué documentos se pueden reutilizar, cuáles se perderán,
        y si hay entrevista que cancelar.
        
        Returns:
            {
                'can_transfer': bool,
                'reusable_docs': [{'archive_id', 'name', 'from_step', 'to_step'}],
                'incompatible_docs': [{'archive_id', 'name', 'file_path'}],
                'missing_docs': [{'archive_id', 'name', 'step_name'}],
                'interview_status': {'has_interview': bool, 'will_cancel': bool, 'reason': str}
            }
        """
        # 1. Obtener submissions actuales del usuario en programa origen
        current_submissions = db.session.execute(
            select(Submission)
            .join(ProgramStep, Submission.program_step_id == ProgramStep.id)
            .where(
                Submission.user_id == user_id,
                ProgramStep.program_id == from_program_id
            )
        ).scalars().all()
        
        # 2. Indexar por archive_id
        current_subs_by_archive = {sub.archive_id: sub for sub in current_submissions}
        
        # 3. Mapear archivos entre programas
        mapping = ProgramTransferService._create_archive_mapping(
            from_program_id, 
            to_program_id
        )
        
        # 4. Clasificar documentos
        reusable = []
        incompatible = []
        
        for from_archive_id, to_archive_id in mapping['equivalent'].items():
            if from_archive_id in current_subs_by_archive:
                sub = current_subs_by_archive[from_archive_id]
                from_arch = db.session.get(Archive, from_archive_id)
                to_arch = db.session.get(Archive, to_archive_id)
                
                reusable.append({
                    'archive_id': from_archive_id,
                    'target_archive_id': to_archive_id,
                    'name': from_arch.name,
                    'from_step': from_arch.step.name,
                    'to_step': to_arch.step.name,
                    'status': sub.status,
                    'is_same_file': from_archive_id == to_archive_id
                })
        
        # Documentos que se perderán
        for archive_id, sub in current_subs_by_archive.items():
            if archive_id not in mapping['equivalent']:
                arch = db.session.get(Archive, archive_id)
                incompatible.append({
                    'archive_id': archive_id,
                    'name': arch.name,
                    'file_path': sub.file_path,
                    'step_name': arch.step.name
                })
        
        # 5. Documentos faltantes en nuevo programa
        to_program_archives = ProgramTransferService._get_program_archives(to_program_id)
        missing = []
        
        for arch in to_program_archives:
            if arch.id not in mapping['equivalent'].values():
                # Este archivo no tiene equivalente en origen
                missing.append({
                    'archive_id': arch.id,
                    'name': arch.name,
                    'step_name': arch.step.name
                })
        
        # 6. Verificar estado de entrevista
        interview_status = ProgramTransferService._check_interview_status(
            user_id, 
            from_program_id,
            to_program_id,
            reusable
        )
        
        return {
            'can_transfer': True,  # Siempre permitir, pero con advertencias
            'reusable_docs': reusable,
            'incompatible_docs': incompatible,
            'missing_docs': missing,
            'interview_status': interview_status
        }
    
    @staticmethod
    def execute_transfer(user_id: int, from_program_id: int, to_program_id: int, 
                        change_request_id: int = None) -> Dict:
        """
        Ejecuta el cambio de programa:
        1. Copia submissions compatibles
        2. Elimina submissions incompatibles (archivos físicos)
        3. Cancela entrevista si no cumple requisitos
        4. Actualiza user_program
        """
        try:
            # 1. Analizar transferencia
            analysis = ProgramTransferService.analyze_transfer(
                user_id, from_program_id, to_program_id
            )
            
            # 2. Obtener mapping
            mapping = ProgramTransferService._create_archive_mapping(
                from_program_id, to_program_id
            )
            
            # 3. Obtener submissions actuales
            current_submissions = db.session.execute(
                select(Submission)
                .join(ProgramStep, Submission.program_step_id == ProgramStep.id)
                .where(
                    Submission.user_id == user_id,
                    ProgramStep.program_id == from_program_id
                )
            ).scalars().all()
            
            # 4. Actualizar submissions reutilizables (modificar existentes, no crear nuevas)
            updated_count = 0
            for sub in current_submissions:
                if sub.archive_id in mapping['equivalent']:
                    to_archive_id = mapping['equivalent'][sub.archive_id]
                    to_archive = db.session.get(Archive, to_archive_id)
                    
                    # Encontrar program_step del destino
                    to_program_step = db.session.execute(
                        select(ProgramStep).where(
                            ProgramStep.program_id == to_program_id,
                            ProgramStep.step_id == to_archive.step_id
                        )
                    ).scalar_one_or_none()
                    
                    if to_program_step:
                        # Determinar el status a conservar
                        # Si es el mismo archivo (mismo ID), conservar status original
                        # Si es archivo equivalente, solo conservar 'approved' y 'rejected', resto va a 'pending'
                        is_same_file = (sub.archive_id == to_archive_id)
                        if is_same_file:
                            # Archivo idéntico: conservar status original completo
                            new_status = sub.status
                            keep_review_data = True
                        else:
                            # Archivo equivalente: solo conservar approved/rejected
                            new_status = sub.status if sub.status in ['approved', 'rejected'] else 'pending'
                            keep_review_data = (new_status == sub.status)
                        
                        # Actualizar la submission existente en lugar de crear nueva
                        sub.archive_id = to_archive_id
                        sub.program_step_id = to_program_step.id
                        sub.status = new_status
                        
                        # Solo conservar datos de revisión si el status no cambia
                        if not keep_review_data:
                            sub.review_date = None
                            sub.reviewer_comment = None
                        
                        updated_count += 1
            
            # 5. Eliminar submissions incompatibles (físico + DB)
            deleted_count = 0
            for sub in current_submissions:
                if sub.archive_id not in mapping['equivalent']:
                    # Eliminar archivo físico
                    ProgramTransferService._delete_physical_file(sub.file_path)
                    db.session.delete(sub)
                    deleted_count += 1
            
            # 6. Cancelar entrevista si es necesario
            interview_cancelled = False
            if analysis['interview_status']['will_cancel']:
                interview_cancelled = ProgramTransferService._cancel_interview(
                    user_id, from_program_id, 
                    reason="Cambio de programa - Requisitos no cumplidos en nuevo programa"
                )
            
            # 7. Actualizar user_program
            user_program = db.session.execute(
                select(UserProgram).where(
                    UserProgram.user_id == user_id,
                    UserProgram.program_id == from_program_id
                )
            ).scalar_one_or_none()
            
            if user_program:
                user_program.program_id = to_program_id
                user_program.enrollment_date = datetime.now(timezone.utc)
                user_program.status = 'active'
            
            db.session.commit()
            
            return {
                'success': True,
                'updated_documents': updated_count,
                'deleted_documents': deleted_count,
                'interview_cancelled': interview_cancelled,
                'new_program_id': to_program_id
            }
            
        except Exception as e:
            db.session.rollback()
            return {
                'success': False,
                'error': str(e)
            }
    
    @staticmethod
    def _create_archive_mapping(from_program_id: int, to_program_id: int) -> Dict:
        """
        Crea mapeo automático de archivos entre programas.
        
        Estrategia:
        1. Archivos con mismo ID → equivalent (archivo idéntico)
        2. Archivos en steps comunes con mismo nombre → equivalent
        3. Resto → incompatible
        """
        # Obtener archivos de ambos programas
        from_archives = ProgramTransferService._get_program_archives(from_program_id)
        to_archives = ProgramTransferService._get_program_archives(to_program_id)
        
        equivalent = {}  # from_archive_id → to_archive_id
        
        # Indexar archivos destino por ID, step_id y nombre
        to_by_id = {arch.id: arch for arch in to_archives}
        to_by_step = {}
        to_by_name = {}
        for arch in to_archives:
            to_by_step.setdefault(arch.step_id, []).append(arch)
            to_by_name.setdefault(arch.name.lower().strip(), []).append(arch)
        
        for from_arch in from_archives:
            matched = False
            
            # Estrategia 1: Mismo ID de archivo (archivo idéntico entre programas)
            if from_arch.id in to_by_id:
                equivalent[from_arch.id] = from_arch.id
                matched = True
            
            # Estrategia 2: Mismo step_id y mismo nombre (para steps comunes)
            elif not matched and from_arch.step_id in to_by_step:
                for to_arch in to_by_step[from_arch.step_id]:
                    if from_arch.name.lower().strip() == to_arch.name.lower().strip():
                        equivalent[from_arch.id] = to_arch.id
                        matched = True
                        break
        
        return {'equivalent': equivalent}
    
    @staticmethod
    def _get_program_archives(program_id: int) -> List[Archive]:
        """Obtiene todos los archivos de admisión de un programa"""
        return db.session.execute(
            select(Archive)
            .join(Step, Archive.step_id == Step.id)
            .join(ProgramStep, Step.id == ProgramStep.step_id)
            .where(
                ProgramStep.program_id == program_id,
                Step.phase_id == 1  # Solo fase de admisión
            )
        ).scalars().all()
    
    @staticmethod
    def _check_interview_status(user_id: int, from_program_id: int, 
                                to_program_id: int, reusable_docs: List) -> Dict:
        """
        Verifica si hay entrevista asignada y si debe cancelarse.
        
        Criterio: Cancelar si no cumple requisitos de documentos aprobados
        en el nuevo programa.
        """
        # Buscar entrevista activa
        appointment = db.session.execute(
            select(Appointment)
            .join(EventSlot, Appointment.slot_id == EventSlot.id)
            .join(EventWindow, EventSlot.event_window_id == EventWindow.id)
            .join(Event, EventWindow.event_id == Event.id)
            .where(
                Appointment.applicant_id == user_id,
                Appointment.status == 'scheduled',
                Event.program_id == from_program_id,
                Event.type == 'interview'
            )
        ).scalar_one_or_none()
        
        if not appointment:
            return {
                'has_interview': False,
                'will_cancel': False,
                'reason': None
            }
        
        # Verificar si cumple requisitos en nuevo programa
        # Contar documentos aprobados reutilizables
        approved_count = sum(1 for doc in reusable_docs if doc['status'] == 'approved')
        
        # Obtener total de documentos requeridos en nuevo programa (excluyendo entrevista)
        required_archives = db.session.execute(
            select(Archive)
            .join(Step, Archive.step_id == Step.id)
            .join(ProgramStep, Step.id == ProgramStep.step_id)
            .where(
                ProgramStep.program_id == to_program_id,
                Step.phase_id == 1,
                ProgramStep.sequence < 4,  # Excluir paso de entrevista
                Archive.is_uploadable == True
            )
        ).scalars().all()
        
        required_count = len(required_archives)
        
        # Cancelar si no tiene suficientes documentos aprobados
        will_cancel = approved_count < required_count
        
        return {
            'has_interview': True,
            'will_cancel': will_cancel,
            'reason': f'Documentos aprobados insuficientes ({approved_count}/{required_count})' if will_cancel else None,
            'appointment_id': appointment.id
        }
    
    @staticmethod
    def _cancel_interview(user_id: int, program_id: int, reason: str) -> bool:
        """Cancela la entrevista del usuario en el programa"""
        try:
            appointment = db.session.execute(
                select(Appointment)
                .join(EventSlot, Appointment.slot_id == EventSlot.id)
                .join(EventWindow, EventSlot.event_window_id == EventWindow.id)
                .join(Event, EventWindow.event_id == Event.id)
                .where(
                    Appointment.applicant_id == user_id,
                    Appointment.status == 'scheduled',
                    Event.program_id == program_id,
                    Event.type == 'interview'
                )
            ).scalar_one_or_none()
            
            if appointment:
                slot = db.session.get(EventSlot, appointment.slot_id)
                appointment.status = 'cancelled'
                appointment.notes = f"{appointment.notes or ''}\n[Auto-cancelada]: {reason}".strip()
                
                if slot:
                    slot.status = 'free'
                    slot.held_by = None
                    slot.hold_expires_at = None
                
                return True
            return False
        except Exception:
            return False
    
    @staticmethod
    def _delete_physical_file(file_path: str):
        """Elimina el archivo físico del sistema"""
        if not file_path:
            return
        
        try:
            full_path = os.path.join(
                current_app.config['USER_DOCS_FOLDER'],
                file_path
            )
            if os.path.exists(full_path):
                os.remove(full_path)
        except Exception as e:
            current_app.logger.error(f"Error eliminando archivo {file_path}: {e}")