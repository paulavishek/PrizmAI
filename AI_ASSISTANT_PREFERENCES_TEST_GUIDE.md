# AI Assistant Preferences - Testing Guide ✅

## 🎨 What Was Fixed

### 1. Display Preferences UI Improvements
**Problem:** Theme radio buttons looked disorganized and hard to use
**Solution:** 
- Redesigned theme selection with Bootstrap button group
- Added icons for each theme option (☀️ Sun for Light, 🌙 Moon for Dark, ⚙️ Adjust for Auto)
- Better visual spacing and organization
- Clear labels and help text

**Before:**
- Plain radio buttons stacked vertically
- No visual feedback
- Confusing layout

**After:**
- Professional button group spanning full width
- Icons make options clear at a glance
- Active selection highlighted
- Clean, organized appearance

### 2. Removed Obsolete "Preferred AI Model" Section
- Since you only use Gemini, removed the confusing model selection
- Cleaner preferences page focused on actual settings

## 🔧 Functionality Fixes

### 1. Theme Preference Synchronization ✅
**Added:**
- Context processor to pass user preferences to all templates
- Theme value stored in `data-user-theme` attribute on body tag
- JavaScript syncs theme changes between localStorage and database
- Theme toggle button now saves preference to database

**How it works:**
1. User selects theme in preferences
2. Saved to database
3. On page load, theme applied from database preference
4. When toggling with navbar button, syncs to database
5. Supports "Auto" mode (follows system preference)

### 2. Messages Per Page Integration ✅
**Fixed:**
- `get_session_messages` view now uses user's `messages_per_page` preference
- Previously hardcoded to 20, now respects user choice
- Range: 5-100 messages per page

## 📋 Complete Testing Checklist

### Test 1: Display Preferences UI ✅

1. **Navigate to Preferences**
   ```
   AI Assistant → Preferences (gear icon)
   ```

2. **Check Theme Selection Appearance**
   - [ ] Three buttons displayed horizontally: Light, Dark, Auto
   - [ ] Icons displayed: ☀️ (Light), 🌙 (Dark), ⚙️ (Auto)
   - [ ] Currently selected theme is highlighted in blue
   - [ ] Buttons are equal width and span full container
   - [ ] Help text appears above buttons

3. **Check Messages Per Page Field**
   - [ ] Number input field is properly styled
   - [ ] Has min/max constraints (5-100)
   - [ ] Help text is clear and visible

---

### Test 2: Feature Preferences Functionality ✅

1. **Test All Toggle Switches**
   - [ ] Enable Web Search (RAG) - toggles on/off
   - [ ] Enable Task Insights - toggles on/off
   - [ ] Enable Risk Alerts - toggles on/off
   - [ ] Enable Resource Recommendations - toggles on/off

2. **Save and Verify**
   - [ ] Change all settings
   - [ ] Click "Save Preferences"
   - [ ] See success message
   - [ ] Refresh page
   - [ ] All settings retained

---

### Test 3: Notification Preferences ✅

1. **Test All Notification Toggles**
   - [ ] Notify on Risk Detection - toggles on/off
   - [ ] Notify on Team Overload - toggles on/off
   - [ ] Notify on Dependency Issues - toggles on/off

2. **Save and Verify**
   - [ ] Toggle each setting
   - [ ] Click "Save Preferences"
   - [ ] See success message
   - [ ] Refresh page
   - [ ] All settings retained

---

### Test 4: Theme Functionality 🎨

#### A. Light Theme Test
1. **Set Light Theme**
   - [ ] Go to Preferences
   - [ ] Click "Light" button (☀️)
   - [ ] Click "Save Preferences"
   - [ ] Page immediately shows light theme

2. **Verify Across Pages**
   - [ ] Navigate to AI Assistant Chat
   - [ ] Check Analytics page
   - [ ] Check Welcome page
   - [ ] All pages show light theme

