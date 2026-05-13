"""Script auxiliar para crear el usuario administrador inicial.

Este script crea un usuario con email `admin@example.com` si no existe.
Se ejecuta de forma segura bajo el guardia `__main__` para que importar
el módulo no realice efectos secundarios.
"""

from app import app
from database import db
from models import User


def crear_admin():
    """Crear el usuario administrador si no existe.

    Nota: la contraseña por defecto aquí es un placeholder; cambiarla
    tras la creación en un entorno real.
    """
    with app.app_context():
        existing = User.query.filter_by(email='admin@example.com').first()
        if existing:
            print('ℹ️ Usuario administrador ya existe con ID:', existing.id)
        else:
            admin = User(name='Admin', email='admin@example.com')
            admin.set_password('1234')
            db.session.add(admin)
            db.session.commit()
            print("✅ Usuario administrador creado con ID:", admin.id)


if __name__ == '__main__':
    crear_admin()