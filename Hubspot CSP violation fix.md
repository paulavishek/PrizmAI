# EXACT CSP FIX FOR HUBSPOT FORMS
# Replace the CSP section in your kanban_board/settings.py with this

# ============================================
# CONTENT SECURITY POLICY (CSP) CONFIGURATION
# ============================================

# CSP settings to prevent XSS and other injection attacks
CSP_DEFAULT_SRC = ("'self'",)

CSP_SCRIPT_SRC = (
    "'self'", 
    "'unsafe-inline'",
    "'unsafe-eval'",  # Required for HubSpot forms
    "https://cdn.jsdelivr.net", 
    "https://code.jquery.com",
    "https://js.hsforms.net",
    "https://js-na1.hsforms.net",
    "https://js-na2.hsforms.net",
    "https://js-eu1.hsforms.net",
    "https://*.hsforms.com",
    "https://*.hsforms.net",  # Added wildcard
    "https://*.hs-scripts.com",
    "https://*.hs-analytics.net",
    "https://www.googletagmanager.com",
    "https://www.google-analytics.com",
)

CSP_STYLE_SRC = (
    "'self'", 
    "'unsafe-inline'", 
    "https://cdn.jsdelivr.net", 
    "https://fonts.googleapis.com", 
    "https://cdnjs.cloudflare.com",
)

CSP_IMG_SRC = (
    "'self'", 
    "data:", 
    "https:",  # Allow all HTTPS images
)

CSP_FONT_SRC = (
    "'self'", 
    "data:", 
    "https://cdn.jsdelivr.net", 
    "https://fonts.gstatic.com", 
    "https://cdnjs.cloudflare.com",
)

# CRITICAL FIX: This is where the issue was
CSP_CONNECT_SRC = (
    "'self'", 
    "wss:", 
    "ws:",
    # HubSpot Forms - Explicit domains for your region
    "https://forms-na2.hubspot.com",  # Your specific NA2 region
    "https://forms.hubspot.com",
    "https://forms-na1.hubspot.com",
    "https://forms-eu1.hubspot.com",
    # HubSpot wildcards - CRITICAL: Must include *.hubspot.com
    "https://*.hubspot.com",  # THIS WAS MISSING - catches all hubspot.com subdomains
    "https://*.hsforms.com",
    "https://*.hsforms.net",
    "https://*.hs-analytics.net",
    "https://*.hs-scripts.com",
    # Google Analytics
    "https://www.google-analytics.com",
    "https://analytics.google.com",
    "https://www.googletagmanager.com",
)

CSP_FRAME_SRC = (
    "'self'",
    "https://forms.hubspot.com",
    "https://forms-na1.hubspot.com",
    "https://forms-na2.hubspot.com",
    "https://forms-eu1.hubspot.com",
    "https://share.hsforms.com",
)

CSP_FRAME_ANCESTORS = ("'none'",)

CSP_BASE_URI = ("'self'",)

# CRITICAL FIX: This also needed the wildcard
CSP_FORM_ACTION = (
    "'self'",
    "https://forms-na2.hubspot.com",  # Your specific region
    "https://forms.hubspot.com",
    "https://forms-na1.hubspot.com",
    "https://forms-eu1.hubspot.com",
    "https://*.hubspot.com",  # CRITICAL: Wildcard for all HubSpot form submissions
)

CSP_UPGRADE_INSECURE_REQUESTS = not DEBUG

CSP_REPORT_ONLY = False  # Set to True for testing without enforcement

# ============================================
# END OF CSP CONFIGURATION
# ============================================


# WHAT CHANGED:
# 1. Added "https://*.hubspot.com" to CSP_CONNECT_SRC (line 54)
# 2. Added "https://*.hsforms.net" to CSP_SCRIPT_SRC for completeness
# 3. Added "https://*.hubspot.com" to CSP_FORM_ACTION (line 76)
# 4. Made NA2 explicit first in lists since that's your region

# WHY THIS FIXES IT:
# The browser was blocking requests to forms-na2.hubspot.com because
# while you had "https://*.hsforms.com", you didn't have "https://*.hubspot.com"
# Note the difference: hsforms.com vs hubspot.com (different domains!)

# HUBSPOT FORM CSP FIX - STEP BY STEP INSTRUCTIONS

## The Problem
Looking at your console errors, the requests to `forms-na2.hubspot.com` are being blocked by CSP.

**Key Issue Identified:**
Your settings.py has `https://*.hsforms.com` but is **MISSING** `https://*.hubspot.com`

