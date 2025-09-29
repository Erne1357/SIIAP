# app/services/admission.py

from flask import current_app
from sqlalchemy.orm import selectinload
from app.models import Step, ProgramStep, Phase, Submission, ExtensionRequest
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
    current_app.logger.warning(f"Active extensions for user_id {user_id}, program_id {program_id}: {json.dumps(extensions_json, indent=2)}")
    # 4) Lock info por paso (considerando extensiones activas)
    def _is_locked(step):
        return False
        # secuencia 0 nunca bloqueada
        seq = step.program_steps[0].sequence
        if seq == 0 or seq == 1:
            return False
        # buscar paso previo
        prev = next((
            st for st in steps
            if any(ps.sequence == seq-1 for ps in st.program_steps)
        ), None)
        if not prev:
            return False
        # revisar todos los archives del paso anterior
        for arch in prev.archives:
            sub = subs.get(arch.id)
            ext = active_extensions.get(arch.id)  # Usar active_extensions
            # Si hay extensión activa, no bloquea
            if ext:
                continue
            # Si no hay submission o no está aprobada, bloquea
            if not sub or sub.status != 'approved':
                return True
        return False

    lock_info = { step.id: _is_locked(step) for step in steps }

    # 5) Estado resumido por paso (incluyendo extensiones)
    def _step_state(step):
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
