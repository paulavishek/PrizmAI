# Fix Google Search API - Step-by-Step Guide

## Problem Identified ✓

**Error**: 403 Forbidden - "Requests to this API customsearch method are blocked"

**Root Cause**: Custom Search API is not enabled in your Google Cloud Project

---

## Solution: Enable Custom Search API

### Step 1: Go to Google Cloud Console

1. Open: https://console.cloud.google.com/
2. Make sure you're in the correct project (check the project selector at the top)

### Step 2: Enable Custom Search API

**Option A: Direct Link**
1. Go to: https://console.cloud.google.com/apis/library/customsearch.googleapis.com
2. Click the **"ENABLE"** button
3. Wait for it to enable (takes a few seconds)

**Option B: Through API Library**
1. Go to: https://console.cloud.google.com/apis/library
2. Search for: **"Custom Search API"**
3. Click on **"Custom Search API"** in the results
4. Click **"ENABLE"**

### Step 3: Verify API is Enabled

1. Go to: https://console.cloud.google.com/apis/dashboard
2. Look for **"Custom Search API"** in the enabled APIs list
3. Should show as **"Enabled"**

### Step 4: Check Billing (REQUIRED)

**Important**: Even though the first 100 queries/day are FREE, you MUST have billing enabled.

1. Go to: https://console.cloud.google.com/billing
2. If you see "This project has no billing account", click **"LINK A BILLING ACCOUNT"**
3. Follow steps to add a credit card
4. **Don't worry**: You won't be charged unless you exceed 100 queries/day

**Free Tier**:
- First 100 queries per day: **FREE**
- After 100: $5 per 1000 queries (you can set daily limits to prevent charges)

### Step 5: Test the Fix

Run the diagnostic again:
```powershell
python diagnose_google_search.py
```

You should see:
```
✅ SUCCESS! Google Search API is working correctly.
```

---

## Alternative: Disable Web Search (Temporary Workaround)

If you don't want to set up billing or can't enable the API right now, you can disable web search:

### Option 1: Disable in .env file
```bash
# In .env file, change:
ENABLE_WEB_SEARCH=False
```

### Option 2: Keep it enabled but AI will handle failures gracefully

**Good news**: I've already updated the code to handle web search failures gracefully!

**What this means**:
- ✅ AI Assistant will still work perfectly
- ✅ AI will use your project data
- ✅ AI will use Gemini's built-in knowledge
- ✅ For strategic questions, Gemini already has extensive knowledge of best practices
- ⚠ You just won't get the latest web search results (but Gemini's knowledge is very current)

---

## Recommended Action

### If you want RAG with web search:
1. ✅ Enable Custom Search API (Step 2 above)
2. ✅ Set up billing (Step 4 above)
3. ✅ Run diagnostic to verify
4. ✅ Enjoy enhanced AI with real-time web search!

### If you want to skip web search for now:
1. ✅ Do nothing! It already works without web search
2. ✅ AI will provide excellent answers using project data + Gemini's knowledge
3. ✅ You can enable it later when ready

---

## What Web Search Adds (RAG)

**With Web Search (RAG)**:
- Current industry trends and news
- Latest best practices from web
- Specific tool/framework documentation
- Recent research and methodologies

**Without Web Search (Still Excellent)**:
- Your complete project data
- Gemini's extensive built-in knowledge (trained on massive datasets)
- Best practices and strategies (from Gemini's training)
- Strategic advice and recommendations

**Bottom Line**: Web search enhances answers with real-time data, but Gemini already has excellent knowledge of project management, risk mitigation, and best practices!

---

## Testing After Fix

Try these questions to test web search:

1. **"What are the latest project management trends in 2025?"**
   - Should include web search results with current info

2. **"How to tackle high-risk issues?"**
   - Should combine web best practices + your project data

3. **"Best practices for risk mitigation"**
   - Should show industry standards + your mitigation plans

If web search is working, you'll see sources like:
- "Based on recent industry research..."
- "According to [web source]..."
- URLs in the response

---

## Summary

**Current Status**:
- ❌ Google Custom Search API not enabled → 403 error
- ✅ AI Assistant still works (uses project data + Gemini's knowledge)
- ✅ Code updated to handle search failures gracefully

**To Enable Web Search**:
1. Enable Custom Search API
2. Set up billing (required, but 100 queries/day are FREE)
3. Test with diagnostic script

**Or Just Use It As-Is**:
- AI works great without web search
- Gemini has excellent built-in knowledge
- You get strategic advice from both project data and Gemini's training
