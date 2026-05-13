"""Ejecuta apply_constraints.sql contra la BD MySQL local (XAMPP).

Uso:
  python apply_constraints.py

Configurable via variables abajo. Por defecto asume `root` sin contraseña
en `localhost:3306` y base `del_campo_al_algoritomo`.
"""
import pymysql
from pymysql.cursors import DictCursor
import os

SQL_FILE = os.path.join(os.path.dirname(__file__), 'apply_constraints.sql')
HOST = os.environ.get('MYSQL_HOST', '127.0.0.1')
PORT = int(os.environ.get('MYSQL_PORT', '3306'))
USER = os.environ.get('MYSQL_USER', 'root')
PASSWORD = os.environ.get('MYSQL_PASSWORD', '')
DB = os.environ.get('MYSQL_DB', 'del_campo_al_algoritomo')

def main():
    with open(SQL_FILE, encoding='utf-8') as f:
        sql = f.read()

    con = pymysql.connect(host=HOST, user=USER, password=PASSWORD, port=PORT, cursorclass=DictCursor)
    cur = con.cursor()
    try:
        cur.execute(f"USE {DB}")
        # split statements by semicolon; execute sequentially
        for stmt in [s.strip() for s in sql.split(';') if s.strip()]:
            print('Ejecutando:', stmt[:120])
            try:
                cur.execute(stmt)
            except Exception as e:
                print('  ERROR:', e)
        con.commit()
        print('Listo. Revisa que no haya errores arriba.')
    finally:
        cur.close()
        con.close()

if __name__ == '__main__':
    main()
