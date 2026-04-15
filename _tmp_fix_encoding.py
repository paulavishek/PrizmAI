"""Fix UTF-8 mojibake across templates: replace broken em dash with proper one."""
import os

BASE = r'c:\Users\Avishek Paul\PrizmAI'

# Files with the encoding issue
files_to_fix = [
    r'templates\kanban\coach_dashboard.html',
    r'templates\kanban\forecast_dashboard.html',
    r'templates\kanban\retrospective_dashboard.html',
    r'templates\kanban\retrospective_list.html',
    r'templates\kanban\stakeholder_list.html',
    r'templates\kanban\gantt_chart.html',
    r'tests\test_kanban\test_onboarding.py',
]

# The mojibake sequence for em dash
BROKEN = '\u00e2\u0080\u0094'   # â€"  (UTF-8 bytes of — decoded as latin-1)
FIXED = '\u2014'                # — (proper em dash)

for rel in files_to_fix:
    path = os.path.join(BASE, rel)
    if not os.path.exists(path):
        print(f"SKIP (not found): {rel}")
        continue
    
    with open(path, 'r', encoding='utf-8', errors='surrogateescape') as f:
        content = f.read()
    
    # Try multiple mojibake patterns
    count = 0
    for broken_pattern in [BROKEN, 'â€"', '\xe2\x80\x94']:
        if broken_pattern in content:
            c = content.count(broken_pattern)
            content = content.replace(broken_pattern, FIXED)
            count += c
    
    if count > 0:
        with open(path, 'w', encoding='utf-8') as f:
            f.write(content)
        print(f"FIXED {count} instance(s) in {rel}")
    else:
        print(f"NO MATCH in {rel}")
