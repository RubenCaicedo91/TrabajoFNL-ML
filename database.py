from flask_sqlalchemy import SQLAlchemy
from flask_login import UserMixin
from datetime import datetime

# Inicializar SQLAlchemy
db = SQLAlchemy()

class User(UserMixin, db.Model):
    """Modelo de Usuario"""
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False)
    department = db.Column(db.String(100))
    role = db.Column(db.String(20), default='USER')
    password_hash = db.Column(db.String(200))
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    is_active = db.Column(db.Boolean, default=True)
    
    def set_password(self, password):
        """Hashear contraseña"""
        from werkzeug.security import generate_password_hash
        self.password_hash = generate_password_hash(password)
    
    def check_password(self, password):
        """Verificar contraseña"""
        from werkzeug.security import check_password_hash
        return check_password_hash(self.password_hash, password)

class ProductionData(db.Model):
    """Modelo de Datos de Producción"""
    id = db.Column(db.Integer, primary_key=True)
    department = db.Column(db.String(100), nullable=False)
    month = db.Column(db.Integer, nullable=False)
    year = db.Column(db.Integer, nullable=False)
    volume_liters = db.Column(db.Float, nullable=False)
    price_per_liter = db.Column(db.Float, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

class Prediction(db.Model):
    """Modelo de Predicciones"""
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    department = db.Column(db.String(100), nullable=False)
    target_month = db.Column(db.Integer, nullable=False)
    target_year = db.Column(db.Integer, nullable=False)
    predicted_volume = db.Column(db.Float, nullable=False)
    predicted_price = db.Column(db.Float, nullable=False)
    confidence = db.Column(db.Float, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    # Relación con usuario
    user = db.relationship('User', backref=db.backref('predictions', lazy=True))

class Region(db.Model):
    """Modelo de Regiones"""
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), unique=True, nullable=False)
    code = db.Column(db.String(10), unique=True, nullable=False)
    is_active = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)