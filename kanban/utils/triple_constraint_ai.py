"""
Triple Constraint AI Analysis
Analyses the relationship between Scope, Cost, and Time for a board using Gemini AI.
Follows the same pattern as kanban/utils/scope_analysis.py.
"""
import json
import logging

import google.generativeai as genai
from django.conf import settings

logger = logging.getLogger(__name__)


def analyze_triple_constraints(board, scope_data, budget_data, time_data):
    """
    Ask Gemini to analyse how Scope, Cost, and Time interact for the given board
    and suggest the optimal configuration.

    Args:
        board       : Board model instance (used for name/context only)
        scope_data  : dict from board.get_current_scope_status() or None
        budget_data : dict with keys allocated_budget, spent_amount, utilization_pct,
                      currency, remaining_budget (or None if no budget set)
        time_data   : dict with keys target_date, predicted_date, days_ahead_behind,
                      velocity_tasks_per_week, risk_level (or None if no prediction)

    Returns:
        dict with AI analysis or a structured error dict on failure.
    """
    try:
        genai.configure(api_key=settings.GEMINI_API_KEY)
        model = genai.GenerativeModel('gemini-2.5-flash')

        # --- build context strings ---
        project_name = board.name

        if scope_data:
            scope_section = (
                f"- Baseline tasks: {scope_data.get('baseline_tasks', 'N/A')}\n"
                f"- Current tasks: {scope_data.get('current_tasks', 'N/A')}\n"
                f"- Scope change: {scope_data.get('scope_change_percentage', 0):+.1f}%\n"
                f"- Tasks added since baseline: {scope_data.get('tasks_added', 0)}\n"
                f"- Baseline complexity: {scope_data.get('baseline_complexity', 'N/A')} pts\n"
                f"- Current complexity: {scope_data.get('current_complexity', 'N/A')} pts"
            )
        else:
            scope_section = "- No baseline set yet; scope tracking not active."

        if budget_data:
            cost_section = (
                f"- Allocated budget: {budget_data.get('currency', '')} {budget_data.get('allocated_budget', 'N/A')}\n"
                f"- Spent so far: {budget_data.get('currency', '')} {budget_data.get('spent_amount', 0)}\n"
                f"- Budget utilisation: {budget_data.get('utilization_pct', 0):.1f}%\n"
                f"- Remaining budget: {budget_data.get('currency', '')} {budget_data.get('remaining_budget', 'N/A')}\n"
                f"- Budget status: {budget_data.get('status', 'unknown')}"
            )
        else:
            cost_section = "- No budget configured for this project yet."

        if time_data:
            time_section = (
                f"- Target completion date: {time_data.get('target_date', 'Not set')}\n"
                f"- AI-predicted completion date: {time_data.get('predicted_date', 'Not calculated')}\n"
                f"- Days ahead/behind target: {time_data.get('days_ahead_behind', 0):+d} days\n"
                f"- Current velocity: {time_data.get('velocity_tasks_per_week', 'N/A')} tasks/week\n"
                f"- Risk level: {time_data.get('risk_level', 'unknown')}\n"
                f"- Delay probability: {time_data.get('delay_probability', 'N/A')}%"
            )
        else:
            time_section = "- No burndown prediction available yet for this project."

        prompt = f"""You are a senior project management consultant specialising in the Triple Constraint framework 
(Scope, Cost, Time). Analyse the current state of this project and provide actionable guidance.

**Project:** {project_name}

**Scope Status**
{scope_section}

**Cost / Budget Status**
{cost_section}

**Time / Schedule Status**
{time_section}

Analyse how changes to one constraint affect the others and provide specific recommendations.

Respond with ONLY valid JSON in the following exact schema (no markdown fences, no extra text):
{{
  "overall_health_score": <integer 1-10, where 10 is perfectly healthy>,
  "overall_health_label": "<one of: Healthy | At Risk | Critical>",
  "most_stressed_constraint": "<one of: Scope | Cost | Time | None>",
  "risk_summary": "<2-3 sentence plain-English summary of the biggest risks>",
  "constraint_insights": {{
    "scope": "<1-2 sentence insight about scope health>",
    "cost": "<1-2 sentence insight about cost/budget health>",
    "time": "<1-2 sentence insight about schedule health>"
  }},
  "trade_off_scenarios": [
    {{
      "title": "Reduce Scope",
      "description": "<what tasks/features to cut and the expected benefit>",
      "estimated_cost_saving_pct": <number>,
      "estimated_time_saving_days": <number>,
      "feasibility": "<Low | Medium | High>"
    }},
    {{
      "title": "Increase Budget",
      "description": "<how additional budget could help and where to invest it>",
      "recommended_budget_increase_pct": <number>,
      "estimated_time_saving_days": <number>,
      "feasibility": "<Low | Medium | High>"
    }},
    {{
      "title": "Extend Timeline",
      "description": "<how much extra time is needed and what it would enable>",
      "recommended_extension_weeks": <number>,
      "estimated_scope_tasks_deliverable": <number>,
      "feasibility": "<Low | Medium | High>"
    }}
  ],
  "recommended_action": "<The single most important action the project manager should take right now, in 1-2 sentences>",
  "optimal_configuration": {{
    "scope_recommendation": "<brief>",
    "cost_recommendation": "<brief>",
    "time_recommendation": "<brief>"
  }}
}}"""

        generation_config = {
            'temperature': 0.4,
            'top_p': 0.8,
            'top_k': 40,
            'max_output_tokens': 8192,  # Large schema needs ample room
        }

        response = model.generate_content(prompt, generation_config=generation_config)
        raw = response.text.strip()

        # Strip markdown fences if present
        if raw.startswith('```'):
            raw = raw.split('```')[1]
            if raw.startswith('json'):
                raw = raw[4:]
            raw = raw.strip()
        # Also strip any trailing fence that Gemini appended after the JSON
        if raw.endswith('```'):
            raw = raw[:-3].strip()

        try:
            result = json.loads(raw)
        except json.JSONDecodeError:
            # Gemini occasionally truncates; try to recover the outermost object
            last_brace = raw.rfind('}')
            if last_brace != -1:
                raw = raw[:last_brace + 1]
                # Attempt to close any open arrays so the outer object can close cleanly
                open_brackets = raw.count('[') - raw.count(']')
                open_braces   = raw.count('{') - raw.count('}')
                raw += ']' * max(open_brackets, 0) + '}' * max(open_braces, 0)
            result = json.loads(raw)   # re-raises JSONDecodeError if still broken

        return result

    except json.JSONDecodeError as e:
        logger.warning('Triple constraint AI: JSON parse error: %s', e)
        return _error_response('AI returned an unparseable response. Please try again.')
    except Exception as e:
        logger.error('Triple constraint AI analysis failed: %s', e)
        return _error_response(str(e))


def _error_response(msg):
    return {
        'error': msg,
        'overall_health_score': None,
        'overall_health_label': 'Unknown',
        'most_stressed_constraint': 'Unknown',
        'risk_summary': 'Analysis unavailable.',
        'constraint_insights': {'scope': '', 'cost': '', 'time': ''},
        'trade_off_scenarios': [],
        'recommended_action': 'Please retry the AI analysis.',
        'optimal_configuration': {
            'scope_recommendation': '',
            'cost_recommendation': '',
            'time_recommendation': '',
        },
    }
