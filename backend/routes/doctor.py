from flask import Blueprint, request, jsonify
from flask_jwt_extended import jwt_required, get_jwt_identity
from datetime import datetime, timedelta, time
from sqlalchemy.orm import joinedload

from ..models import db, User, Doctor, Appointment, Treatment, DoctorAvailability
from ..utils.cache import cache_clear_pattern, cache_get, cache_set

bp = Blueprint('doctor', __name__, url_prefix='/api/doctor')

def doctor_required(fn):
    @jwt_required()
    def wrapper(*args, **kwargs):
        current_user_id = get_jwt_identity()
        user = User.query.get(int(current_user_id))
        
        if not user or user.role != 'doctor':
            return jsonify({'error': 'Doctor access required'}), 403
        return fn(*args, **kwargs)
    wrapper.__name__ = fn.__name__
    return wrapper

@bp.route('/dashboard', methods=['GET'])
@doctor_required
def get_dashboard():
    current_user_id = get_jwt_identity()
    user = User.query.get(int(current_user_id))
    doctor = user.doctor_profile
    
    if not doctor:
        return jsonify({'error': 'Doctor profile not found'}), 404
    
    today = datetime.now().date()
    week_end = today + timedelta(days=7)
    
    upcoming_appointments = Appointment.query.options(joinedload(Appointment.treatment)).filter(
        Appointment.doctor_id == doctor.id,
        Appointment.appointment_date >= today,
        Appointment.appointment_date <= week_end,
        Appointment.status == 'Booked'
    ).order_by(Appointment.appointment_date, Appointment.appointment_time).all()
    
    today_appointments = Appointment.query.options(joinedload(Appointment.treatment)).filter(
        Appointment.doctor_id == doctor.id,
        Appointment.appointment_date == today
    ).order_by(Appointment.appointment_time).all()
    
    total_patients = db.session.query(Appointment.patient_id).filter(
        Appointment.doctor_id == doctor.id
    ).distinct().count()
    
    return jsonify({
        'doctor': doctor.to_dict(),
        'upcoming_appointments': [apt.to_dict() for apt in upcoming_appointments],
        'today_appointments': [apt.to_dict() for apt in today_appointments],
        'total_patients': total_patients
    }), 200

@bp.route('/appointments', methods=['GET'])
@doctor_required
def get_appointments():
    current_user_id = get_jwt_identity()
    user = User.query.get(int(current_user_id))
    doctor = user.doctor_profile
    
    if not doctor:
        return jsonify({'error': 'Doctor profile not found'}), 404
    
    # Check cache first
    cache_key = f'appointments:doctor_{doctor.id}'
    cached_data = cache_get(cache_key)
    if cached_data:
        return jsonify({'appointments': cached_data, 'cached': True}), 200
    
    appointments = Appointment.query.options(joinedload(Appointment.treatment)).filter(
        Appointment.doctor_id == doctor.id
    ).order_by(Appointment.appointment_date.desc(), Appointment.appointment_time.desc()).all()
    
    appointments_data = [apt.to_dict() for apt in appointments]
    cache_set(cache_key, appointments_data, expiry=300)  # 5 minutes
    
    return jsonify({'appointments': appointments_data}), 200

@bp.route('/appointments/<int:appointment_id>/complete', methods=['POST'])
@doctor_required
def complete_appointment(appointment_id):
    current_user_id = get_jwt_identity()
    user = User.query.get(int(current_user_id))
    doctor = user.doctor_profile
    
    appointment = Appointment.query.get(appointment_id)
    if not appointment:
        return jsonify({'error': 'Appointment not found'}), 404
    
    if appointment.doctor_id != doctor.id:
        return jsonify({'error': 'Unauthorized'}), 403
    
    data = request.json
    if not data:
        return jsonify({'error': 'No data provided'}), 400
    
    # Validate required diagnosis field
    diagnosis = data.get('diagnosis', '').strip()
    if not diagnosis:
        return jsonify({'error': 'Diagnosis is required'}), 400
    
    try:
        appointment.status = 'Completed'
        
        if appointment.treatment:
            # Update existing treatment
            treatment = appointment.treatment
            treatment.diagnosis = diagnosis
            treatment.prescription = data.get('prescription', '').strip() or treatment.prescription
            treatment.notes = data.get('notes', '').strip() or treatment.notes
            if data.get('next_visit_date'):
                try:
                    treatment.next_visit_date = datetime.strptime(data.get('next_visit_date'), '%Y-%m-%d').date()
                except (ValueError, TypeError):
                    return jsonify({'error': 'Invalid date format for next_visit_date. Use YYYY-MM-DD'}), 400
        else:
            # Create new treatment
            try:
                next_visit = None
                if data.get('next_visit_date'):
                    next_visit = datetime.strptime(data.get('next_visit_date'), '%Y-%m-%d').date()
                
                treatment = Treatment(
                    appointment_id=appointment.id,
                    diagnosis=diagnosis,
                    prescription=data.get('prescription', '').strip() or None,
                    notes=data.get('notes', '').strip() or None,
                    next_visit_date=next_visit
                )
                db.session.add(treatment)
            except Exception as e:
                db.session.rollback()
                return jsonify({'error': f'Failed to create treatment record: {str(e)}'}), 500
        
        db.session.commit()
        
        # Clear cache - fix pattern to match actual cache keys
        cache_clear_pattern(f'appointments:patient_{appointment.patient_id}')
        cache_clear_pattern(f'appointments:doctor_{doctor.id}')
        
        return jsonify({
            'message': 'Appointment marked as completed',
            'appointment': appointment.to_dict(),
            'treatment': treatment.to_dict()
        }), 200
    except Exception as e:
        db.session.rollback()
        print(f"Error completing appointment: {str(e)}")
        return jsonify({'error': f'Failed to complete appointment: {str(e)}'}), 500

