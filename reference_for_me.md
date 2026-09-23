# 📚 Hospital Management System - Complete Reference Guide

---

# 🚀 QUICKSTART GUIDE

## Starting the Application

### Single Command Startup (Recommended)
```bash
./run.sh
```

This starts all 5 services automatically:
1. **Redis Server** (Port 6379) - Caching & message broker
2. **Flask Backend API** (Port 5000) - REST API
3. **Frontend Server** (Port 8080) - Vue.js SPA
4. **Celery Worker** - Background jobs
5. **Celery Beat** - Scheduled tasks

### Stopping the Application
Press `Ctrl+C` in the terminal where `run.sh` is running, or:
```bash
./stop.sh
```

## What You'll See on Startup

```
═══════════════════════════════════════════════
   🏥 Hospital Management System - Startup    
═══════════════════════════════════════════════

📦 Checking dependencies...
Starting services...

[1/5] Starting Redis Server (Port 6379)...
  ✓  Redis started successfully

[2/5] Starting Backend API (Port 5000)...
  ✓  Backend API started successfully

[3/5] Starting Frontend Server (Port 8080)...
  ✓  Frontend server started successfully

[4/5] Starting Celery Worker (Background Jobs)...
  ✓  Celery Worker started successfully

[5/5] Starting Celery Beat (Scheduled Tasks)...
  ✓  Celery Beat started successfully

═══════════════════════════════════════════════

📊 Service URLs:
  Frontend:     http://localhost:8080
  Backend API:  http://localhost:5000/api
  Health Check: http://localhost:5000/api/health
  Redis:        localhost:6379

👤 Admin Credentials:
  Username: admin
  Password: admin123
```

## Testing the Setup

### 1. Check Health Endpoint
```bash
curl http://localhost:5000/api/health
```

### 2. Check Redis
```bash
redis-cli ping
```

### 3. Access Frontend
Open browser: http://localhost:8080

### 4. Login as Admin
- Username: `admin`
- Password: `admin123`

### 5. Check Logs
```bash
tail -f logs/backend.log          # Backend API logs
tail -f logs/celery_worker.log    # Background jobs
tail -f logs/celery_beat.log      # Scheduled tasks
```

## Troubleshooting

### Port Already in Use
```bash
# Check what's using a port
lsof -i :5000    # Backend
lsof -i :8080    # Frontend
lsof -i :6379    # Redis

# Kill process on port
kill -9 $(lsof -t -i:5000)
```

### Redis Not Starting
```bash
# Check if Redis is installed
which redis-server

# Start Redis manually
redis-server

# Check Redis status
redis-cli ping
```

### Clean Restart
```bash
./stop.sh
pkill -f "celery"
pkill -f "redis-server"
pkill -f "backend.app"
rm -rf .pids/*
./run.sh
```

---

# 🔧 CELERY SETUP - Backend Jobs

## Overview

This application uses Celery for asynchronous task processing and scheduled jobs.

### Scheduled Jobs (Celery Beat)
- **Daily Appointment Reminders**: Runs every day at 9:00 AM
- **Monthly Doctor Reports**: Runs on the 1st of each month at 8:00 AM

### Async Jobs (On-Demand)
- **CSV Export**: Patient treatment history export triggered by users

## Prerequisites

1. **Redis Server** (must be running)
   ```bash
   sudo systemctl start redis
   # OR
   redis-server
   ```

2. **Python Dependencies**
   ```bash
   source .venv/bin/activate
   pip install celery redis flask-mail
   ```

## Running Celery Manually

### Terminal 1: Flask Application
```bash
cd /home/zendachromian/extracted/mad02*
source .venv/bin/activate
python -m backend.app
```

### Terminal 2: Celery Worker (for async jobs)
```bash
cd /home/zendachromian/extracted/mad02*
source .venv/bin/activate
celery -A backend.celery_app.celery_app worker --loglevel=info
```

### Terminal 3: Celery Beat (for scheduled jobs)
```bash
cd /home/zendachromian/extracted/mad02*
source .venv/bin/activate
celery -A backend.celery_app.celery_app beat --loglevel=info
```

### Terminal 4: Frontend Server
```bash
cd /home/zendachromian/extracted/mad02*/frontend
python -m http.server 8080
```

## Scheduled Jobs Details

