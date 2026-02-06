"""
Budget & ROI Tracking Forms
Forms for budget management, time tracking, and cost entry
"""
from django import forms
from django.core.validators import MinValueValidator
from django.core.exceptions import ValidationError
from django.db.models import Sum
from decimal import Decimal
from kanban.budget_models import (
    ProjectBudget, TaskCost, TimeEntry, ProjectROI, BudgetRecommendation
)


class ProjectBudgetForm(forms.ModelForm):
    """
    Form for creating/editing project budgets
    """
    class Meta:
        model = ProjectBudget
        fields = [
            'allocated_budget',
            'currency',
            'allocated_hours',
            'warning_threshold',
            'critical_threshold',
            'ai_optimization_enabled',
        ]
        widgets = {
            'allocated_budget': forms.NumberInput(attrs={
                'class': 'form-control',
                'placeholder': 'Enter allocated budget',
                'step': '0.01',
                'min': '0',
            }),
            'currency': forms.Select(attrs={
                'class': 'form-control',
            }),
            'allocated_hours': forms.NumberInput(attrs={
                'class': 'form-control',
                'placeholder': 'Enter allocated hours (optional)',
                'step': '0.5',
                'min': '0',
            }),
            'warning_threshold': forms.NumberInput(attrs={
                'class': 'form-control',
                'placeholder': 'Warning at % (e.g., 80)',
                'min': '1',
                'max': '100',
            }),
            'critical_threshold': forms.NumberInput(attrs={
                'class': 'form-control',
                'placeholder': 'Critical at % (e.g., 95)',
                'min': '1',
                'max': '100',
            }),
            'ai_optimization_enabled': forms.CheckboxInput(attrs={
                'class': 'form-check-input',
            }),
        }
        help_texts = {
            'allocated_budget': 'Total budget allocated for this project',
            'allocated_hours': 'Optional: Total hours budgeted for the project',
            'warning_threshold': 'Percentage at which to show warnings (default: 80%)',
            'critical_threshold': 'Percentage at which to show critical alerts (default: 95%)',
            'ai_optimization_enabled': 'Enable AI-powered budget optimization and recommendations',
        }
    
    def clean(self):
        cleaned_data = super().clean()
        warning = cleaned_data.get('warning_threshold')
        critical = cleaned_data.get('critical_threshold')
        
        if warning and critical and warning >= critical:
            raise forms.ValidationError(
                'Warning threshold must be less than critical threshold'
            )
        
        return cleaned_data


class TaskCostForm(forms.ModelForm):
    """
    Form for tracking task costs
    """
    class Meta:
        model = TaskCost
        fields = [
            'estimated_cost',
            'estimated_hours',
            'actual_cost',
            'hourly_rate',
            'resource_cost',
        ]
        widgets = {
            'estimated_cost': forms.NumberInput(attrs={
                'class': 'form-control',
                'placeholder': 'Estimated cost',
                'step': '0.01',
                'min': '0',
            }),
            'estimated_hours': forms.NumberInput(attrs={
                'class': 'form-control',
                'placeholder': 'Estimated hours',
                'step': '0.25',
                'min': '0',
            }),
            'actual_cost': forms.NumberInput(attrs={
                'class': 'form-control',
                'placeholder': 'Actual cost incurred',
                'step': '0.01',
                'min': '0',
            }),
            'hourly_rate': forms.NumberInput(attrs={
                'class': 'form-control',
                'placeholder': 'Hourly rate (optional)',
                'step': '0.01',
                'min': '0',
            }),
            'resource_cost': forms.NumberInput(attrs={
                'class': 'form-control',
                'placeholder': 'Resource/material costs',
                'step': '0.01',
                'min': '0',
            }),
        }
        help_texts = {
            'estimated_cost': 'Initial cost estimate for this task',
            'estimated_hours': 'Estimated hours to complete',
            'actual_cost': 'Actual costs incurred (excluding labor)',
            'hourly_rate': 'Hourly rate for labor cost calculation',
            'resource_cost': 'Cost of resources, materials, or third-party services',
        }


