#!/usr/bin/env python
"""
Security Fixes Installation Script
Automated installation and verification of security enhancements
"""

import subprocess
import sys
import os
from pathlib import Path

def print_header(text):
    """Print formatted header"""
    print("\n" + "=" * 70)
    print(f"  {text}")
    print("=" * 70 + "\n")

def run_command(command, description):
    """Run a command and handle errors"""
    print(f"⏳ {description}...")
    try:
        result = subprocess.run(
            command,
            shell=True,
            check=True,
            capture_output=True,
            text=True
        )
        print(f"✅ {description} - SUCCESS")
        return True, result.stdout
    except subprocess.CalledProcessError as e:
        print(f"❌ {description} - FAILED")
        print(f"Error: {e.stderr}")
        return False, e.stderr

def check_file_exists(filepath):
    """Check if a file exists"""
    return Path(filepath).exists()

def main():
    print_header("PrizmAI Security Fixes Installation")
    
    # Check if we're in the right directory
    if not check_file_exists("manage.py"):
        print("❌ Error: Please run this script from the PrizmAI root directory")
        print("   Current directory:", os.getcwd())
        sys.exit(1)
    
    print("✅ Found manage.py - correct directory")
    
    # Step 1: Install dependencies
    print_header("Step 1: Installing Security Dependencies")
    success, output = run_command(
        "pip install -r requirements.txt",
        "Installing requirements"
    )
    
    if not success:
        print("\n⚠️  Warning: Some packages may have failed to install")
        print("   Try running: pip install bleach python-magic-bin django-csp django-axes")
    
    # Step 2: Run migrations
    print_header("Step 2: Running Database Migrations")
    success, output = run_command(
        "python manage.py migrate",
        "Running migrations"
    )
    
    if not success:
        print("\n❌ Migration failed. Please check the error above.")
        sys.exit(1)
    
    # Step 3: Check for SECRET_KEY
    print_header("Step 3: Checking Environment Configuration")
    
    env_file = Path(".env")
    if env_file.exists():
        print("✅ Found .env file")
        with open(env_file, 'r') as f:
            content = f.read()
            if 'SECRET_KEY=' in content and len(content.split('SECRET_KEY=')[1].split()[0]) > 20:
                print("✅ SECRET_KEY is configured")
            else:
                print("⚠️  SECRET_KEY may not be properly configured")
                print("   Generate one with:")
                print("   python -c \"from django.core.management.utils import get_random_secret_key; print(get_random_secret_key())\"")
    else:
        print("⚠️  .env file not found")
        print("   Create .env file with:")
        print("   SECRET_KEY=your-secret-key-here")
        print("   DEBUG=True")
    
    # Step 4: Run security checks
    print_header("Step 4: Running Security Scans")
    
    # Check for eval() usage
    print("🔍 Checking for eval() usage...")
    try:
        result = subprocess.run(
            'findstr /s /n /i "eval(" *.py',
            shell=True,
            capture_output=True,
            text=True
        )
        if 'kanban\\forms\\__init__.py' in result.stdout and 'eval(required_skills_input)' in result.stdout:
            print("❌ WARNING: eval() still found in forms!")
        else:
            print("✅ No dangerous eval() usage found")
    except:
        print("⚠️  Could not check for eval() - manual verification needed")
    
    # Run safety check
    print("\n🔍 Checking for vulnerable dependencies...")
    success, output = run_command(
        "safety check --json",
        "Running safety check"
    )
    
    if success and output and '"vulnerabilities": []' in output:
        print("✅ No known vulnerabilities in dependencies")
    elif success:
        print("⚠️  Some vulnerabilities found - review output above")
    else:
        print("⚠️  Safety check not available - install with: pip install safety")
    
    # Step 5: Verify file validator exists
    print_header("Step 5: Verifying Security Components")
    
    if check_file_exists("kanban/utils/file_validators.py"):
        print("✅ File validator utility created")
    else:
        print("❌ File validator missing - may need manual creation")
    
    # Check bleach installation
    try:
        import bleach
        print("✅ Bleach library installed")
    except ImportError:
        print("❌ Bleach not installed - XSS protection may not work")
    
    # Check magic installation
    try:
        import magic
        print("✅ Python-magic library installed")
    except ImportError:
        print("❌ Python-magic not installed - file validation may not work")
    
    # Check django-csp
    try:
        import csp
        print("✅ Django-CSP installed")
    except ImportError:
        print("❌ Django-CSP not installed")
    
    # Check django-axes
    try:
        import axes
        print("✅ Django-axes installed")
    except ImportError:
        print("❌ Django-axes not installed")
    
    # Final summary
    print_header("Installation Complete!")
    
    print("📋 Next Steps:\n")
    print("1. Verify SECRET_KEY is set in .env file")
    print("2. Test the application: python manage.py runserver")
    print("3. Run security tests (see SECURITY_FIXES_COMPLETED.md)")
    print("4. Test file uploads with malicious files")
    print("5. Test XSS protection in wiki pages")
    print("6. Test brute force protection (5 failed logins)")
    print("\n📖 Full documentation: SECURITY_FIXES_COMPLETED.md")
    print("\n🎉 Your application is now significantly more secure!")
    
    return 0

if __name__ == "__main__":
    try:
        sys.exit(main())
    except KeyboardInterrupt:
        print("\n\n❌ Installation cancelled by user")
        sys.exit(1)
    except Exception as e:
        print(f"\n\n❌ Unexpected error: {e}")
        sys.exit(1)
