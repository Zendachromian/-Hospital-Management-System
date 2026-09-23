from flask import Blueprint, request, jsonify
from flask_jwt_extended import create_access_token, jwt_required, get_jwt_identity
from werkzeug.security import generate_password_hash, check_password_hash
from datetime import datetime

from ..models import db, User, Doctor, Patient

bp = Blueprint('auth', __name__, url_prefix='/api/auth')

@bp.route('/register', methods=['POST'])
def register():
    data = request.json
    
    if User.query.filter_by(username=data.get('username')).first():
        return jsonify({'error': 'Username already exists'}), 400
    
    if User.query.filter_by(email=data.get('email')).first():
        return jsonify({'error': 'Email already exists'}), 400
    
    # Public registration only allows patient role (doctors must be registered by admin)
    role = 'patient'
    if data.get('role') and data.get('role') != 'patient':
        return jsonify({'error': 'Only patients can self-register. Doctors must be registered by admin.'}), 403
    
    user = User(
        username=data.get('username'),
        email=data.get('email'),
        password_hash=generate_password_hash(data.get('password')),
        role=role,
        full_name=data.get('full_name'),
        phone=data.get('phone', '')
    )
    db.session.add(user)
    db.session.flush()
    
    # Only create patient profile if role is patient
    if role == 'patient':
        patient = Patient(
            user_id=user.id,
            date_of_birth=datetime.strptime(data.get('date_of_birth'), '%Y-%m-%d').date() if data.get('date_of_birth') else None,
            gender=data.get('gender'),
            address=data.get('address', ''),
            blood_group=data.get('blood_group', ''),
            emergency_contact=data.get('emergency_contact', '')
        )
        db.session.add(patient)
    
    db.session.commit()
    
    return jsonify({'message': 'Registration successful', 'user': user.to_dict()}), 201

@bp.route('/login', methods=['POST'])
def login():
    data = request.json
    username = data.get('username')
    password = data.get('password')
    
    user = User.query.filter_by(username=username).first()
    
    if not user or not check_password_hash(user.password_hash, password):
        return jsonify({'error': 'Invalid username or password'}), 401
    
    if not user.is_active:
        return jsonify({'error': 'Account is deactivated'}), 403
    
    # FIX: Create token with string identity (user ID as string)
    access_token = create_access_token(identity=str(user.id))
    
    user_data = user.to_dict()
    if user.role == 'doctor' and hasattr(user, 'doctor_profile') and user.doctor_profile:
        user_data['doctor_id'] = user.doctor_profile.id
    elif user.role == 'patient' and hasattr(user, 'patient_profile') and user.patient_profile:
        user_data['patient_id'] = user.patient_profile.id
    
    return jsonify({
        'access_token': access_token,
        'user': user_data
    }), 200

@bp.route('/profile', methods=['GET'])
@jwt_required()
def get_profile():
    # FIX: Get user ID from token and query the user
    current_user_id = get_jwt_identity()
    user = User.query.get(int(current_user_id))
    
    if not user:
        return jsonify({'error': 'User not found'}), 404
    
    user_data = user.to_dict()
    if user.role == 'doctor' and hasattr(user, 'doctor_profile') and user.doctor_profile:
        user_data['doctor_id'] = user.doctor_profile.id
    elif user.role == 'patient' and hasattr(user, 'patient_profile') and user.patient_profile:
        user_data['patient_id'] = user.patient_profile.id
    
    return jsonify({'user': user_data}), 200

@bp.route('/profile', methods=['PUT'])
@jwt_required()
def update_profile():
    # FIX: Get user ID from token and query the user
    current_user_id = get_jwt_identity()
    user = User.query.get(int(current_user_id))
    
    if not user:
        return jsonify({'error': 'User not found'}), 404
    
    data = request.json
    
    if data.get('full_name'):
        user.full_name = data.get('full_name')
    if data.get('phone'):
        user.phone = data.get('phone')
    if data.get('email') and data.get('email') != user.email:
        if User.query.filter_by(email=data.get('email')).first():
            return jsonify({'error': 'Email already exists'}), 400
        user.email = data.get('email')
    
    if user.role == 'patient' and user.patient_profile:
        patient = user.patient_profile
        if data.get('date_of_birth'):
            patient.date_of_birth = datetime.strptime(data.get('date_of_birth'), '%Y-%m-%d').date()
        if data.get('gender'):
            patient.gender = data.get('gender')
        if data.get('address'):
            patient.address = data.get('address')
        if data.get('blood_group'):
            patient.blood_group = data.get('blood_group')
        if data.get('emergency_contact'):
            patient.emergency_contact = data.get('emergency_contact')
    
    db.session.commit()
    
    user_data = user.to_dict()
    if user.role == 'patient' and user.patient_profile:
        user_data['patient_id'] = user.patient_profile.id
    
    return jsonify({'message': 'Profile updated successfully', 'user': user_data}), 200

# Add a debug endpoint to check users
@bp.route('/debug/users', methods=['GET'])
def debug_users():
    """Debug endpoint to check existing users"""
    try:
        users = User.query.all()
        return jsonify({
            'total_users': len(users),
            'users': [{
                'id': user.id,
                'username': user.username,
                'role': user.role,
                'is_active': user.is_active
            } for user in users]
        }), 200
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@bp.route('/notifications', methods=['GET'])
@jwt_required()
def get_notifications():
    """Get unread notifications for current user"""
    current_user_id = get_jwt_identity()
    user = User.query.get(int(current_user_id))
    
    if not user:
        return jsonify({'error': 'User not found'}), 404
    
    from ..models import Notification
    notifications = Notification.query.filter_by(
        user_id=user.id,
        is_read=False
    ).order_by(Notification.created_at.desc()).all()
    
    return jsonify({
        'notifications': [notif.to_dict() for notif in notifications]
    }), 200

@bp.route('/notifications/<int:notification_id>', methods=['PUT'])
@jwt_required()
def mark_notification_read(notification_id):
    """Mark notification as read"""
    current_user_id = get_jwt_identity()
    user = User.query.get(int(current_user_id))
    
    if not user:
        return jsonify({'error': 'User not found'}), 404
    
    from ..models import Notification
    notification = Notification.query.get(notification_id)
    
    if not notification:
        return jsonify({'error': 'Notification not found'}), 404
    
    if notification.user_id != user.id:
        return jsonify({'error': 'Unauthorized'}), 403
    
    notification.is_read = True
    db.session.commit()
    
    return jsonify({'message': 'Notification marked as read'}), 200

@bp.route('/notifications/mark-all-read', methods=['POST'])
@jwt_required()
def mark_all_notifications_read():
    """Mark all notifications as read for current user"""
    current_user_id = get_jwt_identity()
    user = User.query.get(int(current_user_id))
    
    if not user:
        return jsonify({'error': 'User not found'}), 404
    
    from ..models import Notification
    Notification.query.filter_by(
        user_id=user.id,
        is_read=False
    ).update({'is_read': True})
    
    db.session.commit()
    
    return jsonify({'message': 'All notifications marked as read'}), 200