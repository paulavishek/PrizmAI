# kanban/stakeholder_forms.py
"""
Forms for stakeholder engagement tracking and management
"""

from django import forms
from .stakeholder_models import (
    ProjectStakeholder, StakeholderTaskInvolvement, 
    StakeholderEngagementRecord, StakeholderTag
)


class ProjectStakeholderForm(forms.ModelForm):
    """Form for creating and updating project stakeholders"""
    required_css_class = 'required'
    
    class Meta:
        model = ProjectStakeholder
        fields = [
            'name', 'role', 'organization', 'email', 'phone',
            'influence_level', 'interest_level', 
            'current_engagement', 'desired_engagement',
            'notes', 'is_active'
        ]
        widgets = {
            'name': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Stakeholder name'
            }),
            'role': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'e.g., Project Manager, Client Lead'
            }),
            'organization': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Department or organization'
            }),
            'email': forms.EmailInput(attrs={
                'class': 'form-control',
                'placeholder': 'stakeholder@example.com'
            }),
            'phone': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': '+1 (555) 123-4567'
            }),
            'influence_level': forms.Select(attrs={
                'class': 'form-select'
            }),
            'interest_level': forms.Select(attrs={
                'class': 'form-select'
            }),
            'current_engagement': forms.Select(attrs={
                'class': 'form-select'
            }),
            'desired_engagement': forms.Select(attrs={
                'class': 'form-select'
            }),
            'notes': forms.Textarea(attrs={
                'class': 'form-control',
                'rows': 4,
                'placeholder': 'Additional notes about this stakeholder'
            }),
            'is_active': forms.CheckboxInput(attrs={
                'class': 'form-check-input'
            }),
        }


class StakeholderTaskInvolvementForm(forms.ModelForm):
    """Form for recording stakeholder involvement in tasks"""
    required_css_class = 'required'
    
    class Meta:
        model = StakeholderTaskInvolvement
        fields = [
            'involvement_type', 'engagement_status',
            'satisfaction_rating', 'feedback', 'concerns'
        ]
        widgets = {
            'involvement_type': forms.Select(attrs={
                'class': 'form-select'
            }),
            'engagement_status': forms.Select(attrs={
                'class': 'form-select'
            }),
            'satisfaction_rating': forms.Select(attrs={
                'class': 'form-select'
            }),
            'feedback': forms.Textarea(attrs={
                'class': 'form-control',
                'rows': 3,
                'placeholder': 'Stakeholder feedback on this task'
            }),
            'concerns': forms.Textarea(attrs={
                'class': 'form-control',
                'rows': 3,
                'placeholder': 'Any concerns or issues raised'
            }),
        }


class StakeholderEngagementRecordForm(forms.ModelForm):
    """Form for recording stakeholder engagement activities"""
    required_css_class = 'required'
    
    class Meta:
        model = StakeholderEngagementRecord
        fields = [
            'date', 'description', 'communication_channel',
            'outcome', 'follow_up_required', 'follow_up_date',
            'engagement_sentiment', 'satisfaction_rating', 'notes'
        ]
        widgets = {
            'date': forms.DateInput(attrs={
                'class': 'form-control',
                'type': 'date'
            }),
            'description': forms.Textarea(attrs={
                'class': 'form-control',
                'rows': 4,
                'placeholder': 'Describe the engagement activity'
            }),
            'communication_channel': forms.Select(attrs={
                'class': 'form-select'
            }),
            'outcome': forms.Textarea(attrs={
                'class': 'form-control',
                'rows': 3,
                'placeholder': 'Outcome or results of the engagement'
            }),
            'follow_up_required': forms.CheckboxInput(attrs={
                'class': 'form-check-input'
            }),
            'follow_up_date': forms.DateInput(attrs={
                'class': 'form-control',
                'type': 'date'
            }),
            'engagement_sentiment': forms.Select(attrs={
                'class': 'form-select'
            }),
            'satisfaction_rating': forms.Select(attrs={
                'class': 'form-select'
            }),
            'notes': forms.Textarea(attrs={
                'class': 'form-control',
                'rows': 2,
                'placeholder': 'Additional notes'
            }),
        }


class StakeholderTagForm(forms.ModelForm):
    """Form for creating and updating stakeholder tags"""
    required_css_class = 'required'
    
    class Meta:
        model = StakeholderTag
        fields = ['name', 'color']
        widgets = {
            'name': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Tag name (e.g., Executive, Technical)'
            }),
            'color': forms.TextInput(attrs={
                'class': 'form-control',
                'type': 'color'
            }),
        }


class BulkStakeholderImportForm(forms.Form):
    """Form for importing stakeholders from CSV"""
    
    csv_file = forms.FileField(
        label='CSV File',
        help_text='Upload a CSV file with columns: name, role, organization, email, phone, influence_level, interest_level',
        widget=forms.FileInput(attrs={
            'class': 'form-control',
            'accept': '.csv'
        })
    )
    
    overwrite_existing = forms.BooleanField(
        required=False,
        label='Overwrite existing stakeholders with same email',
        widget=forms.CheckboxInput(attrs={
            'class': 'form-check-input'
        })
    )