These are TWO DIFFERENT DOMAINS:
- `hsforms.com` - for scripts
- `hubspot.com` - for form submissions (this is what's blocked)

## The Fix

### Step 1: Open your settings.py file
```bash
# Navigate to your project
cd /path/to/your/project
nano kanban_board/settings.py
# or use your preferred editor
```

### Step 2: Find the CSP_CONNECT_SRC section
Look for this section (around line 450-470):

```python
CSP_CONNECT_SRC = (
    "'self'", 
    "wss:", 
    "ws:", 
    "https://forms.hubspot.com",
    "https://forms-na1.hubspot.com",
    "https://forms-na2.hubspot.com",
    "https://forms-eu1.hubspot.com",
    "https://*.hsforms.com",  # ← You have this
    # BUT YOU'RE MISSING: "https://*.hubspot.com"
    ...
)
```

### Step 3: Add the missing wildcard
Add this line to CSP_CONNECT_SRC:
```python
"https://*.hubspot.com",  # ← ADD THIS LINE
```

The complete CSP_CONNECT_SRC should look like:
```python
CSP_CONNECT_SRC = (
    "'self'", 
    "wss:", 
    "ws:",
    # Explicit HubSpot domains
    "https://forms-na2.hubspot.com",  # Your region
    "https://forms.hubspot.com",
    "https://forms-na1.hubspot.com",
    "https://forms-eu1.hubspot.com",
    # Wildcards - BOTH are needed
    "https://*.hubspot.com",  # ← ADD THIS (catches hubspot.com subdomains)
    "https://*.hsforms.com",   # ← Already have this (catches hsforms.com subdomains)
    "https://*.hsforms.net",
    "https://*.hs-analytics.net",
    "https://*.hs-scripts.com",
    # Google Analytics
    "https://www.google-analytics.com",
    "https://analytics.google.com",
    "https://www.googletagmanager.com",
)
```

### Step 4: Also update CSP_FORM_ACTION
Find CSP_FORM_ACTION and add the same wildcard:

```python
CSP_FORM_ACTION = (
    "'self'",
    "https://forms-na2.hubspot.com",
    "https://forms.hubspot.com",
    "https://forms-na1.hubspot.com",
    "https://forms-eu1.hubspot.com",
    "https://*.hubspot.com",  # ← ADD THIS LINE
)
```

### Step 5: Save and restart Django
```bash
# Save the file (Ctrl+O, Enter, Ctrl+X if using nano)

# Restart Django server
python manage.py runserver
```

### Step 6: Clear browser cache and test
```bash
# In your browser:
# 1. Hard reload: Ctrl+Shift+R (Windows/Linux) or Cmd+Shift+R (Mac)
# 2. Or clear cache completely
# 3. Navigate to /analytics/logout/
# 4. Check console - should see NO CSP violations
# 5. Form should load and submit successfully
```

## Verification

After the fix, your browser console should show:
- ✅ "HubSpot form loaded successfully!"
- ✅ No CSP violation errors mentioning hubspot.com
- ✅ Form visible and interactive
- ✅ Form submits successfully

## Why This Works

HubSpot uses multiple domains:
1. **Script loading**: `js-na2.hsforms.net` (covered by `*.hsforms.net`)
2. **Form submissions**: `forms-na2.hubspot.com` (needs `*.hubspot.com`)
3. **Analytics**: `*.hs-analytics.net` (already covered)

The wildcard `*.hsforms.com` does NOT match `*.hubspot.com` - they're different domains!

## Quick Copy-Paste

If you want to just copy-paste, here are the TWO critical additions:

**Add to CSP_CONNECT_SRC:**
```python
"https://*.hubspot.com",
```

**Add to CSP_FORM_ACTION:**
```python
"https://*.hubspot.com",
```

## Still Not Working?

If it still doesn't work after this fix:

### Option 1: Temporarily disable CSP for testing
```python
# At the top of settings.py
if DEBUG:
    CSP_DEFAULT_SRC = None  # Disables CSP in development
```

### Option 2: Use report-only mode
```python
CSP_REPORT_ONLY = True  # Logs violations but doesn't block
```

### Option 3: Check django-csp is installed
```bash
pip install django-csp
pip freeze | grep django-csp  # Should show: django-csp==x.x.x
```

### Option 4: Verify middleware order
In MIDDLEWARE, ensure CSPMiddleware comes after SecurityMiddleware:
```python
MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    'whitenoise.middleware.WhiteNoiseMiddleware',
    # ...
    'csp.middleware.CSPMiddleware',  # ← Should be here
    # ...
]
```

## Testing Checklist

- [ ] Added `"https://*.hubspot.com"` to CSP_CONNECT_SRC
- [ ] Added `"https://*.hubspot.com"` to CSP_FORM_ACTION  
- [ ] Saved settings.py
- [ ] Restarted Django server
- [ ] Cleared browser cache
- [ ] Navigated to logout page
- [ ] Console shows no CSP violations
- [ ] HubSpot form loads
- [ ] Form accepts input
- [ ] Form submits successfully
- [ ] Success message appears

## Final Note

The key insight: `*.hsforms.com` ≠ `*.hubspot.com`

They are completely different domains, and you need BOTH for HubSpot forms to work:
- `*.hsforms.com` - for form assets and scripts
- `*.hubspot.com` - for form submission endpoints

This is why even though you had hsforms wildcards, the form submissions were still blocked.