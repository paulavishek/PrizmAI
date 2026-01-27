# Implementation Plan: Remove Organization & Fix Demo Reset

## Overview

This plan implements two major changes for MVP simplification:
1. **Remove Organization entirely** - All users (including demo users) share the same space
2. **Fix Reset Demo robustness** - Reset can recover from any state including deleted demo data

---

## Part 1: Remove Organization Model

### Current State
Organization is a ForeignKey in these models:
- `accounts/models.py:31` - UserProfile.organization
- `kanban/models.py:31` - Board.organization
- `wiki/models.py:23` - WikiCategory.organization
- `wiki/models.py:56` - WikiPage.organization
- `wiki/models.py:270` - MeetingNote.organization
- `wiki/models.py:455` - WikiMeetingAnalysis.organization

135 files reference "organization" - this is a significant refactoring.

### Implementation Phases

#### Phase 1A: Make organization optional (nullable)
Instead of deleting immediately, first make organization optional to minimize breakage.

**Files to modify:**
1. `accounts/models.py` - Make `UserProfile.organization` nullable
2. `kanban/models.py` - Make `Board.organization` nullable
3. `wiki/models.py` - Make all organization ForeignKeys nullable

```python
# Example change in accounts/models.py
organization = models.ForeignKey(
    Organization,
    on_delete=models.SET_NULL,  # Changed from CASCADE
    related_name='members',
    null=True,      # NEW
    blank=True      # NEW
)
```

#### Phase 1B: Update views to not require organization

**accounts/views.py changes:**
- `create_organization()` - Remove or redirect to dashboard
- `join_organization()` - Remove or redirect to dashboard
- `organization_choice()` - Remove, redirect to dashboard after signup
- `register_view()` - Remove domain validation

**accounts/forms/__init__.py changes:**
- `RegistrationForm` - Remove domain validation, remove organization requirement
- Remove `OrganizationForm`, `JoinOrganizationForm`

#### Phase 1C: Update all organization filtering

**Key views to update:**
- `kanban/views.py` - Remove organization filtering from board queries
- `kanban/demo_views.py` - Remove organization checks
- `messaging/views.py` - `get_mentions()` returns all users
- `wiki/views.py` - Remove organization filtering
- `ai_assistant/views.py` - Remove organization filtering

**Pattern to find and replace:**
```python
# FROM:
Board.objects.filter(organization=request.user.profile.organization)

# TO:
Board.objects.all()
```

#### Phase 1D: Update signup flow

**New signup flow:**
1. User registers with email (any email, no domain validation)
2. Email verification sent
3. After verification, user logs in
4. User goes directly to dashboard (no organization choice)
5. UserProfile created without organization

**Files:**
- `accounts/views.py` - Simplify registration
- `accounts/urls.py` - Remove organization_choice, join_organization, create_organization URLs
- `templates/accounts/` - Update templates

#### Phase 1E: Database migration

Create migrations to:
1. Make organization fields nullable
2. Data migration to set existing records to NULL if needed

---

## Part 2: Fix Demo Reset Robustness

### Current Problem
`reset_demo_data()` in `kanban/demo_views.py:986-1179`:
- Assumes demo organization exists
- Assumes demo boards exist
- Fails if user deleted demo boards

### Solution: Self-Healing Reset

#### Step 1: Modify reset order

**File:** `kanban/demo_views.py` - `reset_demo_data()`

```python
def reset_demo_data(request):
    if request.method == 'POST':
        try:
            from django.core.management import call_command
            from io import StringIO
            out = StringIO()

            # STEP 1: Ensure demo foundation exists (org, users, boards)
            # This recreates everything from scratch if deleted
            call_command('create_demo_organization', '--reset', stdout=out, stderr=out)

            # STEP 2: Populate all demo content
            call_command('populate_all_demo_data', '--reset', stdout=out, stderr=out)

            # STEP 3: Refresh dates
            try:
                call_command('refresh_demo_dates', '--force', stdout=out, stderr=out)
            except: pass

            # STEP 4: Detect conflicts
            try:
                call_command('detect_conflicts', '--clear', stdout=out, stderr=out)
            except: pass

            messages.success(request, 'Demo data reset successfully!')
            return redirect('demo_dashboard')
```

#### Step 2: Add self-healing to populate_all_demo_data.py

**File:** `kanban/management/commands/populate_all_demo_data.py`

Before querying for demo data, auto-create if missing:
```python
def handle(self, *args, **options):
    # Self-healing: ensure demo org exists
    try:
        self.demo_org = Organization.objects.get(is_demo=True)
    except Organization.DoesNotExist:
        call_command('create_demo_organization')
        self.demo_org = Organization.objects.get(is_demo=True)

    # Self-healing: ensure demo boards exist
    self.demo_boards = Board.objects.filter(
        organization=self.demo_org,
        is_official_demo_board=True
    )
    if self.demo_boards.count() < 3:
        call_command('create_demo_organization')
        self.demo_boards = Board.objects.filter(
            organization=self.demo_org,
            is_official_demo_board=True
        )
```

---

## Part 3: Post-Organization Removal Adjustments

After organization is removed, these features need adjustment:

