"""Verify dashboard fixes: no gap, analytics collapsed."""
import os, django, re
os.environ['DJANGO_SETTINGS_MODULE'] = 'kanban_board.settings'
django.setup()

from django.test import Client
from django.contrib.auth import get_user_model

User = get_user_model()
user = User.objects.filter(username='testuser2').first()
c = Client()
c.force_login(user)
r = c.get('/dashboard/')
html = r.content.decode()

errors = []

# Test 1: No stray </div> between KPI strip and Row 2
kpi_end = html.find('<!-- /KPI Strip -->')
row2_start = html.find('<!-- Row 2:')
if kpi_end > 0 and row2_start > 0:
    section = html[kpi_end:row2_start]
    opens = section.count('<div')
    closes = section.count('</div>')
    if opens != closes:
        errors.append(f"FAIL: Div imbalance between KPI and Row 2: {opens} opens, {closes} closes")
    else:
        print("PASS: Div balance between KPI and Row 2 is correct")

# Test 2: Overall div balance in main-content
main_open = html.find('prizm-main-content">')
main_close = html.find('</main>')
if main_open > 0 and main_close > 0:
    main_section = html[main_open:main_close]
    opens = main_section.count('<div')
    closes = main_section.count('</div>')
    if opens != closes:
        errors.append(f"FAIL: Div imbalance in main-content: {opens} opens, {closes} closes, diff={opens-closes}")
    else:
        print(f"PASS: Div balance in main-content is correct ({opens} each)")

# Test 3: analyticsZone3 has class="collapse" without "show"
analytics_match = re.search(r'<div\s+class="([^"]*)"[^>]*id="analyticsZone3"', html)
if not analytics_match:
    analytics_match = re.search(r'id="analyticsZone3"[^>]*class="([^"]*)"', html)
if analytics_match:
    classes = analytics_match.group(1)
    if 'show' in classes.split():
        errors.append(f"FAIL: analyticsZone3 has 'show' class: {classes}")
    elif 'collapse' in classes.split():
        print(f"PASS: analyticsZone3 has class='{classes}' (collapsed by default)")
    else:
        errors.append(f"FAIL: analyticsZone3 missing 'collapse' class: {classes}")
else:
    errors.append("FAIL: analyticsZone3 element not found in HTML")

# Test 4: No style="display:block" or similar on analyticsZone3
zone3_start = html.find('id="analyticsZone3"')
if zone3_start > 0:
    zone3_tag = html[zone3_start-200:zone3_start+200]
    if 'display:block' in zone3_tag or 'display: block' in zone3_tag:
        errors.append("FAIL: analyticsZone3 has inline display:block")
    else:
        print("PASS: analyticsZone3 has no inline display:block override")

# Test 5: Charts init is deferred (not on DOMContentLoaded directly)
if 'shown.bs.collapse' in html:
    print("PASS: Chart initialization is deferred to collapse shown event")
else:
    errors.append("FAIL: Chart init not properly deferred to collapse event")

# Test 6: prizm-main-wrapper not prematurely closed
wrapper_open = html.find('<div class="prizm-main-wrapper">')
wrapper_close = html.find('<!-- /prizm-main-wrapper -->')
if wrapper_open > 0 and wrapper_close > 0:
    wrapper_section = html[wrapper_open:wrapper_close]
    opens = wrapper_section.count('<div')
    closes = wrapper_section.count('</div>')
    if opens != closes:
        errors.append(f"FAIL: prizm-main-wrapper div imbalance: {opens} opens, {closes} closes")
    else:
        print(f"PASS: prizm-main-wrapper div balance correct")

# Test 7: All major sections inside main-content
main_pos = html.find('prizm-main-content')
main_close_pos = html.find('</main>')
sections = {
    'decision-center-widget': html.find('decision-center-widget'),
    'kpi-strip': html.find('kpi-strip'),
    'board-cards-section': html.find('board-cards-section'),
    'daily-briefing-card': html.find('daily-briefing-card'),
    'mission-overview-card': html.find('mission-overview-card'),
    'analyticsZone3': html.find('analyticsZone3'),
}
all_inside = True
for name, pos in sections.items():
    if pos < main_pos or pos > main_close_pos:
        errors.append(f"FAIL: {name} is OUTSIDE main-content (pos={pos}, main={main_pos}-{main_close_pos})")
        all_inside = False
if all_inside:
    print("PASS: All major sections are inside main-content")

print()
if errors:
    for e in errors:
        print(e)
    print(f"\nFAILED: {len(errors)} error(s)")
else:
    print("ALL TESTS PASSED")
