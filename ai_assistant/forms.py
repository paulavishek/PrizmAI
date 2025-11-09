from django import forms
from .models import AIAssistantSession, UserPreference


class AISessionForm(forms.ModelForm):
    """Form for creating/editing AI Assistant sessions"""
    
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
        fields = [
            'enable_web_search',
            'enable_task_insights',
            'enable_risk_alerts',
            'enable_resource_recommendations',
            'notify_on_risk',
            'notify_on_overload',
            'notify_on_dependency_issues',
            'messages_per_page',
        ]
        widgets = {
            'enable_web_search': forms.CheckboxInput(attrs={
                'class': 'form-check-input',
            }),
            'enable_task_insights': forms.CheckboxInput(attrs={
                'class': 'form-check-input',
            }),
            'enable_risk_alerts': forms.CheckboxInput(attrs={
                'class': 'form-check-input',
            }),
            'enable_resource_recommendations': forms.CheckboxInput(attrs={
                'class': 'form-check-input',
            }),
            'notify_on_risk': forms.CheckboxInput(attrs={
                'class': 'form-check-input',
            }),
            'notify_on_overload': forms.CheckboxInput(attrs={
                'class': 'form-check-input',
            }),
            'notify_on_dependency_issues': forms.CheckboxInput(attrs={
                'class': 'form-check-input',
            }),
            'messages_per_page': forms.NumberInput(attrs={
                'class': 'form-control',
                'min': 5,
                'max': 100,
            }),
        }
