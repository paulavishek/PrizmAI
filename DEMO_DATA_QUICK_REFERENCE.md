# 🚀 Quick Reference: Demo Data Management

## Delete Old Demo Data

### Safe Method (Recommended)
```bash
# Step 1: Preview what will be deleted
python manage.py delete_demo_data --dry-run

# Step 2: Delete (with confirmation)
python manage.py delete_demo_data
# Type "DELETE" when prompted
```

### Fast Method (Skip Confirmation)
```bash
python manage.py delete_demo_data --no-confirm
```

## Create New Demo Data

```bash
python manage.py populate_test_data
```

## Verify Demo Data

```bash
python verify_demo_data.py
```

## Complete Reset Workflow

```bash
# 1. Check what will be deleted
python manage.py delete_demo_data --dry-run

# 2. Delete old demo
python manage.py delete_demo_data

# 3. Create fresh demo
python manage.py populate_test_data

# 4. Verify
python verify_demo_data.py

# 5. Start server
python manage.py runserver
```

## What Gets Deleted

✅ **7 Demo Users**: john_doe, jane_smith, robert_johnson, alice_williams, bob_martinez, carol_anderson, david_taylor  
✅ **2 Organizations**: Dev Team, Marketing Team  
✅ **All Associated Data**: Boards, tasks, chat rooms, stakeholders, etc.  
✅ **Wiki Data**: Categories, pages, attachments  
✅ **Meeting Data**: Transcripts and AI extractions

## What's Protected

🛡️ **Admin User**: Never deleted  
🛡️ **Other Organizations**: Only demo orgs are removed  
🛡️ **Database Schema**: Migrations remain intact

## Safety Features

🔒 **Transaction Protection**: All-or-nothing deletion  
🔒 **Dry-Run Mode**: Preview before deleting  
🔒 **Confirmation Prompt**: Requires typing "DELETE"  
🔒 **Detailed Summary**: Shows exactly what will be deleted

## Typical Counts (Your Current Data)

- Users: 7
- Organizations: 2
- Boards: 3
- Tasks: 32
- Chat Rooms: 12
- Stakeholders: 5
- Wiki Categories: 7
- Wiki Pages: 8
- Meeting Transcripts: 8
- **Total Items**: ~280+

## Files Created

📄 `kanban/management/commands/delete_demo_data.py` - Deletion script  
📄 `DEMO_DATA_DELETION_GUIDE.md` - Full documentation  
📄 `DEMO_DATA_QUICK_REFERENCE.md` - This file  
📄 `WIKI_AND_MEETING_DEMO_DATA_SUMMARY.md` - Wiki & meeting feature details

## Need Help?

Read the full guide: `DEMO_DATA_DELETION_GUIDE.md`

---

**Created:** November 6, 2025  
**Version:** 1.0
