"""Check demo data existence for board 78, user 48."""
import os, sys
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'kanban_board.settings')
import django
django.setup()

results = []

# 1. TimeEntry
try:
    from kanban.budget_models import TimeEntry
    qs = TimeEntry.objects.filter(task__column__board__id=78)
    c = qs.count()
    sample = list(qs.values('id', 'task__title', 'hours_spent', 'work_date')[:2]) if c else []
    results.append(('Time Tracking', 'kanban.budget_models.TimeEntry', c, sample))
except Exception as e:
    results.append(('Time Tracking', 'kanban.budget_models.TimeEntry', 'ERR', str(e)[:150]))

# 2. CalendarEvent
try:
    from kanban.models import CalendarEvent
    qs = CalendarEvent.objects.filter(board_id=78)
    c = qs.count()
    sample = list(qs.values('id', 'title', 'start_date')[:2]) if c else []
    results.append(('Calendar Events', 'kanban.models.CalendarEvent', c, sample))
except Exception as e:
    results.append(('Calendar Events', 'kanban.models.CalendarEvent', 'ERR', str(e)[:150]))

# 3a. ProjectBudget
try:
    from kanban.budget_models import ProjectBudget
    qs = ProjectBudget.objects.filter(board_id=78)
    c = qs.count()
    sample = list(qs.values('id', 'total_budget', 'currency')[:2]) if c else []
    results.append(('Project Budget', 'kanban.budget_models.ProjectBudget', c, sample))
except Exception as e:
    results.append(('Project Budget', 'kanban.budget_models.ProjectBudget', 'ERR', str(e)[:150]))

# 3b. TaskCost
try:
    from kanban.budget_models import TaskCost
    qs = TaskCost.objects.filter(task__column__board__id=78)
    c = qs.count()
    sample = list(qs.values('id', 'task__title', 'estimated_cost', 'actual_cost')[:2]) if c else []
    results.append(('Task Cost', 'kanban.budget_models.TaskCost', c, sample))
except Exception as e:
    results.append(('Task Cost', 'kanban.budget_models.TaskCost', 'ERR', str(e)[:150]))

# 4a. CommitmentProtocol
try:
    from kanban.commitment_models import CommitmentProtocol
    qs = CommitmentProtocol.objects.filter(board_id=78)
    c = qs.count()
    sample = list(qs.values('id', 'name', 'status')[:2]) if c else []
    results.append(('Commitment Protocol', 'kanban.commitment_models.CommitmentProtocol', c, sample))
except Exception as e:
    results.append(('Commitment Protocol', 'commitment_models.CommitmentProtocol', 'ERR', str(e)[:150]))

# 4b. ConfidenceSignal
try:
    from kanban.commitment_models import ConfidenceSignal
    qs = ConfidenceSignal.objects.filter(protocol__board_id=78)
    c = qs.count()
    sample = list(qs.values('id', 'confidence_level', 'note')[:2]) if c else []
    results.append(('Confidence Signal', 'kanban.commitment_models.ConfidenceSignal', c, sample))
except Exception as e:
    results.append(('Confidence Signal', 'commitment_models.ConfidenceSignal', 'ERR', str(e)[:150]))

# 5. BoardAutomation
try:
    from kanban.automation_models import BoardAutomation
    qs = BoardAutomation.objects.filter(board_id=78)
    c = qs.count()
    sample = list(qs.values('id', 'name', 'trigger_type', 'is_active')[:2]) if c else []
    results.append(('Automations', 'kanban.automation_models.BoardAutomation', c, sample))
except Exception as e:
    results.append(('Automations', 'automation_models.BoardAutomation', 'ERR', str(e)[:150]))

# 6. ProjectRetrospective
try:
    from kanban.retrospective_models import ProjectRetrospective
    qs = ProjectRetrospective.objects.filter(board_id=78)
    c = qs.count()
    sample = list(qs.values('id', 'title', 'status')[:2]) if c else []
    results.append(('Retrospectives', 'kanban.retrospective_models.ProjectRetrospective', c, sample))
except Exception as e:
    results.append(('Retrospectives', 'retrospective_models.ProjectRetrospective', 'ERR', str(e)[:150]))

# 7. DecisionItem
try:
    from decision_center.models import DecisionItem
    qs = DecisionItem.objects.filter(board_id=78)
    c = qs.count()
    sample = list(qs.values('id', 'title', 'status', 'decision_type')[:2]) if c else []
    results.append(('Decision Items', 'decision_center.models.DecisionItem', c, sample))
except Exception as e:
    results.append(('Decision Items', 'decision_center.models.DecisionItem', 'ERR', str(e)[:150]))

# 8. WikiPage
try:
    from wiki.models import WikiPage
    qs = WikiPage.objects.filter(organization_id=1)  # testuser1's org
    c = qs.count()
    sample = list(qs.values('id', 'title', 'is_published')[:2]) if c else []
    results.append(('Wiki Pages', 'wiki.models.WikiPage', c, sample))
except Exception as e:
    results.append(('Wiki Pages', 'wiki.models.WikiPage', 'ERR', str(e)[:150]))

# 9. CemeteryEntry
try:
    from exit_protocol.models import CemeteryEntry
    total = CemeteryEntry.objects.count()
    qs = CemeteryEntry.objects.filter(board_id=78)
    c = qs.count()
    sample = [{'total_all_boards': total}]
    if c:
        sample += list(qs.values('id', 'title', 'exit_type')[:2])
    results.append(('Cemetery/Exit', 'exit_protocol.models.CemeteryEntry', c, sample))
except Exception as e:
    results.append(('Cemetery/Exit', 'exit_protocol.models.CemeteryEntry', 'ERR', str(e)[:150]))

# 10a. Notification
try:
    from messaging.models import Notification
    qs = Notification.objects.filter(recipient_id=48)
    c = qs.count()
    sample = list(qs.values('id', 'notification_type', 'is_read', 'text')[:2]) if c else []
    results.append(('Notifications', 'messaging.models.Notification', c, sample))
except Exception as e:
    results.append(('Notifications', 'messaging.models.Notification', 'ERR', str(e)[:150]))

# 10b. ChatMessage
try:
    from messaging.models import ChatMessage
    qs = ChatMessage.objects.filter(author_id=48)
    c = qs.count()
    sample = list(qs.values('id', 'content', 'created_at')[:2]) if c else []
    results.append(('Chat Messages', 'messaging.models.ChatMessage', c, sample))
except Exception as e:
    results.append(('Chat Messages', 'messaging.models.ChatMessage', 'ERR', str(e)[:150]))

# Print results
print()
print('=' * 110)
fmt = '{:<22} {:<50} {:<8} {}'
print(fmt.format('Feature', 'Model', 'Count', 'Has Data'))
print('-' * 110)
for feat, model, count, sample in results:
    if count == 'ERR':
        has = 'ERROR'
    elif isinstance(count, int) and count > 0:
        has = 'YES'
    else:
        has = 'NO'
    print(fmt.format(feat, model, str(count), has))
print('=' * 110)

print('\n--- SAMPLE DATA ---')
for feat, model, count, sample in results:
    if sample and count != 'ERR' and (isinstance(count, int) and count > 0 or isinstance(sample, list) and sample):
        print(f'\n[{feat}] ({count} records):')
        if isinstance(sample, list):
            for s in sample[:3]:
                print(f'  {s}')
        else:
            print(f'  {str(sample)[:200]}')
    elif count == 'ERR':
        print(f'\n[{feat}] ERROR: {sample}')
