# 🗑️ Demo Data Deletion Guide

## Overview

This guide explains how to safely delete all demo data from your PrizmAI application and prepare for a fresh demo setup.

## What Gets Deleted

The deletion script removes **ALL** demo data created by the `populate_test_data` command, including:

### 👥 Users (7 users)
- `john_doe`
- `jane_smith`
- `robert_johnson`
- `alice_williams`
- `bob_martinez`
- `carol_anderson`
- `david_taylor`

**Note:** The `admin` user is **NOT** deleted.

### 🏢 Organizations (2 organizations)
- Dev Team (devteam.com)
- Marketing Team (marketingteam.com)

### 📊 Associated Data
- **Boards** - All boards in demo organizations (Software Project, Bug Tracking, Marketing Campaign)
- **Tasks** - All tasks with dependencies, risk assessments, and requirements
- **Columns** - All kanban columns
- **Labels** - All task labels
- **Comments** - All task comments
- **Activities** - All task activity logs
- **Resource Management**
  - Resource demand forecasts
  - Capacity alerts
  - Workload recommendations
- **Stakeholder Management**
  - Stakeholders
  - Task involvements
  - Engagement records
  - Engagement metrics
- **Messaging**
  - Chat rooms
  - Chat messages
  - Thread comments
  - Notifications
  - File attachments
- **User Profiles** - Profiles for demo users

---

## ⚠️ Safety Features

The deletion script includes multiple safety mechanisms:

1. **Transaction Protection** - All deletions happen in a single database transaction that rolls back on error
2. **Dry-Run Mode** - Preview what will be deleted without actually deleting
3. **Confirmation Prompt** - Requires typing "DELETE" to confirm (can be bypassed with `--no-confirm`)
4. **Detailed Summary** - Shows exactly what will be deleted before proceeding
5. **Targeted Deletion** - Only deletes demo users and their organizations (preserves admin and other data)

---

## 📖 Usage Instructions

### Step 1: Preview What Will Be Deleted (Recommended)

Always run a dry-run first to see what will be deleted:

```bash
python manage.py delete_demo_data --dry-run
```

This will show you:
- Number of items to be deleted in each category
- List of users and organizations that will be removed
- Total item count

**Example Output:**
```
======================================================================
DEMO DATA DELETION SCRIPT
======================================================================

DRY RUN MODE - No data will be deleted

📊 DELETION SUMMARY:

  Users:                    7
  Organizations:            2
  User Profiles:            7
  Boards:                   3
  Columns:                  17
  Labels:                   25
  Tasks:                    32
  Comments:                 19
  Task Activities:          92
  Resource Forecasts:       4
  Capacity Alerts:          0
  Workload Recommendations: 2
  Stakeholders:             5
  Task Involvements:        16
  Engagement Records:       17
  Chat Rooms:               12
  Chat Messages:            0
  Thread Comments:          0
  Notifications:            0

  TOTAL ITEMS TO DELETE:    260
```

### Step 2: Delete Demo Data (With Confirmation)

To actually delete the data, run without `--dry-run`:

```bash
python manage.py delete_demo_data
```

You will be prompted to confirm:

```
⚠️  WARNING: This action cannot be undone!

Type "DELETE" to confirm deletion:
```

Type `DELETE` (all caps) and press Enter to proceed.

### Step 3: Delete Without Confirmation (Dangerous!)

If you're absolutely sure and want to skip confirmation:

```bash
python manage.py delete_demo_data --no-confirm
```

**⚠️ USE WITH EXTREME CAUTION** - This will delete immediately without asking!

---

## 🔄 Complete Workflow: Delete Old Demo → Create New Demo

### Full Reset Process

1. **Review what will be deleted:**
   ```bash
   python manage.py delete_demo_data --dry-run
   ```

2. **Delete the old demo data:**
   ```bash
   python manage.py delete_demo_data
   ```
   Type `DELETE` when prompted

3. **Create fresh demo data:**
   ```bash
   python manage.py populate_test_data
   ```

4. **Verify new demo data:**
   ```bash
   python verify_demo_data.py
   ```

5. **Start the server:**
   ```bash
   python manage.py runserver
   ```

---

## ✅ What Happens After Deletion

After successful deletion, you'll see:

```
======================================================================
✅ DEMO DATA DELETION COMPLETE!
======================================================================

Successfully deleted 260 items from the database.

ℹ️  The database is now clean and ready for new demo data.
   Run "python manage.py populate_test_data" to create new demo data.
```

