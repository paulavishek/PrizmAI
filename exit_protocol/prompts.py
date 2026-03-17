"""
Gemini prompt templates for Exit Protocol.
All prompts handle None/empty values gracefully with safe fallback text.
"""

HOSPICE_ASSESSMENT_PROMPT = """
You are PrizmAI's compassionate project advisor. A project is showing signs of irreversible challenge.
Your role: help the team process this with clarity, dignity, and a forward-looking perspective.

Project Name: {project_name}
Duration: {start_date} to today ({days_active} days active)
Tasks: {completed_tasks} of {total_tasks} completed ({completion_pct}%)
Budget: {budget_spent_pct}
Sprint Velocity Trend: {velocity_trend}
Deadlines Missed (last 30 days): {deadlines_missed}
Days Since Last Activity: {days_inactive}
Pre-Mortem Risks That Materialized: {materialized_risks}
Stress Test Resilience Score: {stress_score}

Write a compassionate, honest, and forward-looking project assessment (300-400 words) that:
1. Acknowledges what has genuinely been achieved (always find something real)
2. Honestly describes the current situation without blame
3. Explains why a wind-down may be the most mature choice
4. Frames wind-down as an act of organizational wisdom, not failure
5. Ends with an encouraging note about what comes next

STRICT TONE RULES:
- NEVER use the words "failed" or "failure"
- Use "encountered insurmountable challenges" or "reached its natural conclusion"
- Tone: warm, professional, forward-looking — like a wise mentor, not a coroner
- Do not invent numbers not present in the data above
"""

ORGAN_REUSABILITY_PROMPT = """
You are analyzing a project component to determine if it could be valuable to future projects.

Component Type: {organ_type}
Component Name: {name}
Component Description: {description}
Component Details: {payload_summary}
Source Project Context: {source_project_context}

Score REUSABILITY from 0 to 100 based on:
- How general-purpose vs. project-specific it is (general = higher score)
- How much effort it would save if reused
- How well-structured and transferable the component is
- Whether it represents a battle-tested process (survived real use)

Return ONLY valid JSON with no preamble, no markdown fences:
{{
  "reusability_score": <integer 0-100>,
  "rationale": "<2-3 sentences>",
  "best_suited_for": "<description of ideal target project types>",
  "cautions": "<limitations or things to watch when reusing, or empty string if none>"
}}
"""

ORGAN_COMPATIBILITY_PROMPT = """
You are matching a reusable component from one project to a potential target project.

COMPONENT:
Type: {organ_type}
Name: {name}
Description: {description}
Originally designed for: {source_context}

TARGET PROJECT:
Name: {target_name}
Description: {target_description}
Current phase: {target_phase}
Team size: {target_team_size}
Domain/Industry: {target_domain}

Score COMPATIBILITY from 0 to 100. Consider:
- Domain similarity between source and target
- Project phase suitability
- Team size appropriateness
- Whether this component fills a real gap in the target project

Return ONLY valid JSON with no preamble, no markdown fences:
{{
  "compatibility_score": <integer 0-100>,
  "match_rationale": "<2 sentences>",
  "adaptation_needed": "<what would need to change for this to work in the target, or empty string>"
}}
"""

CAUSE_OF_DEATH_PROMPT = """
You are analyzing a completed project to classify its primary cause of termination.

Project Data:
- Final velocity vs baseline: {velocity_ratio}
- Budget consumed: {budget_pct}% of {total_budget}
- Tasks completed: {completion_pct}%
- Timeline: {planned_duration} planned, {actual_duration} actual
- Scope changes: {scope_change_count} changes ({scope_change_pct}% expansion)
- Team changes: {team_turnover_count} members left during project
- Strategic context: {strategic_notes}
- Knowledge Graph event summary: {kg_events_summary}

Choose EXACTLY ONE primary cause from this list:
- natural_completion  (finished successfully — tasks done, goals met)
- budget_exhaustion   (ran out of money before completion)
- deadline_collapse   (timeline became untenable)
- scope_creep_spiral  (scope expanded beyond manageability)
- team_dissolution    (team lost too many members to continue)
- strategic_pivot     (cancelled due to company/strategy change — not project failure)
- zombie_death        (slowly abandoned without formal closure)
- merger              (absorbed into another project)

Return ONLY valid JSON with no preamble, no markdown fences:
{{
  "cause": "<one option from the list above>",
  "primary_rationale": "<3-4 sentences>",
  "contributing_factors": ["<factor 1>", "<factor 2>", "<factor 3>"]
}}
"""

LESSONS_PROMPT = """
You are extracting actionable lessons from a completed project's history for future project teams.

Project: {project_name}
Cause of Death: {cause_of_death}
Key Events from Knowledge Graph: {knowledge_graph_summary}
Pre-Mortem Scenarios That Materialized: {premortem_hits}
Scope Changes: {scope_changes}
Positive Signals (what worked): {positive_signals}

Generate three lists of lessons.
Be SPECIFIC and ACTIONABLE — not generic ("communicate better").
Each lesson must reference what actually happened in this project.

Return ONLY valid JSON with no preamble, no markdown fences:
{{
  "lessons_to_repeat": [
    {{"lesson": "<specific actionable lesson>", "evidence": "<what happened here that supports this>"}},
    ... (3-5 items)
  ],
  "lessons_to_avoid": [
    {{"lesson": "<specific mistake or anti-pattern to avoid>", "evidence": "<what happened here>"}},
    ... (3-5 items)
  ],
  "open_questions": [
    {{"question": "<something we still don't know or would investigate differently>"}},
    ... (2-3 items)
  ]
}}
"""

TAGS_PROMPT = """
Generate 5-10 short, searchable tags for this project autopsy.

Project: {project_name}
Description: {project_description}
Cause of Death: {cause_of_death}
Key Lessons: {key_lessons}

Return ONLY a JSON array of lowercase tag strings with no preamble:
["tag1", "tag2", "tag3"]
"""

TRANSITION_MEMO_PROMPT = """
Write a short, positive transition memo for a team member moving on from a project that is winding down.

Team Member Name: {member_name}
Tasks Worked On: {tasks_summary}
Role on Project: {role_name}
Project Name: {project_name}

Write a 100-150 word memo covering:
1. What they contributed (be specific to the tasks listed)
2. Skills they demonstrated
3. Recommendations for their next assignment

Tone: encouraging, specific, forward-looking. This is about celebrating their contributions, not mourning the project.
"""
