# AI Coach Quick Reference

## Check Status
```bash
python check_marketing_bug_suggestions.py
```

## Regenerate Suggestions

### Single Board
```bash
python regenerate_ai_suggestions_universal.py --board "Marketing Campaign"
python regenerate_ai_suggestions_universal.py --board "Bug Tracking"
python regenerate_ai_suggestions_universal.py --board "Software Development"
```

### By Board ID
```bash
python regenerate_ai_suggestions_universal.py --board-id 2
```

### All Demo Boards
```bash
python regenerate_ai_suggestions_universal.py --all-demo
```

### All Boards
```bash
python regenerate_ai_suggestions_universal.py --all
```

## View Details
```bash
python view_detailed_suggestions.py
```

## From Browser
1. Go to board: `http://127.0.0.1:8000/board/<id>/coach/`
2. Click "Refresh Suggestions" button

## Expected Format

All suggestions should have:
- ✅ Generation Method: `hybrid`
- ✅ AI Model: `gemini-2.0-flash-exp`
- ✅ Detailed "Why This Matters" section
- ✅ 3-5 Recommended Actions with rationale
- ✅ Expected Impact section

## Troubleshooting

### Suggestions are still brief?
```bash
# Delete and regenerate
python regenerate_ai_suggestions_universal.py --board "Your Board Name"
```

### No suggestions generated?
- Board may not have issues detected by rule engine
- Check board has tasks and activity
- Use force script for demo boards

### AI enhancement failing?
- Check GEMINI_API_KEY is configured
- Check logs for error messages
- Verify internet connection
