from datetime import datetime, timezone
from app import db
from app.models.program_change_request import ProgramChangeRequest
from app.models.document_mapping import DocumentMapping
from app.models.submission import Submission
from app.models.archive import Archive
from app.models.program_step import ProgramStep
from app.models.step import Step

class ProgramChangesService:
    @staticmethod
    def create_request(applicant_id:int, from_program_id:int, to_program_id:int, reason:str|None=None) -> ProgramChangeRequest:
        req = ProgramChangeRequest(
            applicant_id=applicant_id,
            from_program_id=from_program_id,
            to_program_id=to_program_id,
            reason=reason,
            status='pending',
            created_at=datetime.now(timezone.utc)
        )
        db.session.add(req)
        db.session.commit()
        return req

    @staticmethod
    def decide_request(request_id:int, status:str, decided_by:int):
        if status not in ('approved','rejected','cancelled'):
            raise ValueError("status inválido")

        req = db.session.get(ProgramChangeRequest, request_id)
        if not req:
            raise ValueError("ProgramChangeRequest no encontrado")

        req.status = status
        req.decided_by = decided_by
        req.decided_at = datetime.now(timezone.utc)

        if status == 'approved':
            ProgramChangesService._apply_change(req)

        db.session.commit()
        return req

    @staticmethod
    def _apply_change(req: ProgramChangeRequest):
        """
        Reutiliza submissions mapeadas como 'equivalent'.
        'needs_update': no copia; el checklist del nuevo programa mostrará el pendiente.
        'incompatible': ignora.
        """
        # 1) obtener mapeos
        maps = db.session.query(DocumentMapping).filter_by(
            from_program_id=req.from_program_id,
            to_program_id=req.to_program_id
        ).all()

        # 2) submissions del programa origen del usuario
        origin_subs = db.session.query(Submission).filter(
            Submission.user_id == req.applicant_id,
            Submission.program_step_id.in_(
                db.session.query(ProgramStep.id).filter(
                    ProgramStep.program_id == req.from_program_id
                )
            )
        ).all()

        # 3) indexar por archive_id
        by_archive = {}
        for s in origin_subs:
            by_archive.setdefault(s.archive_id, []).append(s)

        # 4) para cada mapeo, actuar
        for m in maps:
            if m.mapping_rule == 'incompatible':
                continue

            # encontrar el step del programa destino que contiene el archive destino
            to_archive = db.session.get(Archive, m.to_archive_id)
            if not to_archive:
                continue
            # ProgramStep del destino que coincida con el step del archive destino
            dest_ps = db.session.query(ProgramStep).filter_by(
                program_id=req.to_program_id,
                step_id=to_archive.step_id
            ).first()
            if not dest_ps:
                continue

            # copiar la última submission válida del archive origen (si existe)
            origin_list = by_archive.get(m.from_archive_id, [])
            if not origin_list:
                continue
            origin_list.sort(key=lambda s: s.upload_date or datetime.min, reverse=True)
            src = origin_list[0]

            if m.mapping_rule == 'equivalent':
                # duplicar submission apuntando al nuevo program_step / archive destino
                copy = Submission(
                    file_path=src.file_path,
                    status=src.status,  # o 'pending_review' si quieres revalidar
                    user_id=src.user_id,
                    archive_id=to_archive.id,
                    program_step_id=dest_ps.id,
                    period=src.period,
                    semester=src.semester,
                    review_date=src.review_date,
                    reviewer_id=src.reviewer_id,
                    reviewer_comment=src.reviewer_comment
                )
                db.session.add(copy)
            elif m.mapping_rule == 'needs_update':
                # no copiamos archivo; el checklist mostrará el pendiente del archive destino
                pass
