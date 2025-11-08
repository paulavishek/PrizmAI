# PrizmAI RESTful API Documentation

**Version:** v1  
**Base URL:** `http://localhost:8000/api/v1/`  
**Authentication:** Bearer Token

---

## 🚀 Overview

The PrizmAI API provides programmatic access to all core features of PrizmAI, enabling external applications, integrations, and automation tools to interact with your project management data.

### Key Features

- ✅ **RESTful Design** - Standard HTTP methods (GET, POST, PUT, PATCH, DELETE)
- ✅ **Token Authentication** - Secure API tokens with scope-based permissions
- ✅ **Rate Limiting** - 1000 requests/hour per token (configurable)
- ✅ **Pagination** - Efficient data retrieval for large datasets
- ✅ **Filtering & Search** - Query parameters for advanced filtering
- ✅ **JSON Responses** - Consistent, structured data format
- ✅ **Error Handling** - Clear error messages and HTTP status codes

---

## 🔐 Authentication

### Creating an API Token

#### Via Command Line
```bash
python manage.py create_api_token <username> <token_name> --scopes boards.read,tasks.write
```

#### Via API (Session Auth Required)
```bash
POST /api/v1/auth/tokens/create/
Content-Type: application/json

{
    "name": "My Integration",
    "scopes": ["boards.read", "tasks.write", "tasks.read"],
    "expires_in_days": 90
}
```

**Response:**
```json
{
    "id": 1,
    "name": "My Integration",
    "token": "VeryLongSecureTokenString123456789...",
    "scopes": ["boards.read", "tasks.write", "tasks.read"],
    "created_at": "2025-11-08T10:30:00Z",
    "expires_at": "2026-02-06T10:30:00Z",
    "rate_limit_per_hour": 1000
}
```

⚠️ **Important:** Save the token immediately - it won't be shown again!

### Using the Token

Include the token in the `Authorization` header:

```bash
Authorization: Bearer <your_token_here>
```

### Available Scopes

| Scope | Description |
|-------|-------------|
| `*` | Full access (all permissions) |
| `boards.read` | View boards and columns |
| `boards.write` | Create, update, delete boards |
| `tasks.read` | View tasks |
| `tasks.write` | Create, update, delete tasks |
| `comments.read` | View comments |
| `comments.write` | Create, update, delete comments |

---

## 📡 API Endpoints

### Status & Info

#### Check API Status
```http
GET /api/v1/status/
```

**Response:**
```json
{
    "status": "ok",
    "version": "v1",
    "authenticated": true,
    "user": "john_doe",
    "token_info": {
        "name": "My Integration",
        "scopes": ["boards.read", "tasks.write"],
        "rate_limit_per_hour": 1000,
        "requests_remaining": 987,
        "rate_limit_reset_at": "2025-11-08T11:00:00Z"
    }
}
```

---

### Boards

#### List All Boards
```http
GET /api/v1/boards/
```

**Query Parameters:**
- `page` - Page number (default: 1)
- `page_size` - Items per page (default: 50, max: 100)

**Response:**
```json
{
    "count": 5,
    "next": null,
    "previous": null,
    "results": [
        {
            "id": 1,
            "name": "Product Development",
            "description": "Main product board",
            "organization_name": "Acme Corp",
            "created_at": "2025-11-01T10:00:00Z",
            "task_count": 24
        }
    ]
}
```

#### Get Board Details
```http
GET /api/v1/boards/{id}/
```

**Response:**
```json
{
    "id": 1,
    "name": "Product Development",
    "description": "Main product board",
    "organization": 1,
    "organization_name": "Acme Corp",
    "created_at": "2025-11-01T10:00:00Z",
    "created_by": 2,
    "created_by_user": {
        "id": 2,
        "username": "john_doe",
        "email": "john@acme.com",
        "first_name": "John",
        "last_name": "Doe",
        "organization": {
            "id": 1,
            "name": "Acme Corp"
        }
    },
    "columns": [
        {
            "id": 1,
            "name": "To Do",
            "position": 0,
            "task_count": 8
        },
        {
            "id": 2,
            "name": "In Progress",
            "position": 1,
            "task_count": 5
        },
        {
            "id": 3,
            "name": "Done",
            "position": 2,
            "task_count": 11
        }
    ],
    "member_count": 7,
    "task_count": 24,
    "members": [2, 3, 4, 5, 6, 7, 8]
}
```

#### Create Board
```http
POST /api/v1/boards/
Content-Type: application/json

{
    "name": "Marketing Campaign",
    "description": "Q4 2025 marketing initiatives",
    "members": [2, 3, 4]
}
```

**Response:** 201 Created + Board object

#### Update Board
```http
PATCH /api/v1/boards/{id}/
Content-Type: application/json

{
    "description": "Updated description"
}
```

#### Delete Board
```http
DELETE /api/v1/boards/{id}/
```

**Response:** 204 No Content

