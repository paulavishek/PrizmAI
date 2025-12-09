# 🪝 PrizmAI Webhooks & Integration Guide

This guide explains how to use webhooks to integrate PrizmAI with external applications.

**Quick navigation:** [README.md](README.md) | [FEATURES.md](FEATURES.md) | [USER_GUIDE.md](USER_GUIDE.md)

---

## 📚 Table of Contents

- [What Are Webhooks?](#-what-are-webhooks)
- [How Webhooks Work](#-how-webhooks-work)
- [Supported Events](#-supported-events)
- [Setting Up Webhooks](#-setting-up-webhooks)
- [Webhook Payload Examples](#-webhook-payload-examples)
- [Real-World Integration Examples](#-real-world-integration-examples)
- [Webhook Security](#-webhook-security)
- [Testing & Debugging](#-testing--debugging)
- [Troubleshooting](#-troubleshooting)

---

## 🪝 What Are Webhooks?

Webhooks allow PrizmAI to **automatically notify external apps** when important events happen in your projects. Think of it as "push notifications for your integrations."

**Instead of constantly polling:** "Is there anything new?"
**Webhooks push updates:** "Hey! A task was just assigned!"

### Why Use Webhooks?

✅ **Real-time Updates** - Get notified immediately when things happen  
✅ **Automation** - Trigger actions in other apps automatically  
✅ **Integration** - Connect PrizmAI with Slack, Teams, Zapier, etc.  
✅ **Efficiency** - No need to constantly check for updates  
✅ **Visibility** - Keep your whole team informed across platforms  

---

## 🔄 How Webhooks Work

### Step-by-Step Process

1. **You create a webhook** - Provide a URL where PrizmAI should send notifications
2. **You select events** - Choose which events trigger the webhook (task created, updated, assigned, etc.)
3. **Events happen** - When someone creates/updates a task, PrizmAI sends data to your URL
4. **External app receives data** - Your app processes the JSON payload
5. **External app takes action** - Post to Slack, update a spreadsheet, trigger automation, etc.

### Example Flow

```
User creates task in PrizmAI
         ↓
PrizmAI detects "task.created" event
         ↓
PrizmAI sends webhook to your URL:
  POST https://your-app.com/webhooks/prizmAI
  Body: {event: "task.created", data: {...}}
         ↓
Your app receives the data
         ↓
Your app posts message to Slack:
  "📋 New task: 'Design login page' due Friday"
         ↓
Slack channel is updated automatically
```

---

## 📋 Supported Events

### Task Events

**`task.created`** - New task added to board
```json
{
  "event": "task.created",
  "timestamp": "2025-01-15T10:30:00Z",
  "board_id": 42,
  "data": {
    "id": 123,
    "title": "Design homepage mockup",
    "priority": "high",
    "assigned_to": "alice",
    "due_date": "2025-01-20"
  }
}
```

**`task.updated`** - Task details changed (title, description, etc.)
```json
{
  "event": "task.updated",
  "timestamp": "2025-01-15T11:00:00Z",
  "board_id": 42,
  "data": {
    "id": 123,
    "title": "Design homepage mockup",
    "description": "Updated with new requirements",
    "priority": "high"
  }
}
```

**`task.completed`** - Task moved to done/completed column
```json
{
  "event": "task.completed",
  "timestamp": "2025-01-15T15:30:00Z",
  "board_id": 42,
  "data": {
    "id": 123,
    "title": "Design homepage mockup",
    "completed_at": "2025-01-15T15:30:00Z"
  }
}
```

**`task.assigned`** - Task assigned to a team member
```json
{
  "event": "task.assigned",
  "timestamp": "2025-01-15T10:45:00Z",
  "board_id": 42,
  "data": {
    "id": 123,
    "title": "Design homepage mockup",
    "assigned_to": "alice",
    "assigned_by": "bob"
  }
}
```

**`task.moved`** - Task moved to different column
```json
{
  "event": "task.moved",
  "timestamp": "2025-01-15T14:00:00Z",
  "board_id": 42,
  "data": {
    "id": 123,
    "title": "Design homepage mockup",
    "from_column": "To Do",
    "to_column": "In Progress"
  }
}
```

**`task.deleted`** - Task deleted from board
```json
{
  "event": "task.deleted",
  "timestamp": "2025-01-15T16:00:00Z",
  "board_id": 42,
  "data": {
    "id": 123,
    "title": "Design homepage mockup"
  }
}
```

### Comment Events

**`comment.added`** - New comment on a task
```json
{
  "event": "comment.added",
  "timestamp": "2025-01-15T10:50:00Z",
  "board_id": 42,
  "data": {
    "task_id": 123,
    "task_title": "Design homepage mockup",
    "comment": "Added new requirements in the description",
    "author": "alice"
  }
}
```

### Board Events

**`board.updated`** - Board settings changed
```json
{
  "event": "board.updated",
  "timestamp": "2025-01-15T09:00:00Z",
  "board_id": 42,
  "data": {
    "title": "Mobile App - Q1 Release",
    "description": "Updated project scope"
  }
}
```

---

## 🔧 Setting Up Webhooks

### From Your Board

1. Click the **⚙️ Settings** button (top right of board)
2. Select **"Webhooks & Integrations"**
3. Click **"Add Webhook"**
4. **Fill in the form:**

```
Webhook Name: "Slack Notifications"
  └─ For your reference (e.g., "Email Alerts", "Zapier Sync")

Webhook URL: https://hooks.slack.com/services/YOUR/WEBHOOK/URL
  └─ Where PrizmAI should send the data

Select Events:
  ☑ task.created
  ☑ task.updated
  ☑ task.completed
  ☑ task.assigned
  ☐ task.moved
  ☐ task.deleted
  ☐ comment.added
  └─ Choose which events trigger this webhook

Advanced Options (optional):
  Timeout: 30 seconds
  Max Retries: 3
  Custom Headers: (for authentication)
```

5. Click **"Create"**
6. Click **"Test"** to verify it works
7. Done! Now events will be sent automatically

### Example Webhook Creation

```bash
# Using the API to create a webhook (if preferred)
curl -X POST http://localhost:8000/api/v1/webhooks/ \
  -H "Authorization: Bearer YOUR_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "name": "Slack Notifications",
    "url": "https://hooks.slack.com/services/...",
    "events": ["task.created", "task.assigned"],
    "is_active": true
  }'
```

---

## 📨 Webhook Payload Examples

### Complete Payload Format

```json
{
  "event": "task.created",
  "timestamp": "2025-01-15T10:30:00Z",
  "webhook_id": "wh_abc123def456",
  "board_id": 42,
  "signature": "sha256=...",
  "data": {
    "id": 123,
    "title": "Design homepage mockup",
    "description": "Create responsive design for homepage",
    "priority": "high",
    "assigned_to": {
      "id": 5,
      "username": "alice",
      "email": "alice@company.com",
      "full_name": "Alice Smith"
    },
    "created_by": {
      "id": 3,
      "username": "bob",
      "email": "bob@company.com"
    },
    "due_date": "2025-01-20",
    "column": "In Progress",
    "estimated_hours": 8,
    "actual_hours": 2,
    "complexity": 5,
    "status": "in_progress",
    "tags": ["design", "ui", "high-priority"],
    "board": {
      "id": 42,
      "title": "Mobile App - Q1 Release"
    }
  }
}
```

### Headers Sent with Webhook

```
X-PrizmAI-Event: task.created
X-PrizmAI-Webhook-ID: wh_abc123def456
X-PrizmAI-Timestamp: 2025-01-15T10:30:00Z
X-PrizmAI-Signature: sha256=abcdef123456...
Content-Type: application/json
```

---

## 🌐 Real-World Integration Examples

### Example 1: Slack Notifications

**Goal:** Post task updates to Slack channels

**Setup:**
1. Get Slack webhook URL from Slack (Incoming Webhooks)
2. Create PrizmAI webhook pointing to Slack URL
3. Select `task.created`, `task.assigned`, `task.completed` events

**Result:**
```
Channel: #projects
Message:
  📋 New task: "Design homepage mockup"
  👤 Assigned to: Alice
  📅 Due: Friday, Jan 20
  🔗 [View in PrizmAI]

Channel: #projects  
Message:
  ✅ Alice completed "Design homepage mockup"
  🎉 Great work!
```

### Example 2: Email Alerts

**Goal:** Send email notifications for important tasks

**Setup:**
1. Create webhook pointing to your email service (e.g., SendGrid, Mailgun)
2. Select `task.created` (high priority only), `task.completed` events
3. Configure email template in your service

**Result:**
```
From: alerts@prizmAI.com
To: manager@company.com
Subject: New High Priority Task: Design Homepage

Hi Bob,

A new high-priority task has been assigned:
- Title: Design homepage mockup
- Due: Friday, Jan 20
- Assigned to: Alice

View in PrizmAI: [Link]
```

### Example 3: Google Sheets / Airtable Sync

**Goal:** Automatically update spreadsheet with task status

**Setup:**
1. Use Zapier to connect PrizmAI webhooks to Google Sheets
2. Configure Zapier to add new rows for new tasks
3. Configure another Zap to update rows when tasks complete

**Result:**
```
Spreadsheet automatically updates:
- Task name, description, assignee added when created
- Status updated when task moves between columns
- Completed date added when task finishes
```

### Example 4: Custom Automation with Zapier

**Goal:** Multi-step automation - when task is assigned, create entry in CRM

**Setup:**
1. Create Zapier Zap: "When PrizmAI task is assigned..."
2. Add action: "Create record in Salesforce"
3. Map task details to CRM fields

**Result:**
```
When task assigned to Alice:
  → Create Salesforce lead
  → Set assignee to Alice
  → Set due date
  → Add to campaign
```

### Example 5: Project Management Sync

**Goal:** Sync PrizmAI tasks with Jira

**Setup:**
1. Create webhook for `task.created` and `task.updated`
2. Build connector app that:
   - Receives webhook data
   - Transforms to Jira format
   - Creates/updates Jira issue

**Result:**
```
Task created in PrizmAI
  → Webhook fires
  → Connector creates Jira issue
  → Jira and PrizmAI stay in sync
```

---

## 🔒 Webhook Security

### HMAC Signature Verification

Every webhook delivery includes an `X-PrizmAI-Signature` header that you should verify:

```python
# Example: Verify webhook signature (Python)
import hmac
import hashlib

webhook_secret = "your-webhook-secret"
signature = request.headers.get('X-PrizmAI-Signature')
payload_body = request.body

expected_signature = hmac.new(
    webhook_secret.encode(),
    payload_body,
    hashlib.sha256
).hexdigest()

if signature != expected_signature:
    raise ValueError("Invalid signature - not from PrizmAI!")
    
# Process webhook data safely
process_webhook(request.json)
```

### JavaScript Example

```javascript
const crypto = require('crypto');

function verifyWebhookSignature(payload, signature, secret) {
  const hash = crypto
    .createHmac('sha256', secret)
    .update(payload)
    .digest('hex');
  
  return hash === signature;
}

app.post('/webhook', (req, res) => {
  const signature = req.headers['x-prizmAI-signature'];
  
  if (!verifyWebhookSignature(
    JSON.stringify(req.body),
    signature,
    process.env.WEBHOOK_SECRET
  )) {
    return res.status(401).send('Unauthorized');
  }
  
  // Process webhook
  handleWebhookEvent(req.body);
  res.status(200).send('OK');
});
```

### Security Best Practices

✅ **Always verify signatures** - Prevents malicious actors from impersonating PrizmAI  
✅ **Use HTTPS URLs only** - Encrypt data in transit  
✅ **Store secrets securely** - Use environment variables, never commit to code  
✅ **Validate data** - Check that webhook data is what you expect  
✅ **Rate limit** - Prevent abuse by limiting requests per time period  
✅ **Log webhooks** - Keep audit trail of webhook deliveries  
✅ **Use unique secrets** - Different secret per webhook  

---

## 🧪 Testing & Debugging

### Test a Webhook

1. Go to webhook detail page
2. Click **"Test Webhook"** button
3. PrizmAI sends a test payload with sample data
4. View response and status

### Check Delivery Logs

1. Go to webhook detail page
2. Click **"Delivery Logs"** tab
3. See list of all webhook deliveries
4. Click on any delivery to see:
   - Request payload sent
   - Response received
   - Status (success/failure)
   - Timestamp

### Debug Delivery Issues

**Issue: Webhook not being called**

Check:
1. Is the webhook active? (Toggle on/off switch)
2. Are the right events selected? (Create a task to test `task.created`)
3. Is the URL correct? (Typos prevent delivery)
4. Is your endpoint running? (Check logs of your app)

**Issue: Webhook called but not working**

Check:
1. Response status (should be 2xx for success)
2. Signature verification (verify you're checking signature correctly)
3. Data format (compare against documentation)
4. Your endpoint logs (what error is happening?)

**Issue: Webhook timing out**

Check:
1. Your endpoint response time (should be < 30 seconds)
2. Network latency (try endpoint with `curl` locally)
3. Webhook timeout setting (increase if needed)
4. Server logs for slow queries

### Manual Testing with curl

```bash
# Test your endpoint locally
curl -X POST http://localhost:3000/webhook \
  -H "Content-Type: application/json" \
  -H "X-PrizmAI-Signature: sha256=test" \
  -d '{
    "event": "task.created",
    "timestamp": "2025-01-15T10:30:00Z",
    "board_id": 42,
    "data": {
      "id": 123,
      "title": "Test task",
      "assigned_to": "alice"
    }
  }'
```

---

## ⚙️ Webhook Management

### View All Webhooks

1. Open board settings
2. Click "Webhooks & Integrations"
3. See list of all configured webhooks with:
   - Name and URL
   - Active/inactive status
   - Last delivery time
   - Success/failure count

### Edit a Webhook

1. Click webhook name
2. Modify:
   - Events (add/remove)
   - URL (if moving endpoints)
   - Timeout settings
   - Custom headers
3. Click "Update"

### Delete a Webhook

1. Find webhook in list
2. Click three-dot menu
3. Select "Delete"
4. Confirm deletion

### Monitoring Webhook Health

Dashboard shows:
- 📊 Delivery success rate (%)
- 📈 Deliveries over time (graph)
- 🔴 Failed deliveries (with error details)
- ⏱️ Average response time
- ⚠️ Webhooks with high failure rate

---

## 🔄 Webhook Reliability

### Automatic Retries

If webhook delivery fails, PrizmAI retries with exponential backoff:

```
Attempt 1: Immediately
Attempt 2: 5 seconds later
Attempt 3: 30 seconds later
Attempt 4: 5 minutes later
Attempt 5: 30 minutes later
```

If all retries fail, webhook is marked as failed.

### Health Monitoring

If webhook has high failure rate:
- System alerts you
- Webhook is temporarily disabled
- You can re-enable and retry
- Previous deliveries are logged for replay

---

## 📋 Webhook Limits

**Rate Limits:**
- 100 webhooks per board
- 1000 deliveries per hour per webhook
- 10MB payload size maximum

**Timeout:**
- 30 seconds default (configurable)
- Minimum 5 seconds, maximum 120 seconds

**Retention:**
- Delivery logs kept for 30 days
- Failed deliveries can be manually replayed

---

## 🆘 Troubleshooting

| Problem | Solution |
|---------|----------|
| Webhook not firing | Check URL is correct, check events are selected |
| Signature verification failing | Verify you're using correct secret and algorithm |
| Endpoint timing out | Optimize endpoint, increase timeout, check server logs |
| High failure rate | Check logs, verify your endpoint is healthy |
| Slack messages not posting | Verify Slack webhook URL, check Slack workspace settings |
| Need to replay failed deliveries | Use "Retry" button in delivery logs |

---

**← Back to [README.md](README.md)**
