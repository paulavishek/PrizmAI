(1) first of all create total 30 tasks for each board. 

(2) We can create a form to build a WBS:

Recommended UI Formats - 

For a creation form, choose a format based on your users' needs for speed versus visual clarity: 

Outline/Indented List (Highest Utility): Present the WBS as a text-based list where users use an indent function (or Tab/Shift+Tab) to create parent-child relationships. This is the most efficient for rapid data entry.

Key Design Elements & Features:

Numeric Coding System: Automatically assign unique, hierarchical identifiers (e.g., 1.0, 1.1, 1.1.1) to reflect each element's position.
In-line Editing: Allow users to quickly edit, add and delete. 

Deliverable-Centric Naming: Use placeholder text or tooltips that encourage using nouns rather than verbs (e.g., "Login Module" instead of "Build Login Module") to focus on outcomes.

Dynamic Breadcrumbs: For deep hierarchies, use breadcrumbs or a persistent "Parent Item" header to help users understand their location within the structure. 

Essential Metadata Fields:

Each entry in your WBS creation form should typically include these core fields:
WBS ID: Auto-generated hierarchical number.
Deliverable Name: The outcome of that specific work package.
Owner/Accountability: A single individual or team responsible for that element.
Duration/Effort: Estimated time (often following the 8/80 rule, where packages take between 8 and 80 hours).

We can integrate AI in WBS. If users provide the board name, description, duration and number of phases then AI will create the WBS out of it. 

┌─────────────────────────────────────────────────────────┐
│  Create Project Structure                               │
├─────────────────────────────────────────────────────────┤
│                                                          │
│  Option 1: [AI Generate WBS]    Option 2: [Manual]     │
│                                                          │
│  ┌──────────────────────────────────────────────────┐  │
│  │ AI WBS Generator                                  │  │
│  │                                                    │  │
│  │ Board Name: Launch AI Assistant               │  │
│  │ Description: [text area]                          │  │
│  │ Target Duration: 12 weeks                         │  │
│  │ Number of Phases: 3                               │  │
│  │                                                    │  │
│  │ [Generate Structure]                              │  │
│  └──────────────────────────────────────────────────┘  │
│                                                          │
└──────────────────────────────────────────────────────────┘

But for both AI and manual WBS creation, the format should be identical. 

 (3) users will have clear idea about the leaf tasks from the WBS. Then they can use those task titles, say 30 tasks, to fill up the task creation form. Now the task creation form will have two options at the beginning - whether the form is to create a task or a milestone (there will be a drop down menu with only these two options). If it is a task, then the task creation form I used here, I can use the same form.  But if it is a milestone the there will be no start date field, only due date. Plus the form will be much shorter than the task creation form. All the tasks and milestones will go to the "backlog" column. 

 There are two trick questions here, 

 (a) If a user just type "Design Login Page" as one of the leaf tasks into WBS, do they have to type it again into the Task Creation Form?

Guiding Question 1: How can we link the WBS builder directly to the Task Creation form so the user doesn't have to re-enter the data they just created?

Answer: At the WBS there will be an option to create tasks with the leaf level task titles. When users will chose it, it will automatically create all the 30 task creation form and include them in the backlog of the kanban board. Users then selectively pick them to fill up the rest of the task creation fields
 
 (b) The "Milestone" Logic
We are adding a specific drop-down for Task vs. Milestone.

Tasks: Have Duration (Start -> End).

Milestones: Have 0 Duration (Due Date only).

This is a critical distinction for the Gantt chart.

Guiding Question 2: In your proposed Gantt chart, if a Phase has 10 tasks and 2 milestones, usually milestones mark the end of a phase. Should the "Phase End Date" be calculated from the latest Task due date, or does the Milestone date override everything as the hard deadline?

Answer: I think we will let users put both task and milestone due date. Milestones will be appeared as a diamond shaped on the gantt chart. Now it is true that end of phase is usually considered a milestone, but let users decide that. Anyway it shouldn't matter, just like tasks milestones should be placed on the gantt chart based on their due dates. If it overlaps the latest end date of a task or any intermediate dates, it still should be fine if we isolate each milestone from the task and we can place them below the task bar on the gantt chart so that they dont overlap with task bars. In this way both tasks and milestones will position correctly on the gantt chart.
 
 
 (4) now we will go to the Gantt chart. We will divide all the 30 tasks into timebound phases. For example users decide to have 3 phases for the whole board. For each phase 10 tasks and 2 milestones. We can include a separate field for 'phase' on the task creation form. So for every task, users need to mention which phase it belongs to. When we will have all the phases, then the Gantt chart will show only phases with timeline. Now the timeline for each phase will be calculated from the earliest start date and the latest due date among all the tasks in that specific phase. So we will see only three phases on the gantt chart. If users click on each phase then the chart will show the time distribution of only those tasks that fall in that phase. It will also show the milestones in that phase. 

 The "Phase" Concept