### 📅 Daily Appointment Reminders
- **Schedule**: Every day at 9:00 AM
- **Task**: `backend.celery_tasks.send_daily_appointment_reminders`
- **Function**: Checks all appointments for today with status='Booked' and sends email reminders to patients
- **Email Content**: 
  - Patient name and appointment details
  - Doctor name and department
  - Date and time
  - Reminder to arrive 10 minutes early
- **In-App Notification**: Also creates notification in the system

**Manual Test Run**:
```bash
# In Python shell
from backend.celery_tasks import send_daily_appointment_reminders
from backend.app import app
with app.app_context():
    result = send_daily_appointment_reminders()
    print(result)
```

### 📊 Monthly Doctor Reports
- **Schedule**: 1st of every month at 8:00 AM
- **Task**: `backend.celery_tasks.send_monthly_doctor_reports`
- **Function**: Generates HTML report for each doctor containing:
  - Total appointments last month
  - Completed, cancelled, pending counts
  - Table of all completed appointments

**Manual Test Run**:
```bash
# In Python shell
from backend.celery_tasks import send_monthly_doctor_reports
from backend.app import app
with app.app_context():
    result = send_monthly_doctor_reports()
    print(result)
```

## Async Job Details

### 📥 CSV Export (User-Triggered)
- **Trigger**: Patient clicks "Export to CSV" button in Treatment History page
- **Task**: `backend.celery_tasks.export_patient_treatments`
- **Process**:
  1. Creates `ExportJob` record with status='Pending'
  2. Triggers Celery task in background
  3. Task updates status to 'Processing'
  4. Generates CSV file with all completed appointments
  5. Updates status to 'Completed' and creates notification
  6. Frontend polls for completion and triggers download

**CSV Contains**:
- User ID, Username, Patient Name
- Consulting Doctor, Department
- Appointment Date & Time
- Diagnosis, Prescription, Treatment Notes
- Next Visit Date

**Export Location**: `backend/exports/patient_{id}_treatments_{timestamp}.csv`

**API Endpoints**:
- `POST /api/patient/export` - Start export job
- `GET /api/patient/export/<job_id>` - Check job status
- `GET /api/patient/export/<job_id>/download` - Download completed CSV

## Monitoring and Debugging

### Check Celery Worker Status
```bash
celery -A backend.celery_app.celery_app inspect active
```

### Check Scheduled Tasks
```bash
celery -A backend.celery_app.celery_app inspect scheduled
```

### View Celery Beat Schedule
```bash
celery -A backend.celery_app.celery_app inspect registered
```

### Redis Monitoring
```bash
redis-cli
> KEYS *
> GET celery-task-meta-<task_id>
```

### Check Export Jobs in Database
```python
from backend.app import app
from backend.models import ExportJob, db

with app.app_context():
    jobs = ExportJob.query.all()
    for job in jobs:
        print(f"Job {job.id}: {job.status} - {job.file_path}")
```

## Caching Implementation

