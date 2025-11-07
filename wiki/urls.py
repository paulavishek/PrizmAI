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
    
    # Meeting Hub API Endpoints - DISABLED (feature removed)
    # path('api/meetings/<int:meeting_id>/analyze/', api_views.analyze_meeting_transcript_api, 
    #      name='api_analyze_transcript'),
    # path('api/meetings/<int:meeting_id>/details/', api_views.get_meeting_details_api,
    #      name='api_meeting_details'),
    # path('api/meetings/create-tasks/', api_views.create_tasks_from_extraction_api,
    #      name='api_create_tasks_from_extraction'),
    
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
    
    # Search
    path('search/', views.wiki_search, name='search'),
    
    # Legacy Meeting Notes (kept for backward compatibility) - DISABLED
    # path('meeting-notes/', views.meeting_notes_list, name='meeting_notes_list'),
    # path('meeting-notes/create/', views.meeting_notes_create, name='meeting_notes_create'),
    # path('meeting-notes/<int:pk>/', views.meeting_notes_detail, name='meeting_notes_detail'),
]
