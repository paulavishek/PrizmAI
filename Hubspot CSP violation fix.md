# HubSpot Form CSP Violation Fix

## Problem
The HubSpot embedded form is being blocked by Content Security Policy (CSP) headers. The console shows:
```
Failed to load resource: the server responded with a status of 403 ()
Loading the script 'https://js-na2.hsforms.co/forms/embed/v2.js' violates the following Content Security Policy directive: "script-src 'self' 'unsafe-inline'"
```

## Solution
Add HubSpot domains to your CSP configuration in Django settings.

### Step 1: Update Django Settings

Add or modify the CSP configuration in your `settings.py` (or wherever you configure middleware):

```python
# Content Security Policy for HubSpot Integration
CSP_DEFAULT_SRC = ("'self'",)
CSP_SCRIPT_SRC = (
    "'self'",
    "'unsafe-inline'",  # Required for inline scripts
    "'unsafe-eval'",    # Required by some HubSpot scripts
    "https://js.hsforms.net",
    "https://js-na1.hsforms.net",
    "https://js-na2.hsforms.net",
    "https://js-eu1.hsforms.net",
    "https://*.hsforms.com",
    "https://*.hs-scripts.com",
    "https://*.hs-analytics.net",
    "https://www.googletagmanager.com",  # For GA4
    "https://www.google-analytics.com",   # For GA4
)
CSP_CONNECT_SRC = (
    "'self'",
    "https://forms.hubspot.com",
    "https://forms-na1.hubspot.com",
    "https://forms-na2.hubspot.com",
    "https://forms-eu1.hubspot.com",
    "https://*.hsforms.com",
    "https://*.hs-analytics.net",
    "https://www.google-analytics.com",
)
CSP_FONT_SRC = (
    "'self'",
    "data:",
    "https://fonts.gstatic.com",
)
CSP_STYLE_SRC = (
    "'self'",
    "'unsafe-inline'",
    "https://fonts.googleapis.com",
)
CSP_IMG_SRC = (
    "'self'",
    "data:",
    "https:",  # Allow images from HTTPS sources
)
CSP_FRAME_SRC = (
    "'self'",
    "https://forms.hubspot.com",
    "https://share.hsforms.com",
)

# If using django-csp package
CSP_INCLUDE_NONCE_IN = ['script-src']
```

### Step 2: Install django-csp (if not already installed)

```bash
pip install django-csp
```

### Step 3: Add CSP Middleware

In your `MIDDLEWARE` setting, add:

```python
MIDDLEWARE = [
    # ... other middleware ...
    'csp.middleware.CSPMiddleware',
    # ... other middleware ...
]
```

### Alternative: Using Meta Tag (Quick Fix)

If you don't want to use django-csp middleware, add this meta tag to your `base.html` template:

```html
<head>
    <meta http-equiv="Content-Security-Policy" content="
        default-src 'self';
        script-src 'self' 'unsafe-inline' 'unsafe-eval' 
            https://js.hsforms.net 
            https://js-na1.hsforms.net 
            https://js-na2.hsforms.net 
            https://js-eu1.hsforms.net
            https://*.hsforms.com
            https://*.hs-scripts.com
            https://www.googletagmanager.com
            https://www.google-analytics.com;
        connect-src 'self' 
            https://forms.hubspot.com
            https://forms-na1.hubspot.com
            https://forms-na2.hubspot.com
            https://*.hsforms.com
            https://*.hs-analytics.net
            https://www.google-analytics.com;
        style-src 'self' 'unsafe-inline' https://fonts.googleapis.com;
        font-src 'self' data: https://fonts.gstatic.com;
        img-src 'self' data: https:;
        frame-src 'self' https://forms.hubspot.com https://share.hsforms.com;
    ">
</head>
```

### Step 4: Update logout_success.html Template

Update the HubSpot form initialization to handle CSP better:

