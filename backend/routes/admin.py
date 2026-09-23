from flask import Blueprint, request, jsonify
from flask_jwt_extended import jwt_required, get_jwt_identity
from werkzeug.security import generate_password_hash
from datetime import datetime
from sqlalchemy import or_, inspect

from ..models import db, User, Doctor, Patient, Department, Appointment, Treatment
from ..utils.cache import cache_get, cache_set, cache_delete, cache_clear_pattern

bp = Blueprint('admin', __name__, url_prefix='/api/admin')

def admin_required(fn):
    @jwt_required()
    def wrapper(*args, **kwargs):
        current_user_id = get_jwt_identity()
        user = User.query.get(int(current_user_id))
        
        if not user or user.role != 'admin':
            return jsonify({'error': 'Admin access required'}), 403
        return fn(*args, **kwargs)
    wrapper.__name__ = fn.__name__
    return wrapper

@bp.route('/database/test', methods=['GET'])
@admin_required
def test_database():
    """Test database connection and basic operations"""
    try:
        # Test connection - use text() for raw SQL
        from sqlalchemy import text
        db.session.execute(text('SELECT 1'))
        
        # Test Department model
        dept_count = Department.query.count()
        
        return jsonify({
            'database_connected': True,
            'department_count': dept_count,
            'message': f'Database connected successfully. Found {dept_count} departments.'
        }), 200
        
    except Exception as e:
        return jsonify({
            'database_connected': False,
            'error': str(e),
            'message': f'Database connection failed: {str(e)}'
        }), 500
@bp.route('/database/create-tables', methods=['POST'])
@admin_required
def create_tables():
    """Force create all database tables"""
    try:
        db.create_all()
        return jsonify({
            'message': 'All database tables created successfully',
            'tables_created': True
        }), 200
    except Exception as e:
        return jsonify({
            'error': f'Error creating tables: {str(e)}',
            'tables_created': False
        }), 500

@bp.route('/departments/debug', methods=['GET'])
@admin_required
def debug_departments():
    """Debug endpoint to check departments table status"""
    try:
        # Check if table exists by trying to query it
        inspector = inspect(db.engine)
        table_exists = 'departments' in inspector.get_table_names()
        
        if table_exists:
            department_count = Department.query.count()
            departments = Department.query.all()
            return jsonify({
                'table_exists': True,
                'department_count': department_count,
                'departments': [dept.to_dict() for dept in departments],
                'message': f'Departments table exists with {department_count} departments'
            }), 200
        else:
            return jsonify({
                'table_exists': False,
                'department_count': 0,
                'departments': [],
                'message': 'Departments table does not exist in the database'
            }), 200
            
    except Exception as e:
        return jsonify({
            'table_exists': False,
            'error': str(e),
            'message': f'Error checking departments table: {str(e)}'
        }), 500

@bp.route('/departments/seed', methods=['POST'])
@admin_required
def seed_departments():
    """Add initial departments if they don't exist"""
    try:
        departments_data = [
            {'name': 'Cardiology', 'description': 'Heart and cardiovascular system'},
            {'name': 'Neurology', 'description': 'Brain and nervous system'},
            {'name': 'Orthopedics', 'description': 'Bones and joints'},
            {'name': 'Pediatrics', 'description': 'Child healthcare'},
            {'name': 'Dermatology', 'description': 'Skin conditions'},
            {'name': 'Oncology', 'description': 'Cancer treatment'},
            {'name': 'Psychiatry', 'description': 'Mental health'},
            {'name': 'Emergency', 'description': 'Emergency care'},
            {'name': 'General Medicine', 'description': 'General healthcare and consultations'},
            {'name': 'Surgery', 'description': 'Surgical procedures and operations'}
        ]
        
        added_count = 0
        existing_count = 0
        
        for dept_data in departments_data:
            existing = Department.query.filter_by(name=dept_data['name']).first()
            if not existing:
                try:
                    department = Department(
                        name=dept_data['name'],
                        description=dept_data['description']
                    )
                    db.session.add(department)
                    added_count += 1
                    print(f"Added department: {dept_data['name']}")
                except Exception as e:
                    print(f"Error adding department {dept_data['name']}: {str(e)}")
                    continue
            else:
                existing_count += 1
                print(f"Department already exists: {dept_data['name']}")
        
        try:
            db.session.commit()
            print(f"Successfully committed {added_count} new departments")
        except Exception as e:
            db.session.rollback()
            print(f"Error committing departments: {str(e)}")
            return jsonify({
                'error': f'Database error: {str(e)}',
                'added_count': 0,
                'existing_count': existing_count
            }), 500
        
        # Clear cache to ensure fresh data
        try:
            cache_clear_pattern('departments:*')
        except Exception as e:
            print(f"Cache clear warning: {str(e)}")
        
        return jsonify({
            'message': f'Departments seeded successfully. Added {added_count} new departments, {existing_count} already existed.',
            'added_count': added_count,
            'existing_count': existing_count,
            'total_count': Department.query.count()
        }), 201
        
    except Exception as e:
        db.session.rollback()
        error_msg = f'Error seeding departments: {str(e)}'
        print(error_msg)
        return jsonify({'error': error_msg}), 500

