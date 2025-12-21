"""
Analytics utility functions.
"""
import logging
import hashlib

logger = logging.getLogger(__name__)


def get_user_ip(request):
    """Get user IP address from request"""
    x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
    if x_forwarded_for:
        ip = x_forwarded_for.split(',')[0]
    else:
        ip = request.META.get('REMOTE_ADDR')
    return ip


def get_device_type(user_agent):
    """Detect device type from user agent string"""
    user_agent = user_agent.lower()
    
    if 'mobile' in user_agent or 'android' in user_agent:
        return 'mobile'
    elif 'tablet' in user_agent or 'ipad' in user_agent:
        return 'tablet'
    elif 'desktop' in user_agent or 'windows' in user_agent or 'mac' in user_agent:
        return 'desktop'
    else:
        return 'unknown'


class GoogleAnalyticsHelper:
    """
    Helper utilities for working with Google Analytics data.
    """
    
    @staticmethod
    def get_ga_script(measurement_id, user=None, anonymize_ip=True):
        """
        Generate GA4 tracking script with configuration.
        
        Args:
            measurement_id: GA4 measurement ID (G-XXXXXXXXXX)
            user: Django user object (optional)
            anonymize_ip: Whether to anonymize IP addresses (GDPR)
        
        Returns:
            str: HTML script tag for GA4
        """
        config_params = {
            'anonymize_ip': 'true' if anonymize_ip else 'false',
            'cookie_flags': 'SameSite=None;Secure',
        }
        
        user_properties = {}
        if user and user.is_authenticated:
            user_properties['user_type'] = 'registered'
            # Anonymize user ID
            user_properties['user_id_hashed'] = hashlib.md5(str(user.id).encode()).hexdigest()
        else:
            user_properties['user_type'] = 'anonymous'
        
        config_str = ', '.join([f"'{k}': '{v}'" for k, v in config_params.items()])
        props_str = ', '.join([f"'{k}': '{v}'" for k, v in user_properties.items()])
        
        script = f"""
        <!-- Google Analytics 4 -->
        <script async src="https://www.googletagmanager.com/gtag/js?id={measurement_id}"></script>
        <script>
          window.dataLayer = window.dataLayer || [];
          function gtag(){{dataLayer.push(arguments);}}
          gtag('js', new Date());
          
          gtag('config', '{measurement_id}', {{
            {config_str}
          }});
          
          // Set user properties
          gtag('set', 'user_properties', {{
            {props_str}
          }});
        </script>
        """
        
        return script
