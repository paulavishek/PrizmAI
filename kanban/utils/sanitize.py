"""
Shared HTML sanitization utility for PrizmAI.

Used by:
- Task description (Tiptap HTML output)
- Wiki page content (Markdown → HTML)
- Meeting transcript content (Markdown → HTML)

All consumer code should import `sanitize_html` or `sanitize_html_safe` from here
rather than defining their own bleach configuration.
"""

import bleach
from django.utils.safestring import mark_safe

# Tags produced by Tiptap (StarterKit + Link + Image + Highlight + Underline)
# and by the Markdown renderer used by the wiki.
ALLOWED_TAGS = [
    'p', 'br', 'strong', 'em', 'u', 's', 'del', 'ins',
    'h1', 'h2', 'h3', 'h4', 'h5', 'h6',
    'ul', 'ol', 'li',
    'a', 'code', 'pre', 'blockquote',
    'table', 'thead', 'tbody', 'tr', 'th', 'td',
    'hr', 'img', 'div', 'span',
    'mark',  # Tiptap Highlight extension
]

ALLOWED_ATTRIBUTES = {
    'a': ['href', 'title', 'rel'],
    'img': ['src', 'alt', 'title', 'width', 'height'],
    'code': ['class'],   # syntax highlighting class
    'pre': ['class'],
    'div': ['class'],
    'span': ['class', 'style'],
    'mark': ['class', 'style'],  # Tiptap highlight colour
    'h1': ['id'],        # anchor links from TOC
    'h2': ['id'],
    'h3': ['id'],
    'h4': ['id'],
    'h5': ['id'],
    'h6': ['id'],
    'td': ['class', 'style'],
    'th': ['class', 'style'],
}

ALLOWED_PROTOCOLS = ['http', 'https', 'mailto']


def sanitize_html(html_content):
    """
    Sanitize an HTML string to prevent XSS attacks.

    Returns a plain Python string (not mark_safe).  Call `sanitize_html_safe`
    when the result will be rendered directly in a template.
    """
    if not html_content:
        return ''
    return bleach.clean(
        html_content,
        tags=ALLOWED_TAGS,
        attributes=ALLOWED_ATTRIBUTES,
        protocols=ALLOWED_PROTOCOLS,
        strip=True,
    )


def sanitize_html_safe(html_content):
    """
    Sanitize HTML and return a ``mark_safe`` string suitable for ``{{ value }}``
    template rendering without auto-escaping.
    """
    return mark_safe(sanitize_html(html_content))
