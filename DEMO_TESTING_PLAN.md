# 🧪 Demo UX Testing Plan - Step 13
**Date:** December 29, 2025  
**Status:** In Progress  
**Objective:** Comprehensive testing and bug fixes for Steps 1-12

---

## 📋 Testing Overview

This document provides a systematic testing plan for all implemented demo features. Each section includes:
- ✅ **Test cases** - What to test
- 🎯 **Success criteria** - How to verify it works
- 🐛 **Common issues** - What to look for
- 📝 **Testing script** - Manual steps to follow

---

## 🔍 Section 1: Pre-Testing Verification

### **1.1 Database & Models Verification**

**Automated Verification Script:**
Run before starting manual tests to ensure foundation is solid.

**What to Check:**
- ✅ All migrations applied
- ✅ Demo organization exists with correct flags
- ✅ 3 demo personas exist (Alex Chen, Sam Rivera, Jordan Taylor)
- ✅ 3 official demo boards exist
- ✅ 120 demo tasks distributed correctly
- ✅ DemoSession, DemoAnalytics, DemoConversion models exist
- ✅ All model fields present (is_demo, is_official_demo_board, created_by_session)

**Script to Create:** `verify_demo_foundation.py`

---

## 🧭 Section 2: Demo Mode Selection Testing

### **2.1 Desktop - Mode Selection Screen**

**URL to Test:** `/demo/start/`

**Test Case 1: Solo Mode Selection**
1. Navigate to `/demo/start/`
2. Click "Start Solo Exploration" button
3. **Verify:**
   - ✅ Redirects to demo dashboard
   - ✅ Session variable `demo_mode = 'solo'`
   - ✅ Session variable `demo_role = 'admin'`
   - ✅ DemoSession created in database
   - ✅ DemoAnalytics event: `demo_started` with `mode: solo`, `selection_method: selected`
   - ✅ Demo banner shows "Alex Chen (Admin)"

**Test Case 2: Team Mode Selection**
1. Navigate to `/demo/start/`
2. Click "Try Team Mode" button
3. **Verify:**
   - ✅ Redirects to demo dashboard
   - ✅ Session variable `demo_mode = 'team'`
   - ✅ Session variable `demo_role = 'admin'`
   - ✅ DemoSession created with `demo_mode = 'team'`
   - ✅ DemoAnalytics event: `demo_started` with `mode: team`, `selection_method: selected`
   - ✅ Demo banner shows role switcher dropdown

**Test Case 3: Skip Selection**
1. Navigate to `/demo/start/`
2. Click "Skip selection →" link
3. **Verify:**
   - ✅ Redirects to demo dashboard
   - ✅ Defaults to Solo mode (`demo_mode = 'solo'`)
   - ✅ Session variable `demo_role = 'admin'`
   - ✅ DemoAnalytics event: `demo_started` with `selection_method: skipped`
   - ✅ Brief tooltip shows: "✨ Entering Solo mode..."

**Test Case 4: Direct Dashboard Access**
1. Navigate directly to `/demo/dashboard/` (bypassing selection)
2. **Verify:**
   - ✅ Redirects to `/demo/start/` (selection screen)
   - ✅ User must choose mode before accessing demo

