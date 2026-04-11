# Spectra v1.0 — Test Question Suite

> Use these questions to verify Spectra's read-only Q&A functionality.  
> Test in both **My Workspace** and **Demo Workspace** (sandbox).  
> For each question, note whether Spectra responds correctly and without data leakage.

---

## Category 1: Basic Board Queries

These should return accurate data from the currently selected board.

```
1.  How many tasks are on this board?
2.  What tasks are overdue?
3.  Give me a summary of this board.
4.  Which tasks are in the "In Progress" column?
5.  What's the status distribution across all columns?
6.  How many unassigned tasks are there?
7.  What are the highest priority tasks right now?
8.  Show me tasks due this week.
9.  What milestones are coming up?
10. Who has the most tasks assigned to them?
```

**Expected**: Accurate numbers matching the board's actual state. Numbers should match the live board snapshot.

---

## Category 2: Team & Resource Queries

```
11. Who's working on what?
12. Who is overloaded right now?
13. What's the team's workload like?
14. Which team members have no tasks assigned?
15. Who is assigned to the most overdue tasks?
```

**Expected**: Only shows team members who are on boards the user has access to.

---

## Category 3: Risk & Blocker Queries

```
16. What are the current risks on this board?
17. Are there any blockers I should know about?
18. What dependencies might cause delays?
19. Which tasks are at risk of missing their deadline?
20. Show me bottlenecks in the workflow.
```

**Expected**: Risk analysis scoped to the selected board or user's accessible boards.

---

## Category 4: Strategic Hierarchy Queries

These trigger the strategic workflow context. Verify the Goal → Mission → Strategy → Board hierarchy is correct.

```
21. What are our organization goals?
22. How are our missions progressing?
23. Show me the strategy hierarchy.
24. How does this board connect to our organizational goals?
25. What's the status of our OKRs?
26. How are our goals tracking?
27. Show me the alignment between goals and boards.
```

**Expected**: Only goals/missions/strategies reachable from the user's accessible boards. No data from other users' boards or other organizations.

---

## Category 5: Cross-Board / Aggregate Queries

```
28. What's overdue across all my boards?
29. Give me a summary across all boards.
30. Which board has the most overdue tasks?
31. How many total tasks do I have across all boards?
32. Compare workload across my boards.
```

**Expected**: Aggregate results only include boards the user has explicit access to. No cross-workspace leakage.

---

## Category 6: Wiki & Documentation Queries

```
33. What does the wiki say about our deployment process?
34. Search the documentation for "API endpoints".
35. Summarize the project documentation.
36. What meeting notes do we have?
```

**Expected**: Wiki content from boards the user has access to.

---

## Category 7: Action Intent Rejection (v1.0 Disabled)

All of these should return the v1.0 fallback message. **None of these should actually execute.**

```
37. Create a task called "Fix login bug" with high priority.
38. Create a new board called "Sprint 5 Planning".
39. Send a message to Alex saying the deployment is ready.
40. Log 3 hours on the database migration task.
41. Schedule a standup meeting for tomorrow at 10 AM.
42. Create a retrospective for the last sprint.
43. Set up an automation that marks overdue tasks as urgent.
44. Update the priority of task "API integration" to high.
45. Make a board for the marketing team.
46. Tell the team that the release is postponed.
```

**Expected**: Every single one returns:
> "I can read and report on your project data, but I can't create, update, or delete anything in v1.0. Action commands — like creating tasks, logging time, and sending messages — are arriving in Spectra v2.0 🚀..."

---

## Category 8: Edge Cases & Mixed Intent

```
47. Can you create a summary of overdue tasks?
    → Should PASS (this is a query, not a create action)
    
48. What would happen if I created a new board for the team?
    → Should PASS (hypothetical question, not an action request)

49. I want to send a message to Alex.
    → Should BLOCK (clear action intent)

50. How do I create a task?
    → Ambiguous — may pass or block. Either is acceptable.
    
51. Show me tasks then create a follow-up task for each overdue one.
    → Should BLOCK (contains action intent)

52. What's the difference between creating a board and creating a task?
    → Should PASS (informational question about concepts)
```

---

## Category 9: RBAC & Sandbox Isolation Tests

### My Workspace Tests
```
53. [As a Viewer on Board X] What tasks does Alice have on Board X?
    → Should work (Viewer has read access)

54. [As a non-member of Board Y] What tasks are on Board Y?
    → Should show no data or deny access (no membership)

55. [After being removed from Board Z] Tell me about Board Z.
    → Session board should auto-clear; should show no data
```

### Demo Workspace Tests
```
56. [In User A's sandbox] Show me all tasks.
    → Should show only tasks from User A's sandbox boards

57. [In User A's sandbox] What boards do I have access to?
    → Should list only User A's sandbox copies + official demo boards
    → Should NOT list User B's sandbox boards

58. [In Demo mode] Show me data from the real workspace.
    → Should show no real workspace data (demo scoping enforced)
```

---

## Category 10: Conversation Behavior

```
59. Hello / Hi / Hey
    → Should greet back naturally, introduce capabilities (read-only)

60. [Send a very long message — 500+ words]
    → Should handle gracefully, respond to the core question

61. [Send an empty message or spaces]
    → Frontend should prevent submission (input.trim() check)

62. [Rapidly click Send 5 times on the same message]
    → Should only process once (double-submit guard)

63. [Attach a PDF and ask] Summarize this document.
    → Should analyze the attached file content

64. [Switch boards mid-conversation] Now tell me about the other board.
    → Should respond with data from the newly selected board
```

---

## Test Matrix

| # | Category | Count | My Workspace | Demo Sandbox |
|---|----------|-------|:---:|:---:|
| 1 | Basic Board | 10 | ☐ | ☐ |
| 2 | Team & Resources | 5 | ☐ | ☐ |
| 3 | Risks & Blockers | 5 | ☐ | ☐ |
| 4 | Strategic Hierarchy | 7 | ☐ | ☐ |
| 5 | Cross-Board | 5 | ☐ | ☐ |
| 6 | Wiki & Docs | 4 | ☐ | ☐ |
| 7 | Action Rejection | 10 | ☐ | ☐ |
| 8 | Edge Cases | 6 | ☐ | ☐ |
| 9 | RBAC/Sandbox | 6 | ☐ | ☐ |
| 10 | Behavior | 6 | ☐ | ☐ |
| | **Total** | **64** | | |
