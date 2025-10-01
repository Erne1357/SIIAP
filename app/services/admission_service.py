# app/services/admission.py

from flask import current_app
from sqlalchemy.orm import selectinload
from sqlalchemy import and_, or_, select
from app import db
from app.models import Step, ProgramStep, Phase, Submission, ExtensionRequest
from app.models.event import Event, EventSlot, EventAttendance, EventWindow
from datetime import datetime, timezone
import logging,json

def get_admission_state(user_id: int, program_id: int, up) -> dict:
    """
    Devuelve todo lo necesario para la vista de Admisión:
      - steps: lista de objetos Step con sus archives cargados
      - subs: dict archive_id → Submission
      - extensions: dict archive_id → ExtensionRequest (solo las activas)
      - lock_info: dict step_id → bool (bloqueado)
      - step_states: dict step_id → 'approved'|'rejected'|'review'|'pending'|'extended'
      - progress_segments, status_count, progress_pct, pending_items, timeline
    """
    # 1) Traer pasos + archivos
    steps = (
        Step.query
        .join(ProgramStep)
        .join(Phase)
        .filter(
            ProgramStep.program_id == program_id,
            Phase.name == 'admission'
        )
        .options(selectinload(Step.archives))
        .order_by(ProgramStep.sequence)
        .all()
    )

    # 2) Map submissions del usuario
    archive_ids = [a.id for step in steps for a in step.archives]
    subs = {
        s.archive_id: s
        for s in Submission.query
                          .filter_by(user_id=user_id)
                          .filter(Submission.archive_id.in_(archive_ids))
                          .all()
    }

    # 3) Map extensiones activas del usuario
    now = datetime.now(timezone.utc)
    all_extensions = {
        e.archive_id: e
        for e in ExtensionRequest.query
                                .filter_by(user_id=user_id)
                                .filter(ExtensionRequest.archive_id.in_(archive_ids))
                                .order_by(ExtensionRequest.created_at.desc())
                                .all()
    }
    
    # Extensiones activas (solo granted y no expiradas)
    active_extensions = {}
    for aid, ext in all_extensions.items():
        if ext.status == 'granted' and ext.granted_until:
            # Asegurar que granted_until tenga zona horaria
            granted_until = ext.granted_until
            if granted_until.tzinfo is None:
                # Si no tiene zona horaria, asumir UTC
                granted_until = granted_until.replace(tzinfo=timezone.utc)
            
            if granted_until > now:
                active_extensions[aid] = ext
    
    extensions_json = {
        str(archive_id): {
            'id': ext.id,
            'archive_id': ext.archive_id,
            'status': ext.status,
            'reason': ext.reason,
            'granted_until': ext.granted_until.isoformat() if ext.granted_until else None,
            'requested_by': ext.requested_by,
            'role': ext.role,
            'created_at': ext.created_at.isoformat() if ext.created_at else None
        }
        for archive_id, ext in all_extensions.items()
    }
    # 4) Lock info por paso (solo bloquear el último paso)
    def _is_locked(step):
        # Obtener la secuencia de este paso
        seq = step.program_steps[0].sequence
        
        # Nunca bloquear los primeros pasos (secuencia 0 y 1)
        if seq == 0 or seq == 1:
            return False
            
        # Encontrar el paso con la secuencia más alta (último paso)
        max_seq = max(st.program_steps[0].sequence for st in steps)
        
        # Solo bloquear el último paso (entrevista/defensa)
        if seq != max_seq:
            return False
            
        # Para el último paso, verificar que TODOS los pasos anteriores estén completos
        for prev_step in steps:
            prev_seq = prev_step.program_steps[0].sequence
            
            # Saltar el paso actual y el paso 0 (registro)
            if prev_seq >= seq or prev_seq == 0:
                continue
                
            # Revisar todos los archivos del paso anterior
            for arch in prev_step.archives:
                if not arch.is_uploadable:
                    continue
                    
                sub = subs.get(arch.id)
                ext = active_extensions.get(arch.id)
                
                # Si hay extensión activa, está válido
                if ext:
                    continue
                    
                # Si no hay submission o no está aprobada/extendida, bloquea
                if not sub or sub.status not in ['approved', 'extended']:
                    return True
                    
        return False

    lock_info = { step.id: _is_locked(step) for step in steps }

    # 4.5) Verificar si el usuario tiene entrevista asignada (solo EventSlot para entrevistas 1 a 1)
    def _has_interview_assigned():
        # Buscar en EventSlot (para entrevistas individuales 1 a 1)
        slot_assigned = db.session.execute(
            select(EventSlot).join(
                EventWindow, EventSlot.event_window_id == EventWindow.id
            ).join(
                Event, EventWindow.event_id == Event.id
            ).where(
                and_(
                    EventSlot.held_by == user_id,
                    EventSlot.status == 'booked',
                    Event.program_id == program_id,
                    Event.type == 'interview'
                )
            )
        ).scalar_one_or_none()
        current_app.logger.warning(f"Entrevista asignada para usuario {user_id} en programa {program_id}: {bool(slot_assigned)}")
        return bool(slot_assigned)
    
    has_interview = _has_interview_assigned()

    # 5) Estado resumido por paso (incluyendo extensiones y entrevistas)
    def _step_state(step):
        # Determinar si este es el último paso (entrevista/defensa)
        seq = step.program_steps[0].sequence
        max_seq = max(st.program_steps[0].sequence for st in steps)
        is_last_step = (seq == max_seq)
        
        statuses = []
        has_extension = False
        
        for arch in step.archives:
            if arch.id in active_extensions:  # Usar active_extensions
                has_extension = True
                # Si hay extensión activa, consideramos como "extended"
                statuses.append('extended')
            elif arch.id in subs:
                statuses.append(subs[arch.id].status)
            else:
                statuses.append('pending')
        
        # Para el último paso, considerar también si tiene entrevista asignada
        if is_last_step:
            if has_interview:
                return 'approved'  # Verde con palomita si tiene entrevista
            else:
                # Si no tiene entrevista, seguir la lógica normal pero no aprobar automáticamente
                if 'rejected' in statuses:
                    return 'rejected'
                if 'extended' in statuses:
                    return 'extended'
                if any(s == 'review' for s in statuses):
                    return 'review'
                return 'pending'
        else:
            # Para otros pasos, lógica normal
            if 'rejected' in statuses:
                return 'rejected'
            if all(s == 'approved' for s in statuses):
                return 'approved'
            if 'extended' in statuses:
                return 'extended'
            if any(s == 'review' for s in statuses):
                return 'review'
            return 'pending'

    step_states = { step.id: _step_state(step) for step in steps }

    # 6) Conteos y segmentos de progreso (incluyendo extensiones activas)
    total = len(archive_ids)
    status_count = {k:0 for k in ('approved','rejected','review','pending','extended')}
    
    for aid in archive_ids:
        if aid in active_extensions:  # Usar active_extensions
            status_count['extended'] += 1
        elif aid in subs:
            status_count[subs[aid].status] += 1
        else:
            status_count['pending'] += 1
    
    segments = []
    if total:
        for key, css in [
            ('rejected','danger'),
            ('approved','success'),
            ('extended','info'),
            ('review','warning'),
            ('pending','secondary')
        ]:
            pct = round(status_count[key]/total*100,1)
            if pct:
                segments.append({'pct':pct,'class':css})
    
    progress_pct = round(status_count['approved']/total*100) if total else 0

    # 7) Lista de pendientes/rechazados (considerando todas las extensiones)
    pending_items = []
    for step in steps:
        for arch in step.archives:
            if arch.id in active_extensions:
                # Archivo con extensión activa
                ext = active_extensions[arch.id]
                pending_items.append({
                    'name': arch.name,
                    'status': 'extended',
                    'extension_until': ext.granted_until.strftime('%d/%m/%Y %H:%M'),
                    'extension_reason': ext.reason
                })
            elif arch.id not in subs or subs[arch.id].status in ('pending','rejected'):
                # Archivo pendiente o rechazado sin extensión activa
                pending_items.append({
                    'name': arch.name,
                    'status': (subs[arch.id].status if arch.id in subs else 'pending')
                })

    # 8) Timeline
    timeline = [
        {'label':'Registro completado',
         'date': up.enrollment_date.strftime('%d/%m/%Y'),
         'state':'done'},
        {'label':'Documentos enviados',
         'date': (
             subs[next(iter(subs))].upload_date.strftime('%d/%m/%Y')
             if subs else None
         ),
         'state':'done' if subs else 'pending'},
        {'label':'Revisión de documentos',
         'date':None,
         'state':'inprogress' if status_count['approved']<total else 'done'},
        {'label':'Entrevista',
         'date':getattr(up,'interview_date',None),
         'state':'pending'},
        {'label':'Decisión final',
         'date':getattr(up,'decision_date',None),
         'state':getattr(up,'decision_status','pending')}
    ]

    return {
        'steps': steps,
        'subs': subs,
        'extensions': active_extensions,  # Solo extensiones activas para compatibilidad
        'all_extensions': all_extensions,  # Todas las extensiones para mostrar estados
        'lock_info': lock_info,
        'step_states': step_states,
        'progress_segments': segments,
        'status_count': status_count,
        'progress_pct': progress_pct,
        'pending_items': pending_items,
        'timeline': timeline
    }
