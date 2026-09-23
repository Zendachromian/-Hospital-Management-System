from flask import Blueprint, request, jsonify
from flask_jwt_extended import jwt_required, get_jwt_identity
from datetime import datetime, timedelta
from sqlalchemy import or_
from sqlalchemy.orm import joinedload

from ..models import db, User, Patient, Doctor, Department, Appointment, Treatment
from ..utils.cache import cache_get, cache_set, cache_clear_pattern

# ============ HELPER FUNCTIONS ============

def luhn_algorithm(card_number):
    """
    Validate credit card number using Luhn algorithm
    Returns True if valid, False otherwise
    """
    def digits_of(n):
        return [int(d) for d in str(n)]
    
    digits = digits_of(card_number)
    odd_digits = digits[-1::-2]
    even_digits = digits[-2::-2]
    
    checksum = sum(odd_digits)
    for d in even_digits:
        checksum += sum(digits_of(d * 2))
    
    return checksum % 10 == 0

# ============ BLUEPRINT & DECORATORS ============

bp = Blueprint('patient', __name__, url_prefix='/api/patient')

def patient_required(fn):
    @jwt_required()
    def wrapper(*args, **kwargs):
        current_user_id = get_jwt_identity()
        user = User.query.get(int(current_user_id))
        
        if not user or user.role != 'patient':
            return jsonify({'error': 'Patient access required'}), 403
        return fn(*args, **kwargs)
    wrapper.__name__ = fn.__name__
    return wrapper

@bp.route('/dashboard', methods=['GET'])
@patient_required
def get_dashboard():
    current_user_id = get_jwt_identity()
    user = User.query.get(int(current_user_id))
    patient = user.patient_profile
    
    if not patient:
        return jsonify({'error': 'Patient profile not found'}), 404
    
    # Get upcoming appointments
    upcoming_appointments = Appointment.query.options(joinedload(Appointment.treatment)).filter(
        Appointment.patient_id == patient.id,
        Appointment.appointment_date >= datetime.now().date(),
        Appointment.status == 'Booked'
    ).order_by(Appointment.appointment_date, Appointment.appointment_time).all()
    
    # Get departments with doctor counts
    departments = Department.query.all()
    departments_data = []
    for dept in departments:
        dept_data = dept.to_dict()
        dept_data['doctors_count'] = Doctor.query.filter_by(department_id=dept.id).count()
        departments_data.append(dept_data)
    
    return jsonify({
        'patient': patient.to_dict(),
        'upcoming_appointments': [apt.to_dict() for apt in upcoming_appointments],
        'departments': departments_data
    }), 200

@bp.route('/profile', methods=['GET'])
@patient_required
def get_patient_profile():
    current_user_id = get_jwt_identity()
    user = User.query.get(int(current_user_id))
    patient = user.patient_profile
    
    if not patient:
        return jsonify({'error': 'Patient profile not found'}), 404
    
    return jsonify({'patient': patient.to_dict()}), 200

@bp.route('/departments', methods=['GET'])
@patient_required
def get_departments():
    departments = Department.query.all()
    departments_data = []
    for dept in departments:
        dept_data = dept.to_dict()
        dept_data['doctors_count'] = Doctor.query.filter_by(department_id=dept.id).count()
        departments_data.append(dept_data)
    
    return jsonify({'departments': departments_data}), 200

@bp.route('/doctors', methods=['GET'])
@patient_required
def get_doctors():
    department_id = request.args.get('department_id')
    search_query = request.args.get('search', '').strip()
    
    query = Doctor.query.join(User).filter(User.is_active == True)
    
    if department_id:
        query = query.filter(Doctor.department_id == department_id)
    
    if search_query:
        query = query.filter(
            or_(
                User.full_name.ilike(f'%{search_query}%'),
                Doctor.id.cast(db.String).ilike(f'%{search_query}%'),
                Doctor.specialization.ilike(f'%{search_query}%')
            )
        )
    
    # Check cache for doctors list (only if no search query)
    cache_key = f'doctors:list:{department_id or "all"}'
    if not search_query:
        cached_data = cache_get(cache_key)
        if cached_data:
            return jsonify({'doctors': cached_data, 'cached': True}), 200
    
    doctors = query.all()
    doctors_data = [doc.to_dict() for doc in doctors]
    
    # Cache only if no search query
    if not search_query:
        cache_set(cache_key, doctors_data, expiry=600)  # 10 minutes
    
    return jsonify({'doctors': doctors_data}), 200

