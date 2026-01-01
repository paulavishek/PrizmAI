"""
Add realistic dependencies to demo tasks for better Gantt chart display
"""
import os
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'kanban_board.settings')
import django
django.setup()

from kanban.models import Task, Board, Organization
from django.utils import timezone
from datetime import timedelta

org = Organization.objects.get(name='Demo - Acme Corporation')
boards = Board.objects.filter(organization=org)

def add_dependencies_for_board(board_name, dependency_map):
    """
    dependency_map: dict of {task_title_substring: [dependency_title_substring, ...]}
    """
    board = Board.objects.get(name=board_name, organization=org)
    tasks = {t.title: t for t in Task.objects.filter(column__board=board)}
    
    count = 0
    for task_substr, dep_substrs in dependency_map.items():
        # Find the task
        task = None
        for title, t in tasks.items():
            if task_substr.lower() in title.lower():
                task = t
                break
        
        if not task:
            print(f'  Task not found: {task_substr}')
            continue
        
        # Find and add dependencies
        for dep_substr in dep_substrs:
            dep_task = None
            for title, t in tasks.items():
                if dep_substr.lower() in title.lower():
                    dep_task = t
                    break
            
            if dep_task and dep_task.id != task.id:
                # Make sure dependency starts before the task
                if dep_task.due_date and task.start_date:
                    dep_due = dep_task.due_date.date() if hasattr(dep_task.due_date, 'date') else dep_task.due_date
                    task_start = task.start_date if isinstance(task.start_date, type(dep_due)) else task.start_date
                    if dep_due > task_start:
                        # Adjust the task start date to be after the dependency
                        task.start_date = dep_due + timedelta(days=1)
                        task_due = task.due_date.date() if hasattr(task.due_date, 'date') else task.due_date
                        if task.due_date and task.start_date > task_due:
                            task.due_date = timezone.now() + timedelta(days=14)
                        task.save()
                
                task.dependencies.add(dep_task)
                count += 1
                print(f'  {task.title[:35]} <- {dep_task.title[:35]}')
    
    return count

print('\n=== Adding Dependencies to Software Development ===')
sw_deps = {
    'Build REST API endpoints': ['Design database schema', 'authentication system'],
    'Create responsive dashboard': ['Build REST API endpoints'],
    'file upload functionality': ['Build REST API endpoints'],
    'Add email notification': ['Build REST API endpoints'],
    'Build search functionality': ['Design database schema'],
    'Implement API rate limiting': ['Build REST API endpoints'],
    'Build admin dashboard': ['Create responsive dashboard'],
    'Create mobile PWA': ['Create responsive dashboard'],
    'dark mode theme': ['Create responsive dashboard'],
    'user onboarding flow': ['authentication system'],
    'integration with Slack': ['Add webhook support'],
    'analytics dashboard': ['Create responsive dashboard'],
    'activity feed': ['real-time notifications'],
    'bulk actions for task': ['Build REST API endpoints'],
    'advanced filtering': ['Build REST API endpoints'],
    'calendar view for tasks': ['Create responsive dashboard'],
    'comment system with mentions': ['real-time notifications'],
    'audit log': ['Build REST API endpoints'],
    'role-based access control': ['authentication system'],
    'keyboard shortcuts': ['Create responsive dashboard'],
    'template system': ['Build REST API endpoints'],
    'API documentation': ['Build REST API endpoints'],
    'time tracking': ['Build REST API endpoints'],
    'team workload': ['analytics dashboard'],
    'dependency management': ['Build REST API endpoints'],
    'Set up CI/CD pipeline': ['automated backup system'],
    'Configure production': ['Set up CI/CD pipeline'],
    'error tracking with Sentry': ['Configure production'],
    'project documentation': ['API documentation'],
    'monitoring and alerts': ['Configure production'],
}
sw_count = add_dependencies_for_board('Software Development', sw_deps)
print(f'\nAdded {sw_count} dependencies to Software Development')

print('\n=== Adding Dependencies to Marketing Campaign ===')
mk_deps = {
    'Blog post series': ['content calendar planning'],
    'Email newsletter automation': ['email nurture sequence'],
    'Social media contest': ['Design social media graphics'],
    'Partner with industry influencers': ['Influencer outreach list'],
    'Create case studies': ['Customer testimonial'],
    'Webinar series planning': ['content calendar planning'],
    'Redesign landing pages': ['Landing page wireframes'],
    'Launch referral program': ['partnership agreement'],
    'product comparison guides': ['Competitor analysis'],
    'SEO optimization': ['Optimize SEO meta tags'],
    'Q2 content calendar': ['Target audience persona'],
    'Brand guidelines update': ['Deploy new brand identity'],
    'Video production storyboard': ['Film customer testimonial'],
    'Social media ad creative': ['Design social media graphics'],
    'product launch announcement': ['content calendar planning'],
    'Google Ads campaign': ['Marketing budget allocation'],
    'Update website homepage': ['Redesign landing pages'],
    'Build landing page for webinar': ['Landing page wireframes'],
}
mk_count = add_dependencies_for_board('Marketing Campaign', mk_deps)
print(f'\nAdded {mk_count} dependencies to Marketing Campaign')

print('\n=== Adding Dependencies to Bug Tracking ===')
bug_deps = {
    'Memory leak in dashboard': ['Dashboard loading forever'],
    'Email notifications not sent': ['password reset email'],
    'Date picker shows wrong timezone': ['timezone conversion in reports'],
    'Drag and drop broken in Firefox': ['Charts not rendering in IE11'],
    'Database deadlock on task updates': ['slow dashboard query'],
    'Pagination broken on large datasets': ['Database deadlock'],
    'Auto-save not working': ['Real-time updates delayed'],
    'Fix broken image links': ['Avatar images not loading'],
    'Fix SQL injection vulnerability': ['API returns 500 error'],
}
bug_count = add_dependencies_for_board('Bug Tracking', bug_deps)
print(f'\nAdded {bug_count} dependencies to Bug Tracking')

# Verify total dependencies
print('\n=== Verification ===')
for board in boards:
    deps_count = 0
    for t in Task.objects.filter(column__board=board):
        deps_count += t.dependencies.count()
    print(f'{board.name}: {deps_count} dependencies')

print('\n✅ Done!')
