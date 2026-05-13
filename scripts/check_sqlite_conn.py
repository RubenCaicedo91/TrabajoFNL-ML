"""Comprobador rápido de conexión SQLite usado en desarrollo.

Este script intenta abrir la base de datos SQLite localizada en
`instance/usuarios.db` y listar las tablas. Está diseñado como
herramienta de diagnóstico para el desarrollador — no debe importarse
desde otros módulos ya que ejecuta efectos secundarios (imprime en
consola). Ejecutar directamente con `python scripts/check_sqlite_conn.py`.
"""

import sqlite3
import os


def main():
    """Ejecuta la comprobación de conexión y muestra tablas encontradas."""
    p = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'instance', 'usuarios.db'))
    print('path:', p)
    print('exists:', os.path.exists(p))
    try:
        conn = sqlite3.connect(p)
        cur = conn.cursor()
        cur.execute("SELECT name FROM sqlite_master WHERE type='table';")
        tables = cur.fetchall()
        print('tables:', tables)
        conn.close()
        print('sqlite open: OK')
    except Exception as e:
        print('error opening sqlite:', repr(e))


if __name__ == '__main__':
    main()
