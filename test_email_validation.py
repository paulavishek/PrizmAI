"""
Test script to verify email validation with DNS checks
"""
import os
import django

# Set up Django environment
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'kanban_board.settings')
django.setup()

from kanban.utils.email_validation import validate_email_for_signup, has_valid_mx_or_a_record

def test_email_validation():
    """Test various email addresses"""
    
    test_cases = [
        ('paul.biotech10@test.com', False, 'Invalid domain test.com'),
        ('test@gmail.com', True, 'Valid Gmail'),
        ('user@example.com', True, 'Valid example.com'),
        ('test@10minutemail.com', False, 'Disposable email'),
        ('valid@microsoft.com', True, 'Valid Microsoft'),
    ]
    
    print("=" * 80)
    print("EMAIL VALIDATION TEST RESULTS")
    print("=" * 80)
    
    for email, expected_valid, description in test_cases:
        is_valid, error_msg = validate_email_for_signup(email)
        
        status = "✓ PASS" if (is_valid == expected_valid) else "✗ FAIL"
        
        print(f"\n{status} - {description}")
        print(f"  Email: {email}")
        print(f"  Expected: {'Valid' if expected_valid else 'Invalid'}")
        print(f"  Actual: {'Valid' if is_valid else 'Invalid'}")
        if error_msg:
            print(f"  Error: {error_msg}")
    
    print("\n" + "=" * 80)
    
    # Specific test for the reported issue
    print("\n\nSPECIFIC TEST FOR REPORTED ISSUE:")
    print("-" * 80)
    email = 'paul.biotech10@test.com'
    is_valid, error_msg = validate_email_for_signup(email)
    
    print(f"Email: {email}")
    print(f"Valid: {is_valid}")
    print(f"Error Message: {error_msg}")
    
    if not is_valid:
        print("\n✓ SUCCESS: Invalid email correctly rejected!")
    else:
        print("\n✗ FAILURE: Invalid email was accepted!")
    
    print("=" * 80)

if __name__ == '__main__':
    test_email_validation()
