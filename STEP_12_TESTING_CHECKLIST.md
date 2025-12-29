# 🧪 Step 12 Testing Checklist

**Feature:** Role Switching Enhancements  
**Status:** Ready for Testing  
**Date:** December 29, 2025

---

## ✅ Pre-Testing Setup

- [ ] Django development server running
- [ ] Demo mode accessible at `/demo/`
- [ ] Browser developer tools open (F12)
- [ ] Mobile device or Chrome DevTools device emulation ready
- [ ] Console cleared for clean error tracking

---

## 🖥️ Desktop Testing (Chrome, Firefox, Safari, Edge)

### Test 1: Role Dropdown Display
**Steps:**
1. Navigate to `/demo/` and select "Team Mode"
2. Observe the demo banner at the top
3. Locate the "Viewing as: Admin" button

**Expected Results:**
- [ ] Role button displays current role (Admin initially)
- [ ] Button has purple gradient background
- [ ] Chevron down icon visible
- [ ] Button is clickable

**Pass/Fail:** ___________

---

### Test 2: Role Dropdown Menu
**Steps:**
1. Click the "Viewing as: Admin" button
2. Observe the dropdown menu

**Expected Results:**
- [ ] Dropdown appears below button
- [ ] Three role options visible: Alex Chen, Sam Rivera, Jordan Taylor
- [ ] Each has an icon (shield/user/eye)
- [ ] Each has a colored badge (Admin/Member/Viewer)
- [ ] Each has a description below name
- [ ] Active role (Admin) has green check mark
- [ ] Menu has white background with shadow

**Pass/Fail:** ___________

---

### Test 3: Role Badge Colors
**Steps:**
1. With dropdown open, inspect the three role badges

**Expected Results:**
- [ ] Admin badge: Yellow/amber gradient
- [ ] Member badge: Green gradient
- [ ] Viewer badge: Blue gradient
- [ ] All badges have box shadows
- [ ] Text is readable on all badges

**Pass/Fail:** ___________

---

### Test 4: Role Switch to Member
**Steps:**
1. Click "Sam Rivera (Member)" in dropdown
2. Observe the result

**Expected Results:**
- [ ] Dropdown closes immediately
- [ ] Success toast appears at top-right
- [ ] Toast has green gradient background
- [ ] Toast shows "Role Switched!" title
- [ ] Toast shows "Now viewing as Sam Rivera"
- [ ] Toast has user icon
- [ ] Toast auto-dismisses after 1.5 seconds
- [ ] Page reloads after toast dismisses
- [ ] After reload, banner shows "Viewing as: Member"

**Pass/Fail:** ___________

---

### Test 5: Role Switch to Viewer
**Steps:**
1. Click "Viewing as: Member" button
2. Select "Jordan Taylor (Viewer)"
3. Observe the result

**Expected Results:**
- [ ] Same success toast behavior as Test 4
- [ ] Toast shows "Now viewing as Jordan Taylor"
- [ ] Page reloads
- [ ] Banner shows "Viewing as: Viewer"

**Pass/Fail:** ___________

---

### Test 6: Role Switch Back to Admin
**Steps:**
1. Switch from Viewer back to Admin
2. Observe the result

**Expected Results:**
- [ ] Success toast shows "Now viewing as Alex Chen"
- [ ] Page reloads
- [ ] Banner shows "Viewing as: Admin"
- [ ] Full admin permissions restored

**Pass/Fail:** ___________

---

### Test 7: Dropdown Hover States
**Steps:**
1. Open role dropdown
2. Hover over each role option

**Expected Results:**
- [ ] Background changes to light gray on hover
- [ ] Smooth transition animation
- [ ] Cursor changes to pointer
- [ ] No layout shift

**Pass/Fail:** ___________

---

### Test 8: Click Outside Dropdown
**Steps:**
1. Open role dropdown
2. Click anywhere outside the dropdown

