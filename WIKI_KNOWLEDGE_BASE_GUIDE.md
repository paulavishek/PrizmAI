# Wiki & Knowledge Base Integration Guide

## Overview

The Wiki & Knowledge Base feature has been successfully integrated into PrizmAI. This comprehensive system enables project-level documentation, linking to tasks/boards, and meeting notes storage.

## Features

### 1. **Wiki Pages**
- Create and organize wiki pages with markdown support
- Hierarchical page organization (sub-pages)
- Version control and history tracking
- Full-text search across pages
- Tag-based categorization
- Pin important pages for quick access
- View count analytics

### 2. **Wiki Categories**
- Organize pages by categories
- Customizable icons and colors
- Hierarchical category structure
- Quick filtering and navigation

### 3. **Content Linking**
- Link wiki pages to specific tasks
- Link wiki pages to project boards
- Cross-reference wiki pages
- Bidirectional relationship tracking
- Contextual descriptions for each link

### 4. **Meeting Notes**
- Create and store meeting notes
- Link to related boards and wiki pages
- Track attendees
- Record action items and decisions
- Support for markdown content
- Meeting duration tracking

### 5. **Version Control**
- Full version history for all pages
- Track changes and who made them
- Restore to previous versions
- Change summaries for each version

### 6. **Search & Discovery**
- Unified search across wiki, meeting notes, tasks, and boards
- Full-text search support
- Tag-based filtering
- Quick access to related content

## File Structure

```
wiki/
├── models.py                 # 8 wiki-related models
├── views.py                  # 10+ class and function-based views
├── urls.py                   # URL routing
├── forms.py                  # 7 form classes
├── admin.py                  # Django admin configuration
├── apps.py                   # App configuration
├── signals.py                # Signal handlers for automation
├── migrations/
└── management/
    └── commands/

templates/wiki/
├── page_list.html           # Browse all wiki pages
├── page_detail.html         # View single page with all details
├── page_form.html           # Create/edit pages with markdown editor
├── page_history.html        # Version history view
├── meeting_notes_list.html  # Browse meeting notes
├── meeting_notes_form.html  # Create/edit meeting notes
├── meeting_notes_detail.html # View meeting notes
├── search_results.html      # Search results page
├── category_list.html       # Browse categories
└── category_form.html       # Create categories
```

## Models Overview

### 1. **WikiPage**
- Main wiki page model
- Markdown content support
- Organization-scoped
- Version tracking
- Hierarchical support (parent_page)
- Publishing status
- Pinning capability

**Fields:**
- title, slug, content, category, organization
- created_by, updated_by, created_at, updated_at
- is_published, is_pinned, tags, view_count
- version, parent_page

### 2. **WikiCategory**
- Organize pages into categories
- Custom icons and colors
- Position-based ordering

### 3. **WikiAttachment**
- Attach files to wiki pages
- Track file metadata
- File type detection

### 4. **WikiLink**
- Link pages to tasks and boards
- Flexible linking system
- Description/context for links

### 5. **MeetingNotes**
- Dedicated model for meeting notes
- Attendee tracking
- Action items and decisions storage
- Link to boards and wiki pages

### 6. **WikiPageVersion**
- Track page changes over time
- Store old content
- Change summaries

### 7. **WikiLinkBetweenPages**
- Cross-reference wiki pages
- Create knowledge graph

### 8. **WikiPageAccess**
- Track and manage access permissions
- Access level tracking (view, edit, admin)

## Getting Started

### Installation Steps

1. **Install markdown package** (already in requirements.txt):
   ```bash
   pip install Markdown==3.5.1
   ```

2. **Run migrations**:
   ```bash
   python manage.py makemigrations wiki
   python manage.py migrate wiki
   ```

3. **Create wiki app** (if not already done):
   ```bash
   python manage.py startapp wiki
   ```

### Configuration

The wiki app is already registered in `settings.py`:

