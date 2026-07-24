"""
AI-powered Skill Analysis and Gap Detection Module

This module provides intelligent skill matching and gap analysis using:
- Skill extraction from task descriptions
- Team skill profile aggregation
- Gap identification and quantification
- Actionable recommendations (hire/train/redistribute)
"""
import os
import logging
from typing import Dict, List, Optional, Tuple
from datetime import datetime, timedelta
import json
import re

import google.generativeai as genai  # genai retained: legacy direct-call path not yet migrated to AIRouter
from django.conf import settings
from django.db.models import Q, Count, Avg, Sum
from django.contrib.auth import get_user_model
from django.utils import timezone
from django.contrib.auth.models import User

logger = logging.getLogger(__name__)

# Configure Gemini API
try:
    GEMINI_API_KEY = getattr(settings, 'GEMINI_API_KEY', None)
    if not GEMINI_API_KEY:
        GEMINI_API_KEY = os.environ.get('GEMINI_API_KEY', '')
    
    if GEMINI_API_KEY:
        genai.configure(api_key=GEMINI_API_KEY)
    else:
        logger.warning("GEMINI_API_KEY not set. Skill analysis features won't work.")
except Exception as e:
    logger.error(f"Failed to configure Gemini API for skill analysis: {str(e)}")


def get_model():
    """Get or create Gemini 2.5 Flash model instance for skill analysis"""
    try:
        # Use gemini-2.5-flash for skill analysis (more capable than lite version)
        model = genai.GenerativeModel('gemini-2.5-flash')
        return model
    except Exception as e:
        logger.error(f"Failed to initialize Gemini model: {str(e)}")
        return None


def _get_ai_cache():
    """Get the AI cache manager."""
    try:
        from kanban_board.ai_cache import ai_cache_manager
        return ai_cache_manager
    except ImportError:
        return None


def extract_skills_from_task(task_title: str, task_description: str = "", 
                             use_cache: bool = True) -> List[Dict[str, str]]:
    """
    Extract required skills from task title and description using AI (with caching)
    
    Args:
        task_title: Title of the task
        task_description: Optional detailed description
        use_cache: Whether to use caching (default True)
        
    Returns:
        List of skills with proficiency levels:
        [{'name': 'Python', 'level': 'Intermediate'}, ...]
    """
    try:
        prompt = f"""Analyze this task and extract the key technical skills required to complete it.

Task Title: {task_title}
Task Description: {task_description or 'Not provided'}

Rules:
1. Return at most 6 skills — only the most essential ones for this specific task.
2. Use SHORT, CANONICAL skill names only. Do NOT add parenthetical examples, version numbers, tool lists, or any qualifiers after the name.
   CORRECT: "Backend Framework", "Containerization", "CI/CD", "Python", "SQL"
   WRONG:   "Backend Framework (e.g., Node.js/Express, Python/Django)", "Containerization (e.g., Docker, Kubernetes)"
3. For each skill, set the proficiency level needed: Beginner, Intermediate, Advanced, or Expert.
4. Focus on hard skills (languages, tools, frameworks). Include at most 1 soft skill only if it is directly critical.
5. Return ONLY a valid JSON array, nothing else.

Output format:
[
  {{"name": "Python", "level": "Intermediate"}},
  {{"name": "Django", "level": "Advanced"}},
  {{"name": "SQL", "level": "Beginner"}}
]

JSON array:"""

        # Try cache first
        ai_cache = _get_ai_cache()
        if use_cache and ai_cache:
            cached = ai_cache.get(prompt, 'skill_analysis')
            if cached:
                logger.debug("Skill extraction cache HIT")
                return cached
        
        from ai_assistant.utils.ai_router import AIRouter
        router = AIRouter()

        max_attempts = 2
        for attempt in range(max_attempts):
            try:
                result = router.complete(
                    prompt=prompt,
                    user=None,
                    complexity='simple',
                )
                response_text = result.get('text', '').strip()
                
                # Try direct JSON parse first (response_mime_type should guarantee JSON)
                try:
                    skills = json.loads(response_text)
                except json.JSONDecodeError:
                    # Fallback: extract JSON array from response text
                    json_match = re.search(r'\[[\s\S]*\]', response_text)
                    if json_match:
                        skills = json.loads(json_match.group(0))
                    else:
                        if attempt < max_attempts - 1:
                            logger.warning(f"No valid JSON in skill extraction response (attempt {attempt + 1}), retrying...")
                            continue
                        logger.warning(f"No valid JSON found in skill extraction response after {max_attempts} attempts")
                        return []
                
                # Handle if response is a dict wrapping a list
                if isinstance(skills, dict):
                    skills = skills.get('skills', skills.get('data', []))
                
                if not isinstance(skills, list):
                    if attempt < max_attempts - 1:
                        continue
                    return []
                
                # Validate structure
                valid_skills = []
                valid_levels = ['Beginner', 'Intermediate', 'Advanced', 'Expert']
                
                for skill in skills:
                    if isinstance(skill, dict) and 'name' in skill and 'level' in skill:
                        # Normalize level capitalization
                        level = skill['level'].capitalize()
                        if level in valid_levels:
                            valid_skills.append({
                                'name': skill['name'].strip(),
                                'level': level
                            })
                
                # Cache the result
                if use_cache and ai_cache and valid_skills:
                    ai_cache.set(prompt, valid_skills, 'skill_analysis')
                    logger.debug("Skill extraction result cached")
                
                logger.info(f"Extracted {len(valid_skills)} skills from task: {task_title}")
                return valid_skills
                
            except json.JSONDecodeError:
                if attempt < max_attempts - 1:
                    logger.warning(f"JSON parse error in skill extraction (attempt {attempt + 1}), retrying...")
                    continue
                logger.error(f"Failed to parse skill extraction JSON after {max_attempts} attempts")
                return []
        
        return []
        
    except Exception as e:
        logger.error(f"Error extracting skills from task: {str(e)}")
        return []


