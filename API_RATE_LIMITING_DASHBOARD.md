# API Rate Limiting Dashboard

## Overview

The API Rate Limiting Dashboard provides real-time monitoring and visualization of API usage across your PrizmAI instance. It demonstrates operational awareness by showing the **1000 requests per hour** limit in action with comprehensive monitoring capabilities.

## Features

### 📊 Real-Time Monitoring
- **Live Usage Tracking**: Updates every 5 seconds to show current API usage
- **Visual Progress Bars**: Color-coded usage indicators (Green < 50%, Yellow 50-80%, Red > 80%)
- **Countdown Timers**: Real-time countdown showing when rate limits reset
- **Instant Alerts**: Visual warnings when approaching rate limits

### 📈 Analytics & Insights
- **Hourly Request Charts**: Bar chart showing requests per hour over the last 24 hours
- **Minute-by-Minute Analysis**: Line chart tracking requests per minute over the last hour
- **Status Code Distribution**: Pie chart showing HTTP response code breakdown (2xx, 4xx, 5xx)
- **Top Endpoints**: Table listing the 10 most-used API endpoints with average response times

### 🔑 Token Management
- **Multi-Token Support**: Monitor multiple API tokens simultaneously
- **Token Status**: Active/Inactive badges for each token
- **Usage Statistics**: Current usage vs. limit for each token
- **Historical Data**: Last used timestamps and creation dates

### 🎯 Key Metrics Displayed

1. **Total Tokens**: Count of all API tokens created
2. **Active Tokens**: Number of currently active tokens
3. **Requests (1h)**: Total requests in the last hour
4. **Requests (24h)**: Total requests in the last 24 hours

## Rate Limiting Implementation

### How It Works

1. **Token-Based Authentication**: Each API token has an individual rate limit (default: 1000 requests/hour)
2. **Hourly Reset**: Rate limit counters reset exactly one hour after the first request
3. **Automatic Enforcement**: Requests exceeding the limit return HTTP 429 (Too Many Requests)
4. **Request Logging**: All API requests are logged for analytics and monitoring

### Rate Limit Headers

API responses include rate limit information:

```http
X-RateLimit-Limit: 1000
X-RateLimit-Remaining: 847
X-RateLimit-Reset: 2025-12-12T15:30:00Z
```

## Accessing the Dashboard

### Web Interface

1. Log in to your PrizmAI account
2. Click on your username in the top-right corner
3. Select **"API Rate Limits"** from the dropdown menu
4. Or navigate directly to: `/api/v1/dashboard/rate-limits/`

### Authentication Required

- The dashboard requires session authentication (not API token authentication)
- Only shows data for tokens owned by the logged-in user
- Admin users see organization-wide statistics

## Dashboard Components

### 1. Summary Cards

Four key metric cards at the top provide instant insights:
- **Total Tokens**: Your API token inventory
- **Active Tokens**: Tokens currently in use
- **Requests (1h)**: Recent activity indicator
- **Requests (24h)**: Daily usage overview

### 2. Token Cards

Individual cards for each API token showing:
- Token name and ID
- Active/Inactive status
- Current usage with progress bar
- Requests remaining
- Reset countdown timer
- Last used timestamp
- Creation date

### 3. Analytics Charts

Four interactive charts provide historical analysis:

#### Requests Per Hour (24h)
- Bar chart showing hourly distribution
- Identifies peak usage times
- Helps plan API usage patterns

#### Requests Per Minute (1h)
- Line chart with smooth transitions
- Shows recent activity spikes
- Useful for debugging issues

#### Status Code Distribution
- Doughnut chart with color coding
- Green: 2xx Success responses
- Blue: 3xx Redirect responses
- Yellow: 4xx Client errors
- Red: 5xx Server errors

#### Top 10 Endpoints
- Table format for easy reading
- Shows endpoint path and method
- Request count and average response time
- Identifies most-used APIs

## API Endpoint

### Real-Time Stats Endpoint

```
GET /api/v1/dashboard/rate-limits/stats/
```

**Response Format:**

