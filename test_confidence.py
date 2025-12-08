from kanban.resource_leveling import ResourceLevelingService
from kanban.models import Board, Task
from django.contrib.auth.models import User

board = Board.objects.get(name='Software Project')
service = ResourceLevelingService(board.organization)

# Get Jane and Bob
jane = User.objects.get(username='jane_smith')
bob = User.objects.get(username='bob_martinez')

# Get a task
task = Task.objects.filter(column__board=board, title__icontains='Create onboarding').first()
task_text = f'{task.title} {task.description or ""}'

# Get profiles
jane_profile = service.get_or_create_profile(jane)
bob_profile = service.get_or_create_profile(bob)

# Analyze candidates
jane_analysis = service._analyze_candidate(task, task_text, jane_profile)
bob_analysis = service._analyze_candidate(task, task_text, bob_profile)

print('Jane Smith:')
print(f'  Overall: {jane_analysis["overall_score"]}')
print(f'  Skill: {jane_analysis["skill_match"]}')
print(f'  Availability: {jane_analysis["availability"]}')
print(f'  Velocity: {jane_analysis["velocity"]}')
print(f'  Reliability: {jane_analysis["reliability"]}')
print(f'  Quality: {jane_analysis["quality"]}')

print('\nBob Martinez:')
print(f'  Overall: {bob_analysis["overall_score"]}')
print(f'  Skill: {bob_analysis["skill_match"]}')
print(f'  Availability: {bob_analysis["availability"]}')
print(f'  Velocity: {bob_analysis["velocity"]}')
print(f'  Reliability: {bob_analysis["reliability"]}')
print(f'  Quality: {bob_analysis["quality"]}')

print('\nSkill Keywords:')
print(f'  Jane: {list(jane_profile.skill_keywords.keys())[:10]}')
print(f'  Bob: {list(bob_profile.skill_keywords.keys())[:10]}')

print(f'\nTask text: "{task_text}"')
print(f'\nManual skill match calculation:')
print(f'  Jane: {jane_profile.calculate_skill_match(task_text)}')
print(f'  Bob: {bob_profile.calculate_skill_match(task_text)}')
