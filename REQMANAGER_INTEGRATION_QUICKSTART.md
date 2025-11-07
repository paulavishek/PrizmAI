# ReqManager Features Integration - Quick Start

## What Was Added

This document summarizes the three ReqManager features now integrated into PrizmAI:

### 1. Parent-Child Task Relationships ✅
- Create hierarchical task structures
- Prevent circular dependencies automatically
- Track complete dependency chains
- Methods: `get_all_subtasks()`, `get_all_parent_tasks()`, `get_dependency_level()`

### 2. Visual Dependency Tree ✅
- Beautiful HTML/CSS tree visualization
- Color-coded nodes (parent, child, related)
- Interactive task navigation
- Nested multi-level hierarchy display
- Access via `/kanban/task/<id>/dependency-tree/`

### 3. AI-Suggested Task Dependencies ✅
- Analyzes task descriptions automatically
- Suggests parent-child relationships
- Identifies related tasks
- Detects blocking/dependent relationships
- Confidence scoring for each suggestion
- One-click linking from the UI

## Getting Started

### Step 1: Apply Database Migration
```bash
python manage.py migrate kanban
```

### Step 2: Access Features

**Option A: Web Interface**
- Go to any task detail page
- Click the new "Dependency Tree" button (or navigate to `/kanban/task/<id>/dependency-tree/`)
- Click "Analyze Dependencies" to get AI suggestions
- Click "Link" to accept suggestions

**Option B: Admin Interface**
- Open Django admin `/admin/kanban/task/`
- Edit any task
- In the "Task Dependencies" section:
  - Set parent task
  - Add related tasks
  - View dependency chain

**Option C: Management Command**
```bash
# Analyze all tasks
python manage.py analyze_task_dependencies

# Analyze with auto-linking
python manage.py analyze_task_dependencies --board-id 5 --auto-link

# Analyze specific task
python manage.py analyze_task_dependencies --task-id 42
```

**Option D: API**
```bash
# Get dependencies for a task
curl http://localhost:8000/kanban/api/task/1/dependencies/

# Analyze a task (AI suggestions)
curl -X POST http://localhost:8000/kanban/api/task/1/analyze-dependencies/ \
  -H "Content-Type: application/json" \
  -d '{"auto_link": false}'

# Set parent task
curl -X POST http://localhost:8000/kanban/api/task/1/set-parent/ \
  -H "Content-Type: application/json" \
  -d '{"parent_task_id": 2}'

# View dependency tree as JSON
curl http://localhost:8000/kanban/api/task/1/dependency-tree/

# Get board-wide dependency graph
curl http://localhost:8000/kanban/api/board/1/dependency-graph/
```

## Key Improvements Over ReqManager

1. **Adapted for Kanban Boards**: Works with PrizmAI's column-based task organization
2. **Integrated Risk Management**: Dependencies feed into risk assessment
3. **Resource Forecasting Ready**: Dependency data improves workload predictions
4. **AI-Enhanced**: Uses existing AI infrastructure for better suggestions

## Model Structure

```python
class Task(models.Model):
    # ... existing fields ...
    
    # NEW: Dependency Management
    parent_task = ForeignKey('self', on_delete=SET_NULL, ...)
    subtasks = Reverse relation to parent_task
    related_tasks = ManyToManyField('self', ...)
    dependency_chain = JSONField()  # [id_root, id_mid, id_current]
    
    # NEW: AI Suggestions
    suggested_dependencies = JSONField()  # AI analysis results
    last_dependency_analysis = DateTimeField()
```

## Common Use Cases

### Create a Project Breakdown
```python
# Main feature
feature = Task.objects.create(title="User Authentication", ...)

# Implementation tasks
backend = Task.objects.create(title="Backend Login API", parent_task=feature, ...)
frontend = Task.objects.create(title="Login UI", parent_task=feature, ...)

# Subtasks
db_schema = Task.objects.create(title="Design Auth Schema", parent_task=backend, ...)
jwt_impl = Task.objects.create(title="Implement JWT", parent_task=backend, ...)
testing = Task.objects.create(title="Test Authentication", parent_task=backend, ...)
```

### Link Related Tasks
```python
# Tasks aren't hierarchically related but should be coordinated
frontend_task.related_tasks.add(api_task)
api_task.related_tasks.add(documentation_task)
```

### Check Task Dependencies
```python
# Prevent deletion of tasks with subtasks
if task.subtasks.exists():
    print("Cannot delete - has child tasks")

# Find all root tasks in a board
root_tasks = Task.objects.filter(
    column__board=board,
    parent_task__isnull=True
)

# Check dependency level
if task.get_dependency_level() > 3:
    print("This is deeply nested")
```

