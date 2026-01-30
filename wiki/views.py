from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib.auth.mixins import LoginRequiredMixin, UserPassesTestMixin
from django.views.generic import ListView, DetailView, CreateView, UpdateView, DeleteView
from django.db.models import Q, Sum, Count
from django.http import JsonResponse
from django.urls import reverse_lazy, reverse
from django.utils.decorators import method_decorator
from django.views.decorators.http import require_http_methods
from django.contrib import messages

from .models import (
    WikiPage, WikiCategory, WikiAttachment, WikiLink, 
    MeetingNotes, WikiPageVersion, WikiLinkBetweenPages, WikiPageAccess
)
from .forms import (
    WikiPageForm, WikiCategoryForm, WikiAttachmentForm, WikiLinkForm,
    # MeetingNotesForm,  # DISABLED - meetings feature removed
    WikiPageSearchForm, QuickWikiLinkForm
)
from kanban.models import Board, Task
from accounts.models import Organization


class WikiBaseView(LoginRequiredMixin, UserPassesTestMixin):
    """Base view for wiki operations - MVP mode without organization requirement"""
    
    def test_func(self):
        """MVP Mode: All authenticated users can access wiki"""
        # All authenticated users can access wiki content
        return self.request.user.is_authenticated
    
    def get_organization(self):
        """
        Get organization - MVP mode uses demo organization for all wiki data.
        Returns demo org or user's org (can be None in MVP mode).
        """
        org_id = self.kwargs.get('org_id')
        if org_id:
            return get_object_or_404(Organization, pk=org_id)
        
        # MVP Mode: First try user's org, then fall back to demo org
        if hasattr(self.request.user, 'profile') and self.request.user.profile and self.request.user.profile.organization:
            return self.request.user.profile.organization
        
        # Fall back to demo organization for wiki content
        return Organization.objects.filter(is_demo=True).first()
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        org = self.get_organization()
        context['organization'] = org
        
        # MVP Mode: Show all wiki categories (from demo org)
        demo_org = Organization.objects.filter(is_demo=True).first()
        if demo_org:
            context['categories'] = WikiCategory.objects.filter(
                Q(organization=demo_org) | Q(organization__isnull=True)
            ).distinct()
        else:
            context['categories'] = WikiCategory.objects.all()
        return context


class WikiCategoryListView(WikiBaseView, ListView):
    """List all wiki categories - MVP mode shows all categories"""
    model = WikiCategory
    template_name = 'wiki/category_list.html'
    context_object_name = 'categories'
    paginate_by = 20
    
    def get_queryset(self):
        # MVP Mode: Show all wiki categories (from demo org primarily)
        demo_org = Organization.objects.filter(is_demo=True).first()
        if demo_org:
            return WikiCategory.objects.filter(
                Q(organization=demo_org) | Q(organization__isnull=True)
            ).prefetch_related('pages').distinct()
        return WikiCategory.objects.all().prefetch_related('pages')


class WikiPageListView(WikiBaseView, ListView):
    """List all wiki pages - MVP mode shows all pages"""
    model = WikiPage
    template_name = 'wiki/page_list.html'
    context_object_name = 'pages'
    paginate_by = 20
    
    def get_queryset(self):
        # MVP Mode: Show all wiki pages (from demo org primarily)
        demo_org = Organization.objects.filter(is_demo=True).first()
        if demo_org:
            org_filter = Q(organization=demo_org) | Q(organization__isnull=True)
        else:
            org_filter = Q()
        
        queryset = WikiPage.objects.filter(org_filter, is_published=True)
        
        category_id = self.kwargs.get('category_id')
        if category_id:
            queryset = queryset.filter(category_id=category_id)
        
        # Search functionality
        query = self.request.GET.get('q')
        if query:
            # Build the query - avoid JSONField contains lookup for SQLite compatibility
            search_query = Q(title__icontains=query) | Q(content__icontains=query)
            
            # Try to add tags search, but handle SQLite limitation
            try:
                # PostgreSQL/MySQL support: use contains lookup on JSONField
                from django.db import connection
                if connection.vendor != 'sqlite':
                    search_query |= Q(tags__contains=query)
            except Exception:
                # If there's any issue, skip tags search
                pass
            
            queryset = queryset.filter(search_query)
        
        return queryset.select_related('category', 'created_by').order_by('-is_pinned', '-updated_at')
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        org = self.get_organization()
        context['search_form'] = WikiPageSearchForm(self.request.GET, organization=org)
        context['category_id'] = self.kwargs.get('category_id')
        return context