```python
INSTALLED_APPS = [
    # ...
    'wiki',
]
```

### URL Configuration

Wiki URLs are already included in `kanban_board/urls.py`:

```python
path('wiki/', include('wiki.urls')),
```

## Usage Examples

### Creating a Wiki Page

1. Navigate to `/wiki/create/`
2. Fill in the page details:
   - Title
   - Category
   - Content (markdown)
   - Parent page (optional)
   - Tags
   - Publication status
3. Click "Create Page"

### Linking Wiki to Tasks/Boards

1. View a wiki page
2. Click "Link" button
3. Select the content type (Task or Board)
4. Choose the specific item
5. Add a description/context
6. Save the link

### Creating Meeting Notes

1. Navigate to `/wiki/meeting-notes/create/`
2. Fill in details:
   - Title
   - Date and time
   - Content
   - Attendees (comma-separated usernames)
   - Related board (optional)
   - Duration
   - Key decisions
3. Click "Create"

### Searching

1. Use the search bar: `/wiki/search/?q=your-query`
2. Results show:
   - Wiki pages
   - Meeting notes
   - Related tasks
   - Related boards

## Advanced Features

### Markdown Support

The wiki uses CommonMark markdown with syntax highlighting:

```markdown
# Heading
**Bold** and *italic* text
`inline code`
```python
code blocks
```

[Links](url) and ![Images](url)

- Lists
- With items

| Tables | Supported |
|--------|-----------|
| Cell 1 | Cell 2    |
```

### Version Control

- Each edit creates a new version
- View full history: `/wiki/page/<slug>/history/`
- Restore previous versions: `/wiki/page/<slug>/restore/<version_number>/`
- Change summaries for tracking

### Cross-Page References

- Link pages to create a knowledge graph
- See incoming links (pages referencing current page)
- Navigate through related content

## Views and URLs

### Main Views

```
GET  /wiki/                           # List all pages
GET  /wiki/category/<id>/             # Pages by category
GET  /wiki/create/                    # Create new page
GET  /wiki/page/<slug>/               # View page
GET  /wiki/page/<slug>/edit/          # Edit page
GET  /wiki/page/<slug>/delete/        # Delete page
GET  /wiki/page/<slug>/history/       # View history
GET  /wiki/page/<slug>/restore/<v>/   # Restore version
GET  /wiki/page/<slug>/link/          # Link to tasks/boards
GET  /wiki/quick-link/<type>/<id>/    # Quick link from task/board
GET  /wiki/search/                    # Search
GET  /wiki/meeting-notes/             # List meeting notes
GET  /wiki/meeting-notes/create/      # Create meeting notes
GET  /wiki/meeting-notes/<id>/        # View meeting notes
```

## Integration with Existing Features

### Task Integration

Wiki pages can be linked to tasks:
- Add documentation for a task
- Store task-related research/notes
- Link multiple pages to a single task

### Board Integration

Wiki pages can be linked to project boards:
- Store project overview
- Keep governance documents
- Store board-specific guidelines

### Messaging Integration

Meeting notes can be:
- Discussed in messaging threads
- Referenced in task comments
- Attached to chat rooms

## Admin Interface

Access Django admin: `/admin/`

Configured admin models:
- WikiCategory
- WikiPage
- WikiAttachment
- WikiLink
- MeetingNotes
- WikiPageVersion
- WikiLinkBetweenPages
- WikiPageAccess

### Admin Features

- Full CRUD for all models
- Filtering and search
- Bulk actions
- Read-only fields for metadata
- Custom admin displays (color codes, icons, etc.)

## Permissions & Access

### Current Implementation

- All organization members can view published pages
- Page creators and staff can edit/delete pages
- Access is tracked per user per page

### Future Enhancement Opportunities

- Role-based access control
- Fine-grained permissions (view, edit, delete)
- Page-level sharing settings
- Comments and discussions

## Performance Considerations

### Database Indexes

Indexes are created on:
- organization, updated_at
- slug
- category
- date (for meeting notes)

