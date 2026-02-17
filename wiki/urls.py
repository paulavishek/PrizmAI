from django.urls import path
from . import views
from . import api_views

app_name = 'wiki'

urlpatterns = [
    # Knowledge Hub - Wiki Documentation with AI
    path('knowledge/', views.knowledge_hub_home, name='knowledge_hub_home'),
    
    # Meeting Hub - DISABLED (feature removed)
    # path('meetings/', views.meeting_hub_home, name='meeting_hub_home'),
    # path('meetings/list/', views.meeting_hub_list, name='meeting_hub_list'),
    # path('meetings/upload/', views.meeting_hub_upload, name='meeting_hub_upload'),
    # path('meetings/upload/<int:board_id>/', views.meeting_hub_upload, name='meeting_hub_upload_for_board'),
    # path('meetings/<int:pk>/', views.meeting_hub_detail, name='meeting_hub_detail'),
    # path('meetings/analytics/', views.meeting_hub_analytics, name='meeting_hub_analytics'),
    
    # Wiki Meeting Assistant API Endpoints
    path('api/wiki-page/<int:wiki_page_id>/analyze/', api_views.analyze_wiki_meeting_page,
         name='api_analyze_wiki_meeting'),
    path('api/wiki-page/<int:wiki_page_id>/analyze-documentation/', api_views.analyze_wiki_documentation_page,
         name='api_analyze_wiki_documentation'),
    path('api/wiki-page/<int:wiki_page_id>/import-transcript/', api_views.import_transcript_to_wiki_page,
         name='api_import_transcript'),
    path('api/meeting-analysis/<int:analysis_id>/details/', api_views.get_meeting_analysis_details,
         name='api_meeting_analysis_details'),
    path('api/meeting-analysis/<int:analysis_id>/create-tasks/', api_views.create_tasks_from_meeting_analysis,
         name='api_create_tasks_from_analysis'),
    path('api/meeting-analysis/<int:analysis_id>/mark-reviewed/', api_views.mark_analysis_reviewed,
         name='api_mark_analysis_reviewed'),
    path('api/extract-text-from-file/', api_views.extract_text_from_uploaded_file,
         name='api_extract_text_from_file'),
    path('api/boards/', api_views.get_boards_for_organization,
         name='api_get_boards'),
    
    # Category Management
    path('categories/', views.WikiCategoryListView.as_view(), name='category_list'),
    path('categories/create/', views.WikiCategoryCreateView.as_view(), name='category_create'),
    path('categories/<int:pk>/edit/', views.WikiCategoryUpdateView.as_view(), name='category_edit'),
    path('categories/<int:pk>/delete/', views.WikiCategoryDeleteView.as_view(), name='category_delete'),
    
    # Page Management
    path('', views.WikiPageListView.as_view(), name='page_list'),
    path('category/<int:category_id>/', views.WikiPageListView.as_view(), name='page_list_by_category'),
    path('create/', views.WikiPageCreateView.as_view(), name='page_create'),
    path('page/<slug:slug>/', views.WikiPageDetailView.as_view(), name='page_detail'),
    path('page/<slug:slug>/edit/', views.WikiPageUpdateView.as_view(), name='page_edit'),
    path('page/<slug:slug>/delete/', views.WikiPageDeleteView.as_view(), name='page_delete'),
    path('page/<slug:slug>/history/', views.wiki_page_history, name='page_history'),
    path('page/<slug:slug>/restore/<int:version_number>/', views.wiki_page_restore, name='page_restore'),
    
    # Wiki Links
    path('page/<slug:slug>/link/', views.WikiLinkCreateView.as_view(), name='link_create'),
    path('quick-link/<str:content_type>/<int:object_id>/', views.quick_link_wiki, name='quick_link'),
    path('delete-link/<int:link_id>/', views.delete_wiki_link, name='delete_link'),
    
    # Search
    path('search/', views.wiki_search, name='search'),
    
    # Legacy Meeting Notes (kept for backward compatibility) - DISABLED
    # path('meeting-notes/', views.meeting_notes_list, name='meeting_notes_list'),
    # path('meeting-notes/create/', views.meeting_notes_create, name='meeting_notes_create'),
    # path('meeting-notes/<int:pk>/', views.meeting_notes_detail, name='meeting_notes_detail'),
]
