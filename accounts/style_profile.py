"""User AI response-style profile → prompt directive.

Single source of truth for turning a user's persisted formatting preferences
(tone / length / structure + a free-text catch-all on ``UserProfile``) into a
compact prompt fragment. Injected into narrative AI surfaces only (PrizmBrief,
Retrospectives, AI Coach, Spectra chat) — NOT the shared ``generate_ai_content``
wrapper, which many structured/JSON-emitting callers depend on.

Design invariant: when every preference is at its ``'default'`` value and the
free-text field is blank, ``build_ai_style_directive`` returns ``""`` so the
prompt is byte-identical to today's behavior for users who never set a profile.
"""

# Human-readable directive fragments keyed by the stored choice value.
# 'default' intentionally maps to nothing (no directive contribution).
_TONE_DIRECTIVES = {
    'formal': 'Tone: Formal and professional.',
    'conversational': 'Tone: Conversational and approachable.',
    'executive': 'Tone: Executive — high-level, decisive, leadership-friendly.',
}
_LENGTH_DIRECTIVES = {
    'brief': 'Length: Brief — keep it tight; only the essentials.',
    'standard': 'Length: Standard — balanced detail.',
    'detailed': 'Length: Detailed — thorough, with supporting context.',
}
_STRUCTURE_DIRECTIVES = {
    'bullets': 'Structure: Prefer bullet points and short lists over long prose.',
    'narrative': 'Structure: Prefer flowing narrative paragraphs over bullet lists.',
}

# Cap the free-text contribution defensively; the model field already limits to
# 600 chars, but call-sites may pass unsaved/edited values.
_MAX_CUSTOM_CHARS = 600


def build_ai_style_directive(profile) -> str:
    """Return a prompt block describing the user's formatting preferences.

    Returns an empty string when ``profile`` is falsy or every preference is at
    its default (and no custom instructions are set), so callers can splice the
    result unconditionally.

    Args:
        profile: a ``UserProfile`` instance, or ``None``. Passing a ``User`` is
            not supported — resolve ``user.profile`` (guarded) at the call-site.
    """
    if profile is None:
        return ''

    lines = []

    tone = _TONE_DIRECTIVES.get(getattr(profile, 'response_tone', 'default') or 'default')
    if tone:
        lines.append(f'- {tone}')

    length = _LENGTH_DIRECTIVES.get(getattr(profile, 'response_length', 'default') or 'default')
    if length:
        lines.append(f'- {length}')

    structure = _STRUCTURE_DIRECTIVES.get(getattr(profile, 'response_structure', 'default') or 'default')
    if structure:
        lines.append(f'- {structure}')

    custom = (getattr(profile, 'custom_ai_instructions', '') or '').strip()
    if custom:
        lines.append(f'- Additional: {custom[:_MAX_CUSTOM_CHARS]}')

    if not lines:
        return ''

    header = (
        'USER FORMATTING PREFERENCES '
        '(honor these unless they conflict with the required output format or structure):'
    )
    return header + '\n' + '\n'.join(lines)


def directive_for_user(user) -> str:
    """Convenience wrapper: resolve ``user.profile`` safely and build the directive.

    Returns ``""`` for anonymous users or users without a profile.
    """
    if user is None or not getattr(user, 'is_authenticated', False):
        return ''
    profile = getattr(user, 'profile', None)
    return build_ai_style_directive(profile)
