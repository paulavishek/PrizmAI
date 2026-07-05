from django import forms

from .models import (
    Requirement,
    RequirementCategory,
    RequirementComment,
)


class RequirementForm(forms.ModelForm):
    required_css_class = 'required'
    class Meta:
        model = Requirement
        fields = [
            'title', 'description', 'acceptance_criteria',
            'type', 'priority', 'status', 'category',
            'parent', 'assigned_reviewer', 'linked_goals',
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
            'linked_goals': forms.CheckboxSelectMultiple(attrs={'class': 'list-unstyled'}),
        }

    def __init__(self, *args, board=None, user=None, **kwargs):
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
            from kanban.models import OrganizationGoal
            workspace = getattr(board, 'workspace', None)
            # Fall back to the user's active workspace when the board has none (e.g. sandbox copies)
            if workspace is None and user is not None:
                try:
                    from accounts.models import UserProfile
                    profile = UserProfile.objects.filter(user=user).select_related('active_workspace').first()
                    workspace = getattr(profile, 'active_workspace', None) if profile else None
                except Exception:
                    pass
            if workspace:
                self.fields['linked_goals'].queryset = OrganizationGoal.objects.filter(
                    workspace=workspace
                ).order_by('name')
            else:
                self.fields['linked_goals'].queryset = OrganizationGoal.objects.none()
        self.fields['category'].required = False
        self.fields['parent'].required = False
        self.fields['assigned_reviewer'].required = False
        self.fields['linked_goals'].required = False


class RequirementCategoryForm(forms.ModelForm):
    required_css_class = 'required'
    class Meta:
        model = RequirementCategory
        fields = ['name', 'description']
        widgets = {
            'name': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Category name'}),
            'description': forms.Textarea(attrs={'class': 'form-control', 'rows': 2, 'placeholder': 'Optional description'}),
        }


class RequirementCommentForm(forms.ModelForm):
    class Meta:
        model = RequirementComment
        fields = ['content']
        widgets = {
            'content': forms.Textarea(attrs={'class': 'form-control', 'rows': 2, 'placeholder': 'Add a comment...'}),
        }