@bp.route('/appointments', methods=['GET'])
@patient_required
def get_appointments():
    current_user_id = get_jwt_identity()
    user = User.query.get(int(current_user_id))
    patient = user.patient_profile
    
    if not patient:
        return jsonify({'error': 'Patient profile not found'}), 404
    
    # Check cache first
    cache_key = f'appointments:patient_{patient.id}'
    cached_data = cache_get(cache_key)
    if cached_data:
        return jsonify({'appointments': cached_data, 'cached': True}), 200
    
    appointments = Appointment.query.options(joinedload(Appointment.treatment)).filter_by(patient_id=patient.id).order_by(
        Appointment.appointment_date.desc(), 
        Appointment.appointment_time.desc()
    ).all()
    
    appointments_data = [apt.to_dict() for apt in appointments]
    cache_set(cache_key, appointments_data, expiry=300)  # 5 minutes
    
    return jsonify({'appointments': appointments_data}), 200

@bp.route('/appointments', methods=['POST'])
@patient_required
def book_appointment():
    current_user_id = get_jwt_identity()
    user = User.query.get(int(current_user_id))
    patient = user.patient_profile
    
    if not patient:
        return jsonify({'error': 'Patient profile not found'}), 404
    
    data = request.json
    
    # Check if doctor exists
    doctor = Doctor.query.get(data.get('doctor_id'))
    if not doctor:
        return jsonify({'error': 'Doctor not found'}), 404
    
    # Parse date and time
    try:
        appointment_date = datetime.strptime(data.get('appointment_date'), '%Y-%m-%d').date()
        appointment_time = datetime.strptime(data.get('appointment_time'), '%H:%M').time()
    except ValueError:
        return jsonify({'error': 'Invalid date or time format'}), 400
    
    # Check if appointment is in the future
    appointment_datetime = datetime.combine(appointment_date, appointment_time)
    if appointment_datetime <= datetime.now():
        return jsonify({'error': 'Appointment must be in the future'}), 400
    
    # Check if patient already has an appointment at this time
    patient_conflict = Appointment.query.filter(
        Appointment.patient_id == patient.id,
        Appointment.appointment_date == appointment_date,
        Appointment.appointment_time == appointment_time,
        Appointment.status == 'Booked'
    ).first()
    
    if patient_conflict:
        return jsonify({'error': 'You already have an appointment at this time'}), 400
    
    # Check if doctor is available at this time (existing appointments)
    doctor_conflict = Appointment.query.filter(
        Appointment.doctor_id == doctor.id,
        Appointment.appointment_date == appointment_date,
        Appointment.appointment_time == appointment_time,
        Appointment.status == 'Booked'
    ).first()
    
    if doctor_conflict:
        return jsonify({'error': 'Doctor is not available at this time'}), 400
    
    # Check doctor's availability schedule
    from ..models import DoctorAvailability
    doctor_availability = DoctorAvailability.query.filter(
        DoctorAvailability.doctor_id == doctor.id,
        DoctorAvailability.date == appointment_date,
        DoctorAvailability.is_available == True
    ).first()
    
    if doctor_availability:
        # Check if appointment time is within doctor's available hours
        if not (doctor_availability.start_time <= appointment_time <= doctor_availability.end_time):
            return jsonify({
                'error': f'Doctor is only available from {doctor_availability.start_time.strftime("%H:%M")} to {doctor_availability.end_time.strftime("%H:%M")} on this date'
            }), 400
    else:
        # If no availability record exists, check if date has availability marked as unavailable
        unavailable = DoctorAvailability.query.filter(
            DoctorAvailability.doctor_id == doctor.id,
            DoctorAvailability.date == appointment_date,
            DoctorAvailability.is_available == False
        ).first()
        
        if unavailable:
            return jsonify({'error': 'Doctor is not available on this date'}), 400
    
    # Prevent booking past-time slots
    appointment_datetime = datetime.combine(appointment_date, appointment_time)
    if appointment_datetime <= datetime.now():
        return jsonify({'error': 'Cannot book a slot in the past'}), 400
    
    # Create appointment
    appointment = Appointment(
        patient_id=patient.id,
        doctor_id=doctor.id,
        appointment_date=appointment_date,
        appointment_time=appointment_time,
        reason=data.get('reason', ''),
        status='Booked'
    )
    
    db.session.add(appointment)
    
    # Notify doctor about new appointment
    from ..models import Notification
    doctor_notification = Notification(
        user_id=doctor.user.id,
        message=f"📅 New appointment booked! Patient {patient.user.full_name} scheduled an appointment on {appointment_date} at {appointment_time.strftime('%H:%M')}. Reason: {data.get('reason', 'Not specified')}"
    )
    db.session.add(doctor_notification)
    
    # Notify patient about successful booking
    patient_notification = Notification(
        user_id=patient.user.id,
        message=f"✅ Your appointment with Dr. {doctor.user.full_name} has been confirmed for {appointment_date} at {appointment_time.strftime('%H:%M')}."
    )
    db.session.add(patient_notification)
    
    db.session.commit()
    
    # Clear all related caches (including slots)
    cache_clear_pattern(f'appointments:patient_{patient.id}')
    cache_clear_pattern(f'appointments:doctor_{doctor.id}')
    cache_clear_pattern(f'patients:doctor_{doctor.id}')
    cache_clear_pattern('admin:dashboard:stats')
    cache_clear_pattern(f'appointments:doctor_{doctor.id}:*')
    cache_clear_pattern(f'slots:doctor_{doctor.id}:*')  # Clear slots cache for this doctor
    
    return jsonify({
        'message': 'Appointment booked successfully',
        'appointment': appointment.to_dict()
    }), 201