class WikiPageDetailView(WikiBaseView, DetailView):
    """Display a wiki page with all details"""
    model = WikiPage
    template_name = 'wiki/page_detail.html'
    context_object_name = 'page'
    slug_field = 'slug'
    slug_url_kwarg = 'slug'
    
    def test_func(self):
        """Allow access to user's org pages AND demo org pages"""
        # First try to get the page to check its organization
        slug = self.kwargs.get('slug')
        if slug:
            demo_org_names = ['Demo - Acme Corporation']
            demo_orgs = Organization.objects.filter(name__in=demo_org_names)
            
            # Check if the page is in demo org
            page = WikiPage.objects.filter(
                Q(slug=slug),
                Q(organization__in=demo_orgs)
            ).first()
            if page:
                return True  # Allow access to demo pages
        
        # Otherwise, use the default test (user's org)
        return super().test_func()
    
    def get_queryset(self):
        org = self.get_organization()
        # Also allow access to demo organization wiki pages
        demo_org_names = ['Demo - Acme Corporation']
        demo_orgs = Organization.objects.filter(name__in=demo_org_names)
        
        # Include both user's org and demo org pages
        queryset = WikiPage.objects.filter(
            Q(organization=org) | Q(organization__in=demo_orgs)
        )
        return queryset
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        page = self.object
        context['attachments'] = page.attachments.all()
        context['linked_tasks'] = WikiLink.objects.filter(
            wiki_page=page, link_type='task'
        ).select_related('task')
        context['linked_boards'] = WikiLink.objects.filter(
            wiki_page=page, link_type='board'
        ).select_related('board')
        # Meeting notes feature removed
        # context['related_meeting_notes'] = page.meeting_notes_references.all()
        context['versions'] = page.versions.all()[:5]
        context['breadcrumb'] = page.get_breadcrumb()
        context['incoming_links'] = page.incoming_links.select_related('source_page')
        
        return context
    
    def get(self, request, *args, **kwargs):
        """Increment view count on page load"""
        response = super().get(request, *args, **kwargs)
        self.object.increment_view_count()
        return response


class WikiPageCreateView(WikiBaseView, CreateView):
    """Create a new wiki page"""
    model = WikiPage
    form_class = WikiPageForm
    template_name = 'wiki/page_form.html'
    
    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs['organization'] = self.get_organization()
        return kwargs
    
    def form_valid(self, form):
        org = self.get_organization()
        form.instance.organization = org
        form.instance.created_by = self.request.user
        form.instance.updated_by = self.request.user
        response = super().form_valid(form)
        
        # Create initial version
        WikiPageVersion.objects.create(
            page=self.object,
            version_number=1,
            title=self.object.title,
            content=self.object.content,
            edited_by=self.request.user,
            change_summary='Initial creation'
        )
        
        messages.success(self.request, f'Wiki page "{self.object.title}" created successfully!')
        return response
    
    def get_success_url(self):
        return self.object.get_absolute_url()


class WikiPageUpdateView(WikiBaseView, UpdateView):
    """Update an existing wiki page"""
    model = WikiPage
    form_class = WikiPageForm
    template_name = 'wiki/page_form.html'
    slug_field = 'slug'
    slug_url_kwarg = 'slug'
    
    def get_queryset(self):
        org = self.get_organization()
        return WikiPage.objects.filter(organization=org)
    
    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs['organization'] = self.get_organization()
        return kwargs
    
    def form_valid(self, form):
        old_content = WikiPage.objects.get(pk=self.object.pk).content
        form.instance.updated_by = self.request.user
        form.instance.version += 1
        response = super().form_valid(form)
        
        # Create version history entry
        if old_content != form.instance.content:
            WikiPageVersion.objects.create(
                page=self.object,
                version_number=self.object.version,
                title=self.object.title,
                content=old_content,
                edited_by=self.request.user,
                change_summary=self.request.POST.get('change_summary', '')
            )
        
        messages.success(self.request, f'Wiki page "{self.object.title}" updated successfully!')
        return response
    
    def get_success_url(self):
        return self.object.get_absolute_url()