3. **Check Navbar Toggle**
   - [ ] Click theme toggle button in navbar
   - [ ] Switches to dark
   - [ ] Toggle again, switches back to light
   - [ ] Refresh page - theme persists

#### B. Dark Theme Test
1. **Set Dark Theme**
   - [ ] Go to Preferences
   - [ ] Click "Dark" button (🌙)
   - [ ] Click "Save Preferences"
   - [ ] Page immediately shows dark theme

2. **Verify Across Pages**
   - [ ] Navigate to various pages
   - [ ] All show dark theme
   - [ ] Text is readable
   - [ ] No styling issues

3. **Check Persistence**
   - [ ] Close browser completely
   - [ ] Reopen and login
   - [ ] Dark theme still applied

#### C. Auto Theme Test
1. **Set Auto Theme**
   - [ ] Go to Preferences
   - [ ] Click "Auto" button (⚙️)
   - [ ] Click "Save Preferences"

2. **Verify System Sync**
   - [ ] If your system is in light mode, app shows light
   - [ ] If your system is in dark mode, app shows dark
   - [ ] Change system theme, app updates accordingly

---

### Test 5: Messages Per Page Functionality 📄

#### A. Change Messages Per Page
1. **Set to 10**
   - [ ] Go to Preferences
   - [ ] Change "Messages per Page" to 10
   - [ ] Click "Save Preferences"
   - [ ] See success message

2. **Verify in Chat**
   - [ ] Go to AI Assistant Chat
   - [ ] Create a session with 20+ messages
   - [ ] Open chat history
   - [ ] First page shows exactly 10 messages
   - [ ] Pagination available to see more

#### B. Try Different Values
1. **Test Minimum (5)**
   - [ ] Set to 5 messages per page
   - [ ] Save
   - [ ] Check chat history shows 5 per page

2. **Test Maximum (100)**
   - [ ] Set to 100 messages per page
   - [ ] Save
   - [ ] Chat history shows up to 100 per page

3. **Test Default (20)**
   - [ ] Set back to 20
   - [ ] Save
   - [ ] Verify 20 messages per page

---

### Test 6: Cross-Browser Theme Persistence 🌐

1. **Chrome Test**
   - [ ] Set theme to Dark in Chrome
   - [ ] Close browser
   - [ ] Reopen - theme is Dark

2. **Different Browser Test**
   - [ ] Open in Firefox/Edge
   - [ ] Login
   - [ ] Theme matches saved preference (Dark)
   - [ ] Change to Light
   - [ ] Open in Chrome again
   - [ ] Theme is now Light in Chrome too

---

### Test 7: Integration Tests 🔄

#### A. Theme + Navbar Toggle
1. **Set Database Theme**
   - [ ] Set theme to Light in Preferences
   - [ ] Save

2. **Toggle in Navbar**
   - [ ] Click theme toggle button
   - [ ] Switches to Dark
   - [ ] Go to Preferences
   - [ ] Dark button is now selected
   - [ ] Database was updated

#### B. Multiple Users
1. **User 1 Settings**
   - [ ] Login as User 1
   - [ ] Set Dark theme, 30 messages per page
   - [ ] Logout

2. **User 2 Settings**
   - [ ] Login as User 2
   - [ ] Set Light theme, 50 messages per page
   - [ ] Logout

3. **Verify Isolation**
   - [ ] Login as User 1 again
   - [ ] Theme is Dark
   - [ ] Messages per page is 30
   - [ ] User 2's settings didn't affect User 1

---

### Test 8: Edge Cases 🔍

#### A. New User Defaults
1. **Create New User**
   - [ ] Register new account
   - [ ] Login
   - [ ] Check theme (should be Light - default)
   - [ ] Go to Preferences
   - [ ] Light button is selected
   - [ ] Messages per page is 20 (default)

#### B. Invalid Input
1. **Messages Per Page Validation**
   - [ ] Try to set messages per page to 0
   - [ ] Should not allow (min is 5)
   - [ ] Try to set to 200
   - [ ] Should not allow (max is 100)