## UI Components Added

### 1. Dependency Tree View
- **Template**: `templates/kanban/dependency_tree.html`
- **Features**:
  - Visual tree with color-coded nodes
  - Parent task section
  - Subtasks with nesting
  - Related tasks section
  - AI suggestions panel
  - One-click linking

### 2. Analysis Panel
- **Triggered by**: "Analyze Dependencies" button
- **Shows**:
  - Parent task suggestions with confidence scores
  - Related task suggestions
  - Blocking/dependency relationships
  - Link buttons for accepted suggestions

### 3. Admin Enhancements
- **Parent task dropdown** in task edit form
- **Related tasks multi-select** in task edit form
- **Read-only dependency chain display**
- **AI suggestions collapsible section**

## API Endpoints Summary

| Endpoint | Method | Purpose |
|----------|--------|---------|
| `/api/task/<id>/dependencies/` | GET | Get all task relationships |
| `/api/task/<id>/set-parent/` | POST | Set parent task |
| `/api/task/<id>/add-related/` | POST | Add related task |
| `/api/task/<id>/analyze-dependencies/` | POST | Run AI analysis |
| `/api/task/<id>/dependency-tree/` | GET | Get hierarchical tree |
| `/api/board/<id>/dependency-graph/` | GET | Get full board graph |

## Files Reference

### New Files
- `kanban/utils/dependency_suggestions.py` - Core engine (300+ lines)
- `kanban/management/commands/analyze_task_dependencies.py` - CLI tool
- `templates/kanban/dependency_tree.html` - Visualization
- `DEPENDENCY_MANAGEMENT_GUIDE.md` - Full documentation

### Modified Files
- `kanban/models.py` - Added 5 new fields + 5 new methods
- `kanban/admin.py` - Enhanced Task admin with 2 new fieldsets
- `kanban/api_views.py` - Added 6 new API functions (150+ lines)
- `kanban/views.py` - Added 2 new view functions
- `kanban/urls.py` - Added 8 new URL patterns
- `kanban/migrations/0009_task_dependencies.py` - Database schema

## Performance Notes

- ✅ Circular dependency check: O(n) where n = hierarchy depth (usually <10)
- ✅ Get all subtasks: O(n) where n = total descendants (cached in queries)
- ✅ AI analysis: O(m*n) where m = task count, n = avg description length
- ⚠️  AI analysis on large boards (1000+ tasks) may take time - use async for production

## Next Steps

1. **Run migration**: `python manage.py migrate kanban`
2. **Test the feature**: Create a few tasks with parent-child relationships
3. **Use AI suggestions**: Click "Analyze Dependencies" on any task
4. **Link suggestions**: Accept AI suggestions that make sense for your project
5. **Explore the tree view**: Navigate `/kanban/task/<id>/dependency-tree/`
6. **Check admin**: Review dependencies in Django admin
7. **Use the API**: Integrate with external tools if needed

## Troubleshooting

**Problem**: "Circular dependency" error when setting parent
- **Solution**: The task you're setting as parent is already a child/descendant

**Problem**: No AI suggestions appear
- **Solution**: Task descriptions need more content; system looks for keywords

**Problem**: Tree view shows "no dependencies"
- **Solution**: Create parent/child relationships or run "Analyze Dependencies"

**Problem**: Performance is slow on large boards
- **Solution**: Analyze specific boards/tasks rather than entire system

## Examples

### Example 1: Mobile App Project
```
Mobile App Project (root)
├── Backend API
│   ├── Database Schema
│   ├── User Authentication
│   ├── REST Endpoints
│   └── Testing
├── iOS App
│   ├── UI Components
│   ├── API Integration
│   └── Beta Testing
└── Android App
    ├── UI Components
    ├── API Integration
    └── Beta Testing
```

### Example 2: Feature Development
```
Payment Integration (root)
├── Design Payment Flow
├── Implement Stripe Integration
│   ├── Setup Stripe Account
│   ├── Implement Webhooks
│   └── Error Handling
├── Frontend Payment UI
│   ├── Checkout Component
│   └── Payment Method Selection
├── Testing
│   ├── Unit Tests
│   └── Integration Tests
└── Documentation
```

---

**Ready to get started?** Run `python manage.py migrate kanban` and create your first hierarchical task structure!

For detailed documentation, see `DEPENDENCY_MANAGEMENT_GUIDE.md`.
