"""
PrizmAI RBAC — reusable decorators.

With the single-tier personal sandbox architecture, the old Tier-1
read-only guards (demo_write_guard, demo_ai_guard) are no longer needed.
Users own their sandbox copies and can freely edit them.

Kept as no-op passthroughs so any straggling import doesn't crash.
"""
import functools


def demo_write_guard(view_func):
    """No-op — kept for import compatibility during migration."""
    return view_func


def demo_ai_guard(view_func):
    """No-op — kept for import compatibility during migration."""
    return view_func
