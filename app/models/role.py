from app import db

class Role(db.Model):
    __tablename__ = 'role'
    
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(50), nullable=False)
    description = db.Column(db.String(200))
    
    # Relación: Un rol tiene muchos usuarios
    users = db.relationship('User', back_populates='role')

    def __init__(self, name, description):
        self.name = name
        self.description = description
