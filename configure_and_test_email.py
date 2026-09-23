#!/usr/bin/env python3
"""
Interactive Email Configuration and Testing Script
This script helps configure email settings and test them immediately.
"""

import os
import sys
import subprocess
from pathlib import Path

def get_env_file_path():
    """Get the .env file path"""
    return Path("/home/zendachromian/extracted/mad02*/.env")

def prompt_gmail_setup():
    """Prompt for Gmail configuration"""
    print("\n" + "="*60)
    print("📧 GMAIL CONFIGURATION")
    print("="*60)
    print("\n⚠️  IMPORTANT: Use App Password, NOT your regular password!")
    print("📖 How to get App Password:")
    print("   1. Go to: https://myaccount.google.com/security")
    print("   2. Enable 2-Factor Authentication (if not already enabled)")
    print("   3. Go to: https://myaccount.google.com/apppasswords")
    print("   4. Select 'Mail' and 'Windows Computer' (or your device)")
    print("   5. Copy the 16-character password shown\n")
    
    email = input("Enter your Gmail address: ").strip()
    app_password = input("Enter your 16-character App Password: ").strip()
    
    return {
        'MAIL_SERVER': 'smtp.gmail.com',
        'MAIL_PORT': '587',
        'MAIL_USE_TLS': 'True',
        'MAIL_USERNAME': email,
        'MAIL_PASSWORD': app_password
    }

def prompt_other_smtp():
    """Prompt for other SMTP server configuration"""
    print("\n" + "="*60)
    print("📧 OTHER SMTP CONFIGURATION")
    print("="*60)
    
    server = input("Enter SMTP server (e.g., smtp.example.com): ").strip()
    port = input("Enter SMTP port (default 587): ").strip() or "587"
    use_tls = input("Use TLS? (yes/no, default: yes): ").strip().lower()
    use_tls = "True" if use_tls != "no" else "False"
    username = input("Enter SMTP username: ").strip()
    password = input("Enter SMTP password: ").strip()
    
    return {
        'MAIL_SERVER': server,
        'MAIL_PORT': port,
        'MAIL_USE_TLS': use_tls,
        'MAIL_USERNAME': username,
        'MAIL_PASSWORD': password
    }

def save_env_config(config):
    """Save configuration to .env file"""
    env_file = Path("/home/zendachromian/extracted/mad02*/.env")
    env_file.parent.mkdir(parents=True, exist_ok=True)
    
    # Read existing .env if it exists
    existing_lines = []
    if env_file.exists():
        with open(env_file, 'r') as f:
            existing_lines = f.readlines()
    
    # Remove old email config lines
    filtered_lines = [line for line in existing_lines 
                     if not any(key in line for key in config.keys())]
    
    # Add new config
    with open(env_file, 'w') as f:
        f.writelines(filtered_lines)
        f.write('\n# Email Configuration\n')
        for key, value in config.items():
            f.write(f'{key}={value}\n')
    
    print(f"\n✅ Configuration saved to .env")

def test_email_config():
    """Test email configuration by sending a test email"""
    print("\n" + "="*60)
    print("🧪 TESTING EMAIL CONFIGURATION")
    print("="*60)
    
    test_recipient = input("\nEnter test email recipient: ").strip()
    
    try:
        # Source the .env file and run the test
        print(f"\nSending test email to {test_recipient}...")
        
        # Create a Python script to test
        test_script = """
import os
import sys
sys.path.insert(0, '/home/zendachromian/extracted/mad02*')

# Load environment variables
from pathlib import Path
env_file = Path('/home/zendachromian/extracted/mad02*/.env')
if env_file.exists():
    with open(env_file) as f:
        for line in f:
            line = line.strip()
            if line and not line.startswith('#') and '=' in line:
                key, value = line.split('=', 1)
                os.environ[key.strip()] = value.strip()

from backend.app import app
from backend.utils.mailer import send_mail

with app.app_context():
    result = send_mail(
        subject='🧪 Test Email - Hospital Management System',
        recipients=['""" + test_recipient + """'],
        body='''Dear User,

This is a test email from the Hospital Management System.

If you received this email, your email configuration is working correctly!

✅ Email Configuration Status: SUCCESS

Best regards,
Hospital Management System
'''
    )
    
    if result:
        print("✅ Test email sent successfully!")
        print("📧 Check your inbox for the test email.")
    else:
        print("❌ Email sending failed. Check the logs for details.")
"""
        
        result = subprocess.run(
            ['python3', '-c', test_script],
            cwd='/home/zendachromian/extracted/mad02*',
            capture_output=True,
            text=True,
            timeout=30
        )
        
        print(result.stdout)
        if result.stderr:
            print("Errors/Logs:")
            print(result.stderr)
        
        return result.returncode == 0
    
    except Exception as e:
        print(f"❌ Error testing email: {e}")
        return False

def main():
    """Main setup wizard"""
    print("\n" + "="*60)
    print("🏥 HOSPITAL MANAGEMENT SYSTEM")
    print("📧 EMAIL CONFIGURATION SETUP")
    print("="*60)
    
    print("\nChoose your email provider:")
    print("1. Gmail (recommended)")
    print("2. Other SMTP server (Outlook, Yahoo, custom, etc.)")
    
    choice = input("\nEnter choice (1 or 2): ").strip()
    
    if choice == "1":
        config = prompt_gmail_setup()
    elif choice == "2":
        config = prompt_other_smtp()
    else:
        print("❌ Invalid choice")
        return
    
    # Save configuration
    save_env_config(config)
    
    # Test email
    print("\nWould you like to test the email configuration now?")
    test_now = input("Test now? (yes/no): ").strip().lower()
    
    if test_now == "yes" or test_now == "y":
        success = test_email_config()
        if success:
            print("\n" + "="*60)
            print("✅ EMAIL SETUP COMPLETE!")
            print("="*60)
            print("\n🚀 Your email configuration is ready to use!")
            print("   Restart your Flask app and Celery worker for changes to take effect.")
            print("\n📖 Commands to restart:")
            print("   ./stop.sh")
            print("   ./run.sh")
        else:
            print("\n⚠️  Email test failed. Please check your credentials and try again.")
    else:
        print("\n✅ Configuration saved!")
        print("   You can test later by running: python3 configure_and_test_email.py")

if __name__ == '__main__':
    main()
