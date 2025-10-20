from flask import Flask, render_template, request, redirect, url_for, flash, jsonify, session
from flask_login import LoginManager, login_user, logout_user, login_required, current_user
from werkzeug.security import generate_password_hash, check_password_hash
import os
import json
from datetime import datetime, timedelta
import random
import math

# Importaciones locales
from config import Config
from database import db, User, ProductionData, Prediction, Region

app = Flask(__name__)
app.config.from_object(Config)

# Inicializar extensiones
db.init_app(app)

login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'login'

@login_manager.user_loader
def load_user(user_id):
    try:
        return User.query.get(int(user_id))
    except:
        return None

# Rutas principales
@app.route('/')
def index():
    # Página principal con información del proyecto (sin login requerido)
    return render_template('index.html')

@app.route('/dashboard')
@login_required
def dashboard():
    # Dashboard con estadísticas (requiere login)
    production_data = get_mock_production_data()
    department_data = get_mock_department_data()
    predictions_data = get_mock_predictions_data()
    
    stats = [
        {'title': 'Contenidos Activos', 'value': '32', 'change': '+2', 'icon': 'map-pin'},
        {'title': 'Usuarios Registrados', 'value': '1,247', 'change': '+12%', 'icon': 'users'},
        {'title': 'Producción Mensual', 'value': '168,000 L', 'change': '+5.2%', 'icon': 'trending-up'},
        {'title': 'Precio Promedio', 'value': '$935/L', 'change': '+2.1%', 'icon': 'trending-up'}
    ]
    
    return render_template('dashboard.html', 
                         user=current_user,
                         production_data=production_data,
                         department_data=department_data,
                         predictions_data=predictions_data,
                         stats=stats)

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        email = request.form.get('email')
        password = request.form.get('password')
        
        try:
            user = User.query.filter_by(email=email).first()
            
            if user and user.check_password(password):
                login_user(user)
                flash('¡Inicio de sesión exitoso!', 'success')
                
                # Redirigir al dashboard después del login
                next_page = request.args.get('next')
                return redirect(next_page) if next_page else redirect(url_for('dashboard'))
            else:
                flash('Credenciales inválidas', 'error')
        except Exception as e:
            print(f"Error en login: {e}")
            flash('Error al procesar el login', 'error')
    
    return render_template('login.html')

@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        name = request.form.get('name')
        email = request.form.get('email')
        password = request.form.get('password')
        department = request.form.get('department')
        role = request.form.get('role', 'USER')
        
        try:
            # Verificar si el usuario ya existe
            if User.query.filter_by(email=email).first():
                flash('El email ya está registrado', 'error')
                return redirect(url_for('register'))
            
            # Crear nuevo usuario
            user = User(name=name, email=email, department=department, role=role)
            user.set_password(password)
            
            db.session.add(user)
            db.session.commit()
            
            flash('¡Cuenta creada exitosamente! Por favor inicia sesión.', 'success')
            return redirect(url_for('login'))
            
        except Exception as e:
            print(f"Error en registro: {e}")
            db.session.rollback()
            flash('Error al crear la cuenta', 'error')
    
    return render_template('register.html')

@app.route('/logout')
@login_required
def logout():
    logout_user()
    flash('¡Sesión cerrada exitosamente!', 'success')
    return redirect(url_for('index'))

# API Endpoints
@app.route('/api/production')
def api_production():
    try:
        department = request.args.get('department', 'all')
        year = request.args.get('year', '2024')
        
        data = get_mock_production_data()
        return jsonify(data)
    except Exception as e:
        print(f"Error en API production: {e}")
        return jsonify({'error': str(e)}), 500

@app.route('/api/predictions', methods=['GET', 'POST'])
def api_predictions():
    try:
        if request.method == 'POST':
            data = request.get_json()
            
            # Lógica de predicción simplificada
            prediction = generate_simple_prediction(
                data.get('department'),
                data.get('target_month'),
                data.get('target_year')
            )
            
            return jsonify(prediction)
        
        # GET request - obtener predicciones existentes
        data = get_mock_predictions_data()
        return jsonify(data)
    except Exception as e:
        print(f"Error en API predictions: {e}")
        return jsonify({'error': str(e)}), 500

@app.route('/api/predict', methods=['POST'])
@login_required
def api_predict():
    try:
        data = request.get_json()
        
        # Generar predicción
        prediction = generate_simple_prediction(
            data['department'],
            data['target_month'],
            data['target_year']
        )
        
        # Guardar en base de datos
        new_prediction = Prediction(
            user_id=current_user.id,
            department=data['department'],
            target_month=data['target_month'],
            target_year=data['target_year'],
            predicted_volume=prediction['volume'],
            predicted_price=prediction['price'],
            confidence=prediction['confidence']
        )
        
        db.session.add(new_prediction)
        db.session.commit()
        
        return jsonify({
            'success': True,
            'prediction': prediction
        })
        
    except Exception as e:
        print(f"Error en API predict: {e}")
        db.session.rollback()
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