@bp.route('/dashboard', methods=['GET'])
@admin_required
def get_dashboard():
    try:
        from sqlalchemy import func
        from datetime import timedelta
        
        # Check cache first (5 minutes TTL for dashboard stats)
        cache_key = 'admin:dashboard:stats'
        cached_data = cache_get(cache_key)
        if cached_data:
            return jsonify({**cached_data, 'cached': True}), 200
        
        total_doctors = Doctor.query.join(User).filter(User.is_active == True).count()
        total_patients = Patient.query.join(User).filter(User.is_active == True).count()
        total_appointments = Appointment.query.count()
        upcoming_appointments = Appointment.query.filter(
            Appointment.appointment_date >= datetime.now().date(),
            Appointment.status == 'Booked'
        ).count()
        
        # Appointments by status
        status_counts = db.session.query(
            Appointment.status,
            func.count(Appointment.id)
        ).group_by(Appointment.status).all()
        
        appointment_status = {status: count for status, count in status_counts}
        
        # Appointments by department (include departments with 0 appointments)
        dept_counts = db.session.query(
            Department.name,
            func.count(Appointment.id)
        ).outerjoin(Doctor, Department.id == Doctor.department_id
        ).outerjoin(Appointment, Doctor.id == Appointment.doctor_id
        ).group_by(Department.name).all()
        
        appointments_by_department = {dept: count for dept, count in dept_counts}
        
        # Appointments trend (last 7 days)
        today = datetime.now().date()
        appointments_trend = []
        for i in range(6, -1, -1):
            date = today - timedelta(days=i)
            count = Appointment.query.filter(
                Appointment.appointment_date == date
            ).count()
            appointments_trend.append({
                'date': date.strftime('%Y-%m-%d'),
                'count': count
            })
        
        # Gender distribution
        gender_counts = db.session.query(
            Patient.gender,
            func.count(Patient.id)
        ).filter(Patient.gender.isnot(None)
        ).group_by(Patient.gender).all()
        
        gender_distribution = {gender: count for gender, count in gender_counts if gender}
        
        # Top doctors by appointments
        top_doctors_query = db.session.query(
            User.full_name,
            func.count(Appointment.id).label('appointment_count')
        ).join(Doctor, User.id == Doctor.user_id
        ).outerjoin(Appointment, Doctor.id == Appointment.doctor_id
        ).filter(User.is_active == True
        ).group_by(User.full_name
        ).order_by(func.count(Appointment.id).desc()
        ).limit(5).all()
        
        top_doctors = [
            {'name': name, 'appointment_count': count} 
            for name, count in top_doctors_query
        ]
        
        # Peak appointment times
        peak_times_query = db.session.query(
            Appointment.appointment_time,
            func.count(Appointment.id).label('count')
        ).filter(Appointment.appointment_time.isnot(None)
        ).group_by(Appointment.appointment_time
        ).order_by(Appointment.appointment_time).all()
        
        peak_appointment_times = [
            {'time_slot': str(time), 'count': count}
            for time, count in peak_times_query
        ]
        
        dashboard_data = {
            'total_doctors': total_doctors,
            'total_patients': total_patients,
            'total_appointments': total_appointments,
            'upcoming_appointments': upcoming_appointments,
            'appointment_status': appointment_status,
            'appointments_by_department': appointments_by_department,
            'appointments_trend': appointments_trend,
            'gender_distribution': gender_distribution,
            'top_doctors': top_doctors,
            'peak_appointment_times': peak_appointment_times
        }
        
        # Cache the dashboard data for 5 minutes
        cache_set(cache_key, dashboard_data, expiry=300)
        
        return jsonify(dashboard_data), 200
    except Exception as e:
        return jsonify({'error': f'Error loading dashboard: {str(e)}'}), 500