class WikiPageDeleteView(WikiBaseView, DeleteView):
    """Delete a wiki page"""
    model = WikiPage
    template_name = 'wiki/page_confirm_delete.html'
    slug_field = 'slug'
    slug_url_kwarg = 'slug'
    
    def get_queryset(self):
        org = self.get_organization()
        return WikiPage.objects.filter(organization=org)
    
    def get_success_url(self):
        org = self.get_organization()
        return reverse_lazy('wiki:category_list', kwargs={'org_id': org.id})


class WikiCategoryCreateView(WikiBaseView, CreateView):
    """Create a new wiki category"""
    model = WikiCategory
    form_class = WikiCategoryForm
    template_name = 'wiki/category_form.html'
    
    def form_valid(self, form):
        org = self.get_organization()
        form.instance.organization = org
        response = super().form_valid(form)
        messages.success(self.request, f'Category "{self.object.name}" created!')
        return response
    
    def get_success_url(self):
        org = self.get_organization()
        return reverse_lazy('wiki:category_list', kwargs={'org_id': org.id})


class WikiCategoryUpdateView(WikiBaseView, UpdateView):
    """Edit an existing wiki category"""
    model = WikiCategory
    form_class = WikiCategoryForm
    template_name = 'wiki/category_form.html'
    pk_url_kwarg = 'pk'
    
    def get_queryset(self):
        org = self.get_organization()
        return WikiCategory.objects.filter(organization=org)
    
    def form_valid(self, form):
        response = super().form_valid(form)
        messages.success(self.request, f'Category "{self.object.name}" updated!')
        return response
    
    def get_success_url(self):
        org = self.get_organization()
        return reverse_lazy('wiki:category_list', kwargs={'org_id': org.id})


class WikiCategoryDeleteView(WikiBaseView, DeleteView):
    """Delete a wiki category"""
    model = WikiCategory
    template_name = 'wiki/category_confirm_delete.html'
    pk_url_kwarg = 'pk'
    
    def get_queryset(self):
        org = self.get_organization()
        return WikiCategory.objects.filter(organization=org)
    
    def delete(self, request, *args, **kwargs):
        org = self.get_organization()
        messages.success(request, f'Category deleted successfully!')
        return super().delete(request, *args, **kwargs)
    
    def get_success_url(self):
        org = self.get_organization()
        return reverse_lazy('wiki:category_list', kwargs={'org_id': org.id})


class WikiLinkCreateView(WikiBaseView, CreateView):
    """Link a wiki page to a task or board"""
    model = WikiLink
    form_class = WikiLinkForm
    template_name = 'wiki/link_form.html'
    
    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs['organization'] = self.get_organization()
        return kwargs
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        page_slug = self.kwargs.get('slug')
        if page_slug:
            context['page'] = get_object_or_404(
                WikiPage,
                slug=page_slug,
                organization=self.get_organization()
            )
        return context
    
    def form_valid(self, form):
        page_slug = self.kwargs.get('slug')
        page = get_object_or_404(
            WikiPage,
            slug=page_slug,
            organization=self.get_organization()
        )
        form.instance.wiki_page = page
        form.instance.created_by = self.request.user
        
        # Set the appropriate link (task or board)
        if form.cleaned_data.get('task'):
            form.instance.task = form.cleaned_data['task']
            form.instance.link_type = 'task'
        else:
            form.instance.board = form.cleaned_data['board']
            form.instance.link_type = 'board'
        
        response = super().form_valid(form)
        messages.success(self.request, 'Wiki page linked successfully!')
        return response
    
    def get_success_url(self):
        page_slug = self.kwargs.get('slug')
        return reverse_lazy('wiki:page_detail', kwargs={'slug': page_slug})


