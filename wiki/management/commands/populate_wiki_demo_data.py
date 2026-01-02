"""
Management command to populate wiki demo data for the Demo - Acme Corporation organization.
Creates categories, pages of different types, and links to tasks.

Usage:
    python manage.py populate_wiki_demo_data
"""
from django.core.management.base import BaseCommand
from django.contrib.auth.models import User
from django.utils import timezone
from django.db import transaction
from datetime import timedelta

from wiki.models import WikiPage, WikiCategory, WikiLink
from kanban.models import Board, Task
from accounts.models import Organization


class Command(BaseCommand):
    help = 'Populate wiki demo data for the demo organization'

    def add_arguments(self, parser):
        parser.add_argument(
            '--reset',
            action='store_true',
            help='Delete existing wiki demo data before creating new data',
        )

    def handle(self, *args, **options):
        self.stdout.write('=' * 80)
        self.stdout.write('POPULATING WIKI DEMO DATA')
        self.stdout.write('=' * 80)

        # Get demo organization
        try:
            demo_org = Organization.objects.get(name='Demo - Acme Corporation')
            self.stdout.write(self.style.SUCCESS(f'✓ Found organization: {demo_org.name}'))
        except Organization.DoesNotExist:
            self.stdout.write(self.style.ERROR('✗ Demo - Acme Corporation not found!'))
            self.stdout.write('  Please run: python manage.py create_demo_organization')
            return

        # Get a demo user to be the author
        demo_user = User.objects.filter(profile__organization=demo_org).first()
        if not demo_user:
            demo_user = User.objects.filter(username='demo_admin_solo').first()
        if not demo_user:
            demo_user = User.objects.filter(is_superuser=True).first()

        if not demo_user:
            self.stdout.write(self.style.ERROR('✗ No suitable user found to create wiki content!'))
            return

        self.stdout.write(self.style.SUCCESS(f'✓ Using author: {demo_user.username}'))

        # Get demo boards and tasks for linking
        demo_boards = Board.objects.filter(organization=demo_org)
        demo_tasks = Task.objects.filter(column__board__in=demo_boards)

        self.stdout.write(f'  Found {demo_boards.count()} demo boards')
        self.stdout.write(f'  Found {demo_tasks.count()} demo tasks')

        # Reset if requested
        if options['reset']:
            self.reset_wiki_data(demo_org)

        with transaction.atomic():
            # Create categories
            categories = self.create_categories(demo_org)
            
            # Create pages
            pages = self.create_pages(demo_org, demo_user, categories)
            
            # Link pages to tasks
            links = self.create_links(demo_org, demo_user, demo_tasks, demo_boards)

        # Summary
        self.stdout.write('')
        self.stdout.write(self.style.SUCCESS('=' * 80))
        self.stdout.write(self.style.SUCCESS('✓ WIKI DEMO DATA COMPLETE'))
        self.stdout.write(self.style.SUCCESS('=' * 80))
        self.stdout.write(f'  Categories: {len(categories)}')
        self.stdout.write(f'  Wiki pages: {len(pages)}')
        self.stdout.write(f'  Task/Board links: {links}')
        self.stdout.write('')

    def reset_wiki_data(self, demo_org):
        """Delete existing wiki demo data"""
        self.stdout.write('\nResetting wiki demo data...')
        
        # Delete wiki links first
        WikiLink.objects.filter(wiki_page__organization=demo_org).delete()
        
        # Delete wiki pages
        pages_deleted = WikiPage.objects.filter(organization=demo_org).delete()
        self.stdout.write(f'  Deleted {pages_deleted[0]} wiki pages')
        
        # Delete categories
        cats_deleted = WikiCategory.objects.filter(organization=demo_org).delete()
        self.stdout.write(f'  Deleted {cats_deleted[0]} categories')
        
        self.stdout.write(self.style.SUCCESS('  ✓ Wiki data reset complete'))

    def create_categories(self, demo_org):
        """Create wiki categories"""
        self.stdout.write('\n1. Creating Wiki Categories...')

        categories_data = [
            {
                'name': 'Getting Started',
                'slug': 'getting-started',
                'description': 'Onboarding guides, tutorials, and quick start documentation for new team members.',
                'icon': 'rocket',
                'color': '#3498db',
                'ai_assistant_type': 'documentation',
                'position': 1,
            },
            {
                'name': 'Technical Documentation',
                'slug': 'technical-docs',
                'description': 'API references, architecture diagrams, and technical specifications.',
                'icon': 'code',
                'color': '#9b59b6',
                'ai_assistant_type': 'documentation',
                'position': 2,
            },
            {
                'name': 'Meeting Notes',
                'slug': 'meeting-notes',
                'description': 'Team meeting notes, standup summaries, and sprint retrospectives.',
                'icon': 'calendar',
                'color': '#2ecc71',
                'ai_assistant_type': 'meeting',
                'position': 3,
            },
            {
                'name': 'Process & Workflows',
                'slug': 'process-workflows',
                'description': 'Standard operating procedures, workflows, and best practices.',
                'icon': 'sitemap',
                'color': '#e74c3c',
                'ai_assistant_type': 'documentation',
                'position': 4,
            },
            {
                'name': 'Project Resources',
                'slug': 'project-resources',
                'description': 'Project-specific documentation, requirements, and specifications.',
                'icon': 'folder-open',
                'color': '#f39c12',
                'ai_assistant_type': 'documentation',
                'position': 5,
            },
        ]

        created_categories = {}

        for cat_data in categories_data:
            category, created = WikiCategory.objects.update_or_create(
                organization=demo_org,
                slug=cat_data['slug'],
                defaults={
                    'name': cat_data['name'],
                    'description': cat_data['description'],
                    'icon': cat_data['icon'],
                    'color': cat_data['color'],
                    'ai_assistant_type': cat_data['ai_assistant_type'],
                    'position': cat_data['position'],
                }
            )
            created_categories[cat_data['slug']] = category
            status = "Created" if created else "Updated"
            self.stdout.write(f'  {status}: {category.name}')

        return created_categories

    def create_pages(self, demo_org, demo_user, categories):
        """Create wiki pages"""
        self.stdout.write('\n2. Creating Wiki Pages...')

        pages_data = self.get_pages_data()
        created_pages = []

        for page_data in pages_data:
            category = categories.get(page_data['category'])
            if not category:
                continue

            page, created = WikiPage.objects.update_or_create(
                organization=demo_org,
                slug=page_data['slug'],
                defaults={
                    'title': page_data['title'],
                    'content': page_data['content'],
                    'category': category,
                    'created_by': demo_user,
                    'updated_by': demo_user,
                    'is_published': True,
                    'is_pinned': page_data.get('is_pinned', False),
                    'tags': page_data.get('tags', []),
                    'view_count': 0,
                }
            )
            created_pages.append(page)
            status = "Created" if created else "Updated"
            self.stdout.write(f'  {status}: {page.title}')

        return created_pages

    def create_links(self, demo_org, demo_user, demo_tasks, demo_boards):
        """Link wiki pages to tasks and boards"""
        self.stdout.write('\n3. Linking Wiki Pages to Tasks...')

        links_created = 0

        # Find pages to link
        api_doc = WikiPage.objects.filter(organization=demo_org, slug='api-documentation').first()
        coding_standards = WikiPage.objects.filter(organization=demo_org, slug='coding-standards').first()
        sprint_planning = WikiPage.objects.filter(organization=demo_org, slug='sprint-45-planning').first()
        architecture = WikiPage.objects.filter(organization=demo_org, slug='system-architecture').first()
        feature_req = WikiPage.objects.filter(organization=demo_org, slug='feature-req-ai-dashboard').first()

        # Link API documentation to API-related tasks
        if api_doc and demo_tasks.exists():
            api_tasks = demo_tasks.filter(title__icontains='api')[:3]
            for task in api_tasks:
                _, created = WikiLink.objects.get_or_create(
                    wiki_page=api_doc,
                    link_type='task',
                    task=task,
                    defaults={
                        'created_by': demo_user,
                        'description': 'Related API documentation'
                    }
                )
                if created:
                    links_created += 1
                    self.stdout.write(f"  Linked: '{api_doc.title}' → '{task.title}'")

        # Link coding standards to code-related tasks
        if coding_standards and demo_tasks.exists():
            code_tasks = demo_tasks.filter(title__iregex=r'(code|review|refactor|implement)')[:3]
            for task in code_tasks:
                _, created = WikiLink.objects.get_or_create(
                    wiki_page=coding_standards,
                    link_type='task',
                    task=task,
                    defaults={
                        'created_by': demo_user,
                        'description': 'Follow coding standards'
                    }
                )
                if created:
                    links_created += 1
                    self.stdout.write(f"  Linked: '{coding_standards.title}' → '{task.title}'")

        # Link sprint planning to high priority tasks
        if sprint_planning and demo_tasks.exists():
            high_priority_tasks = demo_tasks.filter(priority='high')[:2]
            for task in high_priority_tasks:
                _, created = WikiLink.objects.get_or_create(
                    wiki_page=sprint_planning,
                    link_type='task',
                    task=task,
                    defaults={
                        'created_by': demo_user,
                        'description': 'Discussed in sprint planning'
                    }
                )
                if created:
                    links_created += 1
                    self.stdout.write(f"  Linked: '{sprint_planning.title}' → '{task.title}'")

        # Link architecture doc to design/infrastructure tasks
        if architecture and demo_tasks.exists():
            arch_tasks = demo_tasks.filter(title__iregex=r'(design|architect|infrastructure|setup)')[:2]
            for task in arch_tasks:
                _, created = WikiLink.objects.get_or_create(
                    wiki_page=architecture,
                    link_type='task',
                    task=task,
                    defaults={
                        'created_by': demo_user,
                        'description': 'Architecture reference'
                    }
                )
                if created:
                    links_created += 1
                    self.stdout.write(f"  Linked: '{architecture.title}' → '{task.title}'")

        # Link feature requirements to feature tasks
        if feature_req and demo_tasks.exists():
            feature_tasks = demo_tasks.filter(title__iregex=r'(dashboard|ai|feature|analytics)')[:2]
            for task in feature_tasks:
                _, created = WikiLink.objects.get_or_create(
                    wiki_page=feature_req,
                    link_type='task',
                    task=task,
                    defaults={
                        'created_by': demo_user,
                        'description': 'Feature requirements document'
                    }
                )
                if created:
                    links_created += 1
                    self.stdout.write(f"  Linked: '{feature_req.title}' → '{task.title}'")

        # Link wiki pages to boards
        if demo_boards.exists():
            software_board = demo_boards.filter(name__icontains='software').first()
            if software_board and coding_standards:
                _, created = WikiLink.objects.get_or_create(
                    wiki_page=coding_standards,
                    link_type='board',
                    board=software_board,
                    defaults={
                        'created_by': demo_user,
                        'description': 'Development standards for this project'
                    }
                )
                if created:
                    links_created += 1
                    self.stdout.write(f"  Linked: '{coding_standards.title}' → Board: '{software_board.name}'")

        return links_created

    def get_pages_data(self):
        """Return wiki page content data"""
        current_date = timezone.now().strftime('%B %d, %Y')
        past_date = (timezone.now() - timedelta(days=3)).strftime('%B %d, %Y')
        retro_date = (timezone.now() - timedelta(days=14)).strftime('%B %d, %Y')
        release_date = (timezone.now() - timedelta(days=7)).strftime('%B %d, %Y')

        return [
            # --- GETTING STARTED ---
            {
                'category': 'getting-started',
                'title': 'Welcome to Acme Corporation',
                'slug': 'welcome-to-acme',
                'is_pinned': True,
                'tags': ['onboarding', 'welcome', 'intro'],
                'content': f"""# Welcome to Acme Corporation! 🎉

Welcome to the team! This knowledge hub contains everything you need to get started and succeed at Acme Corporation.

## Quick Links

- **[Team Setup Guide](team-setup-guide)** - Set up your development environment
- **[Coding Standards](coding-standards)** - Our code quality guidelines
- **[Sprint Process](sprint-workflow)** - How we run sprints

## Who to Contact

| Role | Person | Contact |
|------|--------|---------|
| Project Manager | Alex Chen | alex.chen@acme.com |
| Lead Developer | Sam Rivera | sam.rivera@acme.com |
| Stakeholder | Jordan Taylor | jordan.taylor@acme.com |

## First Week Checklist

- [ ] Complete IT security training
- [ ] Set up development environment
- [ ] Meet with your team lead
- [ ] Review current sprint tasks
- [ ] Attend daily standups

## Our Values

1. **Quality First** - We don't ship until it's ready
2. **Collaboration** - We succeed together
3. **Continuous Learning** - Always be improving
4. **Customer Focus** - Everything we do serves our users

---

*Last updated: {current_date}*
"""
            },
            {
                'category': 'getting-started',
                'title': 'Team Setup Guide',
                'slug': 'team-setup-guide',
                'is_pinned': False,
                'tags': ['setup', 'environment', 'installation'],
                'content': """# Team Setup Guide

This guide will help you set up your development environment from scratch.

## Prerequisites

- Python 3.10+ installed
- Node.js 18+ installed
- Git configured with SSH keys
- VS Code or your preferred IDE

## Step 1: Clone the Repository

```bash
git clone git@github.com:acme-corp/main-project.git
cd main-project
```

## Step 2: Backend Setup

```bash
# Create virtual environment
python -m venv venv
source venv/bin/activate  # On Windows: venv\\Scripts\\activate

# Install dependencies
pip install -r requirements.txt

# Run migrations
python manage.py migrate

# Create test data
python manage.py populate_demo_data
```

## Step 3: Frontend Setup

```bash
cd frontend
npm install
npm run dev
```

## Step 4: Run Tests

```bash
# Backend tests
python manage.py test

# Frontend tests
npm test
```

## Common Issues

### Database Connection Error
Make sure PostgreSQL is running and the credentials in `.env` are correct.

### Node modules issues
Try deleting `node_modules` and running `npm install` again.

## Next Steps

Once your environment is set up, check out:
- The [Coding Standards](coding-standards) page
- Your assigned tasks on the board

---

*Need help? Reach out in #dev-support on Slack*
"""
            },
            {
                'category': 'getting-started',
                'title': 'New Employee Onboarding Checklist',
                'slug': 'onboarding-checklist',
                'is_pinned': False,
                'tags': ['onboarding', 'hr', 'checklist'],
                'content': """# New Employee Onboarding Checklist

## Week 1: Getting Started

### Day 1
- [ ] Receive laptop and equipment
- [ ] Complete HR paperwork
- [ ] Get access badges and security setup
- [ ] Meet with manager for welcome meeting
- [ ] Review company policies

### Day 2-3
- [ ] Complete mandatory security training
- [ ] Set up development environment
- [ ] Get access to all required systems
- [ ] Introduction to team members
- [ ] Review current project documentation

### Day 4-5
- [ ] Shadow a team member
- [ ] Attend first standup meeting
- [ ] Review sprint board and backlog
- [ ] Get assigned first starter task

## Week 2: Deep Dive

- [ ] Complete product training
- [ ] Review architecture documentation
- [ ] Pair programming session
- [ ] Complete first pull request
- [ ] 1:1 meeting with manager

## Week 3-4: Contribution

- [ ] Take ownership of assigned tasks
- [ ] Participate actively in sprint ceremonies
- [ ] Complete 30-day feedback session
- [ ] Identify areas of interest for growth

## Resources

- IT Help Desk: help@acme.com
- HR Questions: hr@acme.com
- Buddy Program: Ask your manager

---

*Updated for 2026 onboarding process*
"""
            },

            # --- TECHNICAL DOCUMENTATION ---
            {
                'category': 'technical-docs',
                'title': 'API Documentation',
                'slug': 'api-documentation',
                'is_pinned': True,
                'tags': ['api', 'rest', 'documentation', 'reference'],
                'content': """# API Documentation

## Overview

Our REST API provides programmatic access to all platform features. This document covers authentication, endpoints, and common use cases.

## Authentication

All API requests require authentication via JWT tokens.

```bash
# Get access token
POST /api/auth/token/
Content-Type: application/json

{
    "email": "user@example.com",
    "password": "your_password"
}
```

Response:
```json
{
    "access": "eyJ0eXAiOiJKV1...",
    "refresh": "eyJ0eXAiOiJKV1..."
}
```

## Core Endpoints

### Boards

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/boards/` | List all boards |
| POST | `/api/boards/` | Create new board |
| GET | `/api/boards/{id}/` | Get board details |
| PUT | `/api/boards/{id}/` | Update board |
| DELETE | `/api/boards/{id}/` | Delete board |

### Tasks

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/tasks/` | List tasks |
| POST | `/api/tasks/` | Create task |
| PATCH | `/api/tasks/{id}/` | Update task |
| DELETE | `/api/tasks/{id}/` | Delete task |

## Rate Limiting

- Standard tier: 1000 requests/hour
- Premium tier: 10000 requests/hour

## Error Codes

| Code | Description |
|------|-------------|
| 400 | Bad Request - Invalid parameters |
| 401 | Unauthorized - Invalid token |
| 403 | Forbidden - Insufficient permissions |
| 404 | Not Found |
| 429 | Too Many Requests |

## SDKs

- Python: `pip install acme-sdk`
- JavaScript: `npm install @acme/sdk`

---

*See the [full API reference](https://api.acme.com/docs) for complete documentation.*
"""
            },
            {
                'category': 'technical-docs',
                'title': 'Coding Standards',
                'slug': 'coding-standards',
                'is_pinned': False,
                'tags': ['coding', 'standards', 'best-practices', 'style'],
                'content': '''# Coding Standards

## Overview

This document outlines our coding standards and best practices. Following these guidelines ensures code quality, readability, and maintainability.

## Python Standards

### Style Guide
We follow PEP 8 with some modifications:
- Line length: 100 characters (not 79)
- Use type hints for all function signatures
- Docstrings for all public functions and classes

### Example

```python
from typing import Optional, List

def calculate_task_priority(
    task: Task,
    dependencies: List[Task],
    deadline: Optional[datetime] = None
) -> int:
    """
    Calculate priority score for a task based on dependencies and deadline.
    
    Args:
        task: The task to evaluate
        dependencies: List of dependent tasks
        deadline: Optional deadline override
        
    Returns:
        Priority score from 1-100
    """
    base_score = task.base_priority
    
    if dependencies:
        base_score += len(dependencies) * 5
        
    if deadline and deadline < timezone.now():
        base_score += 20
        
    return min(100, base_score)
```

## JavaScript/TypeScript Standards

### Naming Conventions
- Components: PascalCase (`TaskCard.tsx`)
- Hooks: camelCase with `use` prefix (`useTaskData.ts`)
- Utilities: camelCase (`formatDate.ts`)

### Example

```typescript
interface TaskCardProps {
  task: Task;
  onStatusChange: (status: TaskStatus) => void;
  isEditable?: boolean;
}

export const TaskCard: React.FC<TaskCardProps> = ({
  task,
  onStatusChange,
  isEditable = true,
}) => {
  const { updateTask } = useTaskMutation();
  
  return (
    <Card className="task-card">
      {/* Component content */}
    </Card>
  );
};
```

## Code Review Checklist

- [ ] Code follows style guidelines
- [ ] All tests pass
- [ ] New code has test coverage
- [ ] No security vulnerabilities
- [ ] Documentation updated if needed
- [ ] No hardcoded values

## Tools

- **Linting**: ESLint, Flake8, Black
- **Testing**: pytest, Jest
- **CI/CD**: GitHub Actions

---

*Questions? Ask in #code-review on Slack*
'''
            },
            {
                'category': 'technical-docs',
                'title': 'System Architecture Overview',
                'slug': 'system-architecture',
                'is_pinned': False,
                'tags': ['architecture', 'system', 'design', 'infrastructure'],
                'content': """# System Architecture Overview

## High-Level Architecture

```
+-------------------------------------------------------------+
|                     Client Applications                      |
|  +-----------+  +-----------+  +-----------+                |
|  |  Web App  |  | Mobile App|  |  Desktop  |                |
|  |  (React)  |  |  (React   |  |   App     |                |
|  |           |  |   Native) |  |           |                |
|  +-----+-----+  +-----+-----+  +-----+-----+                |
+--------+---------------+---------------+--------------------+
         |               |               |
         +-------+-------+-------+-------+
                 |
          +------v------+
          |   API       |
          |   Gateway   |
          |  (Kong)     |
          +------+------+
                 |
     +-----------+-----------+
     |           |           |
+----v----+ +----v----+ +----v----+
| Auth    | | Core API| | AI      |
| Service | | (Django)| | Service |
+----+----+ +----+----+ +----+----+
     |           |           |
     +-----+-----+-----+-----+
           |           |
    +------v------+ +--v-------+
    | PostgreSQL  | |  Redis   |
    |  Database   | |  Cache   |
    +-------------+ +----------+
```

## Components

### API Gateway
- **Kong** for request routing, rate limiting, and authentication
- Handles all incoming traffic and routes to appropriate services

### Core API
- **Django REST Framework** for main application logic
- Handles boards, tasks, users, and business logic
- Connects to PostgreSQL for persistent storage

### AI Service
- Separate microservice for AI/ML features
- Handles task suggestions, resource optimization
- Uses dedicated GPU instances when needed

### Authentication
- JWT-based authentication
- OAuth2 integration for SSO
- Session management with Redis

## Data Flow

1. Client makes request through API Gateway
2. Gateway validates token and rate limits
3. Request routed to appropriate service
4. Service processes request, queries database
5. Response cached in Redis if applicable
6. Response returned to client

## Deployment

- **Kubernetes** for container orchestration
- **AWS** for cloud infrastructure
- **Terraform** for infrastructure as code

## Monitoring

- **Datadog** for metrics and logging
- **Sentry** for error tracking
- **PagerDuty** for alerting

---

*For detailed infrastructure docs, see the DevOps wiki*
"""
            },
            {
                'category': 'technical-docs',
                'title': 'Database Schema Reference',
                'slug': 'database-schema',
                'is_pinned': False,
                'tags': ['database', 'schema', 'postgresql', 'models'],
                'content': """# Database Schema Reference

## Core Tables

### Users & Organizations

```sql
-- Organizations
CREATE TABLE organizations (
    id SERIAL PRIMARY KEY,
    name VARCHAR(100) NOT NULL,
    domain VARCHAR(100) NOT NULL,
    created_at TIMESTAMP DEFAULT NOW(),
    is_demo BOOLEAN DEFAULT FALSE
);

-- User Profiles  
CREATE TABLE user_profiles (
    id SERIAL PRIMARY KEY,
    user_id INTEGER REFERENCES auth_user(id),
    organization_id INTEGER REFERENCES organizations(id),
    is_admin BOOLEAN DEFAULT FALSE,
    skills JSONB DEFAULT '[]',
    weekly_capacity_hours INTEGER DEFAULT 40
);
```

### Boards & Tasks

```sql
-- Boards
CREATE TABLE boards (
    id SERIAL PRIMARY KEY,
    name VARCHAR(100) NOT NULL,
    description TEXT,
    organization_id INTEGER REFERENCES organizations(id),
    created_at TIMESTAMP DEFAULT NOW()
);

-- Columns
CREATE TABLE columns (
    id SERIAL PRIMARY KEY,
    board_id INTEGER REFERENCES boards(id),
    name VARCHAR(100) NOT NULL,
    position INTEGER DEFAULT 0,
    wip_limit INTEGER
);

-- Tasks
CREATE TABLE tasks (
    id SERIAL PRIMARY KEY,
    column_id INTEGER REFERENCES columns(id),
    title VARCHAR(255) NOT NULL,
    description TEXT,
    assigned_to_id INTEGER REFERENCES auth_user(id),
    priority VARCHAR(20) DEFAULT 'medium',
    progress INTEGER DEFAULT 0,
    due_date DATE,
    created_at TIMESTAMP DEFAULT NOW()
);
```

## Indexes

```sql
-- Performance indexes
CREATE INDEX idx_tasks_column ON tasks(column_id);
CREATE INDEX idx_tasks_assignee ON tasks(assigned_to_id);
CREATE INDEX idx_tasks_due_date ON tasks(due_date);
CREATE INDEX idx_boards_org ON boards(organization_id);
```

## Common Queries

### Get all tasks for a user

```sql
SELECT t.*, c.name as column_name, b.name as board_name
FROM tasks t
JOIN columns c ON t.column_id = c.id
JOIN boards b ON c.board_id = b.id
WHERE t.assigned_to_id = :user_id
ORDER BY t.due_date;
```

### Get board statistics

```sql
SELECT 
    b.name,
    COUNT(t.id) as total_tasks,
    SUM(CASE WHEN t.progress = 100 THEN 1 ELSE 0 END) as completed,
    AVG(t.progress) as avg_progress
FROM boards b
JOIN columns c ON c.board_id = b.id
JOIN tasks t ON t.column_id = c.id
WHERE b.organization_id = :org_id
GROUP BY b.id;
```

## Migrations

All schema changes must be done through Django migrations:

```bash
# Create migration
python manage.py makemigrations

# Apply migrations
python manage.py migrate

# Check migration status
python manage.py showmigrations
```

---

*See Django models for authoritative schema definition*
"""
            },

            # --- MEETING NOTES ---
            {
                'category': 'meeting-notes',
                'title': 'Sprint 45 Planning Meeting',
                'slug': 'sprint-45-planning',
                'is_pinned': True,
                'tags': ['sprint', 'planning', 'meeting'],
                'content': f"""# Sprint 45 Planning Meeting

**Date:** {past_date}  
**Attendees:** Alex Chen, Sam Rivera, Jordan Taylor  
**Duration:** 60 minutes

## Sprint Goals

1. Complete user authentication improvements
2. Launch new dashboard analytics feature
3. Fix critical bugs from Sprint 44
4. Improve test coverage to 80%

## Backlog Items Selected

### High Priority
- **AUTH-234**: Implement password reset flow
- **DASH-567**: Add burndown chart widget
- **BUG-789**: Fix session timeout issue

### Medium Priority
- **UI-123**: Update navigation menu design
- **API-456**: Add rate limiting to public endpoints

### Nice to Have
- **DOC-101**: Update API documentation

## Capacity Planning

| Team Member | Capacity | Assigned Points |
|-------------|----------|-----------------|
| Alex Chen | 8 pts | 6 pts |
| Sam Rivera | 10 pts | 9 pts |
| Jordan Taylor | 5 pts | 4 pts |

**Total Sprint Capacity:** 23 points

## Risks & Dependencies

- **Risk:** Third-party auth provider maintenance window on Thursday
- **Dependency:** Design assets for UI-123 needed by Wednesday
- **Blocker:** Waiting for security review on AUTH-234

## Action Items

- [ ] @Alex: Create detailed task breakdown for AUTH-234
- [ ] @Sam: Set up monitoring for new endpoints
- [ ] @Jordan: Coordinate with stakeholders on dashboard requirements

## Next Steps

- Daily standups at 9:30 AM
- Mid-sprint check on Wednesday
- Sprint review next Friday at 2 PM

---

*Notes taken by Alex Chen*
"""
            },
            {
                'category': 'meeting-notes',
                'title': 'Weekly Team Standup - Week 1',
                'slug': 'standup-week-1',
                'is_pinned': False,
                'tags': ['standup', 'weekly', 'team'],
                'content': f"""# Weekly Team Standup Summary

**Week of:** {current_date}  
**Facilitator:** Sam Rivera

## Team Updates

### Alex Chen - Project Manager
**Yesterday:**
- Reviewed sprint backlog and reprioritized items
- Met with stakeholders about Q1 roadmap
- Completed resource allocation for next sprint

**Today:**
- Sprint planning meeting
- 1:1s with team members
- Update project timeline

**Blockers:** None

---

### Sam Rivera - Lead Developer
**Yesterday:**
- Completed API endpoint for user preferences
- Code review for authentication PR
- Fixed 2 bugs from QA testing

**Today:**
- Implement caching layer for dashboard
- Help onboard new team member
- Continue authentication improvements

**Blockers:** Waiting for database migration approval

---

### Jordan Taylor - Business Analyst
**Yesterday:**
- Gathered requirements for new reporting feature
- Created wireframes for stakeholder review
- Updated user stories with acceptance criteria

**Today:**
- Stakeholder presentation at 2 PM
- Document API requirements for integration
- Sprint demo preparation

**Blockers:** Need access to production analytics

---

## Team Announcements

1. **Code freeze** for release 2.5 is this Thursday
2. **Company all-hands** meeting Friday at 3 PM
3. **New team member** starting next Monday

## Action Items

- @Sam: Submit database migration request today
- @Alex: Get Jordan production analytics access
- @All: Complete timesheet entries by Friday

---

*Next standup: Monday 9:30 AM*
"""
            },
            {
                'category': 'meeting-notes',
                'title': 'Sprint 44 Retrospective',
                'slug': 'sprint-44-retro',
                'is_pinned': False,
                'tags': ['retrospective', 'sprint', 'improvement'],
                'content': f"""# Sprint 44 Retrospective

**Date:** {retro_date}  
**Facilitator:** Jordan Taylor  
**Format:** Start, Stop, Continue

---

## What Went Well (Continue)

- **Daily standups** - Great for keeping everyone aligned
- **Pair programming sessions** - Helped knowledge sharing
- **Early testing** - Caught bugs before code review
- **Clear sprint goals** - Everyone knew priorities
- **Code review turnaround** - < 24 hours on average

## What Didn't Work (Stop)

- **Too many meetings** on Tuesdays - Need to consolidate
- **Scope creep** mid-sprint - Better backlog grooming needed
- **Late specification changes** - Requirements should be final before sprint
- **Silent Slack channels** - Need more async communication

## New Ideas (Start)

- **Tech debt Friday** - Dedicate time for cleanup
- **Demo preparation day** - Don't rush demos
- **Documentation as part of DoD** - Include in definition of done
- **Buddy system for PRs** - Assign reviewers upfront

---

## Sprint Statistics

| Metric | Target | Actual |
|--------|--------|--------|
| Story Points | 25 | 22 |
| Bugs Fixed | 10 | 12 |
| Test Coverage | 75% | 73% |
| Velocity | 25 | 22 |

## Action Items

| Action | Owner | Due |
|--------|-------|-----|
| Consolidate Tuesday meetings | Alex | Next sprint |
| Create tech debt backlog | Sam | This week |
| Update Definition of Done | Jordan | Tomorrow |
| Set up PR auto-assign | Sam | This week |

---

## Team Mood

Overall team satisfaction: **7.5/10** (up from 7.0 last sprint)

### Individual Feedback
- "Feeling good about velocity" - Sam
- "Better work-life balance this sprint" - Alex  
- "More visibility into blockers" - Jordan

---

*Great job team! Let's keep improving!*
"""
            },

            # --- PROCESS & WORKFLOWS ---
            {
                'category': 'process-workflows',
                'title': 'Sprint Workflow Guide',
                'slug': 'sprint-workflow',
                'is_pinned': True,
                'tags': ['sprint', 'agile', 'scrum', 'workflow'],
                'content': """# Sprint Workflow Guide

## Overview

We follow a modified Scrum framework with 2-week sprints. This guide outlines our sprint process from planning to retrospective.

## Sprint Timeline

```
Week 1                          Week 2
Mon  | Tue  | Wed  | Thu  | Fri  || Mon  | Tue  | Wed  | Thu  | Fri
PLAN |  W   |  W   |  W   |  W   ||  W   |  W   |  W   | DEMO | RETRO
```

## Sprint Ceremonies

### 1. Sprint Planning (Monday Week 1)
- **Duration:** 2 hours
- **Participants:** Entire team
- **Objectives:**
  - Review and refine backlog items
  - Commit to sprint goals
  - Break down tasks and estimate

### 2. Daily Standups
- **Duration:** 15 minutes
- **Time:** 9:30 AM daily
- **Format:** Each person answers:
  1. What did you do yesterday?
  2. What will you do today?
  3. Any blockers?

### 3. Sprint Review/Demo (Thursday Week 2)
- **Duration:** 1 hour
- **Participants:** Team + stakeholders
- **Objectives:**
  - Demo completed work
  - Gather feedback
  - Celebrate achievements

### 4. Sprint Retrospective (Friday Week 2)
- **Duration:** 1 hour
- **Participants:** Team only
- **Objectives:**
  - Reflect on what worked
  - Identify improvements
  - Create action items

## Task States

| State | Description | WIP Limit |
|-------|-------------|-----------|
| To Do | Ready to start | No limit |
| In Progress | Currently being worked on | 3 per person |
| Code Review | Awaiting review | 5 total |
| Testing | In QA testing | 5 total |
| Done | Completed and deployed | No limit |

## Definition of Done

A task is "Done" when:
- [ ] Code is complete and pushed
- [ ] All tests pass
- [ ] Code review approved
- [ ] Documentation updated
- [ ] QA testing passed
- [ ] Deployed to staging

## Tips for Success

1. **Don't overcommit** - It's better to complete everything than to carry over
2. **Raise blockers early** - Don't wait until standup
3. **Collaborate** - Pair programming and mob sessions are encouraged
4. **Document as you go** - Don't leave it for the end

---

*Questions? Ask in #agile-help on Slack*
"""
            },
            {
                'category': 'process-workflows',
                'title': 'Code Review Guidelines',
                'slug': 'code-review-guidelines',
                'is_pinned': False,
                'tags': ['code-review', 'pr', 'guidelines', 'quality'],
                'content': """# Code Review Guidelines

## Purpose

Code reviews are essential for maintaining code quality, sharing knowledge, and catching bugs early. This document outlines our code review process and expectations.

## Before Requesting Review

### Author Checklist

Before submitting a PR for review:

- [ ] Self-review your changes first
- [ ] All tests pass locally
- [ ] Code follows our style guidelines
- [ ] No debug code or console.logs
- [ ] PR description is clear and complete
- [ ] Related issue is linked
- [ ] Screenshots/videos for UI changes

### PR Description Template

```markdown
## Summary
Brief description of changes

## Type of Change
- [ ] Bug fix
- [ ] New feature
- [ ] Breaking change
- [ ] Documentation update

## Testing Done
- [ ] Unit tests added/updated
- [ ] Manual testing completed
- [ ] Edge cases covered

## Screenshots (if applicable)

## Related Issues
Fixes #123
```

## Reviewer Guidelines

### What to Look For

1. **Correctness**
   - Does the code do what it's supposed to?
   - Are edge cases handled?
   - Any potential bugs?

2. **Design**
   - Is the solution well-designed?
   - Does it follow our patterns?
   - Is it maintainable?

3. **Performance**
   - Any performance concerns?
   - N+1 queries?
   - Memory leaks?

4. **Security**
   - Any security vulnerabilities?
   - Input validation?
   - Proper authentication/authorization?

5. **Tests**
   - Are there adequate tests?
   - Do tests cover edge cases?
   - Are tests readable?

### Providing Feedback

#### Good Review Comments

- "Consider using `useMemo` here to prevent unnecessary re-renders on every parent update"
- "This query could become slow with large datasets. Consider adding pagination or an index on `created_at`"

#### Avoid

- "This is wrong"
- "Why did you do it this way?"

### Turnaround Time

- **Small PRs (< 200 lines):** < 4 hours
- **Medium PRs (200-500 lines):** < 8 hours
- **Large PRs (> 500 lines):** < 24 hours

## Approval Requirements

| PR Type | Approvals Required |
|---------|-------------------|
| Feature | 2 |
| Bug fix | 1 |
| Hotfix | 1 (can be post-merge) |
| Refactor | 2 |

---

*Remember: We review code, not people!*
"""
            },
            {
                'category': 'process-workflows',
                'title': 'Incident Response Procedure',
                'slug': 'incident-response',
                'is_pinned': False,
                'tags': ['incident', 'response', 'procedure', 'emergency'],
                'content': """# Incident Response Procedure

## Severity Levels

| Level | Description | Response Time | Examples |
|-------|-------------|---------------|----------|
| **SEV1** | Complete outage | 15 minutes | System down, data loss |
| **SEV2** | Major degradation | 30 minutes | Feature broken, slow response |
| **SEV3** | Minor issue | 4 hours | UI bugs, non-critical errors |
| **SEV4** | Low impact | Next business day | Cosmetic issues |

## Response Process

### 1. Detection & Alert
- Automated monitoring alerts via PagerDuty
- User reports through support channels
- Internal team discovery

### 2. Acknowledge
```
On-call engineer acknowledges alert within:
- SEV1: 5 minutes
- SEV2: 15 minutes
- SEV3: 30 minutes
```

### 3. Assess
- Determine severity level
- Identify affected systems/users
- Initial impact assessment

### 4. Communicate
- Update status page
- Notify stakeholders
- Create incident channel: #incident-YYYY-MM-DD

### 5. Mitigate
- Implement temporary fix if possible
- Roll back if necessary
- Document actions taken

### 6. Resolve
- Implement permanent fix
- Verify resolution
- Update status page

### 7. Post-Mortem
- Schedule within 48 hours
- Document timeline
- Identify root cause
- Create action items

## On-Call Rotation

| Week | Primary | Secondary |
|------|---------|-----------|
| Current | Sam Rivera | Alex Chen |
| Next | Alex Chen | Jordan Taylor |
| Following | Jordan Taylor | Sam Rivera |

## Key Contacts

| Role | Name | Phone |
|------|------|-------|
| On-Call Primary | See rotation | PagerDuty |
| Engineering Manager | Alex Chen | 555-0100 |
| CTO | Jordan Taylor | 555-0101 |
| Security | security@acme.com | - |

---

*Stay calm, communicate clearly, fix the issue!*
"""
            },

            # --- PROJECT RESOURCES ---
            {
                'category': 'project-resources',
                'title': 'Q1 2026 Product Roadmap',
                'slug': 'q1-2026-roadmap',
                'is_pinned': True,
                'tags': ['roadmap', 'planning', 'q1', '2026'],
                'content': f"""# Q1 2026 Product Roadmap

## Vision Statement

**"Enable teams to work smarter with AI-powered project management"**

## Quarter Goals

1. **Increase user engagement by 25%** through new collaboration features
2. **Reduce time-to-task-completion by 30%** with AI suggestions
3. **Expand enterprise features** for larger team adoption
4. **Improve mobile experience** with native app updates

---

## Monthly Breakdown

### January 2026: Foundation

| Initiative | Status | Owner |
|------------|--------|-------|
| AI Task Suggestions v2 | In Progress | Sam Rivera |
| Dashboard Redesign | Complete | Jordan Taylor |
| Performance Optimization | In Progress | Engineering |
| Mobile App Refresh | Planning | Mobile Team |

**Key Milestone:** New dashboard launch (Jan 15)

---

### February 2026: Enhancement

| Initiative | Status | Owner |
|------------|--------|-------|
| Advanced Analytics | Planning | Data Team |
| Team Workload Balancing | Planning | Sam Rivera |
| Enterprise SSO | In Progress | Security |
| API v2 Launch | Planning | Engineering |

**Key Milestone:** Enterprise beta program launch (Feb 1)

---

### March 2026: Growth

| Initiative | Status | Owner |
|------------|--------|-------|
| AI Meeting Assistant | Planning | AI Team |
| Custom Workflows | Planning | Product |
| Integration Marketplace | Planning | Partnerships |
| Mobile Native Features | Planning | Mobile Team |

**Key Milestone:** Public launch of enterprise tier (Mar 15)

---

## Success Metrics

| Metric | Current | Q1 Target |
|--------|---------|-----------|
| Monthly Active Users | 10,000 | 15,000 |
| NPS Score | 45 | 55 |
| Task Completion Rate | 72% | 85% |
| Enterprise Customers | 12 | 25 |

## Dependencies & Risks

### Dependencies
- Third-party AI API availability
- Design resources for mobile refresh
- Security audit completion for SSO

### Risks
| Risk | Likelihood | Impact | Mitigation |
|------|------------|--------|------------|
| API delays | Medium | High | Parallel development track |
| Resource constraints | High | Medium | Flexible scope |
| Market changes | Low | High | Regular strategy reviews |

---

*Roadmap last updated: {current_date}*
*Next review: End of January*
"""
            },
            {
                'category': 'project-resources',
                'title': 'Release Notes v2.5',
                'slug': 'release-notes-v25',
                'is_pinned': False,
                'tags': ['release', 'changelog', 'v2.5'],
                'content': f"""# Release Notes - Version 2.5

**Release Date:** {release_date}  
**Version:** 2.5.0

---

## What's New

### AI-Powered Task Suggestions
Our new AI engine analyzes your project context and suggests:
- Optimal task assignments based on skills and workload
- Due date recommendations based on dependencies
- Risk predictions for overdue tasks

### Enhanced Dashboard
- **New burndown widget** - Visual sprint progress tracking
- **Team workload view** - See who's overloaded at a glance
- **Custom metric cards** - Build your own KPI dashboard

### Collaboration Improvements
- **Real-time comments** - See updates without refreshing
- **@mentions in descriptions** - Notify team members directly
- **Activity timeline** - Track all task changes

---

## Improvements

### Performance
- **50% faster** page loads on large boards
- **Reduced memory usage** by 30%
- **Optimized database queries** for task lists

### User Experience
- Improved drag-and-drop on mobile devices
- Better keyboard navigation for accessibility
- Clearer error messages

### Integrations
- **Slack integration update** - Richer notifications
- **GitHub sync improvements** - Better PR linking
- **Calendar export** - iCal format support

---

## Bug Fixes

- Fixed issue where tasks would disappear after column move
- Resolved timezone issues in date picker
- Fixed notification sound not respecting user preferences
- Corrected calculation in velocity charts
- Fixed search not finding tasks by assignee

---

## Breaking Changes

### API Changes
- `GET /api/tasks/` now requires `board_id` parameter
- Deprecated `task.owner` field (use `task.assigned_to` instead)
- Rate limit reduced to 100 req/min for free tier

### Migration Notes
```bash
# Run after updating
python manage.py migrate
python manage.py rebuild_search_index
```

---

## Known Issues

- Mobile app v2.4 may have sync issues (update to v2.5)
- Safari 16.0 has minor CSS issues (fixed in next patch)

---

*Questions? Contact support@acme.com*
"""
            },
            {
                'category': 'project-resources',
                'title': 'Feature Requirements: AI Dashboard',
                'slug': 'feature-req-ai-dashboard',
                'is_pinned': False,
                'tags': ['requirements', 'feature', 'ai', 'dashboard'],
                'content': f"""# Feature Requirements: AI Dashboard

**Document Version:** 1.2  
**Last Updated:** {current_date}  
**Author:** Jordan Taylor  
**Status:** In Development

---

## Executive Summary

The AI Dashboard feature will provide users with intelligent insights about their projects, teams, and workflows. Using machine learning, it will surface actionable recommendations and predictions to help teams work more effectively.

## Problem Statement

Users currently lack visibility into:
- Which tasks are at risk of missing deadlines
- How to optimally distribute work across team members
- Patterns that lead to project delays
- Opportunities for process improvement

## Goals

1. **Reduce missed deadlines by 40%** through early warning predictions
2. **Improve task assignment accuracy** with AI recommendations
3. **Increase team efficiency** by identifying bottlenecks
4. **Save 2+ hours/week** per manager through automated insights

## User Stories

### As a Project Manager
> I want to see which tasks are at risk of delay so that I can take proactive action.

**Acceptance Criteria:**
- Risk indicators visible on dashboard
- Tasks sorted by risk level
- Click to see risk factors
- One-click to assign more resources

### As a Team Lead
> I want to see balanced workload recommendations so that no one is overloaded.

**Acceptance Criteria:**
- Workload heat map by team member
- AI suggestions for task reallocation
- Capacity planning view
- Historical workload trends

### As a Team Member
> I want to see my priority tasks and recommendations so that I work on what matters most.

**Acceptance Criteria:**
- Personalized task priority list
- AI-suggested focus areas
- Time estimates for tasks
- Break reminders (optional)

## Functional Requirements

### FR-1: Risk Prediction Engine
- Analyze historical data to predict task delays
- Consider: assignee, complexity, dependencies
- Update predictions daily
- Confidence score for each prediction

### FR-2: Workload Optimizer
- Calculate current workload per team member
- Suggest optimal task redistribution
- Consider skills and preferences
- Respect WIP limits

### FR-3: Insights Dashboard
- Widget-based layout
- Customizable card arrangement
- Real-time updates
- Export capabilities

## Non-Functional Requirements

| Requirement | Target |
|-------------|--------|
| Page Load | < 2 seconds |
| Prediction Accuracy | > 80% |
| Availability | 99.9% uptime |
| Data Freshness | < 5 minutes |

## Implementation Phases

### Phase 1: Foundation (Sprint 45-46)
- Basic risk prediction model
- Workload calculation
- Dashboard framework

### Phase 2: Intelligence (Sprint 47-48)
- ML model training
- Recommendation engine
- Insights generation

### Phase 3: Polish (Sprint 49)
- Performance optimization
- User feedback integration
- Documentation

## Open Questions

- [ ] Should predictions be shown to all users or just managers?
- [ ] How to handle edge cases with new users (no history)?
- [ ] What privacy controls are needed?

---

*Feedback? Comment on this document or reach out to Jordan Taylor*
"""
            },
        ]