@bp.route('/doctors', methods=['GET'])
@admin_required
def get_doctors():
    try:
        # Check for search parameters
        search_query = request.args.get('search', '').strip()
        show_inactive = request.args.get('show_inactive', 'false').lower() == 'true'
        
        if search_query:
            # Search by name, doctor ID, or specialization
            query = Doctor.query.join(User)
            if not show_inactive:
                query = query.filter(User.is_active == True)
            
            doctors = query.filter(
                or_(
                    User.full_name.ilike(f'%{search_query}%'),
                    Doctor.id.cast(db.String).ilike(f'%{search_query}%'),
                    Doctor.specialization.ilike(f'%{search_query}%')
                )
            ).all()
            return jsonify({'doctors': [doc.to_dict() for doc in doctors]}), 200
        
        cache_key = f'admin:doctors:{"all" if show_inactive else "active"}'
        cached_data = cache_get(cache_key)
        
        if cached_data:
            return jsonify(cached_data), 200
        
        query = Doctor.query.join(User)
        if not show_inactive:
            query = query.filter(User.is_active == True)
        doctors = query.all()
        response_data = {'doctors': [doc.to_dict() for doc in doctors]}
        
        cache_set(cache_key, response_data, expiry=300)
        return jsonify(response_data), 200
    except Exception as e:
        return jsonify({'error': f'Error loading doctors: {str(e)}'}), 500

@bp.route('/doctors', methods=['POST'])
@admin_required
def add_doctor():
    try:
        data = request.json
        
        # Check if username exists with an ACTIVE user
        existing_user_by_username = User.query.filter_by(username=data.get('username')).first()
        if existing_user_by_username and existing_user_by_username.is_active:
            return jsonify({'error': 'Username already exists'}), 400
        
        # Check if email exists with an ACTIVE user
        existing_user_by_email = User.query.filter_by(email=data.get('email')).first()
        if existing_user_by_email and existing_user_by_email.is_active:
            return jsonify({'error': 'Email already exists'}), 400
        
        # If inactive user exists with same username, reactivate them
        if existing_user_by_username and not existing_user_by_username.is_active:
            user = existing_user_by_username
            user.is_active = True
            user.full_name = data.get('full_name')
            user.email = data.get('email')
            user.phone = data.get('phone', '')
            user.password_hash = generate_password_hash(data.get('password', 'doctor123'))
            
            # Update existing doctor profile
            if user.doctor_profile:
                doctor = user.doctor_profile
                doctor.department_id = data.get('department_id')
                doctor.specialization = data.get('specialization')
                doctor.qualification = data.get('qualification', '')
                doctor.experience_years = data.get('experience_years', 0)
                doctor.consultation_fee = data.get('consultation_fee', 0)
                doctor.gender = data.get('gender', '')
            else:
                # Create new doctor profile if it doesn't exist
                doctor = Doctor(
                    user_id=user.id,
                    department_id=data.get('department_id'),
                    specialization=data.get('specialization'),
                    qualification=data.get('qualification', ''),
                    experience_years=data.get('experience_years', 0),
                    consultation_fee=data.get('consultation_fee', 0),
                    gender=data.get('gender', '')
                )
                db.session.add(doctor)
        else:
            # Check if department exists
            department = Department.query.get(data.get('department_id'))
            if not department:
                return jsonify({'error': 'Invalid department'}), 400
            
            # Create new user
            user = User(
                username=data.get('username'),
                email=data.get('email'),
                password_hash=generate_password_hash(data.get('password', 'doctor123')),
                role='doctor',
                full_name=data.get('full_name'),
                phone=data.get('phone', '')
            )
            db.session.add(user)
            db.session.flush()
            
            # Create new doctor profile
            doctor = Doctor(
                user_id=user.id,
                department_id=data.get('department_id'),
                specialization=data.get('specialization'),
                qualification=data.get('qualification', ''),
                experience_years=data.get('experience_years', 0),
                consultation_fee=data.get('consultation_fee', 0),
                gender=data.get('gender', '')
            )
            db.session.add(doctor)
        
        db.session.commit()
        
        # Clear all related caches
        cache_clear_pattern('admin:doctors:*')
        cache_clear_pattern('patient:doctors:*')
        cache_clear_pattern('departments:*')
        cache_clear_pattern('doctors:list:*')
        cache_delete('admin:dashboard:stats')  # Clear dashboard cache
        
        return jsonify({'message': 'Doctor added successfully', 'doctor': doctor.to_dict()}), 201
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': f'Error adding doctor: {str(e)}'}), 500