The database will be in a clean state with:
- ✅ Admin user still intact
- ✅ All demo organizations removed
- ✅ All demo boards removed
- ✅ All demo tasks and related data removed
- ✅ All demo users removed
- ✅ Database schema intact and ready for new data

---

## 🛡️ What's Protected

The following data is **NEVER** deleted:

- ✅ `admin` user account
- ✅ Any organizations not named "Dev Team" or "Marketing Team"
- ✅ Any users not in the demo user list
- ✅ Any boards not belonging to demo organizations
- ✅ Database migrations and schema
- ✅ Django system tables

---

## 🚨 Error Handling

If an error occurs during deletion:

1. **Transaction Rollback** - All changes are automatically rolled back
2. **Error Message** - You'll see a clear error message
3. **Database State** - Your database remains unchanged
4. **No Partial Deletion** - Either everything is deleted or nothing is deleted

Example error output:

```
======================================================================
❌ ERROR DURING DELETION
======================================================================
Error: [error details]

⚠️  Transaction rolled back - No data was deleted.
   The database remains unchanged.
```

---

## 📋 Command Options Reference

| Option | Description | Example |
|--------|-------------|---------|
| `--dry-run` | Preview deletions without actually deleting | `python manage.py delete_demo_data --dry-run` |
| `--no-confirm` | Skip confirmation prompt (dangerous!) | `python manage.py delete_demo_data --no-confirm` |
| (no options) | Delete with confirmation prompt | `python manage.py delete_demo_data` |

---

## 🎯 Use Cases

### Use Case 1: Testing a New Demo Setup
```bash
# Preview
python manage.py delete_demo_data --dry-run

# Delete old demo
python manage.py delete_demo_data

# Create new demo
python manage.py populate_test_data
```

### Use Case 2: Cleaning Up Before Production
```bash
# Make sure demo data exists
python manage.py delete_demo_data --dry-run

# Remove all demo data
python manage.py delete_demo_data
```

### Use Case 3: Automated Script (CI/CD)
```bash
# Automated deletion (no confirmation needed)
python manage.py delete_demo_data --no-confirm

# Recreate demo
python manage.py populate_test_data
```

---

## 💡 Tips & Best Practices

1. **Always Run Dry-Run First** - Never delete without previewing
2. **Backup Your Database** - Create a backup before deletion if you're unsure
3. **Check Item Counts** - Verify the counts match your expectations
4. **Use in Development Only** - Never run this in production with real user data
5. **Review User List** - Make sure only demo users will be deleted
6. **Test After Deletion** - Verify your app still works after deletion
7. **Document Changes** - Keep track of when you delete/recreate demo data

---

## ⚙️ Technical Details

### Deletion Order

The script deletes data in the correct order to respect foreign key constraints:

1. Notifications (depends on users and content)
2. Typing status, file attachments
3. Chat messages and thread comments
4. Chat rooms
5. Stakeholder engagement records
6. Stakeholder task involvements
7. Stakeholder tags and metrics
8. Stakeholders
9. Workload recommendations
10. Capacity alerts
11. Resource forecasts
12. Task files
13. Task activities
14. Comments
15. Meeting transcripts
16. Tasks
17. Task labels
18. Columns
19. Boards
20. User profiles
21. Organizations
22. Users

### Transaction Protection

All deletions occur within a Django database transaction:

```python
with transaction.atomic():
    # All deletions happen here
    # If any error occurs, ALL changes are rolled back
```

This ensures your database is never left in an inconsistent state.

---

## 🔍 Troubleshooting

### Issue: "No demo data found"

**Solution:** This means demo data was already deleted or never created.

### Issue: Foreign key constraint errors

**Solution:** The script handles this automatically. If you see this error, it means the deletion order needs adjustment (please report as a bug).

### Issue: Permission denied

**Solution:** Make sure you have write access to the database file and media folders.

### Issue: Script hangs or takes too long

**Solution:** For large datasets, this is normal. The script processes all cascading deletions. Wait for completion.

---

## 📞 Support

If you encounter issues:

1. Check the error message carefully
2. Run with `--dry-run` to diagnose
3. Verify your database is accessible
4. Check that demo organizations exist
5. Review the deletion summary for unexpected counts

---

**Last Updated:** November 6, 2025  
**Version:** 1.0  
**Script Location:** `kanban/management/commands/delete_demo_data.py`
