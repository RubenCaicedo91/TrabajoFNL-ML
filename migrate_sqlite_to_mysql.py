"""Script sencillo para migrar tablas y datos de SQLite a MySQL.

Usa pandas + SQLAlchemy. No preserva todas las constraints avanzadas
pero copia estructura básica y datos, suficiente para inspección y
consultas.

Ejemplo de uso:
  pip install pandas sqlalchemy pymysql
  python migrate_sqlite_to_mysql.py --sqlite "instance/usuarios.db" \
      --mysql "mysql+pymysql://user:pass@host:3306/dbname?charset=utf8mb4"

"""
import argparse
import os
import sys
from sqlalchemy import create_engine, inspect
import pandas as pd


def main(sqlite_path, mysql_uri, if_exists='replace'):
    # Normalizar ruta sqlite
    if not os.path.isabs(sqlite_path):
        sqlite_path = os.path.abspath(sqlite_path)
    sqlite_uri = f"sqlite:///{sqlite_path}"

    print(f"Conectando a SQLite: {sqlite_uri}")
    src_engine = create_engine(sqlite_uri)
    print(f"Conectando a MySQL: {mysql_uri}")
    dst_engine = create_engine(mysql_uri)

    inspector = inspect(src_engine)
    tables = inspector.get_table_names()
    if not tables:
        print("No se encontraron tablas en la base de datos SQLite.")
        return

    for tbl in tables:
        print(f"Copiando tabla: {tbl}")
        try:
            # Leer datos desde SQLite
            df = pd.read_sql_query(f'SELECT * FROM "{tbl}"', src_engine)
            # Escribir en MySQL
            df.to_sql(tbl, dst_engine, if_exists=if_exists, index=False)
            print(f"  -> {len(df)} filas copiadas")
        except Exception as e:
            print(f"  ERROR copiando {tbl}: {e}")

    print("Migración completada. Verifica índices y constraints en MySQL.")


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='Migrar SQLite a MySQL (básico)')
    parser.add_argument('--sqlite', required=True, help='Ruta al archivo SQLite (ej: instance/usuarios.db)')
    parser.add_argument('--mysql', required=True, help='URI SQLAlchemy para MySQL (ej: mysql+pymysql://user:pass@host/db)')
    parser.add_argument('--if-exists', default='replace', choices=['fail', 'replace', 'append'], help='Comportamiento en destino')
    args = parser.parse_args()

    try:
        main(args.sqlite, args.mysql, if_exists=args.if_exists)
    except Exception as e:
        print(f"Error durante la migración: {e}")
        sys.exit(1)