You suggested adding a "Phase" field to the creation form.

Guiding Question 3: Is a "Phase" just a label (like a Tag), or is it a container object (like a Folder) that needs to be created first? For example, does the user need to create "Phase 1" before they can assign tasks to it?

Answer: We can use phase as tag, so on each task creation form there will be a separate field for phase. on the gantt chart when users select phase 1, it will display only those tasks that contain phase 1 tag. So first system will check how many different tags users created with the name "Phase". If it is 3 - phase 1,2 and 3, then based on that gantt chart will show at the top level (just below the timeline) all the phases. Now come to the timeframe of each phase. For each phase, system will check how many tasks are present in a particular phase and will isolate them. Then it will check the earliest start date and latest due date among all those isolated tasks. Based on that analysis it will span the phases.

When user clicks "Create Tasks" from WBS, they see:

┌─────────────────────────────────────────────────────────┐
│  Create Items from WBS                                   │
├─────────────────────────────────────────────────────────┤
│                                                          │
│  You have 10 tasks and 3 milestones to create.          │
│                                                          │
│  Creating: Task 1 of 10                                 │
│                                                          │
│  Item Type: [Task ▼]  or  [Milestone]                  │
│                                                          │
│  Pre-filled from WBS:                                    │
│  ┌──────────────────────────────────────────────────┐  │
│  │ Title: Define Requirements                       │  │
│  │ Phase: Phase 1 - Planning                        │  │
│  └──────────────────────────────────────────────────┘  │
│                                                          │
│  (Form continues based on type selection...)             │
└──────────────────────────────────────────────────────────┘

Task Form (Full Form): For better task creation form, please check the already existing "task creation"
form in PrizmAI. We can combine both the existing and our new idea to create the final task creation form. Also, check the "task details" form that we can use to view each task.

┌─────────────────────────────────────────────────────────┐
│  Create Task                                             │
├─────────────────────────────────────────────────────────┤
│                                                          │
│  Title: Define Requirements             [Auto-filled]   │
│  Description: [text area]                                │
│                                                          │
│  Phase: [Phase 1 - Planning ▼]          [Auto-filled]   │
│                                                          │
│  Dates:                                                  │
│  Start Date: [Jan 1, 2025]                              │
│  Due Date:   [Jan 7, 2025]                              │
│                                                          │
│  Assigned To: [Select user ▼]                           │
│  Priority: [Medium ▼]                                    │
│  Tags: [tag1] [tag2] [+ Add]                            │
│                                                          │
│  Dependencies: (optional)                                │
│  □ Depends on: [Select task]                            │
│                                                          │
│  [Cancel]  [Skip]  [Create & Next →]                    │
└──────────────────────────────────────────────────────────┘


Milestone Form (Simplified):

┌─────────────────────────────────────────────────────────┐
│  Create Milestone                                        │
├─────────────────────────────────────────────────────────┤
│                                                          │
│  Title: Planning Complete               [Auto-filled]   │
│  Description: [text area]                                │
│                                                          │
│  Phase: [Phase 1 - Planning ▼]          [Auto-filled]   │
│                                                          │
│  Due Date: [Jan 28, 2025]                               │
│                                                          │
│  Dependencies: (optional)                                │
│  ☑ Wait for: Define Requirements                        │
│  ☑ Wait for: Market Research                            │
│  ☑ Wait for: Technical Architecture                     │
│                                                          │
│  [Cancel]  [Skip]  [Create & Next →]                    │
└──────────────────────────────────────────────────────────┘

All Items Go to Backlog

After creation, all tasks and milestones go to Backlog column:

┌─────────────────────────────────────────────────────────┐
│  Backlog                                                 │
├─────────────────────────────────────────────────────────┤
│                                                          │
│  Phase 1: Planning (4 items)                            │
│  ├─ [TASK] Define Requirements              Jan 1-7     │
│  ├─ [TASK] Market Research                  Jan 8-14    │
│  ├─ [TASK] Technical Architecture           Jan 15-21   │
│  └─ [MILESTONE] Planning Complete           Jan 28      │
│                                                          │
│  Phase 2: Development (5 items)                         │
│  ├─ [TASK] Backend API Development          Feb 1-14    │
│  ├─ [TASK] Frontend UI Development          Feb 1-14    │
│  ├─ [TASK] Database Design                  Feb 15-21   │
│  ├─ [TASK] Integration                      Feb 22-28   │
│  └─ [MILESTONE] MVP Complete                Feb 28      │
│                                                          │
│  Phase 3: Testing (4 items)                             │
│  ├─ [TASK] QA Testing                       Mar 1-7     │
│  ├─ [TASK] Bug Fixes                        Mar 8-14    │
│  ├─ [TASK] Documentation                    Mar 8-14    │
│  └─ [MILESTONE] Launch                      Mar 15      │
│                                                          │
│  [View Gantt Chart]                                     │
└──────────────────────────────────────────────────────────┘