@bp.route('/appointments/<int:appointment_id>', methods=['PUT'])
@patient_required
def update_appointment(appointment_id):
    current_user_id = get_jwt_identity()
    user = User.query.get(int(current_user_id))
    patient = user.patient_profile
    
    if not patient:
        return jsonify({'error': 'Patient profile not found'}), 404
    
    appointment = Appointment.query.get(appointment_id)
    
    if not appointment:
        return jsonify({'error': 'Appointment not found'}), 404
    
    if appointment.patient_id != patient.id:
        return jsonify({'error': 'Unauthorized'}), 403
    
    if appointment.status != 'Booked':
        return jsonify({'error': 'Only booked appointments can be edited'}), 400
    
    data = request.json
    
    # Parse new date and time
    try:
        new_date = datetime.strptime(data.get('appointment_date'), '%Y-%m-%d').date()
        new_time = datetime.strptime(data.get('appointment_time'), '%H:%M').time()
    except (ValueError, TypeError):
        return jsonify({'error': 'Invalid date or time format'}), 400
    
    # Check if appointment is in the future
    appointment_datetime = datetime.combine(new_date, new_time)
    if appointment_datetime <= datetime.now():
        return jsonify({'error': 'Appointment must be in the future'}), 400
    
    # Check if patient already has an appointment at the new time (excluding current appointment)
    patient_conflict = Appointment.query.filter(
        Appointment.patient_id == patient.id,
        Appointment.appointment_date == new_date,
        Appointment.appointment_time == new_time,
        Appointment.status == 'Booked',
        Appointment.id != appointment_id
    ).first()
    
    if patient_conflict:
        return jsonify({'error': 'You already have an appointment at this time'}), 400
    
    # Check if doctor is available at the new time (excluding current appointment)
    doctor_conflict = Appointment.query.filter(
        Appointment.doctor_id == appointment.doctor_id,
        Appointment.appointment_date == new_date,
        Appointment.appointment_time == new_time,
        Appointment.status == 'Booked',
        Appointment.id != appointment_id
    ).first()
    
    if doctor_conflict:
        return jsonify({'error': 'Doctor is not available at this time'}), 400
    
    # Check doctor's availability schedule for the new date/time
    from ..models import DoctorAvailability
    doctor_availability = DoctorAvailability.query.filter(
        DoctorAvailability.doctor_id == appointment.doctor_id,
        DoctorAvailability.date == new_date,
        DoctorAvailability.is_available == True
    ).first()
    
    if doctor_availability:
        # Check if new appointment time is within doctor's available hours
        if not (doctor_availability.start_time <= new_time <= doctor_availability.end_time):
            return jsonify({
                'error': f'Doctor is only available from {doctor_availability.start_time.strftime("%H:%M")} to {doctor_availability.end_time.strftime("%H:%M")} on this date'
            }), 400
    else:
        # If no availability record exists, check if date has availability marked as unavailable
        unavailable = DoctorAvailability.query.filter(
            DoctorAvailability.doctor_id == appointment.doctor_id,
            DoctorAvailability.date == new_date,
            DoctorAvailability.is_available == False
        ).first()
        
        if unavailable:
            return jsonify({'error': 'Doctor is not available on this date'}), 400
    
    # Update appointment
    appointment.appointment_date = new_date
    appointment.appointment_time = new_time
    if data.get('reason') is not None:
        appointment.reason = data.get('reason')
    
    db.session.commit()
    
    # Clear cache (including slots for both old and new dates)
    cache_clear_pattern(f'appointments:patient_{patient.id}')
    cache_clear_pattern(f'appointments:doctor_{appointment.doctor_id}')
    cache_clear_pattern(f'slots:doctor_{appointment.doctor_id}:*')  # Clear slots cache
    
    return jsonify({
        'message': 'Appointment updated successfully',
        'appointment': appointment.to_dict()
    }), 200

