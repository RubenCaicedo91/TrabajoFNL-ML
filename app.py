"""Aplicación Flask principal.

Este módulo inicializa la app Flask, configura la base de datos, el
login manager y registra los blueprints de las distintas partes de la
aplicación (acopio, precio, inversión, perfil).

Contiene además rutas públicas simples como `/`, `/login`, `/register`
y utilidades de sesión.
"""

from flask import Flask, render_template, request, redirect, url_for, session, flash, jsonify
from pathlib import Path
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager, login_user, logout_user, login_required, current_user
from datetime import datetime, timedelta
import pytz

from inversion import inversion_bp
from acopio import acopio_bp
from precio import precio_bp
from perfil import perfil_bp

import pandas as pd
import io, base64
import matplotlib.pyplot as plt
import os


# Inicialización
BASE_DIR = Path(__file__).resolve().parent
app = Flask(__name__, template_folder=str(BASE_DIR / 'templates'), static_folder=str(BASE_DIR / 'static'))
app.secret_key = 'clave_segura_para_sesion'
# Configurar expiración de sesión por inactividad (30 minutos)
app.permanent_session_lifetime = timedelta(minutes=30)

# Configuración de base de datos: usar MySQL exclusivamente.
# - Si existe la variable de entorno `MYSQL_DATABASE_URL` se usa tal cual.
# - Si no existe, por conveniencia se conecta a XAMPP local por defecto
#   con la base `del_campo_al_algoritomo` y usuario `root` sin contraseña.
import os
mysql_url = os.environ.get('MYSQL_DATABASE_URL')
if mysql_url:
    app.config['SQLALCHEMY_DATABASE_URI'] = mysql_url
else:
    # conexión por defecto a XAMPP en localhost
    app.config['SQLALCHEMY_DATABASE_URI'] = (
        'mysql+pymysql://root:@localhost:3306/del_campo_al_algoritomo?charset=utf8mb4'
    )

app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

# Filtro Jinja para formatear fechas en hora local de Colombia (America/Bogota)
def format_colombia(value, fmt="%Y-%m-%d %H:%M"):
    """Convierte un datetime (naive o timezone-aware) a la zona America/Bogota y lo formatea.

    - Si el valor es None devuelve cadena vacía.
    - Si el datetime es naive se asume que está en UTC.
    - Usa pytz para asegurar compatibilidad con las dependencias del proyecto.
    """
    if not value:
        return ''
    try:
        tz_target = pytz.timezone('America/Bogota')
        # Si es naive, asumir UTC
        if value.tzinfo is None or value.tzinfo.utcoffset(value) is None:
            value = pytz.UTC.localize(value)
        local = value.astimezone(tz_target)
        return local.strftime(fmt)
    except Exception:
        try:
            # fallback simple
            return value.strftime(fmt)
        except Exception:
            return str(value)

# Registrar filtro en Jinja
app.jinja_env.filters['format_colombia'] = format_colombia

# Inicializar base de datos usando la instancia compartida
from database import db
db.init_app(app)

# Importar modelo después de inicializar db (evita import circular)
with app.app_context():
    from models import User

# Configurar Flask-Login
login_manager = LoginManager(app)
login_manager.login_view = 'login'

@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))

# Página de inicio pública
@app.route('/')
def inicio():
    return render_template('inicio.html')

# Login CORREGIDO - usuario = email
@app.route('/login', methods=['GET', 'POST'])
def login():
    """Manejador de autenticación.

    El formulario envía 'usuario' (email) y 'contrasena'. Si la
    autenticación es correcta se inicia sesión y se refresca
    `session['last_activity']`.
    """
    import traceback
    error = None
    if request.method == 'POST':
        try:
            # El campo "usuario" en el formulario es el correo electrónico
            email = request.form['usuario']
            contrasena = request.form['contrasena']

            # Buscar usuario por email (correo electrónico)
            user = User.query.filter_by(email=email).first()
            
            if user and user.check_password(contrasena):
                login_user(user)
                session['usuario'] = user.name
                # Marcar sesión como permanente y registrar última actividad
                session.permanent = True
                session['last_activity'] = datetime.utcnow().timestamp()
                # Mostrar mensaje de bienvenida personalizado con el nombre del usuario
                flash(f'¡Bienvenido/a, {user.name}! Has iniciado sesión correctamente.', 'success')
                # Redirigir al inicio en lugar de al menú principal
                return redirect(url_for('inicio'))
            else:
                error = 'Correo electrónico o contraseña incorrectos'
        except Exception as e:
            tb = traceback.format_exc()
            try:
                log_dir = os.path.join(Path(__file__).resolve().parent, 'instance')
                os.makedirs(log_dir, exist_ok=True)
                with open(os.path.join(log_dir, 'login_error.log'), 'a', encoding='utf-8') as f:
                    f.write('\n--- ERROR en /login ---\n')
                    f.write(tb)
            except Exception:
                pass
            # En modo debug devolver traceback para ayuda local
            if app.debug:
                return f"<pre>{tb}</pre>"
            error = 'Ocurrió un error al intentar iniciar sesión. Revisa el log en instance/login_error.log.'
    
    return render_template('login.html', error=error)

