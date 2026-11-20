#!/usr/bin/env python
"""Set up Django's database and administrator for local development."""

import os
import sys
import subprocess
from pathlib import Path

# Change to project directory
project_dir = Path(__file__).parent
os.chdir(project_dir)

def run_command(command, description):
    """Run a shell command and report status."""
    print(f"\n{'='*60}")
    print(f"🔧 {description}")
    print(f"{'='*60}")
    print(f"Command: {command}\n")
    
    result = subprocess.run(command, shell=True, cwd=project_dir)
    
    if result.returncode != 0:
        print(f"\n❌ Error running: {description}")
        return False
    else:
        print(f"\n✅ Completed: {description}")
        return True

def main():
    print("\n")
    print("="*60)
    print("   SmartStock AI - Backend Setup Automation")
    print("="*60)
    
    # Apply the committed schema without generating migrations locally.
    if not run_command(
        "venv\\Scripts\\python manage.py migrate",
        "Running database migrations (creating tables)"
    ):
        sys.exit(1)
    
    # Step 2: Create superuser
    print("\n" + "="*60)
    print("👤 Creating Superuser Account")
    print("="*60)
    print("\nCreate your own administrator credentials when prompted.")
    print("\n")
    
    subprocess.run(
        "venv\\Scripts\\python manage.py createsuperuser",
        shell=True,
        cwd=project_dir
    )
    
    # Step 3: Collect static files
    if not run_command(
        "venv\\Scripts\\python manage.py collectstatic --noinput",
        "Collecting static files"
    ):
        print("⚠️  Warning: Static file collection had issues (non-critical)")
    
    # Summary
    print("\n" + "="*60)
    print("✅ SETUP COMPLETE!")
    print("="*60)
    print("\nYour SmartStock AI backend is ready!")
    print("\nNext steps:")
    print("1. Start the development server:")
    print("   venv\\Scripts\\python manage.py runserver")
    print("\n2. Access the application:")
    print("   Admin:      http://127.0.0.1:8000/admin/")
    print("   Dashboard:  http://127.0.0.1:8000/dashboard/")
    print("\n3. Start the AI service in a separate terminal:")
    print("   venv\\Scripts\\python -m pip install -r ai_service\\requirements.txt")
    print("   venv\\Scripts\\python -m uvicorn ai_service.app:app --host 127.0.0.1 --port 8001")
    print("\n" + "="*60 + "\n")

if __name__ == "__main__":
    main()
