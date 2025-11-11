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
    
    def to_dict(self):
        return {
            'id': self.id,
            'from_program_id': self.from_program_id,
            'to_program_id': self.to_program_id,
            'from_archive_id': self.from_archive_id,
            'to_archive_id': self.to_archive_id,
            'mapping_rule': self.mapping_rule
        }
