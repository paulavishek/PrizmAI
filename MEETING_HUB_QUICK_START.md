# Meeting Hub - Quick Start Guide

## 🎯 Overview

The **Meeting Hub** is a unified platform for managing meeting transcripts, extracting actionable tasks using AI, and collaborating across your organization.

**Access**: Click **"Meetings"** in the main navigation bar

---

## 📊 Quick Navigation

```
Meeting Hub (https://localhost:8000/wiki/meetings/)
├── 📊 Dashboard (Home)
│   ├─ Recent meetings
│   ├─ Statistics (total meetings, tasks created)
│   └─ By-board breakdown
│
├── 📋 All Meetings (/wiki/meetings/list/)
│   ├─ Search by title/content
│   ├─ Filter by type (standup, planning, etc.)
│   ├─ Filter by board
│   └─ Filter by status (pending, completed, failed)
│
├── 🎙️ Upload & Analyze (/wiki/meetings/upload/)
│   ├─ Upload transcript file
│   ├─ Or paste transcript text
│   ├─ AI extracts tasks
│   └─ Review and create tasks
│
├── 📈 Analytics (/wiki/meetings/analytics/)
│   ├─ Meeting types breakdown
│   ├─ Tasks created over time
│   ├─ Top participants
│   └─ Time range filtering (7, 30, 90 days)
│
└── 📄 Individual Meeting Details
    ├─ View transcript
    ├─ See extracted tasks
    ├─ Check action items
    └─ View decisions made
```

---

## 🚀 Getting Started

### Step 1: Upload a Meeting
1. Go to **Meetings** → **"Upload & Analyze"**
2. Choose how to input transcript:
   - **Upload File**: txt, pdf, docx formats
   - **Paste Text**: Manually enter transcript
3. Fill in meeting details:
   - Title
   - Meeting Type (Standup, Planning, Review, Retrospective, General)
   - Date & Time
   - Duration (optional)
   - Attendees (comma-separated usernames)
4. Optionally link to a **Board** for context
5. Click **"Analyze with AI"**

### Step 2: AI Analyzes Transcript
System processes transcript and extracts:
- ✅ Actionable tasks
- 📋 Action items
- 💡 Decisions made
- 📞 Follow-up recommendations
- ⚠️ Unresolved items

**Status**: `pending` → `processing` → `completed`

### Step 3: Review Extracted Tasks
- See AI-extracted tasks with:
  - Task title
  - Description with context
  - Priority level
  - Suggested assignee
  - Estimated effort
  - Recommended due date
- Review extraction summary & confidence level

### Step 4: Create Tasks in Board
1. Select tasks you want to create
2. Click **"Create Selected Tasks"**
3. Tasks automatically added to linked board
4. System shows confirmation with task links

---

## 🎯 Key Features

### 1. **Smart Task Extraction**
AI analyzes meeting transcripts to identify:
- Clear action items
- Decisions requiring follow-up
- Assignments and commitments
- Timeline suggestions
- Dependencies between tasks

### 2. **Organization-Wide Search**
- Search across ALL meetings
- Filter by meeting type, board, status
- Find specific conversations
- Track meeting history

### 3. **Meeting Analytics**
See insights about:
- Most common meeting types
- Teams with most meetings
- Tasks created from meetings
- Participation trends

### 4. **Board Linking**
- Optional link to any board
- Provides context for AI analysis
- Creates tasks in linked board
- See board-specific meeting history

### 5. **Action Item Tracking**
- Auto-extracted action items
- Assigned team members
- Due dates
- Completion status

---

## 📋 Meeting Types

| Type | Use Case |
|------|----------|
| **Standup** | Daily team sync, progress updates |
| **Planning** | Sprint planning, project kickoff |
| **Review** | Status review, sprint review |
| **Retrospective** | Team reflection, improvement discussion |
| **General** | Other meetings |

---

## 🔍 Search & Filter

### Filter Options
- **By Type**: Show only specific meeting types
- **By Board**: Show meetings linked to a board
- **By Status**: Pending analysis, completed, failed
- **Search**: Find by title or content

