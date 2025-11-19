"""
Quick Usage Examples for Skill Matching Feature
This file demonstrates how to use the skill matching API programmatically
"""

from django.contrib.auth.models import User
from kanban.models import Board, Task, SkillGap, SkillDevelopmentPlan
from kanban.utils.skill_analysis import (
    extract_skills_from_task,
    build_team_skill_profile,
    calculate_skill_gaps,
    match_team_member_to_task,
    update_team_skill_profile_model,
    auto_populate_task_skills
)


# ============================================
# Example 1: Extract Skills from Task
# ============================================

def example_extract_skills():
    """Extract required skills from a task description using AI"""
    
    task_title = "Build REST API for user authentication"
    task_description = """
    Create a RESTful API endpoint for user registration and login.
    Use JWT tokens for authentication. Store user data in PostgreSQL.
    Write unit tests with pytest. Document with Swagger.
    """
    
    # AI extracts skills automatically
    skills = extract_skills_from_task(task_title, task_description)
    
    print("Extracted Skills:")
    for skill in skills:
        print(f"  - {skill['name']}: {skill['level']}")
    
    # Expected output:
    # - Python: Intermediate
    # - Django REST Framework: Advanced
    # - JWT: Intermediate
    # - PostgreSQL: Beginner
    # - Pytest: Intermediate
    # - API Documentation: Beginner


# ============================================
# Example 2: Auto-Populate Task Skills
# ============================================

def example_auto_populate_task():
    """Automatically populate skills for an existing task"""
    
    task = Task.objects.get(id=101)
    
    # This will extract and save skills if not already present
    success = auto_populate_task_skills(task)
    
    if success:
        print(f"Auto-populated {len(task.required_skills)} skills for task: {task.title}")
        print(task.required_skills)
    else:
        print("Task already has skills or extraction failed")


# ============================================
# Example 3: Build Team Skill Profile
# ============================================

def example_team_profile():
    """Get comprehensive team skill inventory"""
    
    board = Board.objects.get(id=1)
    profile = build_team_skill_profile(board)
    
    print(f"Team Size: {profile['team_size']}")
    print(f"Total Capacity: {profile['total_capacity_hours']}h/week")
    print(f"Utilization: {profile['utilization_percentage']:.1f}%")
    print(f"\nTop Skills:")
    
    # Show top 5 skills
    skills = profile['skill_inventory']
    for skill_name, skill_data in list(skills.items())[:5]:
        total = sum([skill_data['expert'], skill_data['advanced'], 
                     skill_data['intermediate'], skill_data['beginner']])
        print(f"  - {skill_name}: {total} members")
        print(f"    Expert: {skill_data['expert']}, Advanced: {skill_data['advanced']}")


# ============================================
# Example 4: Calculate and Save Skill Gaps
# ============================================

def example_calculate_gaps():
    """Identify skill gaps for upcoming work"""
    
    board = Board.objects.get(id=1)
    
    # Calculate gaps for next 2 weeks
    gaps = calculate_skill_gaps(board, sprint_period_days=14)
    
    print(f"Found {len(gaps)} skill gaps:")
    
    for gap in gaps:
        print(f"\n{'='*50}")
        print(f"Skill: {gap['skill_name']} ({gap['proficiency_level']})")
        print(f"Gap: Need {gap['gap_count']} more team member(s)")
        print(f"Severity: {gap['severity'].upper()}")
        print(f"Affects {len(gap['affected_tasks'])} tasks")
        
        if gap.get('recommendations'):
            print("\nRecommendations:")
            for rec in gap['recommendations'][:2]:  # Show top 2
                print(f"  {rec['type'].title()}: {rec['title']}")
                print(f"    Timeframe: {rec['timeframe_days']} days")
                print(f"    Priority: {rec['priority']}/10")


# ============================================
# Example 5: Match Team Members to Task
# ============================================

def example_match_team():
    """Find best team members for a task"""
    
    task = Task.objects.get(id=101)
    board = task.column.board
    board_members = board.members.select_related('profile').all()
    
    matches = match_team_member_to_task(task, board_members)
    
    print(f"Task: {task.title}")
    print(f"\nRequired Skills:")
    for skill in task.required_skills:
        print(f"  - {skill['name']}: {skill['level']}")
    
    print(f"\nTop 3 Matches:")
    for i, match in enumerate(matches[:3], 1):
        print(f"\n{i}. {match['full_name']} (Match: {match['match_score']}%)")
        print(f"   Available: {match['available_hours']}h")
        print(f"   Matched Skills:")
        for skill in match['matched_skills']:
            quality = skill['match_quality']
            symbol = "✓" if quality == "exact" else "↑" if quality == "exceeds" else "~"
            print(f"     {symbol} {skill['name']}: {skill['member_level']}")
        
        if match['missing_skills']:
            print(f"   Missing Skills:")
            for skill in match['missing_skills']:
                print(f"     ✗ {skill['name']}: {skill['level']}")


# ============================================
# Example 6: Create Development Plan
# ============================================

