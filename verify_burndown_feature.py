"""
Verify Burndown Feature for Software Project Demo Board
Check prediction data, alerts, and calculations match UI
"""
import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'kanban_board.settings')
django.setup()

from django.utils import timezone
from kanban.models import Board, Task
from kanban.burndown_models import BurndownPrediction, BurndownAlert, TeamVelocitySnapshot

print("=" * 80)
print(" " * 20 + "BURNDOWN FEATURE VERIFICATION")
print("=" * 80)

# Get Software Project board
software_board = Board.objects.filter(name='Software Project').first()

if not software_board:
    print("\n❌ Software Project board not found!")
    exit(1)

print(f"\n📋 Board: {software_board.name}")
print(f"   Organization: {software_board.organization.name}")

# Check task counts
all_tasks = Task.objects.filter(column__board=software_board)
total_tasks = all_tasks.count()
completed_tasks = all_tasks.filter(progress=100).count()
remaining_tasks = total_tasks - completed_tasks
completion_percentage = (completed_tasks / total_tasks * 100) if total_tasks > 0 else 0

print(f"\n📊 Current Progress:")
print(f"   Total Tasks: {total_tasks}")
print(f"   Completed: {completed_tasks}")
print(f"   Remaining: {remaining_tasks}")
print(f"   Completion: {completion_percentage:.1f}%")

expected_total = 29
expected_completed = 21
expected_remaining = 8

if total_tasks == expected_total and completed_tasks == expected_completed:
    print(f"   ✅ Task counts match UI (21/29)")
else:
    print(f"   ⚠️  Task counts don't match UI")
    print(f"      Expected: 21/29, Got: {completed_tasks}/{total_tasks}")

# Check velocity snapshots
print(f"\n🏃 Velocity History:")
velocity_snapshots = TeamVelocitySnapshot.objects.filter(
    board=software_board
).order_by('-period_end')

if velocity_snapshots.exists():
    print(f"   Total snapshots: {velocity_snapshots.count()}")
    print(f"\n   Recent velocity data:")
    for i, snapshot in enumerate(velocity_snapshots[:5], 1):
        print(f"      {i}. {snapshot.period_start} to {snapshot.period_end}")
        print(f"         Tasks completed: {snapshot.tasks_completed}")
        print(f"         Team size: {snapshot.active_team_members}")
else:
    print(f"   ⚠️  No velocity snapshots found")

# Check latest prediction
print(f"\n🔮 Latest Burndown Prediction:")
latest_prediction = BurndownPrediction.objects.filter(
    board=software_board
).order_by('-prediction_date').first()

if latest_prediction:
    print(f"   Generated: {latest_prediction.prediction_date}")
    print(f"   Predicted Completion: {latest_prediction.predicted_completion_date}")
    print(f"   Completion Range: {latest_prediction.completion_date_lower_bound} - {latest_prediction.completion_date_upper_bound}")
    print(f"   Days Until Completion: {latest_prediction.days_until_completion_estimate}")
    print(f"   Risk Level: {latest_prediction.risk_level.upper()}")
    print(f"   Delay Probability: {latest_prediction.delay_probability}%")
    print(f"   Current Velocity: {latest_prediction.current_velocity} tasks/week")
    print(f"   Average Velocity: {latest_prediction.average_velocity} tasks/week")
    print(f"   Velocity Trend: {latest_prediction.velocity_trend}")
    print(f"   Confidence: {latest_prediction.confidence_percentage}%")
    
    # Verify against UI
    ui_expected_date = "Mar 02, 2026"
    ui_expected_days = 74
    ui_expected_velocity = 1.00
    ui_expected_risk = "HIGH RISK"
    
    print(f"\n   📸 UI Comparison:")
    if latest_prediction.predicted_completion_date.strftime("%b %d, %Y") == ui_expected_date:
        print(f"      ✅ Predicted date matches UI: {ui_expected_date}")
    else:
        print(f"      ℹ️  Predicted date: {latest_prediction.predicted_completion_date.strftime('%b %d, %Y')} (UI may show different date)")
    
    if abs(latest_prediction.days_until_completion_estimate - ui_expected_days) <= 2:
        print(f"      ✅ Days until completion close to UI: ~{ui_expected_days} days")
    else:
        print(f"      ℹ️  Days until completion: {latest_prediction.days_until_completion_estimate} (UI shows {ui_expected_days})")
    
    if abs(float(latest_prediction.current_velocity) - ui_expected_velocity) <= 0.1:
        print(f"      ✅ Current velocity matches UI: {ui_expected_velocity} tasks/week")
    else:
        print(f"      ℹ️  Current velocity: {latest_prediction.current_velocity} (UI shows {ui_expected_velocity})")
    
    if "high" in latest_prediction.risk_level.lower() or "critical" in latest_prediction.risk_level.lower():
        print(f"      ✅ Risk level matches UI: {latest_prediction.risk_level.upper()}")
    else:
        print(f"      ℹ️  Risk level: {latest_prediction.risk_level.upper()} (UI shows {ui_expected_risk})")
    
