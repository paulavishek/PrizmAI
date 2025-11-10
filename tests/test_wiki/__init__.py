"""
Tests for Wiki App Models
=========================

Tests coverage:
- WikiCategory model
- WikiPage model with hierarchical structure
- WikiPageVersion for version control
- WikiLink model for cross-references
- WikiLinkBetweenPages for page relationships
- WikiAttachment model
- WikiPageAccess for permissions
- MeetingNotes model
"""

from django.test import TestCase
from django.contrib.auth.models import User
from django.utils import timezone
from wiki.models import (
    WikiCategory, WikiPage, WikiPageVersion, WikiLink,
    WikiLinkBetweenPages, WikiAttachment, WikiPageAccess, MeetingNotes
)
from kanban.models import Board
from accounts.models import Organization, UserProfile


class WikiCategoryTests(TestCase):
    """Test WikiCategory model"""
    
    def setUp(self):
        """Set up test data"""
        self.user = User.objects.create_user(
            username='testuser',
            email='test@example.com',
            password='testpass123'
        )
        self.org = Organization.objects.create(
            name='Test Org',
            domain='test.org',
            created_by=self.user
        )
    
    def test_category_creation(self):
        """Test creating a wiki category"""
        category = WikiCategory.objects.create(
            name='Documentation',
            slug='documentation',
            organization=self.org
        )
        self.assertEqual(category.name, 'Documentation')
        self.assertEqual(category.organization, self.org)
    
    def test_category_slug_generation(self):
        """Test slug generation"""
        category = WikiCategory.objects.create(
            name='API Documentation',
            organization=self.org
        )
        self.assertEqual(category.slug, 'api-documentation')
    
    def test_category_icon(self):
        """Test category icon"""
        category = WikiCategory.objects.create(
            name='Docs',
            slug='docs',
            organization=self.org,
            icon='book'
        )
        self.assertEqual(category.icon, 'book')
    
    def test_category_color(self):
        """Test category color"""
        category = WikiCategory.objects.create(
            name='Docs',
            slug='docs',
            organization=self.org,
            color='#FF5733'
        )
        self.assertEqual(category.color, '#FF5733')
    
    def test_category_position(self):
        """Test category ordering position"""
        cat1 = WikiCategory.objects.create(
            name='First',
            slug='first',
            organization=self.org,
            position=0
        )
        cat2 = WikiCategory.objects.create(
            name='Second',
            slug='second',
            organization=self.org,
            position=1
        )
        categories = WikiCategory.objects.all()
        self.assertEqual(categories[0], cat1)
        self.assertEqual(categories[1], cat2)
    
    def test_unique_category_per_org(self):
        """Test category names are unique per organization"""
        WikiCategory.objects.create(
            name='Docs',
            slug='docs',
            organization=self.org
        )
        with self.assertRaises(Exception):
            WikiCategory.objects.create(
                name='Docs',
                slug='docs',
                organization=self.org
            )
    
    def test_category_string_representation(self):
        """Test category __str__ method"""
        category = WikiCategory.objects.create(
            name='Documentation',
            slug='documentation',
            organization=self.org
        )
        self.assertEqual(str(category), 'Documentation')


