#!/usr/bin/env python
"""Set up Django's database and static files for local development."""

import os
import sys
import subprocess
from pathlib import Path

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
    print("\n" + "="*60)
    print("   SmartStock AI - Setup Automation")
    print("="*60)
    
    python_cmd = sys.executable

    # Step 1: Run migrations
    if not run_command(
        f'"{python_cmd}" manage.py migrate',
        "Running database migrations"
    ):
        sys.exit(1)
    
    # Step 2: Collect static files
    if not run_command(
        f'"{python_cmd}" manage.py collectstatic --noinput',
        "Collecting static files"
    ):
        print("⚠️ Warning: Static file collection had issues (non-critical)")

    # Step 3: Run forecast generation
    run_command(
        f'"{python_cmd}" manage.py run_forecasts',
        "Generating initial demand forecasts"
    )
    
    print("\n" + "="*60)
    print("✅ SETUP COMPLETE!")
    print("="*60)
    print("\nYour SmartStock AI application is ready!")
    print("\nNext steps:")
    print("1. Start the development server:")
    print("   python manage.py runserver")
    print("\n2. Access the application in your browser:")
    print("   Dashboard:  http://127.0.0.1:8000/dashboard/")
    print("   Admin:      http://127.0.0.1:8000/admin/")
    print("\nDemo Login Credentials:")
    print("   Admin:   admin   / admin123")
    print("   Manager: manager / manager123")
    print("   Cashier: cashier / cashier123")
    print("\n" + "="*60 + "\n")

if __name__ == "__main__":
    main()
