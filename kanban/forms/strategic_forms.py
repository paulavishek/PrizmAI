from django import forms
from django.contrib.auth.models import User
from django.db.models import Q

from ..models import (
    OrganizationGoal, Mission, Strategy,
    GoalVersion,
)


CHANGE_REASON_CHOICES = GoalVersion.CHANGE_REASON_CHOICES


def _owner_queryset(workspace, instance=None, current_user=None):
    """
    Users eligible to be picked as owner: members of the given workspace
    (via WorkspaceMembership, the real-org path, or BoardMembership on one
    of the workspace's non-sandbox boards, the demo path — WorkspaceMembership
    rows aren't created for demo personas). Sandbox-copy boards are excluded
    from the BoardMembership side because every user's personal sandbox
    denormalizes to the same shared demo workspace (isolation there is
    per-Board.owner, not per-workspace) — including them would leak other
    users' private sandbox membership into this dropdown. Always keeps the
    record's existing owner and the user doing the editing selectable, even
    if they've since lost membership, so the dropdown never silently drops
    the current value.
    """
    if workspace is None:
        qs = User.objects.none()
    else:
        qs = User.objects.filter(
            Q(board_memberships__board__workspace=workspace,
              board_memberships__board__is_sandbox_copy=False) |
            Q(workspace_memberships__workspace=workspace)
        )

    keep_ids = set()
    if instance is not None and instance.pk and instance.owner_id:
        keep_ids.add(instance.owner_id)
    if current_user is not None:
        keep_ids.add(current_user.pk)
    if keep_ids:
        qs = qs | User.objects.filter(id__in=keep_ids)

    return qs.distinct().order_by('username')


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

    def __init__(self, *args, workspace=None, current_user=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['owner'].queryset = _owner_queryset(workspace, self.instance, current_user)

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

    def __init__(self, *args, workspace=None, current_user=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['owner'].queryset = _owner_queryset(workspace, self.instance, current_user)

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

    def __init__(self, *args, workspace=None, current_user=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['owner'].queryset = _owner_queryset(workspace, self.instance, current_user)

    class Meta:
        model = Strategy
        fields = ['name', 'description', 'due_date', 'owner', 'status']
        widgets = {
            'due_date': forms.DateInput(attrs={'type': 'date'}),
            'description': forms.Textarea(attrs={'rows': 4}),
        }