class WikiPageTests(TestCase):
    """Test WikiPage model"""
    
    def setUp(self):
        """Set up test data"""
        self.user = User.objects.create_user(
            username='testuser',
            email='test@example.com',
            password='testpass123'
        )
        self.org = Organization.objects.create(
            name='Test Org',
            domain='test.org',
            created_by=self.user
        )
        self.category = WikiCategory.objects.create(
            name='Docs',
            slug='docs',
            organization=self.org
        )
    
    def test_page_creation(self):
        """Test creating a wiki page"""
        page = WikiPage.objects.create(
            title='Getting Started',
            slug='getting-started',
            content='# Getting Started\nWelcome!',
            category=self.category,
            organization=self.org,
            created_by=self.user,
            updated_by=self.user
        )
        self.assertEqual(page.title, 'Getting Started')
        self.assertTrue(page.is_published)
    
    def test_page_slug_generation(self):
        """Test automatic slug generation"""
        page = WikiPage.objects.create(
            title='API Reference',
            content='Content',
            category=self.category,
            organization=self.org,
            created_by=self.user,
            updated_by=self.user
        )
        self.assertEqual(page.slug, 'api-reference')
    
    def test_page_publishing(self):
        """Test page publication status"""
        page = WikiPage.objects.create(
            title='Draft Page',
            slug='draft-page',
            content='Draft content',
            category=self.category,
            organization=self.org,
            created_by=self.user,
            updated_by=self.user,
            is_published=False
        )
        self.assertFalse(page.is_published)
    
    def test_page_pinning(self):
        """Test pinning pages"""
        page = WikiPage.objects.create(
            title='Important',
            slug='important',
            content='Important content',
            category=self.category,
            organization=self.org,
            created_by=self.user,
            updated_by=self.user,
            is_pinned=True
        )
        self.assertTrue(page.is_pinned)
    
    def test_page_tags(self):
        """Test tagging pages"""
        tags = ['tutorial', 'beginner', 'api']
        page = WikiPage.objects.create(
            title='API Tutorial',
            slug='api-tutorial',
            content='Content',
            category=self.category,
            organization=self.org,
            created_by=self.user,
            updated_by=self.user,
            tags=tags
        )
        self.assertEqual(page.tags, tags)
    
    def test_page_view_count(self):
        """Test view count tracking"""
        page = WikiPage.objects.create(
            title='Popular Page',
            slug='popular-page',
            content='Content',
            category=self.category,
            organization=self.org,
            created_by=self.user,
            updated_by=self.user
        )
        initial_views = page.view_count
        page.increment_view_count()
        page.refresh_from_db()
        self.assertEqual(page.view_count, initial_views + 1)
    
    def test_page_hierarchy(self):
        """Test hierarchical page structure"""
        parent = WikiPage.objects.create(
            title='Parent Page',
            slug='parent-page',
            content='Parent',
            category=self.category,
            organization=self.org,
            created_by=self.user,
            updated_by=self.user
        )
        child = WikiPage.objects.create(
            title='Child Page',
            slug='child-page',
            content='Child',
            category=self.category,
            organization=self.org,
            created_by=self.user,
            updated_by=self.user,
            parent_page=parent
        )
        self.assertEqual(child.parent_page, parent)
    
    def test_page_breadcrumb(self):
        """Test breadcrumb generation"""
        parent = WikiPage.objects.create(
            title='Parent',
            slug='parent',
            content='P',
            category=self.category,
            organization=self.org,
            created_by=self.user,
            updated_by=self.user
        )
        child = WikiPage.objects.create(
            title='Child',
            slug='child',
            content='C',
            category=self.category,
            organization=self.org,
            created_by=self.user,
            updated_by=self.user,
            parent_page=parent
        )
        breadcrumb = child.get_breadcrumb()
        self.assertEqual(len(breadcrumb), 2)
        self.assertEqual(breadcrumb[0], parent)
        self.assertEqual(breadcrumb[1], child)
    
    def test_page_string_representation(self):
        """Test page __str__ method"""
        page = WikiPage.objects.create(
            title='Test Page',
            slug='test-page',
            content='Content',
            category=self.category,
            organization=self.org,
            created_by=self.user,
            updated_by=self.user
        )
        self.assertEqual(str(page), 'Test Page')


class WikiPageVersionTests(TestCase):
    """Test WikiPageVersion model"""
    
    def setUp(self):
        """Set up test data"""
        self.user = User.objects.create_user(
            username='testuser',
            email='test@example.com',
            password='testpass123'
        )
        self.org = Organization.objects.create(
            name='Test Org',
            domain='test.org',
            created_by=self.user
        )
        self.category = WikiCategory.objects.create(
            name='Docs',
            slug='docs',
            organization=self.org
        )
        self.page = WikiPage.objects.create(
            title='Test Page',
            slug='test-page',
            content='Original content',
            category=self.category,
            organization=self.org,
            created_by=self.user,
            updated_by=self.user
        )
    
    def test_version_creation(self):
        """Test creating a page version"""
        version = WikiPageVersion.objects.create(
            page=self.page,
            version_number=1,
            title='Test Page',
            content='Original content',
            edited_by=self.user
        )
        self.assertEqual(version.page, self.page)
        self.assertEqual(version.version_number, 1)
    
    def test_version_change_summary(self):
        """Test version change summary"""
        version = WikiPageVersion.objects.create(
            page=self.page,
            version_number=1,
            title='Test Page',
            content='Content',
            edited_by=self.user,
            change_summary='Fixed typos'
        )
        self.assertEqual(version.change_summary, 'Fixed typos')
    
    def test_version_ordering(self):
        """Test versions ordered by version number (descending)"""
        v1 = WikiPageVersion.objects.create(
            page=self.page,
            version_number=1,
            title='Page',
            content='v1',
            edited_by=self.user
        )
        v2 = WikiPageVersion.objects.create(
            page=self.page,
            version_number=2,
            title='Page',
            content='v2',
            edited_by=self.user
        )
        versions = WikiPageVersion.objects.all()
        self.assertEqual(versions[0], v2)  # Higher version first