@login_required
def wiki_search(request):
    """Search wiki pages"""
    org = request.user.profile.organization if hasattr(request.user, 'profile') else None
    if not org:
        return redirect('home')
    
    query = request.GET.get('q', '')
    results = {
        'pages': [],
        # 'notes': [],  # Meeting notes feature removed
        'tasks': [],
        'boards': []
    }
    
    if query:
        # Search wiki pages
        results['pages'] = WikiPage.objects.filter(
            organization=org,
            is_published=True
        ).filter(
            Q(title__icontains=query) |
            Q(content__icontains=query)
        )[:10]
        
        # Search meeting notes - DISABLED
        # results['notes'] = MeetingNotes.objects.filter(
        #     organization=org
        # ).filter(
        #     Q(title__icontains=query) |
        #     Q(content__icontains=query)
        # )[:10]
        
        # Search tasks
        from kanban.models import Board
        results['tasks'] = Task.objects.filter(
            column__board__organization=org
        ).filter(
            Q(title__icontains=query) |
            Q(description__icontains=query)
        )[:10]
        
        # Search boards
        results['boards'] = Board.objects.filter(
            organization=org,
            name__icontains=query
        )[:10]
    
    return render(request, 'wiki/search_results.html', {
        'query': query,
        'results': results,
        'organization': org
    })



# MEETING FEATURE DISABLED - Functions commented out
# The following functions were part of the meetings feature which has been removed

# @login_required
# def meeting_notes_list(request):
#     """List all meeting notes for an organization"""
#     org = request.user.profile.organization if hasattr(request.user, 'profile') else None
#     if not org:
#         return redirect('home')
#     
#     notes = MeetingNotes.objects.filter(organization=org).prefetch_related('attendees')
#     
#     # Filter by related board if specified
#     board_id = request.GET.get('board_id')
#     if board_id:
#         notes = notes.filter(related_board_id=board_id)
#     
#     return render(request, 'wiki/meeting_notes_list.html', {
#         'notes': notes,
#         'organization': org,
#         'board_id': board_id
#     })


# @login_required
# def meeting_notes_create(request):
#     """Create meeting notes"""
#     org = request.user.profile.organization if hasattr(request.user, 'profile') else None
#     if not org:
#         return redirect('home')
#     
#     if request.method == 'POST':
#         form = MeetingNotesForm(request.POST, organization=org)
#         if form.is_valid():
#             notes = form.save(commit=False)
#             notes.organization = org
#             notes.created_by = request.user
#             notes.save()
#             
#             # Add attendees
#             attendee_usernames = request.POST.get('attendee_usernames', '').split(',')
#             for username in attendee_usernames:
#                 try:
#                     user = User.objects.get(username=username.strip())
#                     notes.attendees.add(user)
#                 except User.DoesNotExist:
#                     pass
#             
#             messages.success(request, 'Meeting notes created successfully!')
#             return redirect('wiki:meeting_notes_detail', pk=notes.pk)
#     else:
#         form = MeetingNotesForm(organization=org)
#     
#     return render(request, 'wiki/meeting_notes_form.html', {
#         'form': form,
#         'organization': org
#     })


# @login_required
# def meeting_notes_detail(request, pk):
#     """Display meeting notes"""
#     org = request.user.profile.organization if hasattr(request.user, 'profile') else None
#     if not org:
#         return redirect('home')
#     
#     notes = get_object_or_404(MeetingNotes, pk=pk, organization=org)
#     
#     return render(request, 'wiki/meeting_notes_detail.html', {
#         'notes': notes,
#         'organization': org
#     })



