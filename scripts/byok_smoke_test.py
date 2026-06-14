"""
byok_smoke_test.py — Live smoke test for the BYOK AI router.

Makes REAL calls to AI providers using the keys configured in your environment.
Unlike the unit tests (ai_assistant/tests/test_byok.py), this hits the network and
costs tokens, so it is NOT part of the automated test suite.

What it does
------------
1. Platform Gemini check: calls AIRouter.complete(user=None), which resolves to the
   platform GEMINI_API_KEY from .env, and prints the normalised response. This proves
   the router → google.generativeai wiring works end-to-end.
2. Optional per-provider BYOK key validation: pass real keys as env vars to validate
   that AIRouter.validate_api_key() accepts a good key for OpenAI / Anthropic / Gemini
   without storing anything.

Usage
-----
    # Platform Gemini round-trip only (uses GEMINI_API_KEY from .env):
    python scripts/byok_smoke_test.py

    # Also validate BYOK keys (any subset):
    SMOKE_OPENAI_KEY=sk-...  SMOKE_ANTHROPIC_KEY=sk-ant-...  SMOKE_GEMINI_KEY=AIza... \
        python scripts/byok_smoke_test.py
"""

import os
import sys

import django

# --- Django bootstrap (use the REAL settings so we read the real .env keys) ---
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'kanban_board.settings')
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
django.setup()

from ai_assistant.utils.ai_router import AIRouter, AIProviderError  # noqa: E402


def _check_mark(ok):
    return 'PASS' if ok else 'FAIL'


def run_platform_gemini(router):
    print('\n=== 1. Platform Gemini round-trip (user=None) ===')
    try:
        result = router.complete(prompt='Reply with exactly: OK', user=None)
        print(f'  text        : {result.get("text", "")!r}')
        print(f'  provider    : {result.get("provider")}')
        print(f'  model       : {result.get("model")}')
        print(f'  used_byok   : {result.get("used_byok")}')
        print(f'  tokens_used : {result.get("tokens_used")}')
        ok = bool(result.get('text')) and result.get('provider') == 'gemini'
        print(f'  -> {_check_mark(ok)}')
        return ok
    except AIProviderError as exc:
        print(f'  -> FAIL (provider={exc.provider}): {exc}')
        return False
    except Exception as exc:  # noqa: BLE001
        print(f'  -> FAIL (unexpected): {exc!r}')
        return False


def validate_byok_keys(router):
    print('\n=== 2. BYOK key validation (optional) ===')
    probes = [
        ('gemini', os.getenv('SMOKE_GEMINI_KEY')),
        ('openai', os.getenv('SMOKE_OPENAI_KEY')),
        ('anthropic', os.getenv('SMOKE_ANTHROPIC_KEY')),
    ]
    any_run = False
    for provider, key in probes:
        if not key:
            print(f'  {provider:<10}: skipped (set SMOKE_{provider.upper()}_KEY to test)')
            continue
        any_run = True
        ok = router.validate_api_key(provider, key)
        print(f'  {provider:<10}: {_check_mark(ok)}')
    if not any_run:
        print('  (no BYOK keys provided — set SMOKE_*_KEY env vars to validate live keys)')


def main():
    router = AIRouter()
    gemini_ok = run_platform_gemini(router)
    validate_byok_keys(router)
    print('\nDone.')
    sys.exit(0 if gemini_ok else 1)


if __name__ == '__main__':
    main()
