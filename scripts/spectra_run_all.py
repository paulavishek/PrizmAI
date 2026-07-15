"""
Spectra full-suite orchestrator (Q1–Q86) for the pre-ship final test.

The test bank requires every question to run in **My Workspace** (Demo Workspace
bypasses RBAC, so the isolation/aggregate tests would be meaningless there). The
three test users currently have their active_workspace set to the Demo workspace,
so this orchestrator:

  1. records each user's current active_workspace,
  2. switches each user to their own non-demo "My Workspace",
  3. runs the canonical harness (Q1–Q70) then the extension harness (Q71–Q86),
  4. restores each user's original active_workspace in a finally block.

Run: python manage.py shell -v0 -c "exec(open('scripts/spectra_run_all.py',encoding='utf-8').read())"
"""
import os
from django.contrib.auth import get_user_model

U = get_user_model()

# email -> that user's non-demo "My Workspace" id (where their test board lives)
MYWS = {
    'paul.biotech10@gmail.com': 12,   # testuser1
    'avip3310@gmail.com': 10,         # testuser2
    'avishekpaul1310@gmail.com': 13,  # testuser3
}

os.environ.pop('SPECTRA_ONLY', None)  # ensure a full run

originals = {}
for email, wsid in MYWS.items():
    u = U.objects.get(email=email)
    prof = u.profile
    originals[email] = prof.active_workspace_id
    prof.active_workspace_id = wsid
    prof.save(update_fields=['active_workspace'])
    print(f"set {email}: active_ws {originals[email]} -> {wsid}")

try:
    print("=== Running canonical harness (Q1-Q70) ===")
    exec(open('scripts/spectra_test_harness.py', encoding='utf-8').read())
    print("=== Running extension harness (Q71-Q86) ===")
    exec(open('scripts/spectra_test_harness_ext.py', encoding='utf-8').read())
finally:
    for email, orig in originals.items():
        u = U.objects.get(email=email)
        prof = u.profile
        prof.active_workspace_id = orig
        prof.save(update_fields=['active_workspace'])
        print(f"restored {email}: active_ws -> {orig}")

print("=== FULL SUITE COMPLETE ===")
