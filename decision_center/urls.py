"""Decision Center URL configuration."""
from django.urls import path
from . import views

app_name = 'decision_center'

urlpatterns = [
    path(
        'decision-center/',
        views.decision_center_view,
        name='decision_center',
    ),
    path(
        'decision-center/settings/',
        views.decision_center_settings_view,
        name='decision_center_settings',
    ),
    path(
        'decision-center/widget/',
        views.decision_center_widget_data,
        name='decision_center_widget',
    ),
    path(
        'decision-center/item/<int:item_id>/resolve/',
        views.resolve_decision_item,
        name='resolve_decision_item',
    ),
    path(
        'decision-center/item/<int:item_id>/snooze/',
        views.snooze_decision_item,
        name='snooze_decision_item',
    ),
    path(
        'decision-center/item/<int:item_id>/dismiss/',
        views.dismiss_decision_item,
        name='dismiss_decision_item',
    ),
    path(
        'decision-center/resolve-all-quick-wins/',
        views.resolve_all_quick_wins,
        name='resolve_all_quick_wins',
    ),
]
