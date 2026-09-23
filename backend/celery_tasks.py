from celery import Celery
from celery.schedules import crontab
from datetime import datetime, timedelta
import csv
import os

# Initialize celery without Flask app context initially
celery = Celery(__name__)

@celery.task(name='backend.celery_tasks.send_appointment_notification')
def send_appointment_notification(appointment_id):
    """Send appointment notification emails to both patient and doctor (manual trigger)"""
    from .app import app
    from .models import db, Appointment, Notification
    
    with app.app_context():
        appointment = Appointment.query.get(appointment_id)
        if not appointment:
            return f"Appointment {appointment_id} not found"
        
        from .utils.mailer import send_mail
        
        try:
            # Patient details
            patient_email = appointment.patient.user.email
            patient_name = appointment.patient.user.full_name
            
            # Doctor details
            doctor_email = appointment.doctor.user.email
            doctor_name = appointment.doctor.user.full_name
            department = appointment.doctor.department.name if appointment.doctor.department else 'General'
            
            # Appointment details
            appointment_date = appointment.appointment_date.strftime('%B %d, %Y')
            time_str = appointment.appointment_time.strftime('%I:%M %p')
            reason = appointment.reason or 'Not specified'
            
            # Email to Patient
            patient_body = f'''Dear {patient_name},

Your appointment has been confirmed by the hospital administration.

📋 Appointment Details:
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
👨‍⚕️ Doctor: Dr. {doctor_name}
🏥 Department: {department}
📅 Date: {appointment_date}
🕐 Time: {time_str}
📝 Reason: {reason}
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

⏰ Please arrive 10 minutes before your scheduled time.
💊 Bring any relevant medical documents or reports.
📱 If you need to reschedule, please contact us as soon as possible.

Best regards,
Hospital Management System
'''
            
            # Email to Doctor
            doctor_body = f'''Dear Dr. {doctor_name},

A new appointment has been scheduled for your review.

📋 Appointment Details:
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
👤 Patient: {patient_name}
📱 Patient Contact: {appointment.patient.user.phone or 'Not provided'}
📧 Patient Email: {patient_email}
📅 Date: {appointment_date}
🕐 Time: {time_str}
📝 Reason for Visit: {reason}
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

Please review the appointment details and prepare for the consultation.

Best regards,
Hospital Management System
'''
            
            # Send email to patient
            patient_ok = send_mail(
                subject=f'✅ Appointment Confirmed - Dr. {doctor_name}',
                recipients=[patient_email],
                body=patient_body
            )
            
            # Send email to doctor
            doctor_ok = send_mail(
                subject=f'📅 New Appointment Scheduled - {patient_name}',
                recipients=[doctor_email],
                body=doctor_body
            )
            
            if not patient_ok or not doctor_ok:
                raise Exception('One or more emails failed to dispatch')
            
            # Create in-app notifications
            patient_notification = Notification(
                user_id=appointment.patient.user_id,
                message=f'✅ Appointment confirmed with Dr. {doctor_name} on {appointment_date} at {time_str}'
            )
            
            doctor_notification = Notification(
                user_id=appointment.doctor.user_id,
                message=f'📅 New appointment scheduled with {patient_name} on {appointment_date} at {time_str}'
            )
            
            db.session.add(patient_notification)
            db.session.add(doctor_notification)
            db.session.commit()
            
            print(f"✓ Appointment notification emails sent for appointment {appointment_id}")
            return f"Emails sent successfully for appointment {appointment_id}"
        except Exception as e:
            print(f"✗ Error sending appointment notification for {appointment_id}: {str(e)}")
            return f"Error sending emails: {str(e)}"

@celery.task(name='backend.celery_tasks.send_daily_appointment_reminders')
def send_daily_appointment_reminders():
    """Send daily email reminders to patients with appointments today at 9 AM"""
    # Import inside function to avoid circular imports
    from .app import app
    from .models import db, Appointment, Notification
    
    with app.app_context():
        today = datetime.now().date()
        
        appointments = Appointment.query.filter(
            Appointment.appointment_date == today,
            Appointment.status == 'Booked'
        ).all()
        
        from .utils.mailer import send_mail
        
        sent_count = 0
        for appointment in appointments:
            try:
                patient_email = appointment.patient.user.email
                patient_name = appointment.patient.user.full_name
                doctor_name = appointment.doctor.user.full_name
                time_str = appointment.appointment_time.strftime('%I:%M %p')
                department = appointment.doctor.department.name if appointment.doctor.department else 'General'
                
                ok = send_mail(
                    subject='🏥 Appointment Reminder - Today',
                    recipients=[patient_email],
                    body=f'''Dear {patient_name},

This is a reminder that you have an appointment scheduled TODAY.

📋 Appointment Details:
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
👨‍⚕️ Doctor: Dr. {doctor_name}
🏥 Department: {department}
📅 Date: {today.strftime('%B %d, %Y')} (Today)
🕐 Time: {time_str}
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

⏰ Please arrive 10 minutes before your scheduled time.
📱 If you need to reschedule, please contact us as soon as possible.

Best regards,
Hospital Management System
'''
                )
                
                if not ok:
                    raise Exception('Mail dispatch failed')
                
                # Also create in-app notification
                notification = Notification(
                    user_id=appointment.patient.user_id,
                    message=f'Reminder: You have an appointment today at {time_str} with Dr. {doctor_name}'
                )
                db.session.add(notification)
                
                sent_count += 1
                print(f"✓ Reminder sent to {patient_name} for appointment at {time_str}")
            except Exception as e:
                print(f"✗ Error sending reminder for appointment {appointment.id}: {str(e)}")
        
        db.session.commit()
        return f"Sent {sent_count} reminders out of {len(appointments)} appointments"