### Example Searches
- "Login bug fix" → Find meetings discussing that
- Filter by board "Backend" → See all backend meetings
- Status "completed" → View analyzed meetings

---

## 📊 Analytics Dashboard

**Access**: Meetings → Analytics

View metrics:
- **Total Meetings**: In selected time range
- **Tasks Created**: From meeting analysis
- **Average Duration**: Typical meeting length
- **By Meeting Type**: Distribution of meeting types
- **By Board**: Where most meetings occur
- **Active Participants**: Who attends most meetings

**Filter by**: 7 days, 30 days, 90 days

---

## 🤖 AI Features

### What AI Extracts

**Tasks**:
```json
{
  "title": "Fix login authentication bug",
  "description": "Users report login failing with error 401",
  "priority": "high",
  "suggested_assignee": "john_dev",
  "due_date": "2025-11-08",
  "effort": "2-3 days"
}
```

**Decisions**:
```json
[
  "Use PostgreSQL for new database",
  "Deploy to AWS instead of GCP",
  "Review code before merge"
]
```

**Action Items**:
```json
[
  {
    "task": "Send analytics report",
    "assigned_to": "sarah",
    "due_date": "2025-11-06"
  }
]
```

### Confidence Levels
- **High**: Clear, unambiguous action items
- **Medium**: Likely actions, some interpretation needed
- **Low**: Mentioned but needs clarification

### AI Limitations
- Relies on clear communication in transcript
- Works best with technical/structured meetings
- May misinterpret sarcasm or implied meanings
- Always review extracted tasks

---

## 💡 Best Practices

### For Best Results:
1. **Use clear language** in meetings → Better AI extraction
2. **Specify deadlines** explicitly → Accurate due dates
3. **Name assignees** clearly → Correct task assignment
4. **Link to board** when relevant → Better context
5. **Include participants** → Accurate attendee tracking

### Tips:
- Upload transcript in text format when possible (better OCR)
- Review AI suggestions before creating tasks
- Use consistent naming for team members
- Reference relevant documents in meeting
- Record key decisions explicitly

---

## ⚙️ Settings & Configuration

### Meeting Details
- **Private/Public**: (future feature)
- **Transcription**: Manual, auto-transcribed, or uploaded
- **Recording Link**: (optional)
- **Related Docs**: Link to agendas, notes, etc.

---

## 🔐 Access Control

### Who Can See Meetings?
- **Creator**: Always
- **Attendees**: Always  
- **Board Members**: If meeting linked to board
- **Organization Members**: Can view all org meetings

### Who Can Create Tasks?
- **Linked Board**: Must be board member
- **Standalone**: Need wiki access

---

## 📱 File Upload Support

| Format | Support | Notes |
|--------|---------|-------|
| **TXT** | ✅ Full | Plain text transcripts |
| **PDF** | ✅ Full | Extracted via OCR |
| **DOCX** | ✅ Full | Word documents |
| **WAV/MP3** | ⏳ Future | Audio transcription |

**Max file size**: 10 MB

---

## 🆘 Troubleshooting

### Issue: "No tasks extracted"
**Solution**: 
- Ensure transcript has clear action items
- Check transcript wasn't corrupted during upload
- Try with different meeting type hint

### Issue: "Wrong assignee suggested"
**Solution**:
- Specify full name/username clearly
- Ensure user is spelled exactly as in system
- Add to attendees list

### Issue: "Due date not detected"
**Solution**:
- Use explicit dates: "by Friday" or "November 8"
- Avoid relative dates: "soon", "ASAP"
- Specify: "by end of sprint"

### Issue: "Can't create tasks in board"
**Solution**:
- Verify you're a board member
- Check board exists and is accessible
- Try creating task manually first

---

## 🔗 Related Features

- **Wiki**: Store meeting notes as wiki pages
- **AI Assistant**: Chat about meetings and decisions
- **Boards**: View meeting-extracted tasks
- **Messages**: Share meeting notes in channels

---

## 📞 Support

For issues or questions:
1. Check this guide
2. Visit Meeting Hub home page (help section)
3. Contact your organization admin
4. Report bugs with transcript sample (if not sensitive)

---

**Last Updated**: November 4, 2025
**Status**: ✅ Live & Ready