### Cache Keys and TTL
- `appointments:patient_{id}` - **5 minutes** (patient appointments)
- `appointments:doctor_{id}` - **5 minutes** (doctor appointments)
- `slots:doctor_{id}:{date}` - **2 minutes** (available slots)
- `doctors:list:{dept_id}` - **10 minutes** (doctors list)
- `history:patient_{id}` - **10 minutes** (treatment history)
- `patients:doctor_{id}` - **15 minutes** (doctor's patients)
- `admin:dashboard:stats` - **5 minutes** (dashboard statistics)

### Cache Invalidation
Cache is automatically cleared when:
- New appointment is booked
- Appointment is cancelled/completed
- Treatment record is updated
- Doctor availability is changed
- Doctor/Patient profile is updated

### Manual Cache Clear
```python
from backend.utils.cache import cache_clear_pattern, cache_delete

# Clear all appointment caches
cache_clear_pattern('appointments:*')

# Clear specific cache
cache_delete('admin:dashboard:stats')
```

## Production Tips

1. **Increase Workers**: For production, run multiple workers
   ```bash
   celery -A backend.celery_app.celery_app worker --concurrency=4
   ```

2. **Monitor Queue Length**:
   ```bash
   celery -A backend.celery_app.celery_app inspect stats
   ```

3. **Enable Flower** (Celery monitoring tool):
   ```bash
   pip install flower
   celery -A backend.celery_app.celery_app flower
   # Access at http://localhost:5555
   ```

## Troubleshooting

| Issue | Solution |
|-------|----------|
| Tasks not executing | Ensure both worker AND beat are running |
| Email not sending | Check MAIL_* environment variables |
| Redis connection refused | `sudo systemctl start redis` |
| Export CSV not downloading | Check `backend/exports/` directory exists |
| Cache not working | Verify Redis running: `redis-cli ping` |

---

# 📧 EMAIL SETUP

## Quick Setup

### Option 1: Interactive Setup (Recommended)
```bash
./setup_email.sh
```

### Option 2: Manual Setup

#### For Gmail:
```bash
export MAIL_USERNAME='your-email@gmail.com'
export MAIL_PASSWORD='your-16-char-app-password'
```

#### For Other SMTP:
```bash
export MAIL_SERVER='smtp.yourserver.com'
export MAIL_PORT='587'
export MAIL_USE_TLS='True'
export MAIL_USERNAME='your-email@example.com'
export MAIL_PASSWORD='your-password'
```

## Testing Email

### Test with Script:
```bash
source .env  # If you used setup_email.sh
python3 test_email.py
```

### Manual Test:
```bash
source .venv/bin/activate
python3 << EOF
from backend.app import app
from flask_mail import Message, Mail

with app.app_context():
    mail = Mail(app)
    msg = Message(
        subject='Test Email',
        sender=('Hospital Management System', 'donotreply@hms.com'),
        recipients=['recipient@example.com'],
        body='This is a test email'
    )
    mail.send(msg)
    print('✓ Email sent!')
EOF
```

## Email Schedule

| Task | Schedule | Time Zone |
|------|----------|-----------|
| **Daily Reminders** | Every day at 9:00 AM | UTC |
| **Monthly Reports** | 1st of month at 8:00 AM | UTC |

## Configuration Files

- **Email Settings**: `backend/config.py`
- **Daily Reminders**: `backend/celery_tasks.py` (line 10)
- **Monthly Reports**: `backend/celery_tasks.py` (line 77)
- **Schedule**: `backend/celery_app.py` (line 17)

## Sender Information

All emails are sent from:
- **Display Name**: Hospital Management System
- **Email Address**: donotreply@hms.com

## Troubleshooting

### Gmail Issues

1. **"Username and Password not accepted"**
   - Use App Password (16 characters), NOT your regular password
   - Enable 2FA first: https://myaccount.google.com/security
   - Generate App Password: https://myaccount.google.com/apppasswords

2. **"Less secure app access" error**
   - Google deprecated this - use App Password instead

3. **Emails not sending**
   - Check Celery worker is running: `ps aux | grep celery`
   - Check logs: `tail -f logs/celery_worker.log`
   - Verify credentials: `python3 test_email.py`

### Other SMTP Issues

1. **Connection timeout**
   - Check firewall settings
   - Verify SMTP server and port
   - Try port 465 with SSL instead of 587 with TLS

2. **Authentication failed**
   - Verify username and password
   - Some servers require full email as username
   - Check if SMTP auth is enabled

## Restart After Configuration

After setting up email credentials:
```bash
# Stop services
pkill -f celery
pkill -f flask

# Apply environment variables
source .env

# Restart services
./run.sh
```

---

# ⚡ INSTANT EMAIL SETUP

## Configuration Script
```bash
python3 configure_and_test_email.py
```

## For Gmail Users
1. Go to: https://myaccount.google.com/security
2. Enable 2-Factor Authentication (if not already done)
3. Go to: https://myaccount.google.com/apppasswords
4. Select "Mail" and "Windows Computer"
5. Copy the **16-character password**
6. Run the script and enter:
   - Your Gmail address: `your-email@gmail.com`
   - Your App Password: `xxxx xxxx xxxx xxxx` (the 16 characters)

## For Other Providers
Run the script and select option 2, then enter:
- SMTP server address
- SMTP port (usually 587 or 465)
- Your username and password

## Verification

After configuration:
1. Restart the system: `./stop.sh && ./run.sh`
2. Login as admin
3. Go to Appointments
4. Click "Send Email" on any appointment
5. Email should arrive instantly!

## Configuration Details

Settings are saved in `.env` file:
- `MAIL_SERVER` - SMTP server address
- `MAIL_PORT` - SMTP port (usually 587)
- `MAIL_USE_TLS` - Use TLS (True/False)
- `MAIL_USERNAME` - Your email/username
- `MAIL_PASSWORD` - Your password or app password

## Troubleshooting Email

### Gmail Says "Password not accepted"
- ✅ Use **App Password** (16 characters), NOT regular password
- ✅ Enable 2FA first
- ✅ Generate password at: https://myaccount.google.com/apppasswords

### Emails still not sending
- Check `.env` file exists: `cat .env`
- Restart Flask: `./stop.sh && ./run.sh`
- Check logs: `cat logs/celery_worker.log`

### Port/Connection errors
- Try port 465 with SSL instead of 587 with TLS
- Check firewall isn't blocking outgoing SMTP
- Verify credentials are exactly correct

---

# 🌐 LANDING PAGE & FRONTEND SETUP

## System Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                         Browser (User)                           │
└────────────┬──────────────────────────────────────────────┬─────┘
             │                                              │
        ┌────▼─────────────────┐                  ┌────────▼────────┐
        │  Frontend Server     │                  │ Backend API     │
        │  Port 8080           │                  │ Port 5000       │
        │                      │                  │                 │
        │ /           landing  │◄─────────────────►│ /api/*  routes  │
        │ /app        main app │   (CORS enabled)  │                 │
        │ /static/*   files    │                  │ /api/health ✓   │
        │ /manifest   PWA      │                  │                 │
        └──────────────────────┘                  └─────────────────┘
```

## Port Configuration

```
Frontend (Port 8080):
├── http://localhost:8080/              → Landing Page
└── http://localhost:8080/app           → Main Vue.js Application

Backend API (Port 5000):
├── http://localhost:5000/api           → All API endpoints
└── http://localhost:5000/api/health    → Health check

Other Services:
└── Redis: localhost:6379
```

## File Structure

```
frontend/
├── templates/
│   ├── landing.html          ✨ Argon-inspired landing page
│   └── index.html            📱 Main Vue.js application
├── static/
│   └── css/
│       ├── style.css         🎨 Modern main CSS (1049 lines)
│       └── landing.css       🎨 Landing page CSS (703 lines)
├── manifest.json             📦 PWA manifest
├── service-worker.js         🔄 Service worker
└── server.py                 🔧 Routing logic

backend/
├── app.py                    🔌 API server (port 5000)
├── __init__.py               ✅ Cleaned: No landing page route
└── routes/
    ├── auth.py               🔐 Authentication API
    ├── admin.py              👔 Admin API
    ├── doctor.py             🩺 Doctor API
    └── patient.py            🏥 Patient API
```

## Access Points

### 1️⃣ Landing Page (First Time Visitors)
**URL:** `http://localhost:8080`
- Beautiful design
- Hospital features showcase
- Team introduction
- Sign In button → Redirects to `/app`

### 2️⃣ Main Application (Authenticated Users)
**URL:** `http://localhost:8080/app`
- Vue.js dashboard
- Doctor management
- Patient management
- Appointments & treatments

### 3️⃣ API Backend (Application Data)
**URL:** `http://localhost:5000/api`
- Authentication endpoints
- CRUD operations
- Health checks

## Navigation Flow

```
Visits http://localhost:8080
        │
        ▼
   ┌─────────────┐
   │   Landing   │
   │    Page     │
   └─────────────┘
        │
        │ Click "Sign In"
        ▼
   ┌─────────────────┐
   │  Check Token    │
   │  in Database    │
   └────────┬────────┘
            │
    ┌───────┴────────┐
    │                │
No Token         Has Token
    │                │
    ▼                ▼
┌────────────┐  ┌────────────┐
│   Login    │  │ Dashboard  │
│   Screen   │  │            │
└────────────┘  └────────────┘
```

## Landing Page Features

✨ **Modern Design Elements:**
- Diagonal wave-shaped sections
- Animated floating icons
- Smooth scroll navigation
- Feature cards (6 total)
- Service highlights
- Team member profiles
- Statistics showcase
- Professional footer

📱 **Fully Responsive:**
- Mobile (<480px)
- Tablet (480px-768px)
- Desktop (>768px)

## Key Statistics On Landing

- **500+** Hospitals Using HMS
- **50K+** Active Users
- **1M+** Appointments Managed
- **99.9%** Uptime Guarantee

## How to Start Services

### Start Backend (Terminal 1)
```bash
cd /home/zendachromian/extracted/mad02*
python3 -m backend.app
```

### Start Frontend (Terminal 2)
```bash
cd /home/zendachromian/extracted/mad02*/frontend
python3 server.py
```

### Start Celery Workers (Terminal 3) - Optional
```bash
cd /home/zendachromian/extracted/mad02*
celery -A backend.celery_app worker -l info
```

## Verification Commands

```bash
# Check Frontend Landing Page
curl http://localhost:8080/ | grep -c "section-shaped"

# Check Frontend App
curl http://localhost:8080/app | grep -c "id=\"app\""

# Check Backend API
curl http://localhost:5000/api/health | grep healthy

# Verify Redis Connection
redis-cli ping

# Check Celery Status
celery -A backend.celery_app inspect active
```

## User Journey

```
1. NEW USER
   ↓
   Visits http://localhost:8080
   ↓
   Sees professional landing page
   ↓
   Clicks "Sign In" or "Get Started"
   ↓
   Redirected to /app (main application)
   ↓
   Authentication form shown
   ↓
   Logs in with credentials
   ↓
   Accesses dashboard based on role

2. RETURNING USER
   ↓
   Visits http://localhost:8080/app directly
   ↓
   Checks local token
   ↓
   If valid → Dashboard
   ↓
   If invalid → Login screen
```

## Troubleshooting

| Issue | Solution |
|-------|----------|
| Port 8080 already in use | `sudo lsof -i :8080` then `kill -9 <PID>` |
| Port 5000 already in use | `sudo lsof -i :5000` then `kill -9 <PID>` |
| CORS errors | Check backend CORS config for port 8080 |
| Landing page not showing | Verify `server.py` routing logic |
| API not responding | Check backend logs: `tail logs/backend.log` |
| Redis connection failed | Verify Redis running: `redis-cli ping` |

---

# 📧 LOCAL EMAIL CONFIGURATION

## Configuration Applied

Your HMS is configured to send emails using a **Local Mail Transfer Agent (MTA)** approach, which requires **NO credentials**.

## Email Sending Priority

The email system tries methods in this order:

### 1️⃣ **Local MTA (localhost:25)** - Primary
- No credentials needed
- Works with any MTA (Postfix, Exim, Sendmail, etc.)

### 2️⃣ **Mail Command** - Fallback
- Uses system mail utility (`mail.mailutils`)
- Available on most Unix/Linux systems

### 3️⃣ **SendGrid API** - If configured
- Requires `SENDGRID_API_KEY` environment variable

### 4️⃣ **Flask-Mail SMTP** - Legacy support
- Requires SMTP credentials (Gmail, Office365, etc.)

### 5️⃣ **.eml File Fallback** - Last resort
- Emails saved to: `backend/exports/emails_outbox/`
- Format: `email_[sender]_[recipient].eml`

## Current Configuration

```conf
MAIL_SERVER = localhost
MAIL_PORT = 25
MAIL_USE_TLS = False
MAIL_USERNAME = (empty - no credentials needed)
MAIL_PASSWORD = (empty - no credentials needed)
MAIL_DEFAULT_SENDER = Hospital Management System <donotreply@hms.com>
```

**File**: `backend/config.py`

## Testing Email Sending

### Test Script
```bash
cd /home/zendachromian/extracted/mad02*
source .venv/bin/activate
python3 test_local_email.py
```

### Manual Test with Python
```bash
source .venv/bin/activate
python3 << 'EOF'
import sys
sys.path.insert(0, 'backend')

from backend.app import app
from backend.utils.mailer import send_mail

with app.app_context():
    result = send_mail(
        subject='Test Email',
        recipients=['your-email@example.com'],
        body='This is a test email',
        sender=('HMS', 'donotreply@hms.com')
    )
    print(f"Email sent: {result}")
EOF
```

## What Happens When Email is Sent

### If localhost:25 Available (Ideal)
```
✓ Email queued with local MTA
✓ MTA handles delivery to recipient
✓ No credentials needed
```

### If mail.mailutils Available (Current)
```
✓ Email passed to mail command
✓ Mail command queues for delivery
✓ No credentials needed
```

### If Nothing Available (Fallback)
```
✓ Email saved as .eml file
⚠️  File in: backend/exports/emails_outbox/
⚠️  Email is NOT sent to recipient
✓ Useful for testing/debugging
```

## Installation Status

- ✅ `mailutils` installed (provides `mail` command)
- ⚠️ `postfix` NOT installed
- ⚠️ `exim4` NOT installed

## Optional: Install Full Mail Server

### Install Exim4 (lightweight)
```bash
sudo apt-get install -y exim4
sudo dpkg-reconfigure exim4-config  # Choose "Internet Site"
```

### Install Postfix
```bash
sudo apt-get install -y postfix
# During setup choose: "Internet Site"
```

## Email Logs

Check logs for email activity:
- Location: `logs/` directory (if enabled)
- Entries start with: "Attempting to send email via..."
- Success indicators: "✓ Email sent via..."

## Troubleshooting

### "Email sent but recipient didn't receive"
- Check local mail queue: `mailq` or `sendmail -bp`
- Or check if running with mail.mailutils fallback
- Emails in `/backend/exports/emails_outbox/` are NOT delivered

### "Connection refused on localhost:25"
- MTA not running
- Will automatically try mail command instead
- Check logs for which method succeeded

### "Permission denied" errors
- mail.mailutils permissions issue
- Run Flask app with proper user
- Or install full mail server

## For Production

1. **Install full MTA** (Postfix/Exim):
   ```bash
   sudo apt-get install postfix
   sudo dpkg-reconfigure exim4-config
   ```

2. **Configure DNS records** (SPF, DKIM, DMARC)

3. **Monitor mail queue**:
   ```bash
   mailq          # View queue
   postfix flush  # Force delivery attempts
   ```

## Summary

- ✅ Email system configured for **local MTA approach**
- ✅ **No credentials required**
- ✅ `mail.mailutils` available as fallback
- ✅ Emails sent via system mail command
- ✅ Safe fallback to `.eml` files if needed
- ✅ Ready to test with `test_local_email.py`

---

# 📋 ADDITIONAL TIPS

## Features to Test

### Patient Features
1. Register new patient account
2. Login and view dashboard
3. Search for doctors by name/specialization
4. Book appointment with available doctor
5. View appointment history
6. Export treatment history to CSV
7. View notifications

### Doctor Features
1. Login with doctor credentials (created by admin)
2. View dashboard with statistics
3. See all appointments
4. Complete appointments with diagnosis
5. View patient list
6. View patient treatment history
7. Update treatment records

### Admin Features
1. Login with admin/admin123
2. View dashboard with charts
3. Add new doctors
4. Add new patients
5. Manage departments
6. Search doctors and patients
7. View all appointments
8. Update profiles

### Background Jobs
1. **Daily Reminders**: Create appointment for today, check email at 9 AM
2. **Monthly Reports**: Wait for 1st of month or trigger manually
3. **CSV Export**: Click export button, wait for notification, download file

## Performance Tips

1. **Increase Workers**: For production, run multiple workers
   ```bash
   celery -A backend.celery_app worker --concurrency=4
   ```

2. **Monitor Queue Length**:
   ```bash
   celery -A backend.celery_app inspect stats
   ```

3. **Adjust Cache TTL**: Modify `expiry` parameter in `cache_set()` calls

4. **Enable Flower** (Celery monitoring tool):
   ```bash
   pip install flower
   celery -A backend.celery_app flower
   # Access at http://localhost:5555
   ```

## Success Checklist

- [ ] Redis server is running (redis-cli ping returns PONG)
- [ ] Backend API responds on http://localhost:5000/api/health
- [ ] Frontend loads at http://localhost:8080
- [ ] Can login as admin (admin/admin123)
- [ ] Can see dashboard with statistics
- [ ] Celery worker log shows "ready"
- [ ] Celery beat log shows scheduled tasks
- [ ] Can create and view appointments
- [ ] Cache is working (check response times)
- [ ] Notifications appear for users
- [ ] Slots update correctly after booking
- [ ] Email configuration tested

## Key Directories

- `backend/` - Flask API application
- `frontend/` - Vue.js UI application
- `logs/` - Application logs
- `backend/exports/` - CSV exports and email outbox
- `backend/models/` - Database models
- `backend/routes/` - API route handlers
- `backend/utils/` - Utility functions (cache, mailer)

## Important Commands

```bash
# Start all services
./run.sh

# Stop all services
./stop.sh

# Run Redis directly
redis-server

# Test Redis
redis-cli ping

# Start backend only
python3 -m backend.app

# Start frontend only
cd frontend && python3 server.py

# Celery worker
celery -A backend.celery_app worker -l info

# Celery beat
celery -A backend.celery_app beat -l info

# Check Python environment
python3 --version
which python3

# Activate virtual environment
source .venv/bin/activate

# View Celery logs
tail -f logs/celery_worker.log

# View backend logs
tail -f logs/backend.log
```

---

**Last Updated**: April 3, 2026
**Status**: ✅ All systems operational