```json
{
  "tokens": [
    {
      "id": 1,
      "name": "Production App",
      "rate_limit": 1000,
      "current_usage": 247,
      "remaining": 753,
      "usage_percent": 24.7,
      "reset_at": "2025-12-12T15:30:00Z",
      "seconds_until_reset": 1847,
      "last_used": "2025-12-12T14:58:23Z"
    }
  ],
  "charts": {
    "hourly_requests": [...],
    "minute_requests": [...],
    "status_distribution": [...],
    "top_endpoints": [...]
  },
  "timestamp": "2025-12-12T14:59:00Z"
}
```

**Query Parameters:**
- `token_id` (optional): Filter stats for a specific token

## Testing Rate Limits

### Using the Test Script

We provide a test script to simulate API usage:

```bash
python test_api_rate_limits.py
```

This script:
1. Creates a test API token if needed
2. Makes multiple API requests to demonstrate rate limiting
3. Shows real-time usage statistics
4. Demonstrates rate limit enforcement (HTTP 429)
5. Shows automatic reset after one hour

### Manual Testing with cURL

```bash
# Get an API token from the dashboard first
TOKEN="your_token_here"

# Make API requests
curl -H "Authorization: Bearer $TOKEN" \
  http://localhost:8000/api/v1/status/

# Check rate limit headers in response
curl -I -H "Authorization: Bearer $TOKEN" \
  http://localhost:8000/api/v1/status/
```

## Operational Awareness Benefits

### 1. **Proactive Monitoring**
- Identify usage patterns before hitting limits
- Plan capacity and scaling decisions
- Detect unusual activity patterns

### 2. **Performance Insights**
- Average response times per endpoint
- Error rate tracking
- Peak usage time identification

### 3. **Resource Planning**
- Historical data for trend analysis
- Usage forecasting capabilities
- Token allocation optimization

### 4. **Security & Compliance**
- Audit trail of all API requests
- IP address tracking
- Error pattern detection

### 5. **User Experience**
- Transparent rate limit display
- Clear countdown timers
- No surprises when limits are reached

## Best Practices

### For Administrators

1. **Regular Monitoring**: Check the dashboard weekly to review patterns
2. **Token Management**: Deactivate unused tokens
3. **Rate Limit Tuning**: Adjust limits based on usage patterns
4. **Error Investigation**: Review 4xx/5xx errors regularly

### For Developers

1. **Implement Retry Logic**: Handle 429 responses gracefully
2. **Cache Responses**: Reduce redundant API calls
3. **Batch Requests**: Combine multiple operations when possible
4. **Monitor Headers**: Check rate limit headers in responses

### For Organizations

1. **Token Segregation**: Use separate tokens for different apps
2. **Usage Policies**: Define acceptable usage patterns
3. **Alert Thresholds**: Set up notifications for high usage
4. **Capacity Planning**: Review trends for scaling decisions

## Technical Implementation

### Database Models

- **APIToken**: Stores token metadata and rate limit counters
- **APIRequestLog**: Records every API request for analytics

### Middleware

- **APIRequestLoggingMiddleware**: Automatically logs all API requests
- **APITokenAuthentication**: Enforces rate limits on each request

### Real-Time Updates

- JavaScript polls the stats endpoint every 5 seconds
- Countdown timers update every second
- Charts refresh automatically with new data

## Troubleshooting

### Dashboard Not Updating

1. Check browser console for JavaScript errors
2. Verify AJAX endpoint is accessible
3. Ensure user is authenticated

### Rate Limits Not Enforcing

1. Verify middleware is enabled in settings
2. Check token is active
3. Review database rate limit values

### Missing Historical Data

1. Confirm APIRequestLog entries are being created
2. Check database migrations are applied
3. Verify middleware is capturing requests

## Future Enhancements

Potential additions to consider:

- Email/SMS alerts when approaching limits
- Custom rate limit rules per token
- Geographic usage breakdown
- Integration with monitoring tools (Prometheus, Grafana)
- Export data to CSV/JSON
- Webhook notifications for rate limit events

## Support

For issues or questions about the Rate Limiting Dashboard:

1. Check the API documentation: `/api/v1/status/`
2. Review logs in the admin panel
3. Consult this documentation
4. Contact your system administrator

---

**Version**: 1.0  
**Last Updated**: December 12, 2025  
**Maintainer**: PrizmAI Development Team