@bp.route('/appointments/<int:appointment_id>/cancel', methods=['POST'])
@doctor_required
def cancel_appointment(appointment_id):
    current_user_id = get_jwt_identity()
    user = User.query.get(int(current_user_id))
    doctor = user.doctor_profile
    
    appointment = Appointment.query.get(appointment_id)
    if not appointment:
        return jsonify({'error': 'Appointment not found'}), 404
    
    if appointment.doctor_id != doctor.id:
        return jsonify({'error': 'Unauthorized'}), 403
    
    appointment.status = 'Cancelled'
    
    # Notify patient about cancellation
    from ..models import Notification
    patient_user = appointment.patient.user
    notification = Notification(
        user_id=patient_user.id,
        message=f"❌ Dr. {doctor.user.full_name} cancelled your appointment on {appointment.appointment_date} at {appointment.appointment_time.strftime('%H:%M')}. Please contact the hospital to reschedule."
    )
    db.session.add(notification)
    db.session.commit()
    
    cache_clear_pattern(f'appointments:patient_{appointment.patient_id}:*')
    cache_clear_pattern(f'appointments:doctor_{doctor.id}:*')
    
    return jsonify({'message': 'Appointment cancelled', 'appointment': appointment.to_dict()}), 200

@bp.route('/patients/<int:patient_id>/history', methods=['GET'])
@doctor_required
def get_patient_history(patient_id):
    current_user_id = get_jwt_identity()
    user = User.query.get(int(current_user_id))
    doctor = user.doctor_profile
    
    # Get all completed appointments for this patient with this doctor
    appointments = Appointment.query.filter(
        Appointment.patient_id == patient_id,
        Appointment.doctor_id == doctor.id,
        Appointment.status == 'Completed'
    ).order_by(Appointment.appointment_date.desc()).all()
    
    history = []
    for apt in appointments:
        apt_data = apt.to_dict()
        if apt.treatment:
            apt_data['treatment'] = apt.treatment.to_dict()
        history.append(apt_data)
    
    return jsonify({'history': history}), 200

@bp.route('/treatments/<int:treatment_id>', methods=['PUT'])
@doctor_required
def update_treatment(treatment_id):
    current_user_id = get_jwt_identity()
    user = User.query.get(int(current_user_id))
    doctor = user.doctor_profile
    
    if not doctor:
        return jsonify({'error': 'Doctor profile not found'}), 404
    
    treatment = Treatment.query.get(treatment_id)
    if not treatment:
        return jsonify({'error': 'Treatment record not found'}), 404
    
    # Verify doctor owns this treatment record
    if treatment.appointment.doctor_id != doctor.id:
        return jsonify({'error': 'Unauthorized - not your patient'}), 403
    
    data = request.json
    
    # Track what changed
    changes = []
    
    # Update treatment fields
    if data.get('diagnosis') is not None:
        treatment.diagnosis = data.get('diagnosis')
        changes.append("Diagnosis")
    if data.get('prescription') is not None:
        treatment.prescription = data.get('prescription')
        changes.append("Prescription")
    if data.get('notes') is not None:
        treatment.notes = data.get('notes')
        changes.append("Doctor's notes")
    if data.get('next_visit_date'):
        treatment.next_visit_date = datetime.strptime(data.get('next_visit_date'), '%Y-%m-%d').date()
        changes.append(f"Next visit date: {data.get('next_visit_date')}")
    
    # Notify patient about treatment update with specific changes
    from ..models import Notification
    patient_user = treatment.appointment.patient.user
    changes_text = ", ".join(changes) if changes else "treatment details"
    notification = Notification(
        user_id=patient_user.id,
        message=f"📋 Dr. {doctor.user.full_name} updated your treatment record (Appointment: {treatment.appointment.appointment_date}). Updated: {changes_text}. Check your treatment history for full details."
    )
    db.session.add(notification)
    db.session.commit()
    
    # Clear all related caches
    cache_clear_pattern(f'appointments:patient_{treatment.appointment.patient_id}:*')
    cache_clear_pattern(f'appointments:doctor_{doctor.id}:*')
    cache_clear_pattern(f'history:patient_{treatment.appointment.patient_id}')
    cache_clear_pattern(f'patients:doctor_{doctor.id}')
    
    return jsonify({
        'message': 'Treatment record updated successfully',
        'treatment': treatment.to_dict()
    }), 200

