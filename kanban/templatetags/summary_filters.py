"""
Template filter: render_bullets
Converts AI summary text (either • bullet lines or legacy paragraph) to HTML <ul>.

Usage in templates:
    {% load summary_filters %}
    {{ obj.ai_summary|render_bullets }}
"""
from django import template
from django.utils.html import escape
from django.utils.safestring import mark_safe

register = template.Library()


@register.filter(name='render_bullets', is_safe=True)
def render_bullets(text):
    """
    Convert AI summary text to a compact <ul> bullet list.

    Handles two cases:
    1. New-format summaries: lines starting with '•' or '-' become <li> items.
    2. Legacy paragraph summaries (no bullet prefix): split by '. ' into sentences,
       each becoming its own <li> for visual scannability.
    """
    if not text:
        return mark_safe('')

    text = str(text).strip()
    lines = [line.strip() for line in text.splitlines()]
    bullet_lines = []

    # Try bullet-format first (•, *, or - prefix)
    for line in lines:
        if not line:
            continue
        if line.startswith('•'):
            bullet_lines.append(line.lstrip('•').strip())
        elif line.startswith('* ') or line == '*':
            bullet_lines.append(line[1:].strip())
        elif line.startswith('- ') or (line.startswith('-') and len(line) > 2):
            bullet_lines.append(line[1:].strip())

    # Fallback: paragraph text — split on sentence boundaries
    if not bullet_lines:
        import re
        sentences = re.split(r'(?<=[.!?])\s+', text)
        bullet_lines = [s.strip() for s in sentences if s.strip()]

    if not bullet_lines:
        return mark_safe(f'<span class="ai-summary-plain">{escape(text)}</span>')

    items_html = ''.join(
        f'<li>{escape(item)}</li>'
        for item in bullet_lines
        if item
    )
    return mark_safe(f'<ul class="ai-bullet-list mb-0">{items_html}</ul>')


@register.filter(name='prettify_feature', is_safe=True)
def prettify_feature(text):
    """Convert internal feature code names to human-readable labels."""
    if not text:
        return text
    DISPLAY_NAMES = {
        'strategy_summary_dashboard': 'Strategy Summary',
        'Strategy_Summary_Dashboard': 'Strategy Summary',
        'mission_summary_dashboard': 'Mission Summary',
        'Mission_Summary_Dashboard': 'Mission Summary',
        'board_summary_dashboard': 'Board Summary',
        'Board_Summary_Dashboard': 'Board Summary',
        'goal_summary_dashboard': 'Goal Summary',
        'Goal_Summary_Dashboard': 'Goal Summary',
        'next_task_suggestion': 'Next Task Suggestion',
        'priority_suggestion': 'Priority Suggestion',
        'ai_coach': 'AI Coach',
        'ai_assistant': 'AI Assistant',
    }
    key = str(text)
    if key in DISPLAY_NAMES:
        return DISPLAY_NAMES[key]
    # Fallback: replace underscores with spaces, strip common suffixes, title case
    label = key.lower().replace('_dashboard', '').replace('_', ' ').strip()
    return label.title()
