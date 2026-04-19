import os, sys
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'kanban_board.settings')
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import django
django.setup()

from kanban.models import Task
from kanban.utils.task_prediction import update_task_prediction

t = Task.objects.get(id=10088)
pred = update_task_prediction(t)
if pred:
    for s in pred.get('similar_tasks', []):
        st = Task.objects.get(id=s['id'])
        comp = st.completed_at.date() if st.completed_at else None
        print(f"  {st.title}: dur={st.actual_duration_days}d start={st.start_date} completed={comp}")
    avg = pred['factors']['historical_avg_days']
    print(f"Avg: {avg}d")
    print(f"Task planned: {t.start_date} to {t.due_date}")
else:
    print("No prediction")
