import sys, os
# Asegurar que el root del proyecto esté en sys.path cuando se ejecuta desde /scripts
ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from app import app
from database import db

# Lista de departamentos de Colombia (incluye Bogotá D.C. y San Andrés y Providencia)
DEPARTAMENTOS = [
    'Amazonas', 'Antioquia', 'Arauca', 'Atlántico', 'Bolívar', 'Boyacá', 'Caldas', 'Caquetá',
    'Casanare', 'Cauca', 'Cesar', 'Chocó', 'Córdoba', 'Cundinamarca', 'Guainía', 'Guaviare',
    'Huila', 'La Guajira', 'Magdalena', 'Meta', 'Nariño', 'Norte de Santander', 'Putumayo',
    'Quindío', 'Risaralda', 'San Andrés y Providencia', 'Santander', 'Sucre', 'Tolima',
    'Valle del Cauca', 'Vaupés', 'Vichada', 'Bogotá D.C.'
]

with app.app_context():
    inserted = 0
    for name in DEPARTAMENTOS:
        try:
            # normalizar
            key = name.strip()
            row = db.engine.execute('SELECT id FROM departamentos WHERE name = %s', (key,)).fetchone()
            if row:
                continue
            db.engine.execute('INSERT INTO departamentos (name) VALUES (%s)', (key,))
            inserted += 1
        except Exception as e:
            print('ERROR insertando', name, e)
    try:
        db.session.commit()
    except Exception as e:
        print('ERROR commit:', e)

    total = db.engine.execute('SELECT COUNT(*) FROM departamentos').fetchone()[0]
    print('Departamentos insertados (nuevos):', inserted)
    print('Total departamentos en la tabla:', total)
