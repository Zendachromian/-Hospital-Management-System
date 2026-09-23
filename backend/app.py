from flask import Flask, jsonify
from flask_jwt_extended import JWTManager
from flask_mail import Mail
from werkzeug.security import generate_password_hash
from datetime import datetime, date
import os

# Import the app factory
from . import create_app

# Get the absolute path to the project root
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.dirname(BASE_DIR)

app = create_app()

jwt = JWTManager(app)
mail = Mail(app)

# Initialize Celery AFTER the app is created
try:
    from .celery_tasks import make_celery, celery
    celery_app = make_celery(app)
    celery.conf.update(celery_app.conf)
    print("✓ Celery initialized successfully")
except ImportError as e:
    print(f"⚠ Celery initialization warning: {e}")

@app.route('/api/health')
def health():
    return jsonify({'status': 'healthy', 'message': 'Hospital Management System API', 'port': 5000})

def init_database():
    with app.app_context():
        from .models import db, User, Department
        
        db.create_all()
        
        admin_exists = User.query.filter_by(role='admin').first()
        if not admin_exists:
            admin = User(
                username='admin',
                email='admin@hospital.com',
                password_hash=generate_password_hash('admin123'),
                role='admin',
                full_name='System Administrator',
                phone='1234567890',
                is_active=True
            )
            db.session.add(admin)
            
            default_departments = [
                Department(name='Cardiology', description='Heart and cardiovascular system'),
                Department(name='Neurology', description='Brain and nervous system'),
                Department(name='Orthopedics', description='Bones, joints, and muscles'),
                Department(name='Pediatrics', description='Children healthcare'),
                Department(name='Dermatology', description='Skin, hair, and nails'),
                Department(name='Oncology', description='Cancer treatment and care'),
                Department(name='Psychiatry', description='Mental health services'),
                Department(name='Emergency', description='Emergency medical services'),
                Department(name='General Medicine', description='General health issues'),
                Department(name='Surgery', description='Surgical procedures and operations')
            ]
            
            for dept in default_departments:
                existing = Department.query.filter_by(name=dept.name).first()
                if not existing:
                    db.session.add(dept)
            
            db.session.commit()
            print("✓ Database initialized with admin user and departments")
            print("  Admin credentials: username=admin, password=admin123")

if __name__ == '__main__':
    # Ensure the instance folder exists for the SQLite db
    try:
        os.makedirs(os.path.join(os.path.dirname(__file__), 'instance'))
    except FileExistsError:
        pass

    print(f"� Backend API Server Starting...")
    print(f"📁 Project root: {PROJECT_ROOT}")
    print(f"🌐 API URL: http://localhost:5000/api")
    print(f"🔗 Frontend: http://localhost:8080")
    print(f"🔴 Redis: localhost:6379")
    
    init_database()
    app.run(host='0.0.0.0', port=5000, debug=True)