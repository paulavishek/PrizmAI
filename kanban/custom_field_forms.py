"""
Forms for the Custom Fields admin UI.

The field-definition form is a ModelForm. Option rows for list-type fields
are POSTed as parallel arrays (option_values[], option_defaults[],
option_positions[]) which we parse in the view — simpler than a formset
given the small expected count (<20 options per field).
"""

from django import forms

from .custom_field_models import CustomFieldDefinition, FIELD_TYPE_LIST


class CustomFieldDefinitionForm(forms.ModelForm):
    class Meta:
        model = CustomFieldDefinition
        fields = [
            'name',
            'field_type',
            'is_required',
            'is_multi_select',
            'default_text',
            'default_number',
            'default_date',
            'default_boolean',
            'exclude_from_ai',
            'applies_to_epics',
        ]
        widgets = {
            'name': forms.TextInput(attrs={'class': 'form-control'}),
            'field_type': forms.Select(attrs={'class': 'form-select'}),
            'default_text': forms.TextInput(attrs={'class': 'form-control'}),
            'default_number': forms.NumberInput(attrs={'class': 'form-control', 'step': 'any'}),
            'default_date': forms.DateInput(attrs={'class': 'form-control', 'type': 'date'}),
            'is_required': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
            'exclude_from_ai': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
            'applies_to_epics': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
        }

    def __init__(self, *args, workspace=None, sandbox_owner=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.workspace = workspace
        # Demo per-user scope: uniqueness is checked within the same
        # sandbox_owner partition so two demo users can each own a same-named
        # field (mirrors the DB constraint on (workspace, sandbox_owner, name)).
        # On edit, prefer the instance's existing owner.
        self.sandbox_owner = (
            getattr(self.instance, 'sandbox_owner', None) or sandbox_owner
        )

    def clean_name(self):
        name = (self.cleaned_data.get('name') or '').strip()
        if not name:
            raise forms.ValidationError("Name is required.")

        # Enforce active-name uniqueness per (workspace, sandbox_owner) (mirrors
        # the DB constraint with a friendly error). The DB constraint is the
        # safety net.
        if self.workspace is not None:
            qs = CustomFieldDefinition.objects.filter(
                workspace=self.workspace, name__iexact=name, is_active=True,
                sandbox_owner=self.sandbox_owner,
            )
            if self.instance.pk:
                qs = qs.exclude(pk=self.instance.pk)
            if qs.exists():
                raise forms.ValidationError(
                    f"A custom field named '{name}' already exists in this workspace."
                )
        return name

    def clean(self):
        cleaned = super().clean()
        field_type = cleaned.get('field_type')
        if field_type != FIELD_TYPE_LIST and cleaned.get('is_multi_select'):
            cleaned['is_multi_select'] = False  # Silently coerce — only meaningful for lists.
        return cleaned
