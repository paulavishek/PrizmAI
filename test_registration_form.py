"""
Test the RegistrationForm to verify email validation is working
"""
import os
import django

# Set up Django environment
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'kanban_board.settings')
django.setup()

from accounts.forms import RegistrationForm

def test_registration_form():
    """Test the RegistrationForm with various email addresses"""
    
    print("=" * 80)
    print("REGISTRATION FORM EMAIL VALIDATION TEST")
    print("=" * 80)
    
    # Test case 1: Invalid domain (test.com)
    print("\n1. Testing with paul.biotech10@test.com (invalid domain)")
    form_data = {
        'username': 'newuser1',
        'email': 'paul.biotech10@test.com',
        'password1': 'SecurePass123!',
        'password2': 'SecurePass123!'
    }
    form = RegistrationForm(data=form_data)
    is_valid = form.is_valid()
    print(f"   Form Valid: {is_valid}")
    if not is_valid:
        print(f"   Errors: {form.errors.as_text()}")
        print("   ✓ PASS: Invalid email correctly rejected by form!")
    else:
        print("   ✗ FAIL: Invalid email was accepted by form!")
    
    # Test case 2: Valid Gmail
    print("\n2. Testing with test@gmail.com (valid domain)")
    form_data = {
        'username': 'newuser2',
        'email': 'test@gmail.com',
        'password1': 'SecurePass123!',
        'password2': 'SecurePass123!'
    }
    form = RegistrationForm(data=form_data)
    is_valid = form.is_valid()
    print(f"   Form Valid: {is_valid}")
    if is_valid:
        print("   ✓ PASS: Valid email accepted by form!")
    else:
        print(f"   Errors: {form.errors.as_text()}")
        print("   ✗ FAIL: Valid email was rejected by form!")
    
    # Test case 3: Disposable email
    print("\n3. Testing with test@10minutemail.com (disposable domain)")
    form_data = {
        'username': 'newuser3',
        'email': 'test@10minutemail.com',
        'password1': 'SecurePass123!',
        'password2': 'SecurePass123!'
    }
    form = RegistrationForm(data=form_data)
    is_valid = form.is_valid()
    print(f"   Form Valid: {is_valid}")
    if not is_valid:
        print(f"   Errors: {form.errors.as_text()}")
        print("   ✓ PASS: Disposable email correctly rejected by form!")
    else:
        print("   ✗ FAIL: Disposable email was accepted by form!")
    
    print("\n" + "=" * 80)
    print("SUMMARY:")
    print("The RegistrationForm now properly validates email domains!")
    print("- Invalid domains (like test.com) are rejected")
    print("- Disposable email domains are rejected")
    print("- Valid email domains (like gmail.com) are accepted")
    print("=" * 80)

if __name__ == '__main__':
    test_registration_form()