**Expected Results:**
- [ ] Dropdown closes
- [ ] No role switch occurs
- [ ] Page remains on same role

**Pass/Fail:** ___________

---

### Test 9: Error Handling (Network Failure)
**Steps:**
1. Open browser DevTools → Network tab
2. Set network to "Offline"
3. Try to switch roles
4. Observe error handling

**Expected Results:**
- [ ] Request fails
- [ ] Error toast appears (red gradient)
- [ ] Error message displayed
- [ ] Current role maintained
- [ ] Page does not reload
- [ ] User can retry

**Pass/Fail:** ___________

---

## 📱 Mobile Testing (iOS Safari & Android Chrome)

### Test 10: Mobile Demo Banner
**Steps:**
1. Open `/demo/` on mobile device or Chrome DevTools (375x667)
2. Select "Team Mode"
3. Observe demo banner

**Expected Results:**
- [ ] Banner is responsive
- [ ] Shows "Demo Mode" title
- [ ] Shows current role
- [ ] Has menu/hamburger icon
- [ ] Text is readable

**Pass/Fail:** ___________

---

### Test 11: Mobile Bottom Sheet Trigger
**Steps:**
1. Tap the hamburger/menu icon in banner
2. Tap "Change Role" button (or equivalent)

**Expected Results:**
- [ ] Bottom sheet slides up from bottom
- [ ] Dark overlay appears behind sheet
- [ ] Animation is smooth (no jank)
- [ ] Sheet covers ~70% of screen height

**Pass/Fail:** ___________

---

### Test 12: Mobile Bottom Sheet Content
**Steps:**
1. With bottom sheet open, observe the layout

**Expected Results:**
- [ ] Sheet has rounded top corners (20px)
- [ ] Grey handle bar at top (visual affordance)
- [ ] "Choose Your Role" header
- [ ] X close button in top-right
- [ ] Three large role cards
- [ ] Each card shows: icon, name, badge, description
- [ ] Active role is highlighted (border/background)
- [ ] Cards have adequate padding

**Pass/Fail:** ___________

---

### Test 13: Mobile Touch Targets
**Steps:**
1. With bottom sheet open, test touch targets

**Expected Results:**
- [ ] Each role card is at least 44px tall
- [ ] Cards have clear tap affordance (full card clickable)
- [ ] No accidental taps on adjacent elements
- [ ] Visual feedback on tap (highlight)

**Pass/Fail:** ___________

---

### Test 14: Mobile Role Switch
**Steps:**
1. Tap a different role card
2. Observe the result

**Expected Results:**
- [ ] Bottom sheet closes immediately
- [ ] Success toast appears
- [ ] Toast is positioned correctly (not hidden by keyboard)
- [ ] Page reloads
- [ ] New role is active

**Pass/Fail:** ___________

---

### Test 15: Mobile Swipe Gesture
**Steps:**
1. Open bottom sheet
2. Swipe down from middle of sheet
3. Observe the result

**Expected Results:**
- [ ] Sheet closes on swipe down
- [ ] Animation is smooth
- [ ] Overlay fades out
- [ ] Body scroll is restored
- [ ] No role switch occurs

**Pass/Fail:** ___________

---

### Test 16: Mobile Overlay Tap
**Steps:**
1. Open bottom sheet
2. Tap the dark overlay area (outside sheet)

**Expected Results:**
- [ ] Sheet closes
- [ ] No role switch occurs
- [ ] Smooth animation

**Pass/Fail:** ___________

---

### Test 17: Mobile X Button
**Steps:**
1. Open bottom sheet
2. Tap the X close button

**Expected Results:**
- [ ] Sheet closes
- [ ] Smooth animation
- [ ] No role switch

**Pass/Fail:** ___________

---

## 🔐 Permission Enforcement Testing

### Test 18: Viewer Permission Check
**Steps:**
1. Switch to Viewer role
2. Navigate to a demo board
3. Try to create a new task

