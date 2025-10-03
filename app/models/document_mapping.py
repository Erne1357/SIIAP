from app import db

class DocumentMapping(db.Model):
    __tablename__ = 'document_mapping'

    id = db.Column(db.Integer, primary_key=True)

    from_program_id = db.Column(db.Integer, db.ForeignKey('program.id', ondelete='CASCADE', onupdate='CASCADE'), nullable=False)
    to_program_id   = db.Column(db.Integer, db.ForeignKey('program.id', ondelete='CASCADE', onupdate='CASCADE'), nullable=False)

    # Mapeo por tipo de evidencia concreta (archive) entre programas
    from_archive_id = db.Column(db.Integer, db.ForeignKey('archive.id', ondelete='CASCADE', onupdate='CASCADE'), nullable=False)
    to_archive_id   = db.Column(db.Integer, db.ForeignKey('archive.id', ondelete='CASCADE', onupdate='CASCADE'), nullable=False)

    mapping_rule = db.Column(db.String(20), nullable=False, default='equivalent')  # equivalent|needs_update|incompatible
