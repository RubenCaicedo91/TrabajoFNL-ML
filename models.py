"""Modelos de la base de datos.

Contiene las clases ORM `User` y `Consulta` empleadas por la aplicación.
Proporciona métodos auxiliares para persistencia y utilidades básicas.
"""

from flask_login import UserMixin
from werkzeug.security import generate_password_hash, check_password_hash
from database import db
from datetime import datetime


# Lookup para razas y departamentos (3FN)
class Raza(db.Model):
    __tablename__ = 'razas'
    id = db.Column(db.BigInteger, primary_key=True)
    name = db.Column(db.String(120), unique=True, nullable=False)

    def save(self):
        if not self.id:
            db.session.add(self)
        db.session.commit()


class Departamento(db.Model):
    __tablename__ = 'departamentos'
    id = db.Column(db.BigInteger, primary_key=True)
    name = db.Column(db.String(120), unique=True, nullable=False)

    def save(self):
        if not self.id:
            db.session.add(self)
        db.session.commit()

class User(db.Model, UserMixin):
    __tablename__ = 'blog_user'
    """Modelo de usuario.

    Campos principales: id, name, email, password, is_admin.
    Métodos: set_password, check_password, save, y selectores estáticos.
    """
    id = db.Column(db.BigInteger, primary_key=True)
    name = db.Column(db.String(80), nullable=False)
    email = db.Column(db.String(256), unique=True, nullable=False)
    password = db.Column(db.String(128), nullable=False)
    is_admin = db.Column(db.Boolean, default=False)
    # Rol del usuario: 'free', 'pago1', 'pago2', 'admin'
    role = db.Column(db.String(20), default='free')
    # Fecha de expiración de la suscripción (si aplica). UTC.
    subscription_expires = db.Column(db.DateTime, nullable=True)
    # Identificación y datos personales (añadidos para 3FN y requisitos legales)
    __table_args__ = (
        db.UniqueConstraint('tipo_documento', 'numero_documento', name='uq_user_document'),
    )
    tipo_documento = db.Column(db.String(30), nullable=True)
    numero_documento = db.Column(db.String(60), nullable=True)
    primer_nombre = db.Column(db.String(80), nullable=False)
    segundo_nombre = db.Column(db.String(80), nullable=True)
    primer_apellido = db.Column(db.String(80), nullable=False)
    segundo_apellido = db.Column(db.String(80), nullable=True)
    # Contacto y metadatos
    telefono = db.Column(db.String(30), nullable=True)
    direccion = db.Column(db.String(256), nullable=True)
    fecha_nacimiento = db.Column(db.Date, nullable=True)
    created_at = db.Column(db.DateTime, server_default=db.func.now())
    updated_at = db.Column(db.DateTime, server_default=db.func.now(), onupdate=db.func.now())

    def __repr__(self):
        return f'<User {self.email}>'

    def set_password(self, password):
        """Hashea y almacena la contraseña provista.

        Nota: utiliza `werkzeug.security.generate_password_hash`.
        """
        self.password = generate_password_hash(password)

    def check_password(self, password):
        """Comprueba que `password` coincida con el hash almacenado.

        Devuelve True si coinciden, False en caso contrario.
        """
        return check_password_hash(self.password, password)

    def save(self):
        """Guarda (insert/commit) el objeto en la base de datos.

        Añade el objeto a la sesión si es nuevo y realiza commit. No
        devuelve valor; si falla lanzará excepción del ORM.
        """
        if not self.id:
            db.session.add(self)
        db.session.commit()

    @staticmethod
    def get_by_id(id):
        """Retorna el usuario por su id (o None si no existe)."""
        return User.query.get(id)

    @staticmethod
    def get_by_email(email):
        """Retorna el usuario cuyo correo coincide con `email` o None."""
        return User.query.filter_by(email=email).first()


class Consulta(db.Model):
    __tablename__ = 'consultas'
    """Modelo para consultas de inversión guardadas por usuarios.

    `query_text` almacena el JSON de la solicitud y `summary` guarda
    metadatos/estimaciones precalculadas como JSON en texto.
    """
    id = db.Column(db.BigInteger, primary_key=True)
    user_id = db.Column(db.BigInteger, db.ForeignKey('blog_user.id'), nullable=False)
    titulo = db.Column(db.String(200), nullable=False)
    descripcion = db.Column(db.Text, nullable=True)
    # 'query' es un nombre reservado a nivel de modelo por Flask-SQLAlchemy (Consulta.query existe como Query property)
    # por eso renombramos la columna a 'query_text' para evitar colisiones.
    query_text = db.Column(db.Text, nullable=True)
    # resumen o metadatos calculados (JSON string) con estimaciones de producción, se guarda por comodidad
    summary = db.Column(db.Text, nullable=True)
    created_at = db.Column(db.DateTime, server_default=db.func.now())
    updated_at = db.Column(db.DateTime, server_default=db.func.now(), onupdate=db.func.now())

    user = db.relationship('User', backref=db.backref('consultas', lazy='dynamic'))

    def save(self):
        """Inserta o actualiza la consulta en la base de datos."""
        if not self.id:
            db.session.add(self)
        db.session.commit()

    def delete(self):
        """Elimina esta instancia de la base de datos y hace commit."""
        db.session.delete(self)
        db.session.commit()

    def __repr__(self):
        return f'<Consulta {self.id} - {self.titulo}>'

    # Campos atómicos para normalización (3NF)
    raza = db.Column(db.String(80), nullable=True)
    raza_id = db.Column(db.BigInteger, db.ForeignKey('razas.id'), nullable=True)
    num_vacas = db.Column(db.Integer, nullable=True)
    litros_por_vaca = db.Column(db.Float, nullable=True)

    raza_rel = db.relationship('Raza', backref=db.backref('consultas', lazy='dynamic'))


class ConsultaQuery(db.Model):
    __tablename__ = 'consulta_queries'
    id = db.Column(db.BigInteger, primary_key=True)
    consulta_id = db.Column(db.BigInteger, db.ForeignKey('consultas.id'), nullable=False)
    query_text = db.Column(db.Text, nullable=True)

    consulta = db.relationship('Consulta', backref=db.backref('queries', lazy='dynamic'))

    def save(self):
        if not self.id:
            db.session.add(self)
        db.session.commit()


class ConsultaSummary(db.Model):
    __tablename__ = 'consulta_summaries'
    id = db.Column(db.BigInteger, primary_key=True)
    consulta_id = db.Column(db.BigInteger, db.ForeignKey('consultas.id'), nullable=False)
    summary = db.Column(db.Text, nullable=True)

    consulta = db.relationship('Consulta', backref=db.backref('summaries', lazy='dynamic'))

    def save(self):
        if not self.id:
            db.session.add(self)
        db.session.commit()


class ConsultaPrecio(db.Model):
    __tablename__ = 'consulta_precios'
    id = db.Column(db.BigInteger, primary_key=True)
    consulta_id = db.Column(db.BigInteger, db.ForeignKey('consultas.id'), nullable=False)
    departamento = db.Column(db.String(120), nullable=True)
    departamento_id = db.Column(db.BigInteger, db.ForeignKey('departamentos.id'), nullable=True)
    precio = db.Column(db.Float, nullable=True)

    consulta = db.relationship('Consulta', backref=db.backref('precios', lazy='dynamic'))
    departamento_rel = db.relationship('Departamento', backref=db.backref('precios', lazy='dynamic'))

    def save(self):
        if not self.id:
            db.session.add(self)
        db.session.commit()