@celery.task(name='backend.celery_tasks.send_monthly_doctor_reports')
def send_monthly_doctor_reports():
    """Generate and send monthly activity reports to all doctors on the 1st of each month"""
    # Import inside function to avoid circular imports
    from .app import app
    from .models import db, Appointment, Doctor, Treatment
    
    with app.app_context():
        now = datetime.now()
        # Get last month's date range
        last_month = now.replace(day=1) - timedelta(days=1)
        start_date = last_month.replace(day=1)
        end_date = last_month.replace(day=28) + timedelta(days=4)  # Last day of month
        end_date = end_date.replace(day=1) - timedelta(days=1)
        
        doctors = Doctor.query.join(Doctor.user).filter_by(is_active=True).all()
        
        from .utils.mailer import send_mail
        
        sent_count = 0
        for doctor in doctors:
            try:
                appointments = Appointment.query.filter(
                    Appointment.doctor_id == doctor.id,
                    Appointment.appointment_date >= start_date,
                    Appointment.appointment_date <= end_date
                ).all()
                
                if not appointments:
                    print(f"⊘ No appointments for Dr. {doctor.user.full_name} in {last_month.strftime('%B %Y')}")
                    continue
                
                completed = [apt for apt in appointments if apt.status == 'Completed']
                cancelled = [apt for apt in appointments if apt.status == 'Cancelled']
                booked = [apt for apt in appointments if apt.status == 'Booked']
                
                # Get diagnosis and treatment details
                treatments_html = ""
                for apt in completed:
                    if apt.treatment:
                        treatments_html += f'''
                        <tr>
                            <td>{apt.appointment_date.strftime('%Y-%m-%d')}</td>
                            <td>{apt.patient.user.full_name}</td>
                            <td>{apt.treatment.diagnosis[:100]}...</td>
                            <td>{apt.treatment.prescription[:100] if apt.treatment.prescription else 'N/A'}...</td>
                        </tr>
                        '''
                
                report_html = f'''
                <html>
                <head>
                    <style>
                        body {{ font-family: Arial, sans-serif; margin: 20px; }}
                        h2 {{ color: #2c3e50; border-bottom: 3px solid #3498db; padding-bottom: 10px; }}
                        h3 {{ color: #34495e; margin-top: 30px; }}
                        .summary {{ background: #ecf0f1; padding: 20px; border-radius: 5px; margin: 20px 0; }}
                        .summary p {{ margin: 10px 0; font-size: 16px; }}
                        table {{ width: 100%; border-collapse: collapse; margin-top: 20px; }}
                        th {{ background: #3498db; color: white; padding: 12px; text-align: left; }}
                        td {{ padding: 10px; border-bottom: 1px solid #ddd; }}
                        .stat {{ display: inline-block; margin: 10px 20px 10px 0; }}
                        .stat-value {{ font-size: 32px; font-weight: bold; color: #3498db; }}
                        .stat-label {{ color: #7f8c8d; font-size: 14px; }}
                    </style>
                </head>
                <body>
                    <h2>📊 Monthly Activity Report - {last_month.strftime('%B %Y')}</h2>
                    <p>Dear Dr. {doctor.user.full_name},</p>
                    <p>Here is your comprehensive activity report for last month.</p>
                    
                    <div class="summary">
                        <h3>📈 Summary Statistics</h3>
                        <div class="stat">
                            <div class="stat-value">{len(appointments)}</div>
                            <div class="stat-label">Total Appointments</div>
                        </div>
                        <div class="stat">
                            <div class="stat-value">{len(completed)}</div>
                            <div class="stat-label">Completed</div>
                        </div>
                        <div class="stat">
                            <div class="stat-value">{len(cancelled)}</div>
                            <div class="stat-label">Cancelled</div>
                        </div>
                        <div class="stat">
                            <div class="stat-value">{len(booked)}</div>
                            <div class="stat-label">Pending</div>
                        </div>
                    </div>
                    
                    <h3>📋 Treatment Details (Completed Appointments)</h3>
                    <table>
                        <thead>
                            <tr>
                                <th>Date</th>
                                <th>Patient</th>
                                <th>Diagnosis</th>
                                <th>Prescription</th>
                            </tr>
                        </thead>
                        <tbody>
                            {treatments_html if treatments_html else '<tr><td colspan="4">No completed treatments</td></tr>'}
                        </tbody>
                    </table>
                    
                    <p style="margin-top: 40px; color: #7f8c8d;">
                        This report was automatically generated on {now.strftime('%B %d, %Y')}.<br>
                        For any questions, please contact the hospital administration.
                    </p>
                </body>
                </html>
                '''
                
                ok = send_mail(
                    subject=f'📊 Monthly Activity Report - {last_month.strftime("%B %Y")}',
                    recipients=[doctor.user.email],
                    html=report_html
                )
                
                if not ok:
                    raise Exception('Mail dispatch failed')
                sent_count += 1
                print(f"✓ Monthly report sent to Dr. {doctor.user.full_name} ({len(appointments)} appointments)")
            except Exception as e:
                print(f"✗ Error sending report for doctor {doctor.id}: {str(e)}")
        
        return f"Sent reports to {sent_count} doctors"