def build_team_skill_profile(board) -> Dict:
    """
    Build comprehensive skill inventory for a team/board
    
    Args:
        board: Board instance
        
    Returns:
        Dictionary with skill inventory and capacity data
    """
    try:
        from kanban.models import Board
        from accounts.models import UserProfile
        
        # Get all team members
        User = get_user_model()
        members = User.objects.filter(board_memberships__board=board).select_related('profile')
        
        # Aggregate skills across team
        skill_inventory = {}
        total_capacity = 0
        utilized_capacity = 0
        
        for member in members:
            try:
                profile = member.profile
                
                # Add capacity
                total_capacity += profile.weekly_capacity_hours
                utilized_capacity += profile.current_workload_hours
                
                # Aggregate skills
                for skill in profile.skills:
                    skill_name = skill.get('name', '').strip()
                    skill_level = skill.get('level', 'Intermediate').capitalize()
                    
                    # Normalize skill name to title case for consistent aggregation
                    # (e.g., "python" and "Python" should merge into "Python")
                    if skill_name:
                        skill_name = skill_name.title() if skill_name.islower() else skill_name
                        if skill_name not in skill_inventory:
                            skill_inventory[skill_name] = {
                                'expert': 0,
                                'advanced': 0,
                                'intermediate': 0,
                                'beginner': 0,
                                'members': []
                            }
                        
                        # Increment count for this level
                        level_key = skill_level.lower()
                        if level_key in skill_inventory[skill_name]:
                            skill_inventory[skill_name][level_key] += 1
                        
                        # Track which members have this skill
                        skill_inventory[skill_name]['members'].append({
                            'user_id': member.id,
                            'username': member.username,
                            'level': skill_level
                        })
                        
            except Exception as e:
                logger.warning(f"Error processing skills for user {member.username}: {str(e)}")
                continue
        
        return {
            'skill_inventory': skill_inventory,
            'total_capacity_hours': total_capacity,
            'utilized_capacity_hours': utilized_capacity,
            'utilization_percentage': (utilized_capacity / total_capacity * 100) if total_capacity > 0 else 0,
            'team_size': members.count()
        }
        
    except Exception as e:
        logger.error(f"Error building team skill profile: {str(e)}")
        return {
            'skill_inventory': {},
            'total_capacity_hours': 0,
            'utilized_capacity_hours': 0,
            'utilization_percentage': 0,
            'team_size': 0
        }


def _canonicalize_skill_name(name: str) -> str:
    """Strip parenthetical examples and qualifiers from an AI-extracted skill name.

    AI models frequently emit verbose names such as:
        "Backend Framework (e.g., Node.js/Express, Python/Django/Flask)"
        "Containerization (e.g., Docker, Kubernetes)"
    These cause every task to produce unique skill name strings that never
    deduplicate even after lowercasing.

    This function strips everything inside parentheses so that all of those
    variations collapse to the same base name:
        "Backend Framework (e.g., Node.js)" -> "Backend Framework"
        "Containerization (e.g., Docker, Kubernetes)" -> "Containerization"
    """
    # Remove everything in parentheses, including the parentheses themselves
    cleaned = re.sub(r'\s*\([^)]*\)', '', name)
    # Strip any trailing punctuation / whitespace left behind
    return cleaned.strip(' ,;:')


# Curated discipline alias map: normalized skill name -> canonical bucket key.
#
# WHY: The AI extracts *discipline* names from task titles ("Backend Development",
# "Frontend Development", "Database Design") while team member profiles store
# *specific technologies* ("Python", "React", "PostgreSQL"). Exact-name matching
# can never bridge the two, so a fully capable team was reported as having ZERO
# coverage for almost everything. Mapping BOTH the generic and the specific names
# into the same canonical bucket lets coverage be detected correctly.
#
# Keys MUST already be canonicalized + lowercased (i.e. the output of
# _canonicalize_skill_name(name).lower()) so the lookup is exact.
#
# AUTH / SECURITY buckets (below) DELIBERATELY DO NOT collapse into backend/
# frontend/etc — the demo team has no dedicated auth/security specialist, so
# these must remain genuine, visible gaps. They ARE bucketed among themselves,
# however, so trivial variants don't show up as separate duplicate gaps
# (e.g. "OAuth" and "OAuth 2.0", "Authentication" and "Auth", "Web Security"
# and "Application Security"). Cryptography stays on its own — it is a distinct
# competency from general web security in the demo narrative.
_SKILL_ALIASES = {
    # backend
    'backend development': 'backend',
    'backend framework': 'backend',
    'backend api development': 'backend',
    'python': 'backend',
    'django': 'backend',
    'flask': 'backend',
    'node.js': 'backend',
    'nodejs': 'backend',
    'asynchronous programming': 'backend',
    # api
    'api integration': 'api',
    'api design': 'api',
    'api development': 'api',
    'api gateway': 'api',
    'rest apis': 'api',
    'rest api': 'api',
    'rest': 'api',
    # frontend
    'frontend development': 'frontend',
    'frontend optimization': 'frontend',
    'react': 'frontend',
    'javascript': 'frontend',
    'typescript': 'frontend',
    'css': 'frontend',
    'css / tailwind': 'frontend',
    'html': 'frontend',
    'ux design': 'frontend',
    # database
    'database design': 'database',
    'database management': 'database',
    'database migration': 'database',
    'sql': 'database',
    'postgresql': 'database',
    'mysql': 'database',
    'data access layer': 'database',
    # devops / ci-cd
    'ci/cd': 'devops',
    'github actions': 'devops',
    'infrastructure as code': 'devops',
    'docker': 'devops',
    'containerization': 'devops',
    'docker / containers': 'devops',
    'google cloud platform': 'devops',
    'cloud computing': 'devops',
    'kubernetes': 'devops',
    'test automation': 'devops',
    # architecture (System Architecture IS Software Architecture — the team's
    # "System Architecture" skill must cover "Software Architecture" tasks)
    'system architecture': 'architecture',
    'software architecture': 'architecture',
    'architecture': 'architecture',
    'solution architecture': 'architecture',
    # auth (kept OUT of backend so it stays a genuine gap; variants collapse)
    'oauth': 'oauth',
    'oauth 2.0': 'oauth',
    'oauth2': 'oauth',
    'oauth 2': 'oauth',
    'openid connect': 'oauth',
    'authentication': 'authentication',
    'auth': 'authentication',
    'authentication protocols': 'authentication',
    'authentication & authorization': 'authentication',
    'authorization': 'authentication',
    'user authentication': 'authentication',
    # security (web/app security variants collapse; cryptography stays separate).
    # NOTE: "security scanning" is intentionally NOT mapped here — it is a real
    # team skill (running vulnerability scanners) and must not silently grant
    # coverage for secure-design work ("Web Security"), which the team lacks.
    'web security': 'security',
    'application security': 'security',
    'security': 'security',
    'security engineering': 'security',
    'appsec': 'security',
}