@bp.route('/doctors/<int:doctor_id>', methods=['PUT'])
@admin_required
def update_doctor(doctor_id):
    try:
        doctor = Doctor.query.get(doctor_id)
        if not doctor:
            return jsonify({'error': 'Doctor not found'}), 404
        
        data = request.json
        user = doctor.user
        
        if data.get('full_name'):
            user.full_name = data.get('full_name')
        if data.get('phone'):
            user.phone = data.get('phone')
        if data.get('email') and data.get('email') != user.email:
            if User.query.filter_by(email=data.get('email')).first():
                return jsonify({'error': 'Email already exists'}), 400
            user.email = data.get('email')
        
        # Update password if provided
        if data.get('password'):
            user.password_hash = generate_password_hash(data.get('password'))
        
        if data.get('department_id'):
            department = Department.query.get(data.get('department_id'))
            if not department:
                return jsonify({'error': 'Invalid department'}), 400
            doctor.department_id = data.get('department_id')
        if data.get('specialization'):
            doctor.specialization = data.get('specialization')
        if data.get('qualification'):
            doctor.qualification = data.get('qualification')
        if 'experience_years' in data:
            doctor.experience_years = data.get('experience_years')
        if 'consultation_fee' in data:
            doctor.consultation_fee = data.get('consultation_fee')
        if data.get('gender'):
            doctor.gender = data.get('gender')
        
        # Build detailed notification message
        from ..models import Notification
        changes = []
        if data.get('full_name'): changes.append(f"Name: {data.get('full_name')}")
        if data.get('phone'): changes.append(f"Phone: {data.get('phone')}")
        if data.get('email') and data.get('email') != user.email: changes.append(f"Email: {data.get('email')}")
        if data.get('password'): changes.append("Password updated")
        if data.get('department_id'): 
            dept = Department.query.get(data.get('department_id'))
            changes.append(f"Department: {dept.name}")
        if data.get('specialization'): changes.append(f"Specialization: {data.get('specialization')}")
        if data.get('qualification'): changes.append(f"Qualification: {data.get('qualification')}")
        if 'experience_years' in data: changes.append(f"Experience: {data.get('experience_years')} years")
        if 'consultation_fee' in data: changes.append(f"Fee: ${data.get('consultation_fee')}")
        if data.get('gender'): changes.append(f"Gender: {data.get('gender')}")
        
        changes_text = ", ".join(changes) if changes else "profile details"
        notification = Notification(
            user_id=user.id,
            message=f"👨‍⚕️ Admin updated your profile: {changes_text}. Please review the changes."
        )
        db.session.add(notification)
        db.session.commit()
        
        cache_clear_pattern('admin:doctors:*')
        cache_clear_pattern('patient:doctors:*')
        cache_clear_pattern('departments:*')
        
        return jsonify({'message': 'Doctor updated successfully', 'doctor': doctor.to_dict()}), 200
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': f'Error updating doctor: {str(e)}'}), 500

