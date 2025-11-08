"""
URL Configuration for Webhooks
"""
from django.urls import path
from webhooks import views

app_name = 'webhooks'

urlpatterns = [
    # Webhook management
    path('boards/<int:board_id>/webhooks/', views.webhook_list, name='webhook_list'),
    path('boards/<int:board_id>/webhooks/create/', views.webhook_create, name='webhook_create'),
    path('webhooks/<int:webhook_id>/', views.webhook_detail, name='webhook_detail'),
    path('webhooks/<int:webhook_id>/edit/', views.webhook_edit, name='webhook_edit'),
    path('webhooks/<int:webhook_id>/delete/', views.webhook_delete, name='webhook_delete'),
    path('webhooks/<int:webhook_id>/toggle/', views.webhook_toggle, name='webhook_toggle'),
    path('webhooks/<int:webhook_id>/test/', views.webhook_test, name='webhook_test'),
    
    # Event logs
    path('boards/<int:board_id>/webhook-events/', views.webhook_events, name='webhook_events'),
]
