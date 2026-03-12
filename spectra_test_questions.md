# Spectra Test Questions

25 test prompts covering the full spectrum of Spectra's capabilities.
Use these against a board with tasks, members, and data to validate end-to-end behavior.

---

## Conversational Q&A (Project Intelligence)

1. **Board overview** — "What's the current status of this board? How many tasks are overdue?"
2. **Task prioritization** — "What should I work on next?"
3. **Risk assessment** — "Are there any high-risk tasks or blockers I should know about?"
4. **Workload analysis** — "Who on the team has the most tasks assigned right now?"
5. **Sprint progress** — "How is the sprint going? Are we on track to finish on time?"
6. **Strategic alignment** — "How does this board connect to our organizational goals?"
7. **Deadline awareness** — "Which tasks are due this week?"
8. **Documentation search** — "What did we decide in last week's meeting about the API redesign?"

## Task Creation

9. **Simple task** — "Create a task called Update the login page"
10. **Rich task** — "Create a high-priority task called Fix payment gateway bug, assign it to Alex, due next Friday"
11. **Task without board** (test board selection) — Open Spectra without a board selected, then: "Add a task called Write unit tests for auth module"

## Board Creation

12. **Simple board** — "Create a new board called Q2 Marketing Campaign"
13. **Board with description** — "Create a board called Bug Tracker with description Tracking all production bugs"

## Send Message

14. **Direct message** — "Send a message to Alex saying the deployment is scheduled for tonight"
15. **Intent-based message** — "Tell Sam that the design review has been moved to Thursday"

## Log Time

16. **Simple time log** — "Log 2 hours on the API integration task"
17. **Time with date and description** — "Log 1.5 hours on the database migration task for yesterday, worked on schema changes"

## Schedule Event

18. **Simple meeting** — "Schedule a team standup tomorrow at 10 AM"
19. **Detailed event** — "Schedule a sprint planning meeting next Monday at 2 PM with Alex and Sam in Conference Room B"

## Create Retrospective

20. **Sprint retro** — "Generate a retrospective for the last two weeks"
21. **Custom period retro** — "Create a project retrospective from March 1 to March 12"

## Automation

22. **Template automation** — "Set up an automation to mark overdue tasks as urgent"
23. **Custom trigger automation** — "Create an automation called Notify on completion that sends a notification when a task is completed"
24. **Scheduled automation** — "Create a daily automation called Morning Digest that sends notifications to board members about incomplete tasks at 9 AM"

## Flow Control & Edge Cases

25. **Cancel mid-flow** — Start "Create a task called Test", then when asked for due date say "Cancel"