@bp.route('/doctors/<int:doctor_id>', methods=['DELETE'])
@admin_required
def delete_doctor(doctor_id):
    try:
        doctor = Doctor.query.get(doctor_id)
        if not doctor:
            return jsonify({'error': 'Doctor not found'}), 404
        
        doctor.user.is_active = False
        
        # Notify doctor about deactivation
        from ..models import Notification
        notification = Notification(
            user_id=doctor.user.id,
            message=f"⚠️ Your account has been deactivated by the admin. Please contact the hospital administration for more information."
        )
        db.session.add(notification)
        db.session.commit()
        
        cache_clear_pattern('admin:doctors:*')
        cache_clear_pattern('patient:doctors:*')
        cache_clear_pattern('departments:*')
        cache_delete('admin:dashboard:stats')
        
        return jsonify({'message': 'Doctor deactivated successfully'}), 200
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': f'Error deactivating doctor: {str(e)}'}), 500

@bp.route('/doctors/<int:doctor_id>/reactivate', methods=['POST'])
@admin_required
def reactivate_doctor(doctor_id):
    try:
        doctor = Doctor.query.get(doctor_id)
        if not doctor:
            return jsonify({'error': 'Doctor not found'}), 404
        
        if doctor.user.is_active:
            return jsonify({'error': 'Doctor is already active'}), 400
        
        doctor.user.is_active = True
        
        # Notify doctor about reactivation
        from ..models import Notification
        notification = Notification(
            user_id=doctor.user.id,
            message=f"✅ Your account has been reactivated by the admin. You can now log in and access all features."
        )
        db.session.add(notification)
        db.session.commit()
        
        cache_clear_pattern('admin:doctors:*')
        cache_clear_pattern('patient:doctors:*')
        cache_clear_pattern('departments:*')
        cache_delete('admin:dashboard:stats')
        
        return jsonify({'message': 'Doctor reactivated successfully', 'doctor': doctor.to_dict()}), 200
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': f'Error reactivating doctor: {str(e)}'}), 500

@bp.route('/departments', methods=['GET'])
@admin_required
def get_departments():
    try:
        cache_key = 'departments:all'
        cached_data = cache_get(cache_key)
        
        if cached_data:
            return jsonify(cached_data), 200
        
        departments = Department.query.all()
        response_data = {'departments': [dept.to_dict() for dept in departments]}
        
        cache_set(cache_key, response_data, expiry=600)
        return jsonify(response_data), 200
    except Exception as e:
        return jsonify({'error': f'Error loading departments: {str(e)}'}), 500

@bp.route('/departments', methods=['POST'])
@admin_required
def add_department():
    try:
        data = request.json
        
        if Department.query.filter_by(name=data.get('name')).first():
            return jsonify({'error': 'Department already exists'}), 400
        
        department = Department(
            name=data.get('name'),
            description=data.get('description', '')
        )
        db.session.add(department)
        db.session.commit()
        
        cache_clear_pattern('departments:*')
        cache_delete('admin:dashboard:stats')
        
        return jsonify({
            'message': 'Department added successfully',
            'department': department.to_dict()
        }), 201
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': f'Error adding department: {str(e)}'}), 500

@bp.route('/patients', methods=['GET'])
@admin_required
def get_patients():
    try:
        # Check for search parameters
        search_query = request.args.get('search', '').strip()
        show_inactive = request.args.get('show_inactive', 'false').lower() == 'true'
        
        if search_query:
            # Search by name, patient ID, phone, or email
            query = Patient.query.join(User)
            if not show_inactive:
                query = query.filter(User.is_active == True)
            
            patients = query.filter(
                or_(
                    User.full_name.ilike(f'%{search_query}%'),
                    Patient.id.cast(db.String).ilike(f'%{search_query}%'),
                    User.phone.ilike(f'%{search_query}%'),
                    User.email.ilike(f'%{search_query}%')
                )
            ).all()
            return jsonify({'patients': [patient.to_dict() for patient in patients]}), 200
        
        query = Patient.query.join(User)
        if not show_inactive:
            query = query.filter(User.is_active == True)
        patients = query.all()
        return jsonify({'patients': [patient.to_dict() for patient in patients]}), 200
    except Exception as e:
        return jsonify({'error': f'Error loading patients: {str(e)}'}), 500

