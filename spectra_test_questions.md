# Spectra Test Questions

Comprehensive test suite covering ALL of Spectra's capabilities.
Run these against the **Demo Workspace** (Software Development board) to validate end-to-end behavior.
Record each result as: PASS / FAIL / PARTIAL — with notes on what went wrong.

**Setup:** Open Spectra from the Demo - Acme Corporation dashboard with the Software Development board selected.

---

## SECTION A: Conversational Q&A — Project Intelligence (20 questions)

### A1. Board Overview & Status
1. "What's the current status of the Software Development board?"
   — *Expected: Task counts, column distribution, completion %, overdue summary*

2. "How many tasks are on this board and how many are complete?"
   — *Expected: 30 tasks total, accurate done/completed count with percentage*

3. "Give me a quick summary of what's happening on this board"
   — *Expected: High-level overview with key stats and notable items*

### A2. Task Queries
4. "What tasks are currently overdue on this board?"
   — *Expected: Lists overdue tasks with due dates, assignees, and days overdue*

5. "What tasks are assigned to Alex Chen?"
   — *Expected: Lists Alex's tasks with status and priority*

6. "What should I work on next?"
   — *Expected: Prioritized recommendation based on urgency, deadlines, or priority*

7. "Show me all high-priority and urgent tasks"
   — *Expected: Filtered list of high/urgent tasks with details*

8. "Which tasks are still incomplete on this board?"
   — *Expected: Lists all not-done tasks grouped by status/column*

9. "What tasks are due this week?"
   — *Expected: Tasks with due dates falling within the current week*

### A3. Workload & Resource Analysis
10. "Who on the team has the most tasks assigned right now?"
    — *Expected: Task distribution across Alex Chen, Sam Rivera, Jordan Taylor with counts*

11. "Is anyone on the team overloaded with work?"
    — *Expected: Capacity analysis, identifies over-allocated members*

12. "What's the workload distribution across team members?"
    — *Expected: Per-member breakdown of tasks, overdue items, and status*

### A4. Risk & Dependency Analysis
13. "Are there any blockers or high-risk tasks I should know about?"
    — *Expected: Identifies critical/blocked tasks, dependency chains*

14. "Can we finish all remaining tasks by end of this month?"
    — *Expected: Deadline feasibility projection with analysis*

15. "What are the task dependencies on this board?"
    — *Expected: Dependency relationships, blocking chains, critical path*

### A5. Progress & Analytics
16. "How is the project going? Are we on track?"
    — *Expected: Completion rate, velocity, burndown insights, on-track assessment*

17. "Compare the progress across all boards"
    — *Expected: Multi-board comparison with task counts, completion %, activity*

18. "How many tasks are there in total across all boards?"
    — *Expected: Aggregate count across all accessible boards*

### A6. Strategic & Organizational
19. "How does this board connect to our organizational goals?"
    — *Expected: Goal → Mission → Strategy → Board hierarchy with progress*

20. "What are our current organizational goals and missions?"
    — *Expected: Lists goals, linked missions, strategies, and associated boards*

---

## SECTION B: Documentation & Knowledge Queries (5 questions)

21. "What documentation do we have in the wiki?"
    — *Expected: Lists wiki pages/categories (Getting Started, Technical Docs, etc.)*

22. "What did we discuss in recent meetings?"
    — *Expected: Meeting notes, action items, decisions from transcript data*

23. "Do we have any coding standards documented?"
    — *Expected: References coding standards wiki page content*

24. "Search the knowledge base for API documentation"
    — *Expected: Finds and summarizes relevant wiki pages about APIs*

25. "What are the best practices for sprint planning?"
    — *Expected: References wiki content or provides PM best practices*

---

## SECTION C: Web Search (2 questions)

26. "What are the latest trends in agile project management for 2026?"
    — *Expected: Web search triggered, returns external results with sources*

27. "What is the difference between Scrum and Kanban methodologies?"
    — *Expected: Web search or knowledge-based comparison with citations*

---

## SECTION D: Task Creation (7 questions)

