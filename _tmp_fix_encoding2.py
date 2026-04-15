"""Fix double-encoded em dash across all templates and source files."""
import os

BASE = r'c:\Users\Avishek Paul\PrizmAI'

# The double-encoded em dash byte sequence (UTF-8 -> CP1252 -> UTF-8)
BROKEN = b'\xc3\xa2\xe2\x82\xac\xe2\x80\x9d'
# Correct UTF-8 em dash
FIXED = b'\xe2\x80\x94'  # U+2014

files_to_check = [
    r'templates\kanban\coach_dashboard.html',
    r'templates\kanban\forecast_dashboard.html',
    r'templates\kanban\retrospective_dashboard.html',
    r'templates\kanban\retrospective_list.html',
    r'templates\kanban\stakeholder_list.html',
    r'templates\kanban\gantt_chart.html',
    r'tests\test_kanban\test_onboarding.py',
]

total_fixed = 0
for rel in files_to_check:
    path = os.path.join(BASE, rel)
    if not os.path.exists(path):
        print(f"SKIP (not found): {rel}")
        continue
    
    with open(path, 'rb') as f:
        data = f.read()
    
    count = data.count(BROKEN)
    if count > 0:
        data = data.replace(BROKEN, FIXED)
        with open(path, 'wb') as f:
            f.write(data)
        print(f"FIXED {count} instance(s) in {rel}")
        total_fixed += count
    else:
        print(f"NO MATCH in {rel}")

print(f"\nTotal fixed: {total_fixed}")