# Friendly display labels for canonical bucket keys (used as the gap's
# skill_name when multiple aliases collapse into a single bucket).
_CANONICAL_DISPLAY = {
    'backend': 'Backend Development',
    'api': 'API Development',
    'frontend': 'Frontend Development',
    'database': 'Database',
    'devops': 'DevOps / CI-CD',
    'architecture': 'Software Architecture',
    'oauth': 'OAuth',
    'authentication': 'Authentication',
    'security': 'Security',
}


def _normalize_skill_name(name: str) -> str:
    """Normalize a skill name to a case-insensitive deduplication key.

    Applies _canonicalize_skill_name first (strips parenthetical qualifiers),
    then lowercases, then maps known aliases to a canonical discipline bucket
    via _SKILL_ALIASES.  This ensures both verbose AI-extracted names like
        'Backend Framework (e.g., Node.js)'  and
        'Backend Framework (e.g., Django/Flask)'
    collapse to one key, AND that generic task disciplines match the specific
    technologies stored on team profiles:
        'Backend Development' / 'Python' / 'Django'  -> 'backend'
        'CI/CD' / 'CI/CD (GitHub Actions)'           -> 'devops'
    """
    base = _canonicalize_skill_name(name).lower()
    return _SKILL_ALIASES.get(base, base)


def _is_active_column(column) -> bool:
    """True if a task's column represents work actively in flight.

    Active = In Progress / Review / Blocked. Backlog, To Do and Done columns
    are NOT active. Used to calibrate gap severity: a skill required only by
    tasks sitting in the backlog is a *planning* gap, not a "cannot proceed"
    blocker, so it must not be labelled Critical. Uses the shared column
    semantics so column renames don't silently break the classification.
    """
    try:
        from kanban.column_semantics import (
            is_in_progress_column, is_review_column, is_blocked_column,
        )
        return (
            is_in_progress_column(column)
            or is_review_column(column)
            or is_blocked_column(column)
        )
    except Exception:
        return False


