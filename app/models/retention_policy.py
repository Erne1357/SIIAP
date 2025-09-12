from app import db

class RetentionPolicy(db.Model):
    __tablename__ = 'retention_policy'

    id = db.Column(db.Integer, primary_key=True)
    archive_id = db.Column(db.Integer, db.ForeignKey('archive.id', ondelete='CASCADE', onupdate='CASCADE'), nullable=False)

    keep_years = db.Column(db.Integer)                 # ej. 4
    keep_forever = db.Column(db.Boolean, default=False, nullable=False)
    apply_after = db.Column(db.String(20), default='graduated')  # graduated|dropped|enrollment