#### Get Board Tasks
```http
GET /api/v1/boards/{id}/tasks/
```

Returns all tasks for a specific board.

#### Get Board Columns
```http
GET /api/v1/boards/{id}/columns/
```

Returns all columns for a specific board.

---

### Tasks

#### List All Tasks
```http
GET /api/v1/tasks/
```

**Query Parameters:**
- `board_id` - Filter by board ID
- `assigned_to` - Filter by assigned user ID
- `priority` - Filter by priority (low, medium, high, urgent)
- `column_id` - Filter by column ID
- `page` - Page number
- `page_size` - Items per page

**Example:**
```http
GET /api/v1/tasks/?board_id=1&priority=high&assigned_to=2
```

**Response:**
```json
{
    "count": 3,
    "next": null,
    "previous": null,
    "results": [
        {
            "id": 42,
            "title": "Fix login bug",
            "column": 2,
            "column_name": "In Progress",
            "priority": "high",
            "progress": 60,
            "assigned_to": 2,
            "assigned_to_username": "john_doe",
            "due_date": "2025-11-15T17:00:00Z",
            "label_count": 2,
            "created_at": "2025-11-08T09:00:00Z",
            "updated_at": "2025-11-08T14:30:00Z"
        }
    ]
}
```

#### Get Task Details
```http
GET /api/v1/tasks/{id}/
```

**Response:**
```json
{
    "id": 42,
    "title": "Fix login bug",
    "description": "Users are unable to login with Google OAuth",
    "column": 2,
    "column_name": "In Progress",
    "board_id": 1,
    "position": 1,
    "created_at": "2025-11-08T09:00:00Z",
    "updated_at": "2025-11-08T14:30:00Z",
    "start_date": "2025-11-08",
    "due_date": "2025-11-15T17:00:00Z",
    "assigned_to": 2,
    "assigned_to_user": {
        "id": 2,
        "username": "john_doe",
        "email": "john@acme.com",
        "first_name": "John",
        "last_name": "Doe",
        "organization": {
            "id": 1,
            "name": "Acme Corp"
        }
    },
    "created_by": 3,
    "created_by_user": {
        "id": 3,
        "username": "jane_smith",
        "email": "jane@acme.com",
        "first_name": "Jane",
        "last_name": "Smith",
        "organization": {
            "id": 1,
            "name": "Acme Corp"
        }
    },
    "labels": [
        {
            "id": 5,
            "name": "Bug",
            "color": "#FF0000",
            "category": "regular"
        },
        {
            "id": 8,
            "name": "High Priority",
            "color": "#FFA500",
            "category": "regular"
        }
    ],
    "priority": "high",
    "progress": 60,
    "ai_risk_score": 35,
    "required_skills": [
        {
            "name": "OAuth",
            "level": "Intermediate"
        }
    ],
    "skill_match_score": 85
}
```

#### Create Task
```http
POST /api/v1/tasks/
Content-Type: application/json

{
    "title": "Design landing page",
    "description": "Create mockup for new landing page",
    "column": 1,
    "priority": "medium",
    "assigned_to": 4,
    "due_date": "2025-11-20T17:00:00Z",
    "label_ids": [2, 5],
    "progress": 0
}
```

**Response:** 201 Created + Task object

#### Update Task
```http
PATCH /api/v1/tasks/{id}/
Content-Type: application/json

{
    "progress": 75,
    "priority": "high"
}
```

#### Delete Task
```http
DELETE /api/v1/tasks/{id}/
```

**Response:** 204 No Content

#### Move Task to Different Column
```http
POST /api/v1/tasks/{id}/move/
Content-Type: application/json

{
    "column_id": 3
}
```

Moves task to a different column (e.g., from "In Progress" to "Done").

#### Assign Task to User
```http
POST /api/v1/tasks/{id}/assign/
Content-Type: application/json

{
    "user_id": 5
}
```

Assigns task to a board member.

---

### Comments

#### List Comments
```http
GET /api/v1/comments/?task_id={task_id}
```

**Response:**
```json
{
    "count": 2,
    "next": null,
    "previous": null,
    "results": [
        {
            "id": 15,
            "task": 42,
            "user": {
                "id": 2,
                "username": "john_doe",
                "email": "john@acme.com",
                "first_name": "John",
                "last_name": "Doe"
            },
            "content": "I've identified the issue in the OAuth callback handler.",
            "created_at": "2025-11-08T14:30:00Z"
        }
    ]
}
```

#### Create Comment
```http
POST /api/v1/comments/
Content-Type: application/json

{
    "task": 42,
    "content": "This is resolved. PR #123 merged."
}
```

**Response:** 201 Created + Comment object

#### Delete Comment
```http
DELETE /api/v1/comments/{id}/
```

---

## 🔢 HTTP Status Codes

