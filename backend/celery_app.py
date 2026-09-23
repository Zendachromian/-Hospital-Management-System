from celery import Celery
from celery.schedules import crontab
import os

def make_celery():
    # Set the default Django settings module for the 'celery' program.
    os.environ.setdefault('FORKED_BY_MULTIPROCESSING', '1')
    
    celery = Celery(
        'backend',
        broker='redis://localhost:6379/0',
        backend='redis://localhost:6379/0',
        include=['backend.celery_tasks']
    )
    
    # Configuration with proper scheduling
    celery.conf.update(
        result_expires=3600,
        timezone='UTC',
        enable_utc=True,
        beat_schedule={
            # Daily reminders - every day at 9:00 AM
            'send-daily-reminders': {
                'task': 'backend.celery_tasks.send_daily_appointment_reminders',
                'schedule': crontab(hour=9, minute=0),  # 9:00 AM daily
            },
            # Monthly reports on 1st of every month at 8:00 AM
            'send-monthly-reports': {
                'task': 'backend.celery_tasks.send_monthly_doctor_reports',
                'schedule': crontab(day_of_month=1, hour=8, minute=0),  # 1st of month at 8:00 AM
            },
        }
    )
    
    return celery

# Create the Celery app instance
celery_app = make_celery()

if __name__ == '__main__':
    celery_app.start()