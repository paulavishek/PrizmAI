"""
Test Script for Resource Leveling Implementation
Run with: python manage.py shell < test_resource_leveling.py
"""

from django.contrib.auth.models import User
from kanban.models import Board, Column, Task
from kanban.resource_leveling import ResourceLevelingService, WorkloadBalancer
from kanban.resource_leveling_models import UserPerformanceProfile, ResourceLevelingSuggestion
from django.utils import timezone
from datetime import timedelta
import random

def test_resource_leveling():
    print("=" * 80)
    print("RESOURCE LEVELING IMPLEMENTATION TEST")
    print("=" * 80)
    
    # 1. Check if models are installed
    print("\n1. Testing Models...")
    try:
        profile_count = UserPerformanceProfile.objects.count()
        print(f"   ✅ UserPerformanceProfile accessible ({profile_count} existing)")
        
        suggestion_count = ResourceLevelingSuggestion.objects.count()
        print(f"   ✅ ResourceLevelingSuggestion accessible ({suggestion_count} existing)")
        
    except Exception as e:
        print(f"   ❌ Error accessing models: {e}")
        print("   → Run: python manage.py migrate")
        return False
    
    # 2. Get test board
    print("\n2. Getting Test Board...")
    try:
        board = Board.objects.first()
        if not board:
            print("   ❌ No boards found. Create a board first.")
            return False
        print(f"   ✅ Using board: {board.name}")
        
        members = board.members.all()
        if members.count() < 2:
            print(f"   ⚠️  Board has only {members.count()} member(s). Add more for better testing.")
        else:
            print(f"   ✅ Board has {members.count()} members")
        
    except Exception as e:
        print(f"   ❌ Error getting board: {e}")
        return False
    
    # 3. Test Service Initialization
    print("\n3. Testing Service Initialization...")
    try:
        service = ResourceLevelingService(board.organization)
        print("   ✅ ResourceLevelingService initialized")
        
        balancer = WorkloadBalancer(board.organization)
        print("   ✅ WorkloadBalancer initialized")
        
    except Exception as e:
        print(f"   ❌ Error initializing services: {e}")
        return False
    
    # 4. Test Profile Creation
    print("\n4. Testing Performance Profile Creation...")
    try:
        for member in board.members.all()[:3]:  # Test first 3 members
            profile = service.get_or_create_profile(member)
            print(f"   ✅ Profile for {member.username}:")
            print(f"      - Velocity: {profile.velocity_score:.2f} tasks/week")
            print(f"      - Utilization: {profile.utilization_percentage:.1f}%")
            print(f"      - Active tasks: {profile.current_active_tasks}")
            print(f"      - Completed: {profile.total_tasks_completed} tasks")
        
    except Exception as e:
        print(f"   ❌ Error creating profiles: {e}")
        return False
    
    # 5. Test Workload Report
    print("\n5. Testing Workload Report...")
    try:
        report = service.get_team_workload_report(board)
        print(f"   ✅ Team Report Generated:")
        print(f"      - Team size: {report['team_size']}")
        print(f"      - Bottlenecks: {len(report['bottlenecks'])}")
        print(f"      - Underutilized: {len(report['underutilized'])}")
        
        if report['members']:
            print(f"\n      Team Members:")
            for member in report['members'][:5]:  # Show first 5
                status_icon = {
                    'overloaded': '🔴',
                    'balanced': '🟢',
                    'underutilized': '🔵'
                }.get(member['status'], '⚪')
                print(f"      {status_icon} {member['name']}: {member['utilization']:.0f}% ({member['active_tasks']} tasks)")
        
    except Exception as e:
        print(f"   ❌ Error generating workload report: {e}")
        return False
    
    # 6. Test Task Analysis
    print("\n6. Testing Task Analysis...")
    try:
        # Get an active task
        task = Task.objects.filter(
            column__board=board,
            completed_date__isnull=True
        ).first()
        
        if not task:
            print("   ⚠️  No active tasks found. Create a task to test assignment analysis.")
        else:
            print(f"   Analyzing task: {task.title}")
            analysis = service.analyze_task_assignment(task)
            
            if 'error' in analysis:
                print(f"   ⚠️  {analysis['error']}")
            else:
                top = analysis['top_recommendation']
                if top:
                    print(f"   ✅ Analysis Complete:")
                    print(f"      - Top recommendation: {top['username']}")
                    print(f"      - Overall score: {top['overall_score']:.1f}/100")
                    print(f"      - Skill match: {top['skill_match']:.1f}%")
                    print(f"      - Availability: {top['availability']:.1f}%")
                    print(f"      - Estimated hours: {top['estimated_hours']:.1f}h")
                    
                    if analysis['should_reassign']:
                        print(f"      - Recommendation: {analysis['reasoning']}")
                    else:
                        print(f"      - Current assignment is optimal")
                else:
                    print("   ⚠️  No candidates available for assignment")
        
    except Exception as e:
        print(f"   ❌ Error analyzing task: {e}")
        return False
    
    # 7. Test Suggestion Generation
    print("\n7. Testing Suggestion Generation...")
    try:
        suggestions = service.get_board_optimization_suggestions(board, limit=5)
        print(f"   ✅ Generated {len(suggestions)} suggestions")
        
        if suggestions:
            print(f"\n      Top Suggestions:")
            for i, s in enumerate(suggestions[:3], 1):
                print(f"      {i}. {s.task.title}")
                print(f"         From: {s.current_assignee.username if s.current_assignee else 'unassigned'}")
                print(f"         To: {s.suggested_assignee.username}")
                print(f"         Savings: {s.time_savings_percentage:.0f}%")
                print(f"         Confidence: {s.confidence_score:.0f}%")
                print(f"         Reason: {s.reasoning[:80]}...")
        else:
            print("      ℹ️  No optimization opportunities found (team is well balanced!)")
        
    except Exception as e:
        print(f"   ❌ Error generating suggestions: {e}")
        return False
    
    # 8. Test Workload Balancing
    print("\n8. Testing Workload Balancing...")
    try:
        result = balancer.balance_workload(board, target_utilization=75.0)
        print(f"   ✅ Balancing Result:")
        print(f"      - {result['message']}")
        
        if result.get('suggestions'):
            print(f"\n      Balancing Suggestions:")
            for i, s in enumerate(result['suggestions'][:3], 1):
                print(f"      {i}. {s['task']}")
                print(f"         {s['from']} → {s['to']}")
                print(f"         Reason: {s['reason']}")
        
    except Exception as e:
        print(f"   ❌ Error balancing workload: {e}")
        return False
    
    # 9. Test Skill Matching
    print("\n9. Testing Skill Matching...")
    try:
        member = board.members.first()
        if member:
            profile = service.get_or_create_profile(member)
            
            # Test different task descriptions
            test_tasks = [
                "Fix authentication bug in Django API",
                "Design new logo for homepage",
                "Write user documentation for feature"
            ]
            
            print(f"   Testing skill match for {member.username}:")
            for task_text in test_tasks:
                score = profile.calculate_skill_match(task_text)
                print(f"      - '{task_text[:40]}...': {score:.1f}% match")
        
    except Exception as e:
        print(f"   ❌ Error testing skill matching: {e}")
        return False
    
    # 10. Test Completion Time Prediction
    print("\n10. Testing Completion Time Prediction...")
    try:
        task = Task.objects.filter(column__board=board).first()
        if task and board.members.exists():
            member = board.members.first()
            profile = service.get_or_create_profile(member)
            
            predicted_hours = profile.predict_completion_time(task)
            predicted_date = timezone.now() + timedelta(hours=predicted_hours)
            
            print(f"   ✅ Prediction for {member.username}:")
            print(f"      - Task: {task.title}")
            print(f"      - Estimated time: {predicted_hours:.1f} hours")
            print(f"      - Expected completion: {predicted_date.strftime('%Y-%m-%d %H:%M')}")
        
    except Exception as e:
        print(f"   ❌ Error predicting completion time: {e}")
        return False
    
    # Final Summary
    print("\n" + "=" * 80)
    print("TEST SUMMARY")
    print("=" * 80)
    print("✅ All tests passed!")
    print("\nNext Steps:")
    print("1. Add widget to board_detail.html:")
    print("   {% include 'kanban/resource_leveling_widget.html' %}")
    print("\n2. Start using the feature:")
    print(f"   - Visit board: /boards/{board.id}/")
    print("   - View suggestions in the AI Resource Optimization widget")
    print("   - Accept beneficial suggestions with one click")
    print("\n3. Monitor performance:")
    print("   - Admin: /admin/kanban/userperformanceprofile/")
    print("   - Track suggestion acceptance rate and prediction accuracy")
    print("\n4. Optional - Enable background tasks:")
    print("   celery -A kanban_board worker -l info")
    print("   celery -A kanban_board beat -l info")
    print("\n" + "=" * 80)
    
    return True


if __name__ == '__main__':
    success = test_resource_leveling()
    if not success:
        print("\n⚠️  Some tests failed. Review the output above.")
        print("   Common issues:")
        print("   - Migrations not run: python manage.py migrate")
        print("   - No boards/tasks: Create test data first")
        print("   - No organization: Ensure users have organizations")
