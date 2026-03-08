"""Thorough dashboard check: gap elimination + analytics collapse."""
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
body_start = html.find('<body')
body = html[body_start:]

print("=== STATUS ===")
print(f"Response: {r.status_code}")

# 1) Check no stray </div> between KPI strip and boards
kpi = body.find('<!-- /KPI Strip -->')
row2 = body.find('<!-- Row 2:')
between = body[kpi:row2]
opens_between = len(re.findall(r'<div[\s>]', between))
closes_between = between.count('</div>')
print(f"\n=== GAP CHECK (between KPI strip and Row 2) ===")
print(f"Div opens: {opens_between}, closes: {closes_between}, balance: {opens_between - closes_between}")
# Count visible block-level elements (not modals, not display:none)
# The section should only have modals (display:none) and the demo banner (inside {% if demo_mode %})
non_modal_divs = [m.start() for m in re.finditer(r'<div[^>]*>', between) if 'modal' not in between[m.start():m.start()+200] and 'display:none' not in between[m.start():m.start()+200]]
print(f"Non-modal visible divs between KPI and Row 2: {len(non_modal_divs)}")

# 2) Check the gap between decision-center and My Boards
dc_widget = body.find('id="decision-center-widget"')
my_boards = body.find('My Boards')
dc_to_boards = body[dc_widget:my_boards]
# Search for any block-level element that could produce visible height
gap_blocks = re.findall(r'<(?:div|section|article|p|h[1-6])[^>]*class="[^"]*"[^>]*>', dc_to_boards)
print(f"\n=== STRUCTURE: Decision Center to My Boards ===")
print(f"Distance in chars: {my_boards - dc_widget}")
# Show the major structural elements
for i, block in enumerate(gap_blocks[:15]):
    print(f"  [{i}] {block[:120]}")

# 3) Check analytics collapse state
analytics_tag_start = body.find('id="analyticsZone3"')
if analytics_tag_start > 0:
    # Get the full tag
    tag_start = body.rfind('<', 0, analytics_tag_start)
    tag_end = body.find('>', analytics_tag_start) + 1
    tag = body[tag_start:tag_end]
    print(f"\n=== ANALYTICS COLLAPSE STATE ===")
    print(f"Tag: {tag}")
    has_show = 'show' in tag.split('class="')[1].split('"')[0] if 'class="' in tag else False
    has_collapse = 'collapse' in tag
    print(f"Has 'collapse' class: {has_collapse}")
    print(f"Has 'show' class: {has_show}")
    print(f"Correctly collapsed: {has_collapse and not has_show}")
    
    # Check aria-expanded on the toggle
    toggle_search = body[analytics_tag_start-500:analytics_tag_start]
    aria_match = re.search(r'aria-expanded="(\w+)"', toggle_search)
    if aria_match:
        print(f"Toggle aria-expanded: {aria_match.group(1)}")

# 4) Check chart init deferral
print(f"\n=== CHART INIT ===")
print(f"'shown.bs.collapse' found: {'shown.bs.collapse' in html}")
print(f"'_chartsInitialised' found: {'_chartsInitialised' in html}")

# 5) First visible content after main-content
main_content = body.find('prizm-main-content">')
after_main = body[main_content+len('prizm-main-content">'):main_content+500]
# Strip whitespace-only lines and show first real content
lines = [l.strip() for l in after_main.split('\n') if l.strip() and not l.strip().startswith('<!--')]
print(f"\n=== FIRST CONTENT AFTER main-content ===")
for line in lines[:5]:
    print(f"  {line[:100]}")

print("\n=== OVERALL VERDICT ===")
gap_ok = opens_between == closes_between
analytics_ok = 'class="collapse"' in body[analytics_tag_start-50:analytics_tag_start+100] and 'show' not in body[analytics_tag_start-10:analytics_tag_start+100].split('class="')[0] if analytics_tag_start > 0 else False
# Re-check analytics properly
at = body.find('id="analyticsZone3"')
tag_area = body[at-100:at+50]
analytics_ok = 'class="collapse"' in tag_area and 'class="collapse show"' not in tag_area

if gap_ok and analytics_ok:
    print("ALL GOOD - Gap fixed, Analytics collapsed")
else:
    if not gap_ok:
        print("ISSUE: Gap still has div imbalance")
    if not analytics_ok:
        print("ISSUE: Analytics not properly collapsed")
