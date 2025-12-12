"""
URL configuration for kanban_board project.

The `urlpatterns` list routes URLs to views. For more information please see:
    https://docs.djangoproject.com/en/5.2/topics/http/urls/
Examples:
Function views
    1. Add an import:  from my_app import views
    2. Add a URL to urlpatterns:  path('', views.home, name='home')
Class-based views
    1. Add an import:  from other_app.views import Home
    2. Add a URL to urlpatterns:  path('', Home.as_view(), name='home')
Including another URLconf
    1. Import the include() function: from django.urls import include, path
    2. Add a URL to urlpatterns:  path('blog/', include('blog.urls'))
"""
from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static

urlpatterns = [
    path('admin/', admin.site.urls),
    path('', include('kanban.urls')),
    path('stakeholder/', include('kanban.stakeholder_urls')),
    path('accounts/', include('accounts.urls')),
    path('accounts/', include('allauth.urls')),  # Add allauth URLs
    path('assistant/', include('ai_assistant.urls')),  # AI Project Assistant URLs
    path('messaging/', include('messaging.urls')),  # Real-time messaging URLs
    path('wiki/', include('wiki.urls')),  # Wiki and Knowledge Base URLs
    path('api/v1/', include('api.v1.urls')),  # RESTful API v1
    path('api/ai-usage/', include('api.ai_usage_urls')),  # AI Usage tracking
    path('webhooks/', include('webhooks.urls')),  # Webhook management
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
    urlpatterns += static(settings.STATIC_URL, document_root=settings.STATIC_ROOT)

