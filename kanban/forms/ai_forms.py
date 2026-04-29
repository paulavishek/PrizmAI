"""
ai_forms.py — Django forms for AI provider settings.

These forms are used on:
  - Workspace Settings page  (OrganizationAISettingsForm)  — Org Admins only
  - Profile page             (UserAISettingsForm)           — all logged-in users
"""

from django import forms
from django.core.exceptions import ValidationError

from ai_assistant.models import PROVIDER_CHOICES, USER_PROVIDER_CHOICES

# A blank-prefixed version of PROVIDER_CHOICES used for the optional BYOK
# provider selectors.
_BYOK_PROVIDER_CHOICES = [('', '--- Select provider ---')] + list(PROVIDER_CHOICES)


class OrganizationAISettingsForm(forms.Form):
    """
    Form for Org Admins to configure the organisation-wide AI provider and
    optional BYOK (Bring Your Own Key) API key.

    Rendered on: kanban/workspace_preset_settings.html
    Processed in: kanban.views.workspace_preset_settings (POST, form_type='ai_settings')
    """

    provider = forms.ChoiceField(
        choices=PROVIDER_CHOICES,
        widget=forms.Select(attrs={'class': 'form-select'}),
        label='Default AI Provider',
    )

    allow_user_provider_override = forms.BooleanField(
        required=False,
        widget=forms.CheckboxInput(attrs={'class': 'form-check-input'}),
        label='Allow team members to choose their own AI provider',
    )

    byok_provider = forms.ChoiceField(
        choices=_BYOK_PROVIDER_CHOICES,
        required=False,
        widget=forms.Select(attrs={'class': 'form-select'}),
        label='BYOK Key Provider',
    )

    raw_api_key = forms.CharField(
        required=False,
        widget=forms.PasswordInput(
            attrs={'class': 'form-control', 'autocomplete': 'off'},
            render_value=False,
        ),
        label='API Key',
        help_text=(
            'Leave blank to keep your existing key. '
            'Enter a new key to replace it.'
        ),
    )

    remove_byok_key = forms.BooleanField(
        required=False,
        widget=forms.CheckboxInput(attrs={'class': 'form-check-input'}),
        label='Remove stored API key',
    )

    def clean(self):
        cleaned = super().clean()
        raw_key = cleaned.get('raw_api_key', '').strip()
        byok_provider = cleaned.get('byok_provider', '').strip()
        remove = cleaned.get('remove_byok_key', False)

        if raw_key and not byok_provider:
            raise ValidationError(
                'Please select which provider this API key belongs to.'
            )

        if remove and raw_key:
            raise ValidationError(
                'You cannot enter a new key and remove the key at the same time.'
            )

        # Normalise empty string back to None-equivalent for the view
        if not raw_key:
            cleaned['raw_api_key'] = ''
        else:
            cleaned['raw_api_key'] = raw_key

        return cleaned
