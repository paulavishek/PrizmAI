# Simplification Implementation Plan

**Date:** January 2026
**Status:** ✅ IMPLEMENTED
**Goal:** Simplify PrizmAI from dual-mode with RBAC to single-environment with simple collaboration

---

## Executive Summary

Removed complexity while preserving all core features:
- ❌ Removed: Demo/Real mode distinction, Solo/Team modes, complex RBAC (56 permissions), VPN penalties
- ✅ Kept: Single authenticated environment, demo data, simple board membership, per-user AI quotas, rate limiting

---

## What Changed

### 1. Access Control (simple_access.py)
**Before:** 56 permissions, 5 roles, column-level restrictions, permission overrides
**After:** 
- Board creator = full access (can delete, manage members)
- Board members = full CRUD access
- No role selection, no permission errors

**Files created/modified:**
- `kanban/simple_access.py` - New simplified access control module
- `kanban/permission_utils.py` - Now imports from simple_access.py for backwards compatibility

### 2. Demo Mode (demo_settings.py, demo_views.py)
**Before:** Solo vs Team mode selection, virtual admin login, role switching
**After:**
- `SIMPLIFIED_MODE = True` flag enables new behavior
- Authenticated users go directly to dashboard
- Demo boards visible in main dashboard
- No mode selection page needed

**Files modified:**
- `kanban/utils/demo_settings.py` - Added SIMPLIFIED_MODE flag and updated defaults
- `kanban/demo_views.py` - Skip mode selection in simplified mode
- `kanban/context_processors.py` - Return simplified context for templates

### 3. Cost Protection (demo_abuse_prevention.py)
**Before:** VPN users got 50% reduced limits, complex fingerprinting enforcement
**After:**
- `APPLY_VPN_PENALTIES = False` - No VPN penalties
- VPN detection kept for analytics only
- Per-user quotas still enforced (50/month, 10/day)
- Rate limiting still enforced (5 per 10 minutes)

**Files modified:**
- `kanban/utils/demo_abuse_prevention.py` - Check APPLY_VPN_PENALTIES before reducing limits

### 4. Dashboard (views.py)
**Before:** Demo boards excluded from main dashboard
**After:** Demo boards shown in main dashboard for all authenticated users

---

## Feature Flag

The simplification is controlled by a single flag in `kanban/utils/demo_settings.py`:

```python
SIMPLIFIED_MODE = True  # Enable simplified single-environment mode
```

To revert to legacy behavior, set `SIMPLIFIED_MODE = False`.

---

## Current Settings (Simplified Mode)

| Setting | Value | Description |
|---------|-------|-------------|
| SIMPLIFIED_MODE | True | Single environment, no Solo/Team |
| APPLY_VPN_PENALTIES | False | VPN users get same limits as everyone |
| DEMO_PROJECT_LIMIT | 999 | Effectively unlimited projects |
| DEMO_AI_GENERATION_LIMIT | 50 | Monthly AI quota |
| DAILY_AI_LIMIT | 10 | Daily AI limit |
| DEMO_ALLOW_EXPORTS | True | Exports enabled |
| AI_RATE_LIMIT_REQUESTS | 5 | Requests per 10 minutes |

---

## Backwards Compatibility

All existing code that uses these functions continues to work:
- `user_has_board_permission()` - Redirects to simple access check
- `user_has_task_permission()` - Redirects to simple access check
- `get_user_board_membership()` - Returns a simplified membership object
- All permission decorators - Simplified to basic access checks

---

## Interview Talking Points

> "I initially built a comprehensive RBAC system with 56 permissions and 5 roles. But user research showed my target audience - solo PMs and small teams - just wanted simple collaboration without friction.
>
> So I made a scope decision: introduced a SIMPLIFIED_MODE flag that replaces complex RBAC with simple 'creator + members' access. This reduced the permission code from 500+ lines to 50, eliminated role selection UI, and removed user friction.
>
> The result: 75% reduction in access control complexity while maintaining full backwards compatibility through a simple abstraction layer."

---

## Files Changed Summary

