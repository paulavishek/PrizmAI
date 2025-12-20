"""
HubSpot integration utilities for syncing contacts and feedback.
"""
import requests
import logging
from django.conf import settings
from datetime import datetime

logger = logging.getLogger(__name__)


class HubSpotIntegration:
    """
    Integrate with HubSpot CRM for contact management and feedback tracking.
    """
    
    def __init__(self):
        self.api_key = getattr(settings, 'HUBSPOT_API_KEY', None)
        self.portal_id = getattr(settings, 'HUBSPOT_PORTAL_ID', None)
        self.base_url = "https://api.hubapi.com"
        self.headers = {
            'Content-Type': 'application/json',
        }
        if self.api_key:
            self.headers['Authorization'] = f'Bearer {self.api_key}'
    
    def is_configured(self):
        """Check if HubSpot is properly configured"""
        return bool(self.api_key and self.portal_id)
    
    def create_or_update_contact(self, email, first_name='', last_name='', 
                                 company='', phone='', **custom_properties):
        """
        Create or update a contact in HubSpot.
        
        Args:
            email: Contact email (required)
            first_name: First name
            last_name: Last name
            company: Company name
            phone: Phone number
            **custom_properties: Any additional custom properties
        
        Returns:
            dict: HubSpot contact data including vid (contact ID)
        """
        if not self.is_configured():
            logger.warning("HubSpot not configured. Skipping contact sync.")
            return None
        
        url = f"{self.base_url}/contacts/v1/contact/createOrUpdate/email/{email}/"
        
        properties = [
            {'property': 'email', 'value': email},
        ]
        
        if first_name:
            properties.append({'property': 'firstname', 'value': first_name})
        if last_name:
            properties.append({'property': 'lastname', 'value': last_name})
        if company:
            properties.append({'property': 'company', 'value': company})
        if phone:
            properties.append({'property': 'phone', 'value': phone})
        
        # Add custom properties
        for key, value in custom_properties.items():
            properties.append({'property': key, 'value': str(value)})
        
        data = {'properties': properties}
        
        try:
            response = requests.post(url, json=data, headers=self.headers, timeout=10)
            response.raise_for_status()
            result = response.json()
            logger.info(f"Successfully synced contact {email} to HubSpot")
            return result
        except requests.exceptions.RequestException as e:
            logger.error(f"Error syncing contact to HubSpot: {e}")
            return None
    
    def create_engagement(self, contact_id, engagement_type='NOTE', 
                         subject='', body=''):
        """
        Create an engagement (note, email, task, etc.) for a contact.
        
        Args:
            contact_id: HubSpot contact ID (vid)
            engagement_type: Type of engagement (NOTE, EMAIL, TASK, etc.)
            subject: Engagement subject
            body: Engagement body/content
        
        Returns:
            dict: Engagement data
        """
        if not self.is_configured():
            return None
        
        url = f"{self.base_url}/engagements/v1/engagements"
        
        data = {
            'engagement': {
                'active': True,
                'type': engagement_type,
                'timestamp': int(datetime.now().timestamp() * 1000),
            },
            'associations': {
                'contactIds': [contact_id],
            },
            'metadata': {
                'subject': subject,
                'body': body,
            }
        }
        
        try:
            response = requests.post(url, json=data, headers=self.headers, timeout=10)
            response.raise_for_status()
            result = response.json()
            logger.info(f"Successfully created engagement for contact {contact_id}")
            return result
        except requests.exceptions.RequestException as e:
            logger.error(f"Error creating engagement in HubSpot: {e}")
            return None
    
    def sync_feedback_to_hubspot(self, feedback):
        """
        Sync feedback object to HubSpot.
        Creates/updates contact and adds feedback as note.
        
        Args:
            feedback: Feedback model instance
        
        Returns:
            tuple: (contact_id, engagement_id)
        """
        if not self.is_configured():
            return None, None
        
        if not feedback.email:
            logger.warning("Feedback has no email. Cannot sync to HubSpot.")
            return None, None
        
        # Prepare custom properties
        custom_props = {
            'app_usage_level': feedback.user_session.engagement_level if feedback.user_session else 'unknown',
            'feedback_rating': feedback.rating or 0,
            'feedback_sentiment': feedback.sentiment or 'neutral',
        }
        
        if feedback.user_session:
            custom_props.update({
                'session_duration': feedback.user_session.duration_minutes,
                'ai_features_used': feedback.user_session.ai_features_used,
                'tasks_created': feedback.user_session.tasks_created,
                'boards_created': feedback.user_session.boards_created,
            })
        
        # Create/update contact
        contact_data = self.create_or_update_contact(
            email=feedback.email,
            first_name=feedback.name.split()[0] if feedback.name else '',
            last_name=' '.join(feedback.name.split()[1:]) if feedback.name and len(feedback.name.split()) > 1 else '',
            company=feedback.organization,
            **custom_props
        )
        
        if not contact_data:
            return None, None
        
        contact_id = contact_data.get('vid')
        
        # Create engagement (note) with feedback
        engagement_subject = f"Feedback: {feedback.rating}★ - {feedback.sentiment}"
        engagement_body = f"""
        Feedback from PrizmAI:
        
        Rating: {feedback.rating}★
        Sentiment: {feedback.sentiment}
        Type: {feedback.feedback_type}
        
        Feedback:
        {feedback.feedback_text}
        
        Session Details:
        - Engagement Level: {feedback.user_session.engagement_level if feedback.user_session else 'N/A'}
        - Duration: {feedback.user_session.duration_minutes if feedback.user_session else 0} minutes
        - AI Features Used: {feedback.user_session.ai_features_used if feedback.user_session else 0}
        - Tasks Created: {feedback.user_session.tasks_created if feedback.user_session else 0}
        
        Submitted: {feedback.submitted_at.strftime('%Y-%m-%d %H:%M')}
        """
        
        engagement_data = self.create_engagement(
            contact_id=contact_id,
            engagement_type='NOTE',
            subject=engagement_subject,
            body=engagement_body
        )
        
        engagement_id = engagement_data.get('engagement', {}).get('id') if engagement_data else None
        
        # Update feedback model
        feedback.hubspot_contact_id = str(contact_id)
        feedback.synced_to_hubspot = True
        from django.utils import timezone
        feedback.hubspot_sync_date = timezone.now()
        feedback.save(update_fields=['hubspot_contact_id', 'synced_to_hubspot', 'hubspot_sync_date'])
        
        return contact_id, engagement_id
    
    def send_follow_up_email(self, contact_id, template_id, custom_properties=None):
        """
        Send a follow-up email using HubSpot email templates.
        
        Args:
            contact_id: HubSpot contact ID
            template_id: HubSpot email template ID
            custom_properties: Dict of custom properties to personalize email
        
        Returns:
            dict: Email send result
        """
        if not self.is_configured():
            return None
        
        url = f"{self.base_url}/email/public/v1/singleEmail/send"
        
        data = {
            'emailId': template_id,
            'contactProperties': custom_properties or {},
            'contactId': contact_id,
        }
        
        try:
            response = requests.post(url, json=data, headers=self.headers, timeout=10)
            response.raise_for_status()
            result = response.json()
            logger.info(f"Successfully sent follow-up email to contact {contact_id}")
            return result
        except requests.exceptions.RequestException as e:
            logger.error(f"Error sending follow-up email: {e}")
            return None


# Google Analytics integration helper
class GoogleAnalyticsHelper:
    """
    Helper utilities for working with Google Analytics data.
    For server-side GA4 API integration.
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
            import hashlib
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
    
    @staticmethod
    def track_event(event_name, event_data=None):
        """
        Generate JavaScript to track a custom event.
        
        Args:
            event_name: Name of the event
            event_data: Dict of event parameters
        
        Returns:
            str: JavaScript code to track event
        """
        data_str = ''
        if event_data:
            params = ', '.join([f"'{k}': '{v}'" for k, v in event_data.items()])
            data_str = f', {{{params}}}'
        
        return f"gtag('event', '{event_name}'{data_str});"