@app.route('/register', methods=['GET', 'POST'])
def register():
    """Registrar un nuevo usuario.

    POST: valida que el correo no esté registrado, crea la instancia
    `User`, guarda la contraseña hasheada y redirige al login.
    GET: renderiza el formulario de registro.
    """
    if request.method == 'POST':
        # Nombres y apellidos separados
        primer_nombre = request.form.get('primer_nombre')
        segundo_nombre = request.form.get('segundo_nombre')
        primer_apellido = request.form.get('primer_apellido')
        segundo_apellido = request.form.get('segundo_apellido')
        # Construir `name` para compatibilidad con otras partes del sistema
        name = f"{primer_nombre} {' ' + segundo_nombre if segundo_nombre else ''} {primer_apellido} {' ' + segundo_apellido if segundo_apellido else ''}".strip()
        email = request.form['email']
        password = request.form['password']
        plan = request.form.get('plan', 'free')
        payment_method = request.form.get('payment_method', 'none')
        tipo_documento = request.form.get('tipo_documento')
        numero_documento = request.form.get('numero_documento')
        telefono = request.form.get('telefono')

        # Verificar si ya existe el usuario por email
        existing_user = User.query.filter_by(email=email).first()
        if existing_user:
            flash('El correo electrónico ya está registrado', 'danger')
            return redirect(url_for('register'))

        new_user = User(name=name, email=email)
        # Asignar campos adicionales de identificación
        new_user.primer_nombre = primer_nombre
        new_user.segundo_nombre = segundo_nombre
        new_user.primer_apellido = primer_apellido
        new_user.segundo_apellido = segundo_apellido
        new_user.tipo_documento = tipo_documento
        new_user.numero_documento = numero_documento
        new_user.telefono = telefono
        new_user.set_password(password)

        # Si seleccionó un plan de pago, simulamos el cobro y asignamos rol temporal
        if plan in ('pago1', 'pago2'):
            # simulación: aceptar cualquier método y dar suscripción por 30 días
            try:
                new_user.role = 'pago1' if plan == 'pago1' else 'pago2'
                new_user.subscription_expires = datetime.utcnow() + timedelta(days=30)
            except Exception:
                # si falla asignación, dejar en free
                new_user.role = 'free'
                new_user.subscription_expires = None
        else:
            new_user.role = 'free'
            new_user.subscription_expires = None

        db.session.add(new_user)
        db.session.commit()
        flash('Usuario registrado correctamente. Por favor inicie sesión.', 'success')
        return redirect(url_for('login'))

    return render_template('register.html')

# Logout
@app.route('/logout')
@login_required
def logout():
    """Cerrar la sesión del usuario actual.

    Limpia las claves de sesión y redirige al inicio mostrando un flash
    informativo.
    """
    logout_user()
    session.pop('usuario', None)
    session.pop('last_activity', None)
    flash('Has cerrado sesión correctamente.', 'info')
    return redirect(url_for('inicio'))


# Endpoint opcional para extender la sesión desde cliente (invocado por JS cuando hay actividad)
@app.route('/keepalive', methods=['POST'])
@login_required
def keepalive():
    """Extiende la sesión del usuario (ping desde el cliente).

    Este endpoint es invocado por JavaScript de la UI para actualizar
    `session['last_activity']` y evitar expiraciones mientras el
    usuario está activo. Devuelve 204 en éxito.
    """
    try:
        session['last_activity'] = datetime.utcnow().timestamp()
        return ('', 204)
    except Exception:
        return jsonify({'ok': False}), 500


@app.before_request
def session_timeout_handler():
    # No aplicamos para endpoints estáticos o si no hay sesión
    try:
        if 'usuario' not in session and not current_user.is_authenticated:
            return None
    except Exception:
        # en caso de fallo al leer current_user, no cortar el request
        return None

    # Obtener última actividad
    last = session.get('last_activity')
    now_ts = datetime.utcnow().timestamp()
    if last:
        elapsed = now_ts - float(last)
        # 1800 segundos = 30 minutos
        if elapsed > 1800:
            try:
                logout_user()
            except Exception:
                pass
            session.clear()
            flash('Tu sesión expiró por inactividad. Por favor inicia sesión de nuevo.', 'warning')
            return redirect(url_for('login'))

    # Actualizar last_activity para cada request válida
    session['last_activity'] = now_ts
    # Verificar expiración de suscripción y degradar rol si corresponde
    try:
        if current_user.is_authenticated:
            expires = getattr(current_user, 'subscription_expires', None)
            if expires is not None:
                # Si expiró, degradar a 'free'
                try:
                    if expires and expires < datetime.utcnow():
                        current_user.role = 'free'
                        current_user.subscription_expires = None
                        db.session.commit()
                        flash('Tu suscripción expiró y tu cuenta fue degradada a Free.', 'info')
                except Exception:
                    pass
    except Exception:
        pass

# Menú principal (solo con sesión activa)
@app.route('/menu')
@login_required
def menu():
    # Redirigimos al inicio ya que la plantilla 'menu.html' se ha eliminado
    return redirect(url_for('inicio'))

# datos proyecto
@app.route('/index1')
def index1():
    return render_template('index1.html')

@app.route('/index2')
def index2():
    return render_template('index2.html')

# Crear la base de datos si no existe
with app.app_context():
    # Crear tablas en MySQL si no existen, excepto cuando se ejecutan scripts
    # de mantenimiento/migración que establecen la variable SKIP_CREATE_ALL=1
    if os.environ.get('SKIP_CREATE_ALL') != '1':
        db.create_all()

# Política de tratamiento de datos
@app.route("/politica-datos")
def politica_datos():
    return render_template("politica_datos.html")
#===================================================================================




# =======================
# REGISTRO DE BLUEPRINTS
# =======================

# ✅ Registro de blueprints
app.register_blueprint(acopio_bp)
app.register_blueprint(precio_bp)
app.register_blueprint(inversion_bp)
app.register_blueprint(perfil_bp)

# ✅ Ejecución de la app
if __name__ == '__main__':
    app.run(debug=True, port=5000)