### Optimization Tips

1. Use categories to organize pages
2. Pin frequently accessed pages
3. Archive old meeting notes
4. Clean up unused versions periodically

## Customization

### Adding Custom Fields

To add fields to WikiPage:

```python
# In models.py
class WikiPage(models.Model):
    # existing fields...
    custom_field = models.CharField(max_length=100)
    
# In admin.py
fieldsets = (
    # existing fieldsets...
    ('Custom', {
        'fields': ('custom_field',)
    }),
)
```

### Customizing Templates

Templates are in `templates/wiki/`:
- Modify styling with custom CSS
- Add additional template blocks
- Integrate with other app templates

### Extending Signals

Add handlers in `signals.py`:
```python
@receiver(post_save, sender=WikiPage)
def custom_handler(sender, instance, created, **kwargs):
    # Your custom logic
    pass
```

## API Integration (Future)

To add REST API endpoints:

1. Create `serializers.py`:
```python
from rest_framework import serializers
from .models import WikiPage, WikiCategory

class WikiPageSerializer(serializers.ModelSerializer):
    class Meta:
        model = WikiPage
        fields = ['id', 'title', 'content', 'category', 'created_at', 'updated_at']
```

2. Create `api_views.py`:
```python
from rest_framework import viewsets
from .serializers import WikiPageSerializer
from .models import WikiPage

class WikiPageViewSet(viewsets.ModelViewSet):
    queryset = WikiPage.objects.all()
    serializer_class = WikiPageSerializer
```

3. Register in URLs:
```python
from rest_framework import routers
from .api_views import WikiPageViewSet

router = routers.DefaultRouter()
router.register(r'pages', WikiPageViewSet)

urlpatterns = [
    path('api/', include(router.urls)),
]
```

## Troubleshooting

### Common Issues

**1. Migrations not found**
- Solution: Ensure wiki app is in INSTALLED_APPS
- Run: `python manage.py makemigrations wiki`

**2. Markdown not rendering**
- Solution: Check if markdown package is installed
- Run: `pip install Markdown==3.5.1`

**3. Links not appearing**
- Solution: Ensure WikiLink relationships are properly saved
- Check organization field is set correctly

### Debug Mode

Enable detailed logging in `settings.py`:
```python
LOGGING = {
    'version': 1,
    'handlers': {
        'console': {
            'class': 'logging.StreamHandler',
        },
    },
    'root': {
        'handlers': ['console'],
        'level': 'DEBUG',
    },
}
```

## Next Steps

1. **Create first wiki page**
   - Navigate to `/wiki/create/`
   - Add project documentation

2. **Set up categories**
   - Go to `/wiki/categories/`
   - Create organization-specific categories

3. **Link existing content**
   - Start linking wiki pages to tasks and boards
   - Create cross-references

4. **Store meeting notes**
   - Start recording meeting notes
   - Link to relevant wiki pages

5. **Gather team feedback**
   - Train team on wiki usage
   - Gather feedback for improvements

## Support & Documentation

- Django Documentation: https://docs.djangoproject.com/
- Markdown Guide: https://www.markdownguide.org/
- CommonMark Spec: https://spec.commonmark.org/

## Future Enhancement Ideas

- Rich text editor alternative to markdown
- Wiki page templates
- Collaborative editing
- Page commenting system
- Wiki notifications
- PDF export functionality
- Advanced permissions system
- Wiki activity feed
- Suggested links (AI-powered)
- Page recommendations
- Wiki analytics dashboard
- Mobile app support

## Summary

The Wiki & Knowledge Base feature provides a robust system for:
- ✅ Project-level documentation
- ✅ Linking documentation to tasks and boards
- ✅ Storing and organizing meeting notes
- ✅ Version control and history tracking
- ✅ Full-text search capabilities
- ✅ Team collaboration on documentation

The implementation is production-ready and can be extended with additional features based on specific organizational needs.
