from datetime import datetime, timezone
from sqlalchemy.exc import IntegrityError
from app import db
from app.models.submission import Submission
from app.models.extension_request import ExtensionRequest

class ExtensionsService:
    @staticmethod
    def create_request(submission_id:int, requested_by:int, role:str, reason:str=None, requested_until=None) -> ExtensionRequest:
        er = ExtensionRequest(
            submission_id=submission_id,
            requested_by=requested_by,
            role=role,
            reason=reason,
            requested_until=requested_until,
            status='pending',
            created_at=datetime.now(timezone.utc),
            updated_at=datetime.now(timezone.utc),
        )
        db.session.add(er)
        db.session.commit()
        return er

    @staticmethod
    def list_requests(submission_id=None, status=None, applicant_id=None):
        q = db.session.query(ExtensionRequest)
        if submission_id:
            q = q.filter(ExtensionRequest.submission_id == submission_id)
        if status:
            q = q.filter(ExtensionRequest.status == status)
        if applicant_id:
            # filtra por owner del submission
            q = q.join(Submission, Submission.id == ExtensionRequest.submission_id).filter(Submission.user_id == applicant_id)
        return q.order_by(ExtensionRequest.created_at.desc()).all()

    @staticmethod
    def decide_request(extreq_id:int, status:str, decided_by:int, granted_until=None, condition_text=None) -> ExtensionRequest:
        er = db.session.get(ExtensionRequest, extreq_id)
        if not er:
            raise ValueError("ExtensionRequest no encontrado")

        if status not in ('granted','rejected','cancelled'):
            raise ValueError("status inválido")

        er.status = status
        er.decided_by = decided_by
        er.decided_at = datetime.now(timezone.utc)
        er.updated_at = datetime.now(timezone.utc)
        er.granted_until = granted_until
        er.condition_text = condition_text

        # Impacto en la submission
        sub = db.session.get(Submission, er.submission_id)
        if not sub:
            raise ValueError("Submission no encontrada para la prórroga")

        if status == 'granted':
            if not granted_until:
                raise ValueError("Se requiere granted_until para aprobar")
            sub.deadline_at = granted_until
            sub.is_in_extension = True
        else:
            # al rechazar/cancelar, no forzamos cambios de deadline; solo limpiamos flag si apuntaba a esta prórroga
            # (opcional) puedes recalcular el deadline efectivo en otro servicio si manejas varias prórrogas
            sub.is_in_extension = False

        db.session.commit()
        return er
