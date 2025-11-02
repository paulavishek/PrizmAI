# Gantt Chart Demo Data - Dynamic Date System

## ✅ What Changed

The Gantt chart demo data now uses **dynamic dates** that are always relative to the current date, ensuring the demo remains relevant regardless of when it's run.

## 🔄 How It Works

### Before (❌ Fixed Dates)
```python
# Old approach - dates would become outdated
start_date = datetime(2025, 11, 1)  # Fixed date
due_date = datetime(2025, 11, 10)    # Fixed date
```

**Problem**: If someone runs the demo in 2026 or later, all tasks would appear outdated or expired.

### After (✅ Dynamic Dates)
```python
# New approach - always relative to today
base_date = timezone.now().date()    # Always uses current date
start_date = base_date + timedelta(days=-7)   # 7 days ago
due_date = start_date + timedelta(days=5)     # 5 day duration
```

**Benefit**: Demo data automatically adjusts to be current, no matter when it's run!

## 📅 Date Logic

All task dates are calculated relative to **today** using offsets:

### Software Project Board

| Column | Offset Range | Example (if today is Nov 2) |
|--------|-------------|--------------------------|
| **Done** | -25 to -15 days | Oct 8 - Oct 18 |
| **Review** | -3 days | Oct 30 |
| **In Progress** | -7 to -5 days | Oct 26 - Oct 28 |
| **To Do** | +2 to +5 days | Nov 4 - Nov 7 |
| **Backlog** | +12 to +25 days | Nov 14 - Nov 27 |

### Bug Tracking Board

| Column | Offset Range | Example (if today is Nov 2) |
|--------|-------------|--------------------------|
| **Closed** | -12 to -8 days | Oct 21 - Oct 25 |
| **Testing** | -4 days | Oct 29 |
| **In Progress** | -2 days | Oct 31 |
| **Investigating** | -1 day | Nov 1 |
| **New** | 0 to +1 days | Nov 2 - Nov 3 |

## 🎯 Task Timeline Spread

Tasks are intelligently distributed across time:

```
Past (Completed)    Present (Active)    Future (Planned)
     ◄─────────────────┼─────────────────►
     
Oct 8       Oct 28    Nov 2    Nov 14      Dec 1
  │            │        │         │          │
Done      In Progress Today   To Do      Backlog
```

## 🔧 Running The Commands

### Fix Gantt Data (Re-run anytime)
```bash
python manage.py fix_gantt_demo_data
```
**When to use**: 
- After creating/resetting demo data
- If dates seem outdated
- Can be run monthly/quarterly to "refresh" the timeline

### Populate Test Data (Includes auto-fix)
```bash
python manage.py populate_test_data
```
**Note**: This now automatically calls `fix_gantt_demo_data` at the end, so Gantt charts are always properly configured!

## 📊 Dependencies Created

The system creates realistic **Finish-to-Start** dependencies:

### Software Project Flow
```
Setup Repository (Done)
    ↓
Auth Middleware (In Progress)
    ↓
Dashboard Layout (In Progress)
    ↓
Review Homepage (Review)
    ↓
Component Library (To Do)
    ↓
Documentation (To Do)

Database Schema (Backlog)
    ↓
User Authentication (Backlog)
    ↓
CI/CD Pipeline (Backlog)
```

### Bug Tracking Flow
```
Inconsistent Data (Investigating)
    ├→ Pagination Fix (Testing)
    └→ Search Performance (New)
```

## 🌟 Benefits

1. **Always Current**: Demo data never looks outdated
2. **Realistic Timeline**: Tasks span past, present, and future
3. **Proper Dependencies**: Shows real project workflow
4. **Easy Maintenance**: Run one command to refresh
5. **Time-Proof**: Works in 2025, 2026, 2027, and beyond!

## 🧪 Testing Different Timelines

You can test how the Gantt chart will look at different times by temporarily changing the base_date in the code, but in production it will always use the current date automatically.

---

**Last Updated**: November 2, 2025  
**Auto-updates**: Every time `fix_gantt_demo_data` is run, dates recalculate based on current date