28. "Create a task called SPECTRA_TEST_SIMPLE"
    — *Expected: Asks for due date → assignee → confirms → creates task*

29. "Create a high-priority task called SPECTRA_TEST_RICH due tomorrow assigned to Alex Chen"
    — *Expected: Extracts all fields inline, shows confirmation, creates on confirm*

30. "Create a task called Authentication System"
    — *Expected: Duplicate warning — task already exists, asks to proceed or rename*

31. "Create an urgent task called SPECTRA_TEST_URGENT due next Friday"
    — *Expected: Extracts title + priority + due date, asks for assignee, then confirms*

32. *(Open Spectra WITHOUT a board selected first)* "Create a task called SPECTRA_TEST_NO_BOARD"
    — *Expected: Asks which board to create the task on, lists available boards*

33. Start with: "Create a task called SPECTRA_TEST_SKIP"
    Then when asked for due date: "skip"
    Then when asked for assignee: "none"
    — *Expected: Creates task with no due date and no assignee*

34. Start with: "Create a task called SPECTRA_TEST_CANCEL"
    Then when asked for due date: "cancel"
    — *Expected: Cancels the flow, confirms cancellation*

---

## SECTION E: Task Update (5 questions)

35. "Mark the Requirements Analysis & Planning task as done"
    — *Expected: Moves task to Done column, confirms completion*

36. "Change the priority of File Upload System to urgent"
    — *Expected: Updates priority, confirms the change*

37. "Reassign the Notification Service task to Jordan Taylor"
    — *Expected: Updates assignee, confirms reassignment*

38. "Change the due date of API Rate Limiting to next Monday"
    — *Expected: Updates due date, confirms new date*

39. "Rename the task Performance Optimization to Performance Tuning & Optimization"
    — *Expected: Updates title, confirms the rename*

---

## SECTION F: Board Creation (3 questions)

40. "Create a new board called SPECTRA_TEST_BOARD"
    — *Expected: Asks for description → confirms → creates board with default columns*

41. "Create a board called SPECTRA_TEST_BOARD_DESC with description Testing Spectra board creation capabilities"
    — *Expected: Extracts name + description, confirms, creates board*

42. "Create a board called Software Development"
    — *Expected: Duplicate warning — board already exists*

---

## SECTION G: Send Message (3 questions)

43. "Send a message to Alex Chen saying the deployment is scheduled for tonight at 9 PM"
    — *Expected: Shows confirmation with recipient + message, sends on confirm*

44. "Tell Sam Rivera that the design review has been moved to Thursday"
    — *Expected: Detects send_message intent, shows confirmation, sends*

45. "Send a message to NonExistentUser saying hello"
    — *Expected: Reports user not found, lists available board members*

---

## SECTION H: Log Time (3 questions)

46. "Log 2 hours on the Authentication System task"
    — *Expected: Shows confirmation with task + hours, logs on confirm*

47. "Log 1.5 hours on the database migration task for yesterday, worked on schema changes"
    — *Expected: Fuzzy matches 'Database Schema & Migrations', includes date + description*

48. "Log 1 hour on API"
    — *Expected: Fuzzy matches 'Base API Structure' or disambiguates between API tasks*

---

## SECTION I: Schedule Event (2 questions)

49. "Schedule a team standup tomorrow at 10 AM"
    — *Expected: Shows confirmation with event details, creates on confirm*

50. "Schedule a sprint planning meeting next Monday at 2 PM with Alex Chen and Sam Rivera"
    — *Expected: Extracts title + datetime + participants, confirms, creates*

---

## SECTION J: Create Retrospective (2 questions)

51. "Generate a retrospective for the last two weeks"
    — *Expected: Creates retro with sprint analytics, what went well/poorly*

52. "Create a project retrospective from March 1 to March 31"
    — *Expected: Custom date range retro with period-specific data*

---

## SECTION K: Automation (3 questions)

53. "Set up an automation to mark overdue tasks as urgent"
    — *Expected: Recognizes template, shows confirmation, activates*

54. "Create an automation that sends a notification when a task is completed"
    — *Expected: Custom trigger automation flow, collects details, creates*