| Code | Meaning |
|------|---------|
| `200 OK` | Request successful |
| `201 Created` | Resource created successfully |
| `204 No Content` | Delete successful |
| `400 Bad Request` | Invalid request data |
| `401 Unauthorized` | Invalid or missing token |
| `403 Forbidden` | Insufficient permissions/scopes |
| `404 Not Found` | Resource not found |
| `429 Too Many Requests` | Rate limit exceeded |
| `500 Internal Server Error` | Server error |

---

## 🚦 Rate Limiting

- **Default:** 1000 requests/hour per token
- **Anonymous:** 100 requests/hour per IP
- **Rate limit headers** included in responses:
  - `X-RateLimit-Limit`
  - `X-RateLimit-Remaining`
  - `X-RateLimit-Reset`

When rate limit is exceeded:
```json
{
    "detail": "Rate limit exceeded. Please try again later."
}
```

---

## 📄 Pagination

All list endpoints support pagination:

**Request:**
```http
GET /api/v1/tasks/?page=2&page_size=25
```

**Response:**
```json
{
    "count": 100,
    "next": "http://localhost:8000/api/v1/tasks/?page=3&page_size=25",
    "previous": "http://localhost:8000/api/v1/tasks/?page=1&page_size=25",
    "results": [...]
}
```

---

## 🛠️ Example Use Cases

### 1. Slack Integration - Post Task Updates

```python
import requests

API_TOKEN = "your_token_here"
SLACK_WEBHOOK = "https://hooks.slack.com/services/..."

# Get high priority tasks
response = requests.get(
    "http://localhost:8000/api/v1/tasks/?priority=high",
    headers={"Authorization": f"Bearer {API_TOKEN}"}
)

tasks = response.json()['results']

# Post to Slack
for task in tasks:
    message = f"🔥 High Priority: {task['title']} - Due: {task['due_date']}"
    requests.post(SLACK_WEBHOOK, json={"text": message})
```

### 2. Create Task from External System

```javascript
const axios = require('axios');

async function createTaskFromJira(jiraIssue) {
    const response = await axios.post(
        'http://localhost:8000/api/v1/tasks/',
        {
            title: jiraIssue.summary,
            description: jiraIssue.description,
            column: 1, // "To Do" column
            priority: mapPriority(jiraIssue.priority),
            assigned_to: getUserIdFromEmail(jiraIssue.assignee.email)
        },
        {
            headers: {
                'Authorization': `Bearer ${process.env.PRIZMAI_API_TOKEN}`,
                'Content-Type': 'application/json'
            }
        }
    );
    
    return response.data;
}
```

### 3. Daily Report Generation

```bash
#!/bin/bash

API_TOKEN="your_token_here"
API_URL="http://localhost:8000/api/v1"

# Get today's completed tasks
COMPLETED=$(curl -s -H "Authorization: Bearer $API_TOKEN" \
    "$API_URL/tasks/?column_id=3&page_size=100" | \
    jq '.count')

echo "Tasks completed today: $COMPLETED"

# Get overdue tasks
OVERDUE=$(curl -s -H "Authorization: Bearer $API_TOKEN" \
    "$API_URL/tasks/?due_date__lt=$(date +%Y-%m-%d)" | \
    jq '.count')

echo "Overdue tasks: $OVERDUE"
```

---

## 🔍 Error Handling

All errors follow this format:

```json
{
    "detail": "Error message here",
    "error_code": "INVALID_TOKEN",
    "status_code": 401
}
```

Common errors:

### Invalid Token
```json
{
    "detail": "Invalid API token.",
    "status_code": 401
}
```

### Insufficient Scopes
```json
{
    "detail": "You do not have permission to perform this action.",
    "status_code": 403
}
```

### Rate Limit Exceeded
```json
{
    "detail": "Rate limit exceeded. Please try again later.",
    "status_code": 429
}
```

---

## 📊 Token Management

### List Your Tokens
```http
GET /api/v1/auth/tokens/
```

Returns all tokens for the authenticated user (session auth required).

### Delete Token
```http
DELETE /api/v1/auth/tokens/{token_id}/delete/
```

Revoke an API token immediately.

---

## 🔒 Security Best Practices

1. **Never commit tokens** to version control
2. **Use environment variables** to store tokens
3. **Rotate tokens regularly** (set expiration dates)
4. **Use minimal scopes** - only grant necessary permissions
5. **Monitor usage** - check token logs regularly
6. **Revoke compromised tokens** immediately
7. **Use IP whitelisting** for sensitive integrations

---

## 📚 Next Steps

1. ✅ **Create your first token** using the management command
2. ✅ **Test with curl** or Postman
3. ✅ **Build your integration** using the examples above
4. ✅ **Set up webhooks** (coming soon) for real-time notifications
5. ✅ **Explore Slack connector** (coming soon) for seamless integration

---

## 🆘 Support

- **API Issues:** Check your token scopes and rate limits
- **Integration Help:** Review the example code above
- **Feature Requests:** Open an issue on GitHub

---

**Last Updated:** November 8, 2025  
**API Version:** v1.0.0