class WikiLinkBetweenPagesTests(TestCase):
    """Test WikiLinkBetweenPages model"""
    
    def setUp(self):
        """Set up test data"""
        self.user = User.objects.create_user(
            username='testuser',
            email='test@example.com',
            password='testpass123'
        )
        self.org = Organization.objects.create(
            name='Test Org',
            domain='test.org',
            created_by=self.user
        )
        self.category = WikiCategory.objects.create(
            name='Docs',
            slug='docs',
            organization=self.org
        )
        self.page1 = WikiPage.objects.create(
            title='Page 1',
            slug='page-1',
            content='Content 1',
            category=self.category,
            organization=self.org,
            created_by=self.user,
            updated_by=self.user
        )
        self.page2 = WikiPage.objects.create(
            title='Page 2',
            slug='page-2',
            content='Content 2',
            category=self.category,
            organization=self.org,
            created_by=self.user,
            updated_by=self.user
        )
    
    def test_link_creation(self):
        """Test creating link between pages"""
        link = WikiLinkBetweenPages.objects.create(
            source_page=self.page1,
            target_page=self.page2,
            created_by=self.user
        )
        self.assertEqual(link.source_page, self.page1)
        self.assertEqual(link.target_page, self.page2)
    
    def test_link_uniqueness(self):
        """Test preventing duplicate links between same pages"""
        WikiLinkBetweenPages.objects.create(
            source_page=self.page1,
            target_page=self.page2,
            created_by=self.user
        )
        with self.assertRaises(Exception):
            WikiLinkBetweenPages.objects.create(
                source_page=self.page1,
                target_page=self.page2,
                created_by=self.user
            )


class MeetingNotesTests(TestCase):
    """Test MeetingNotes model"""
    
    def setUp(self):
        """Set up test data"""
        self.user = User.objects.create_user(
            username='testuser',
            email='test@example.com',
            password='testpass123'
        )
        self.org = Organization.objects.create(
            name='Test Org',
            domain='test.org',
            created_by=self.user
        )
    
    def test_meeting_notes_creation(self):
        """Test creating meeting notes"""
        notes = MeetingNotes.objects.create(
            title='Q1 Planning Meeting',
            date=timezone.now(),
            content='# Meeting Notes\n\nDiscussed Q1 goals',
            organization=self.org,
            created_by=self.user
        )
        self.assertEqual(notes.title, 'Q1 Planning Meeting')
        self.assertEqual(notes.organization, self.org)
    
    def test_meeting_type(self):
        """Test meeting type choices"""
        types = ['standup', 'planning', 'review', 'retrospective', 'general']
        for meeting_type in types:
            notes = MeetingNotes.objects.create(
                title=f'Meeting-{meeting_type}',
                date=timezone.now(),
                content='Content',
                organization=self.org,
                created_by=self.user,
                meeting_type=meeting_type
            )
            self.assertEqual(notes.meeting_type, meeting_type)
    
    def test_meeting_attendees(self):
        """Test tracking attendees"""
        notes = MeetingNotes.objects.create(
            title='Team Meeting',
            date=timezone.now(),
            content='Content',
            organization=self.org,
            created_by=self.user
        )
        user2 = User.objects.create_user(
            username='user2',
            email='user2@example.com',
            password='testpass123'
        )
        notes.attendees.add(self.user, user2)
        self.assertEqual(notes.attendees.count(), 2)
    
    def test_meeting_duration(self):
        """Test recording meeting duration"""
        notes = MeetingNotes.objects.create(
            title='Meeting',
            date=timezone.now(),
            content='Content',
            organization=self.org,
            created_by=self.user,
            duration_minutes=60
        )
        self.assertEqual(notes.duration_minutes, 60)
    
    def test_action_items(self):
        """Test action items tracking"""
        actions = [
            {'task': 'Review PR', 'assigned_to': 'user1', 'due_date': '2025-11-20'},
            {'task': 'Deploy to staging', 'assigned_to': 'user2', 'due_date': '2025-11-15'}
        ]
        notes = MeetingNotes.objects.create(
            title='Meeting',
            date=timezone.now(),
            content='Content',
            organization=self.org,
            created_by=self.user,
            action_items=actions
        )
        self.assertEqual(len(notes.action_items), 2)
    
    def test_meeting_notes_ordering(self):
        """Test notes ordered by date (newest first)"""
        notes1 = MeetingNotes.objects.create(
            title='Old Meeting',
            date=timezone.now(),
            content='Content',
            organization=self.org,
            created_by=self.user
        )
        notes2 = MeetingNotes.objects.create(
            title='New Meeting',
            date=timezone.now(),
            content='Content',
            organization=self.org,
            created_by=self.user
        )
        notes = MeetingNotes.objects.all()
        self.assertEqual(notes[0], notes2)
