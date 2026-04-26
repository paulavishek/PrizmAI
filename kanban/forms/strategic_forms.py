from django import forms
from django.contrib.auth.models import User

from ..models import (
    OrganizationGoal, Mission, Strategy,
    GoalVersion, Milestone,
)


CHANGE_REASON_CHOICES = GoalVersion.CHANGE_REASON_CHOICES


class GoalEditForm(forms.ModelForm):
    required_css_class = 'required'
    change_reason = forms.ChoiceField(
        choices=CHANGE_REASON_CHOICES,
        widget=forms.RadioSelect,
        label='Change reason',
    )
    change_notes = forms.CharField(
        required=False,
        widget=forms.Textarea(attrs={'rows': 2, 'placeholder': 'Why is this changing?'}),
        label='Notes (optional)',
    )
    owner = forms.ModelChoiceField(
        queryset=User.objects.all(),
        required=False,
        label='Owner',
    )

    class Meta:
        model = OrganizationGoal
        fields = ['name', 'description', 'target_date', 'owner', 'target_metric', 'status']
        widgets = {
            'target_date': forms.DateInput(attrs={'type': 'date'}),
            'description': forms.Textarea(attrs={'rows': 4}),
        }


class MissionEditForm(forms.ModelForm):
    required_css_class = 'required'
    change_reason = forms.ChoiceField(
        choices=CHANGE_REASON_CHOICES,
        widget=forms.RadioSelect,
        label='Change reason',
    )
    change_notes = forms.CharField(
        required=False,
        widget=forms.Textarea(attrs={'rows': 2, 'placeholder': 'Why is this changing?'}),
        label='Notes (optional)',
    )
    owner = forms.ModelChoiceField(
        queryset=User.objects.all(),
        required=False,
        label='Owner',
    )

    class Meta:
        model = Mission
        fields = ['name', 'description', 'due_date', 'owner', 'status']
        widgets = {
            'due_date': forms.DateInput(attrs={'type': 'date'}),
            'description': forms.Textarea(attrs={'rows': 4}),
        }


class StrategyEditForm(forms.ModelForm):
    required_css_class = 'required'
    change_reason = forms.ChoiceField(
        choices=CHANGE_REASON_CHOICES,
        widget=forms.RadioSelect,
        label='Change reason',
    )
    change_notes = forms.CharField(
        required=False,
        widget=forms.Textarea(attrs={'rows': 2, 'placeholder': 'Why is this changing?'}),
        label='Notes (optional)',
    )
    owner = forms.ModelChoiceField(
        queryset=User.objects.all(),
        required=False,
        label='Owner',
    )

    class Meta:
        model = Strategy
        fields = ['name', 'description', 'due_date', 'owner', 'status']
        widgets = {
            'due_date': forms.DateInput(attrs={'type': 'date'}),
            'description': forms.Textarea(attrs={'rows': 4}),
        }


class MilestoneForm(forms.ModelForm):
    required_css_class = 'required'
    class Meta:
        model = Milestone
        fields = ['name', 'due_date', 'status']
        widgets = {
            'due_date': forms.DateInput(attrs={'type': 'date'}),
        }
