"""Debug script to analyze the dashboard HTML structure."""
import os, django
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

# Check 1: Find all occurrences of 'collapse' class (not 'collapse show')
print("=== COLLAPSE CLASSES ===")
import re
for m in re.finditer(r'class="collapse[^"]*"', html):
    start = max(0, m.start() - 80)
    print(f"  pos {m.start()}: ...{html[start:m.end()+30]}...")
    print()

# Check 2: Count open/close divs between prizm-main-content and Row 2
print("=== DIV BALANCE ===")
main_start = html.find('prizm-main-content')
row2_start = html.find('Row 2:')
section = html[main_start:row2_start]
opens = section.count('<div')
closes = section.count('</div>')
print(f"Between main-content and Row 2: {opens} opens, {closes} closes, balance={opens-closes}")

# Check 3: Show the exact area around the stray </div>
kpi_end = html.find('</div>\n\n</div>\n<!-- /KPI Strip -->')
if kpi_end > 0:
    print(f"\n=== STRAY DIV AREA (pos {kpi_end}) ===")
    print(repr(html[kpi_end:kpi_end+100]))
else:
    print("\nStray div pattern not found, searching alternative...")
    kpi_comment = html.find('<!-- /KPI Strip -->')
    if kpi_comment > 0:
        print(f"KPI Strip comment at pos {kpi_comment}")
        print(repr(html[kpi_comment-150:kpi_comment+50]))

# Check 4: Is analyticsZone3 inside or outside prizm-main-wrapper?
wrapper_close = html.find('<!-- /prizm-main-wrapper -->')
analytics_pos = html.find('analyticsZone3')
print(f"\n=== POSITIONS ===")
print(f"prizm-main-wrapper close: {wrapper_close}")
print(f"analyticsZone3: {analytics_pos}")
print(f"Analytics inside wrapper: {analytics_pos < wrapper_close if wrapper_close > 0 else 'wrapper close not found'}")

# Check 5: Look for Bootstrap CSS/JS that controls collapse
for pattern in ['bootstrap.min.css', 'bootstrap.min.js', 'bootstrap.bundle']:
    pos = html.find(pattern)
    print(f"  {pattern}: {'found at ' + str(pos) if pos > 0 else 'NOT FOUND'}")
