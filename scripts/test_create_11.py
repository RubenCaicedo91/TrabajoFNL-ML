"""Prueba funcional que crea un usuario de test y publica 11 consultas.

Este script está pensado para ejecución manual en entorno de desarrollo
para validar la lógica de guardado y la política FIFO de `Consulta`.
No debe importarse desde la aplicación (ejecutar como script
principal)."""

import sys
import os
import json
import time


def main():
    sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
    from app import app
    from models import User, Consulta
    from database import db

    TEST_EMAIL = 'test@example.com'
    TEST_PASS = 'testpass'

    with app.app_context():
        user = User.get_by_email(TEST_EMAIL)
        if not user:
            user = User(name='Test User', email=TEST_EMAIL)
            user.set_password(TEST_PASS)
            db.session.add(user)
            db.session.commit()
            print('Created test user', TEST_EMAIL)
        else:
            print('Test user exists:', TEST_EMAIL)

        client = app.test_client()
        # login
        rv = client.post('/login', data={'usuario': TEST_EMAIL, 'contrasena': TEST_PASS}, follow_redirects=True)
        print('Login status code:', rv.status_code)

        # create 11 consultas
        # limpiar consultas previas del usuario de prueba (si las hay)
        try:
            Consulta.query.filter_by(user_id=user.id).delete()
            db.session.commit()
            print('Cleared existing consultas for test user')
        except Exception as e:
            print('Warning clearing consultas:', e)

        for i in range(11):
            payload = {
                'raza': 'Holstein',
                'num_vacas': i + 1,
                'departamentos': ['ANTIOQUIA', 'BOGOTÁ DC'],
                'precios_departamentos': [
                    {'departamento': 'ANTIOQUIA', 'precio': 1200 + i * 10},
                    {'departamento': 'BOGOTÁ DC', 'precio': 1250 + i * 10}
                ]
            }
            data = {
                'titulo': f'Test consulta {i+1}',
                'descripcion': 'Prueba automatizada',
                'query': json.dumps(payload, ensure_ascii=False)
            }
            rv = client.post('/mis-consultas/guardar', data=data, follow_redirects=True)
            print(f'Posted consulta {i+1} -> status {rv.status_code}')
            time.sleep(0.1)

        # show final count and list
        qs = Consulta.query.filter_by(user_id=user.id).order_by(Consulta.created_at.asc()).all()
        print('Total consultas for user after inserts:', len(qs))
        for c in qs:
            print(c.id, c.titulo, c.created_at, 'summary:', (c.summary[:80] + '...') if c.summary else None)


if __name__ == '__main__':
    main()
