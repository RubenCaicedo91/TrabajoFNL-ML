import sys, os
ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from app import app
from database import db

DEPARTAMENTOS = [
    'Amazonas', 'Antioquia', 'Arauca', 'Atlántico', 'Bolívar', 'Boyacá', 'Caldas', 'Caquetá',
    'Casanare', 'Cauca', 'Cesar', 'Chocó', 'Córdoba', 'Cundinamarca', 'Guainía', 'Guaviare',
    'Huila', 'La Guajira', 'Magdalena', 'Meta', 'Nariño', 'Norte de Santander', 'Putumayo',
    'Quindío', 'Risaralda', 'San Andrés y Providencia', 'Santander', 'Sucre', 'Tolima',
    'Valle del Cauca', 'Vaupés', 'Vichada', 'Bogotá D.C.'
]

with app.app_context():
    try:
        # Eliminar todas las filas (no eliminar la tabla)
        db.engine.execute('DELETE FROM departamentos')
    except Exception as e:
        print('ERROR borrando departamentos:', e)

    inserted = 0
    for name in DEPARTAMENTOS:
        try:
            db.engine.execute('INSERT INTO departamentos (name) VALUES (%s)', (name.strip(),))
            inserted += 1
        except Exception as e:
            print('ERROR insertando', name, e)

    try:
        db.session.commit()
    except Exception as e:
        print('ERROR commit:', e)

    total = db.engine.execute('SELECT COUNT(*) FROM departamentos').fetchone()[0]
    print('Departamentos reinsertados:', inserted)
    print('Total departamentos en la tabla:', total)