### Demo Data Commands
Update these commands to not require organization:
- `create_demo_organization.py` - Rename to `create_demo_data.py`, creates demo users and boards
- `populate_all_demo_data.py` - Remove organization references
- `populate_demo_data.py` - Remove organization references

### Views with Organization Filtering
Remove organization filtering from:
- Board queries - show all boards user is member of
- Wiki queries - show all wiki pages
- Messaging - show all users in mentions

---

## Files to Modify (Summary)

### High Priority (Core Changes)
| File | Changes |
|------|---------|
| `accounts/models.py` | Make organization nullable/optional |
| `accounts/views.py` | Simplify signup, remove org choice/creation |
| `accounts/forms/__init__.py` | Remove domain validation, org forms |
| `accounts/urls.py` | Remove org-related URLs |
| `kanban/models.py` | Make Board.organization nullable |
| `kanban/demo_views.py` | Fix reset order, add self-healing |
| `kanban/views.py` | Remove organization filtering |
| `messaging/views.py` | Update get_mentions() |

### Medium Priority (Feature Updates)
| File | Changes |
|------|---------|
| `wiki/models.py` | Make organization nullable |
| `wiki/views.py` | Remove organization filtering |
| `ai_assistant/views.py` | Remove organization filtering |
| `kanban/management/commands/create_demo_organization.py` | Add self-healing |
| `kanban/management/commands/populate_all_demo_data.py` | Add self-healing |

### Low Priority (Cleanup)
- Remove unused organization templates
- Update tests
- Clean up management commands

---

## Implementation Order

1. **Phase 1: Fix Reset First** (Lower risk)
   - Modify `reset_demo_data()` to call `create_demo_organization --reset` first
   - Add self-healing to `populate_all_demo_data.py`
   - Test reset from various states

2. **Phase 2: Make Organization Optional** (Medium risk)
   - Create migration to make organization nullable
   - Update views to handle null organization
   - Keep Organization model but make it optional

3. **Phase 3: Simplify Signup** (Medium risk)
   - Remove domain validation
   - Skip organization choice after signup
   - Auto-create UserProfile without organization

4. **Phase 4: Remove Organization Filtering** (Higher risk)
   - Update all views to not filter by organization
   - All users see all content
   - Demo users visible to everyone

---

## Part 4: First Login Welcome Modal

### Purpose
Show new users a welcome modal explaining:
- Demo users (Alex Chen, Sam Rivera, Jordan Taylor) are available to explore collaboration features
- In real-world scenarios, users would invite their team members
- Reset demo button can restore original demo data anytime

### Implementation

**File:** `templates/kanban/dashboard.html` or new `templates/includes/welcome_modal.html`

Add welcome modal that shows on first login:
```html
{% if not user.profile.has_seen_welcome %}
<div class="modal fade" id="welcomeModal" tabindex="-1">
  <div class="modal-dialog modal-dialog-centered">
    <div class="modal-content">
      <div class="modal-header">
        <h5 class="modal-title">Welcome to PrizmAI!</h5>
      </div>
      <div class="modal-body">
        <p>To help you explore all features, we've set up demo data including:</p>
        <ul>
          <li><strong>Demo Team Members:</strong> Alex Chen, Sam Rivera, Jordan Taylor</li>
          <li><strong>Sample Boards:</strong> Software Development, Marketing Campaign, Bug Tracking</li>
        </ul>
        <p class="text-muted">
          <i class="bi bi-info-circle"></i> In your real workspace, you would invite
          your actual team members. The <strong>Reset Demo</strong> button restores
          all demo data anytime.
        </p>
      </div>
      <div class="modal-footer">
        <button type="button" class="btn btn-primary" data-bs-dismiss="modal">
          Get Started
        </button>
      </div>
    </div>
  </div>
</div>
<script>
document.addEventListener('DOMContentLoaded', function() {
  new bootstrap.Modal(document.getElementById('welcomeModal')).show();
});
</script>
{% endif %}
```

**File:** `accounts/models.py` - Add flag to UserProfile:
```python
has_seen_welcome = models.BooleanField(default=False)
```

**File:** `kanban/views.py` - Mark welcome as seen:
```python
def dashboard(request):
    # ... existing code ...
    if not request.user.profile.has_seen_welcome:
        request.user.profile.has_seen_welcome = True
        request.user.profile.save()
```

---

## Verification Plan

### Test Reset Robustness
```bash
# Test 1: Delete a demo board, then reset
python manage.py shell
>>> from kanban.models import Board
>>> Board.objects.filter(is_official_demo_board=True).first().delete()
# Then click Reset Demo in UI - should recover

# Test 2: Delete all demo data, then reset
python manage.py shell
>>> from accounts.models import Organization
>>> Organization.objects.filter(is_demo=True).delete()
# Then click Reset Demo - should recreate everything
```

### Test Signup Flow
1. Register new user with any email (e.g., test@gmail.com)
2. Verify email
3. Login - should go directly to dashboard
4. Should see demo boards and demo users

### Test Messaging
1. Go to Messages
2. Type @ to mention someone
3. Should see all users including demo users (Alex, Sam, Jordan)

### Run Tests
```bash
python manage.py test accounts
python manage.py test kanban
python manage.py test messaging
python manage.py test wiki
```