Phase-Based Gantt Chart

Default View: Phases Only

┌──────────────────────────────────────────────────────────────────────┐
│  Gantt Chart - Phase View                  [⚙️ Settings] [🔍 Filter] │
├──────────────────────────────────────────────────────────────────────┤
│                                                                        │
│  ┌─ Phases ─────────┐  ┌─ Timeline ─────────────────────────────┐   │
│  │                   │  │  Jan  │  Feb  │  Mar  │  Apr  │  May   │   │
│  │                   │  │       │       │       │       │        │   │
│  │ ▶ Phase 1         │  │ ████████████                           │   │
│  │   Planning        │  │              ♦                         │   │
│  │   4 tasks         │  │                                        │   │
│  │   1 milestone     │  │                                        │   │
│  │                   │  │                                        │   │
│  │ ▶ Phase 2         │  │              ████████████████████      │   │
│  │   Development     │  │                                   ♦    │   │
│  │   4 tasks         │  │                                        │   │
│  │   1 milestone     │  │                                        │   │
│  │                   │  │                                        │   │
│  │ ▶ Phase 3         │  │                                   ██████   │
│  │   Testing         │  │                                       ♦│   │
│  │   3 tasks         │  │                                        │   │
│  │   1 milestone     │  │                                        │   │
│  │                   │  │                                        │   │
│  └───────────────────┘  └────────────────────────────────────────┘   │
│                                                                        │
│  3 phases shown  |  13 tasks hidden  |  3 milestones shown           │
└────────────────────────────────────────────────────────────────────────┘

Clean! Only 3 rows ✓

Phase Timeline Calculation Logic:

const calculatePhaseTimeline = (phase, tasks, milestones) => {
  const phaseTasks = tasks.filter(t => t.phase === phase.id);
  const phaseMilestones = milestones.filter(m => m.phase === phase.id);
  
  // Phase start = earliest task start date
  const phaseStart = Math.min(
    ...phaseTasks.map(t => new Date(t.start_date))
  );
  
  // Phase end = latest of (task due dates OR milestone due date)
  const phaseEnd = Math.max(
    ...phaseTasks.map(t => new Date(t.due_date)),
    ...phaseMilestones.map(m => new Date(m.due_date))
  );
  
  return { start: phaseStart, end: phaseEnd };
};

Expanded View: Phase → Tasks
User clicks on "▶ Phase 2":

┌──────────────────────────────────────────────────────────────────────┐
│  Gantt Chart - Phase 2 Expanded                                      │
├──────────────────────────────────────────────────────────────────────┤
│                                                                        │
│  ┌─ Phase 2 Tasks ──────┐  ┌─ Timeline ────────────────────────┐   │
│  │                       │  │    Feb    │    Mar                │   │
│  │                       │  │ 1   7  14  21  28  7               │   │
│  │                       │  │                                     │   │
│  │ ▼ Phase 2             │  │ ████████████████████               │   │
│  │   Development         │  │                     ♦              │   │
│  │                       │  │                                     │   │
│  │  Tasks:               │  │                                     │   │
│  │  ○ Backend API        │  │ ██████████                         │   │
│  │    (assigned: Alice)  │  │                                     │   │
│  │                       │  │                                     │   │
│  │  ○ Frontend UI        │  │ ██████████                         │   │
│  │    (assigned: Bob)    │  │                                     │   │
│  │                       │  │                                     │   │
│  │  ○ Database Design    │  │          ████████                  │   │
│  │    (assigned: Carol)  │  │                                     │   │
│  │                       │  │                                     │   │
│  │  ○ Integration        │  │                  ████████           │   │
│  │    (assigned: Alice)  │  │                                     │   │
│  │                       │  │                                     │   │
│  │  📍 MVP Complete      │  │                         ♦          │   │
│  │                       │  │                                     │   │
│  └───────────────────────┘  └─────────────────────────────────────┘   │
│                                                                        │
│  [← Back to Phase View]  |  Showing 4 tasks + 1 milestone            │
└────────────────────────────────────────────────────────────────────────┘

Focused view! Only 6 rows ✓

Enhanced Task Model
Database Schema Updates:

from django.db import models

