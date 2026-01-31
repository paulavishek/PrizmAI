# Kanban Board Import Schema for PrizmAI

You've hit on a key challenge in PM tool interoperability! Let me break this down:

## The Schema Problem

You're absolutely right - **direct imports only work if schemas match**, which is rare between different tools. Each PM tool has its own proprietary data structure. This is why most tools don't support direct imports from competitors.

## How PM Tools Actually Handle This

Real-world solutions typically use one of these approaches:

1. **Standard formats** - CSV exports (lowest common denominator - just task lists)
2. **API integrations** - Tools like Zapier/Make map fields between different schemas
3. **Custom importers** - Build specific converters for popular tools (Trello → Your Tool, Asana → Your Tool)
4. **Manual mapping UI** - Let users map columns during import (source field → destination field)

## What Format You'll Actually Get

- **Trello**: JSON export via API or JSON file download
- **Asana**: CSV or JSON via API
- **Jira**: XML, CSV, or JSON
- **Monday.com**: CSV or Excel
- **Most tools**: CSV is the universal fallback

## Sample Kanban Board Data

Here's what a **PrizmAI-native JSON export** might look like for import:

```json
{
  "board_metadata": {
    "board_id": "board_001",
    "board_name": "Product Launch Q1 2024",
    "export_date": "2024-01-31T10:30:00Z",
    "exported_by": "avi@clairlabs.com",
    "tool_name": "PrizmAI",
    "version": "1.0"
  },
  "columns": [
    {
      "column_id": "col_1",
      "name": "Backlog",
      "position": 0,
      "wip_limit": null,
      "color": "#E8E8E8"
    },
    {
      "column_id": "col_2",
      "name": "To Do",
      "position": 1,
      "wip_limit": 5,
      "color": "#FFF4E6"
    },
    {
      "column_id": "col_3",
      "name": "In Progress",
      "position": 2,
      "wip_limit": 3,
      "color": "#E3F2FD"
    },
    {
      "column_id": "col_4",
      "name": "Review",
      "position": 3,
      "wip_limit": 2,
      "color": "#FFF9C4"
    },
    {
      "column_id": "col_5",
      "name": "Done",
      "position": 4,
      "wip_limit": null,
      "color": "#C8E6C9"
    }
  ],
  "cards": [
    {
      "card_id": "card_001",
      "title": "Design landing page mockups",
      "description": "Create high-fidelity mockups for the product landing page including hero section, features, pricing, and testimonials",
      "column_id": "col_3",
      "position": 0,
      "priority": "high",
      "labels": ["design", "frontend", "marketing"],
      "assignees": ["user_101", "user_102"],
      "due_date": "2024-02-15",
      "created_at": "2024-01-20T09:00:00Z",
      "updated_at": "2024-01-28T14:30:00Z",
      "estimated_hours": 16,
      "actual_hours": 8,
      "attachments": [
        {
          "filename": "brand_guidelines.pdf",
          "url": "/files/brand_guidelines.pdf",
          "size": 2048576
        }
      ],
      "checklist": [
        {
          "item": "Wireframe approval",
          "completed": true
        },
        {
          "item": "Design system review",
          "completed": true
        },
        {
          "item": "Stakeholder feedback",
          "completed": false
        }
      ],
      "comments": [
        {
          "comment_id": "cmt_001",
          "user_id": "user_103",
          "text": "Looks great! Can we add more whitespace in the hero section?",
          "created_at": "2024-01-27T11:20:00Z"
        }
      ],
      "custom_fields": {
        "department": "Product",
        "sprint": "Sprint 3",
        "story_points": 5
      }
    },
    {
      "card_id": "card_002",
      "title": "Set up analytics tracking",
      "description": "Implement Google Analytics 4 and Mixpanel for product usage tracking",
      "column_id": "col_2",
      "position": 0,
      "priority": "medium",
      "labels": ["backend", "analytics"],
      "assignees": ["user_104"],
      "due_date": "2024-02-20",
      "created_at": "2024-01-25T10:15:00Z",
      "updated_at": "2024-01-25T10:15:00Z",
      "estimated_hours": 8,
      "actual_hours": 0,
      "attachments": [],
      "checklist": [
        {
          "item": "GA4 setup",
          "completed": false
        },
        {
          "item": "Mixpanel integration",
          "completed": false
        },
        {
          "item": "Event tracking plan",
          "completed": true
        }
      ],
      "comments": [],
      "custom_fields": {
        "department": "Engineering",
        "sprint": "Sprint 4",
        "story_points": 3
      }
    },
    {
      "card_id": "card_003",
      "title": "Write API documentation",
      "description": "Create comprehensive API docs using Swagger/OpenAPI spec",
      "column_id": "col_4",
      "position": 0,
      "priority": "high",
      "labels": ["documentation", "api"],
      "assignees": ["user_105"],
      "due_date": "2024-02-10",
      "created_at": "2024-01-15T08:00:00Z",
      "updated_at": "2024-01-30T16:45:00Z",
      "estimated_hours": 12,
      "actual_hours": 10,
      "attachments": [],
      "checklist": [
        {
          "item": "Authentication endpoints",
          "completed": true
        },
        {
          "item": "CRUD operations",
          "completed": true
        },
        {
          "item": "Webhook documentation",
          "completed": false
        }
      ],
      "comments": [
        {
          "comment_id": "cmt_002",
          "user_id": "user_106",
          "text": "Please add code examples in Python and JavaScript",
          "created_at": "2024-01-29T09:30:00Z"
        }
      ],
      "custom_fields": {
        "department": "Engineering",
        "sprint": "Sprint 3",
        "story_points": 5
      }
    },
    {
      "card_id": "card_004",
      "title": "Conduct user testing sessions",
      "description": "Run 5 moderated user testing sessions with beta customers",
      "column_id": "col_1",
      "position": 0,
      "priority": "medium",
      "labels": ["research", "ux"],
      "assignees": ["user_107"],
      "due_date": "2024-03-01",
      "created_at": "2024-01-28T13:00:00Z",
      "updated_at": "2024-01-28T13:00:00Z",
      "estimated_hours": 20,
      "actual_hours": 0,
      "attachments": [],
      "checklist": [],
      "comments": [],
      "custom_fields": {
        "department": "Product",
        "sprint": "Sprint 5",
        "story_points": 8
      }
    },
    {
      "card_id": "card_005",
      "title": "Fix login page responsive issues",
      "description": "Mobile layout breaks on screens < 375px width",
      "column_id": "col_5",
      "position": 0,
      "priority": "high",
      "labels": ["bug", "frontend", "mobile"],
      "assignees": ["user_102"],
      "due_date": "2024-01-25",
      "created_at": "2024-01-22T11:30:00Z",
      "updated_at": "2024-01-26T10:00:00Z",
      "estimated_hours": 4,
      "actual_hours": 3,
      "attachments": [
        {
          "filename": "bug_screenshot.png",
          "url": "/files/bug_screenshot.png",
          "size": 156789
        }
      ],
      "checklist": [
        {
          "item": "Test on iPhone SE",
          "completed": true
        },
        {
          "item": "Test on Android small screen",
          "completed": true
        },
        {
          "item": "Deploy fix",
          "completed": true
        }
      ],
      "comments": [],
      "custom_fields": {
        "department": "Engineering",
        "sprint": "Sprint 3",
        "story_points": 2
      }
    }
  ],
  "users": [
    {
      "user_id": "user_101",
      "name": "Sarah Chen",
      "email": "sarah@clairlabs.com",
      "avatar_url": "/avatars/sarah.jpg"
    },
    {
      "user_id": "user_102",
      "name": "Raj Patel",
      "email": "raj@clairlabs.com",
      "avatar_url": "/avatars/raj.jpg"
    },
    {
      "user_id": "user_103",
      "name": "Emily Rodriguez",
      "email": "emily@clairlabs.com",
      "avatar_url": "/avatars/emily.jpg"
    },
    {
      "user_id": "user_104",
      "name": "Mike Johnson",
      "email": "mike@clairlabs.com",
      "avatar_url": "/avatars/mike.jpg"
    },
    {
      "user_id": "user_105",
      "name": "Priya Sharma",
      "email": "priya@clairlabs.com",
      "avatar_url": "/avatars/priya.jpg"
    },
    {
      "user_id": "user_106",
      "name": "David Kim",
      "email": "david@clairlabs.com",
      "avatar_url": "/avatars/david.jpg"
    },
    {
      "user_id": "user_107",
      "name": "Lisa Thompson",
      "email": "lisa@clairlabs.com",
      "avatar_url": "/avatars/lisa.jpg"
    }
  ],
  "board_settings": {
    "visibility": "team",
    "allow_guests": false,
    "enable_time_tracking": true,
    "enable_wip_limits": true
  }
}
```

## Practical Recommendation for PrizmAI

Start with these **import strategies in order of priority**:

1. **Native JSON format** (as above) - for PrizmAI exports/imports
2. **CSV import with field mapping** - universal compatibility
3. **Trello JSON importer** - Trello is most commonly exported from
4. **API integrations** (later phase) - Asana, Jira, Monday
