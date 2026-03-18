# app/models/semester_enrollment.py
from app import db
from app.utils.datetime_utils import now_local


class SemesterEnrollment(db.Model):
    """
    Registro de inscripcion semestral del estudiante.

    Representa la participacion de un estudiante en un semestre especifico
    dentro de un periodo academico determinado.

    Estados (status):
    - pending:   Inicio de periodo, pendiente de confirmar pago/inscripcion
    - active:    Coordinador confirmo la inscripcion del semestre
    - completed: Semestre terminado exitosamente
    - on_leave:  Baja temporal (permiso)
    - dropped:   Baja definitiva del semestre
    """
    __tablename__ = 'semester_enrollment'

    id = db.Column(db.Integer, primary_key=True)

    user_program_id = db.Column(
        db.Integer, db.ForeignKey('user_program.id'), nullable=False
    )
    academic_period_id = db.Column(
        db.Integer, db.ForeignKey('academic_period.id'), nullable=False
    )

    # Numero de semestre que corresponde a esta inscripcion (1, 2, 3, ...)
    semester_number = db.Column(db.Integer, nullable=False)

    # Estado de la inscripcion semestral
    status = db.Column(db.String(30), default='pending', nullable=False)

    # Confirmacion por coordinador
    enrollment_confirmed = db.Column(db.Boolean, default=False, nullable=False)
    confirmed_by = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=True)
    confirmed_at = db.Column(db.DateTime, nullable=True)

    # Notas del coordinador
    notes = db.Column(db.Text, nullable=True)

    # Fecha limite para entrega de documentos de permanencia
    documents_deadline = db.Column(db.DateTime, nullable=True)

    created_at = db.Column(db.DateTime, default=now_local, nullable=False)
    updated_at = db.Column(
        db.DateTime, default=now_local, onupdate=now_local, nullable=False
    )

    # Relaciones
    user_program = db.relationship(
        'UserProgram', back_populates='semester_enrollments'
    )
    academic_period = db.relationship(
        'AcademicPeriod', back_populates='semester_enrollments'
    )
    confirmed_by_user = db.relationship('User', foreign_keys=[confirmed_by])

    def to_dict(self):
        return {
            'id': self.id,
            'user_program_id': self.user_program_id,
            'academic_period_id': self.academic_period_id,
            'semester_number': self.semester_number,
            'status': self.status,
            'enrollment_confirmed': self.enrollment_confirmed,
            'confirmed_by': self.confirmed_by,
            'confirmed_at': self.confirmed_at.isoformat() if self.confirmed_at else None,
            'notes': self.notes,
            'documents_deadline': self.documents_deadline.isoformat() if self.documents_deadline else None,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'updated_at': self.updated_at.isoformat() if self.updated_at else None,
        }
