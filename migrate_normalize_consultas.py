"""Script para migrar datos existentes: copiar `query_text` y `summary`
desde `consultas` hacia las nuevas tablas `consulta_queries` y
`consulta_summaries`.

Uso:
  python migrate_normalize_consultas.py
"""
from database import db
from models import Consulta, ConsultaQuery, ConsultaSummary
from app import app
import json

def migrate():
    with app.app_context():
        # Asegurar que las columnas atómicas existan en `consultas` (si la tabla vino de migración previa)
        try:
            db.engine.execute("ALTER TABLE consultas ADD COLUMN IF NOT EXISTS raza VARCHAR(80) NULL")
            db.engine.execute("ALTER TABLE consultas ADD COLUMN IF NOT EXISTS num_vacas INT NULL")
            db.engine.execute("ALTER TABLE consultas ADD COLUMN IF NOT EXISTS litros_por_vaca DOUBLE NULL")
        except Exception as e:
            # algunos servidores MySQL antiguos no soportan IF NOT EXISTS en ADD COLUMN
            # intentamos agregar ignorando errores si ya existen
            try:
                db.engine.execute("ALTER TABLE consultas ADD COLUMN raza VARCHAR(80) NULL")
            except Exception:
                pass
            try:
                db.engine.execute("ALTER TABLE consultas ADD COLUMN num_vacas INT NULL")
            except Exception:
                pass
            try:
                db.engine.execute("ALTER TABLE consultas ADD COLUMN litros_por_vaca DOUBLE NULL")
            except Exception:
                pass

        # Crear tablas normalizadas si no existen
        from models import ConsultaQuery, ConsultaSummary, ConsultaPrecio
        try:
            ConsultaQuery.__table__.create(bind=db.engine, checkfirst=True)
            ConsultaSummary.__table__.create(bind=db.engine, checkfirst=True)
            ConsultaPrecio.__table__.create(bind=db.engine, checkfirst=True)
        except Exception as e:
            print('Advertencia creando tablas normalizadas:', e)

        allc = Consulta.query.all()
        for c in allc:
            try:
                # intentar parsear query_text JSON y poblar tablas normalizadas
                if getattr(c, 'query_text', None):
                    try:
                        payload = json.loads(c.query_text)
                    except Exception:
                        payload = None
                    if payload is not None:
                        cq = ConsultaQuery(consulta_id=c.id, query_text=c.query_text)
                        cq.save()
                        # extraer campos atómicos
                        raza = payload.get('raza') or payload.get('Raza') or None
                        nv = payload.get('num_vacas') or payload.get('numVacas') or None
                        try:
                            nv = int(nv) if nv is not None else None
                        except Exception:
                            nv = None
                        litros_vaca = payload.get('litros_por_vaca') or payload.get('litrosPorVaca') or None
                        try:
                            litros_vaca = float(litros_vaca) if litros_vaca is not None else None
                        except Exception:
                            litros_vaca = None
                        # asignar a la consulta existente
                        c.raza = raza
                        c.num_vacas = nv
                        c.litros_por_vaca = litros_vaca
                        db.session.add(c)
                        # precios por departamento
                        precios = payload.get('precios_departamentos') or payload.get('precios') or []
                        from models import ConsultaPrecio
                        if isinstance(precios, list):
                            for p in precios:
                                dept = p.get('departamento') or ''
                                precio_val = None
                                try:
                                    precio_val = float(p.get('precio')) if p.get('precio') is not None else None
                                except Exception:
                                    precio_val = None
                                cp = ConsultaPrecio(consulta_id=c.id, departamento=dept, precio=precio_val)
                                cp.save()
                if getattr(c, 'summary', None):
                    cs = ConsultaSummary(consulta_id=c.id, summary=c.summary)
                    cs.save()
            except Exception as e:
                print('ERROR migrando consulta', c.id, e)
        # commit once after loop
        try:
            db.session.commit()
        except Exception as e:
            print('ERROR haciendo commit final:', e)

if __name__ == '__main__':
    migrate()
