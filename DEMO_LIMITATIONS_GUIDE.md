# 🎯 Demo Limitations & Conversion Strategy

> Strategic demo restrictions designed to drive conversion while demonstrating product value.

---

## Overview

PrizmAI's demo mode provides **full feature access** with strategic limitations that create natural conversion incentives. These limits are carefully designed to let users experience the product's value while motivating them to create accounts.

---

## 📊 Demo Limitations

| Feature | Demo Limit | Full Account |
|---------|-----------|--------------|
| **Projects** | 2 boards max | Unlimited |
| **Export** | ❌ Blocked | ✅ Full export (PDF, CSV, JSON) |
| **AI Generations** | 20 per session | Based on plan |
| **Data Persistence** | 48 hours (resets) | Permanent |

---

## 🔒 How Limitations Work

### Project Limit (Max 2 Boards)

Demo users can create up to **2 projects** to explore board creation and management:

```python
# In kanban/utils/demo_limits.py
DEMO_LIMITS = {
    'max_projects': 2,
    'max_ai_generations': 20,
    'export_enabled': False,
    'data_reset_hours': 48,
}
```

**When limit is reached:**
1. User sees an upgrade modal explaining the limit
2. GA4 event `limitation_encountered` fires with `limitation_type: 'project_limit'`
3. Counter is cumulative—deleting boards doesn't restore the limit

### Export Blocking

Export functionality is completely blocked in demo mode:

- **Affected exports:** PDF, CSV, JSON board exports
- **User experience:** Shown upgrade modal with explanation
- **Tracking:** `demo_export_blocked` GA4 event fires

### AI Generation Limit

AI features work normally up to 20 generations:

- Includes: AI Coach suggestions, task recommendations, risk detection
- After limit: Upgrade modal with AI benefits highlighted
- Tracking: `ai_limit_reached` event

### 48-Hour Data Reset

- Demo data persists for 48 hours from session start
- Banner shows countdown: "Data resets in Xh"
- After reset, demo returns to initial state

---

## 🛡️ Workaround Prevention

### The Export-Delete-Recreate Loop

**Concern:** Users might try to export, delete boards, create new ones, and export again.

**Solution:** Export is completely blocked, making this impossible:

```
User creates 2 boards → Hits limit
User deletes a board → Counter stays at 2 (cumulative)
User can't export → Deleted data is permanently lost
```

### Workaround Detection Analytics

When a user deletes a board while at the project limit, we track potential workaround attempts:

```javascript
// Fires when: user deletes board AND was at project limit
gtag('event', 'board_deleted_in_demo', {
    'potential_workaround': true,
    'projects_at_deletion': 2,
    'session_id': sessionId
});
```

This helps identify if users are testing the system limits.

---

## 📈 GA4 Conversion Events

All limitation encounters are tracked for conversion optimization:

### Events Fired

| Event | Trigger | Data |
|-------|---------|------|
| `limitation_encountered` | User hits any limit | `limitation_type`, `session_id`, `time_in_demo` |
| `demo_conversion_initiated` | User clicks upgrade CTA | `trigger_source`, `limitation_hit` |
| `demo_export_blocked` | Export attempt in demo | `export_type`, `board_id` |
| `board_deleted_in_demo` | Board deletion | `potential_workaround`, `project_count` |

### Tracking Implementation

```javascript
// static/js/demo_ga4_analytics.js
window.DemoAnalytics = {
    trackLimitationEncountered(type) { /* ... */ },
    trackConversionInitiated(source) { /* ... */ },
    trackWorkaroundAttempt(details) { /* ... */ }
};
```

---

## 🎨 UI Components

### Demo Banner (Updated)

Shows live status in the demo banner:

```
🎮 Demo Mode | 2/2 projects | Data resets in 23h | [Create Account]
```

### Limitation Modal

When users hit limits, a modal appears with:

- Clear explanation of the limitation
- Benefits of creating an account
- "Create Free Account" CTA (tracked)
- "Continue Exploring" option

Location: `templates/demo/partials/limitation_modal.html`

---

## 🔧 Implementation Files

| File | Purpose |
|------|---------|
| `kanban/utils/demo_limits.py` | Core limitation logic and constants |
| `kanban/views.py` | Enforcement in create_board, export_board, delete_board |
| `kanban/context_processors.py` | Demo status passed to all templates |
| `analytics/models.py` | DemoSession tracking fields |
| `static/js/demo_ga4_analytics.js` | Client-side GA4 event tracking |
| `templates/demo/partials/limitation_modal.html` | Upgrade modal UI |
| `templates/demo/partials/demo_banner.html` | Status display |

---

## 📊 Analytics Dashboard

View limitation and conversion metrics:

```bash
# Demo analytics report
python manage.py demo_analytics_report --days 7

# Output includes:
# - Limitation encounter rates by type
# - Conversion rate after hitting limits
# - Workaround attempt frequency
# - Most effective upgrade triggers
```

---

## 🎯 Conversion Philosophy

The limitations are designed around these principles:

1. **Value First:** Users experience full functionality before hitting limits
2. **Natural Friction:** Limits occur at logical points (2nd project, first export)
3. **Clear Communication:** Every limitation explains the "why" and shows benefits
4. **Non-Punitive:** Users can continue exploring; limits don't block existing work
5. **Trackable:** Every interaction is measured for optimization

---

## Related Documentation

- [Demo Data Guide](DEMO_DATA_GUIDE.md) - Dynamic demo data system
- [Anonymous Demo Tracking](ANONYMOUS_DEMO_TRACKING_GUIDE.md) - Full analytics guide
- [Improving Demo UX](Improving%20Demo%20UX.md) - Demo experience design
