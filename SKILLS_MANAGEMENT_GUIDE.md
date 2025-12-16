# How to Add and Manage Skills for Real Users

## Summary of Changes

I've updated the system so users can now add and manage their skills through their profile page.

## What Was Done

### 1. Updated the Profile Form
- Added a **Skills** field where users can enter their skills separated by commas
- Added a **Weekly Working Hours** field to set capacity
- Skills are stored in the database and used by the AI for better task matching

### 2. Added Skills to Existing Real Users
The following users now have skills:

| User | Skills |
|------|--------|
| user1 | DevOps, AWS, Docker, CI/CD |
| user2 | Data Analysis, SQL, Python, Visualization |
| user3 | Full-Stack Development, Node.js, MongoDB, API Development |
| user4 | Python, JavaScript, React, Django |
| user5 | Project Management, Agile, Scrum, Documentation |
| user6 | UI Design, UX Research, Figma, CSS |
| user7 | DevOps, AWS, Docker, CI/CD |
| user8 | Data Analysis, SQL, Python, Visualization |

### 3. Profile Display
The profile page now shows:
- User's skills as badges
- Weekly capacity hours
- Current utilization percentage

## How Users Can Add/Edit Their Skills

### Option 1: Through the Web Interface (Recommended)
1. Log in to your account
2. Click on your username in the top right corner
3. Select "Profile" from the dropdown
4. In the "Edit Profile" section, you'll see:
   - **Skills** field: Enter skills separated by commas (e.g., `Python, JavaScript, Project Management`)
   - **Weekly Working Hours**: Set your available hours per week
5. Click "Save Changes"
6. Your skills will now be displayed on your profile and used by the AI

### Option 2: Programmatically (For Admins)
You can run the script `add_skills_to_real_users.py` to batch update multiple users.

## How Skills Affect AI Suggestions

The AI Resource Optimization now considers skills when making suggestions:

1. **Skill Matching**: When a task requires specific technologies (e.g., "Implement data export feature"), users with matching skills (like Data Analysis, Python) get higher scores

2. **Equal Scores**: When multiple users have the same score, those with relevant skills appear higher in suggestions

3. **Visibility**: All real users in the same organization see each other (if they're board members) plus all demo users

## Example

Before adding skills:
```
Top recommendations: carol_anderson, david_taylor, user7, user8
(All have equal scores of 73.0, alphabetical order)
```

After adding skills (for a data-related task):
```
Top recommendations:
- user8 (has Data Analysis, SQL, Python skills)
- user2 (has Data Analysis, SQL, Python skills)
- carol_anderson
- david_taylor
```

## Current Status

✅ Skills field added to profile form
✅ Profile page updated to display skills
✅ All real users (user1-user8) have skills assigned
✅ AI considers skills when making recommendations
✅ Demo users remain visible to all users
✅ Organization-based filtering working correctly

## Next Steps for Users

1. **Update Your Profile**: Go to your profile page and add your actual skills
2. **Set Your Capacity**: Update your weekly working hours if the default (40 hours) doesn't match your availability
3. **Keep Skills Updated**: As you learn new skills or change roles, update your profile

The AI will now better match tasks to people based on their skills and availability!
