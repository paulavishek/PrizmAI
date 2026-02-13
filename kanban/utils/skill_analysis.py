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

import google.generativeai as genai
from django.conf import settings
from django.db.models import Q, Count, Avg, Sum
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
        prompt = f"""Analyze this task and extract the technical skills required to complete it.

Task Title: {task_title}
Task Description: {task_description or 'Not provided'}

Instructions:
1. Identify all technical skills, tools, frameworks, and technologies required
2. For each skill, estimate the proficiency level needed: Beginner, Intermediate, Advanced, or Expert
3. Be specific (e.g., "Python" not just "Programming")
4. Include both hard skills (programming languages, tools) and relevant soft skills (e.g., "Communication" for tasks requiring stakeholder interaction)
5. Return ONLY a valid JSON array, nothing else

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
        
        model = get_model()
        if not model:
            return []

        # Generation config for skill extraction - simpler JSON output
        generation_config = {
            'temperature': 0.3,  # Low for consistent skill identification
            'top_p': 0.8,
            'top_k': 40,
            'max_output_tokens': 1024,  # Skill list doesn't need many tokens
        }

        response = model.generate_content(prompt, generation_config=generation_config)
        response_text = response.text.strip()
        
        # Extract JSON from response (handle markdown code blocks)
        json_match = re.search(r'\[[\s\S]*\]', response_text)
        if json_match:
            skills_json = json_match.group(0)
            skills = json.loads(skills_json)
            
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
        
        logger.warning(f"No valid JSON found in skill extraction response")
        return []
        
    except json.JSONDecodeError as e:
        logger.error(f"Failed to parse skill extraction JSON: {str(e)}")
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
        members = board.members.select_related('profile').all()
        
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
                    
                    if skill_name:
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
        
        # Auto-populate required_skills for tasks that don't have them
        tasks_needing_skills = [t for t in tasks if not t.required_skills]
        skills_extracted_count = 0
        
        if tasks_needing_skills:
            logger.info(f"Auto-extracting skills for {len(tasks_needing_skills)} tasks without defined skills")
            # Limit to first 15 to avoid API rate limits (increased from 10)
            for task in tasks_needing_skills[:15]:
                try:
                    extracted_skills = extract_skills_from_task(task.title, task.description or "")
                    if extracted_skills:
                        task.required_skills = extracted_skills
                        task.save(update_fields=['required_skills'])
                        skills_extracted_count += 1
                except Exception as e:
                    logger.warning(f"Failed to extract skills for task {task.id}: {str(e)}")
                    continue
            
            if skills_extracted_count > 0:
                logger.info(f"Auto-extracted skills for {skills_extracted_count} tasks")
        
        # Build team skill profile
        team_profile = build_team_skill_profile(board)
        skill_inventory = team_profile['skill_inventory']
        team_size = team_profile.get('team_size', 1) or 1
        
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
                        if skill_name not in required_skills:
                            required_skills[skill_name] = {
                                'expert': 0,
                                'advanced': 0,
                                'intermediate': 0,
                                'beginner': 0,
                                'tasks': [],
                                'unique_tasks': set()
                            }
                        
                        # Count requirement for this level
                        level_key = skill_level.lower()
                        if level_key in required_skills[skill_name]:
                            required_skills[skill_name][level_key] += 1
                        
                        required_skills[skill_name]['tasks'].append({
                            'id': task.id,
                            'title': task.title,
                            'level': skill_level
                        })
                        required_skills[skill_name]['unique_tasks'].add(task.id)
        
        # Calculate gaps
        gaps = []
        
        for skill_name, requirements in required_skills.items():
            available = skill_inventory.get(skill_name, {
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
            
            # CASE 1: Team has ZERO coverage for this skill
            # This is always a gap - the team cannot do this work at all
            if not has_any_coverage:
                # Calculate gap count based on workload
                # Assume 1 person can handle up to 5 tasks in a sprint
                tasks_per_person = 5
                gap_count = max(1, (total_tasks_needing_skill + tasks_per_person - 1) // tasks_per_person)
                # Cap at reasonable number (not more than team size)
                gap_count = min(gap_count, max(2, team_size))
                
                # Determine the highest level needed
                highest_level = 'beginner'
                for level in ['expert', 'advanced', 'intermediate', 'beginner']:
                    if requirements[level] > 0:
                        highest_level = level
                        break
                
                gaps.append({
                    'skill_name': skill_name,
                    'proficiency_level': highest_level.capitalize(),
                    'required_count': gap_count,
                    'available_count': 0,
                    'gap_count': gap_count,
                    'affected_tasks': all_affected_tasks,
                    'task_count': total_tasks_needing_skill,
                    'has_team_coverage': False,
                    'severity': 'critical' if total_tasks_needing_skill >= 3 or highest_level in ['expert', 'advanced'] else 'high'
                })
                continue
            
            # CASE 2: Team has SOME coverage - check each proficiency level
            for level in ['expert', 'advanced', 'intermediate', 'beginner']:
                task_count_at_level = requirements[level]
                
                if task_count_at_level == 0:
                    continue
                
                # Get effective team members who can handle this level
                available_for_level = effective_coverage.get(level, 0)
                
                # Calculate capacity-based need
                # Assume each person can handle 4-5 tasks per sprint
                tasks_per_person = 4
                slots_needed = max(1, (task_count_at_level + tasks_per_person - 1) // tasks_per_person)
                
                # Calculate gap
                gap_count = max(0, slots_needed - available_for_level)
                
                # Even if gap_count is 0, check if coverage is thin (bus factor)
                # If only 1 person covers many tasks, that's a risk
                is_thin_coverage = available_for_level == 1 and task_count_at_level >= 4
                
                if gap_count > 0 or is_thin_coverage:
                    affected_tasks = [t for t in requirements['tasks'] if t['level'].lower() == level]
                    
                    # Determine severity
                    if gap_count > 0:
                        severity = _calculate_gap_severity(
                            skill_name, level, gap_count, affected_tasks,
                            has_team_coverage=True,
                            total_team_coverage=total_team_coverage,
                            effective_coverage=available_for_level,
                            team_size=team_size
                        )
                    else:
                        # Thin coverage warning (bus factor risk)
                        severity = 'low'
                        gap_count = 1  # Suggest adding 1 more for redundancy
                    
                    gaps.append({
                        'skill_name': skill_name,
                        'proficiency_level': level.capitalize(),
                        'required_count': slots_needed,
                        'available_count': available_for_level,
                        'gap_count': gap_count,
                        'affected_tasks': affected_tasks,
                        'task_count': task_count_at_level,
                        'has_team_coverage': True,
                        'thin_coverage': is_thin_coverage and gap_count == 1,
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
        model = get_model()
        if not model:
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

        # Generation config for recommendations - needs more detail
        generation_config = {
            'temperature': 0.5,  # Balanced for creative yet practical recommendations
            'top_p': 0.8,
            'top_k': 40,
            'max_output_tokens': 2048,  # More tokens for detailed recommendations
        }

        response = model.generate_content(prompt, generation_config=generation_config)
        response_text = response.text.strip()
        
        # Extract JSON
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
    
    # Build member skill lookup
    member_skill_map = {}
    for skill in member_skills:
        skill_name = skill.get('name', '').strip().lower()
        skill_level = skill.get('level', 'Intermediate').lower()
        member_skill_map[skill_name] = level_weights.get(skill_level, 2)
    
    # Check each required skill
    for req_skill in required_skills:
        skill_name = req_skill.get('name', '').strip()
        required_level = req_skill.get('level', 'Intermediate').lower()
        required_weight = level_weights.get(required_level, 2)
        total_required_weight += required_weight
        
        skill_name_lower = skill_name.lower()
        
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
        
        # Build current profile
        profile_data = build_team_skill_profile(board)
        
        # Update or create model
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
