"""Migra la BD para convertir cadenas repetidas en tablas lookup (3FN).

Pasos:
 - crea tablas `razas` y `departamentos` si no existen
 - añade columnas FK `raza_id` en `consultas` y `departamento_id` en `consulta_precios` si faltan
 - puebla `razas` con valores distintos de `consultas.raza`
 - puebla `departamentos` con valores distintos de `consulta_precios.departamento`
 - actualiza filas para apuntar a los nuevos IDs (sin borrar columnas string legacy)

Ejecutar con MySQL activo. Evita que `app.py` cree tablas automáticas estableciendo
`SKIP_CREATE_ALL=1` en el entorno.
"""
from app import app
from database import db
from models import Raza, Departamento, Consulta, ConsultaPrecio

with app.app_context():
    # Crear tablas lookup
    try:
        Raza.__table__.create(bind=db.engine, checkfirst=True)
        Departamento.__table__.create(bind=db.engine, checkfirst=True)
    except Exception as e:
        print('Advertencia creando tablas lookup:', e)

    # Añadir columnas FK si faltan
    try:
        db.engine.execute("ALTER TABLE consultas ADD COLUMN IF NOT EXISTS raza_id BIGINT NULL")
        db.engine.execute("ALTER TABLE consulta_precios ADD COLUMN IF NOT EXISTS departamento_id BIGINT NULL")
    except Exception:
        # fallback para MySQL que no soporte IF NOT EXISTS
        try:
            db.engine.execute("ALTER TABLE consultas ADD COLUMN raza_id BIGINT NULL")
        except Exception:
            pass
        try:
            db.engine.execute("ALTER TABLE consulta_precios ADD COLUMN departamento_id BIGINT NULL")
        except Exception:
            pass

    # Poblar `razas` desde valores existentes
    distinct_razas = db.engine.execute("SELECT DISTINCT raza FROM consultas WHERE raza IS NOT NULL AND raza != ''").fetchall()
    inserted_razas = {}
    for (r,) in distinct_razas:
        if not r:
            continue
        # normalizar espacio y mayúsculas mínimamente
        name = r.strip()
        exists = db.engine.execute("SELECT id FROM razas WHERE name = %s", (name,)).fetchone()
        if exists:
            inserted_razas[name] = exists[0]
        else:
            res = db.engine.execute("INSERT INTO razas (name) VALUES (%s)", (name,))
            # obtener id recién insertado
            idrow = db.engine.execute("SELECT id FROM razas WHERE name = %s", (name,)).fetchone()
            inserted_razas[name] = idrow[0]

    # Poblar `departamentos` desde `consulta_precios.departamento`
    distinct_depts = db.engine.execute("SELECT DISTINCT departamento FROM consulta_precios WHERE departamento IS NOT NULL AND departamento != ''").fetchall()
    inserted_depts = {}
    for (d,) in distinct_depts:
        if not d:
            continue
        name = d.strip()
        exists = db.engine.execute("SELECT id FROM departamentos WHERE name = %s", (name,)).fetchone()
        if exists:
            inserted_depts[name] = exists[0]
        else:
            db.engine.execute("INSERT INTO departamentos (name) VALUES (%s)", (name,))
            idrow = db.engine.execute("SELECT id FROM departamentos WHERE name = %s", (name,)).fetchone()
            inserted_depts[name] = idrow[0]

    # Actualizar consultas: asignar raza_id según el valor string
    for name, rid in inserted_razas.items():
        try:
            db.engine.execute("UPDATE consultas SET raza_id = %s WHERE raza = %s", (rid, name))
        except Exception as e:
            print('ERROR actualizando consultas para raza', name, e)

    # Actualizar consulta_precios: asignar departamento_id según departamento string
    for name, did in inserted_depts.items():
        try:
            db.engine.execute("UPDATE consulta_precios SET departamento_id = %s WHERE departamento = %s", (did, name))
        except Exception as e:
            print('ERROR actualizando consulta_precios para dept', name, e)

    try:
        db.session.commit()
    except Exception as e:
        print('ERROR commit final en migrate_to_3fn:', e)

    print('Normalización parcial completada. Razas creadas:', len(inserted_razas), 'Departamentos creados:', len(inserted_depts))
