# API Rate Limiting Dashboard - Quick Setup Guide

## 🚀 Quick Start

### 1. Apply Database Migrations (if needed)

```bash
python manage.py makemigrations
python manage.py migrate
```

### 2. Start the Development Server

```bash
python manage.py runserver
```

Or use the provided batch file:
```bash
start_prizmAI_dev.bat
```

### 3. Access the Dashboard

1. Log in to PrizmAI: http://localhost:8000
2. Click your username (top-right corner)
3. Select **"API Rate Limits"** from dropdown

Or navigate directly to: http://localhost:8000/api/v1/dashboard/rate-limits/

## 🧪 Testing the Feature

### Option 1: Run the Demo Script

```bash
python test_api_rate_limits.py --demo
```

This will:
- Create a test API token
- Make sample API requests
- Demonstrate rate limiting
- Show real-time updates in the dashboard

### Option 2: Run Custom Tests

```bash
# Make 100 requests with delays
python test_api_rate_limits.py --requests 100

# Test rapid requests (trigger rate limiting)
python test_api_rate_limits.py --rapid

# Use specific token
python test_api_rate_limits.py --token YOUR_TOKEN_HERE --requests 50
```

### Option 3: Manual Testing

1. Create an API token via Django admin or the API
2. Make requests using curl or Postman:

```bash
curl -H "Authorization: Bearer YOUR_TOKEN" \
     http://localhost:8000/api/v1/status/
```

3. Watch the dashboard update in real-time!

## 📋 Requirements

### Python Packages

```bash
pip install colorama requests
```

All other dependencies are already in requirements.txt.

## 🎯 What to Look For

### In the Dashboard

1. **Summary Cards** (top) - Shows total tokens, active tokens, and request counts
2. **Token Cards** - Individual rate limit status with progress bars and timers
3. **Hourly Chart** - Bar chart showing request distribution over 24 hours
4. **Minute Chart** - Line chart showing recent activity (last hour)
5. **Status Codes** - Pie chart showing HTTP response distribution
6. **Top Endpoints** - Table listing most-used API endpoints

### Real-Time Features

- ⏱️ **Countdown timers** update every second
- 📊 **Progress bars** change color based on usage (green → yellow → red)
- 🔄 **Charts refresh** every 5 seconds
- 🎨 **Live indicator** shows dashboard is actively updating

## 💡 Demo Scenarios

### Scenario 1: Normal Usage
```bash
python test_api_rate_limits.py --requests 50
```
- Watch progress bar gradually fill
- See countdown timer in action
- Observe request patterns in charts

### Scenario 2: Approaching Limit
```bash
python test_api_rate_limits.py --requests 800
```
- Progress bar turns yellow/red
- Clear visual warning of approaching limit
- Shows operational awareness in action

### Scenario 3: Rate Limit Enforcement
```bash
python test_api_rate_limits.py --rapid
```
- Temporarily sets low limit (20 requests)
- Triggers HTTP 429 responses
- Demonstrates enforcement mechanism
- Shows how limits protect the API

## 🔧 Configuration

### Adjust Rate Limits

Edit in Django admin or programmatically:

```python
from api.models import APIToken

token = APIToken.objects.get(id=1)
token.rate_limit_per_hour = 2000  # Increase to 2000
token.save()
```

### Customize Dashboard Refresh Rate

Edit in [templates/api/rate_limit_dashboard.html](templates/api/rate_limit_dashboard.html):

```javascript
// Change from 5000ms (5 seconds) to 10000ms (10 seconds)
setInterval(updateDashboard, 10000);
```

## 📊 Key Features Demonstrated

### ✅ Operational Awareness
- Real-time visibility into API usage
- Proactive monitoring before hitting limits
- Clear visual indicators of system state

### ✅ 1000 Requests/Hour Limit
- Configurable per-token rate limits
- Automatic enforcement
- Graceful handling with HTTP 429

### ✅ Monitoring & Analytics
- Historical request data (24 hours)
- Minute-by-minute tracking
- Status code distribution
- Endpoint performance metrics

### ✅ User Experience
- Intuitive visual design
- Color-coded status indicators
- Live countdown timers
- No surprises - transparent limits

## 🐛 Troubleshooting

### Dashboard Not Showing Data

1. Ensure you're logged in
2. Create at least one API token
3. Make some API requests
4. Check browser console for errors

### Rate Limiting Not Working

1. Verify middleware is enabled in settings.py:
   ```python
   'kanban.audit_middleware.APIRequestLoggingMiddleware'
   ```

2. Check token is active:
   ```python
   token.is_active = True
   token.save()
   ```

3. Verify authentication header format:
   ```
   Authorization: Bearer YOUR_TOKEN
   ```

### Test Script Errors

Install required packages:
```bash
pip install colorama requests
```

## 📚 Additional Resources

- **Full Documentation**: [API_RATE_LIMITING_DASHBOARD.md](API_RATE_LIMITING_DASHBOARD.md)
- **API Documentation**: [API_DOCUMENTATION.md](API_DOCUMENTATION.md)
- **Dashboard URL**: http://localhost:8000/api/v1/dashboard/rate-limits/
- **API Status Endpoint**: http://localhost:8000/api/v1/status/

## 🎥 Quick Demo Flow

1. **Start server**: `python manage.py runserver`
2. **Open dashboard**: http://localhost:8000/api/v1/dashboard/rate-limits/
3. **Run demo**: `python test_api_rate_limits.py --demo` (in another terminal)
4. **Watch dashboard**: See real-time updates as requests are made
5. **Review analytics**: Check charts and statistics after test completes

## ✨ What Makes This Stand Out

1. **Live Updates**: Dashboard refreshes automatically, no manual refresh needed
2. **Visual Excellence**: Professional UI with color-coded indicators
3. **Comprehensive Analytics**: Not just limits - full usage insights
4. **Production Ready**: Real rate limiting with proper enforcement
5. **Developer Friendly**: Easy to test, monitor, and understand
6. **Operational Focus**: Demonstrates awareness and proactive management

---

**Ready to see it in action?** Run: `python test_api_rate_limits.py --demo`