@celery.task(name='backend.celery_tasks.export_patient_treatments')
def export_patient_treatments(job_id):
    """Export patient treatment history as CSV - async job"""
    # Import inside function to avoid circular imports
    from .app import app
    from .models import db, Appointment, Treatment, ExportJob, Notification
    
    with app.app_context():
        export_job = ExportJob.query.get(job_id)
        if not export_job:
            return "Job not found"
        
        try:
            export_job.status = 'Processing'
            db.session.commit()
            
            patient = export_job.patient
            
            appointments = Appointment.query.filter(
                Appointment.patient_id == patient.id,
                Appointment.status == 'Completed'
            ).order_by(Appointment.appointment_date.desc()).all()
            
            # Create exports directory if it doesn't exist
            exports_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'backend', 'exports')
            os.makedirs(exports_dir, exist_ok=True)
            
            filename = f'patient_{patient.id}_treatments_{datetime.now().strftime("%Y%m%d_%H%M%S")}.csv'
            file_path = os.path.join(exports_dir, filename)
            
            # Write CSV file
            with open(file_path, 'w', newline='', encoding='utf-8') as csvfile:
                fieldnames = [
                    'User ID', 'Username', 'Patient Name', 'Consulting Doctor', 
                    'Department', 'Appointment Date', 'Appointment Time', 
                    'Diagnosis', 'Prescription', 'Treatment Notes', 'Next Visit Date'
                ]
                writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
                writer.writeheader()
                
                for apt in appointments:
                    treatment = apt.treatment
                    writer.writerow({
                        'User ID': patient.user_id,
                        'Username': patient.user.username,
                        'Patient Name': patient.user.full_name,
                        'Consulting Doctor': apt.doctor.user.full_name,
                        'Department': apt.doctor.department.name if apt.doctor.department else 'N/A',
                        'Appointment Date': apt.appointment_date.strftime('%Y-%m-%d'),
                        'Appointment Time': apt.appointment_time.strftime('%H:%M'),
                        'Diagnosis': treatment.diagnosis if treatment else 'N/A',
                        'Prescription': treatment.prescription if treatment else 'N/A',
                        'Treatment Notes': treatment.notes if treatment else 'N/A',
                        'Next Visit Date': treatment.next_visit_date.strftime('%Y-%m-%d') if treatment and treatment.next_visit_date else 'N/A'
                    })
            
            export_job.status = 'Completed'
            export_job.file_path = filename
            export_job.completed_at = datetime.utcnow()
            
            # Create notification for patient
            notification = Notification(
                user_id=patient.user_id,
                message=f'Your treatment history export is ready! File: {filename}'
            )
            db.session.add(notification)
            db.session.commit()
            
            print(f"✓ Export completed for patient {patient.id}: {filename}")
            return f"Export completed: {filename}"
        except Exception as e:
            export_job.status = 'Failed'
            db.session.commit()
            print(f"✗ Export failed for job {job_id}: {str(e)}")
            return f"Export failed: {str(e)}"

def make_celery(app):
    """Create Celery instance with Flask app context"""
    # Use get() with fallback values to avoid KeyError
    celery = Celery(
        app.import_name,
        broker=app.config.get('broker_url', 'redis://localhost:6379/0'),
        backend=app.config.get('result_backend', 'redis://localhost:6379/0')
    )
    celery.conf.update(app.config)
    
    class ContextTask(celery.Task):
        def __call__(self, *args, **kwargs):
            with app.app_context():
                return self.run(*args, **kwargs)
    
    celery.Task = ContextTask
    return celery  