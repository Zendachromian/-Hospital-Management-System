# backend/__init__.py
from flask import Flask, send_from_directory
from flask_cors import CORS
from .config import Config
import os

def create_app():
    # Get the absolute path to the project root
    BASE_DIR = os.path.dirname(os.path.abspath(__file__))
    PROJECT_ROOT = os.path.dirname(BASE_DIR)
    FRONTEND_DIR = os.path.join(PROJECT_ROOT, 'frontend')
    
    app = Flask(__name__)
    app.config.from_object(Config)
    
    # Configure CORS for frontend on port 8080
    CORS(app, resources={
        r"/api/*": {
            "origins": ["http://localhost:8080", "http://127.0.0.1:8080"],
            "methods": ["GET", "POST", "PUT", "DELETE", "OPTIONS"],
            "allow_headers": ["Content-Type", "Authorization"]
        }
    })
    
    # Initialize extensions
    from .models import db
    db.init_app(app)
    
    # Import and register blueprints
    from .routes import auth, admin, doctor, patient
    
    app.register_blueprint(auth.bp)
    app.register_blueprint(admin.bp)
    app.register_blueprint(doctor.bp)
    app.register_blueprint(patient.bp)
    
    # PWA Routes - Serve manifest.json and service-worker.js
    @app.route('/manifest.json')
    def manifest():
        """Serve PWA manifest for app installation"""
        return send_from_directory(FRONTEND_DIR, 'manifest.json', mimetype='application/manifest+json')
    
    @app.route('/service-worker.js')
    def service_worker():
        """Serve service worker for PWA offline support and caching"""
        return send_from_directory(FRONTEND_DIR, 'service-worker.js', mimetype='application/javascript')
    
    return app