**Expected Results:**
- [ ] "Create Task" button is hidden or disabled
- [ ] If button exists, clicking shows error
- [ ] Error message: "Viewers cannot create tasks"
- [ ] User understands limitation

**Pass/Fail:** ___________

---

### Test 19: Member Permission Check
**Steps:**
1. Switch to Member role
2. Navigate to a demo board
3. Try to edit board settings

**Expected Results:**
- [ ] "Board Settings" button is hidden or disabled
- [ ] If accessible, shows error message
- [ ] Error: "Members cannot edit board settings"
- [ ] Task editing still works

**Pass/Fail:** ___________

---

### Test 20: Admin Full Access
**Steps:**
1. Switch to Admin role
2. Navigate to a demo board
3. Test all features

**Expected Results:**
- [ ] All buttons/features are enabled
- [ ] No permission errors
- [ ] Can create, edit, delete everything

**Pass/Fail:** ___________

---

## 📊 Analytics Tracking Testing

### Test 21: Role Switch Event Tracking
**Steps:**
1. Open browser console
2. Switch roles multiple times
3. Check Django logs or database

**Expected Results:**
- [ ] Console shows AJAX requests to `/demo/switch-role/`
- [ ] Requests return 200 OK
- [ ] `DemoSession.current_role` updates in database
- [ ] `DemoSession.role_switches` count increments
- [ ] `DemoAnalytics` records created for each switch

**Pass/Fail:** ___________

---

## 🎨 Visual/CSS Testing

### Test 22: Badge Gradient Rendering
**Steps:**
1. Switch between all 3 roles
2. Inspect role badges in dropdown

**Expected Results:**
- [ ] Gradients render smoothly (no banding)
- [ ] Colors match design spec
- [ ] Box shadows are subtle
- [ ] Text contrast is sufficient (WCAG AA)

**Pass/Fail:** ___________

---

### Test 23: Toast Animation Smoothness
**Steps:**
1. Switch roles multiple times
2. Observe toast animations

**Expected Results:**
- [ ] Slide-in is smooth (no stuttering)
- [ ] Auto-dismiss timing is correct (1.5s)
- [ ] Slide-out is smooth
- [ ] No layout shift when toast appears

**Pass/Fail:** ___________

---

### Test 24: Bottom Sheet Animation
**Steps:**
1. On mobile, open/close bottom sheet multiple times

**Expected Results:**
- [ ] Slide-up animation is smooth
- [ ] Overlay fade-in is smooth
- [ ] Close animation is smooth
- [ ] No janky transitions

**Pass/Fail:** ___________

---

## 🔄 Edge Case Testing

### Test 25: Rapid Role Switching
**Steps:**
1. Switch roles rapidly (Admin → Member → Viewer → Admin)
2. Don't wait for page reload

**Expected Results:**
- [ ] Only last switch takes effect
- [ ] No race conditions
- [ ] No duplicate toasts
- [ ] Page reloads once with final role

**Pass/Fail:** ___________

---

### Test 26: Multiple Tabs
**Steps:**
1. Open demo in two browser tabs
2. Switch role in Tab 1
3. Observe Tab 2

**Expected Results:**
- [ ] Tab 2 still shows old role (session-based)
- [ ] Tab 2 can switch independently
- [ ] No conflicts
- [ ] Session updates correctly

**Pass/Fail:** ___________

---

### Test 27: Session Expiry During Role Switch
**Steps:**
1. Let demo session expire (48 hours - or mock it)
2. Try to switch roles

**Expected Results:**
- [ ] Error message shown
- [ ] User redirected to demo selection or login
- [ ] No crashes

**Pass/Fail:** ___________

---

### Test 28: Invalid Role Request
**Steps:**
1. Open browser console
2. Send POST to `/demo/switch-role/` with invalid role
3. Observe response

**Expected Results:**
- [ ] Server returns 400 error
- [ ] Error message: "Invalid role"
- [ ] Current role maintained
- [ ] No security issues

**Pass/Fail:** ___________

