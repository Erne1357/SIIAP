from datetime import datetime, timedelta
from app import db
from app.models.retention_policy import RetentionPolicy
from app.models.submission import Submission
from app.models.user_program import UserProgram

class RetentionService:
    @staticmethod
    def compute_candidates(now:datetime) -> list[Submission]:
        """
        Retorna submissions candidatas a borrado según retention_policy.
        - apply_after: 'graduated'|'dropped'|'enrollment'
        """
        policies = db.session.query(RetentionPolicy).all()
        candidates = []

        for pol in policies:
            q = db.session.query(Submission).filter(Submission.archive_id == pol.archive_id)

            if pol.keep_forever:
                continue
            if pol.keep_years is None:
                continue

            if pol.apply_after == 'enrollment':
                # comparar contra enrollment_date del user_program (primero por programa del submission)
                # Este cálculo puede variar si tienes múltiples user_program para el user.
                q = q.join(UserProgram, UserProgram.user_id == Submission.user_id)
                threshold = now - timedelta(days=pol.keep_years*365)
                q = q.filter(UserProgram.enrollment_date <= threshold)
            else:
                # En esta versión mínima, asumimos que el estado final (graduated/dropped)
                # quedó invertido en user_program.status. Filtra por antigüedad general del archivo.
                threshold = now - timedelta(days=pol.keep_years*365)
                q = q.filter(Submission.upload_date <= threshold)

            candidates.extend(q.all())

        return candidates

    @staticmethod
    def purge_submissions(submission_ids:list[int]) -> int:
        """
        Borra lógicamente los registros; si quieres borrar archivos físicos, hazlo en un job aparte.
        """
        if not submission_ids:
            return 0
        deleted = db.session.query(Submission).filter(Submission.id.in_(submission_ids)).delete(synchronize_session=False)
        db.session.commit()
        return deleted
