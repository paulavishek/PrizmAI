from django.urls import path

from . import views

urlpatterns = [
    path('', views.form_list, name='form_list'),
    path('create/', views.form_create, name='form_create'),
    path('<uuid:form_id>/', views.form_detail, name='form_detail'),
    path('<uuid:form_id>/edit/', views.form_edit, name='form_edit'),
    path('<uuid:form_id>/fill/', views.form_fill, name='form_fill'),
    path('<uuid:form_id>/toggle/', views.form_toggle_active, name='form_toggle_active'),
    path('<uuid:form_id>/delete/', views.form_delete, name='form_delete'),
    path('submission/<int:submission_id>/status/', views.form_submission_status, name='form_submission_status'),
]