def calculate_skill_gaps(board, sprint_period_days: int = 14) -> List[Dict]:
    """
    Calculate skill gaps by comparing required skills (from tasks) 
    vs available skills (from team members)
    
    METHODOLOGY:
    - A gap exists when required skill coverage exceeds available team capacity
    - Zero-coverage skills (no team members have it) are always flagged
    - Severity is calibrated: Critical for zero coverage, graduated otherwise
    - Gap count is realistic (not 1:1 with task count, but capacity-based)
    
    Args:
        board: Board instance
        sprint_period_days: Number of days to look ahead for tasks (default: 2 weeks)
        
    Returns:
        List of skill gap dictionaries with recommendations
    """
    try:
        from kanban.models import Task
        
        # Get all incomplete tasks for the board
        # We analyze ALL active tasks, not just those due soon, because:
        # 1. Tasks due far in the future still need skilled resources to eventually complete them
        # 2. The sprint_period helps prioritize but shouldn't exclude work entirely
        # 3. A PM needs to see all skill gaps, not just immediate ones
        tasks = list(Task.objects.filter(
            column__board=board,
            progress__lt=100
        ).select_related('column'))
        
        logger.info(f"Analyzing {len(tasks)} active tasks for skill gaps on board {board.name}")
        
        # One-time cleanup: clear stored skills that contain parenthetical verbose names
        # (e.g., "Backend Framework (e.g., Node.js/Express)") so they are re-extracted
        # with the updated prompt that produces short canonical names.
        # A skill entry is considered verbose if any name contains a '(' character.
        verbose_tasks_cleared = 0
        for task in tasks:
            if task.required_skills:
                skills_list = task.required_skills
                if isinstance(skills_list, str):
                    try:
                        skills_list = json.loads(skills_list)
                    except (json.JSONDecodeError, TypeError):
                        skills_list = []
                if isinstance(skills_list, list):
                    has_verbose = any(
                        '(' in (s.get('name', '') if isinstance(s, dict) else str(s))
                        for s in skills_list
                    )
                    if has_verbose:
                        task.required_skills = []
                        task.save(update_fields=['required_skills'])
                        verbose_tasks_cleared += 1
        if verbose_tasks_cleared > 0:
            logger.info(
                f"Cleared verbose required_skills from {verbose_tasks_cleared} task(s) — "
                "will re-extract with canonical short names."
            )

        # Auto-populate required_skills for tasks that don't have them
        tasks_needing_skills = [t for t in tasks if not t.required_skills]
        skills_extracted_count = 0
        extraction_failures = 0
        
        # Time budget: limit skill extraction to 60 seconds to prevent request timeouts
        import time as _time
        extraction_start = _time.time()
        EXTRACTION_TIME_BUDGET_SECS = 60
        
        if tasks_needing_skills:
            logger.info(f"Auto-extracting skills for {len(tasks_needing_skills)} tasks without defined skills")
            # Process up to 50 tasks so a single Run Analysis populates all tasks,
            # making gap detection fully deterministic on subsequent runs.
            for task in tasks_needing_skills[:50]:
                # Check time budget before each extraction
                elapsed = _time.time() - extraction_start
                if elapsed > EXTRACTION_TIME_BUDGET_SECS:
                    logger.warning(
                        f"Skill extraction time budget exhausted ({elapsed:.1f}s). "
                        f"Processed {skills_extracted_count + extraction_failures}/{len(tasks_needing_skills)} tasks."
                    )
                    break
                
                # Stop early if too many consecutive failures (API issue)
                if extraction_failures >= 5 and skills_extracted_count == 0:
                    logger.warning(
                        f"Stopping skill extraction after {extraction_failures} consecutive failures - "
                        f"possible API issue. Will use existing task skills for gap analysis."
                    )
                    break
                
                try:
                    extracted_skills = extract_skills_from_task(task.title, task.description or "")
                    if extracted_skills:
                        task.required_skills = extracted_skills
                        task.save(update_fields=['required_skills'])
                        skills_extracted_count += 1
                        extraction_failures = 0  # Reset consecutive failure counter
                    else:
                        extraction_failures += 1
                except Exception as e:
                    extraction_failures += 1
                    logger.warning(f"Failed to extract skills for task {task.id}: {str(e)}")
                    continue
            
            if skills_extracted_count > 0:
                logger.info(f"Auto-extracted skills for {skills_extracted_count} tasks")
        
        # Build team skill profile
        team_profile = build_team_skill_profile(board)
        skill_inventory = team_profile['skill_inventory']
        team_size = team_profile.get('team_size', 1) or 1

        # Build a normalized lookup to match AI-extracted skill names to team profile names.
        # Both sides are routed through _normalize_skill_name so that:
        #   - parenthetical qualifiers are stripped ("CI/CD (GitHub Actions)" -> "ci/cd" -> "devops")
        #   - generic disciplines match specific technologies via the alias map
        #     ("Python"/"Django" -> "backend", "React"/"JavaScript" -> "frontend")
        # Multiple profile skills can collapse to the same canonical key, so we MERGE
        # (sum level counts) and dedupe members by user_id — each member counts once per
        # bucket at their highest level, otherwise coverage is inflated and real gaps hidden.
        _level_rank = {'expert': 4, 'advanced': 3, 'intermediate': 2, 'beginner': 1}
        skill_inventory_norm = {}
        for raw_name, data in skill_inventory.items():
            key = _normalize_skill_name(raw_name)
            entry = skill_inventory_norm.setdefault(key, {
                'expert': 0, 'advanced': 0, 'intermediate': 0, 'beginner': 0,
                'members': [],
            })
            for member in data.get('members', []):
                uid = member.get('user_id')
                m_level = (member.get('level') or 'Intermediate').lower()
                existing = next((m for m in entry['members'] if m.get('user_id') == uid), None)
                if existing is None:
                    entry['members'].append(dict(member))
                elif _level_rank.get(m_level, 0) > _level_rank.get((existing.get('level') or '').lower(), 0):
                    # Keep the member's highest level across collapsed skills
                    existing['level'] = member.get('level')
            # Recompute per-level counts from the deduped member list
            for lvl in ('expert', 'advanced', 'intermediate', 'beginner'):
                entry[lvl] = sum(
                    1 for m in entry['members'] if (m.get('level') or '').lower() == lvl
                )

        # Aggregate required skills from tasks (re-check since some may have been updated)
        required_skills = {}
        
        for task in tasks:
            # Refresh from DB if we extracted skills
            if skills_extracted_count > 0 and task in tasks_needing_skills[:15]:
                task.refresh_from_db(fields=['required_skills'])
            
            if task.required_skills:
                skills_list = task.required_skills
                
                # Handle if stored as JSON string
                if isinstance(skills_list, str):
                    try:
                        skills_list = json.loads(skills_list)
                    except (json.JSONDecodeError, TypeError):
                        logger.warning(f"Invalid required_skills format for task {task.id}")
                        continue
                
                if not isinstance(skills_list, list):
                    continue
                
                for skill in skills_list:
                    # Handle both dict format and string format
                    if isinstance(skill, dict):
                        skill_name = skill.get('name', '').strip()
                        skill_level = skill.get('level', 'Intermediate').capitalize()
                    elif isinstance(skill, str):
                        # Check if it's a stringified dict like "{'name': 'Python', 'level': 'Expert'}"
                        if skill.startswith('{') and 'name' in skill:
                            try:
                                # Try to parse as Python dict (uses single quotes)
                                import ast
                                parsed = ast.literal_eval(skill)
                                if isinstance(parsed, dict):
                                    skill_name = parsed.get('name', '').strip()
                                    skill_level = parsed.get('level', 'Intermediate').capitalize()
                                else:
                                    continue
                            except (ValueError, SyntaxError):
                                skill_name = skill.strip()
                                skill_level = 'Intermediate'
                        else:
                            skill_name = skill.strip()
                            skill_level = 'Intermediate'  # Default level for string-only skills
                    else:
                        continue
                    
                    if skill_name:
                        # Use a normalized (lowercase) key so that name variations like
                        # "Problem-Solving" and "Problem Solving" collapse into one entry
                        skill_key = _normalize_skill_name(skill_name)
                        if skill_key not in required_skills:
                            required_skills[skill_key] = {
                                # Friendly label for canonical buckets (e.g. "backend" ->
                                # "Backend Development"); otherwise the canonicalized
                                # (no-parens) name so the UI shows "Backend Framework"
                                # not "Backend Framework (e.g., …)".
                                'display_name': _CANONICAL_DISPLAY.get(
                                    skill_key, _canonicalize_skill_name(skill_name)
                                ),
                                'expert': 0,
                                'advanced': 0,
                                'intermediate': 0,
                                'beginner': 0,
                                'tasks': [],
                                'unique_tasks': set(),
                                # Task IDs currently in an ACTIVE column (in
                                # progress / review / blocked). A skill needed
                                # only by backlog/to-do tasks is not blocking
                                # work *right now*, so it should not be flagged
                                # "Critical – Cannot proceed". See severity calc.
                                'active_tasks': set(),
                            }

                        # Count requirement for this level
                        level_key = skill_level.lower()
                        if level_key in required_skills[skill_key]:
                            required_skills[skill_key][level_key] += 1

                        required_skills[skill_key]['tasks'].append({
                            'id': task.id,
                            'title': task.title,
                            'level': skill_level
                        })
                        required_skills[skill_key]['unique_tasks'].add(task.id)
                        if _is_active_column(task.column):
                            required_skills[skill_key]['active_tasks'].add(task.id)

        # Frequency filter: drop skills that appear in only 1 unique task.
        # A skill needed by a single task is a one-off task requirement, not a
        # team-level capability gap worth tracking.  Requiring ≥2 tasks dramatically
        # reduces noise (one-offs like "WCAG", "ERD", "Static Site Generators") while
        # keeping genuinely cross-cutting gaps like "Security", "Backend Development".
        total_extracted = len(required_skills)
        required_skills = {
            k: v for k, v in required_skills.items()
            if len(v.get('unique_tasks', set())) >= 2
        }
        logger.info(
            f"Frequency filter: {len(required_skills)} of {total_extracted} extracted skills "
            "appear in 2+ tasks and qualify for gap analysis"
        )

        # Calculate gaps
        gaps = []
        
        for skill_key, requirements in required_skills.items():
            # skill_key is the normalized (lowercase) key; use display_name for output
            display_name = requirements.get('display_name', skill_key)

            # Use normalized lookup to match AI-extracted names to team profile names
            available = skill_inventory_norm.get(skill_key, {
                'expert': 0,
                'advanced': 0,
                'intermediate': 0,
                'beginner': 0,
                'members': []
            })
            
            # Calculate team coverage for this skill
            expert_count = available.get('expert', 0)
            advanced_count = available.get('advanced', 0)
            intermediate_count = available.get('intermediate', 0)
            beginner_count = available.get('beginner', 0)
            
            total_team_coverage = expert_count + advanced_count + intermediate_count + beginner_count
            has_any_coverage = total_team_coverage > 0
            
            # Calculate effective coverage for each level (higher levels can cover lower)
            effective_coverage = {
                'expert': expert_count,
                'advanced': expert_count + advanced_count,
                'intermediate': expert_count + advanced_count + intermediate_count,
                'beginner': total_team_coverage
            }
            
            # Total tasks needing this skill (at any level)
            total_tasks_needing_skill = len(requirements.get('unique_tasks', set()))
            all_affected_tasks = requirements['tasks']
            # How many affected tasks are ACTIVE (in progress / review / blocked).
            # "Cannot proceed" (critical) is only truthful when the missing skill
            # is blocking work that is actually in flight — a skill needed solely
            # by backlog/to-do items is a planning gap, not a live blocker.
            active_task_count = len(requirements.get('active_tasks', set()))

            # Determine the highest proficiency level required across all tasks for this skill
            highest_level = 'beginner'
            for level in ['expert', 'advanced', 'intermediate', 'beginner']:
                if requirements[level] > 0:
                    highest_level = level
                    break

            # CASE 1: Team has ZERO coverage for this skill
            # This is always a gap - the team cannot do this work at all
            if not has_any_coverage:
                # Capacity estimate: how many people would be needed (~4 tasks/person/sprint)
                tasks_per_person = 4
                slots_needed = max(1, (total_tasks_needing_skill + tasks_per_person - 1) // tasks_per_person)
                # Cap to a reasonable number (not more than team size)
                slots_needed = min(slots_needed, max(2, team_size))

                # Severity: zero coverage is serious, but "Critical – Cannot
                # proceed" is reserved for skills blocking ACTIVE work. With no
                # active task, cap at 'high' (Blocking work) — the team can't do
                # it, but nothing is stalled on it yet.
                if active_task_count >= 1 and (
                    total_tasks_needing_skill >= 3 or highest_level in ['expert', 'advanced']
                ):
                    zero_cov_severity = 'critical'
                elif total_tasks_needing_skill >= 2 or highest_level in ['expert', 'advanced']:
                    zero_cov_severity = 'high'
                else:
                    zero_cov_severity = 'medium'

                gaps.append({
                    'skill_name': display_name,
                    'proficiency_level': highest_level.capitalize(),
                    'required_count': slots_needed,
                    'available_count': 0,
                    'gap_count': slots_needed,
                    'affected_tasks': all_affected_tasks,
                    'task_count': total_tasks_needing_skill,
                    'active_task_count': active_task_count,
                    'has_team_coverage': False,
                    'severity': zero_cov_severity,
                })
                continue

            # CASE 2: Team has SOME coverage — create ONE gap entry for this skill.
            # Compare total task workload against coverage at the highest required level.
            available_for_highest = effective_coverage.get(highest_level, 0)

            # Capacity estimate for how many people are ideally needed (display/recommendation use)
            tasks_per_person = 4
            slots_needed = max(1, (total_tasks_needing_skill + tasks_per_person - 1) // tasks_per_person)

            # Actual gap: additional people needed beyond current coverage at this level
            actual_gap = max(0, slots_needed - available_for_highest)

            # Bus factor: thin coverage is a risk even without a hard capacity gap
            is_thin_coverage = available_for_highest == 1 and total_tasks_needing_skill >= 4

            if actual_gap > 0 or is_thin_coverage:
                if actual_gap == 0:
                    # Thin coverage only — recommend adding 1 more for redundancy
                    actual_gap = 1
                    slots_needed = available_for_highest + 1
                    severity = 'low'
                else:
                    severity = _calculate_gap_severity(
                        display_name, highest_level, actual_gap, all_affected_tasks,
                        has_team_coverage=True,
                        total_team_coverage=total_team_coverage,
                        effective_coverage=available_for_highest,
                        team_size=team_size
                    )

                gaps.append({
                    'skill_name': display_name,
                    'proficiency_level': highest_level.capitalize(),
                    'required_count': slots_needed,
                    'available_count': available_for_highest,
                    'gap_count': actual_gap,
                    'affected_tasks': all_affected_tasks,
                    'task_count': total_tasks_needing_skill,
                    'active_task_count': active_task_count,
                    'has_team_coverage': True,
                    'thin_coverage': is_thin_coverage and actual_gap == 1,
                    'severity': severity
                })
        
        # Sort by severity and gap size
        severity_order = {'critical': 0, 'high': 1, 'medium': 2, 'low': 3}
        gaps.sort(key=lambda x: (severity_order.get(x['severity'], 99), -x['gap_count']))
        
        logger.info(f"Identified {len(gaps)} skill gaps for board {board.name}")
        return gaps
        
    except Exception as e:
        logger.error(f"Error calculating skill gaps: {str(e)}")
        return []


def _calculate_gap_severity(skill_name: str, level: str, gap_count: int, affected_tasks: List[Dict],
                            has_team_coverage: bool = False, total_team_coverage: int = 0,
                            effective_coverage: int = 0, team_size: int = 1) -> str:
    """
    Determine severity of a skill gap based on multiple factors
    
    CALIBRATION LOGIC:
    - Critical: Team has NO coverage OR coverage is zero for the required level with many tasks
    - High: Significant capacity gap (need 2+ more) or many tasks affected
    - Medium: Moderate gap with some coverage
    - Low: Minor gap, thin coverage warning, or small impact
    
    Args:
        skill_name: Name of the skill
        level: Proficiency level
        gap_count: Number of resources short
        affected_tasks: Tasks requiring this skill
        has_team_coverage: Whether any team member has this skill at any level
        total_team_coverage: Total team members with this skill at any level
        effective_coverage: Team members who can cover this specific level
        team_size: Total team size
        
    Returns:
        Severity level: 'low', 'medium', 'high', or 'critical'
    """
    num_affected = len(affected_tasks)
    
    # ZERO COVERAGE for this skill at the required level
    if effective_coverage == 0:
        if has_team_coverage:
            # Team has the skill but at lower level than needed
            # e.g., have Intermediate but need Expert
            if level in ['expert', 'advanced'] and num_affected >= 2:
                return 'high'
            if num_affected >= 4:
                return 'high'
            if num_affected >= 2:
                return 'medium'
            return 'low'
        else:
            # Team has NO ONE with this skill - this is serious
            if num_affected >= 3 or level in ['expert', 'advanced']:
                return 'critical'
            if num_affected >= 2:
                return 'high'
            return 'medium'  # Even 1 task needing a skill no one has is medium
    
    # PARTIAL COVERAGE exists
    # The gap represents additional capacity needed beyond what we have
    
    if gap_count >= 2:
        # Need 2+ more people
        if num_affected >= 5:
            return 'high'
        return 'medium'
    
    # gap_count is 1
    if num_affected >= 6:
        return 'medium'
    if num_affected >= 3:
        return 'low'
    
    return 'low'


def generate_skill_gap_recommendations(gap_data: Dict, board) -> List[Dict]:
    """
    Generate AI-powered recommendations for addressing skill gaps
    
    Args:
        gap_data: Dictionary containing gap information
        board: Board instance for context
        
    Returns:
        List of recommendation dictionaries
    """
    try:
        from ai_assistant.utils.ai_router import AIRouter
        router = AIRouter()

        if not router:
            return _get_fallback_recommendations(gap_data)
        
        # Build context about the gap
        skill_name = gap_data['skill_name']
        level = gap_data['proficiency_level']
        gap_count = gap_data['gap_count']
        affected_tasks = gap_data.get('affected_tasks', [])
        severity = gap_data.get('severity', 'medium')
        
        prompt = f"""You are a resource management AI assistant. Analyze this skill gap and provide actionable recommendations.

**Skill Gap Details:**
- Skill: {skill_name} ({level} level)
- Gap: Need {gap_count} more team member(s) with this skill
- Severity: {severity}
- Affected Tasks: {len(affected_tasks)} tasks require this skill

**Context:**
Tasks requiring this skill:
{json.dumps([t['title'] for t in affected_tasks[:5]], indent=2)}

**Instructions:**
Provide 3-4 specific, actionable recommendations to address this gap. Consider:
1. Training/upskilling existing team members
2. Hiring or contracting resources
3. Redistributing work or adjusting timelines
4. Cross-training or pair programming
5. Using external consultants or vendors

For each recommendation:
- Provide clear action steps
- Estimate timeframe (days or weeks)
- Estimate cost (low/medium/high)
- Rate priority (1-10, where 10 is most urgent)

Return ONLY a valid JSON array, nothing else:
[
  {{
    "type": "training",
    "title": "Brief title",
    "description": "Detailed action steps",
    "timeframe_days": 14,
    "cost_estimate": "medium",
    "priority": 8,
    "expected_impact": "Expected outcome"
  }}
]

Valid types: "training", "hiring", "contractor", "redistribute", "mentorship", "cross_training"

JSON array:"""

        # Generation config for recommendations - low temperature for consistent outputs
        generation_config = {
            'temperature': 0.2,  # Low for consistent, reproducible recommendations
            'top_p': 0.8,
            'top_k': 40,
            'max_output_tokens': 2048,  # More tokens for detailed recommendations
        }

        result = router.complete(
            prompt=prompt,
            user=None,
            complexity='simple',
        )
        response_text = result.get('text', '').strip()
        json_match = re.search(r'\[[\s\S]*\]', response_text)
        if json_match:
            recommendations_json = json_match.group(0)
            recommendations = json.loads(recommendations_json)
            
            # Validate and enrich
            valid_recs = []
            valid_types = ['training', 'hiring', 'contractor', 'redistribute', 'mentorship', 'cross_training']
            
            for rec in recommendations:
                if isinstance(rec, dict) and 'type' in rec and rec['type'] in valid_types:
                    valid_recs.append({
                        'type': rec['type'],
                        'title': rec.get('title', 'Recommendation'),
                        'description': rec.get('description', ''),
                        'timeframe_days': rec.get('timeframe_days', 30),
                        'cost_estimate': rec.get('cost_estimate', 'medium'),
                        'priority': rec.get('priority', 5),
                        'expected_impact': rec.get('expected_impact', ''),
                        'ai_generated': True
                    })
            
            logger.info(f"Generated {len(valid_recs)} AI recommendations for {skill_name} gap")
            return valid_recs
        
        return _get_fallback_recommendations(gap_data)
        
    except Exception as e:
        logger.error(f"Error generating recommendations: {str(e)}")
        return _get_fallback_recommendations(gap_data)


def _get_fallback_recommendations(gap_data: Dict) -> List[Dict]:
    """
    Provide rule-based fallback recommendations if AI fails
    """
    skill_name = gap_data['skill_name']
    level = gap_data['proficiency_level']
    gap_count = gap_data['gap_count']
    
    recommendations = []
    
    # Training recommendation
    if level in ['Beginner', 'Intermediate']:
        recommendations.append({
            'type': 'training',
            'title': f'Upskill team members in {skill_name}',
            'description': f'Provide {skill_name} training to {gap_count} team member(s) to reach {level} proficiency.',
            'timeframe_days': 30 if level == 'Beginner' else 60,
            'cost_estimate': 'medium',
            'priority': 7,
            'expected_impact': f'{gap_count} team member(s) will be able to handle {skill_name} tasks',
            'ai_generated': False
        })
    
    # Hiring recommendation for advanced skills
    if level in ['Advanced', 'Expert'] or gap_count >= 2:
        recommendations.append({
            'type': 'hiring',
            'title': f'Hire {skill_name} specialist',
            'description': f'Recruit {gap_count} team member(s) with {level} {skill_name} expertise.',
            'timeframe_days': 60,
            'cost_estimate': 'high',
            'priority': 9 if level == 'Expert' else 7,
            'expected_impact': f'Immediate capability to handle {skill_name} tasks',
            'ai_generated': False
        })
    
    # Redistribution recommendation
    recommendations.append({
        'type': 'redistribute',
        'title': f'Redistribute {skill_name} work',
        'description': f'Adjust task assignments and timelines to work around {skill_name} constraint.',
        'timeframe_days': 7,
        'cost_estimate': 'low',
        'priority': 5,
        'expected_impact': 'Short-term mitigation while permanent solution is implemented',
        'ai_generated': False
    })
    
    return recommendations


def match_team_member_to_task(task, board_members) -> List[Dict]:
    """
    Find best team members for a task based on skill matching
    
    Args:
        task: Task instance with required_skills
        board_members: QuerySet of User objects (board members)
        
    Returns:
        List of match results sorted by score (best first)
        [{'user': User, 'match_score': 85, 'matched_skills': [...], 'missing_skills': [...]}]
    """
    try:
        if not task.required_skills:
            return []
        
        matches = []
        
        for member in board_members:
            try:
                profile = member.profile
                match_result = _calculate_skill_match(task.required_skills, profile.skills)
                
                # Only include if some match
                if match_result['match_score'] > 0:
                    matches.append({
                        'user': member,
                        'user_id': member.id,
                        'username': member.username,
                        'full_name': member.get_full_name() or member.username,
                        'match_score': match_result['match_score'],
                        'matched_skills': match_result['matched_skills'],
                        'missing_skills': match_result['missing_skills'],
                        'current_workload': profile.current_workload_hours,
                        'available_hours': profile.available_hours
                    })
            except Exception as e:
                logger.warning(f"Error matching member {member.username}: {str(e)}")
                continue
        
        # Sort by match score (descending), then by available capacity
        matches.sort(key=lambda x: (-x['match_score'], -x['available_hours']))
        
        return matches
        
    except Exception as e:
        logger.error(f"Error matching team members to task: {str(e)}")
        return []


def _calculate_skill_match(required_skills: List[Dict], member_skills: List[Dict]) -> Dict:
    """
    Calculate how well a team member's skills match task requirements
    
    Args:
        required_skills: Task required skills
        member_skills: Team member's skills
        
    Returns:
        Match result with score and details
    """
    if not required_skills:
        return {'match_score': 0, 'matched_skills': [], 'missing_skills': []}
    
    # Level scoring weights
    level_weights = {
        'beginner': 1,
        'intermediate': 2,
        'advanced': 3,
        'expert': 4
    }
    
    matched_skills = []
    missing_skills = []
    total_required_weight = 0
    total_matched_weight = 0
    
    # Build member skill lookup, keyed by the same canonical key used for gap
    # detection so generic task disciplines match specific member technologies
    # (e.g. task "Backend Development" matches member "Python"/"Django"). If
    # several member skills collapse to one key, keep the highest weight.
    member_skill_map = {}
    for skill in member_skills:
        skill_name = _normalize_skill_name(skill.get('name', '').strip())
        skill_level = skill.get('level', 'Intermediate').lower()
        weight = level_weights.get(skill_level, 2)
        if weight > member_skill_map.get(skill_name, 0):
            member_skill_map[skill_name] = weight

    # Check each required skill
    for req_skill in required_skills:
        skill_name = req_skill.get('name', '').strip()
        required_level = req_skill.get('level', 'Intermediate').lower()
        required_weight = level_weights.get(required_level, 2)
        total_required_weight += required_weight

        skill_name_lower = _normalize_skill_name(skill_name)

        if skill_name_lower in member_skill_map:
            member_weight = member_skill_map[skill_name_lower]
            
            # Partial credit if member has skill but at lower level
            if member_weight >= required_weight:
                # Full match
                total_matched_weight += required_weight
                matched_skills.append({
                    'name': skill_name,
                    'required_level': required_level.capitalize(),
                    'member_level': _get_level_name(member_weight),
                    'match_quality': 'exact' if member_weight == required_weight else 'exceeds'
                })
            else:
                # Partial match (has skill but lower level)
                total_matched_weight += member_weight * 0.7  # 70% credit
                matched_skills.append({
                    'name': skill_name,
                    'required_level': required_level.capitalize(),
                    'member_level': _get_level_name(member_weight),
                    'match_quality': 'partial'
                })
        else:
            missing_skills.append({
                'name': skill_name,
                'level': required_level.capitalize()
            })
    
    # Calculate percentage match
    match_score = int((total_matched_weight / total_required_weight * 100) if total_required_weight > 0 else 0)
    
    return {
        'match_score': min(100, match_score),
        'matched_skills': matched_skills,
        'missing_skills': missing_skills
    }


def _get_level_name(weight: int) -> str:
    """Convert weight back to level name"""
    weight_to_level = {1: 'Beginner', 2: 'Intermediate', 3: 'Advanced', 4: 'Expert'}
    return weight_to_level.get(weight, 'Intermediate')


def update_team_skill_profile_model(board):
    """
    Update or create TeamSkillProfile model for a board
    
    Args:
        board: Board instance
    """
    try:
        from kanban.models import TeamSkillProfile
        import time as _time
        
        # Build current profile
        profile_data = build_team_skill_profile(board)
        
        # Update or create model with retry for SQLite database lock
        max_retries = 3
        for attempt in range(max_retries):
            try:
                team_profile, created = TeamSkillProfile.objects.update_or_create(
                    board=board,
                    defaults={
                        'skill_inventory': profile_data['skill_inventory'],
                        'total_capacity_hours': profile_data['total_capacity_hours'],
                        'utilized_capacity_hours': profile_data['utilized_capacity_hours'],
                        'last_analysis': timezone.now()
                    }
                )
                
                action = "Created" if created else "Updated"
                logger.info(f"{action} TeamSkillProfile for board {board.name}")
                return team_profile
            except Exception as db_err:
                if 'database is locked' in str(db_err) and attempt < max_retries - 1:
                    logger.warning(f"Database locked updating TeamSkillProfile, retrying ({attempt + 1}/{max_retries})...")
                    _time.sleep(0.5 * (attempt + 1))
                    continue
                raise
        
    except Exception as e:
        logger.error(f"Error updating TeamSkillProfile: {str(e)}")
        return None


def auto_populate_task_skills(task):
    """
    Automatically extract and populate required_skills for a task
    
    Args:
        task: Task instance
        
    Returns:
        True if skills were extracted and saved, False otherwise
    """
    try:
        # Skip if skills already defined
        if task.required_skills:
            logger.info(f"Task {task.id} already has skills defined, skipping auto-population")
            return False
        
        # Extract skills
        skills = extract_skills_from_task(task.title, task.description or "")
        
        if skills:
            task.required_skills = skills
            task.save(update_fields=['required_skills'])
            logger.info(f"Auto-populated {len(skills)} skills for task {task.id}: {task.title}")
            return True
        
        return False
        
    except Exception as e:
        logger.error(f"Error auto-populating task skills: {str(e)}")
        return False
