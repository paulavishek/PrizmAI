from django import forms

from .models import (
    ProjectObjective,
    Requirement,
    RequirementCategory,
    RequirementComment,
)


class RequirementForm(forms.ModelForm):
    class Meta:
        model = Requirement
        fields = [
            'title', 'description', 'acceptance_criteria',
            'type', 'priority', 'status', 'category',
            'parent', 'assigned_reviewer',
        ]
        widgets = {
            'title': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Requirement title'}),
            'description': forms.Textarea(attrs={'class': 'form-control', 'rows': 4, 'placeholder': 'Detailed requirement description'}),
            'acceptance_criteria': forms.Textarea(attrs={'class': 'form-control', 'rows': 3, 'placeholder': 'How to verify this requirement is met'}),
            'type': forms.Select(attrs={'class': 'form-select'}),
            'priority': forms.Select(attrs={'class': 'form-select'}),
            'status': forms.Select(attrs={'class': 'form-select'}),
            'category': forms.Select(attrs={'class': 'form-select'}),
            'parent': forms.Select(attrs={'class': 'form-select'}),
            'assigned_reviewer': forms.Select(attrs={'class': 'form-select'}),
        }

    def __init__(self, *args, board=None, **kwargs):
        super().__init__(*args, **kwargs)
        if board:
            self.fields['category'].queryset = RequirementCategory.objects.filter(board=board)
            self.fields['parent'].queryset = Requirement.objects.filter(board=board)
            if self.instance and self.instance.pk:
                self.fields['parent'].queryset = self.fields['parent'].queryset.exclude(pk=self.instance.pk)
            # Board members as reviewer options
            from kanban.models import BoardMembership
            member_ids = BoardMembership.objects.filter(board=board).values_list('user_id', flat=True)
            from django.contrib.auth.models import User
            self.fields['assigned_reviewer'].queryset = User.objects.filter(id__in=member_ids)
        self.fields['category'].required = False
        self.fields['parent'].required = False
        self.fields['assigned_reviewer'].required = False


class RequirementCategoryForm(forms.ModelForm):
    class Meta:
        model = RequirementCategory
        fields = ['name', 'description']
        widgets = {
            'name': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Category name'}),
            'description': forms.Textarea(attrs={'class': 'form-control', 'rows': 2, 'placeholder': 'Optional description'}),
        }


class ProjectObjectiveForm(forms.ModelForm):
    class Meta:
        model = ProjectObjective
        fields = ['title', 'description']
        widgets = {
            'title': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Objective title'}),
            'description': forms.Textarea(attrs={'class': 'form-control', 'rows': 3, 'placeholder': 'Describe what this objective aims to achieve'}),
        }


class RequirementCommentForm(forms.ModelForm):
    class Meta:
        model = RequirementComment
        fields = ['content']
        widgets = {
            'content': forms.Textarea(attrs={'class': 'form-control', 'rows': 2, 'placeholder': 'Add a comment...'}),
        }