55. "Create a daily automation called Morning Digest that sends board summaries at 9 AM"
    — *Expected: Scheduled automation flow, creates recurring rule*

---

## SECTION L: Commitment Protocols (3 questions)

56. "What's the commitment status on this board?"
    — *Expected: Shows commitment health, confidence levels, status*

57. "Are there any at-risk commitments?"
    — *Expected: Lists commitments with critical/at-risk status*

58. "Place a bet on a commitment with 80% confidence and 10 tokens"
    — *Expected: Processes bet, confirms tokens wagered, updates balance*

---

## SECTION M: Lean & Efficiency (2 questions)

59. "Are there any waste or inefficiency areas in our workflow?"
    — *Expected: Lean analysis — identifies NVA tasks, bottlenecks, waste*

60. "What value-added vs non-value-added tasks do we have?"
    — *Expected: LSS classification breakdown of tasks*

---

## SECTION N: Flow Control & Edge Cases (7 questions)

61. Start: "Create a task called SPECTRA_TEST_FLOW"
    At confirmation: "Change the due date to next Wednesday"
    — *Expected: Updates the due date in the confirmation, re-presents for approval*

62. Start: "Create a task called SPECTRA_TEST_SWITCH"
    Before completing: "Actually, send a message to Alex instead"
    — *Expected: Warns about abandoning task creation, switches to message flow*

63. At any confirmation step: "Yes, go ahead" or "Looks good, create it"
    — *Expected: Natural language confirmation accepted, action executed*

64. At any confirmation step: "No, don't do it" or "Never mind"
    — *Expected: Cancels the pending action cleanly*

65. "Create a task" *(no title given)*
    — *Expected: Asks "What should the task be called?" — starts collection flow*

66. Send an empty message or just whitespace
    — *Expected: Graceful error — "Message cannot be empty"*

67. Ask a very long question (500+ characters) about multiple topics at once
    — *Expected: Handles gracefully without truncation errors*

---

## SECTION O: Multi-Capability Sequences (3 questions)

68. After creating a task (Q28), immediately: "Now log 2 hours on SPECTRA_TEST_SIMPLE"
    — *Expected: State resets cleanly, new time log flow starts*

69. After creating a board (Q40), ask: "How many boards do I have now?"
    — *Expected: Returns to Q&A mode, provides accurate board count*

70. After any action, ask: "What tasks are overdue?"
    — *Expected: Clean transition back to Q&A, accurate overdue list*

---

## SECTION P: Session & Export (3 questions)

71. Rename the current chat session — click the edit/pencil icon next to the session name
    — *Expected: Session name updates, persists on refresh*

72. Click the Export button and export as JSON
    — *Expected: Downloads .json file with all messages, metadata*

73. Click the Export button and export as Markdown
    — *Expected: Downloads .md file with formatted conversation*

---

## SECTION Q: File Analysis (2 questions)

74. Upload a small text or PDF file, then ask: "What is this document about?"
    — *Expected: Spectra analyzes the uploaded document and summarizes it*

75. With a file still attached, ask: "What are the key points in the attached document?"
    — *Expected: Extracts and presents key points from the uploaded file*

---

## Results Summary Template

| Section | Total | Pass | Fail | Partial |
|---------|-------|------|------|---------|
| A. Q&A Intelligence | 20 | | | |
| B. Documentation | 5 | | | |
| C. Web Search | 2 | | | |
| D. Task Creation | 7 | | | |
| E. Task Update | 5 | | | |
| F. Board Creation | 3 | | | |
| G. Send Message | 3 | | | |
| H. Log Time | 3 | | | |
| I. Schedule Event | 2 | | | |
| J. Retrospective | 2 | | | |
| K. Automation | 3 | | | |
| L. Commitments | 3 | | | |
| M. Lean/Efficiency | 2 | | | |
| N. Edge Cases | 7 | | | |
| O. Multi-Sequence | 3 | | | |
| P. Session/Export | 3 | | | |
| Q. File Analysis | 2 | | | |
| **TOTAL** | **75** | | | |