@bp.route('/appointments/<int:appointment_id>', methods=['DELETE'])
@patient_required
def cancel_appointment(appointment_id):
    current_user_id = get_jwt_identity()
    user = User.query.get(int(current_user_id))
    patient = user.patient_profile
    
    if not patient:
        return jsonify({'error': 'Patient profile not found'}), 404
    
    appointment = Appointment.query.get(appointment_id)
    
    if not appointment:
        return jsonify({'error': 'Appointment not found'}), 404
    
    if appointment.patient_id != patient.id:
        return jsonify({'error': 'Unauthorized'}), 403
    
    if appointment.status != 'Booked':
        return jsonify({'error': 'Only booked appointments can be cancelled'}), 400
    
    appointment.status = 'Cancelled'
    db.session.commit()
    
    # Clear cache (including slots)
    cache_clear_pattern(f'appointments:patient_{patient.id}')
    cache_clear_pattern(f'appointments:doctor_{appointment.doctor_id}')
    cache_clear_pattern(f'slots:doctor_{appointment.doctor_id}:*')  # Clear slots cache
    
    return jsonify({'message': 'Appointment cancelled successfully'}), 200


@bp.route('/doctors/<int:doctor_id>/availability-batch', methods=['POST'])
@patient_required
def get_doctor_availability_batch(doctor_id):
    """Batch check availability for multiple dates (prevents N+1 API calls)"""
    from ..models import DoctorAvailability
    doctor = Doctor.query.get(doctor_id)
    if not doctor:
        return jsonify({'error': 'Doctor not found'}), 404

    data = request.get_json() or {}
    dates = data.get('dates', [])
    
    if not dates or not isinstance(dates, list):
        return jsonify({'error': 'dates array required in request body'}), 400
    
    if len(dates) > 60:  # Limit to 60 dates per request
        return jsonify({'error': 'Maximum 60 dates allowed per request'}), 400
    
    availability = {}
    
    # Parse dates and fetch availability records
    parsed_dates = []
    for date_str in dates:
        try:
            date_obj = datetime.strptime(date_str, '%Y-%m-%d').date()
            parsed_dates.append(date_obj)
        except ValueError:
            return jsonify({'error': f'Invalid date format: {date_str}, expected YYYY-MM-DD'}), 400
    
    # Batch query for all dates
    records = DoctorAvailability.query.filter(
        DoctorAvailability.doctor_id == doctor.id,
        DoctorAvailability.date.in_(parsed_dates),
        DoctorAvailability.is_available == True
    ).all()
    
    # Build availability map
    for date_obj in parsed_dates:
        has_slots = any(r.date == date_obj for r in records)
        availability[date_obj.isoformat()] = has_slots
    
    return jsonify({'doctor_id': doctor_id, 'availability': availability}), 200

