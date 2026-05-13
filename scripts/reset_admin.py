import sys
import os
# Asegurar que el directorio raíz del proyecto esté en sys.path
ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from app import app
from database import db
from models import User

with app.app_context():
    u = User.get_by_email('admin@example.com')
    if u:
        u.set_password('1234')
        u.is_admin = True
        db.session.commit()
        print('Admin updated:', u.id)
    else:
        admin = User(name='Admin', email='admin@example.com')
        admin.set_password('1234')
        admin.is_admin = True
        db.session.add(admin)
        db.session.commit()
        print('Admin created:', admin.id)
