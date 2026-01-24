# RBAC Simplification Decision

**Date:** January 2026
**Context:** Architecture simplification for PrizmAI portfolio project
**Status:** Decision documented - implementation pending

---

## Table of Contents

1. [Background](#background)
2. [Current RBAC Implementation](#current-rbac-implementation)
3. [The Strategic Question](#the-strategic-question)
4. [Analysis: Complexity vs. Value](#analysis-complexity-vs-value)
5. [Decision](#decision)
6. [Rationale](#rationale)
7. [Technical Implications](#technical-implications)
8. [Benefits of Simplification](#benefits-of-simplification)
9. [Implementation Guidance](#implementation-guidance)
10. [Appendix: Current System Details](#appendix-current-system-details)

---

## Background

PrizmAI currently implements a comprehensive Role-Based Access Control (RBAC) system inspired by enterprise project management tools. This includes:

- Multiple user roles with hierarchical permissions
- Granular permission system (56+ distinct permissions)
- Column-level workflow restrictions
- Permission override mechanisms
- Comprehensive audit logging
- Two demo modes (Solo vs. Team) to showcase RBAC capabilities

The system was built to demonstrate technical sophistication and enterprise-ready features. However, as a portfolio project targeting PM positions at companies like Google and Amazon, a strategic question emerged about whether this complexity serves the project's goals.

---

## Current RBAC Implementation

### Overview

**Scale of Implementation:**
- **5 Database Models:** Role, BoardMembership, PermissionOverride, ColumnPermission, PermissionAuditLog
- **500+ Lines of Code:** Just for permission models
- **89 Permission Checks:** Across 13 different files
- **56+ Permissions:** Covering every possible action
- **5 Default Roles:** Owner, Admin, Editor, Member, Viewer

### Role Hierarchy

```
Owner (admin.full)
  ├─ Full organization control
  └─ Cannot be removed

Admin (admin.full)
  ├─ Full administrative access
  └─ Board management capabilities

Editor
  ├─ board.view, board.export
  ├─ column.create, column.edit, column.reorder
  ├─ task.* (all task permissions)
  ├─ comment.view, comment.create, comment.edit_own, comment.delete_own
  ├─ label.view, label.create, label.assign
  ├─ file.view, file.upload, file.download, file.delete
  └─ analytics.view

Member
  ├─ board.view
  ├─ task.view, task.create, task.edit_own, task.move
  ├─ comment.view, comment.create, comment.edit_own, comment.delete_own
  ├─ label.view, label.assign
  └─ file.view, file.upload, file.download

Viewer (Read-only)
  ├─ board.view
  ├─ task.view
  ├─ comment.view
  ├─ label.view
  ├─ file.view, file.download
  └─ analytics.view
```

### Permission Categories

**Board Permissions (6):**
- board.view, board.create, board.edit, board.delete
- board.manage_members, board.export

**Column Permissions (4):**
- column.create, column.edit, column.delete, column.reorder

**Task Permissions (9):**
- task.view, task.view_own, task.create
- task.edit, task.edit_own
- task.delete, task.delete_own
- task.assign, task.move

**Comment Permissions (6):**
- comment.view, comment.create
- comment.edit, comment.edit_own
- comment.delete, comment.delete_own

**Label Permissions (5):**
- label.view, label.create, label.edit, label.delete, label.assign

**File Permissions (4):**
- file.view, file.upload, file.download, file.delete

**Advanced Permissions (6):**
- webhook.manage, api.access, analytics.view, audit.view
- data.export, data.import

**Administrative (1):**
- admin.full

### Advanced Features

**Permission Overrides:**
- Allow granting specific permissions beyond a role
- Allow explicitly denying permissions even if role has them
- Time-limited overrides with expiration
- Audit trail for all override changes

**Column-Level Restrictions:**
- can_move_to: Control which roles can move tasks INTO a column
- can_move_from: Control which roles can move tasks OUT OF a column
- can_create_in: Control task creation in specific columns
- can_edit_in: Control task editing in specific columns

**Audit Logging:**
- Tracks all permission changes
- Records role assignments/removals
- Logs permission grants/revocations
- Captures IP address and user agent
- Full audit trail for compliance

### Demo Mode Implementation

**Solo Mode (~5 min):**
- User gets full admin access
- Explores all features independently
- No permission restrictions
- Focus on product capabilities

**Team Mode (~10 min):**
- User can switch between roles (Admin, Member, Viewer)
- Experiences permission restrictions in action
- Sees approval workflows
- Understands team collaboration features

**Purpose:**
- Demonstrate RBAC sophistication to potential enterprise users
- Show understanding of team workflow management
- Highlight security and compliance features

---

## The Strategic Question

> "Do we need these two modes - solo and team? The reason to implement team mode was so users understand the importance of RBAC and other restrictions. But if you think all these access level restrictions add little value and more complexity, then I will remove the solo/team mode and all access level restrictions and keep it simple."

### Context

This question arose during a strategic review of the application architecture, following a discussion about simplifying demo mode and cost protection strategies. The underlying question: **Does RBAC complexity serve the goals of a PM portfolio project?**

### Goals of the Project

1. **Primary Goal:** Demonstrate PM skills for applications to Google, Amazon, and other big tech companies
2. **Secondary Goal:** Showcase technical capabilities and full-stack development
3. **Tertiary Goal:** Gather user feedback and study adoption behavior
4. **Not a Goal:** Build a commercial enterprise SaaS product

---

## Analysis: Complexity vs. Value

### Development Cost

**Time Investment:**
- RBAC models and utilities: ~1 week
- Permission enforcement across views: ~1 week
- Column-level restrictions: ~2 days
- Audit logging: ~2 days
- Demo mode (solo vs. team): ~2 days
- Testing and debugging: ~3 days
- **Total: 3-4 weeks of development time**

**Maintenance Cost:**
- 500+ lines of permission code to maintain
- 89 permission checks to keep consistent
- Complex state management for role switching
- Additional database queries for permission checks
- Testing complexity (test each role × each feature)

**Cognitive Load:**
- New developers need to understand permission system
- Every new feature requires permission planning
- Risk of bugs in permission enforcement
- Documentation overhead

### Value Delivered

**For Users (Freemium PMO Tool):**

**Typical Use Case:**
- Small teams (2-5 people)
- Startup/small company environment
- Informal collaboration
- No compliance requirements
- No strict approval workflows

**User Expectations:**
- "Can I invite my team to this board?"
- "Can we all edit tasks?"
- "Is there a way to share this with stakeholders?"

**What Users DON'T Ask:**
- "Can I restrict Members from editing tasks in the Done column?"
- "Can I grant temporary override permissions to a Viewer?"
- "Can I audit who changed task permissions last month?"

**For Portfolio/Interview:**

**What RBAC Demonstrates:**
- ✅ Technical sophistication
- ✅ Understanding of enterprise patterns
- ✅ Systems thinking
- ❌ But... sounds like over-engineering
- ❌ "Did users ask for this?"
- ❌ "Why build this instead of user-facing features?"

**What Simplicity Demonstrates:**
- ✅ Ruthless prioritization
- ✅ User-focused decision making
- ✅ Scope management
- ✅ Shipping velocity
- ✅ Learning from user feedback

### Comparison Table

| Aspect | Complex RBAC (Current) | Simple Collaboration (Proposed) |
|--------|------------------------|----------------------------------|
| **Development Time** | 3-4 weeks | 2-3 hours |
| **Lines of Code** | 500+ (permissions only) | ~50 lines |
| **Database Models** | 5 models | 1 simple relation |
| **Permission Checks** | 89 checks across 13 files | 5-10 simple checks |
| **User Friction** | Role selection, permission errors | Zero friction |
| **Demo Complexity** | 2 modes, role switching | Single clear experience |
| **Maintenance** | High (complex state) | Low (simple logic) |
| **Testing Effort** | High (combinatorial) | Low (straightforward) |
| **Interview Story** | "I built enterprise RBAC..." | "I focused on user value..." |
| **PM Credibility** | Questionable (over-engineering?) | Strong (prioritization) |

### User Research Insights

**Typical Freemium PM Tool Users:**
- Solo entrepreneurs
- Small startup teams (2-10 people)
- Department teams at larger companies
- Side project collaborators
- Students/learners

**What They Need:**
- ✅ Basic collaboration (invite team members)
- ✅ Shared visibility (everyone sees everything)
- ✅ Full editing (everyone can update tasks)
- ✅ Simple sharing (send a link)
- ❌ NOT complex role hierarchies
- ❌ NOT granular permission restrictions
- ❌ NOT workflow enforcement
- ❌ NOT approval processes

**Enterprise Features (RBAC) Make Sense For:**
- Companies with 50+ employees
- Regulated industries (finance, healthcare)
- Strict compliance requirements
- Multi-tier organizational hierarchies
- Formal approval workflows
- Security audit requirements

**PrizmAI's Target Market:**
- Freemium individual/small team tool
- Portfolio demonstration project
- NOT enterprise SaaS (yet)

### ROI Analysis

**Return on Investment:**

**RBAC System:**
- **Cost:** 3-4 weeks development, ongoing maintenance, testing overhead
- **Benefit:** Demonstrates technical capability
- **Risk:** Sounds like over-engineering in PM interviews
- **ROI:** Low to negative for portfolio goals

**Focusing on Core Features Instead:**
- **Cost:** Same 3-4 weeks
- **Benefit:** Ship AI Coach improvements, better burndown forecasting, enhanced analytics, more user feedback
- **Interviews:** "I prioritized features users requested based on data"
- **ROI:** Very high for portfolio goals

---

## Decision

### Final Decision

**Remove RBAC system entirely. Implement simple, frictionless collaboration where all board members have full CRUD permissions.**

### Specific Decisions

1. **✅ Remove Solo vs. Team Demo Modes**
   - Keep single demo experience
   - All users get same capabilities
   - Focus demo time on features, not permission explanations

2. **✅ Remove RBAC System**
   - No role hierarchies (Owner, Admin, Editor, Member, Viewer)
   - No 56-permission system
   - No permission overrides
   - No column-level restrictions
   - No permission audit logs

3. **✅ Implement Simple Collaboration**
   - Board creator (implicit ownership)
   - Invited members (full access)
   - No role selection, no permission errors
   - Zero UX friction

4. **✅ Focus Complexity Budget Elsewhere**
   - Invest time in AI features (Coach, forecasting)
   - Better analytics and user feedback collection
   - Enhanced burndown charts and scope creep detection
   - More polished core user experience

---

## Rationale

### Primary Rationale: Zero UX Friction

**User Experience Philosophy:**
- "Get out of the user's way"
- "Make collaboration effortless"
- "Don't make users think about permissions"

**What This Looks Like:**

**Current (Complex):**
```
User invites teammate
  → "What role should they have?"
  → User reads role descriptions
  → User picks "Editor" (maybe?)
  → Teammate joins
  → Teammate tries to move task to Done column
  → ❌ "You don't have permission to move tasks to this column"
  → Teammate confused
  → User has to go fix permissions
  → Teammate tries again
  → ✅ Finally works
```

**Simplified:**
```
User invites teammate
  → Teammate joins
  → Teammate creates/edits/moves tasks
  → ✅ Everything just works
```

**Friction Eliminated:**
- No role selection during invite
- No permission errors during work
- No "why can't I do this?" support questions
- No permission management overhead

### Secondary Rationale: PM Portfolio Narrative

**What PM Interviewers Look For:**
1. User empathy and research
2. Data-driven decision making
3. Ruthless prioritization
4. Shipping velocity
5. Learning from feedback

**RBAC Narrative (Weak):**
> "I built a comprehensive RBAC system with 56 permissions, role hierarchies, permission overrides, and column-level workflow restrictions to demonstrate enterprise-ready capabilities."

**Interviewer Thoughts:**
- "Did users ask for this?"
- "How did you validate the need?"
- "Why spend 3-4 weeks on permissions?"
- "Sounds like over-engineering"
- ⚠️ Red flag: Building for complexity's sake

**Simplified Narrative (Strong):**
> "I initially considered building enterprise RBAC, but user research showed that my target market (solo PMs and small teams) just needed simple collaboration. So I cut RBAC from the roadmap and instead invested that 3-4 weeks in the AI Coach feature, which became the most requested feature based on user feedback data."

**Interviewer Thoughts:**
- "User-focused decision making ✓"
- "Validated assumptions ✓"
- "Ruthless prioritization ✓"
- "Data-driven ✓"
- "Learning mindset ✓"
- ✅ Strong PM thinking

### Tertiary Rationale: Velocity and Focus

**Complexity Budget Principle:**
- Every project has a finite "complexity budget"
- Spend it on things that differentiate your product
- Don't waste it on table stakes or over-engineering

**Where to Spend Complexity Budget:**

**Bad Investment (Current):**
- ❌ RBAC with 56 permissions
- ❌ Permission overrides
- ❌ Column-level restrictions
- ❌ Audit logging
- **Why Bad:** Doesn't differentiate PrizmAI, adds friction

**Good Investment:**
- ✅ AI Coach that gives smart suggestions
- ✅ Burndown forecasting with machine learning
- ✅ Scope creep detection algorithms
- ✅ Intelligent conflict detection
- ✅ Rich analytics and insights
- **Why Good:** Differentiates PrizmAI, delivers user value

**Velocity Impact:**

**With RBAC:**
- Every new feature: "What permissions does this need?"
- Bug fix: "Did I break permission checks?"
- Testing: "Test each role × each feature"
- Onboarding: "New developer learns permission system"

**Without RBAC:**
- New feature: Just build it
- Bug fix: Straightforward
- Testing: Test the feature
- Onboarding: No permission overhead

### Alignment with Project Goals

**Goal 1: PM Portfolio for Big Tech**
- ✅ Simplification demonstrates strong PM thinking
- ✅ Shows prioritization and user focus
- ✅ Better interview narrative
- ❌ RBAC complexity suggests over-engineering

**Goal 2: Showcase Technical Skills**
- ✅ Still showcasing: Django, AI integration, WebSockets, REST API, analytics
- ✅ RBAC removal doesn't diminish technical credibility
- ✅ Focus shifts to more interesting technical challenges (AI, forecasting)

**Goal 3: User Feedback and Adoption**
- ✅ Simpler onboarding = more users complete signup
- ✅ Zero friction = better retention
- ✅ Clearer value prop = better conversion
- ❌ Complex permissions = user confusion and drop-off

---

## Technical Implications

### Current Database Models (To Be Removed)

```python
# kanban/permission_models.py (500+ lines)

class Role(models.Model):
    """Define roles with specific permissions"""
    name = CharField(max_length=50)
    organization = ForeignKey(Organization)
    permissions = JSONField(default=list)  # 56+ permissions
    is_system_role = BooleanField(default=False)
    # ... additional fields

class BoardMembership(models.Model):
    """Role-based membership"""
    board = ForeignKey(Board)
    user = ForeignKey(User)
    role = ForeignKey(Role)  # Links to complex role
    expires_at = DateTimeField(null=True)
    # ... additional fields

class PermissionOverride(models.Model):
    """Override permissions beyond role"""
    membership = ForeignKey(BoardMembership)
    permission = CharField(max_length=50)
    override_type = CharField(choices=['grant', 'deny'])
    # ... additional fields

class ColumnPermission(models.Model):
    """Column-specific workflow restrictions"""
    column = ForeignKey(Column)
    role = ForeignKey(Role)
    can_move_to = BooleanField(default=True)
    can_move_from = BooleanField(default=True)
    can_create_in = BooleanField(default=True)
    can_edit_in = BooleanField(default=True)

class PermissionAuditLog(models.Model):
    """Track all permission changes"""
    action = CharField(max_length=30)
    actor = ForeignKey(User)
    affected_user = ForeignKey(User)
    details = JSONField(default=dict)
    # ... additional fields
```

### Simplified Model (Proposed)

```python
# kanban/models.py (additions)

class Board(models.Model):
    # ... existing fields
    created_by = ForeignKey(User, on_delete=CASCADE, related_name='owned_boards')
    members = ManyToManyField(User, related_name='boards', blank=True)

    def user_can_access(self, user):
        """Simple access check: creator or member"""
        return user == self.created_by or self.members.filter(id=user.id).exists()
```

**That's it.** No roles, no permissions, no overrides, no audit logs.

### Permission Check Changes

**Before (Complex):**
```python
# kanban/permission_utils.py
def user_has_board_permission(user, board, permission):
    """Check if user has a specific permission on a board"""
    # 100+ lines of logic
    # Check superuser
    # Check board creator
    # Check org admin
    # Check membership
    # Check permission overrides (deny)
    # Check role permissions
    # Check permission overrides (grant)
    # Check column permissions
    # Check expiration
    # ...
    return has_permission

# Usage in views
@require_board_permission('task.edit')
def edit_task(request, board_id, task_id):
    # ...
```

**After (Simple):**
```python
# kanban/views.py
def edit_task(request, board_id, task_id):
    board = get_object_or_404(Board, id=board_id)

    # Simple check
    if not board.user_can_access(request.user):
        raise PermissionDenied("You don't have access to this board")

    # Rest of view logic
    # ...
```

### Files to Remove

**Complete Removal:**
- `kanban/permission_models.py` (500+ lines)
- `kanban/permission_utils.py` (200+ lines)
- `kanban/permission_views.py` (300+ lines)
- `kanban/permission_audit.py` (100+ lines)
- `kanban/templates/kanban/permissions/` (entire directory)
- `kanban/management/commands/create_default_roles.py`

**Simplification (remove permission checks):**
- `kanban/views.py` - Remove 27 permission check decorators
- `kanban/api_views.py` - Remove 8 permission checks
- `kanban/coach_views.py` - Remove 3 permission checks
- `kanban/retrospective_views.py` - Remove 13 permission checks
- Other view files - Remove remaining permission checks

**Database Migrations:**
```bash
# Create migration to:
1. Drop PermissionAuditLog table
2. Drop ColumnPermission table
3. Drop PermissionOverride table
4. Drop BoardMembership table
5. Drop Role table
6. Add Board.members ManyToMany field
7. Migrate existing BoardMembership data to Board.members
```

### URL Changes

**Remove URLs:**
```python
# kanban/urls.py - Remove these patterns
path('permissions/roles/', views.manage_roles),
path('permissions/roles/create/', views.create_role),
path('permissions/members/', views.manage_members),
path('permissions/members/add/', views.add_member),
path('permissions/audit/', views.permission_audit),
# ... ~10 permission-related URLs
```

**Keep URLs (just simplify checks):**
```python
# Board access
path('boards/<int:board_id>/', views.board_detail),  # Just check membership
path('boards/<int:board_id>/tasks/', views.task_list),  # Just check membership
# etc.
```

### Demo Mode Changes

**Current:**
```python
# Two demo mode choices
def demo_mode_selection(request):
    # Show solo vs. team mode selection page
    # User chooses mode
    # Set session['demo_mode'] = 'solo' or 'team'

    if mode == 'team':
        # Create demo org with RBAC roles
        # Create demo boards with different permission sets
        # Allow role switching
    else:
        # Create demo org, give user admin access
```

**Simplified:**
```python
# Single demo experience
def start_demo(request):
    # Create demo org
    # Create demo boards
    # Add user as member to all boards
    # No role selection, no permission configuration
    # Just... use the product
```

### View Decorator Changes

**Before:**
```python
from kanban.permission_utils import require_board_permission

@require_board_permission('task.edit')
def edit_task(request, board_id, task_id):
    # View logic
    pass

@require_board_permission('task.delete')
def delete_task(request, board_id, task_id):
    # View logic
    pass

@require_board_permission('board.export')
def export_board(request, board_id):
    # View logic
    pass
```

**After:**
```python
from django.shortcuts import get_object_or_404
from django.core.exceptions import PermissionDenied

def edit_task(request, board_id, task_id):
    board = get_object_or_404(Board, id=board_id)
    if not board.user_can_access(request.user):
        raise PermissionDenied
    # View logic
    pass

def delete_task(request, board_id, task_id):
    board = get_object_or_404(Board, id=board_id)
    if not board.user_can_access(request.user):
        raise PermissionDenied
    # View logic
    pass

def export_board(request, board_id):
    board = get_object_or_404(Board, id=board_id)
    if not board.user_can_access(request.user):
        raise PermissionDenied
    # View logic
    pass
```

---

## Benefits of Simplification

### 1. User Experience

**Immediate Benefits:**
- ✅ No role selection confusion
- ✅ No permission error messages
- ✅ No "I can't do X, how do I fix it?" support questions
- ✅ Faster onboarding (skip permission explanation)
- ✅ Clear mental model: "You're on the board, you can do everything"

**Metrics Impact:**
- **Signup completion rate:** Expected +10-20% (less friction)
- **Time to first task created:** Expected -30% (no permission setup)
- **User frustration:** Significant reduction
- **Support tickets:** -90% permission-related issues

### 2. Development Velocity

**Code Reduction:**
- Remove 500+ lines of permission models
- Remove 200+ lines of permission utilities
- Remove 300+ lines of permission views
- Remove 89 permission check decorators
- **Total: ~1,200 lines removed**

**Future Feature Development:**
- No permission planning overhead
- No "what permissions does this need?" discussions
- No permission-related bugs
- Faster testing (no role combinations)

**Maintenance:**
- Simpler codebase to understand
- Faster onboarding for new contributors
- Less code to maintain
- Fewer edge cases

### 3. Testing Simplification

**Current Testing Complexity:**
```
5 roles × 56 permissions × N features = Massive test matrix
```

**Example:**
- Test "Edit Task" feature:
  - ✅ Owner can edit
  - ✅ Admin can edit
  - ✅ Editor can edit
  - ✅ Member can edit own tasks
  - ❌ Member cannot edit other's tasks
  - ❌ Viewer cannot edit
  - ✅ Permission override grants access
  - ❌ Permission override denies access
  - Edge cases: expired memberships, column restrictions, etc.

**Simplified Testing:**
```
Test "Edit Task" feature:
  - ✅ Board creator can edit
  - ✅ Board member can edit
  - ❌ Non-member cannot edit
```

**Testing Time Reduction:** ~80% for permission-related tests

### 4. Documentation Simplification

**Current Documentation Needs:**
- Role descriptions and capabilities
- Permission reference (56 permissions)
- Permission override system
- Column-level restrictions
- Audit log interpretation
- How to troubleshoot permission issues

**Simplified Documentation:**
- "Invite team members to collaborate"
- "Everyone can create, edit, and manage tasks"
- Done.

### 5. Mental Model Clarity

**Current Mental Model (Complex):**
```
User needs to understand:
├─ What are roles?
├─ What can each role do?
├─ How do I choose the right role?
├─ What are permission overrides?
├─ Why can't I move this task?
├─ How do column permissions work?
└─ How do I fix permission errors?
```

**Simplified Mental Model:**
```
User needs to understand:
└─ If you're on the board, you can do everything.
```

**Cognitive Load Reduction:** ~90%

### 6. Error Handling Simplification

**Current Error Scenarios:**
- User tries task.edit, doesn't have permission → Error
- User tries column.delete, doesn't have permission → Error
- User tries board.export, doesn't have permission → Error
- User tries task move to restricted column → Error
- User has expired membership → Error
- Permission override expired → Error

**Each error requires:**
- User-friendly error message
- Guidance on how to fix (contact admin, change role, etc.)
- Support documentation
- Handling in UI

**Simplified Error Scenarios:**
- User tries to access board they're not on → Error: "You're not a member of this board"
- That's it.

### 7. Database Performance

**Current Queries:**
```sql
-- Check user permission
SELECT * FROM kanban_boardmembership
  WHERE user_id = ? AND board_id = ? AND is_active = true;

SELECT * FROM kanban_role WHERE id = ?;

SELECT * FROM kanban_permissionoverride
  WHERE membership_id = ? AND permission = ?;

SELECT * FROM kanban_columnpermission
  WHERE column_id = ? AND role_id = ?;

-- 4 queries per permission check
```

**Simplified Query:**
```sql
-- Check user access
SELECT * FROM kanban_board_members
  WHERE board_id = ? AND user_id = ?;

-- 1 query per access check
```

**Performance Improvement:** ~75% fewer database queries for access checks

---

## Implementation Guidance

### Phase 1: Database Migration (Day 1)

**Step 1: Create Migration**
```bash
python manage.py makemigrations kanban --empty -n simplify_permissions
```

**Step 2: Migration Code**
```python
# kanban/migrations/XXXX_simplify_permissions.py

def migrate_memberships_to_simple(apps, schema_editor):
    """Migrate BoardMembership to simple Board.members"""
    Board = apps.get_model('kanban', 'Board')
    BoardMembership = apps.get_model('kanban', 'BoardMembership')

    for membership in BoardMembership.objects.filter(is_active=True):
        # Add user to board.members
        membership.board.members.add(membership.user)

class Migration(migrations.Migration):
    dependencies = [
        ('kanban', 'PREVIOUS_MIGRATION'),
    ]

    operations = [
        # Add members field to Board
        migrations.AddField(
            model_name='board',
            name='members',
            field=models.ManyToManyField(
                to='auth.User',
                related_name='boards',
                blank=True
            ),
        ),

        # Migrate data
        migrations.RunPython(migrate_memberships_to_simple),

        # Drop old tables (after data migration)
        migrations.DeleteModel(name='PermissionAuditLog'),
        migrations.DeleteModel(name='ColumnPermission'),
        migrations.DeleteModel(name='PermissionOverride'),
        migrations.DeleteModel(name='BoardMembership'),
        migrations.DeleteModel(name='Role'),
    ]
```

**Step 3: Run Migration**
```bash
python manage.py migrate
```

### Phase 2: Code Cleanup (Day 2-3)

**Remove Files:**
```bash
# Delete entire files
rm kanban/permission_models.py
rm kanban/permission_utils.py
rm kanban/permission_views.py
rm kanban/permission_audit.py
rm -rf kanban/templates/kanban/permissions/
```

**Update Board Model:**
```python
# kanban/models.py

class Board(models.Model):
    # ... existing fields
    created_by = ForeignKey(User, on_delete=CASCADE, related_name='owned_boards')
    members = ManyToManyField(User, related_name='boards', blank=True)

    def user_can_access(self, user):
        """Check if user can access this board"""
        if not user.is_authenticated:
            return False
        # Creator always has access
        if self.created_by == user:
            return True
        # Members have access
        return self.members.filter(id=user.id).exists()

    def add_member(self, user):
        """Add a member to this board"""
        self.members.add(user)

    def remove_member(self, user):
        """Remove a member from this board"""
        if user == self.created_by:
            raise ValueError("Cannot remove board creator")
        self.members.remove(user)
```

**Update Views:**
```python
# kanban/views.py

def board_detail(request, board_id):
    board = get_object_or_404(Board, id=board_id)

    # Simple access check
    if not board.user_can_access(request.user):
        raise PermissionDenied("You don't have access to this board")

    # Rest of view logic
    tasks = board.tasks.all()
    return render(request, 'kanban/board_detail.html', {
        'board': board,
        'tasks': tasks,
    })

def edit_task(request, board_id, task_id):
    board = get_object_or_404(Board, id=board_id)
    task = get_object_or_404(Task, id=task_id, board=board)

    if not board.user_can_access(request.user):
        raise PermissionDenied("You don't have access to this board")

    # Edit logic
    # ...
```

**Pattern for All Views:**
```python
# Before (with decorator)
@require_board_permission('permission.name')
def my_view(request, board_id):
    pass

# After (simple check)
def my_view(request, board_id):
    board = get_object_or_404(Board, id=board_id)
    if not board.user_can_access(request.user):
        raise PermissionDenied
    # ... rest of logic
```

### Phase 3: Template Updates (Day 3)

**Remove Permission Checks from Templates:**

**Before:**
```django
{% if perms.task.edit or user_is_admin %}
  <button>Edit Task</button>
{% endif %}

{% if perms.board.export %}
  <a href="{% url 'export_board' board.id %}">Export</a>
{% endif %}
```

**After:**
```django
{% if board.user_can_access %}
  <button>Edit Task</button>
  <a href="{% url 'export_board' board.id %}">Export</a>
{% endif %}
```

**Or even simpler (since access check is in view):**
```django
<!-- Just show the buttons - view will enforce access -->
<button>Edit Task</button>
<a href="{% url 'export_board' board.id %}">Export</a>
```

### Phase 4: Demo Mode Simplification (Day 4)

**Remove Mode Selection:**
```python
# DELETE: kanban/demo_views.py - demo_mode_selection view
# DELETE: templates/demo/mode_selection.html

# SIMPLIFY: kanban/demo_views.py
def start_demo(request):
    """Create demo session with simple access"""
    # Create or get demo organization
    demo_org, _ = Organization.objects.get_or_create(
        name=f'Demo Org - {request.session.session_key[:8]}',
        is_demo=True
    )

    # Create demo user (or use session-based virtual user)
    demo_user = request.user if request.user.is_authenticated else create_demo_user()

    # Create demo boards
    boards = create_demo_boards(demo_org, demo_user)

    # Add user as member to all boards
    for board in boards:
        board.members.add(demo_user)

    # Set session
    request.session['is_demo_mode'] = True
    request.session['demo_org_id'] = demo_org.id

    # Redirect to first board
    return redirect('board_detail', board_id=boards[0].id)
```

**Update Demo Data Population:**
```python
# kanban/management/commands/populate_demo_data.py

def create_demo_boards(organization, user):
    """Create demo boards with user as member"""
    boards = []

    # Marketing Campaign board
    board = Board.objects.create(
        name='Marketing Campaign - Q1 2026',
        organization=organization,
        created_by=user
    )
    # No role assignment needed - user is creator
    boards.append(board)

    # Software Development board
    board = Board.objects.create(
        name='Website Redesign Project',
        organization=organization,
        created_by=user
    )
    boards.append(board)

    # Bug Tracking board
    board = Board.objects.create(
        name='Bug Tracking Dashboard',
        organization=organization,
        created_by=user
    )
    boards.append(board)

    return boards
```

### Phase 5: Testing Updates (Day 5)

**Remove Permission Tests:**
```bash
# Delete or simplify
tests/test_permissions.py  # Delete entire file
tests/test_rbac.py  # Delete entire file
```

**Update Feature Tests:**
```python
# tests/test_board_views.py

def test_board_access():
    """Test simple board access"""
    # Create board
    board = Board.objects.create(name='Test', created_by=user1)

    # Creator has access
    assert board.user_can_access(user1)

    # Non-member doesn't have access
    assert not board.user_can_access(user2)

    # Add member
    board.add_member(user2)
    assert board.user_can_access(user2)

    # Remove member
    board.remove_member(user2)
    assert not board.user_can_access(user2)

def test_task_edit():
    """Test task editing with simple access"""
    board = Board.objects.create(name='Test', created_by=user1)
    task = Task.objects.create(board=board, title='Test Task')

    # Creator can edit
    response = client.post(f'/boards/{board.id}/tasks/{task.id}/edit/', data)
    assert response.status_code == 200

    # Non-member cannot edit
    client.logout()
    client.login(username='user2')
    response = client.post(f'/boards/{board.id}/tasks/{task.id}/edit/', data)
    assert response.status_code == 403

    # Member can edit
    board.add_member(user2)
    response = client.post(f'/boards/{board.id}/tasks/{task.id}/edit/', data)
    assert response.status_code == 200
```

### Phase 6: Documentation Updates (Day 6)

**Update README:**
```markdown
# Before
## Role-Based Access Control (RBAC)
PrizmAI features enterprise-grade RBAC with:
- 5 default roles (Owner, Admin, Editor, Member, Viewer)
- 56+ granular permissions
- Permission overrides
- Column-level workflow restrictions
- Comprehensive audit logging

# After
## Team Collaboration
Invite team members to collaborate on boards:
- Board creators can invite team members
- All members can create, edit, and manage tasks
- Simple, frictionless collaboration
```

**Update User Guide:**
```markdown
# Before (Complex)
## Managing Team Permissions

### Understanding Roles
1. Owner - Full organization control
2. Admin - Board management capabilities
3. Editor - Can edit tasks and content
4. Member - Can work on assigned tasks
5. Viewer - Read-only access

### Assigning Roles
To assign a role to a team member:
1. Go to Board Settings > Members
2. Click "Add Member"
3. Select user and choose role
4. Configure permission overrides if needed
...

# After (Simple)
## Inviting Team Members

To invite someone to your board:
1. Click "Share" on the board
2. Enter their email address
3. They'll receive an invite and can start collaborating

All team members can create, edit, and manage tasks.
```

### Phase 7: URL Cleanup (Day 7)

**Remove Permission URLs:**
```python
# kanban/urls.py

# REMOVE these patterns:
# path('permissions/roles/', views.manage_roles, name='manage_roles'),
# path('permissions/roles/create/', views.create_role, name='create_role'),
# path('permissions/roles/<int:role_id>/edit/', views.edit_role, name='edit_role'),
# path('permissions/members/', views.manage_board_members, name='manage_board_members'),
# path('permissions/members/add/', views.add_board_member, name='add_board_member'),
# path('permissions/members/<int:membership_id>/remove/', views.remove_board_member),
# path('permissions/audit/', views.permission_audit_log, name='permission_audit'),
# ... etc.

# KEEP simple patterns:
urlpatterns = [
    path('boards/<int:board_id>/', views.board_detail, name='board_detail'),
    path('boards/<int:board_id>/share/', views.share_board, name='share_board'),
    path('boards/<int:board_id>/members/add/', views.add_member, name='add_member'),
    path('boards/<int:board_id>/members/<int:user_id>/remove/', views.remove_member),
    # ... rest of patterns
]
```

**New Simple Views:**
```python
# kanban/views.py

def share_board(request, board_id):
    """Share board with team members"""
    board = get_object_or_404(Board, id=board_id)

    # Only creator can share
    if board.created_by != request.user:
        raise PermissionDenied

    if request.method == 'POST':
        email = request.POST.get('email')
        user = User.objects.get(email=email)
        board.add_member(user)

        # Send invitation email
        send_board_invitation(board, user)

        messages.success(request, f'{user.email} added to board')
        return redirect('board_detail', board_id=board.id)

    return render(request, 'kanban/share_board.html', {'board': board})
```

### Estimated Timeline

| Phase | Description | Time |
|-------|-------------|------|
| Phase 1 | Database migration | 4 hours |
| Phase 2 | Code cleanup (remove files, update imports) | 8 hours |
| Phase 3 | Template updates | 4 hours |
| Phase 4 | Demo mode simplification | 4 hours |
| Phase 5 | Testing updates | 6 hours |
| Phase 6 | Documentation updates | 3 hours |
| Phase 7 | URL cleanup and new simple views | 3 hours |
| **Total** | **Complete simplification** | **~4 days** |

### Risk Mitigation

**Backup First:**
```bash
# Backup database
python manage.py dumpdata > backup_before_simplification.json

# Create git branch
git checkout -b simplify-rbac
git commit -am "Checkpoint before RBAC removal"
```

**Incremental Rollout:**
1. Keep old code commented out initially
2. Test thoroughly in development
3. Deploy to staging environment
4. Monitor for issues
5. Deploy to production
6. Remove commented code after 1 week

**Rollback Plan:**
```bash
# If issues arise
git checkout main
python manage.py loaddata backup_before_simplification.json
```

---

## Appendix: Current System Details

### Complete Permission List (56 Permissions)

**Board (6):**
1. board.view
2. board.create
3. board.edit
4. board.delete
5. board.manage_members
6. board.export

**Column (4):**
7. column.create
8. column.edit
9. column.delete
10. column.reorder

**Task (9):**
11. task.view
12. task.view_own
13. task.create
14. task.edit
15. task.edit_own
16. task.delete
17. task.delete_own
18. task.assign
19. task.move

**Comment (6):**
20. comment.view
21. comment.create
22. comment.edit
23. comment.edit_own
24. comment.delete
25. comment.delete_own

**Label (5):**
26. label.view
27. label.create
28. label.edit
29. label.delete
30. label.assign

**File (4):**
31. file.view
32. file.upload
33. file.download
34. file.delete

**Advanced (6):**
35. webhook.manage
36. api.access
37. analytics.view
38. audit.view
39. data.export
40. data.import

**Administrative (1):**
41. admin.full

### Database Schema (Current)

```sql
-- Role table
CREATE TABLE kanban_role (
    id SERIAL PRIMARY KEY,
    name VARCHAR(50) NOT NULL,
    description TEXT,
    organization_id INT NOT NULL,
    permissions JSONB DEFAULT '[]',
    is_system_role BOOLEAN DEFAULT FALSE,
    is_default BOOLEAN DEFAULT FALSE,
    created_at TIMESTAMP DEFAULT NOW(),
    created_by_id INT,
    updated_at TIMESTAMP DEFAULT NOW(),
    UNIQUE(organization_id, name)
);

-- BoardMembership table
CREATE TABLE kanban_boardmembership (
    id SERIAL PRIMARY KEY,
    board_id INT NOT NULL,
    user_id INT NOT NULL,
    role_id INT NOT NULL,
    added_at TIMESTAMP DEFAULT NOW(),
    added_by_id INT,
    expires_at TIMESTAMP NULL,
    is_active BOOLEAN DEFAULT TRUE,
    UNIQUE(board_id, user_id)
);

-- PermissionOverride table
CREATE TABLE kanban_permissionoverride (
    id SERIAL PRIMARY KEY,
    membership_id INT NOT NULL,
    permission VARCHAR(50) NOT NULL,
    override_type VARCHAR(10) NOT NULL,  -- 'grant' or 'deny'
    reason TEXT,
    created_at TIMESTAMP DEFAULT NOW(),
    created_by_id INT,
    expires_at TIMESTAMP NULL,
    UNIQUE(membership_id, permission)
);

-- ColumnPermission table
CREATE TABLE kanban_columnpermission (
    id SERIAL PRIMARY KEY,
    column_id INT NOT NULL,
    role_id INT NOT NULL,
    can_move_to BOOLEAN DEFAULT TRUE,
    can_move_from BOOLEAN DEFAULT TRUE,
    can_create_in BOOLEAN DEFAULT TRUE,
    can_edit_in BOOLEAN DEFAULT TRUE,
    UNIQUE(column_id, role_id)
);

-- PermissionAuditLog table
CREATE TABLE kanban_permissionauditlog (
    id SERIAL PRIMARY KEY,
    action VARCHAR(30) NOT NULL,
    timestamp TIMESTAMP DEFAULT NOW(),
    actor_id INT,
    organization_id INT,
    board_id INT,
    affected_user_id INT,
    details JSONB DEFAULT '{}',
    ip_address INET,
    user_agent TEXT
);
```

### Code Statistics (Current)

**File Breakdown:**
- `kanban/permission_models.py`: 500 lines
- `kanban/permission_utils.py`: 200 lines
- `kanban/permission_views.py`: 300 lines
- `kanban/permission_audit.py`: 100 lines
- Templates: 500+ lines across 8 files
- Tests: 800+ lines

**Total RBAC Code: ~2,400 lines**

### Demo Mode Complexity (Current)

**Solo Mode Flow:**
```
1. User clicks "Try Demo"
2. Mode selection page loads
3. User clicks "Explore Solo"
4. System creates:
   - Demo organization
   - Demo user with Admin role
   - 3 demo boards
   - 1000+ demo tasks
   - Assigns user as Admin to all boards
5. User explores with full access
6. No permission restrictions
7. Demo timer starts (48 hours)
```

**Team Mode Flow:**
```
1. User clicks "Try Demo"
2. Mode selection page loads
3. User clicks "Try as a Team"
4. System creates:
   - Demo organization
   - Demo user (starts as Admin)
   - 3 demo boards with different permission sets
   - 1000+ demo tasks
   - Creates all 5 roles (Owner, Admin, Editor, Member, Viewer)
   - Sets up column permissions
5. User sees role switcher in navbar
6. User switches to "Member" role
7. UI updates to show limited permissions
8. User tries to delete task → Permission denied
9. User switches to "Admin" role
10. User can now delete tasks
11. Demo timer starts (48 hours)
```

**Code for Role Switching:**
```python
# kanban/demo_views.py (current)
def switch_demo_role(request):
    """Allow switching roles in team demo mode"""
    if request.session.get('demo_mode') != 'team':
        return HttpResponseForbidden("Role switching only in team mode")

    new_role = request.POST.get('role')  # 'admin', 'member', 'viewer'

    # Get demo boards
    demo_org = get_demo_organization(request)
    boards = Board.objects.filter(organization=demo_org)

    # Get or create role
    role = Role.objects.get(organization=demo_org, name=new_role.title())

    # Update all memberships
    for board in boards:
        membership = BoardMembership.objects.get(
            board=board,
            user=request.user
        )
        membership.role = role
        membership.save()

    # Store in session
    request.session['demo_role'] = new_role

    messages.success(request, f'Switched to {new_role.title()} role')
    return redirect('demo_dashboard')
```

---

## Conclusion

After thorough analysis of the RBAC system complexity versus the value it provides for a PM portfolio project, the decision is clear: **Simplify dramatically.**

### Key Takeaways

1. **RBAC adds complexity without serving project goals**
   - 3-4 weeks development time
   - 2,400+ lines of code
   - Ongoing maintenance burden
   - Doesn't differentiate PrizmAI
   - Weak interview narrative

2. **Simple collaboration serves users better**
   - Zero UX friction
   - Intuitive mental model
   - Faster onboarding
   - Better retention
   - Focus on core value proposition

3. **Simplification demonstrates PM thinking**
   - Ruthless prioritization
   - User-focused decisions
   - Scope management
   - Shipping velocity
   - Strong interview narrative

4. **Implementation is straightforward**
   - ~4 days of work
   - Low risk (with proper backups)
   - Immediate benefits
   - Frees time for high-value features

### Final Recommendation

**Remove the entire RBAC system and implement simple collaboration where all board members have full CRUD permissions.** This aligns with project goals, serves users better, creates a stronger PM narrative, and frees up development time to focus on features that actually differentiate PrizmAI.

---

*This document captures the strategic decision-making process for removing RBAC complexity from PrizmAI. Implementation is pending user approval.*

**Last Updated:** January 2026