class TimeEntryForm(forms.ModelForm):
    """
    Form for logging time spent on tasks
    """
    class Meta:
        model = TimeEntry
        fields = [
            'hours_spent',
            'work_date',
            'description',
        ]
        widgets = {
            'hours_spent': forms.NumberInput(attrs={
                'class': 'form-control',
                'placeholder': 'Hours spent',
                'step': '0.25',
                'min': '0.01',
                'required': True,
            }),
            'work_date': forms.DateInput(attrs={
                'class': 'form-control',
                'type': 'date',
                'required': True,
            }),
            'description': forms.Textarea(attrs={
                'class': 'form-control',
                'placeholder': 'What did you work on? (optional)',
                'rows': 3,
            }),
        }
        help_texts = {
            'hours_spent': 'Number of hours spent on this task',
            'work_date': 'Date when the work was performed',
            'description': 'Optional description of work performed',
        }
    
    def __init__(self, *args, user=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.user = user
    
    def clean_hours_spent(self):
        """Validate hours with max limit and 0.25 increments"""
        hours = self.cleaned_data.get('hours_spent')
        if hours is None:
            return hours
        
        # Check maximum hours per entry
        if hours > Decimal('16.00'):
            raise ValidationError('Hours cannot exceed 16 per entry.')
        
        # Check minimum
        if hours <= Decimal('0'):
            raise ValidationError('Hours must be greater than 0.')
        
        # Round to nearest 0.25 increment
        rounded_hours = Decimal(str(round(float(hours) * 4) / 4))
        if rounded_hours != hours:
            # Auto-round and show message (don't reject)
            return rounded_hours
        
        return hours
    
    def clean(self):
        """Cross-field validation for daily total"""
        cleaned_data = super().clean()
        hours = cleaned_data.get('hours_spent')
        work_date = cleaned_data.get('work_date')
        
        if hours and work_date and self.user:
            # Calculate existing hours for that day (excluding current entry if editing)
            existing_qs = TimeEntry.objects.filter(
                user=self.user,
                work_date=work_date
            )
            if self.instance and self.instance.pk:
                existing_qs = existing_qs.exclude(pk=self.instance.pk)
            
            existing_hours = existing_qs.aggregate(
                total=Sum('hours_spent')
            )['total'] or Decimal('0.00')
            
            if existing_hours + hours > Decimal('24.00'):
                raise ValidationError(
                    f'Daily total would exceed 24 hours. '
                    f'You already have {existing_hours}h logged for {work_date}.'
                )
        
        return cleaned_data


class ProjectROIForm(forms.ModelForm):
    """
    Form for creating ROI snapshots
    """
    class Meta:
        model = ProjectROI
        fields = [
            'expected_value',
            'realized_value',
        ]
        widgets = {
            'expected_value': forms.NumberInput(attrs={
                'class': 'form-control',
                'placeholder': 'Expected value/revenue',
                'step': '0.01',
                'min': '0',
            }),
            'realized_value': forms.NumberInput(attrs={
                'class': 'form-control',
                'placeholder': 'Actual realized value',
                'step': '0.01',
                'min': '0',
            }),
        }
        help_texts = {
            'expected_value': 'Expected value or revenue from this project',
            'realized_value': 'Actual value realized (if completed)',
        }


class BudgetRecommendationActionForm(forms.Form):
    """
    Form for acting on budget recommendations
    """
    ACTION_CHOICES = [
        ('accept', 'Accept'),
        ('reject', 'Reject'),
        ('implemented', 'Mark as Implemented'),
    ]
    
    action = forms.ChoiceField(
        choices=ACTION_CHOICES,
        widget=forms.RadioSelect(attrs={
            'class': 'form-check-input',
        }),
        required=True,
    )
    
    notes = forms.CharField(
        widget=forms.Textarea(attrs={
            'class': 'form-control',
            'placeholder': 'Add notes about your decision (optional)',
            'rows': 3,
        }),
        required=False,
    )


class BudgetFilterForm(forms.Form):
    """
    Form for filtering budget views
    """
    date_from = forms.DateField(
        required=False,
        widget=forms.DateInput(attrs={
            'class': 'form-control',
            'type': 'date',
        }),
        label='From Date',
    )
    
    date_to = forms.DateField(
        required=False,
        widget=forms.DateInput(attrs={
            'class': 'form-control',
            'type': 'date',
        }),
        label='To Date',
    )
    
    STATUS_CHOICES = [
        ('all', 'All'),
        ('ok', 'OK'),
        ('warning', 'Warning'),
        ('critical', 'Critical'),
        ('over', 'Over Budget'),
    ]
    
    status = forms.ChoiceField(
        choices=STATUS_CHOICES,
        required=False,
        widget=forms.Select(attrs={
            'class': 'form-control',
        }),
    )


class QuickTimeEntryForm(forms.Form):
    """
    Quick time entry form for inline logging
    """
    hours = forms.DecimalField(
        max_digits=6,
        decimal_places=2,
        min_value=Decimal('0.01'),
        widget=forms.NumberInput(attrs={
            'class': 'form-control form-control-sm',
            'placeholder': 'Hours',
            'step': '0.25',
            'min': '0.01',
        }),
    )
    
    description = forms.CharField(
        max_length=200,
        required=False,
        widget=forms.TextInput(attrs={
            'class': 'form-control form-control-sm',
            'placeholder': 'What did you work on?',
        }),
    )