---

## ⚡ Performance Testing

### Test 29: Role Switch Response Time
**Steps:**
1. Open browser DevTools → Network tab
2. Switch roles
3. Measure response time

**Expected Results:**
- [ ] Response time < 200ms
- [ ] Toast appears < 400ms after click
- [ ] Page reload starts ~1.5s after click
- [ ] No blocking operations

**Pass/Fail:** ___________

---

### Test 30: Memory Leak Check
**Steps:**
1. Open Chrome DevTools → Performance tab
2. Switch roles 20 times
3. Take heap snapshot

**Expected Results:**
- [ ] Memory usage stays stable
- [ ] No detached DOM nodes
- [ ] Event listeners cleaned up
- [ ] No memory leaks

**Pass/Fail:** ___________

---

## 🌐 Cross-Browser Testing

### Test 31: Chrome
- [ ] All desktop tests pass
- [ ] All mobile tests pass (DevTools)
- [ ] CSS renders correctly
- [ ] Animations are smooth

**Pass/Fail:** ___________

---

### Test 32: Firefox
- [ ] All desktop tests pass
- [ ] CSS renders correctly
- [ ] Gradients display properly
- [ ] Animations work

**Pass/Fail:** ___________

---

### Test 33: Safari (macOS & iOS)
- [ ] All desktop tests pass (macOS)
- [ ] All mobile tests pass (iOS)
- [ ] Webkit-specific CSS works
- [ ] Touch events work on iOS

**Pass/Fail:** ___________

---

### Test 34: Edge
- [ ] All desktop tests pass
- [ ] CSS renders correctly
- [ ] No Chromium-specific issues

**Pass/Fail:** ___________

---

## 📝 Documentation Testing

### Test 35: Code Comments
**Steps:**
1. Review `demo_permissions.py`
2. Review JavaScript in `demo_banner.html`

**Expected Results:**
- [ ] Functions have docstrings
- [ ] Complex logic is commented
- [ ] Parameters are documented
- [ ] Return values are clear

**Pass/Fail:** ___________

---

### Test 36: Progress Documentation
**Steps:**
1. Review `DEMO_UX_IMPLEMENTATION_PROGRESS.md`
2. Check Step 12 section

**Expected Results:**
- [ ] Step 12 marked complete
- [ ] Implementation details documented
- [ ] Files listed correctly
- [ ] Next steps clear

**Pass/Fail:** ___________

---

## 🎯 Final Checklist

### Overall Step 12 Completion
- [ ] All 36 tests passed
- [ ] No critical bugs found
- [ ] Minor bugs documented (if any)
- [ ] Permission system works correctly
- [ ] Desktop UI is polished
- [ ] Mobile UI is polished
- [ ] Analytics tracking works
- [ ] Performance is acceptable
- [ ] Documentation is complete

### Ready for Step 13?
- [ ] YES - Proceed to comprehensive testing phase
- [ ] NO - Address failing tests first

---

## 📊 Test Results Summary

**Date Tested:** ___________  
**Tester:** ___________  
**Environment:** ___________

**Total Tests:** 36  
**Passed:** _____ / 36  
**Failed:** _____ / 36  
**Skipped:** _____ / 36

**Critical Bugs Found:** _____  
**Minor Bugs Found:** _____  
**Enhancements Suggested:** _____

**Overall Status:**
- [ ] Ready for Production
- [ ] Needs Minor Fixes
- [ ] Needs Major Fixes

**Next Action:** ___________

---

## 📋 Bug Report Template

**Bug #:** _____  
**Severity:** Critical / Major / Minor / Cosmetic  
**Test #:** _____  
**Description:** _____  
**Steps to Reproduce:** _____  
**Expected Result:** _____  
**Actual Result:** _____  
**Screenshot/Video:** _____  
**Browser/Device:** _____  
**Proposed Fix:** _____

---

**Testing Completed by:** ___________  
**Date:** ___________  
**Signature:** ___________
