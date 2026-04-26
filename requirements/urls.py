from django.urls import path

from . import views

app_name = 'requirements'

urlpatterns = [
    # Dashboard (list)
    path('board/<int:board_id>/', views.requirements_dashboard, name='dashboard'),

    # CRUD
    path('board/<int:board_id>/create/', views.requirement_create, name='requirement_create'),
    path('board/<int:board_id>/<int:pk>/', views.requirement_detail, name='requirement_detail'),
    path('board/<int:board_id>/<int:pk>/edit/', views.requirement_update, name='requirement_update'),
    path('board/<int:board_id>/<int:pk>/delete/', views.requirement_delete, name='requirement_delete'),

    # Quick status update
    path('board/<int:board_id>/<int:pk>/status/', views.requirement_status_update, name='status_update'),

    # Comments
    path('board/<int:board_id>/<int:pk>/comment/', views.requirement_add_comment, name='add_comment'),

    # Link / unlink
    path('board/<int:board_id>/<int:pk>/link-task/', views.requirement_link_task, name='link_task'),
    path('board/<int:board_id>/<int:pk>/unlink-task/', views.requirement_unlink_task, name='unlink_task'),
    path('board/<int:board_id>/<int:pk>/link-objective/', views.requirement_link_objective, name='link_objective'),

    # Category & Objective
    path('board/<int:board_id>/category/create/', views.category_create, name='category_create'),
    path('board/<int:board_id>/objective/create/', views.objective_create, name='objective_create'),

    # Traceability matrix
    path('board/<int:board_id>/traceability/', views.traceability_matrix, name='traceability_matrix'),

    # Export
    path('board/<int:board_id>/export/', views.export_requirements_csv, name='export_csv'),

    # API (JSON)
    path('board/<int:board_id>/api/data/', views.api_requirements_data, name='api_requirements_data'),

    # AI Analysis
    path('board/<int:board_id>/<int:pk>/ai/quality/', views.requirement_ai_quality_check, name='ai_quality_check'),
    path('board/<int:board_id>/<int:pk>/ai/criteria/', views.requirement_ai_generate_criteria, name='ai_generate_criteria'),
    path('board/<int:board_id>/<int:pk>/ai/impact/', views.requirement_ai_impact_analysis, name='ai_impact_analysis'),
    path('board/<int:board_id>/ai/gaps/', views.board_requirements_gap_analysis, name='ai_gap_analysis'),
]
