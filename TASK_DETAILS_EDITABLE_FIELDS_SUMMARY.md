# Task Details Page - Comprehensive Editable Fields Summary

## Overview
This document provides a complete list of all fields that are displayed and editable on the task details page. All fields have been verified to be included in the TaskForm so users have full control over all displayed information.

---

## Main Task Information (Left Column)

| Field | Type | Required | Editable | Notes |
|-------|------|----------|----------|-------|
| **Title** | Text | ✅ Yes | ✅ Yes | Task name |
| **Description** | Text Area | ❌ No | ✅ Yes | Detailed task description |
| **Start Date** | Date | ❌ No | ✅ Yes | For Gantt chart scheduling |
| **Due Date** | DateTime | ❌ No | ✅ Yes | Task deadline |
| **Priority** | Select | ❌ No | ✅ Yes | Low, Medium, High, Urgent |
| **Progress** | Number (0-100) | ❌ No | ✅ Yes | Completion percentage |
| **Assigned To** | Select | ❌ No | ✅ Yes | Team member assignment |
| **Labels** | MultiSelect | ❌ No | ✅ Yes | Task categorization (including Lean Six Sigma) |
| **Complexity Score** | Range Slider (1-10) | ❌ No | ✅ Yes | Task complexity rating |

---

## Dependencies & Requirements (Right Column)

### Task Hierarchy
| Field | Type | Required | Editable | Notes |
|-------|------|----------|----------|-------|
| **Parent Task** | Select | ❌ No | ✅ Yes | Creates subtask hierarchy |
| **Dependencies** | MultiSelect | ❌ No | ✅ Yes | Tasks that must be completed first |
| **Related Tasks** | MultiSelect | ❌ No | ✅ Yes | **NEW** - Related but not dependent tasks |

### Required Skills & Resource Analysis
| Field | Type | Required | Editable | Notes |
|-------|------|----------|----------|-------|
| **Required Skills** | JSON Textarea | ❌ No | ✅ Yes | **NEWLY EDITABLE** - Skills needed (JSON format) |
| **Skill Match Score** | Number (0-100) | ❌ No | ✅ Yes | **NEWLY EDITABLE** - Assignee skill match percentage |
| **Collaboration Required** | Checkbox | ❌ No | ✅ Yes | **NEWLY EDITABLE** - Does task need team collaboration? |
| **Workload Impact** | Select | ❌ No | ✅ Yes | Low/Medium/High/Critical impact on workload |

---

## Risk Management (Right Column)

| Field | Type | Required | Editable | Notes |
|-------|------|----------|----------|-------|
| **Risk Likelihood** | Select | ❌ No | ✅ Yes | 1=Low, 2=Medium, 3=High |
| **Risk Impact** | Select | ❌ No | ✅ Yes | 1=Low, 2=Medium, 3=High |
| **Risk Level** | Select | ❌ No | ✅ Yes | Low/Medium/High/Critical |
| **Risk Indicators** | Text Area | ❌ No | ✅ Yes | Key indicators to monitor (one per line) |
| **Mitigation Strategies** | Text Area | ❌ No | ✅ Yes | Risk mitigation approaches (one per line) |

---

## Read-Only Information (For Reference - NOT Editable)

These fields are automatically managed by the system:

| Field | Source | Notes |
|-------|--------|-------|
| **Status** | Column | Changes via Kanban board interaction |
| **Created By** | System | User who created the task |
| **Created On** | System | Task creation timestamp |
| **Comments** | User Input | Added via comments form below |
| **Activity Log** | System | Automatically tracked |
| **File Attachments** | User Upload | Uploaded separately |
| **Stakeholders** | Separate Interface | Managed via Stakeholder Manager |

---

## Form Field Mapping

### Fields in TaskForm.Meta.fields:
```python
fields = [
    'title',                      # Main form
    'description',                # Main form
    'start_date',                 # Main form
    'due_date',                   # Main form
    'assigned_to',                # Main form
    'labels',                      # Main form
    'priority',                    # Main form
    'progress',                    # Main form
    'dependencies',               # Dependencies section
    'parent_task',                # Dependencies section
    'complexity_score',           # Skills & Resource section
    'required_skills',            # Skills & Resource section (NEWLY EDITABLE)
    'skill_match_score',          # Skills & Resource section (NEWLY EDITABLE)
    'collaboration_required',     # Skills & Resource section (NEWLY EDITABLE)
    'workload_impact',            # Skills & Resource section
    'related_tasks',              # Dependencies section (NEWLY EDITABLE)
    'risk_likelihood',            # Risk Management section
    'risk_impact',                # Risk Management section
    'risk_level',                 # Risk Management section
]
```

---

## Required Skills Format

When editing **Required Skills**, use JSON format:

### Example:
```json
[
  {
    "name": "Python",
    "level": "Advanced"
  },
  {
    "name": "Django",
    "level": "Intermediate"
  },
  {
    "name": "PostgreSQL",
    "level": "Intermediate"
  }
]
```

### Alternative Format (Python list):
```python
[{"name": "Python", "level": "Advanced"}, {"name": "Django", "level": "Intermediate"}]
```

---

## Recent Updates (v1.1)

### Fields Made Editable:
✅ **required_skills** - Now users can edit required skills for tasks
✅ **skill_match_score** - Now users can edit the skill match percentage
✅ **collaboration_required** - Now users can indicate collaboration needs
✅ **related_tasks** - Now users can link related tasks

### Widget Improvements:
- ✅ Required Skills: Textarea with JSON format guide
- ✅ Skill Match Score: Number input (0-100)
- ✅ Collaboration Required: Checkbox
- ✅ Related Tasks: MultiSelect with tasks from same board

---

## Testing Checklist

- [ ] Edit a task and modify all Required Skills
- [ ] Edit Skill Match Score for a task
- [ ] Check/uncheck Collaboration Required
- [ ] Add Related Tasks to a task
- [ ] Verify all changes save correctly
- [ ] Verify all displayed fields can be modified
- [ ] Test JSON parsing for Required Skills field
- [ ] Confirm changes appear on task detail page refresh

---

## Support & Help

### JSON Format Help
For required_skills, the system accepts both:
- Valid JSON format with proper formatting
- Python list format
- If parsing fails, field is set to empty list

### Field Descriptions
Hover over field labels in the form for detailed explanations of each field's purpose.

### Related Documentation
- See `kanban/forms/__init__.py` for field definitions
- See `kanban/models.py` for model field specifications
- See `templates/kanban/task_detail.html` for UI layout

---

**Last Updated:** November 9, 2025
**Version:** 1.1
**Status:** All editable fields now have user control ✅