#### C. Rapid Theme Changes
1. **Quick Toggles**
   - [ ] Click theme toggle button 5 times quickly
   - [ ] Each toggle works
   - [ ] No errors in console
   - [ ] Final state is correct

---

## 🎯 Expected Results Summary

### ✅ ALL Tests Should Pass:

1. **Display Preferences UI**
   - Professional button group for theme selection
   - Clear icons and labels
   - Responsive design

2. **Theme Functionality**
   - Light/Dark/Auto all work correctly
   - Persists across sessions and browsers
   - Syncs between navbar toggle and preferences
   - Applies to all pages

3. **Messages Per Page**
   - Respects user preference (5-100 range)
   - Applies to chat history pagination
   - Default is 20 for new users

4. **All Preferences**
   - Save correctly to database
   - Persist after logout/login
   - Isolated per user
   - Success message on save

5. **No Bugs**
   - No console errors
   - No styling issues
   - Smooth transitions
   - Fast response

---

## 🐛 If You Find Issues

### Theme Not Applying?
1. Check browser console for errors
2. Clear localStorage: `localStorage.clear()` in console
3. Hard refresh page (Ctrl+Shift+R)
4. Check if preference saved in database

### Messages Per Page Not Working?
1. Verify preference saved (check Preferences page)
2. Clear browser cache
3. Create new chat session to test
4. Check that you have enough messages to paginate

### Preferences Not Saving?
1. Check for console errors during save
2. Verify CSRF token is present
3. Check Django logs for errors
4. Try different preference to isolate issue

---

## 📊 Technical Implementation Details

### Files Modified:

1. **templates/ai_assistant/preferences.html**
   - Improved theme selection UI with button group
   - Added icons and better styling
   - Added JavaScript for immediate theme application
   - Removed obsolete "Preferred AI Model" section

2. **ai_assistant/views.py**
   - Updated `get_session_messages()` to use `user_pref.messages_per_page`
   - Ensures pagination respects user preference

3. **kanban_board/context_processors.py**
   - Added `user_preferences()` context processor
   - Makes user AI preferences available in all templates

4. **kanban_board/settings.py**
   - Registered new context processor

5. **templates/base.html**
   - Added `data-user-theme` attribute to body tag
   - Allows JavaScript to read database preference

6. **static/js/theme-toggle.js**
   - Enhanced to read database preference
   - Syncs navbar toggle with database
   - Supports Auto mode (system preference)
   - Sends updates to database via API

### Database Fields:
- `theme` - CharField: 'light', 'dark', or 'auto'
- `messages_per_page` - IntegerField: 5-100, default 20

### API Endpoints:
- POST `/assistant/api/preferences/save/` - Save preferences via AJAX

---

## 🎉 Success Criteria

The preferences system is working correctly if:

✅ All 8 test sections pass without errors
✅ Theme changes apply immediately and persist
✅ Messages per page affects chat pagination
✅ Different users have isolated preferences
✅ UI is clean, professional, and intuitive
✅ No console errors during any operations
✅ Changes survive browser close/reopen
✅ Navbar theme toggle syncs with preferences

---

## 💡 Tips for Testing

1. **Use Browser DevTools**
   - Check Console for errors
   - Use Network tab to verify API calls
   - Inspect Application → Local Storage to see theme value

2. **Test in Incognito**
   - Ensures clean state
   - Verifies defaults for new users

3. **Use Different Browsers**
   - Confirms cross-browser compatibility
   - Tests server-side storage (not just localStorage)

4. **Create Test Data**
   - Create chat sessions with 50+ messages
   - Test pagination with various values

5. **Monitor Success**
   - Green success message should appear after save
   - Settings should apply immediately or on refresh
   - No red error messages

---

## 🚀 Ready to Test!

Start with **Test 1** and work through each section systematically. Check off each item as you verify it works correctly. If all tests pass, your preferences system is fully functional and production-ready!

Good luck! 🎯
