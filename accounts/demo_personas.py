"""Canonical demo persona definitions — single source of truth.

When swapping demo personas in the future, update ``DEMO_PERSONAS`` below.
All demo seeders should import from this module rather than hard-coding
usernames or emails.

Narrative content (sprint notes, AI chat samples, etc.) still hard-codes
display names inline for readability. Those occurrences are not covered
by this module and will require a separate sweep on the next persona swap.
"""

# Keys ``lead``, ``frontend``, ``devops`` are STABLE across persona swaps so
# consuming code doesn't have to change — only the values move.
DEMO_PERSONAS = {
    'lead': {
        'username': 'priya.sharma',
        'email': 'priya.sharma@demo.prizmai.local',
        'first_name': 'Priya',
        'last_name': 'Sharma',
        'display_name': 'Priya Sharma',
        'role_label': 'Backend Lead',
        'org_role': 'admin',
        'skills': [
            {'name': 'Python', 'level': 'Expert'},
            {'name': 'Django', 'level': 'Expert'},
            {'name': 'REST APIs', 'level': 'Expert'},
            {'name': 'PostgreSQL', 'level': 'Advanced'},
            {'name': 'System Architecture', 'level': 'Advanced'},
        ],
        'weekly_capacity': 40,
    },
    'frontend': {
        'username': 'marcus.chen',
        'email': 'marcus.chen@demo.prizmai.local',
        'first_name': 'Marcus',
        'last_name': 'Chen',
        'display_name': 'Marcus Chen',
        'role_label': 'Frontend / UX',
        'org_role': 'member',
        'skills': [
            {'name': 'JavaScript', 'level': 'Expert'},
            {'name': 'React', 'level': 'Advanced'},
            {'name': 'CSS / Tailwind', 'level': 'Advanced'},
            {'name': 'UX Design', 'level': 'Advanced'},
            {'name': 'Accessibility (WCAG)', 'level': 'Intermediate'},
        ],
        'weekly_capacity': 40,
    },
    'devops': {
        'username': 'elena.vasquez',
        'email': 'elena.vasquez@demo.prizmai.local',
        'first_name': 'Elena',
        'last_name': 'Vasquez',
        'display_name': 'Elena Vasquez',
        'role_label': 'DevOps / QA',
        'org_role': 'member',
        'skills': [
            {'name': 'Docker / Containers', 'level': 'Expert'},
            {'name': 'CI/CD (GitHub Actions)', 'level': 'Expert'},
            {'name': 'Google Cloud Platform', 'level': 'Advanced'},
            {'name': 'Test Automation', 'level': 'Advanced'},
            {'name': 'Security Scanning', 'level': 'Intermediate'},
        ],
        'weekly_capacity': 40,
    },
}

# Convenience aliases for the three personas.
LEAD = DEMO_PERSONAS['lead']
FRONTEND = DEMO_PERSONAS['frontend']
DEVOPS = DEMO_PERSONAS['devops']

# Shared password for all demo personas — single source of truth.  Both the
# seeder (create_demo_organization) and the one-click "Login as <persona>"
# flow (accounts.views.quick_demo_login) must use this exact value; a mismatch
# here is what previously caused "Demo user not found or credentials invalid".
DEMO_PASSWORD = 'DemoUser@2026'

# Tuples for ``__in`` filters and membership checks.
DEMO_USERNAMES = tuple(p['username'] for p in DEMO_PERSONAS.values())
DEMO_EMAILS = tuple(p['email'] for p in DEMO_PERSONAS.values())

# Legacy persona identifiers — kept so cleanup paths in seeders can purge
# stale BoardMembership / WorkspaceMembership rows and deactivate accounts
# left over from a previous persona generation. Do not delete these tuples
# without first auditing every consumer of ``populate_all_demo_data._delete_legacy_demo_accounts``.
LEGACY_DEMO_USERNAMES = ('alex_chen_demo', 'sam_rivera_demo', 'jordan_taylor_demo')
LEGACY_DEMO_EMAILS = (
    'alex.chen@demo.prizmai.local',
    'sam.rivera@demo.prizmai.local',
    'jordan.taylor@demo.prizmai.local',
)
