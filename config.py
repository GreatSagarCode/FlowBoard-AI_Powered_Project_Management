import os
import logging

class Config:
    SECRET_KEY = os.environ.get('SECRET_KEY') or os.urandom(32)
    BASE_DIR = os.path.abspath(os.path.dirname(__file__))
    SQLALCHEMY_DATABASE_URI = os.environ.get('DATABASE_URL') or 'sqlite:///' + os.path.join(BASE_DIR, 'project_management.db')
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    SESSION_COOKIE_HTTPONLY = True
    SESSION_COOKIE_SECURE = os.environ.get('FLASK_ENV') == 'production'
    WTF_CSRF_ENABLED = True
    WTF_CSRF_TIME_LIMIT = 1800
