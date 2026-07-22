from django import forms
from integrations.models import GitHubIntegration
from kanban.models import Column


class GitHubIntegrationForm(forms.ModelForm):

    class Meta:
        model = GitHubIntegration
        fields = ["repo_full_name", "in_review_column", "is_active"]
        widgets = {
            "repo_full_name": forms.TextInput(attrs={
                "class": "form-control",
                "placeholder": "owner/repository — e.g. acme/backend",
            }),
            "is_active": forms.CheckboxInput(attrs={"class": "form-check-input"}),
        }
        labels = {
            "repo_full_name": "GitHub Repository",
            "in_review_column": '"In Review" Column',
            "is_active": "Integration Active",
        }
        help_texts = {
            "repo_full_name": 'Format: owner/repo — must match the GitHub repository exactly.',
            "in_review_column": "Tasks mentioned in a PR will be moved to this column.",
        }

    def __init__(self, *args, board=None, **kwargs):
        super().__init__(*args, **kwargs)
        if board is not None:
            # Restrict column choices to this board only.
            self.fields["in_review_column"].queryset = Column.objects.filter(
                board=board
            ).order_by("position")
            self.fields["in_review_column"].widget = forms.Select(
                attrs={"class": "form-select"}
            )
        self.fields["in_review_column"].required = False