@bp.route('/doctors/<int:doctor_id>/slots', methods=['GET'])
@patient_required
def get_doctor_slots(doctor_id):
    """Return 30-min slots for a given doctor and date, excluding past-time and already booked slots."""
    from ..models import DoctorAvailability
    
    date_str = request.args.get('date')
    if not date_str:
        return jsonify({'error': 'date query param required (YYYY-MM-DD)'}), 400
    try:
        target_date = datetime.strptime(date_str, '%Y-%m-%d').date()
    except ValueError:
        return jsonify({'error': 'Invalid date format, expected YYYY-MM-DD'}), 400

    # Check cache first (slots cache for 2 minutes to avoid stale data)
    cache_key = f'slots:doctor_{doctor_id}:{date_str}'
    cached_slots = cache_get(cache_key)
    if cached_slots is not None:
        return jsonify(cached_slots), 200

    doctor = Doctor.query.get(doctor_id)
    if not doctor:
        return jsonify({'error': 'Doctor not found'}), 404

    # Check availability record
    availability = DoctorAvailability.query.filter(
        DoctorAvailability.doctor_id == doctor.id,
        DoctorAvailability.date == target_date,
        DoctorAvailability.is_available == True
    ).first()
    if not availability:
        result = {'slots': [], 'message': 'Doctor not available on this date', 'date': date_str, 'doctor_id': doctor_id}
        cache_set(cache_key, result, expiry=120)  # Cache empty slots (2 min)
        return jsonify(result), 200

    # Generate 30-min slots between start_time and end_time
    start_dt = datetime.combine(target_date, availability.start_time)
    end_dt = datetime.combine(target_date, availability.end_time)

    # Exclude past-time slots for today
    now = datetime.now()
    slot = start_dt
    slots = []

    # Fetch existing booked appointments for the date
    existing = Appointment.query.filter(
        Appointment.doctor_id == doctor.id,
        Appointment.appointment_date == target_date,
        Appointment.status == 'Booked'
    ).all()
    booked_times = {datetime.combine(target_date, a.appointment_time) for a in existing}

    while slot <= end_dt:
        # Skip past slots
        if slot <= now:
            slot += timedelta(minutes=30)
            continue
        # Skip booked slots
        if slot in booked_times:
            slot += timedelta(minutes=30)
            continue
        slots.append(slot.strftime('%H:%M'))
        slot += timedelta(minutes=30)

    result = {'date': target_date.strftime('%Y-%m-%d'), 'doctor_id': doctor_id, 'slots': slots}
    cache_set(cache_key, result, expiry=120)  # Cache for 2 minutes
    return jsonify(result), 200