@login_required
@require_http_methods(['GET', 'POST'])
def quick_link_wiki(request, content_type, object_id):
    """Quick link wiki pages to tasks or boards"""
    # MVP Mode: Get organization, fall back to demo org if user doesn't have one
    org = request.user.profile.organization if hasattr(request.user, 'profile') and request.user.profile.organization else None
    
    # Get demo organization as fallback
    demo_org = Organization.objects.filter(is_demo=True).first()
    if not demo_org:
        demo_org = Organization.objects.filter(name='Demo - Acme Corporation').first()
    
    # Use user's org if available, otherwise use demo org
    if not org:
        org = demo_org
    
    # Build list of allowed organizations
    allowed_orgs = []
    if org:
        allowed_orgs.append(org)
    if demo_org and demo_org not in allowed_orgs:
        allowed_orgs.append(demo_org)
    
    if content_type == 'task':
        # Allow tasks from allowed organizations
        if allowed_orgs:
            item = get_object_or_404(Task, pk=object_id, column__board__organization__in=allowed_orgs)
        else:
            item = get_object_or_404(Task, pk=object_id)
    elif content_type == 'board':
        # Allow boards from allowed organizations
        if allowed_orgs:
            item = get_object_or_404(Board, pk=object_id, organization__in=allowed_orgs)
        else:
            item = get_object_or_404(Board, pk=object_id)
    else:
        return JsonResponse({'error': 'Invalid content type'}, status=400)
    
    if request.method == 'GET':
        form = QuickWikiLinkForm(organization=org)
        return render(request, 'wiki/quick_link_modal.html', {
            'form': form,
            'content_type': content_type,
            'object_id': object_id,
            'item': item
        })
    
    form = QuickWikiLinkForm(request.POST, organization=org)
    if form.is_valid():
        pages = form.cleaned_data['wiki_pages']
        for page in pages:
            WikiLink.objects.get_or_create(
                wiki_page=page,
                link_type=content_type,
                **{content_type: item},
                defaults={
                    'created_by': request.user,
                    'description': form.cleaned_data['link_description']
                }
            )
        
        # Check if this is an AJAX request
        if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            return JsonResponse({'success': True, 'message': 'Wiki pages linked successfully!'})
        
        # Regular form submission - redirect back
        if content_type == 'task':
            messages.success(request, 'Wiki pages linked to task successfully!')
            return redirect('task_detail', task_id=object_id)
        elif content_type == 'board':
            messages.success(request, 'Wiki pages linked to board successfully!')
            return redirect('board_detail', board_id=object_id)
    
    # If AJAX request with errors, return JSON
    if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
        return JsonResponse({'error': form.errors}, status=400)
    
    # Regular form submission with errors - re-render template
    return render(request, 'wiki/quick_link_modal.html', {
        'form': form,
        'content_type': content_type,
        'object_id': object_id,
        'item': item
    })


@login_required
def delete_wiki_link(request, link_id):
    """Delete a wiki link"""
    link = get_object_or_404(WikiLink, pk=link_id)
    
    # Access restriction removed - all authenticated users can delete wiki links
    can_delete = True
    
    # Store the redirect URL before deleting
    if link.board:
        redirect_url = reverse('board_detail', kwargs={'board_id': link.board.id})
    elif link.task:
        redirect_url = reverse('task_detail', kwargs={'task_id': link.task.id})
    else:
        redirect_url = reverse('home')
    
    # Delete the link
    wiki_page_title = link.wiki_page.title
    link.delete()
    
    messages.success(request, f'Successfully removed link to "{wiki_page_title}"')
    return redirect(redirect_url)


@login_required
def wiki_page_history(request, slug):
    """View wiki page version history"""
    org = request.user.profile.organization if hasattr(request.user, 'profile') else None
    if not org:
        return redirect('home')
    
    page = get_object_or_404(WikiPage, slug=slug, organization=org)
    versions = page.versions.all()
    
    return render(request, 'wiki/page_history.html', {
        'page': page,
        'versions': versions,
        'organization': org
    })


@login_required
def wiki_page_restore(request, slug, version_number):
    """Restore a previous version of a wiki page"""
    org = request.user.profile.organization if hasattr(request.user, 'profile') else None
    if not org:
        return redirect('home')
    
    page = get_object_or_404(WikiPage, slug=slug, organization=org)
    version = get_object_or_404(WikiPageVersion, page=page, version_number=version_number)
    
    # Create new version with restored content
    page.content = version.content
    page.title = version.title
    page.version += 1
    page.updated_by = request.user
    page.save()
    
    WikiPageVersion.objects.create(
        page=page,
        version_number=page.version,
        title=page.title,
        content=version.content,
        edited_by=request.user,
        change_summary=f'Restored from version {version_number}'
    )
    
    messages.success(request, f'Page restored to version {version_number}')
    return redirect('wiki:page_detail', slug=slug)