@bp.route('/patients', methods=['GET'])
@doctor_required
def get_my_patients():
    """Get list of all patients who have appointments with this doctor"""
    current_user_id = get_jwt_identity()
    user = User.query.get(int(current_user_id))
    doctor = user.doctor_profile
    
    if not doctor:
        return jsonify({'error': 'Doctor profile not found'}), 404
    
    # Get unique patients who have had appointments with this doctor
    patient_ids = db.session.query(Appointment.patient_id).filter(
        Appointment.doctor_id == doctor.id
    ).distinct().all()
    
    patients = []
    for (patient_id,) in patient_ids:
        from ..models import Patient
        patient = Patient.query.get(patient_id)
        if patient:
            patient_data = patient.to_dict()
            # Add appointment stats
            total_appointments = Appointment.query.filter(
                Appointment.patient_id == patient_id,
                Appointment.doctor_id == doctor.id
            ).count()
            completed_appointments = Appointment.query.filter(
                Appointment.patient_id == patient_id,
                Appointment.doctor_id == doctor.id,
                Appointment.status == 'Completed'
            ).count()
            patient_data['total_appointments'] = total_appointments
            patient_data['completed_appointments'] = completed_appointments
            patients.append(patient_data)
    
    return jsonify({'patients': patients}), 200

@bp.route('/availability', methods=['GET'])
@doctor_required
def get_availability():
    current_user_id = get_jwt_identity()
    user = User.query.get(int(current_user_id))
    doctor = user.doctor_profile
    
    if not doctor:
        return jsonify({'error': 'Doctor profile not found'}), 404
    
    today = datetime.now().date()
    week_end = today + timedelta(days=7)
    
    availability = DoctorAvailability.query.filter(
        DoctorAvailability.doctor_id == doctor.id,
        DoctorAvailability.date >= today,
        DoctorAvailability.date <= week_end
    ).order_by(DoctorAvailability.date).all()
    
    return jsonify({'availability': [avail.to_dict() for avail in availability]}), 200

@bp.route('/availability', methods=['POST'])
@doctor_required
def set_availability():
    current_user_id = get_jwt_identity()
    user = User.query.get(int(current_user_id))
    doctor = user.doctor_profile
    
    if not doctor:
        return jsonify({'error': 'Doctor profile not found'}), 404
    
    data = request.json
    
    date_obj = datetime.strptime(data.get('date'), '%Y-%m-%d').date()
    start_time_obj = datetime.strptime(data.get('start_time'), '%H:%M').time()
    end_time_obj = datetime.strptime(data.get('end_time'), '%H:%M').time()
    
    existing = DoctorAvailability.query.filter_by(
        doctor_id=doctor.id,
        date=date_obj
    ).first()
    
    if existing:
        existing.start_time = start_time_obj
        existing.end_time = end_time_obj
        existing.is_available = data.get('is_available', True)
    else:
        availability = DoctorAvailability(
            doctor_id=doctor.id,
            date=date_obj,
            start_time=start_time_obj,
            end_time=end_time_obj,
            is_available=data.get('is_available', True)
        )
        db.session.add(availability)
    
    db.session.commit()
    
    return jsonify({'message': 'Availability updated successfully'}), 200

