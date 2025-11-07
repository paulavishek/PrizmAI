# PrizmAI Dependency Management Integration Guide

## Overview

This guide explains how to use the new Task Dependency Management features integrated from the ReqManager project into PrizmAI. These features enable you to:

1. **Create parent-child task relationships** - Organize tasks hierarchically
2. **Build visual dependency trees** - Visualize task dependencies and relationships
3. **Get AI-suggested dependencies** - Let AI analyze task descriptions and suggest related tasks

## Features Implemented

### 1. Simple Parent-Child Task Relationships

Tasks can now have parent-child relationships, enabling hierarchical task organization:

```
Project Implementation (Parent)
├── Design Database Schema (Child)
├── Implement API Endpoints (Child)
│   ├── GET Endpoints (Grandchild)
│   └── POST Endpoints (Grandchild)
└── Frontend Components (Child)
```

#### Model Fields Added to Task:
- `parent_task`: ForeignKey to self - Links to the parent task
- `subtasks`: Reverse relation - Shows all direct child tasks
- `related_tasks`: ManyToManyField - Non-hierarchical related tasks
- `dependency_chain`: JSONField - Complete path from root to this task
- `suggested_dependencies`: JSONField - AI-suggested task relationships
- `last_dependency_analysis`: DateTimeField - Last AI analysis timestamp

#### Key Methods:
```python
task.get_all_subtasks()           # Get all child tasks recursively
task.get_all_parent_tasks()       # Get all ancestor tasks
task.get_dependency_level()       # Get nesting level
task.has_circular_dependency()    # Check if link would create cycle
task.update_dependency_chain()    # Update the full dependency path
```

### 2. Visual Dependency Tree

Access the dependency tree view to visualize task hierarchies:

- **URL**: `/kanban/task/<task_id>/dependency-tree/`
- **Shows**:
  - Parent task (if exists)
  - All subtasks with nesting visualization
  - Related tasks (non-hierarchical connections)
  - Dependency level indicators
  - Task status and assignment information

#### Tree Visualization Features:
- Color-coded nodes:
  - Green: Parent tasks
  - Purple: Child tasks
  - Yellow: Related tasks
- Recursive rendering of multi-level hierarchies
- Click-through navigation between related tasks
- One-click linking from AI suggestions

### 3. AI-Suggested Task Dependencies

The system analyzes task descriptions to suggest potential dependencies:

#### How It Works:
1. Analyzes task titles and descriptions
2. Looks for keywords indicating parent-child relationships:
   - Parent indicators: "implement", "setup", "configure", "design", "architect"
   - Child indicators: "test", "validate", "verify", "debug", "fix", "optimize"
3. Calculates relatedness scores based on keyword overlap
4. Identifies blocking/dependent relationships
5. Returns ranked suggestions with confidence scores

#### Usage:

```python
from kanban.utils.dependency_suggestions import analyze_and_suggest_dependencies

# Analyze a task and get suggestions
result = analyze_and_suggest_dependencies(task, auto_link=False)

# Auto-link top parent suggestion if confidence > 0.7
result = analyze_and_suggest_dependencies(task, auto_link=True)
```

#### Management Command:
```bash
# Analyze all tasks
python manage.py analyze_task_dependencies

# Analyze specific board
python manage.py analyze_task_dependencies --board-id 5

# Analyze specific task
python manage.py analyze_task_dependencies --task-id 42

# Auto-link top suggestions
python manage.py analyze_task_dependencies --board-id 5 --auto-link
```

## API Endpoints

### Get Task Dependencies
```
GET /kanban/api/task/<task_id>/dependencies/
```
Returns all relationships (parents, children, related tasks) for a task.

### Set Parent Task
```
POST /kanban/api/task/<task_id>/set-parent/
Body: { "parent_task_id": <parent_id> }
```
Links a parent task or removes it if parent_task_id is null.

### Add Related Task
```
POST /kanban/api/task/<task_id>/add-related/
Body: { "related_task_id": <related_id> }
```
Adds a non-hierarchical relationship between tasks.

### Analyze Task Dependencies
```
POST /kanban/api/task/<task_id>/analyze-dependencies/
Body: { "auto_link": false }
```
Runs AI analysis and returns dependency suggestions.

### Get Dependency Tree
```
GET /kanban/api/task/<task_id>/dependency-tree/?include_related=false
```
Returns a hierarchical tree structure of dependencies.

### Get Board Dependency Graph
```
GET /kanban/api/board/<board_id>/dependency-graph/
Query: root_task_id (optional)
```
Returns all tasks and relationships for graph visualization.

## Admin Interface

The Django admin has been updated to manage dependencies:

1. **Task List View**: Shows parent_task column for quick reference
2. **Task Edit Form**: New "Task Dependencies" section with:
   - Parent task dropdown (with circular dependency prevention)
   - Related tasks multi-select
   - Read-only dependency chain visualization
3. **AI Suggestions**: Collapsible section showing:
   - AI-suggested dependencies
   - Last analysis timestamp

## Usage Examples

### Creating Task Hierarchies Programmatically

```python
from kanban.models import Task

# Create parent task
design_task = Task.objects.create(
    title="Design System Architecture",
    description="Design the overall system architecture",
    column=planning_column,
    created_by=user
)

# Create child task
api_task = Task.objects.create(
    title="Implement REST API",
    description="Build REST API endpoints",
    parent_task=design_task,  # Link to parent
    column=dev_column,
    created_by=user
)

# Create another child
test_task = Task.objects.create(
    title="API Unit Tests",
    description="Write unit tests for REST API",
    parent_task=api_task,  # Nested hierarchy
    column=test_column,
    created_by=user
)

# Link related tasks
documentation_task = Task.objects.create(
    title="API Documentation",
    description="Document the REST API endpoints",
    column=docs_column,
    created_by=user
)

api_task.related_tasks.add(documentation_task)
```