# Import User model
from django.contrib.auth.models import User
from django.utils import timezone
import json


# ============================================================================
# MEETING HUB VIEWS - Unified Meeting Management
# ============================================================================

@login_required
def knowledge_hub_home(request):
    """Unified Knowledge Hub - Wiki Documentation with AI"""
    org = request.user.profile.organization if hasattr(request.user, 'profile') else None
    if not org:
        return redirect('dashboard')
    
    # Get search query
    search_query = request.GET.get('q', '')
    
    # Include demo organization content for all authenticated users
    demo_org = Organization.objects.filter(name='Demo - Acme Corporation').first()
    org_filter = Q(organization=org)
    if demo_org:
        org_filter |= Q(organization=demo_org)
    
    # Get wiki pages from user's org AND demo org
    wiki_pages = WikiPage.objects.filter(org_filter, is_published=True).select_related('category', 'created_by')
    if search_query:
        wiki_pages = wiki_pages.filter(
            Q(title__icontains=search_query) |
            Q(content__icontains=search_query) |
            Q(tags__contains=search_query)
        )
    wiki_pages = wiki_pages.order_by('-is_pinned', '-updated_at')[:20]
    
    # Get statistics (include demo org content)
    total_wiki_pages = WikiPage.objects.filter(org_filter, is_published=True).count()
    total_views = WikiPage.objects.filter(org_filter, is_published=True).aggregate(
        total=Sum('view_count'))['total'] or 0
    
    # Get wiki categories (include demo org categories)
    wiki_categories = WikiCategory.objects.filter(org_filter).prefetch_related('pages').distinct()
    
    return render(request, 'wiki/knowledge_hub_home.html', {
        'organization': org,
        'wiki_pages': wiki_pages,
        'search_query': search_query,
        'total_wiki_pages': total_wiki_pages,
        'total_views': total_views,
        'wiki_categories': wiki_categories,
    })


# @login_required
# def meeting_hub_home(request):
#     """Main Meeting Hub dashboard - Legacy view, redirects to unified Knowledge Hub"""
#     return redirect('wiki:knowledge_hub_home')


# @login_required
# def meeting_hub_upload(request, board_id=None):
#     """Upload and analyze meeting transcript"""
#     org = request.user.profile.organization if hasattr(request.user, 'profile') else None
#     if not org:
#         return redirect('home')
#     
#     board = None
#     if board_id:
#         board = get_object_or_404(Board, id=board_id, organization=org)
#         # Check board access
#         if not (board.created_by == request.user or request.user in board.members.all()):
#             return redirect('home')
#     
#     if request.method == 'POST':
#         form = MeetingNotesForm(request.POST, request.FILES, organization=org)
#         if form.is_valid():
#             notes = form.save(commit=False)
#             notes.organization = org
#             notes.created_by = request.user
#             if board:
#                 notes.related_board = board
#             notes.processing_status = 'processing'
#             notes.save()
#             
#             # Add attendees
#             attendee_usernames = request.POST.get('attendee_usernames', '').split(',')
#             for username in attendee_usernames:
#                 try:
#                     user = User.objects.get(username=username.strip())
#                     notes.attendees.add(user)
#                 except User.DoesNotExist:
#                     pass
#             
#             messages.success(request, 'Meeting notes created! Processing transcript...')
#             return redirect('wiki:meeting_notes_detail', pk=notes.pk)
#     else:
#         form = MeetingNotesForm(organization=org)
#     
#     # Get previous meetings from same board for context
#     previous_meetings = []
#     if board:
#         previous_meetings = MeetingNotes.objects.filter(
#             related_board=board,
#             organization=org
#         ).order_by('-date')[:5]
#     
#     return render(request, 'wiki/meeting_hub_upload.html', {
#         'form': form,
#         'organization': org,
#         'board': board,
#         'previous_meetings': previous_meetings
#     })


