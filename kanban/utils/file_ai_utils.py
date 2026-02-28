"""
AI-powered file analysis utility for PrizmAI.

Supports: PDF, DOCX, TXT (plain text).
Reuses the text extraction helper from wiki.ai_utils and routes through
the shared GeminiClient for consistency with the rest of the AI stack.
"""

import json
import logging
import re

logger = logging.getLogger(__name__)

# File types that can be parsed and sent to AI
AI_SUPPORTED_TYPES = {'pdf', 'docx', 'txt', 'doc'}

# Max characters sent to Gemini — keeps us comfortably within the token budget
MAX_TEXT_CHARS = 12_000

VALID_PRIORITIES = {'low', 'medium', 'high'}


def analyze_attachment(file_path: str, file_type: str, filename: str = 'document') -> dict:
    """
    Analyze a file attachment using Gemini AI.

    Extracts text from the file, sends it to Gemini with a structured prompt,
    and returns a summary plus a list of suggested tasks.

    Args:
        file_path: Absolute path to the file on disk.
        file_type: File extension without the dot (e.g. 'pdf', 'docx', 'txt').
        filename:  Original filename for display in the prompt.

    Returns:
        dict with keys:
          - summary (str): 2-4 sentence summary of the document.
          - tasks (list): [{title, description, priority}] extracted from document.
          - error (str|None): Human-readable error message, or None on success.
    """
    ft = file_type.lower().lstrip('.')

    # Guard: only supported types
    if ft not in AI_SUPPORTED_TYPES:
        return {
            'summary': '',
            'tasks': [],
            'error': (
                f'File type "{file_type}" is not supported for AI analysis. '
                'Supported types: PDF, DOCX, TXT.'
            ),
        }

    # ── Text extraction ──────────────────────────────────────────────────────
    try:
        from wiki.ai_utils import extract_text_from_file
        # wiki utility maps 'doc' -> None; we try 'docx' as fallback
        text = extract_text_from_file(file_path, ft)
        if text is None and ft == 'doc':
            text = extract_text_from_file(file_path, 'docx')
    except Exception as exc:
        logger.error('Error importing extract_text_from_file: %s', exc)
        text = None

    if not text or not text.strip():
        return {
            'summary': '',
            'tasks': [],
            'error': (
                'Could not extract text from this file. '
                'The file may be empty, password-protected, or in an unsupported sub-format.'
            ),
        }

    # Truncate to token-budget-safe length
    text_excerpt = text[:MAX_TEXT_CHARS]
    if len(text) > MAX_TEXT_CHARS:
        text_excerpt += (
            f'\n\n[... Content truncated — showing first {MAX_TEXT_CHARS:,} '
            f'of {len(text):,} characters ...]'
        )

    # ── Build Gemini prompt ───────────────────────────────────────────────────
    prompt = f"""You are a project management assistant analyzing a document.
Document filename: {filename}

DOCUMENT CONTENT:
---
{text_excerpt}
---

Provide your response as a single valid JSON object — no prose before or after it.

The JSON must have exactly this structure:
{{
  "summary": "<2-4 sentence summary of the document's key content and purpose>",
  "tasks": [
    {{
      "title": "<short, actionable task title>",
      "description": "<optional context or detail>",
      "priority": "<low | medium | high>"
    }}
  ]
}}

Rules:
- Include only genuinely actionable tasks or follow-up actions implied by the document.
- If no actionable tasks are present, return an empty "tasks" array.
- Limit to a maximum of 10 tasks.
- Ensure JSON is valid and complete."""

    # ── Call Gemini ───────────────────────────────────────────────────────────
    try:
        from ai_assistant.utils.ai_clients import GeminiClient
        client = GeminiClient()
        result = client.get_response(
            prompt,
            task_complexity='complex',
            temperature=0.3,
            cache_operation='file_analysis',
        )

        raw = result.get('content', '')
        if result.get('error') and not raw:
            return {
                'summary': '',
                'tasks': [],
                'error': f'AI analysis failed: {result["error"]}',
            }

        # Parse structured JSON from AI response
        parsed = _extract_json_object(raw)
        if not parsed:
            # Fallback: return raw text as summary (better than nothing)
            return {
                'summary': raw.strip()[:800],
                'tasks': [],
                'error': None,
            }

        summary = str(parsed.get('summary', '')).strip()
        raw_tasks = parsed.get('tasks', [])

        # Validate and sanitise task list
        valid_tasks = []
        for t in raw_tasks if isinstance(raw_tasks, list) else []:
            if isinstance(t, dict) and t.get('title'):
                priority = str(t.get('priority', 'medium')).lower()
                if priority not in VALID_PRIORITIES:
                    priority = 'medium'
                valid_tasks.append({
                    'title': str(t['title'])[:200],
                    'description': str(t.get('description', ''))[:500],
                    'priority': priority,
                })

        return {'summary': summary, 'tasks': valid_tasks, 'error': None}

    except Exception as exc:
        logger.error('Error during AI file analysis: %s', exc)
        return {
            'summary': '',
            'tasks': [],
            'error': f'Analysis failed: {str(exc)}',
        }


# ── Internal helpers ──────────────────────────────────────────────────────────

def _extract_json_object(text: str) -> dict | None:
    """Extract the first JSON object from an AI response string."""
    if not text:
        return None
    # Strip markdown code fences
    text = re.sub(r'```(?:json)?', '', text).strip()
    match = re.search(r'(\{.*\})', text, re.DOTALL)
    if not match:
        return None
    try:
        return json.loads(match.group(1))
    except (json.JSONDecodeError, ValueError):
        return None
