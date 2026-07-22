"""
Forms for Webhook Management
"""
import json

from django import forms
from webhooks.models import Webhook
from webhooks.security import validate_webhook_target


class WebhookForm(forms.ModelForm):
    """Form for creating/editing webhooks"""
    required_css_class = 'required'

    # Only events that have a signal handler are offered (board.member_added /
    # board.member_removed have no handler and would never fire).
    EVENT_CHOICES = [
        ('task.created', 'Task Created'),
        ('task.updated', 'Task Updated'),
        ('task.deleted', 'Task Deleted'),
        ('task.completed', 'Task Completed'),
        ('task.assigned', 'Task Assigned'),
        ('task.moved', 'Task Moved'),
        ('comment.added', 'Comment Added'),
        ('board.updated', 'Board Updated'),
    ]
    
    events = forms.MultipleChoiceField(
        choices=EVENT_CHOICES,
        widget=forms.CheckboxSelectMultiple,
        help_text="Select which events should trigger this webhook"
    )

    # Set by the Quick-setup preset buttons; drives provider-specific payload formatting.
    provider = forms.CharField(required=False, widget=forms.HiddenInput())

    # JSON object of extra HTTP headers (e.g. auth tokens for GitHub/GitLab/PagerDuty).
    custom_headers = forms.CharField(
        required=False,
        widget=forms.Textarea(attrs={
            'class': 'form-control', 'rows': 3,
            'placeholder': '{"Authorization": "Bearer <token>"}'
        }),
        help_text='Optional. JSON object of extra HTTP headers sent with every delivery.'
    )

    # JSON config some providers need in the body (PagerDuty routing_key, GitHub event_type).
    provider_config = forms.CharField(
        required=False,
        widget=forms.Textarea(attrs={
            'class': 'form-control', 'rows': 2,
            'placeholder': '{"routing_key": "..."}'
        }),
        help_text='Optional. Provider-specific JSON config (e.g. PagerDuty routing_key).'
    )

    class Meta:
        model = Webhook
        fields = [
            'name', 'url', 'events', 'is_active',
            'timeout_seconds', 'max_retries', 'retry_delay_seconds',
            'secret', 'provider', 'custom_headers', 'provider_config'
        ]
        widgets = {
            'name': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'e.g., Slack Notifications'}),
            'url': forms.URLInput(attrs={'class': 'form-control', 'placeholder': 'https://hooks.slack.com/services/...'}),
            'timeout_seconds': forms.NumberInput(attrs={'class': 'form-control', 'min': 1, 'max': 60}),
            'max_retries': forms.NumberInput(attrs={'class': 'form-control', 'min': 0, 'max': 10}),
            'retry_delay_seconds': forms.NumberInput(attrs={'class': 'form-control', 'min': 10, 'max': 3600}),
            'secret': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Optional: Secret key for HMAC signatures'}),
        }
        help_texts = {
            'url': 'The URL to send webhook POST requests to',
            'timeout_seconds': 'Request timeout in seconds (1-60)',
            'max_retries': 'Number of retry attempts on failure (0-10)',
            'retry_delay_seconds': 'Delay between retries in seconds',
            'secret': 'Optional secret key for webhook signature verification',
        }
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # On edit, render the stored JSON dicts as pretty text in the textareas.
        if self.instance and self.instance.pk:
            if self.instance.custom_headers:
                self.initial.setdefault(
                    'custom_headers', json.dumps(self.instance.custom_headers, indent=2)
                )
            if self.instance.provider_config:
                self.initial.setdefault(
                    'provider_config', json.dumps(self.instance.provider_config, indent=2)
                )
            self.initial.setdefault('provider', self.instance.provider)

    def _clean_json_object(self, field_name):
        """Parse a textarea field into a JSON object (dict); empty -> {}."""
        raw = (self.cleaned_data.get(field_name) or '').strip()
        if not raw:
            return {}
        try:
            parsed = json.loads(raw)
        except (ValueError, TypeError):
            raise forms.ValidationError("Enter valid JSON.")
        if not isinstance(parsed, dict):
            raise forms.ValidationError("Must be a JSON object (key/value pairs).")
        return parsed

    def clean_events(self):
        """Convert selected events to list format"""
        events = self.cleaned_data.get('events')
        if not events:
            raise forms.ValidationError("Please select at least one event type")
        return list(events)

    def clean_custom_headers(self):
        headers = self._clean_json_object('custom_headers')
        for key, value in headers.items():
            if not isinstance(key, str) or not isinstance(value, str):
                raise forms.ValidationError("Header names and values must both be strings.")
        return headers

    def clean_provider_config(self):
        return self._clean_json_object('provider_config')

    def clean_url(self):
        """Reject SSRF-prone targets (internal/private addresses, bad schemes)."""
        url = self.cleaned_data.get('url')
        if url:
            # validate_webhook_target raises django ValidationError, which
            # ModelForm surfaces as a field error.
            validate_webhook_target(url)
        return url


class WebhookTestForm(forms.Form):
    """Form for testing a webhook"""
    test_event = forms.ChoiceField(
        choices=[
            ('task.created', 'Task Created'),
            ('task.updated', 'Task Updated'),
            ('comment.added', 'Comment Added'),
        ],
        widget=forms.Select(attrs={'class': 'form-control'}),
        help_text="Choose an event type to test"
    )
