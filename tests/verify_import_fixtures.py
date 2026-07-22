"""
Verify the Import Board adapters against real fixture files.

Runs every sample in tests/fixtures/import_samples/ through the SAME code path the
upload endpoint uses (AdapterFactory.detect_and_import) and reports, per format:
detected tool + confidence, success, errors/warnings, and import stats. It stops at
parse/transform (no DB writes) — the DB-write half is exercised by the UI upload test.

Run with:
    python manage.py shell < tests/verify_import_fixtures.py
"""
import os
import sys

# Allow running directly (python tests/verify_import_fixtures.py) by putting the
# repo root on sys.path, not just the tests/ dir.
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'kanban_board.settings')
import django
django.setup()

from kanban.utils.import_adapters import AdapterFactory, detect_format

FIXTURE_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                           'fixtures', 'import_samples')

# (filename, read_as_bytes, expected_source_tool, spot_check_fn)
CASES = []


def _read(filename, as_bytes):
    path = os.path.join(FIXTURE_DIR, filename)
    mode = 'rb' if as_bytes else 'r'
    kwargs = {} if as_bytes else {'encoding': 'utf-8'}
    with open(path, mode, **kwargs) as f:
        return f.read()


def _find(tasks, **match):
    for t in tasks:
        if all(str(t.get(k, '')).startswith(v) for k, v in match.items()):
            return t
    return None


def check_trello(result):
    notes = []
    # Archived list + archived card should be dropped: 3 columns, 4 active cards.
    assert len(result.columns_data) == 3, f"expected 3 columns, got {len(result.columns_data)}"
    assert len(result.tasks_data) == 4, f"expected 4 tasks (archived dropped), got {len(result.tasks_data)}"
    # Checklist -> progress (2 of 4 complete = 50%)
    landing = _find(result.tasks_data, title='Build landing page')
    assert landing and landing['progress'] == 50, f"checklist progress wrong: {landing and landing['progress']}"
    notes.append("archived list/card dropped; checklist->50% progress")
    # 200-char truncation
    longt = max(result.tasks_data, key=lambda t: len(t['title']))
    assert len(longt['title']) <= 200, f"title not truncated: {len(longt['title'])}"
    notes.append(f"long title truncated to {len(longt['title'])} chars")
    # Priority label -> urgent/high
    assert landing['priority'] == 'high', f"High label -> priority {landing['priority']}"
    notes.append("'High' label -> high priority")
    return notes


def check_jira(result):
    notes = []
    assert len(result.tasks_data) == 5, f"expected 5 issues, got {len(result.tasks_data)}"
    bug = _find(result.tasks_data, external_id='KAN-2')
    assert bug['priority'] == 'urgent', f"Highest -> {bug['priority']}"
    assert bug['progress'] == 50, f"In Progress -> {bug['progress']}"
    notes.append("Highest->urgent priority; In Progress->50%")
    # Issue Type added as a label
    assert 'Bug' in bug['label_names'], f"issue type not a label: {bug['label_names']}"
    notes.append("issue type 'Bug' added as label")
    # Assignee string is parsed from the CSV (DB-resolution happens later in the view)
    assert bug['assigned_to_username'] == 'jane@example.com', bug['assigned_to_username']
    notes.append("assignee email parsed onto task")
    return notes


def check_asana(result):
    notes = []
    assert len(result.tasks_data) == 5, f"expected 5 tasks, got {len(result.tasks_data)}"
    # Completed At set -> progress 100
    shipped = _find(result.tasks_data, external_id='1201000003')
    assert shipped['progress'] == 100, f"completed task progress {shipped['progress']}"
    notes.append("Completed At -> 100% progress")
    # 'Doing' section -> In Progress column
    cols = {c['name'] for c in result.columns_data}
    assert 'In Progress' in cols, f"'Doing' not mapped to In Progress; cols={cols}"
    notes.append("section 'Doing' -> 'In Progress' column")
    # multi-tag labels
    design = _find(result.tasks_data, external_id='1201000002')
    assert 'design' in design['label_names'] and 'ux' in design['label_names'], design['label_names']
    notes.append("multi-tag split into labels")
    return notes


def check_generic(result):
    notes = []
    assert len(result.tasks_data) == 5, f"expected 5 rows, got {len(result.tasks_data)}"
    t = _find(result.tasks_data, title='Refactor auth module')
    assert t['priority'] == 'medium', f"priority map {t['priority']}"
    assert 'backend' in t['label_names'] and 'tech-debt' in t['label_names'], t['label_names']
    notes.append("auto-mapped Title/Status/Priority/Labels; multi-label split")
    return notes


def check_monday(result):
    notes = []
    assert len(result.tasks_data) == 5, f"expected 5 tasks, got {len(result.tasks_data)}"
    cols = {c['name'] for c in result.columns_data}
    # Status values become columns
    for expected in ('Working on it', 'Stuck', 'Not Started', 'Done'):
        assert expected in cols, f"missing column {expected}; got {cols}"
    notes.append("Status values -> columns (Working on it/Stuck/Not Started/Done)")
    billing = _find(result.tasks_data, title='Launch billing v2')
    assert billing['progress'] == 50, f"Working on it -> {billing['progress']}"
    assert 'billing' in billing['label_names'], billing['label_names']
    notes.append("Working on it->50%; tags split into labels")
    return notes


CASES = [
    ('trello_board.json', False, 'Trello', check_trello),
    ('jira_export.csv', False, 'Jira', check_jira),
    ('asana_export.csv', False, 'Asana', check_asana),
    ('generic_tasks.csv', False, 'CSV', check_generic),
    ('monday_board.xlsx', True, 'Monday.com', check_monday),
]


def run():
    factory = AdapterFactory()
    failures = []

    print("=" * 68)
    print("  Import Board fixture verification")
    print("=" * 68)

    for filename, as_bytes, expected_tool, checker in CASES:
        print(f"\n--- {filename}  (expect: {expected_tool}) ---")
        try:
            data = _read(filename, as_bytes)
        except FileNotFoundError:
            print(f"  MISSING fixture: {filename}")
            failures.append(filename)
            continue

        fmt, adapter_cls, conf = detect_format(data, filename)
        print(f"  detected : {fmt}  (confidence {conf:.0%})")

        result = factory.detect_and_import(data, filename)
        print(f"  success  : {result.success}")
        print(f"  stats    : {result.stats}")
        print(f"  counts   : columns={len(result.columns_data)} "
              f"tasks={len(result.tasks_data)} labels={len(result.labels_data)}")
        if result.warnings:
            print(f"  warnings : {result.warnings}")
        if result.errors:
            print(f"  errors   : {result.errors}")

        try:
            assert fmt == expected_tool, f"detected '{fmt}', expected '{expected_tool}'"
            assert result.success, f"import failed: {result.errors}"
            for note in checker(result):
                print(f"  check OK : {note}")
            print("  RESULT   : PASS")
        except AssertionError as e:
            print(f"  RESULT   : FAIL -> {e}")
            failures.append(filename)
        except Exception as e:
            import traceback
            print(f"  RESULT   : ERROR -> {e}")
            traceback.print_exc()
            failures.append(filename)

    print("\n" + "=" * 68)
    if failures:
        print(f"  {len(failures)} FORMAT(S) FAILED: {', '.join(failures)}")
        print("=" * 68)
        sys.exit(1)
    print("  ALL 5 FORMATS PASSED")
    print("=" * 68)


run()
