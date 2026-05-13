from app import app
from database import db

with app.app_context():
    for t in ('consulta_queries','consulta_summaries','consulta_precios'):
        try:
            res = db.engine.execute(f"SELECT COUNT(*) FROM {t}").fetchone()
            print(f"{t}: {res[0]}")
        except Exception as e:
            print(f"{t}: ERROR ->", e)
