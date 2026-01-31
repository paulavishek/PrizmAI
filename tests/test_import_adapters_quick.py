"""
Quick test script for import adapters
Run with: python manage.py shell < tests/test_import_adapters_quick.py
"""
import os
import sys

# Setup Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'kanban_board.settings')

import django
django.setup()

from kanban.utils.import_adapters import (
    AdapterFactory, 
    detect_format,
    TrelloAdapter,
    JiraAdapter,
    AsanaAdapter,
    CSVAdapter,
    PrizmAIAdapter
)


def test_format_detection():
    """Test auto-detection of various formats"""
    print("\n=== Testing Format Detection ===\n")
    
    # Test Trello JSON
    trello_sample = '''
    {
        "name": "My Trello Board",
        "lists": [{"id": "1", "name": "To Do", "closed": false}],
        "cards": [{"idList": "1", "name": "Task 1", "idBoard": "123"}],
        "url": "https://trello.com/b/abc123"
    }
    '''
    fmt, adapter, conf = detect_format(trello_sample)
    print(f"✓ Trello JSON: Detected as '{fmt}' with {conf:.0%} confidence")
    assert fmt == "Trello", f"Expected Trello, got {fmt}"
    
    # Test Jira CSV
    jira_csv = "Issue Key,Summary,Status,Priority,Assignee\nPROJ-1,Fix bug,In Progress,High,john"
    fmt, adapter, conf = detect_format(jira_csv)
    print(f"✓ Jira CSV: Detected as '{fmt}' with {conf:.0%} confidence")
    assert fmt == "Jira", f"Expected Jira, got {fmt}"
    
    # Test Asana CSV
    asana_csv = "Task ID,Name,Section/Column,Assignee,Due Date\n123,My Task,To Do,jane,2026-02-01"
    fmt, adapter, conf = detect_format(asana_csv)
    print(f"✓ Asana CSV: Detected as '{fmt}' with {conf:.0%} confidence")
    assert fmt == "Asana", f"Expected Asana, got {fmt}"
    
    # Test PrizmAI native
    prizmAI_sample = '''
    {
        "board": {"name": "My Board", "description": "Test", "num_phases": 3},
        "columns": [{"name": "To Do", "position": 0, "tasks": []}]
    }
    '''
    fmt, adapter, conf = detect_format(prizmAI_sample)
    print(f"✓ PrizmAI JSON: Detected as '{fmt}' with {conf:.0%} confidence")
    assert fmt == "PrizmAI", f"Expected PrizmAI, got {fmt}"
    
    # Test generic CSV (should fallback to CSV adapter)
    generic_csv = "Title,Description,Status\nTask 1,Do something,To Do"
    fmt, adapter, conf = detect_format(generic_csv)
    print(f"✓ Generic CSV: Detected as '{fmt}' with {conf:.0%} confidence")
    
    print("\n✓ All format detection tests passed!")


def test_trello_import():
    """Test Trello adapter transformation"""
    print("\n=== Testing Trello Import ===\n")
    
    trello_data = {
        "name": "Test Trello Board",
        "desc": "A test board",
        "url": "https://trello.com/b/test",
        "lists": [
            {"id": "list1", "name": "To Do", "pos": 0, "closed": False},
            {"id": "list2", "name": "In Progress", "pos": 1, "closed": False},
            {"id": "list3", "name": "Done", "pos": 2, "closed": False},
        ],
        "cards": [
            {
                "id": "card1",
                "name": "Implement feature",
                "desc": "Add new functionality",
                "idList": "list1",
                "pos": 0,
                "due": "2026-02-15T00:00:00.000Z",
                "idLabels": ["label1"],
                "idMembers": ["member1"],
                "closed": False,
            },
            {
                "id": "card2", 
                "name": "Fix bug",
                "desc": "Critical bug fix",
                "idList": "list2",
                "pos": 0,
                "idLabels": ["label2"],
                "closed": False,
            }
        ],
        "labels": [
            {"id": "label1", "name": "Feature", "color": "green"},
            {"id": "label2", "name": "Bug", "color": "red"},
        ],
        "members": [
            {"id": "member1", "username": "johndoe", "fullName": "John Doe"},
        ],
        "checklists": [],
        "actions": [],
    }
    
    adapter = TrelloAdapter()
    result = adapter.import_data(trello_data)
    
    assert result.success, f"Import failed: {result.errors}"
    assert result.board_data['name'] == "Test Trello Board"
    assert len(result.columns_data) == 3
    assert len(result.tasks_data) == 2
    assert len(result.labels_data) == 2
    
    print(f"✓ Board: {result.board_data['name']}")
    print(f"✓ Columns: {[c['name'] for c in result.columns_data]}")
    print(f"✓ Tasks: {len(result.tasks_data)} imported")
    print(f"✓ Labels: {[l['name'] for l in result.labels_data]}")
    print(f"✓ Stats: {result.stats}")
    
    print("\n✓ Trello import test passed!")


def test_csv_import():
    """Test CSV adapter with auto-mapping"""
    print("\n=== Testing CSV Import ===\n")
    
    csv_data = """Title,Description,Status,Priority,Assignee
Task 1,First task description,To Do,High,john
Task 2,Second task,In Progress,Medium,jane
Task 3,Third task,Done,Low,"""
    
    adapter = CSVAdapter()
    result = adapter.import_data(csv_data, "tasks.csv")
    
    assert result.success, f"Import failed: {result.errors}"
    assert len(result.tasks_data) == 3
    
    print(f"✓ Detected mappings: {result.field_mappings}")
    print(f"✓ Tasks imported: {len(result.tasks_data)}")
    print(f"✓ Columns created: {[c['name'] for c in result.columns_data]}")
    
    # Check field mapping worked
    task1 = result.tasks_data[0]
    assert task1['title'] == 'Task 1'
    assert task1['priority'] == 'high'
    
    print("\n✓ CSV import test passed!")


def test_factory():
    """Test AdapterFactory"""
    print("\n=== Testing Adapter Factory ===\n")
    
    factory = AdapterFactory()
    
    # List available adapters
    adapters = factory.get_available_adapters()
    print(f"✓ Available adapters: {[a['display_name'] for a in adapters]}")
    
    # Test preview
    csv_data = "Name,Status\nTask 1,To Do"
    preview = factory.preview_import(csv_data, "test.csv")
    print(f"✓ Preview result: {preview}")
    
    print("\n✓ Factory tests passed!")


if __name__ == "__main__":
    print("=" * 50)
    print("  Import Adapters Test Suite")
    print("=" * 50)
    
    try:
        test_format_detection()
        test_trello_import()
        test_csv_import()
        test_factory()
        
        print("\n" + "=" * 50)
        print("  ALL TESTS PASSED ✓")
        print("=" * 50)
    except AssertionError as e:
        print(f"\n✗ Test failed: {e}")
        sys.exit(1)
    except Exception as e:
        print(f"\n✗ Unexpected error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
