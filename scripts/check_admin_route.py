import sys
import os
ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from app import app

with app.test_client() as c:
    # login
    r = c.post('/login', data={'usuario':'admin@example.com','contrasena':'1234'}, follow_redirects=True)
    print('Login status:', r.status_code)
    # request admin users
    r2 = c.get('/admin/users')
    print('Admin users status:', r2.status_code)
    print('Length:', len(r2.data))
    print('Snippet:\n', r2.data.decode('utf-8')[:2000])
