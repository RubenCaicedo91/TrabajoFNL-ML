"""Inicialización del objeto `db` de SQLAlchemy.

Este módulo expone la instancia `db` sin vincularla a la aplicación.
Permite realizar la importación circular controlada (importar `db` en
modelos antes de inicializar la app). La aplicación principal debe
ejecutar `db.init_app(app)` al arrancar.
"""

from flask_sqlalchemy import SQLAlchemy

# create the SQLAlchemy object without binding to app yet
db = SQLAlchemy()
