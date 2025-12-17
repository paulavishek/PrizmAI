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


def extract_skills_from_task(task_title: str, task_description: str = "") -> List[Dict[str, str]]:
    """
    Extract required skills from task title and description using AI
    
    Args:
        task_title: Title of the task
        task_description: Optional detailed description
        
    Returns:
        List of skills with proficiency levels:
        [{'name': 'Python', 'level': 'Intermediate'}, ...]
    """
    try:
        model = get_model()
        if not model:
            return []
        
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

        response = model.generate_content(prompt)
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
    
    Args:
        board: Board instance
        sprint_period_days: Number of days to look ahead for tasks (default: 2 weeks)
        
    Returns:
        List of skill gap dictionaries with recommendations
    """
    try:
        from kanban.models import Task
        
        # Get upcoming/active tasks with optimized query
        end_date = timezone.now() + timedelta(days=sprint_period_days)
        tasks = Task.objects.filter(
            column__board=board,
            progress__lt=100
        ).filter(
            Q(due_date__isnull=True) | Q(due_date__lte=end_date)
        ).select_related('column').only('id', 'title', 'required_skills', 'column__board')
        
        # Build team skill profile
        team_profile = build_team_skill_profile(board)
        skill_inventory = team_profile['skill_inventory']
        
        # Aggregate required skills from tasks
        required_skills = {}
        
        for task in tasks:
            if task.required_skills:
                for skill in task.required_skills:
                    skill_name = skill.get('name', '').strip()
                    skill_level = skill.get('level', 'Intermediate').capitalize()
                    
                    if skill_name:
                        if skill_name not in required_skills:
                            required_skills[skill_name] = {
                                'expert': 0,
                                'advanced': 0,
                                'intermediate': 0,
                                'beginner': 0,
                                'tasks': []
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
        
        # Calculate gaps
        gaps = []
        
        for skill_name, requirements in required_skills.items():
            available = skill_inventory.get(skill_name, {
                'expert': 0,
                'advanced': 0,
                'intermediate': 0,
                'beginner': 0
            })
            
            # Check each proficiency level
            for level in ['expert', 'advanced', 'intermediate', 'beginner']:
                required_count = requirements[level]
                available_count = available.get(level, 0)
                
                if required_count > available_count:
                    gap = {
                        'skill_name': skill_name,
                        'proficiency_level': level.capitalize(),
                        'required_count': required_count,
                        'available_count': available_count,
                        'gap_count': required_count - available_count,
                        'affected_tasks': [t for t in requirements['tasks'] if t['level'].lower() == level],
                        'severity': _calculate_gap_severity(skill_name, level, required_count - available_count, requirements['tasks'])
                    }
                    gaps.append(gap)
        
        # Sort by severity and gap size
        severity_order = {'critical': 0, 'high': 1, 'medium': 2, 'low': 3}
        gaps.sort(key=lambda x: (severity_order.get(x['severity'], 99), -x['gap_count']))
        
        logger.info(f"Identified {len(gaps)} skill gaps for board {board.name}")
        return gaps
        
    except Exception as e:
        logger.error(f"Error calculating skill gaps: {str(e)}")
        return []


def _calculate_gap_severity(skill_name: str, level: str, gap_count: int, affected_tasks: List[Dict]) -> str:
    """
    Determine severity of a skill gap based on multiple factors
    
    Args:
        skill_name: Name of the skill
        level: Proficiency level
        gap_count: Number of resources short
        affected_tasks: Tasks requiring this skill
        
    Returns:
        Severity level: 'low', 'medium', 'high', or 'critical'
    """
    # Critical if gap > 2 or expert/advanced level needed
    if gap_count >= 3 or (gap_count >= 2 and level in ['expert', 'advanced']):
        return 'critical'
    
    # High if gap >= 2 or affects many tasks
    if gap_count >= 2 or len(affected_tasks) >= 5:
        return 'high'
    
    # Medium if affects multiple tasks
    if len(affected_tasks) >= 2:
        return 'medium'
    
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

        response = model.generate_content(prompt)
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
