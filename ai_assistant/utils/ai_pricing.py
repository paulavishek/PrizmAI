"""
ai_pricing.py — Gemini token pricing for internal cost attribution.

Standalone helper (no imports from ai_router / Django models) so reporting code in
the api/ app can estimate per-feature cost without pulling in the whole router or
risking a circular import.

Figures are USD per 1,000,000 tokens, split input/output because output tokens are
priced several times higher than input on every tier — a combined token count would
badly misestimate cost. Confirm these against the live GCP price list at implementation
time (published pricing changes over time).
"""

# USD per 1M tokens: {'input': ..., 'output': ...}
GEMINI_PRICING = {
    'gemini-2.5-flash-lite': {'input': 0.10, 'output': 0.40},
    'gemini-3.1-flash-lite': {'input': 0.25, 'output': 1.50},
    'gemini-2.5-flash':      {'input': 0.30, 'output': 2.50},
}


def estimate_cost_usd(model, input_tokens, output_tokens):
    """
    Estimate the USD cost of a single Gemini call.

    Args:
        model (str): Model name as recorded on the request (e.g. 'gemini-3.1-flash-lite').
        input_tokens (int|None): Prompt tokens.
        output_tokens (int|None): Generated (candidate) tokens.

    Returns:
        float cost in USD, or None if the model isn't in the pricing table (caller
        should treat None as "unknown / unpriced" rather than zero).
    """
    p = GEMINI_PRICING.get(model)
    if not p:
        return None
    return ((input_tokens or 0) * p['input'] + (output_tokens or 0) * p['output']) / 1_000_000