class Phase(models.Model):
    """New model to represent project phases"""
    project = models.ForeignKey('Project', on_delete=models.CASCADE)
    name = models.CharField(max_length=200)
    order = models.IntegerField()  # For sorting
    
    # Calculated fields (auto-computed from tasks)
    start_date = models.DateField(null=True, blank=True)
    end_date = models.DateField(null=True, blank=True)
    
    class Meta:
        ordering = ['order']
        unique_together = ['project', 'order']

class Task(models.Model):
    # Existing fields...
    title = models.CharField(max_length=500)
    description = models.TextField(blank=True)
    project = models.ForeignKey('Project', on_delete=models.CASCADE)
    
    # NEW: Item Type
    ITEM_TYPE_CHOICES = [
        ('task', 'Task'),
        ('milestone', 'Milestone')
    ]
    item_type = models.CharField(
        max_length=20, 
        choices=ITEM_TYPE_CHOICES,
        default='task'
    )
    
    # NEW: Phase assignment
    phase = models.ForeignKey(
        Phase, 
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='tasks'
    )
    
    # Dates (different handling for tasks vs milestones)
    start_date = models.DateField(null=True, blank=True)  # Only for tasks
    due_date = models.DateField()  # Required for both
    
    # Task-specific fields (not applicable to milestones)
    assigned_to = models.ForeignKey(
        'User', 
        on_delete=models.SET_NULL,
        null=True, 
        blank=True
    )
    
    # Progress (tasks: 0-100%, milestones: binary)
    completion_percentage = models.IntegerField(default=0)
    
    def save(self, *args, **kwargs):
        # Validation: Milestones shouldn't have start_date or assigned_to
        if self.item_type == 'milestone':
            self.start_date = None
            self.assigned_to = None
            
        super().save(*args, **kwargs)
        
        # Update phase timeline after saving
        if self.phase:
            self.phase.update_timeline()
    
    @property
    def duration_days(self):
        """Calculate duration (only for tasks)"""
        if self.item_type == 'milestone':
            return 0
        
        if self.start_date and self.due_date:
            return (self.due_date - self.start_date).days
        return 0

# Update Phase model with timeline calculation
class Phase(models.Model):
    # ... existing fields ...
    
    def update_timeline(self):
        """Auto-calculate phase start/end from tasks"""
        tasks = self.tasks.all()
        
        if not tasks.exists():
            self.start_date = None
            self.end_date = None
        else:
            # Earliest start date among tasks
            task_starts = [t.start_date for t in tasks if t.start_date]
            self.start_date = min(task_starts) if task_starts else None
            
            # Latest due date among tasks and milestones
            all_due_dates = [t.due_date for t in tasks if t.due_date]
            self.end_date = max(all_due_dates) if all_due_dates else None
        
        self.save(update_fields=['start_date', 'end_date'])

API Endpoints

WBS Generation:

# POST /api/wbs/generate/
{
  "project_id": "uuid",
  "project_title": "Launch AI Assistant",
  "project_description": "...",
  "num_phases": 3,
  "target_duration_weeks": 12
}

# Response:
{
  "phases": [
    {
      "name": "Planning",
      "order": 1,
      "tasks": [
        {"title": "Define Requirements", "type": "task"},
        {"title": "Market Research", "type": "task"},
        {"title": "Planning Complete", "type": "milestone"}
      ]
    },
    ...
  ],
  "total_tasks": 10,
  "total_milestones": 3
}

Batch Task Creation:

# POST /api/tasks/batch-create/
{
  "project_id": "uuid",
  "items": [
    {
      "title": "Define Requirements",
      "type": "task",
      "phase_id": "phase-1-id",
      "start_date": "2025-01-01",
      "due_date": "2025-01-07"
    },
    {
      "title": "Planning Complete",
      "type": "milestone",
      "phase_id": "phase-1-id",
      "due_date": "2025-01-28"
    }
  ]
}

# Response:
{
  "created": 13,
  "errors": []
}

Gantt Phase Data:

# GET /api/gantt/phases/?project_id=uuid

# Response:
{
  "phases": [
    {
      "id": "phase-1",
      "name": "Planning",
      "start_date": "2025-01-01",
      "end_date": "2025-01-28",
      "task_count": 3,
      "milestone_count": 1,
      "completion_percentage": 60
    },
    ...
  ],
  "total_duration_days": 84
}

# GET /api/gantt/phase-detail/?phase_id=phase-1

# Response:
{
  "phase": {...},
  "tasks": [...],
  "milestones": [...],
  "gantt_data": {
    "items": [
      {
        "id": "task-1",
        "title": "Define Requirements",
        "start": "2025-01-01",
        "end": "2025-01-07",
        "type": "task"
      },
      {
        "id": "milestone-1",
        "title": "Planning Complete",
        "date": "2025-01-28",
        "type": "milestone"
      }
    ]
  }
}

