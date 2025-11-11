from app import db

class Phase(db.Model):
    __tablename__ = 'phase'
    
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(50), nullable=False)  # Ejemplo: 'admission', 'permanence', etc.
    description = db.Column(db.Text)
    
    # Relación: Una fase tiene muchos steps
    steps = db.relationship("Step", back_populates="phase")

    def __init__(self, name, description):
        self.name = name
        self.description = description
    
    def to_dict(self):
        return {
            'id': self.id,
            'name': self.name,
            'description': self.description
        }