import os
from datetime import timedelta

# Get the absolute path of the directory where this file is (i.e., backend/)
BASE_DIR = os.path.abspath(os.path.dirname(__file__))

class Config:
    SECRET_KEY = os.environ.get('JHDFGIABE87ERABVWI87TRVAIWYTRVAWBT', 'AIBYCTRA87RTV8A7TRA87OTRAO8754OV87QAT4OWTV87O8WT4V')
    JWT_SECRET_KEY = os.environ.get('ABOCUIYRA7YVAY74WOOVR79Y4WOYAV2Y4O5VAY5O25Y7OQV', 'ANWO4YOTV9A48YWOT89AO9VWY98ATVWY4AT4NVYAOYO5VTAOWY4YOTV5W4BVOYBV')
    JWT_ACCESS_TOKEN_EXPIRES = timedelta(hours=24)
    
    # This will create 'hospital.db' inside 'backend/instance/hospital.db'
    SQLALCHEMY_DATABASE_URI = 'sqlite:///' + os.path.join(BASE_DIR, 'instance', 'hospital.db')
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    
    REDIS_URL = os.environ.get('REDIS_URL', 'redis://localhost:6379/0')
    CACHE_TYPE = 'redis'
    CACHE_REDIS_URL = REDIS_URL
    CACHE_DEFAULT_TIMEOUT = 300
    
    # --- THESE MUST BE LOWERCASE ---
    broker_url = os.environ.get('CELERY_BROKER_URL', 'redis://localhost:6379/0')
    result_backend = os.environ.get('CELERY_RESULT_BACKEND', 'redis://localhost:6379/0')
    # --- END LOWERCASE SETTINGS ---
    
    MAIL_SERVER = os.environ.get('MAIL_SERVER', 'smtp.gmail.com')
    MAIL_PORT = int(os.environ.get('MAIL_PORT', 587))
    MAIL_USE_TLS = os.environ.get('MAIL_USE_TLS', 'True') == 'True'
    MAIL_USERNAME = os.environ.get('MAIL_USERNAME', 'shshsr24@gmail.com')
    MAIL_PASSWORD = os.environ.get('MAIL_PASSWORD', 'uiznptufkwuppjbi')
    MAIL_DEFAULT_SENDER = ('Hospital Management System', 'admin@hospital.com')
    MAIL_USE_SSL = False
    MAIL_DEBUG = True
    
    # HTTP Email Provider (SendGrid)
    SENDGRID_API_KEY = os.environ.get('SENDGRID_API_KEY', '')