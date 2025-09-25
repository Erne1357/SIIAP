# app/services/admission.py

from sqlalchemy.orm import selectinload
from app.models import Step, ProgramStep, Phase, Submission

def get_admission_state(user_id: int, program_id: int, up) -> dict:
    """
    Devuelve todo lo necesario para la vista de Admisión:
      - steps: lista de objetos Step con sus archives cargados
      - subs: dict archive_id → Submission
      - lock_info: dict step_id → bool (bloqueado)
      - step_states: dict step_id → 'approved'|'rejected'|'review'|'pending'
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

    # 3) Lock info por paso
    def _is_locked(step):
        # secuencia 0 nunca bloqueada
        return False
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
            if not sub or sub.status != 'approved':
                return True
        return False

    lock_info = { step.id: _is_locked(step) for step in steps }

    # 4) Estado resumido por paso
    def _step_state(step):
        statuses = [
            (subs[arch.id].status if arch.id in subs else 'pending')
            for arch in step.archives
        ]
        if 'rejected' in statuses:
            return 'rejected'
        if all(s == 'approved' for s in statuses):
            return 'approved'
        if any(s == 'review' for s in statuses):
            return 'review'
        return 'pending'

    step_states = { step.id: _step_state(step) for step in steps }

    # 5) Conteos y segmentos de progreso
    total = len(archive_ids)
    status_count = {k:0 for k in ('approved','rejected','review','pending')}
    for sid in archive_ids:
        st = subs.get(sid)
        key = st.status if st else 'pending'
        status_count[key] += 1
    segments = []
    if total:
        for key, css in [
            ('rejected','danger'),
            ('approved','success'),
            ('review','warning'),
            ('pending','secondary')
        ]:
            pct = round(status_count[key]/total*100,1)
            if pct:
                segments.append({'pct':pct,'class':css})
    progress_pct = round(status_count['approved']/total*100) if total else 0

    # 6) Lista de pendientes/rechazados
    pending_items = [
        {'name': arch.name,
         'status': (subs[arch.id].status if arch.id in subs else 'pending')}
        for step in steps for arch in step.archives
        if arch.id not in subs or subs[arch.id].status in ('pending','rejected')
    ]

    # 7) Timeline
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
        'lock_info': lock_info,
        'step_states': step_states,
        'progress_segments': segments,
        'status_count': status_count,
        'progress_pct': progress_pct,
        'pending_items': pending_items,
        'timeline': timeline
    }
