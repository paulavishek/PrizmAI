from django.urls import path
from . import views

urlpatterns = [
    # Board-specific knowledge
    path('boards/<int:board_id>/knowledge/', views.board_knowledge, name='board_knowledge'),
    path('boards/<int:board_id>/knowledge/add/', views.add_manual_memory, name='add_manual_memory'),
    path('boards/<int:board_id>/deja-vu/', views.deja_vu_check, name='deja_vu_check'),
    # Global organizational memory
    path('memory/', views.organizational_memory, name='organizational_memory'),
    path('memory/search/', views.organizational_memory_search, name='organizational_memory_search'),
    path('memory/feedback/<int:query_id>/', views.memory_feedback, name='memory_feedback'),
]
