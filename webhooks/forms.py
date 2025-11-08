"""
Forms for Webhook Management
"""
from django import forms
from webhooks.models import Webhook


class WebhookForm(forms.ModelForm):
    """Form for creating/editing webhooks"""
    
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
    
    class Meta:
        model = Webhook
        fields = [
            'name', 'url', 'events', 'is_active',
            'timeout_seconds', 'max_retries', 'retry_delay_seconds',
            'secret'
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
    
    def clean_events(self):
        """Convert selected events to list format"""
        events = self.cleaned_data.get('events')
        if not events:
            raise forms.ValidationError("Please select at least one event type")
        return list(events)


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