@bp.route('/doctors/<int:doctor_id>/profile', methods=['GET'])
@patient_required
def get_doctor_profile(doctor_id):
    doctor = Doctor.query.get(doctor_id)
    if not doctor:
        return jsonify({'error': 'Doctor not found'}), 404
    
    return jsonify({'doctor': doctor.to_dict()}), 200

@bp.route('/doctors/availability', methods=['GET'])
@patient_required
def get_doctors_availability():
    """Get 7-day availability for all active doctors"""
    from ..models import DoctorAvailability
    
    today = datetime.now().date()
    end_date = today + timedelta(days=7)
    
    # Get all active doctors
    doctors = Doctor.query.join(User).filter(User.is_active == True).all()
    
    doctors_availability = []
    for doctor in doctors:
        doctor_data = doctor.to_dict()
        
        # Get availability for next 7 days
        availability = DoctorAvailability.query.filter(
            DoctorAvailability.doctor_id == doctor.id,
            DoctorAvailability.date >= today,
            DoctorAvailability.date < end_date
        ).order_by(DoctorAvailability.date).all()
        
        doctor_data['availability'] = [avail.to_dict() for avail in availability]
        doctors_availability.append(doctor_data)
    
    return jsonify({'doctors': doctors_availability}), 200

@bp.route('/history', methods=['GET'])
@patient_required
def get_treatment_history():
    current_user_id = get_jwt_identity()
    user = User.query.get(int(current_user_id))
    patient = user.patient_profile
    
    if not patient:
        return jsonify({'error': 'Patient profile not found'}), 404
    
    # Check cache first
    cache_key = f'history:patient_{patient.id}'
    cached_data = cache_get(cache_key)
    if cached_data:
        return jsonify({'history': cached_data, 'cached': True}), 200
    
    appointments = Appointment.query.filter(
        Appointment.patient_id == patient.id,
        Appointment.status == 'Completed'
    ).order_by(Appointment.appointment_date.desc()).all()
    
    history = []
    for apt in appointments:
        apt_data = apt.to_dict()
        if apt.treatment:
            apt_data['treatment'] = apt.treatment.to_dict()
        history.append(apt_data)
    
    cache_set(cache_key, history, expiry=600)  # 10 minutes
    
    return jsonify({'history': history}), 200

@bp.route('/export', methods=['POST'])
@patient_required
def export_treatments():
    """Trigger async CSV export job for patient treatment history"""
    current_user_id = get_jwt_identity()
    user = User.query.get(int(current_user_id))
    patient = user.patient_profile
    
    if not patient:
        return jsonify({'error': 'Patient profile not found'}), 404
    
    # Import here to avoid circular imports
    from ..models import ExportJob, Notification
    from ..celery_tasks import export_patient_treatments
    
    try:
        # Create export job record
        export_job = ExportJob(
            patient_id=patient.id,
            status='Pending'
        )
        db.session.add(export_job)
        db.session.commit()
        
        # Trigger async Celery task
        export_patient_treatments.delay(export_job.id)
        
        # Create notification
        notification = Notification(
            user_id=user.id,
            message='Your treatment history export has been started. You will be notified when it is ready.'
        )
        db.session.add(notification)
        db.session.commit()
        
        return jsonify({
            'message': 'Export job started successfully',
            'job_id': export_job.id
        }), 202
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': f'Failed to start export: {str(e)}'}), 500

@bp.route('/export/<int:job_id>', methods=['GET'])
@patient_required
def get_export_status(job_id):
    """Check status of export job"""
    current_user_id = get_jwt_identity()
    user = User.query.get(int(current_user_id))
    patient = user.patient_profile
    
    from ..models import ExportJob
    
    export_job = ExportJob.query.filter_by(
        id=job_id,
        patient_id=patient.id
    ).first()
    
    if not export_job:
        return jsonify({'error': 'Export job not found'}), 404
    
    return jsonify(export_job.to_dict()), 200