```html
<!-- In logout_success.html -->
<script charset="utf-8" type="text/javascript" src="//js.hsforms.net/forms/embed/v2.js"></script>
<script>
    window.addEventListener('load', function() {
        console.log('Page loaded, initializing HubSpot form...');
        
        // Add longer timeout for script to load
        setTimeout(function() {
            if (typeof hbspt === 'undefined') {
                console.error('HubSpot script (hbspt) not loaded!');
                document.getElementById('hubspot-form-container').innerHTML = 
                    '<div class="alert alert-warning">Unable to load feedback form. Please check your internet connection or try disabling ad blockers.</div>';
                return;
            }
            
            try {
                hbspt.forms.create({
                    region: "{{ hubspot_region|default:'na1' }}",
                    portalId: "{{ hubspot_portal_id|default:'244661638' }}",
                    formId: "{{ hubspot_form_id|default:'0451cb1c-53b3-47d6-abf4-338f73832a88' }}",
                    target: '#hubspot-form-container',
                    onFormReady: function($form) {
                        console.log('HubSpot form loaded successfully!');
                    },
                    onFormSubmit: function($form) {
                        console.log('HubSpot form submitted!');
                        setTimeout(function() {
                            document.getElementById('hubspot-form-container').style.display = 'none';
                            document.getElementById('success-message').style.display = 'block';
                        }, 1000);
                        
                        if (typeof gtag !== 'undefined') {
                            gtag('event', 'feedback_submitted', {
                                'engagement_level': '{{ engagement_level }}',
                                'session_duration': {{ session_stats.duration_minutes|default:0 }},
                                'form_type': 'hubspot'
                            });
                        }
                    },
                    onFormSubmitted: function() {
                        console.log('HubSpot form submission confirmed!');
                    }
                });
            } catch (error) {
                console.error('Error creating HubSpot form:', error);
                document.getElementById('hubspot-form-container').innerHTML = 
                    '<div class="alert alert-danger">Error loading feedback form. Please try refreshing the page.</div>';
            }
        }, 1000); // Give script time to load
    });
</script>
```

## Verification Steps

1. **Check Browser Console**: After implementing, check for CSP violations
2. **Test Form Loading**: Visit logout page and verify form loads
3. **Test Form Submission**: Submit test feedback to ensure it works
4. **Check Network Tab**: Verify all HubSpot resources load successfully

## Common Issues

### Issue 1: Still Getting CSP Errors
- **Solution**: Clear browser cache and hard reload (Ctrl+Shift+R)
- **Solution**: Check that CSP middleware is after SecurityMiddleware

### Issue 2: Form Loads but Doesn't Submit
- **Solution**: Check `connect-src` includes your HubSpot region's form endpoint
- **Solution**: Verify your HubSpot Form ID is correct in settings

### Issue 3: Ad Blockers
- **Note**: Some ad blockers block HubSpot. Ask users to disable temporarily if needed
- **Alternative**: Show the fallback form for these users

## Security Considerations

**Why 'unsafe-inline' and 'unsafe-eval'?**
- HubSpot's embedded forms require these directives to function
- This is a known limitation of embedded third-party forms
- The risk is acceptable for a feedback form on a logout page
- Consider implementing nonces for better security if needed

**Minimize Risk:**
1. Only use HubSpot forms on specific pages (logout)
2. Implement Subresource Integrity (SRI) where possible
3. Monitor CSP reports for violations
4. Keep HubSpot domains whitelisted, not wildcards when possible

## Testing Checklist

- [ ] CSP configuration added to settings
- [ ] Middleware installed and configured
- [ ] Template updated with error handling
- [ ] Browser console shows no CSP violations
- [ ] HubSpot form loads successfully
- [ ] Form submission works
- [ ] Fallback form still available
- [ ] Google Analytics tracking works

## For Production

Remember to:
1. Set appropriate CSP report-uri to monitor violations
2. Test on staging environment first
3. Document the CSP policy in your security docs
4. Consider using CSP report-only mode initially