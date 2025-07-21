from sqlalchemy.orm import selectinload
from app.models import (UserProgram, Program, ProgramStep,
                        Step, Archive, Submission, Phase)
def get_admission_state(user_id,program_id,up):
    
    # ── 2. Trae pasos/archivos de la fase admission ───────────────
    admission_steps = (
        Step.query
        .join(ProgramStep)
        .join(Phase)
        .filter(ProgramStep.program_id == program_id,
                Phase.name == 'admission', ProgramStep.sequence > 0)
        .options(selectinload(Step.archives))
        .order_by(ProgramStep.sequence)
        .all()
    )

    # ── 3. Submissions del usuario ────────────────────────────────
    archive_ids = [a.id for st in admission_steps for a in st.archives]
    subs = {s.archive_id: s for s in
            Submission.query
                      .filter_by(user_id=user_id)
                      .filter(Submission.archive_id.in_(archive_ids))
                      .all()}

    # ── 4. Cálculos para la barra y listas ────────────────────────
    total_docs   = len(archive_ids)
    status_count = {"approved": 0, "rejected": 0, "review": 0, "pending": 0}

    for a_id in archive_ids:
        sub = subs.get(a_id)
        if not sub:
            status_count["pending"] += 1
        elif sub.status == "approved":
            status_count["approved"] += 1
        elif sub.status == "rejected":
            status_count["rejected"] += 1
        else:                           # pending -or- in review
            status_count["review"] += 1

    # segmentos para la barra (orden: rojo, verde, amarillo, gris)
    progress_segments = []
    if total_docs:
        for key, css in [("rejected", "danger"),
                        ("approved", "success"),
                        ("review",   "warning"),  # amarillo
                        ("pending",  "secondary")]:
            pct = round(status_count[key] / total_docs * 100, 1)
            if pct:
                progress_segments.append({"pct": pct, "class": css})

    # porcentaje global de aprobación (sigue sirviendo para texto)
    progress_pct = round(status_count["approved"] / total_docs * 100) if total_docs else 0


    pending_items = []
    for st in admission_steps:
        for arch in st.archives:
            sub = subs.get(arch.id)
            if not sub or sub.status in ('pending', 'rejected'):
                pending_items.append({'name': arch.name,
                                      'status': sub.status if sub else 'pending'})

    # ── 5. Timeline (muy básico) ──────────────────────────────────
    timeline = [
        {'label': 'Registro completado',
         'date': up.enrollment_date.strftime('%d/%m/%Y'),
         'state': 'done'},
        {'label': 'Documentos enviados',
         'date': subs[next(iter(subs))].upload_date.strftime('%d/%m/%Y')
                 if subs else None,
         'state': 'done' if subs else 'pending'},
        {'label': 'Revisión de documentos',
         'date': None,
         'state': 'inprogress' if status_count["approved"] < total_docs else 'done'},
        {'label': 'Entrevista',
         'date': getattr(up, 'interview_date', None),
         'state': 'pending'},
        {'label': 'Decisión final',
         'date': getattr(up, 'decision_date', None),
         'state': getattr(up, 'decision_status', 'pending')}
    ]
    return {
        "progress_segments": progress_segments,
        "status_count": status_count,
        "progress_pct": progress_pct,
        "pending_items": pending_items,
        "timeline": timeline
    }