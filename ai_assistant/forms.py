from django import forms
from .models import AIAssistantSession, UserPreference


class AISessionForm(forms.ModelForm):
    """Form for creating/editing AI Assistant sessions"""
    required_css_class = 'required'
    
    class Meta:
        model = AIAssistantSession
        fields = ['title', 'description', 'board']
        widgets = {
            'title': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Enter session title (e.g., "Project Planning")',
                'required': True,
            }),
            'description': forms.Textarea(attrs={
                'class': 'form-control',
                'placeholder': 'Optional: Describe what you want to discuss',
                'rows': 3,
            }),
            'board': forms.Select(attrs={
                'class': 'form-select',
            }),
        }


class UserPreferenceForm(forms.ModelForm):
    """Form for user AI preferences"""
    
    class Meta:
        model = UserPreference
        # NOTE: enable_web_search and the notify_on_* fields are intentionally
        # NOT exposed here. Web search is disabled product-wide (ENABLE_WEB_SEARCH
        # defaults off + Spectra has no live web access), and nothing consumes the
        # notification flags, so showing them would mislead users. The model fields
        # are retained for compatibility.
        fields = [
            'enable_task_insights',
            'enable_risk_alerts',
            'enable_resource_recommendations',
            'messages_per_page',
        ]
        widgets = {
            'enable_task_insights': forms.CheckboxInput(attrs={
                'class': 'form-check-input',
            }),
            'enable_risk_alerts': forms.CheckboxInput(attrs={
                'class': 'form-check-input',
            }),
            'enable_resource_recommendations': forms.CheckboxInput(attrs={
                'class': 'form-check-input',
            }),
            'messages_per_page': forms.NumberInput(attrs={
                'class': 'form-control',
                'min': 5,
                'max': 100,
            }),
        }