@bp.route('/export/<int:job_id>/download', methods=['GET'])
@patient_required
def download_export(job_id):
    """Download completed export file"""
    from flask import send_file
    import os
    
    current_user_id = get_jwt_identity()
    user = User.query.get(int(current_user_id))
    patient = user.patient_profile
    
    from ..models import ExportJob
    
    export_job = ExportJob.query.filter_by(
        id=job_id,
        patient_id=patient.id
    ).first()
    
    if not export_job:
        return jsonify({'error': 'Export job not found'}), 404
    
    if export_job.status != 'Completed':
        return jsonify({'error': 'Export is not yet completed', 'status': export_job.status}), 400
    
    file_path = os.path.join(
        os.path.dirname(os.path.dirname(os.path.dirname(__file__))),
        'backend', 'exports', export_job.file_path
    )
    
    if not os.path.exists(file_path):
        return jsonify({'error': 'Export file not found'}), 404
    
    return send_file(
        file_path,
        as_attachment=True,
        download_name=export_job.file_path,
        mimetype='text/csv'
    )

# ===== PAYMENT PORTAL =====

@bp.route('/completed-appointments', methods=['GET'])
@patient_required
def get_completed_appointments():
    """Get booked and completed appointments available for payment"""
    current_user_id = get_jwt_identity()
    user = User.query.get(int(current_user_id))
    patient = user.patient_profile
    
    if not patient:
        return jsonify({'error': 'Patient profile not found'}), 404
    
    from ..models import Payment
    
    # Get booked and completed appointments without existing payments
    appointments = Appointment.query.filter(
        Appointment.patient_id == patient.id,
        Appointment.status.in_(['Booked', 'Completed'])
    ).order_by(Appointment.appointment_date.desc()).all()
    
    result = []
    for apt in appointments:
        # Check if already paid
        paid = Payment.query.filter_by(appointment_id=apt.id).first()
        
        # Only show unpaid appointments
        if not paid:
            result.append({
                'id': apt.id,
                'doctor_name': apt.doctor.user.full_name,
                'department': apt.doctor.department.name if apt.doctor.department else 'General',
                'appointment_date': apt.appointment_date.isoformat(),
                'appointment_time': apt.appointment_time.strftime('%H:%M') if apt.appointment_time else '',
                'diagnosis': apt.treatment.diagnosis if apt.treatment else 'General Consultation',
                'consultation_fee': apt.doctor.consultation_fee or 500,
                'appointment_status': apt.status,
                'is_paid': False
            })
    
    return jsonify({'appointments': result}), 200