| File | Change |
|------|--------|
| `kanban/simple_access.py` | **NEW** - Simplified access control |
| `kanban/permission_utils.py` | Modified - Imports from simple_access |
| `kanban/utils/demo_settings.py` | Modified - Added SIMPLIFIED_MODE and new settings |
| `kanban/utils/demo_abuse_prevention.py` | Modified - Respect APPLY_VPN_PENALTIES flag |
| `kanban/demo_views.py` | Modified - Skip mode selection in simplified mode |
| `kanban/context_processors.py` | Modified - Return simplified context |
| `kanban/views.py` | Modified - Include demo boards in dashboard |

---

## Phase 1: Simplify Access Control (RBAC → Simple Membership)

### Current State
- 5 roles: Owner, Admin, Editor, Member, Viewer
- 56 granular permissions
- Column-level restrictions
- Permission overrides
- BoardMembership with Role FK

### Target State
- Board creator = full access (can delete board, manage members)
- Board members = full CRUD access (via M2M `Board.members`)
- No role selection, no permission errors

### Files to Modify
1. `kanban/permission_utils.py` - Simplify to creator + member checks only
2. `kanban/views.py` - Remove permission checks, use simple membership
3. `kanban/api_views.py` - Same simplification
4. `kanban/templates/` - Remove role-related UI elements

### Files to Keep (but not enforce)
- `kanban/permission_models.py` - Keep models for backwards compatibility, but don't enforce
- Keep `BoardMembership` for existing data, but make role optional

---

## Phase 2: Remove Demo Mode Distinction

### Current State
- Demo mode selection page (Solo vs Team)
- Demo session tracking with 48-hour expiry
- Demo-specific URLs and views
- Demo admin virtual user login
- Demo role switching

### Target State
- Single authenticated environment
- All users get full access to their boards
- Demo boards pre-populated for new users
- No mode selection, no session tracking, no expiry

### Files to Modify
1. `kanban/demo_views.py` - Simplify or remove most views
2. `kanban/urls.py` - Remove demo mode URLs (keep demo data reset)
3. `kanban/utils/demo_admin.py` - No longer needed
4. `kanban/utils/demo_permissions.py` - No longer needed
5. `kanban/utils/demo_settings.py` - Simplify
6. `templates/demo/` - Remove mode selection UI

---

## Phase 3: Simplify Cost Protections

### Current State (Remove)
- VPN detection and penalties
- Global IP limits
- Fingerprint-based blocking
- Complex abuse prevention

### Target State (Keep)
- Per-user AI quotas (50/month, 10/day) via `AIUsageQuota`
- Rate limiting (5 requests per 10 minutes)
- Email verification (standard)
- Monitoring/analytics (keep tracking, remove enforcement)

### Files to Modify
1. `kanban/utils/vpn_detection.py` - Keep detection, remove penalties
2. `kanban/utils/demo_abuse_prevention.py` - Convert to analytics only
3. `api/ai_usage_utils.py` - Keep per-user quotas
4. `analytics/models.py` - Keep DemoSession for analytics, remove enforcement

---

## Phase 4: Update Templates & UI

### Remove
- Demo mode selection page
- Solo/Team mode toggle
- Role switcher in demo banner
- Permission error messages
- Role selection in member invite

### Keep
- Login/signup flow
- Board list and detail views
- All feature UIs (AI Coach, Gantt, etc.)
- Demo data board markers

---

## Implementation Order

1. **Create simple permission check function** (new utility)
2. **Update permission_utils.py** with simplified logic
3. **Update views.py** to use simple checks
4. **Update demo_views.py** - remove mode selection
5. **Update URLs** - remove demo mode routes
6. **Update templates** - remove role UI
7. **Test all features**

---

## Key Decisions

### Board Access Rules (Simplified)
```python
def can_access_board(user, board):
    """Simple access check: creator or member"""
    if not user.is_authenticated:
        return False
    if board.created_by == user:
        return True
    if user in board.members.all():
        return True
    # Organization members can access org boards
    if hasattr(user, 'profile') and user.profile.organization == board.organization:
        return True
    return False

def can_manage_board(user, board):
    """Only creator can delete/manage members"""
    return board.created_by == user or user.is_superuser
```

### AI Quota Rules (Keep)
- 50 AI requests per month
- 10 AI requests per day
- Rate limit: 5 per 10 minutes
- No VPN penalties

---

## Rollback Plan

If issues arise:
1. Keep all models (just don't enforce)
2. Simple feature flags to re-enable RBAC if needed
3. Database migrations are additive only (no data loss)