# @login_required
# def meeting_hub_list(request):
#     """List all meetings in the organization"""
#     org = request.user.profile.organization if hasattr(request.user, 'profile') else None
#     if not org:
#         return redirect('home')
#     
#     meetings = MeetingNotes.objects.filter(organization=org).prefetch_related(
#         'attendees', 'related_board'
#     ).order_by('-date')
#     
#     # Filtering
#     meeting_type = request.GET.get('type')
#     if meeting_type:
#         meetings = meetings.filter(meeting_type=meeting_type)
#     
#     board_id = request.GET.get('board_id')
#     if board_id:
#         meetings = meetings.filter(related_board_id=board_id)
#     
#     status = request.GET.get('status')
#     if status:
#         meetings = meetings.filter(processing_status=status)
#     
#     # Search
#     query = request.GET.get('q')
#     if query:
#         meetings = meetings.filter(
#             Q(title__icontains=query) |
#             Q(content__icontains=query)
#         )
#     
#     # Pagination
#     from django.core.paginator import Paginator
#     paginator = Paginator(meetings, 20)
#     page_number = request.GET.get('page')
#     page_obj = paginator.get_page(page_number)
#     
#     # Get available boards for filter
#     boards = Board.objects.filter(
#         organization=org,
#         meeting_notes__isnull=False
#     ).distinct()
#     
#     return render(request, 'wiki/meeting_hub_list.html', {
#         'page_obj': page_obj,
#         'meetings': page_obj.object_list,
#         'organization': org,
#         'boards': boards,
#         'meeting_types': MeetingNotes.MEETING_TYPE_CHOICES,
#         'current_type': meeting_type,
#         'current_board': board_id,
#         'current_status': status,
#         'query': query
#     })


# @login_required
# def meeting_hub_detail(request, pk):
#     """Display meeting notes with AI extraction results"""
#     org = request.user.profile.organization if hasattr(request.user, 'profile') else None
#     if not org:
#         return redirect('home')
#     
#     notes = get_object_or_404(MeetingNotes, pk=pk, organization=org)
#     
#     # Parse extraction results if available
#     extracted_tasks = []
#     if notes.extraction_results:
#         extracted_tasks = notes.extraction_results.get('extracted_tasks', [])
#     
#     return render(request, 'wiki/meeting_hub_detail.html', {
#         'notes': notes,
#         'organization': org,
#         'extracted_tasks': extracted_tasks,
#         'attendees': notes.attendees.all(),
#         'action_items': notes.action_items,
#         'decisions': notes.decisions
#     })


# @login_required
# def meeting_hub_analytics(request):
#     """Meeting Hub analytics and insights"""
#     org = request.user.profile.organization if hasattr(request.user, 'profile') else None
#     if not org:
#         return redirect('home')
#     
#     from django.db.models import Count, Sum, Avg
#     from datetime import timedelta
#     
#     # Time range filtering
#     days = int(request.GET.get('days', 30))
#     start_date = timezone.now() - timedelta(days=days)
#     
#     meetings = MeetingNotes.objects.filter(
#         organization=org,
#         date__gte=start_date
#     )
#     
#     # Analytics data
#     analytics = {
#         'total_meetings': meetings.count(),
#         'total_tasks_created': meetings.aggregate(Sum('tasks_created_count'))['tasks_created_count__sum'] or 0,
#         'avg_meeting_duration': meetings.aggregate(Avg('duration_minutes'))['duration_minutes__avg'] or 0,
#         'meetings_by_type': meetings.values('meeting_type').annotate(count=Count('id')),
#         'meetings_by_board': meetings.filter(related_board__isnull=False).values(
#             'related_board__name'
#         ).annotate(count=Count('id')),
#         'most_active_attendees': User.objects.filter(
#             meeting_notes_attended__organization=org,
#             meeting_notes_attended__date__gte=start_date
#         ).annotate(meeting_count=Count('meeting_notes_attended')).order_by('-meeting_count')[:10]
#     }
#     
#     return render(request, 'wiki/meeting_hub_analytics.html', {
#         'organization': org,
#         'analytics': analytics,
#         'days': days
#     })

# END OF DISABLED MEETING FUNCTIONS