@bp.route('/process-payment', methods=['POST'])
@patient_required
def process_payment():
    """Process dummy payment for completed treatment"""
    current_user_id = get_jwt_identity()
    user = User.query.get(int(current_user_id))
    patient = user.patient_profile
    
    if not patient:
        return jsonify({'error': 'Patient profile not found'}), 404
    
    data = request.get_json()
    appointment_id = data.get('appointment_id')
    card_holder_name = data.get('card_holder_name')
    card_number = data.get('card_number')
    amount = data.get('amount')
    
    # Validation - Check all required fields
    if not all([appointment_id, card_holder_name, card_number, amount]):
        return jsonify({'error': 'Missing required fields'}), 400
    
    # APPOINTMENT_ID VALIDATION
    try:
        appointment_id = int(appointment_id)
    except (ValueError, TypeError):
        return jsonify({'error': 'Invalid appointment ID (must be numeric)'}), 400
    
    appointment = Appointment.query.get(appointment_id)
    if not appointment or appointment.patient_id != patient.id:
        return jsonify({'error': 'Appointment not found or unauthorized'}), 404
    
    # CARDHOLDER NAME VALIDATION
    if not isinstance(card_holder_name, str):
        return jsonify({'error': 'Cardholder name must be text'}), 400
    
    card_holder_name = card_holder_name.strip()
    if len(card_holder_name) < 2 or len(card_holder_name) > 50:
        return jsonify({'error': 'Cardholder name must be 2-50 characters'}), 400
    
    if not card_holder_name.replace(' ', '').isalpha():
        return jsonify({'error': 'Cardholder name must contain only letters and spaces'}), 400
    
    # CARD NUMBER VALIDATION
    if not isinstance(card_number, str):
        return jsonify({'error': 'Card number must be text'}), 400
    
    card_number_clean = card_number.replace(' ', '').replace('-', '')
    if not card_number_clean.isdigit():
        return jsonify({'error': 'Card number must contain only digits'}), 400
    
    if len(card_number_clean) != 16:
        return jsonify({'error': 'Card number must be exactly 16 digits'}), 400
    
    # Validate using Luhn Algorithm
    if not luhn_algorithm(card_number_clean):
        return jsonify({'error': 'Card number is invalid (failed validation)'}), 400
    
    # Check for obviously fake test cards (all same digits)
    if len(set(card_number_clean)) == 1:
        return jsonify({'error': 'Card number cannot contain all identical digits'}), 400
    
    # AMOUNT VALIDATION
    try:
        amount_float = float(amount)
    except (ValueError, TypeError):
        return jsonify({'error': 'Amount must be numeric'}), 400
    
    # Check amount is positive and reasonable
    if amount_float <= 0:
        return jsonify({'error': 'Amount must be greater than 0'}), 400
    
    if amount_float > 999999:
        return jsonify({'error': 'Amount exceeds maximum limit (₹999,999)'}), 400
    
    # Verify amount matches appointment consultation fee
    expected_amount = appointment.doctor.consultation_fee or 500
    if abs(amount_float - expected_amount) > 0.01:  # Allow for floating point differences
        return jsonify({'error': 'Amount does not match appointment fee'}), 400
    
    from ..models import Payment
    import uuid
    
    # Check if payment already exists
    existing_payment = Payment.query.filter_by(appointment_id=appointment_id).first()
    if existing_payment:
        return jsonify({'error': 'Payment already processed for this appointment'}), 400
    
    try:
        # Create dummy payment (no actual processing)
        card_last_four = card_number_clean[-4:] if len(card_number_clean) >= 4 else '****'
        transaction_id = f"TXN-{uuid.uuid4().hex[:12].upper()}"
        
        payment = Payment(
            appointment_id=appointment_id,
            patient_id=patient.id,
            amount=amount_float,
            payment_method='card',
            card_holder_name=card_holder_name,
            card_last_four=card_last_four,
            transaction_id=transaction_id,
            status='Completed',
            notes=f'Payment processed for diagnosis: {appointment.treatment.diagnosis if appointment.treatment else "N/A"}'
        )
        
        db.session.add(payment)
        db.session.commit()
        
        return jsonify({
            'message': 'Payment processed successfully',
            'payment_id': payment.id,
            'transaction_id': transaction_id,
            'amount': payment.amount,
            'status': payment.status
        }), 200
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': f'Payment processing failed: {str(e)}'}), 500

@bp.route('/payment-history', methods=['GET'])
@patient_required
def get_payment_history():
    """Get patient's payment history"""
    current_user_id = get_jwt_identity()
    user = User.query.get(int(current_user_id))
    patient = user.patient_profile
    
    if not patient:
        return jsonify({'error': 'Patient profile not found'}), 404
    
    from ..models import Payment
    
    payments = Payment.query.filter_by(patient_id=patient.id).order_by(
        Payment.created_at.desc()
    ).all()
    
    history = []
    for payment in payments:
        apt = payment.appointment
        history.append({
            'id': payment.id,
            'transaction_id': payment.transaction_id,
            'appointment_date': apt.appointment_date.isoformat(),
            'doctor_name': apt.doctor.user.full_name,
            'amount': payment.amount,
            'status': payment.status,
            'card_last_four': payment.card_last_four,
            'created_at': payment.created_at.isoformat() if payment.created_at else None
        })
    
    return jsonify({'payments': history}), 200