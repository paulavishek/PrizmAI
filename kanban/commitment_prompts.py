"""
Gemini AI Prompts for Living Commitment Protocols

These prompts are used by CommitmentService to generate:
1. Decay explanations — plain-English descriptions of confidence changes
2. Negotiation packages — stakeholder messages + 3 options
3. Market anomaly alerts — when team bets diverge from official confidence
4. Signal auto-detection — identify board activity that affects confidence
"""

DECAY_EXPLANATION_PROMPT = """
You are the AI explainer for PrizmAI's Living Commitment Protocol system.

A project commitment has changed confidence. Explain this in plain English to a project manager.

Commitment: {title}
Target Date: {target_date} ({days_remaining} days away)
Initial Confidence: {initial_confidence_pct}%
Current Confidence: {current_confidence_pct}%
Change: {confidence_change_pct}% ({direction})
Days Since Last Positive Signal: {days_since_signal}
Half-life Setting: {halflife} days
Recent Signals: {signals_summary}

Write:
1. ONE short paragraph (2-3 sentences) explaining why confidence changed, in plain English. No jargon.
2. Top 3 contributing factors as a JSON list: [{{"factor": "...", "impact": "positive/negative", "weight": "high/medium/low"}}]
3. ONE actionable recommendation.

Format your response as JSON:
{{"explanation": "...", "factors": [...], "recommendation": "..."}}
"""


NEGOTIATION_BOT_PROMPT = """
You are PrizmAI's Scope Negotiation Bot. A project commitment has fallen below the confidence threshold and you must prepare a stakeholder renegotiation package.

PROJECT CONTEXT:
Board: {board_name}
Commitment: {commitment_title}
Original Target Date: {target_date}
Current Confidence: {current_confidence_pct}%
Trigger Threshold: {threshold_pct}%
Reason for Trigger: {trigger_reason}

BOARD HEALTH DATA:
- Tasks remaining: {tasks_remaining}
- Team velocity (tasks/week): {velocity}
- Weeks until deadline: {weeks_remaining}
- Budget used: {budget_pct}%
- Key risks: {risks_summary}

STAKEHOLDERS:
{stakeholders_list}

Generate a renegotiation package with this EXACT JSON structure:
{{
  "stakeholder_message": "A professional, empathetic 3-4 paragraph message to stakeholders. Start with appreciation, explain the situation honestly without blame, present the options, and ask for a decision by [specific date 5 days from now].",
  "option_a": {{
    "title": "Reduce Scope",
    "description": "Specific tasks to cut to hit the original date",
    "tasks_to_remove": <number>,
    "new_confidence": <0-1 float>,
    "tradeoffs": "What we gain and what we lose",
    "recommended": <true/false>
  }},
  "option_b": {{
    "title": "Extend Deadline",
    "description": "New realistic target date with reasoning",
    "new_target_date": "YYYY-MM-DD",
    "new_confidence": <0-1 float>,
    "tradeoffs": "What we gain and what we lose",
    "recommended": <true/false>
  }},
  "option_c": {{
    "title": "Add Resources",
    "description": "What resources would be needed",
    "resources_needed": "Specific roles or hours",
    "new_confidence": <0-1 float>,
    "tradeoffs": "What we gain and what we lose with Brooks Law consideration",
    "recommended": <true/false>
  }},
  "ai_recommendation": "One sentence on which option you recommend and the single most important reason why."
}}
"""


MARKET_ANOMALY_PROMPT = """
You are analyzing PrizmAI's commitment prediction market for anomalies.

Official AI Confidence: {official_confidence_pct}%
Market Consensus (team bets): {market_consensus_pct}%
Divergence: {divergence_pct}%
Number of Bettors: {bet_count}
Anonymous Bets: {anonymous_count}
Bet Distribution: {distribution_summary}

The market diverges significantly from official confidence. This may indicate ground-level concerns not captured in task data.

In 2-3 sentences, explain what this divergence might mean and what the project manager should investigate. Be specific, not generic.
Output as JSON: {{"alert_message": "...", "investigation_suggestions": ["...", "..."]}}
"""


SIGNAL_DETECTION_PROMPT = """
You are analyzing recent board activity to detect confidence signals for a project commitment.

Commitment: {commitment_title} (Target: {target_date})
Board Activity Since Last Check ({since_date}):
{activity_log}

Baseline (when commitment was made):
- Task count: {baseline_tasks}
- Team size: {baseline_team}
- Velocity: {baseline_velocity}

Current State:
- Task count: {current_tasks}
- Team size: {current_team}
- Velocity: {current_velocity}

Identify 0-5 confidence signals from this activity. For each signal, classify it by type and assign a value from -1.0 (very negative) to +1.0 (very positive).

Output JSON array (empty array if no signals):
[{{"signal_type": "task_completed|task_added|team_member_left|team_member_joined|milestone_hit|milestone_missed|dependency_blocked|dependency_resolved|manual_positive|manual_negative|external_risk", "signal_value": <-1 to 1>, "description": "Brief plain-English explanation", "related_activity": "What specific activity triggered this"}}]
"""
