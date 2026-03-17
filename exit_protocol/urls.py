from django.urls import path
from . import views

app_name = 'exit_protocol'

urlpatterns = [
    # Hospice / Dashboard (board-scoped)
    path('boards/<int:board_id>/exit-protocol/', views.exit_protocol_dashboard, name='dashboard'),
    path('boards/<int:board_id>/exit-protocol/initiate/', views.initiate_hospice, name='initiate'),
    path('boards/<int:board_id>/exit-protocol/recalculate/', views.recalculate_health_score, name='recalculate'),
    path('boards/<int:board_id>/exit-protocol/checklist/<str:item_id>/complete/', views.complete_checklist_item, name='complete_checklist_item'),
    path('boards/<int:board_id>/exit-protocol/transition-memos/', views.view_transition_memos, name='transition_memos'),
    path('boards/<int:board_id>/exit-protocol/bury/', views.bury_project, name='bury'),
    path('boards/<int:board_id>/exit-protocol/dismiss-banner/', views.dismiss_hospice_banner, name='dismiss_banner'),

    # Organ Transplant (board-scoped)
    path('boards/<int:board_id>/exit-protocol/organs/', views.organ_bank, name='organ_bank'),

    # Organ Transplant (global)
    path('exit-protocol/organ-library/', views.organ_library, name='organ_library'),
    path('exit-protocol/organs/<int:organ_id>/transplant/', views.transplant_organ, name='transplant'),
    path('exit-protocol/organs/<int:organ_id>/reject/', views.reject_organ, name='reject_organ'),

    # Cemetery (global)
    path('cemetery/', views.cemetery, name='cemetery'),
    path('cemetery/<int:entry_id>/', views.autopsy_report, name='autopsy_report'),
    path('cemetery/<int:entry_id>/lessons/update/', views.update_lessons, name='update_lessons'),
    path('cemetery/<int:entry_id>/resurrect/', views.resurrect_project, name='resurrect'),
    path('cemetery/<int:entry_id>/export-pdf/', views.export_autopsy_pdf, name='export_pdf'),
]
