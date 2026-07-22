"""
Template tag for rendering Feature Guide help badges on AI feature pages.

Usage:
    {% load feature_guide_tags %}
    <h2>Shadow Board {% feature_help "shadow_board" %}</h2>

Renders a styled "What is this?" pill badge that opens a popover on click,
plus a hidden modal with the detailed description.
"""
from django import template
from django.utils.safestring import mark_safe

register = template.Library()

# Module-level cache cleared on server restart; good enough for ~10 rows
# that rarely change.
_cache = {}


def _get_guide(feature_key):
    """Fetch a FeatureGuide by key, caching in-process."""
    if feature_key not in _cache:
        from kanban.feature_guide_models import FeatureGuide
        try:
            guide = FeatureGuide.objects.get(
                feature_key=feature_key, is_active=True
            )
        except FeatureGuide.DoesNotExist:
            guide = None
        _cache[feature_key] = guide
    return _cache[feature_key]


@register.simple_tag
def feature_help(feature_key):
    """
    Render a 'What is this?' badge + modal for the given feature_key.
    Returns empty string if the key doesn't exist or is inactive.
    """
    guide = _get_guide(feature_key)
    if guide is None:
        return ''

    # Escape quotes in the brief for safe embedding in a data-attribute.
    brief_escaped = (
        guide.brief_description
        .replace('&', '&amp;')
        .replace('"', '&quot;')
        .replace("'", '&#39;')
        .replace('<', '&lt;')
        .replace('>', '&gt;')
    )

    modal_id = f'featureGuideModal-{feature_key}'

    # Popover content: brief text + "Learn more" link
    popover_content = (
        f'{brief_escaped}'
        f'&lt;div class=&quot;mt-2&quot;&gt;'
        f'&lt;a href=&quot;#&quot; class=&quot;feature-guide-learn-more small&quot; '
        f'data-modal-target=&quot;{modal_id}&quot;&gt;'
        f'Learn more &amp;rarr;&lt;/a&gt;&lt;/div&gt;'
    )

    # The badge button
    badge_html = (
        f'<button type="button" '
        f'class="feature-guide-badge" '
        f'data-bs-toggle="popover" '
        f'data-bs-trigger="click" '
        f'data-bs-placement="bottom" '
        f'data-bs-html="true" '
        f'data-bs-content="{popover_content}" '
        f'aria-label="What is {guide.feature_name}?">'
        f'<i class="fas fa-circle-question me-1"></i>'
        f'<span class="d-none d-md-inline">What is this?</span>'
        f'</button>'
    )

    # The detail modal
    modal_html = (
        f'<div class="modal fade feature-guide-modal" id="{modal_id}" '
        f'tabindex="-1" aria-labelledby="{modal_id}-label" aria-hidden="true">'
        f'<div class="modal-dialog modal-dialog-scrollable modal-lg">'
        f'<div class="modal-content">'
        f'<div class="modal-header">'
        f'<h5 class="modal-title" id="{modal_id}-label">'
        f'<i class="fas fa-circle-question text-primary me-2"></i>'
        f'{guide.feature_name}</h5>'
        f'<button type="button" class="btn-close" data-bs-dismiss="modal" '
        f'aria-label="Close"></button>'
        f'</div>'
        f'<div class="modal-body">{guide.detailed_description}</div>'
        f'<div class="modal-footer">'
        f'<button type="button" class="btn btn-secondary btn-sm" '
        f'data-bs-dismiss="modal">Close</button>'
        f'</div></div></div></div>'
    )

    return mark_safe(badge_html + modal_html)


@register.simple_tag
def clear_feature_guide_cache():
    """Clear the in-process feature guide cache (for admin/debug use)."""
    _cache.clear()
    return ''
