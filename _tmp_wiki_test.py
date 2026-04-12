import django, os
os.environ['DJANGO_SETTINGS_MODULE'] = 'kanban_board.settings'
django.setup()
from ai_assistant.utils.chatbot_service import TaskFlowChatbotService
from django.contrib.auth import get_user_model
from kanban.models import Board

user = get_user_model().objects.get(username='testuser1')
board = Board.objects.get(id=78)
svc = TaskFlowChatbotService(user=user, board=board, is_demo_mode=True)

queries = [
    'What does the wiki say about our deployment process?',
    'Search the documentation for API endpoints',
    'Summarize the project documentation',
]
for q in queries:
    wiki = svc._is_wiki_query(q)
    search = svc._is_search_query(q)
    print(f'Q: {q}')
    print(f'  is_wiki_query={wiki}, is_search_query={search}')
    ctx = svc._get_wiki_context(q)
    status = "OK" if ctx else "None"
    chars = len(ctx) if ctx else 0
    print(f'  wiki_context: {status} ({chars} chars)')
    if ctx:
        for line in ctx.split('\n'):
            if '📄' in line:
                print(f'    {line.strip()}')
    print()

# Also test doc summary
doc = svc._get_documentation_summary_context()
print(f'Doc summary: {"OK" if doc else "None"} ({len(doc) if doc else 0} chars)')