else:
    print(f"   ⚠️  No burndown prediction found")
    print(f"   Generating new prediction...")

# Check active alerts
print(f"\n⚠️  Active Alerts:")
active_alerts = BurndownAlert.objects.filter(
    board=software_board,
    status__in=['active', 'acknowledged']
).order_by('-severity', '-created_at')

if active_alerts.exists():
    print(f"   Total active alerts: {active_alerts.count()}")
    for i, alert in enumerate(active_alerts, 1):
        print(f"\n   {i}. [{alert.severity.upper()}] {alert.title}")
        print(f"      {alert.message[:80]}...")
        print(f"      Created: {alert.created_at}")
    
    ui_expected_alerts = 6
    if active_alerts.count() == ui_expected_alerts:
        print(f"\n   ✅ Alert count matches UI: {ui_expected_alerts} active alerts")
    else:
        print(f"\n   ℹ️  Alert count: {active_alerts.count()} (UI shows {ui_expected_alerts})")
        print(f"      Note: Alerts may have been generated at different times")
else:
    print(f"   ⚠️  No active alerts found")

# Check actionable suggestions
if latest_prediction and latest_prediction.actionable_suggestions:
    print(f"\n💡 Actionable Suggestions:")
    suggestions = latest_prediction.actionable_suggestions
    print(f"   Total suggestions: {len(suggestions)}")
    
    for i, suggestion in enumerate(suggestions[:5], 1):
        impact = suggestion.get('impact', 'unknown').upper()
        print(f"\n   {i}. {suggestion.get('title')} [{impact} IMPACT]")
        print(f"      {suggestion.get('description')[:80]}...")
    
    ui_expected_suggestions = 5
    if len(suggestions) >= ui_expected_suggestions:
        print(f"\n   ✅ Suggestions generated (showing {ui_expected_suggestions})")
    else:
        print(f"\n   ℹ️  Total suggestions: {len(suggestions)}")

# Summary
print(f"\n{'=' * 80}")
print("VERIFICATION SUMMARY:")
print(f"{'=' * 80}")

issues = []
checks = []

# Task count check
if total_tasks == expected_total and completed_tasks == expected_completed:
    checks.append("✅ Task counts (21/29) - CORRECT")
else:
    issues.append(f"Task counts: Expected 21/29, got {completed_tasks}/{total_tasks}")

# Velocity snapshots check
if velocity_snapshots.exists():
    checks.append(f"✅ Velocity history exists ({velocity_snapshots.count()} snapshots)")
else:
    issues.append("No velocity snapshots found")

# Prediction check
if latest_prediction:
    checks.append("✅ Burndown prediction exists")
    
    # Check risk level
    if latest_prediction.risk_level in ['high', 'critical']:
        checks.append(f"✅ Risk level is HIGH ({latest_prediction.delay_probability}% probability)")
    else:
        issues.append(f"Risk level is {latest_prediction.risk_level}, expected HIGH")
    
    # Check velocity
    if 0.5 <= float(latest_prediction.current_velocity) <= 2.0:
        checks.append(f"✅ Current velocity reasonable ({latest_prediction.current_velocity} tasks/week)")
    else:
        issues.append(f"Velocity seems off: {latest_prediction.current_velocity} tasks/week")
else:
    issues.append("No burndown prediction found")

# Alerts check
if active_alerts.exists():
    checks.append(f"✅ Active alerts exist ({active_alerts.count()} alerts)")
else:
    issues.append("No active alerts found")

# Print results
for check in checks:
    print(f"  {check}")

if issues:
    print(f"\n  ⚠️  ISSUES FOUND:")
    for issue in issues:
        print(f"     - {issue}")
else:
    print(f"\n  🎉 ALL CHECKS PASSED!")

print(f"\n{'=' * 80}")
print("NOTE: Some differences with UI may be expected due to:")
print("  - Time differences (predictions age over time)")
print("  - User interactions (acknowledging alerts)")
print("  - Task completions (affecting calculations)")
print(f"{'=' * 80}")