# Funciones auxiliares
def get_mock_production_data():
    """Generar datos de ejemplo para producción"""
    months = ['Ene', 'Feb', 'Mar', 'Abr', 'May', 'Jun', 
              'Jul', 'Ago', 'Sep', 'Oct', 'Nov', 'Dic']
    
    data = []
    base_volume = 125000
    base_price = 850
    
    for i, month in enumerate(months):
        # Simular crecimiento estacional
        seasonal_factor = 1 + 0.1 * math.sin(2 * math.pi * i / 12)
        volume = base_volume + (i * 3500) + random.randint(-5000, 5000)
        price = base_price + (i * 7) + random.randint(-20, 20)
        
        data.append({
            'month': month,
            'volume': int(volume * seasonal_factor),
            'price': int(price)
        })
    
    return data

def get_mock_department_data():
    """Generar datos de ejemplo por departamento"""
    return [
        {'name': 'Antioquia', 'value': 28, 'production': 1680000},
        {'name': 'Cundinamarca', 'value': 22, 'production': 1320000},
        {'name': 'Valle del Cauca', 'value': 18, 'production': 1080000},
        {'name': 'Boyacá', 'value': 15, 'production': 900000},
        {'name': 'Nariño', 'value': 10, 'production': 600000},
        {'name': 'Otros', 'value': 7, 'production': 420000}
    ]

def get_mock_predictions_data():
    """Generar datos de ejemplo para predicciones"""
    months = ['Ene 2025', 'Feb 2025', 'Mar 2025', 'Abr 2025', 'May 2025', 'Jun 2025']
    
    data = []
    base_volume = 172000
    
    for i, month in enumerate(months):
        # Simular tendencia con variación
        trend = base_volume + (i * 3000)
        variation = random.randint(-2000, 2000)
        confidence = max(0.6, min(0.95, 0.85 - (i * 0.02)))
        
        data.append({
            'month': month,
            'predicted': int(trend + variation),
            'confidence': round(confidence, 2)
        })
    
    return data

def generate_simple_prediction(department, target_month, target_year):
    """Generar predicción usando algoritmo simplificado"""
    
    # Factores por departamento (simulación)
    department_factors = {
        'Antioquia': 1.2,
        'Cundinamarca': 1.0,
        'Valle del Cauca': 1.1,
        'Boyacá': 0.9,
        'Nariño': 0.8
    }
    
    # Factor estacional
    month_factor = 1 + 0.15 * math.sin(2 * math.pi * int(target_month) / 12)
    
    # Base de cálculo
    base_volume = 150000
    base_price = 900
    
    # Aplicar factores
    dept_factor = department_factors.get(department, 1.0)
    
    predicted_volume = base_volume * dept_factor * month_factor
    predicted_price = base_price * (1 + (int(target_month) - 6) * 0.02)  # Variación mensual
    
    # Calcular confianza basada en factores
    volume_confidence = min(0.95, 0.7 + (dept_factor * 0.2))
    seasonal_confidence = 0.8 + 0.1 * abs(math.cos(2 * math.pi * int(target_month) / 12))
    
    final_confidence = (volume_confidence + seasonal_confidence) / 2
    
    return {
        'volume': int(predicted_volume + random.randint(-5000, 5000)),
        'price': int(predicted_price + random.randint(-10, 10)),
        'confidence': round(final_confidence, 2)
    }

# Inicializar base de datos
@app.before_request
def create_tables():
    # Crear tablas solo si no existen
    if not hasattr(app, '_tables_created'):
        try:
            db.create_all()
            
            # Crear usuario admin si no existe
            if not User.query.filter_by(email='admin@lecheml.com').first():
                admin = User(
                    name='Administrador',
                    email='admin@lecheml.com',
                    role='ADMIN',
                    department='Cundinamarca'
                )
                admin.set_password('admin123')
                db.session.add(admin)
                db.session.commit()
                print("Usuario admin creado exitosamente")
            
            app._tables_created = True
            print("Base de datos inicializada correctamente")
            
        except Exception as e:
            print(f"Error al crear tablas: {e}")

if __name__ == '__main__':
    with app.app_context():
        try:
            db.create_all()
            print("Tablas creadas exitosamente")
        except Exception as e:
            print(f"Error al crear tablas: {e}")
    
    app.run(debug=True, host='0.0.0.0', port=5000)