from django.urls import path
from integrations import views

app_name = "integrations"

urlpatterns = [
    # Inbound GitHub webhook receiver (no auth — HMAC-verified)
    path("github/", views.github_webhook_receiver, name="github_receiver"),

    # Board settings UI
    path("boards/<int:board_id>/github/", views.github_integration_settings, name="github_settings"),

    # Live migration wizard (import a whole project from another PM tool via API)
    path("migrate/", views.migration_start, name="migrate_start"),
    path("migrate/connect/", views.migration_connect, name="migrate_connect"),
    path("migrate/run/", views.migration_run, name="migrate_run"),
    path("migrate/status/<str:task_id>/", views.migration_status, name="migrate_status"),
]