def example_create_dev_plan():
    """Create a skill development plan to address a gap"""
    
    from django.utils import timezone
    from datetime import timedelta
    
    # Find a critical skill gap
    gap = SkillGap.objects.filter(
        severity='critical',
        status='identified'
    ).first()
    
    if not gap:
        print("No critical gaps found")
        return
    
    # Create training plan
    plan = SkillDevelopmentPlan.objects.create(
        skill_gap=gap,
        board=gap.board,
        plan_type='training',
        title=f"Upskill team in {gap.skill_name}",
        description=f"Provide {gap.skill_name} training to bridge gap",
        target_skill=gap.skill_name,
        target_proficiency=gap.proficiency_level,
        created_by=User.objects.first(),
        start_date=timezone.now().date(),
        target_completion_date=(timezone.now() + timedelta(days=60)).date(),
        estimated_cost=3000.00,
        estimated_hours=80,
        status='proposed',
        ai_suggested=True
    )
    
    # Assign to team members
    # Find members who have this skill at lower level
    from accounts.models import UserProfile
    candidates = UserProfile.objects.filter(
        organization=gap.board.organization
    )
    
    for profile in candidates:
        for skill in profile.skills:
            if skill.get('name') == gap.skill_name:
                plan.target_users.add(profile.user)
    
    print(f"Created development plan: {plan.title}")
    print(f"Target: {plan.target_users.count()} team members")
    print(f"Timeline: {plan.start_date} to {plan.target_completion_date}")
    print(f"Budget: ${plan.estimated_cost}")


# ============================================
# Example 7: Update Team Profile Model
# ============================================

def example_update_profile():
    """Update the TeamSkillProfile model for a board"""
    
    board = Board.objects.get(id=1)
    
    # This will calculate and save the team profile
    team_profile = update_team_skill_profile_model(board)
    
    print(f"Updated Team Skill Profile for: {board.name}")
    print(f"Total Skills Tracked: {len(team_profile.available_skills)}")
    print(f"Team Utilization: {team_profile.utilization_percentage:.1f}%")
    print(f"Last Updated: {team_profile.last_updated}")


# ============================================
# Example 8: Get Gap Analysis Report
# ============================================

def example_gap_report():
    """Generate a comprehensive gap analysis report"""
    
    board = Board.objects.get(id=1)
    
    # Get all active gaps
    gaps = SkillGap.objects.filter(
        board=board,
        status__in=['identified', 'acknowledged', 'in_progress']
    ).order_by('-severity', '-gap_count')
    
    print(f"{'='*70}")
    print(f"SKILL GAP ANALYSIS REPORT - {board.name}")
    print(f"{'='*70}\n")
    
    # Summary
    critical = gaps.filter(severity='critical').count()
    high = gaps.filter(severity='high').count()
    medium = gaps.filter(severity='medium').count()
    low = gaps.filter(severity='low').count()
    
    print(f"Total Gaps: {gaps.count()}")
    print(f"  Critical: {critical}")
    print(f"  High: {high}")
    print(f"  Medium: {medium}")
    print(f"  Low: {low}")
    print()
    
    # Details
    for gap in gaps:
        print(f"\n{'-'*70}")
        print(f"Skill: {gap.skill_name} ({gap.proficiency_level})")
        print(f"Gap: {gap.gap_count} member(s) needed")
        print(f"Severity: {gap.severity.upper()}")
        print(f"Status: {gap.status}")
        print(f"Affected Tasks: {gap.affected_tasks.count()}")
        
        # Show development plans
        plans = SkillDevelopmentPlan.objects.filter(skill_gap=gap)
        if plans.exists():
            print(f"\nDevelopment Plans ({plans.count()}):")
            for plan in plans:
                print(f"  - {plan.title} ({plan.status})")
                print(f"    Progress: {plan.progress_percentage}%")


# ============================================
# Example 9: Bulk Process Tasks
# ============================================

def example_bulk_process():
    """Process multiple tasks to extract and analyze skills"""
    
    board = Board.objects.get(id=1)
    tasks = Task.objects.filter(
        column__board=board,
        progress__lt=100,
        required_skills=[]  # Tasks without skills
    )
    
    print(f"Processing {tasks.count()} tasks...")
    
    processed = 0
    for task in tasks:
        if auto_populate_task_skills(task):
            processed += 1
    
    print(f"Successfully processed {processed} tasks")
    
    # Now run gap analysis
    print("\nRunning gap analysis...")
    gaps = calculate_skill_gaps(board, sprint_period_days=14)
    print(f"Identified {len(gaps)} skill gaps")


# ============================================
# Example 10: API Usage (Django Shell)
# ============================================

def example_api_usage():
    """
    Example of calling the API endpoints programmatically
    (Run this in Django shell with requests library)
    """
    
    import requests
    from django.contrib.auth.models import User
    
    # Setup
    user = User.objects.first()
    board_id = 1
    base_url = "http://localhost:8000"
    
    # You would need to handle authentication in a real scenario
    # This is just to show the endpoint structure
    
    print("Available API Endpoints:")
    print(f"\n1. Analyze Gaps:")
    print(f"   GET {base_url}/kanban/api/skill-gaps/analyze/{board_id}/")
    
    print(f"\n2. Get Team Profile:")
    print(f"   GET {base_url}/kanban/api/team-skill-profile/{board_id}/")
    
    print(f"\n3. Match Team to Task:")
    print(f"   POST {base_url}/kanban/api/task/{{task_id}}/match-team/")
    
    print(f"\n4. Extract Task Skills:")
    print(f"   POST {base_url}/kanban/api/task/{{task_id}}/extract-skills/")
    
    print(f"\n5. Create Development Plan:")
    print(f"   POST {base_url}/kanban/api/development-plans/create/")
    
    print(f"\n6. List Skill Gaps:")
    print(f"   GET {base_url}/kanban/api/skill-gaps/list/{board_id}/")
    
    print(f"\n7. Get Development Plans:")
    print(f"   GET {base_url}/kanban/api/development-plans/{board_id}/")


# ============================================
# Run Examples
# ============================================

if __name__ == "__main__":
    print("Skill Matching Feature - Usage Examples")
    print("=" * 70)
    print("\nTo run these examples, execute them in Django shell:")
    print("  python manage.py shell")
    print("  >>> from skill_matching_examples import *")
    print("  >>> example_extract_skills()")
    print("\nOr run specific examples:")
    print("  >>> example_calculate_gaps()")
    print("  >>> example_match_team()")