### Checking Circular Dependencies

```python
# Safe way to set parent
new_parent = Task.objects.get(id=5)

if not task.has_circular_dependency(new_parent):
    task.parent_task = new_parent
    task.save()
else:
    print("Cannot set this parent - would create circular dependency")
```

### Querying Task Hierarchies

```python
# Get all root tasks (no parent)
root_tasks = Task.objects.filter(parent_task__isnull=True)

# Get all leaf tasks (no children)
from django.db.models import Count
leaf_tasks = Task.objects.annotate(
    child_count=Count('subtasks')
).filter(child_count=0)

# Get all tasks at a specific level
all_parents = Task.objects.filter(parent_task__isnull=False)
```

## Django Migration

Run the migration to add dependency fields to your Task model:

```bash
python manage.py migrate kanban
```

This creates:
- `parent_task` ForeignKey field
- `related_tasks` ManyToMany through table
- `dependency_chain` JSON field
- `suggested_dependencies` JSON field
- `last_dependency_analysis` DateTime field

## Integration with Existing Features

### Risk Management
Dependencies are considered in risk assessment:
- Subtasks inherit some risk factors from parent
- Blocked tasks can be identified through dependencies
- Critical path analysis uses dependency chains

### Resource Forecasting
Dependency information helps with:
- Understanding task prerequisites
- Better scheduling recommendations
- Identifying potential bottlenecks

### AI Features
Existing AI features now have access to:
- Task dependency information
- Task hierarchy context
- Related task descriptions for better analysis

## Performance Considerations

### Query Optimization
When working with dependencies, use select_related and prefetch_related:

```python
# Optimized query
tasks = Task.objects.select_related(
    'parent_task',
    'column__board'
).prefetch_related(
    'subtasks',
    'related_tasks'
)
```

### Large Hierarchies
For tasks with many subtasks, consider pagination:

```python
subtasks = task.subtasks.all()[:50]  # Limit in view
```

### Analysis Performance
AI analysis is optimized but can be slow for very large boards. Consider:
- Running analysis as a background task for many tasks
- Analyzing specific columns rather than entire board
- Using `auto_link=False` for manual review of suggestions

## Troubleshooting

### Circular Dependency Error
If you get "This would create a circular dependency":
- The parent task you're trying to link is already a descendant
- Rearrange your hierarchy first
- Check `task.get_all_subtasks()` to see the current structure

### Missing Suggestions
If AI suggestions are empty:
- Task descriptions may be too short (need 20+ characters)
- No similar tasks exist on the board
- Low keyword matching with other tasks
- Check `last_dependency_analysis` timestamp

### Performance Issues
If the dependency tree is slow:
- Board has too many tasks with deep hierarchies
- Consider archiving or splitting old projects
- Use the management command with `--board-id` for targeted analysis

## Advanced: Custom Analysis

You can extend the AI analysis logic:

```python
from kanban.utils.dependency_suggestions import DependencyAnalyzer

# Create custom analyzer
analyzer = DependencyAnalyzer()

# Analyze with custom keywords
custom_result = analyzer.analyze_task_description(task, board)

# Customize scoring
score = analyzer._calculate_parent_relationship_score(
    desc1, desc2, task1, task2
)
```

## Files Modified/Added

### New Files:
- `kanban/utils/dependency_suggestions.py` - Core analysis engine
- `kanban/management/commands/analyze_task_dependencies.py` - CLI command
- `templates/kanban/dependency_tree.html` - Visualization template

### Modified Files:
- `kanban/models.py` - Added dependency fields and methods
- `kanban/admin.py` - Enhanced Task admin interface
- `kanban/api_views.py` - Added 6 new API endpoints
- `kanban/views.py` - Added 2 new view functions
- `kanban/urls.py` - Added routing for new features
- `kanban/migrations/0009_task_dependencies.py` - Database migration

## Testing

Run the dependency analysis on your board:

```bash
# Analyze a single task
curl -X POST http://localhost:8000/kanban/api/task/1/analyze-dependencies/ \
  -H "Content-Type: application/json" \
  -d '{"auto_link": false}'

# Get dependency tree
curl http://localhost:8000/kanban/api/task/1/dependency-tree/

# Get board graph
curl http://localhost:8000/kanban/api/board/1/dependency-graph/
```

## Future Enhancements

Possible future improvements:
1. **Advanced Visualizations**: D3.js or vis.js based graph rendering
2. **Automatic Scheduling**: Schedule subtasks based on parent completion
3. **Gantt Chart Integration**: Visual timeline based on dependencies
4. **Workflow Enforcement**: Prevent moving tasks until dependencies met
5. **Dependency Notifications**: Alert when related tasks complete
6. **Custom Analysis Models**: Train on your project's specific patterns

## Support & Questions

For issues or questions:
1. Check the troubleshooting section above
2. Review the API endpoint documentation
3. Check logs: `tail -f logs/kanban.log`
4. Run migrations: `python manage.py migrate`
5. Rebuild the database index: `python manage.py rebuild_index`

---

**Version**: 1.0  
**Last Updated**: October 24, 2025  
**Source**: Integrated from ReqManager project