@bp.route('/patients/<int:patient_id>', methods=['PUT'])
@admin_required
def update_patient(patient_id):
    try:
        patient = Patient.query.get(patient_id)
        if not patient:
            return jsonify({'error': 'Patient not found'}), 404
        
        data = request.json
        user = patient.user
        
        if data.get('full_name'):
            user.full_name = data.get('full_name')
        if data.get('phone'):
            user.phone = data.get('phone')
        if data.get('email') and data.get('email') != user.email:
            if User.query.filter_by(email=data.get('email')).first():
                return jsonify({'error': 'Email already exists'}), 400
            user.email = data.get('email')
        
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
        
        # Build detailed notification message
        from ..models import Notification
        changes = []
        if data.get('full_name'): changes.append(f"Name: {data.get('full_name')}")
        if data.get('phone'): changes.append(f"Phone: {data.get('phone')}")
        if data.get('email') and data.get('email') != user.email: changes.append(f"Email: {data.get('email')}")
        if data.get('date_of_birth'): changes.append(f"Date of Birth: {data.get('date_of_birth')}")
        if data.get('gender'): changes.append(f"Gender: {data.get('gender')}")
        if data.get('address'): changes.append("Address updated")
        if data.get('blood_group'): changes.append(f"Blood Group: {data.get('blood_group')}")
        if data.get('emergency_contact'): changes.append(f"Emergency Contact: {data.get('emergency_contact')}")
        
        changes_text = ", ".join(changes) if changes else "profile details"
        notification = Notification(
            user_id=user.id,
            message=f"👤 Admin updated your profile: {changes_text}. Please review the changes."
        )
        db.session.add(notification)
        db.session.commit()
        
        return jsonify({'message': 'Patient updated successfully', 'patient': patient.to_dict()}), 200
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': f'Error updating patient: {str(e)}'}), 500

@bp.route('/patients/<int:patient_id>', methods=['DELETE'])
@admin_required
def delete_patient(patient_id):
    try:
        patient = Patient.query.get(patient_id)
        if not patient:
            return jsonify({'error': 'Patient not found'}), 404
        
        patient.user.is_active = False
        
        # Notify patient about deactivation
        from ..models import Notification
        notification = Notification(
            user_id=patient.user.id,
            message=f"⚠️ Your account has been deactivated by the admin. Please contact the hospital for more information."
        )
        db.session.add(notification)
        db.session.commit()
        
        cache_delete('admin:dashboard:stats')
        
        return jsonify({'message': 'Patient deactivated successfully'}), 200
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': f'Error deactivating patient: {str(e)}'}), 500

@bp.route('/patients/<int:patient_id>/reactivate', methods=['POST'])
@admin_required
def reactivate_patient(patient_id):
    try:
        patient = Patient.query.get(patient_id)
        if not patient:
            return jsonify({'error': 'Patient not found'}), 404
        
        if patient.user.is_active:
            return jsonify({'error': 'Patient is already active'}), 400
        
        patient.user.is_active = True
        
        # Notify patient about reactivation
        from ..models import Notification
        notification = Notification(
            user_id=patient.user.id,
            message=f"✅ Your account has been reactivated by the admin. You can now log in and access all features."
        )
        db.session.add(notification)
        db.session.commit()
        
        cache_delete('admin:dashboard:stats')
        
        return jsonify({'message': 'Patient reactivated successfully', 'patient': patient.to_dict()}), 200
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': f'Error reactivating patient: {str(e)}'}), 500

@bp.route('/appointments', methods=['GET'])
@admin_required
def get_appointments():
    try:
        appointments = Appointment.query.order_by(Appointment.appointment_date.desc(), Appointment.appointment_time.desc()).all()
        return jsonify({'appointments': [apt.to_dict() for apt in appointments]}), 200
    except Exception as e:
        return jsonify({'error': f'Error loading appointments: {str(e)}'}), 500

