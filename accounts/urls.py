from django.urls import path
from django.contrib.auth import views as auth_views
from . import views
from .forms import CustomSetPasswordForm

# Import analytics logout view to replace default logout
from analytics.views import CustomLogoutView

urlpatterns = [
    path('login/', views.login_view, name='login'),
    path('logout/', CustomLogoutView.as_view(), name='logout'),  # Use analytics logout view
    path('register/', views.register_view, name='register'),
    path('register/<int:org_id>/', views.register_view, name='register_with_org'),
    path('organization-choice/', views.organization_choice, name='organization_choice'),
    path('join-organization/', views.join_organization, name='join_organization'),
    path('create-organization/', views.create_organization, name='create_organization'),
    path('profile/', views.profile_view, name='profile'),
    path('organization/members/', views.organization_members, name='organization_members'),
    path('organization/settings/', views.organization_settings, name='organization_settings'),
    path('organization/toggle-admin/<int:profile_id>/', views.toggle_admin, name='toggle_admin'),
    path('organization/remove-member/<int:profile_id>/', views.remove_member, name='remove_member'),
    path('organization/delete/', views.delete_organization, name='delete_organization'),
    
    # Social login completion
    path('social-signup-complete/', views.social_signup_complete, name='social_signup_complete'),
    
    # Password Reset URLs
    path('password-reset/', 
         auth_views.PasswordResetView.as_view(
             template_name='accounts/password_reset.html',
             email_template_name='accounts/password_reset_email.html',
             subject_template_name='accounts/password_reset_subject.txt',
             success_url='/accounts/password-reset/done/'
         ),
         name='password_reset'),
    
    path('password-reset/done/',
         auth_views.PasswordResetDoneView.as_view(
             template_name='accounts/password_reset_done.html'
         ),
         name='password_reset_done'),
      path('reset/<uidb64>/<token>/',
         auth_views.PasswordResetConfirmView.as_view(
             template_name='accounts/password_reset_confirm.html',
             form_class=CustomSetPasswordForm,
             success_url='/accounts/reset/complete/'
         ),
         name='password_reset_confirm'),
    
    path('reset/complete/',
         auth_views.PasswordResetCompleteView.as_view(
             template_name='accounts/password_reset_complete.html'
         ),
         name='password_reset_complete'),
]