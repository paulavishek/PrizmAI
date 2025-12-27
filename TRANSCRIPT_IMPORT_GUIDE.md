# 📝 Transcript Import Feature - User Guide

## Overview
The **Transcript Import** feature allows you to import meeting transcripts from various sources (Fireflies.ai, Otter.ai, Zoom, Teams, etc.) directly into your wiki pages. The AI will then analyze the transcript and extract action items, decisions, blockers, and key points.

## ✨ Features

- **Multi-Source Support**: Import from Fireflies.ai, Otter.ai, Microsoft Teams, Zoom, Google Meet, or paste manually
- **Automatic AI Analysis**: Optionally analyze the transcript immediately after import
- **Metadata Tracking**: Store meeting date, duration, participants, and source information
- **Non-Intrusive**: Transcripts are appended to existing wiki content without overwriting
- **No External Dependencies**: Works with your existing AI infrastructure

## 🚀 How to Use

### Step 1: Create or Open a Wiki Page
1. Navigate to **Knowledge Hub** (Wiki section)
2. Create a new page or open an existing one
3. Make sure the page is in a **Meeting Notes** category (AI Meeting Analysis enabled)

### Step 2: Import Transcript
1. Click the **"Import Transcript"** button (orange button next to the AI assistant buttons)
2. Select your transcript source from the dropdown:
   - **Fireflies.ai**
   - **Otter.ai**
   - **Microsoft Teams**
   - **Zoom**
   - **Google Meet**
   - **Manual Paste / Other**

### Step 3: Add Transcript Details
1. **Paste Transcript**: Copy and paste your meeting transcript into the text area
2. **Meeting Date** (optional): Select the meeting date
3. **Duration** (optional): Enter meeting duration in minutes
4. **Participants** (optional): Add comma-separated participant names

### Step 4: Choose Analysis Option
- ✅ **Automatically run AI analysis after import** (recommended)
  - The AI will immediately extract action items, decisions, blockers, and risks
  - Results will be available right away
  
- ⬜ **Import without analysis**
  - Just append the transcript to the page
  - Run AI analysis manually later

### Step 5: Import
1. Click **"Import & Append to Page"**
2. Wait for the import to complete (2-5 seconds)
3. Page will reload with the transcript added

## 📋 Transcript Format Examples

### Fireflies.ai Format
```
Speaker 1: Let's start with the sprint review.
Speaker 2: The authentication feature is complete. I'll demo it now.
Speaker 1: Great! What's the status on the dashboard redesign?
Speaker 3: We're 70% done. Should be ready by Friday.
```

### Otter.ai Format
```
John Smith 0:00
Hey everyone, thanks for joining the standup today.

Sarah Johnson 0:15
No problem. I finished the API integration yesterday.

Mike Chen 0:30
I'm still working on the UI components. Should be done by EOD.
```

### Manual/General Format
```
Meeting: Q4 Planning Session
Date: December 27, 2025

John: We need to prioritize the mobile app for Q4.
Sarah: Agreed. I suggest we allocate 2 engineers to that.
Mike: What about the web dashboard updates?
John: That can be Q1. Mobile is more urgent.

Action Items:
- John to draft mobile app requirements
- Sarah to assign 2 engineers
- Team to review requirements by Friday
```

## 🎯 Best Practices

1. **Use Meeting Categories**: Ensure your wiki page is in a "Meeting Notes" or similar category with AI Meeting Analysis enabled
2. **Include Context**: Add participant names and meeting date for better AI analysis
3. **Auto-Analyze**: Enable automatic analysis to save time
4. **Clean Transcripts**: Remove excessive timestamps or formatting issues before importing
5. **Review AI Results**: Always review AI-extracted action items before creating tasks

## 🔧 Technical Details

### Supported Sources
- **Fireflies.ai**: Paste transcript directly from Fireflies
- **Otter.ai**: Export and paste from Otter
- **Microsoft Teams**: Copy transcript from Teams meeting recap
- **Zoom**: Use Zoom's transcript feature
- **Google Meet**: Copy transcript from Meet recording
- **Manual**: Any text-based transcript

### What Gets Stored
- Original transcript content (appended to wiki page)
- Source information (Fireflies, Otter, etc.)
- Import timestamp
- Meeting metadata (date, duration, participants)
- AI analysis results (if auto-analyzed)

### Privacy & Security
- All transcripts are stored in your database
- No external API calls for transcript storage
- AI analysis uses your existing OpenAI configuration
- Transcripts respect your organization's access controls

## 🆚 Comparison: Import vs. Native Integrations

### Why Import (Current Approach)?
✅ **No external dependencies or costs**
✅ **Works with any transcript source**
✅ **Full data control and privacy**
✅ **Uses your existing AI infrastructure**
✅ **Simple and flexible**

### Native Fireflies/Otter Integration (Future Option)
❌ Requires API keys and additional costs
❌ Limited to specific platforms
❌ Data sent to third-party services
❌ More complex setup and maintenance
✅ Automatic capture (no manual paste)

## 🔮 Future Enhancements

Potential additions based on user feedback:
- Bulk import multiple transcripts
- Direct file upload (.txt, .docx)
- Fireflies API integration (optional)
- Speaker diarization improvements
- Transcript search and filtering
- Transcript version history

## 🐛 Troubleshooting

**Import button not showing?**
- Verify your page is in a Meeting Notes category
- Check that AI Meeting Analysis is enabled for the category

**Analysis not running automatically?**
- Ensure "Automatically run AI analysis" is checked
- Verify you have AI quota remaining
- Check your OpenAI API configuration

**Transcript formatting looks odd?**
- Clean up excessive line breaks before importing
- Remove timestamps if they're too frequent
- Use markdown formatting if needed

## 📞 Support

For issues or feature requests:
1. Check this guide first
2. Review the wiki page category settings
3. Contact your system administrator
4. Submit feedback through the analytics feedback form

---

**Version**: 1.0  
**Last Updated**: December 27, 2025  
**Feature Status**: ✅ Production Ready