@bp.route('/availability/bulk', methods=['POST'])
@doctor_required
def set_bulk_availability():
    current_user_id = get_jwt_identity()
    user = User.query.get(int(current_user_id))
    doctor = user.doctor_profile
    
    if not doctor:
        return jsonify({'error': 'Doctor profile not found'}), 404
    
    data = request.json
    availability_list = data.get('availability', [])
    cancelled_count = 0
    rebooked_count = 0
    
    for avail_data in availability_list:
        date_obj = datetime.strptime(avail_data.get('date'), '%Y-%m-%d').date()
        start_time_obj = datetime.strptime(avail_data.get('start_time'), '%H:%M').time()
        end_time_obj = datetime.strptime(avail_data.get('end_time'), '%H:%M').time()
        is_available = avail_data.get('is_available', True)
        
        existing = DoctorAvailability.query.filter_by(
            doctor_id=doctor.id,
            date=date_obj
        ).first()
        
        if existing:
            existing.start_time = start_time_obj
            existing.end_time = end_time_obj
            existing.is_available = is_available
        else:
            availability = DoctorAvailability(
                doctor_id=doctor.id,
                date=date_obj,
                start_time=start_time_obj,
                end_time=end_time_obj,
                is_available=is_available
            )
            db.session.add(availability)
        
        # Handle appointments based on availability changes
        from ..models import Notification
        
        # Find all appointments on this date (both booked and cancelled)
        booked_appointments = Appointment.query.filter(
            Appointment.doctor_id == doctor.id,
            Appointment.appointment_date == date_obj,
            Appointment.status == 'Booked'
        ).all()
        
        cancelled_appointments = Appointment.query.filter(
            Appointment.doctor_id == doctor.id,
            Appointment.appointment_date == date_obj,
            Appointment.status == 'Cancelled'
        ).all()
        
        # Cancel booked appointments that conflict with new availability
        for apt in booked_appointments:
            should_cancel = False
            
            # If doctor marked entire day as unavailable
            if not is_available:
                should_cancel = True
                reason = f"Dr. {doctor.user.full_name} is not available on {date_obj.strftime('%Y-%m-%d')}"
            # If appointment time is outside available hours
            elif apt.appointment_time < start_time_obj or apt.appointment_time > end_time_obj:
                should_cancel = True
                reason = f"Dr. {doctor.user.full_name} changed availability hours. Now available {start_time_obj.strftime('%H:%M')}-{end_time_obj.strftime('%H:%M')}"
            
            if should_cancel:
                apt.status = 'Cancelled'
                cancelled_count += 1
                
                # Create notification for patient
                patient_user = apt.patient.user
                notification = Notification(
                    user_id=patient_user.id,
                    message=f"❌ Your appointment on {apt.appointment_date} at {apt.appointment_time.strftime('%H:%M')} with Dr. {doctor.user.full_name} has been cancelled. Reason: {reason}"
                )
                db.session.add(notification)
        
        # Re-book cancelled appointments if doctor becomes available again
        if is_available:
            for apt in cancelled_appointments:
                # Check if appointment time now falls within available hours
                if start_time_obj <= apt.appointment_time <= end_time_obj:
                    # Check if there's no conflict with other booked appointments
                    has_conflict = Appointment.query.filter(
                        Appointment.doctor_id == doctor.id,
                        Appointment.appointment_date == date_obj,
                        Appointment.appointment_time == apt.appointment_time,
                        Appointment.status == 'Booked',
                        Appointment.id != apt.id
                    ).first()
                    
                    if not has_conflict:
                        apt.status = 'Booked'
                        rebooked_count += 1
                        
                        # Create notification for patient
                        patient_user = apt.patient.user
                        notification = Notification(
                            user_id=patient_user.id,
                            message=f"✅ Good news! Your appointment on {apt.appointment_date} at {apt.appointment_time.strftime('%H:%M')} with Dr. {doctor.user.full_name} has been restored. The doctor is now available."
                        )
                        db.session.add(notification)
    
    db.session.commit()
    
    # Clear cache for doctor and all affected patients
    cache_clear_pattern(f'appointments:doctor_{doctor.id}:*')
    affected_patients = set()
    for apt in booked_appointments + cancelled_appointments:
        affected_patients.add(apt.patient_id)
    for patient_id in affected_patients:
        cache_clear_pattern(f'appointments:patient_{patient_id}:*')
    
    message = 'Availability updated successfully'
    if cancelled_count > 0:
        message += f'. {cancelled_count} appointment(s) cancelled'
    if rebooked_count > 0:
        if cancelled_count > 0:
            message += f' and {rebooked_count} appointment(s) restored'
        else:
            message += f'. {rebooked_count} appointment(s) restored'
    if cancelled_count > 0 or rebooked_count > 0:
        message += '. Patients have been notified.'
    
    return jsonify({
        'message': message, 
        'cancelled_appointments': cancelled_count,
        'rebooked_appointments': rebooked_count
    }), 200