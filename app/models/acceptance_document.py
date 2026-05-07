# app/models/acceptance_document.py
from app import db
from app.utils.datetime_utils import now_local


class AcceptanceDocument(db.Model):
    """
    Documentos de aceptacion e inscripcion.

    Tipos de documentos (document_type):
    - acceptance_letter: Carta de aceptacion (coordinador sube, aspirante descarga)
    - course_schedule:   Tira de materias   (coordinador sube, aspirante descarga)
    - enrollment_receipt: Boleta de servicios escolares (aspirante sube, coordinador revisa)

    Estados (status):
    - pending:  No subido aun
    - uploaded: Subido, pendiente de revision (solo enrollment_receipt)
    - approved: Aprobado
    - rejected: Rechazado
    """
    __tablename__ = 'acceptance_document'

    id = db.Column(db.Integer, primary_key=True)
    user_program_id = db.Column(db.Integer, db.ForeignKey('user_program.id'), nullable=False)
    document_type = db.Column(db.String(30), nullable=False)
    file_path = db.Column(db.String(500), nullable=True)

    uploaded_by_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=True)
    uploaded_at = db.Column(db.DateTime, nullable=True)

    status = db.Column(db.String(20), nullable=False, default='pending')

    reviewed_by_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=True)
    reviewed_at = db.Column(db.DateTime, nullable=True)
    review_notes = db.Column(db.Text, nullable=True)

    created_at = db.Column(db.DateTime, default=now_local, nullable=False)
    updated_at = db.Column(db.DateTime, default=now_local, onupdate=now_local, nullable=False)

    # Relaciones
    user_program = db.relationship('UserProgram', back_populates='acceptance_documents')
    uploaded_by = db.relationship('User', foreign_keys=[uploaded_by_id])
    reviewed_by = db.relationship('User', foreign_keys=[reviewed_by_id])

    def to_dict(self):
        return {
            'id': self.id,
            'user_program_id': self.user_program_id,
            'document_type': self.document_type,
            'file_path': self.file_path,
            'uploaded_by_id': self.uploaded_by_id,
            'uploaded_at': self.uploaded_at.isoformat() if self.uploaded_at else None,
            'status': self.status,
            'reviewed_by_id': self.reviewed_by_id,
            'reviewed_at': self.reviewed_at.isoformat() if self.reviewed_at else None,
            'review_notes': self.review_notes,
        }
