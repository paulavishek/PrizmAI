"""
Guard test: the automation engine must never make a synchronous LLM call or
queue async work directly from an action handler.

PrizmAI deliberately decouples cheap, deterministic automation actions (field
writes, comments, ORM status updates, record creation) from expensive AI work,
which runs later in separate scheduled sweeps. This test locks that property in:
it reads the action-handler source and fails if it references the AI layer or
async dispatch. If a future action legitimately needs AI, route it through a
deferred flag/record (like request_ai_analysis / generate_status_report do) — do
NOT call the LLM inline — or update the allowlist here deliberately with review.
"""

import re

from django.test import SimpleTestCase

# Tokens that indicate a synchronous AI call or direct async dispatch.
FORBIDDEN = [
    'gemini',
    'generativeai',
    'AIRouter',
    'ai_router',
    '.complete(',
    'ai_utils',
    'ai_briefing',
    'embedding',
    'apply_async',
    '.delay(',
]


class AutomationActionsAreLlmFreeTest(SimpleTestCase):
    def test_no_synchronous_ai_or_async_dispatch_in_action_handlers(self):
        import kanban.automation_actions as mod

        with open(mod.__file__, encoding='utf-8') as fh:
            source = fh.read()

        # Strip the module docstring so prose mentioning these terms can't trip
        # the guard — we only care about code references.
        code = re.sub(r'^\s*""".*?"""', '', source, count=1, flags=re.DOTALL)

        hits = [tok for tok in FORBIDDEN if tok in code]
        self.assertEqual(
            hits, [],
            f'automation_actions.py must stay LLM-free / non-blocking, but found: '
            f'{hits}. Route AI through a deferred flag/record, not an inline call.'
        )
