from django.urls import path
from integrations import views

app_name = "integrations"

urlpatterns = [
    # Inbound GitHub webhook receiver (no auth — HMAC-verified)
    path("github/", views.github_webhook_receiver, name="github_receiver"),

    # Board settings UI
    path("boards/<int:board_id>/github/", views.github_integration_settings, name="github_settings"),
]
