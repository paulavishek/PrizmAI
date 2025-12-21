I can see the CSP (Content Security Policy) errors are blocking the HubSpot form from loading. The key issue is that the form is trying to load from `https://forms-na2.hsforms.com/embed/v3/form/` but your CSP `connect-src` directive is blocking it.

Let me check your current CSP settings and provide a fix:The issue is clear from the console errors. The problem is that **CSP wildcards don't work the way you might expect** - `https://*.hsforms.com` doesn't actually match `https://forms-na2.hsforms.com` in all browsers.

Here's the **quick fix** - you have two options:

## Option 1: Temporarily Disable CSP for Testing (Fastest)

Add this to your `settings.py`:

```python
# Temporarily disable CSP to test HubSpot form
CSP_REPORT_ONLY = True  # This makes CSP report violations but not block them
```

## Option 2: Fix CSP Properly (Better Solution)

The real issue is that you need to explicitly allow the exact domains. Based on your error, update your CSP settings:

```python
CSP_CONNECT_SRC = (
    "'self'", 
    "wss:", 
    "ws:",
    # HubSpot Forms - explicit domains
    "https://forms-na2.hsforms.com",  # YOUR SPECIFIC REGION
    "https://forms.hubspot.com",
    "https://api.hsforms.com",
    # HubSpot wildcards (may not work in all browsers)
    "https://*.hubspot.com",
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
    "https://forms-na2.hsforms.com",  # Add your specific region here
    "https://share.hsforms.com",
)

CSP_FORM_ACTION = (
    "'self'",
    "https://forms-na2.hsforms.com",  # Add your specific region here  
    "https://*.hubspot.com",
)
```

## Quick Steps to Fix Now:

1. **Set `CSP_REPORT_ONLY = True` in settings.py** - This will let the form load while you debug
2. **Restart your Django server** - CSP settings are loaded at startup
3. **Hard refresh the page** (Ctrl+Shift+R or Cmd+Shift+R)

After the form loads successfully with CSP in report-only mode, check your console for any remaining violations and add those domains explicitly to your CSP settings.