**Test Case 5: Page Refresh**
1. Select mode, then refresh page
2. **Verify:**
   - ✅ Stays on demo dashboard (doesn't reset session)
   - ✅ Session persists

**Common Issues:**
- 🐛 Session not persisting across requests
- 🐛 DemoSession creation fails silently
- 🐛 Redirect loop between selection and dashboard

---

### **2.2 Mobile - Mode Selection Screen**

**Test Case 1: Mobile Layout**
1. Open `/demo/start/` on mobile device (or Chrome DevTools mobile emulation)
2. **Verify:**
   - ✅ Modal is responsive (90% width on mobile)
   - ✅ Buttons are touch-friendly (minimum 44x44px)
   - ✅ Text is readable without zoom
   - ✅ All content fits without horizontal scroll
   - ✅ Icons and layout adjust for small screen

**Test Case 2: Touch Interactions**
1. Tap "Start Solo Exploration" button
2. **Verify:**
   - ✅ Button responds to touch (no delay)
   - ✅ Visual feedback on tap
   - ✅ Selection works correctly

---

## 🎯 Section 3: Demo Banner Testing

### **3.1 Desktop - Banner Display**

**Test Case 1: Banner Visibility**
1. Enter demo mode (any method)
2. Navigate to demo dashboard
3. **Verify:**
   - ✅ Banner is visible at top of page
   - ✅ Banner shows "🎯 Demo Mode Active"
   - ✅ Current persona name displayed (e.g., "Alex Chen (Admin)")
   - ✅ Banner is sticky (stays visible when scrolling)
   - ✅ Visual distinction (colored background - yellow/gold)
   - ✅ All action buttons visible: Reset, Switch Role, Create Account, Exit

**Test Case 2: Banner on Board Detail Page**
1. From demo dashboard, click into a board
2. **Verify:**
   - ✅ Banner still visible on board detail page
   - ✅ All information correct
   - ✅ Actions still functional

**Test Case 3: Banner Context Data**
1. Check banner displays correct info
2. **Verify:**
   - ✅ Role badge shows correct color (Admin=yellow, Member=green, Viewer=blue)
   - ✅ Time remaining displayed (if expiry warning active)
   - ✅ "All changes are temporary" message shown

---

### **3.2 Mobile - Banner Display**

**Test Case 1: Collapsed State**
1. Open demo on mobile
2. **Verify:**
   - ✅ Banner is collapsed by default (shows minimal info)
   - ✅ Shows: "🎯 Demo Mode" and persona name
   - ✅ Hamburger menu visible (⋮ Menu)

**Test Case 2: Expanded State**
1. Tap hamburger menu (⋮)
2. **Verify:**
   - ✅ Bottom sheet opens with all actions
   - ✅ Actions listed: Reset Demo, Create Account, Switch Role, Exit Demo
   - ✅ Touch-friendly buttons (44x44px minimum)
   - ✅ Backdrop dims background

**Test Case 3: Dismiss Bottom Sheet**
1. Open bottom sheet, then tap backdrop
2. **Verify:**
   - ✅ Bottom sheet closes
   - ✅ Banner returns to collapsed state

**Test Case 4: Swipe Gesture**
1. Swipe banner down
2. **Verify:**
   - ✅ Banner temporarily hides
   - ✅ Reappears on scroll (sticky behavior)

---

## 🔄 Section 4: Role Switching Testing (Team Mode)

### **4.1 Desktop - Role Switcher**

**Test Case 1: Switch to Member Role**
1. Enter Team demo mode
2. Click role dropdown (shows "Alex Chen (Admin)")
3. Click "Sam Rivera (Member)"
4. **Verify:**
   - ✅ Success toast displays: "Switched to Sam Rivera (Member)"
   - ✅ Banner updates to show "Sam Rivera (Member)"
   - ✅ Page reloads with new role
   - ✅ Session variable `demo_role = 'member'`
   - ✅ DemoAnalytics event: `role_switched` with `from: admin`, `to: member`
   - ✅ Member permissions enforced (limited delete, no settings access)

**Test Case 2: Switch to Viewer Role**
1. From any role, switch to "Jordan Taylor (Viewer)"
2. **Verify:**
   - ✅ Success toast displays
   - ✅ Banner updates to show "Jordan Taylor (Viewer)"
   - ✅ Viewer permissions enforced (read-only, can comment)
   - ✅ Create/Edit/Delete buttons hidden or disabled
   - ✅ Settings page inaccessible (shows error or redirects)

**Test Case 3: Switch Back to Admin**
1. From Member or Viewer, switch back to Admin
2. **Verify:**
   - ✅ Full permissions restored
   - ✅ All features accessible again

**Test Case 4: Permission Enforcement**
1. Switch to Member role
2. Try to delete a high-priority task
3. **Verify:**
   - ✅ Approval required popup appears (or action blocked)
   - ✅ Task not deleted immediately
   - ✅ User understands restriction

4. Switch to Viewer role
5. Try to create a new task
6. **Verify:**
   - ✅ Create button disabled or shows error
   - ✅ Clear message: "Viewers cannot create tasks"

**Test Case 5: Error Handling**
1. Disconnect network, then try to switch role
2. **Verify:**
   - ✅ Error toast displays: "Failed to switch role. Please try again."
   - ✅ User stays in current role
   - ✅ No session corruption

---

### **4.2 Mobile - Role Switcher**

**Test Case 1: Open Role Selector**
1. Enter Team demo on mobile
2. Tap role name in banner
3. **Verify:**
   - ✅ Bottom sheet modal opens
   - ✅ Shows all 3 roles as touch-friendly cards
   - ✅ Current role has check mark
   - ✅ Role badges visible (Admin/Member/Viewer)
   - ✅ Role descriptions shown under each name

**Test Case 2: Switch Role on Mobile**
1. Tap "Sam Rivera (Member)" card
2. **Verify:**
   - ✅ Success toast displays (mobile-sized)
   - ✅ Bottom sheet closes
   - ✅ Banner updates
   - ✅ Page reloads
   - ✅ Permissions enforced

**Test Case 3: Swipe to Dismiss**
1. Open role selector bottom sheet
2. Swipe down on sheet
3. **Verify:**
   - ✅ Sheet dismisses
   - ✅ No role change occurs

---

## ⏱️ Section 5: Session Management Testing

### **5.1 Session Initialization**

**Test Case 1: New Session**
1. Enter demo mode for the first time
2. **Verify:**
   - ✅ DemoSession created with unique session_id
   - ✅ `created_at` timestamp correct
   - ✅ `expires_at` = created_at + 48 hours
   - ✅ `features_explored = 0`
   - ✅ `aha_moments = 0`
   - ✅ Session variables initialized

**Test Case 2: Session Persistence**
1. Enter demo, navigate to different pages
2. **Verify:**
   - ✅ Session persists across page loads
   - ✅ Session data accessible on all demo pages
   - ✅ No duplicate DemoSession records created

---

### **5.2 Expiry Warnings**

**Test Case 1: 4-Hour Warning** (Requires time manipulation or wait)
1. Set session expiry to 4 hours from now (modify DemoSession in DB)
2. Load demo page
3. **Verify:**
   - ✅ Info-level warning banner displays
   - ✅ Message: "⏰ Demo session expires in 4h 0m"
   - ✅ Shows buttons: "Extend Session" and "Create Account"
   - ✅ Banner is dismissible

**Test Case 2: 1-Hour Warning**
1. Set session expiry to 1 hour from now
2. Load demo page
3. **Verify:**
   - ✅ Warning-level alert displays (orange/yellow)
   - ✅ Message more urgent
   - ✅ "Extend Session" CTA more prominent

**Test Case 3: 15-Minute Critical Warning**
1. Set session expiry to 15 minutes from now
2. Load demo page
3. **Verify:**
   - ✅ Critical alert displays (red)
   - ✅ Animated slide-down effect
   - ✅ Urgent messaging
   - ✅ Strong CTA to create account

**Test Case 4: Session Expired**
1. Set session expiry to past time
2. Load demo page
3. **Verify:**
   - ✅ Redirects to `/demo/start/` (mode selection)
   - ✅ Message: "Your demo session has expired. Start a new demo?"
   - ✅ User can start fresh demo

---

### **5.3 Session Extension**

**Test Case 1: First Extension**
1. Click "Extend Session" button
2. **Verify:**
   - ✅ AJAX request to `/demo/extend/`
   - ✅ Success message: "Session extended by 1 hour"
   - ✅ DemoSession.expires_at updated (+1 hour)
   - ✅ DemoSession.extensions_count incremented
   - ✅ Warning banner updates with new expiry time
   - ✅ DemoAnalytics event: `session_extended`

**Test Case 2: Multiple Extensions**
1. Extend session 3 times
2. **Verify:**
   - ✅ First 3 extensions work
   - ✅ On 4th attempt, shows message: "Maximum extensions reached. Create account to continue."
   - ✅ Extensions_count = 3 (limit enforced)

**Test Case 3: Extension Error**
1. Disconnect network, try to extend
2. **Verify:**
   - ✅ Error message: "Failed to extend session. Please try again."
   - ✅ Session not corrupted
   - ✅ User can retry

---

### **5.4 Session Cleanup**

**Test Case 1: Cleanup Command Dry Run**
1. Create expired demo sessions (set expires_at to past)
2. Run: `python manage.py cleanup_demo_sessions --dry-run`
3. **Verify:**
   - ✅ Lists expired sessions to be deleted
   - ✅ Shows session-created content to be removed
   - ✅ No actual deletion occurs

**Test Case 2: Cleanup Execution**
1. Run: `python manage.py cleanup_demo_sessions`
2. **Verify:**
   - ✅ Expired DemoSession records deleted
   - ✅ Session-created tasks deleted (where created_by_session matches)
   - ✅ Session-created boards deleted
   - ✅ Official demo boards NOT deleted (is_official_demo_board=True)
   - ✅ Console output shows deletion counts

**Test Case 3: Cleanup with Analytics Preservation**
1. Run: `python manage.py cleanup_demo_sessions --keep-analytics`
2. **Verify:**
   - ✅ Session and content deleted
   - ✅ DemoAnalytics records preserved for reporting

---

## 🔄 Section 6: Reset Demo Testing

### **6.1 Desktop - Reset Functionality**

**Test Case 1: Successful Reset**
1. Enter demo, create 2-3 new tasks
2. Click "🔄 Reset Demo" button in banner
3. **Verify:**
   - ✅ Confirmation modal appears
   - ✅ Modal lists what will be reset
   - ✅ Shows "Cancel" and "Yes, Reset Demo" buttons

4. Click "Yes, Reset Demo"
5. **Verify:**
   - ✅ AJAX request to reset endpoint
   - ✅ User-created tasks deleted
   - ✅ User-created boards deleted (if any)
   - ✅ Official demo boards restored to default state
   - ✅ Success message: "✅ Demo reset! You're back to a clean workspace"
   - ✅ Page reloads with fresh data
   - ✅ Session.reset_count incremented
   - ✅ DemoAnalytics event: `demo_reset`

**Test Case 2: Reset Cancellation**
1. Click "🔄 Reset Demo"
2. Click "Cancel" in confirmation modal
3. **Verify:**
   - ✅ Modal closes
   - ✅ No reset occurs
   - ✅ User data intact

**Test Case 3: Reset with Error**
1. Disconnect network
2. Attempt reset
3. **Verify:**
   - ✅ Error message: "Failed to reset demo. Retrying..."
   - ✅ Automatic retry (3 attempts with exponential backoff)
   - ✅ If all retries fail: "Unable to reset. Please refresh the page."
   - ✅ Error logged server-side
   - ✅ Session not corrupted

**Test Case 4: Partial Reset Failure**
1. Simulate server error during reset (e.g., database lock)
2. **Verify:**
   - ✅ Clear error message to user
   - ✅ Fallback option: "Try manual refresh"
   - ✅ Session remains valid
   - ✅ User can retry reset

**Test Case 5: Multiple Resets**
1. Reset demo 3 times in succession
2. **Verify:**
   - ✅ Each reset works correctly
   - ✅ Reset count tracks accurately
   - ✅ Official demo data always restored correctly
   - ✅ No data corruption

---

### **6.2 Mobile - Reset Functionality**

**Test Case 1: Reset on Mobile**
1. Open demo on mobile
2. Tap hamburger menu → "Reset Demo"
3. **Verify:**
   - ✅ Full-screen modal or bottom sheet confirmation
   - ✅ Touch-friendly buttons
   - ✅ Reset works same as desktop
   - ✅ Success message displays properly

---

## ✨ Section 7: Aha Moment Testing

### **7.1 AI Suggestion Aha Moment**

**Test Case 1: AI Suggestion Accepted**
1. Navigate to board with AI suggestions
2. Click "Accept" on an AI-suggested task assignment
3. **Verify:**
   - ✅ Aha celebration modal appears within 2 seconds
   - ✅ Shows: 🤖 icon, "AI-Powered Productivity!" title
   - ✅ Description explains value
   - ✅ CTA button: "See More AI Features"
   - ✅ Confetti animation plays
   - ✅ Modal auto-dismisses after 6 seconds
   - ✅ Click backdrop to dismiss early (works)
   - ✅ DemoAnalytics event: `aha_moment` with `moment_type: ai_suggestion`
   - ✅ Session.aha_moments incremented
   - ✅ Session.aha_moments_list includes 'ai_suggestion'

**Test Case 2: Duplicate Prevention**
1. Accept another AI suggestion
2. **Verify:**
   - ✅ No second celebration (already shown once)
   - ✅ SessionStorage prevents duplicate

---

### **7.2 Burndown Chart Aha Moment**

**Test Case 1: Burndown View**
1. Navigate to board with burndown chart
2. View burndown chart for at least 10 seconds
3. **Verify:**
   - ✅ After 10 seconds, aha celebration triggers
   - ✅ Shows: 📈 icon, "Data-Driven Insights!" title
   - ✅ Description explains forecasting value
   - ✅ DemoAnalytics event tracked

**Test Case 2: Quick View (< 10 seconds)**
1. View burndown chart for 5 seconds, then navigate away
2. **Verify:**
   - ✅ No aha moment triggered (timer not reached)
   - ✅ Timer resets if user returns to chart later

---

### **7.3 RBAC Workflow Aha Moment**

**Test Case 1: Role Switch in Team Mode**
1. Enter Team demo
2. Switch from Admin to Member role
3. **Verify:**
   - ✅ Aha celebration triggers
   - ✅ Shows: 🛡️ icon, "Enterprise Security Discovery!" title
   - ✅ Description explains RBAC value

---

### **7.4 Time Tracking Aha Moment**

**Test Case 1: Start Timer**
1. Click "Start Timer" on a task
2. **Verify:**
   - ✅ Aha celebration triggers
   - ✅ Shows: ⏱️ icon, "Time Mastery Unlocked!" title

---

### **7.5 Other Aha Moments**

**Test remaining 4 aha moments:**
- ✅ Dependency created (🔗 Smart Task Management)
- ✅ Gantt chart viewed >3 seconds (📊 Project Timeline Mastery)
- ✅ Skill gap viewed >5 seconds (👥 Team Optimization Discovery)
- ✅ Conflict detected (⚠️ Conflict Prevention Feature)

**For each:**
1. Trigger the specific action
2. **Verify:**
   - ✅ Correct icon, title, description
   - ✅ Confetti animation
   - ✅ Auto-dismiss works
   - ✅ Analytics tracked
   - ✅ No duplicates

---

### **7.6 Mobile Aha Moments**

**Test Case 1: Mobile Layout**
1. Trigger any aha moment on mobile
2. **Verify:**
   - ✅ Modal is responsive (90% width)
   - ✅ Text readable without zoom
   - ✅ CTA button touch-friendly
   - ✅ Animation smooth on mobile

---

## 💡 Section 8: Conversion Nudge Testing

### **8.1 Soft Nudge (Time-Based)**

**Test Case 1: 3-Minute Trigger**
1. Enter demo and wait 3 minutes (or manipulate session.demo_started_at)
2. **Verify:**
   - ✅ Soft nudge toast appears bottom-right (desktop)
   - ✅ Shows: "💡 Like what you see?"
   - ✅ Has "Create free account" and "Dismiss" buttons
   - ✅ Auto-dismisses after 10 seconds
   - ✅ DemoAnalytics event: `nudge_shown` with `nudge_type: soft`

**Test Case 2: 3-Features Trigger**
1. Perform 3 meaningful interactions (e.g., create task, view burndown, log time)
2. **Verify:**
   - ✅ Soft nudge appears
   - ✅ Timing logic works (3 features explored)

**Test Case 3: Dismissal**
1. Click "Dismiss" on soft nudge
2. **Verify:**
   - ✅ Nudge disappears
   - ✅ DemoAnalytics event: `nudge_dismissed` with `nudge_type: soft`
   - ✅ Cooldown period starts (2 minutes before next nudge)

---

### **8.2 Medium Nudge**

**Test Case 1: 5-Minute Trigger**
1. Wait 5 minutes in demo
2. **Verify:**
   - ✅ Medium nudge modal appears (soft overlay)
   - ✅ Shows: "🎯 You've explored X features!"
   - ✅ Lists benefits (unlimited projects, all features, free)
   - ✅ Has "Start Free Account" and "Keep Exploring" buttons
   - ✅ DemoAnalytics event: `nudge_shown` with `nudge_type: medium`

**Test Case 2: Aha Moment Trigger**
1. Experience 1 aha moment
2. Wait 30 seconds
3. **Verify:**
   - ✅ Medium nudge appears
   - ✅ Message references aha moment

---

### **8.3 Peak Nudge**

**Test Case 1: Aha-Triggered Nudge**
1. Trigger any aha moment
2. Wait 3 seconds after aha celebration
3. **Verify:**
   - ✅ Peak nudge appears (contextual modal)
   - ✅ Shows: "🚀 Imagine this for your real projects!"
   - ✅ Lists unlock benefits
   - ✅ Strong CTA: "Start for Free"
   - ✅ Appears near location of aha moment (contextual)
   - ✅ DemoAnalytics event: `nudge_shown` with `nudge_type: peak`

**Test Case 2: Multiple Peak Nudges**
1. Trigger 2 different aha moments
2. **Verify:**
   - ✅ Peak nudge can show for each aha type (unique per aha)
   - ✅ Not frequency capped same way as other nudges

---

### **8.4 Exit Intent Nudge (Desktop Only)**

**Test Case 1: Mouse Exit Detection**
1. Spend 2+ minutes in demo
2. Move mouse cursor to browser address bar (simulate exit intent)
3. **Verify:**
   - ✅ Exit intent nudge appears (prominent modal)
   - ✅ Shows: "👋 Before you go..."
   - ✅ Lists save progress benefits
   - ✅ Shows time commitment: "Takes just 30 seconds"
   - ✅ Risk removal: "no credit card required"
   - ✅ Has "Create Account (Free)" and "Continue Demo" buttons
   - ✅ Only shows once per session
   - ✅ DemoAnalytics event: `nudge_shown` with `nudge_type: exit_intent`

**Test Case 2: Mobile (No Exit Intent)**
1. Test on mobile device
2. **Verify:**
   - ✅ Exit intent detection NOT active on mobile
   - ✅ Medium nudge shown at 7-8 minutes instead

---

### **8.5 Frequency Capping**

**Test Case 1: Maximum 3 Nudges**
1. Trigger soft nudge (dismiss)
2. Trigger medium nudge (dismiss)
3. Trigger peak nudge (dismiss)
4. Try to trigger another nudge
5. **Verify:**
   - ✅ No 4th nudge appears
   - ✅ Frequency cap enforced (max 3 per session)

**Test Case 2: Cooldown Periods**
1. Dismiss soft nudge
2. Wait less than 2 minutes
3. Try to trigger medium nudge
4. **Verify:**
   - ✅ Medium nudge doesn't show yet (cooldown active)

---

### **8.6 Mobile Nudges**

**Test Case 1: Soft Nudge on Mobile**
1. Trigger soft nudge on mobile
2. **Verify:**
   - ✅ Appears as snackbar (bottom of screen)
   - ✅ Touch-friendly buttons
   - ✅ Auto-dismisses after 5 seconds (shorter than desktop)

**Test Case 2: Medium Nudge on Mobile**
1. Trigger medium nudge on mobile
2. **Verify:**
   - ✅ Appears as bottom sheet
   - ✅ Swipe-to-dismiss works
   - ✅ Layout adapted for small screen

---

## 📊 Section 9: Analytics Tracking Testing

### **9.1 Server-Side Tracking**

**Test Case 1: DemoSession Creation**
1. Start new demo
2. Query database: `DemoSession.objects.filter(session_id=<session_key>)`
3. **Verify:**
   - ✅ DemoSession record exists
   - ✅ Correct demo_mode ('solo' or 'team')
   - ✅ Correct demo_role ('admin', 'member', 'viewer')
   - ✅ created_at timestamp accurate
   - ✅ expires_at = created_at + 48 hours
   - ✅ features_explored = 0 initially
   - ✅ aha_moments = 0 initially

**Test Case 2: Event Tracking**
1. Perform various actions (role switch, aha moment, nudge shown)
2. Query: `DemoAnalytics.objects.filter(session_id=<session_key>)`
3. **Verify:**
   - ✅ Events logged with correct event_type
   - ✅ event_data JSON contains relevant info
   - ✅ Timestamps accurate
   - ✅ device_type detected correctly

**Test Case 3: Ad-Blocker Immunity**
1. Enable ad-blocker extension (uBlock Origin, AdBlock Plus)
2. Perform demo actions
3. Query database
4. **Verify:**
   - ✅ Server-side events still tracked (immune to blockers)
   - ✅ 100% coverage for critical events

---

### **9.2 Client-Side Tracking (if GA4 integrated)**

**Test Case 1: GA4 Events**
1. Open browser console with GA4 debugger
2. Perform demo actions
3. **Verify:**
   - ✅ GA4 events fire (when not blocked)
   - ✅ Events include custom parameters
   - ✅ User properties set correctly

**Test Case 2: Client-Side Failure**
1. Enable ad-blocker
2. Perform demo actions
3. **Verify:**
   - ✅ Client-side tracking fails gracefully
   - ✅ No JavaScript errors in console
   - ✅ Server-side tracking still works
   - ✅ User experience unaffected

---

### **9.3 Hybrid Coverage Verification**

**Test Case 1: Coverage Report**
1. Run multiple demo sessions (some with blockers, some without)
2. Query database for tracking coverage
3. **Verify:**
   - ✅ 100% of sessions have server-side tracking
   - ✅ ~70% of sessions have client-side tracking
   - ✅ Overall hybrid coverage: 85%+ (as targeted)

---

## 🌐 Section 10: Cross-Browser Testing

### **10.1 Desktop Browsers**

**Browsers to Test:**
- Google Chrome (latest)
- Mozilla Firefox (latest)
- Safari (latest, macOS only)
- Microsoft Edge (latest)

**For Each Browser, Test:**
1. Demo mode selection
2. Banner display and stickiness
3. Role switching
4. Reset functionality
5. Aha moment celebrations
6. Conversion nudges
7. Session expiry warnings
8. All animations and transitions

**Common Issues to Watch:**
- 🐛 CSS inconsistencies (especially Safari)
- 🐛 JavaScript errors (check console)
- 🐛 Fetch API compatibility
- 🐛 SessionStorage/LocalStorage issues

---

### **10.2 Mobile Browsers**

**Devices/Browsers to Test:**
- iOS Safari (iPhone)
- Android Chrome (Samsung/Pixel)

**Chrome DevTools Emulation:**
- iPhone 12/13/14 Pro
- Samsung Galaxy S21/S22
- iPad Pro

**For Each Device, Test:**
1. Mode selection responsiveness
2. Banner collapse/expand
3. Bottom sheets (role switcher, actions menu)
4. Touch interactions (taps, swipes)
5. Aha moment mobile layout
6. Nudge mobile adaptations
7. Reset confirmation modal
8. Scroll behavior

---

## 🐛 Section 11: Edge Case & Error Testing

### **11.1 Session Edge Cases**

**Test Case 1: Multiple Tabs**
1. Open demo in 2 browser tabs
2. Perform actions in both tabs
3. **Verify:**
   - ✅ Session state syncs between tabs (or handles gracefully)
   - ✅ No duplicate DemoSession records
   - ✅ Role switching in one tab reflects in other (after refresh)

**Test Case 2: Browser Back Button**
1. Navigate through demo (selection → dashboard → board detail)
2. Click browser back button multiple times
3. **Verify:**
   - ✅ Navigation works correctly
   - ✅ No redirect loops
   - ✅ Session persists
   - ✅ Banner state correct on each page

**Test Case 3: Browser Refresh**
1. Perform actions in demo
2. Hard refresh page (Ctrl+F5)
3. **Verify:**
   - ✅ Session persists
   - ✅ Demo state maintained
   - ✅ Analytics not duplicated

**Test Case 4: Session Timeout (Browser Closed)**
1. Enter demo, then close browser
2. Reopen browser and navigate back to demo
3. **Verify:**
   - ✅ Session may be expired (depends on cookie settings)
   - ✅ Redirects to selection screen gracefully
   - ✅ User can start fresh demo

---

### **11.2 Network Error Scenarios**

**Test Case 1: Slow Network**
1. Throttle network to "Slow 3G" (Chrome DevTools)
2. Perform demo actions (role switch, reset)
3. **Verify:**
   - ✅ Loading indicators show
   - ✅ Actions complete successfully (just slower)
   - ✅ No timeouts or errors

**Test Case 2: Network Interruption**
1. Start action (e.g., reset), then disconnect network mid-request
2. **Verify:**
   - ✅ Error message displays
   - ✅ Retry logic attempts reconnection
   - ✅ User can retry after network restored

**Test Case 3: Server Error (500)**
1. Simulate server error (modify view to raise exception)
2. **Verify:**
   - ✅ User-friendly error message (not stack trace)
   - ✅ Fallback options provided
   - ✅ Error logged server-side

---

### **11.3 Concurrent Request Testing**

**Test Case 1: Rapid Action Clicks**
1. Rapidly click "Reset Demo" button 10 times
2. **Verify:**
   - ✅ Only one reset executes (duplicate prevention)
   - ✅ No race conditions
   - ✅ Button disabled during processing

**Test Case 2: Concurrent Role Switches**
1. Click role switcher, immediately click another role
2. **Verify:**
   - ✅ Only one switch processes
   - ✅ Final role is correct
   - ✅ No session corruption

---

## 📋 Section 12: Performance Testing

### **12.1 Page Load Times**

**Test Case 1: Initial Load**
1. Clear cache, navigate to `/demo/start/`
2. Measure load time (Chrome DevTools Performance tab)
3. **Verify:**
   - ✅ Page loads in < 2 seconds
   - ✅ No render-blocking resources
   - ✅ Images optimized

**Test Case 2: Demo Dashboard Load**
1. Navigate to demo dashboard with 120 tasks
2. Measure load time
3. **Verify:**
   - ✅ Dashboard loads in < 3 seconds
   - ✅ Tasks render efficiently
   - ✅ No janky scrolling

---

### **12.2 Database Query Optimization**

**Test Case 1: Query Count**
1. Enable Django Debug Toolbar
2. Load demo dashboard
3. **Verify:**
   - ✅ Reasonable query count (< 50 queries)
   - ✅ No N+1 query issues
   - ✅ Proper use of select_related/prefetch_related

---

### **12.3 Reset Operation Speed**

**Test Case 1: Reset Time**
1. Create 50 user tasks
2. Time reset operation
3. **Verify:**
   - ✅ Reset completes in < 5 seconds
   - ✅ Efficient deletion queries
   - ✅ No database locks

---

## ✅ Section 13: Testing Checklist Summary

### **Critical Path (Must Pass Before Launch):**
- [ ] Demo mode selection works (Solo, Team, Skip)
- [ ] Demo banner displays correctly (desktop + mobile)
- [ ] Role switching functional (Team mode)
- [ ] Reset demo works with error handling
- [ ] Session management and expiry warnings work
- [ ] Aha moments trigger and celebrate correctly
- [ ] Conversion nudges show at right times
- [ ] Analytics tracking (server-side) functional
- [ ] No critical bugs in Chrome/Firefox/Safari
- [ ] Mobile experience usable on iOS/Android

### **High Priority (Should Pass Before Launch):**
- [ ] All 8 aha moments tested
- [ ] All 4 nudge types tested
- [ ] Frequency capping enforced
- [ ] Permission enforcement (Admin/Member/Viewer)
- [ ] Error handling for all major actions
- [ ] Cross-browser testing complete
- [ ] Edge cases handled gracefully
- [ ] Performance benchmarks met

### **Medium Priority (Can Fix Post-Launch):**
- [ ] Minor UI inconsistencies
- [ ] Mobile swipe gestures
- [ ] Advanced analytics (GA4 integration)
- [ ] A/B testing framework
- [ ] Optimization based on data

---

## 🐛 Bug Reporting Template

**For each bug found, document:**

**Bug ID:** BUG-001  
**Severity:** Critical / High / Medium / Low  
**Component:** (e.g., Demo Banner, Role Switching, Reset, etc.)  
**Browser/Device:** (e.g., Chrome 120 / iPhone 14 Safari)  
**Steps to Reproduce:**
1. Step 1
2. Step 2
3. Step 3

**Expected Behavior:** What should happen  
**Actual Behavior:** What actually happens  
**Screenshot/Video:** (if applicable)  
**Console Errors:** (copy from browser console)  
**Server Logs:** (copy from Django logs)  

**Priority:** (1-5, 1 = fix immediately, 5 = nice to have)  
**Assigned To:** (team member or yourself)  
**Status:** Open / In Progress / Fixed / Verified  

---

## 📝 Testing Progress Tracker

**Date Started:** _________  
**Date Completed:** _________  
**Total Bugs Found:** _________  
**Critical Bugs Fixed:** _________  
**High Priority Bugs Fixed:** _________  
**Medium/Low Bugs:** _________ (can defer)

**Sign-off:**
- [ ] All critical tests passed
- [ ] All high priority tests passed
- [ ] Bug report created for remaining issues
- [ ] Ready for production deployment

**Tested By:** _________  
**Date:** _________  
**Signature:** _________

---

**End of Testing Plan**

*This comprehensive testing plan ensures all implemented features (Steps 1-12) are thoroughly validated before production deployment. Follow each section systematically, document all issues, and prioritize fixes based on severity.*
