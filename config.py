import os

class Config:
    """Configuración de la aplicación Flask"""
    SECRET_KEY = os.environ.get('SECRET_KEY') or 'clave-secreta-temporal-2024-lecheml-colombia'
    SQLALCHEMY_DATABASE_URI = os.environ.get('DATABASE_URL') or 'sqlite:///lecheml.db'
    SQLALCHEMY_TRACK_MODIFICATIONS = False