@bp.route('/search/doctors', methods=['GET'])
@admin_required
def search_doctors():
    try:
        query = request.args.get('q', '')
        
        doctors = Doctor.query.join(User).join(Department).filter(
            or_(
                User.full_name.ilike(f'%{query}%'),
                Department.name.ilike(f'%{query}%'),
                Doctor.specialization.ilike(f'%{query}%')
            )
        ).all()
        
        return jsonify({'doctors': [doc.to_dict() for doc in doctors]}), 200
    except Exception as e:
        return jsonify({'error': f'Error searching doctors: {str(e)}'}), 500

@bp.route('/search/patients', methods=['GET'])
@admin_required
def search_patients():
    try:
        query = request.args.get('q', '')
        
        patients = Patient.query.join(User).filter(
            or_(
                User.full_name.ilike(f'%{query}%'),
                User.email.ilike(f'%{query}%'),
                User.phone.ilike(f'%{query}%')
            )
        ).all()
        
        return jsonify({'patients': [patient.to_dict() for patient in patients]}), 200
    except Exception as e:
        return jsonify({'error': f'Error searching patients: {str(e)}'}), 500

@bp.route('/appointments/<int:appointment_id>/send-email', methods=['POST'])
@admin_required
def send_appointment_email(appointment_id):
    """Manually send appointment notification emails to patient and doctor (async)"""
    try:
        appointment = Appointment.query.get(appointment_id)
        if not appointment:
            return jsonify({'error': 'Appointment not found'}), 404
        
        # Send email asynchronously to avoid blocking the request
        from ..celery_tasks import send_appointment_notification
        task = send_appointment_notification.apply_async(args=(appointment_id,), countdown=0)
        
        return jsonify({
            'message': 'Email notification queued successfully',
            'appointment_id': appointment_id,
            'task_id': task.id,
            'status': 'queued'
        }), 200
    except Exception as e:
        return jsonify({'error': f'Error sending email: {str(e)}'}), 500

# ===== SCHEDULED JOBS TEST ENDPOINTS =====

@bp.route('/test/send-daily-reminders', methods=['POST'])
@admin_required
def test_daily_reminders():
    """Test endpoint to trigger daily appointment reminders immediately"""
    try:
        from ..celery_tasks import send_daily_appointment_reminders
        result = send_daily_appointment_reminders.apply_async()
        
        return jsonify({
            'message': 'Daily reminder task triggered successfully',
            'task_id': result.id,
            'status': 'queued'
        }), 200
    except Exception as e:
        return jsonify({'error': f'Error triggering daily reminders: {str(e)}'}), 500

@bp.route('/test/send-monthly-reports', methods=['POST'])
@admin_required
def test_monthly_reports():
    """Test endpoint to trigger monthly doctor activity reports immediately"""
    try:
        from ..celery_tasks import send_monthly_doctor_reports
        result = send_monthly_doctor_reports.apply_async()
        
        return jsonify({
            'message': 'Monthly report task triggered successfully',
            'task_id': result.id,
            'status': 'queued'
        }), 200
    except Exception as e:
        return jsonify({'error': f'Error triggering monthly reports: {str(e)}'}), 500

@bp.route('/celery/task-result/<task_id>', methods=['GET'])
@admin_required
def get_task_result(task_id):
    """Get the result of a Celery task"""
    try:
        from ..celery_app import celery_app
        from celery.result import AsyncResult
        
        task_result = AsyncResult(task_id, app=celery_app)
        
        return jsonify({
            'task_id': task_id,
            'status': task_result.status,
            'result': str(task_result.result) if task_result.status == 'SUCCESS' else None,
            'error': str(task_result.info) if task_result.status == 'FAILURE' else None
        }), 200
    except Exception as e:
        return jsonify({'error': f'Error fetching task result: {str(e)}'}), 500
        return jsonify({'error': f'Error sending appointment emails: {str(e)}'}), 500