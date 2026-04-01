"""
Seed Feature Guide entries for the 9 AI features that have dedicated pages.
Idempotent — safe to run multiple times (update_or_create on feature_key).
Content is adapted from the README's plain-English feature descriptions.
"""
from django.core.management.base import BaseCommand
from kanban.feature_guide_models import FeatureGuide


FEATURE_GUIDES = [
    {
        'feature_key': 'prizmbrief',
        'feature_name': 'PrizmBrief',
        'order': 10,
        'brief_description': (
            'Generate structured, audience-aware presentation content '
            'directly from your live board data. Answer 3 quick questions '
            '— who is the audience, what is the purpose, and how much '
            'detail — and PrizmBrief pulls real tasks, progress, and '
            'metrics into slide-ready content you can paste into any '
            'presentation tool.'
        ),
        'detailed_description': (
            '<h6>How it works</h6>'
            '<ol>'
            '<li><strong>Pick your audience</strong> — Choose who the '
            'presentation is for: a client, executive, or internal team. '
            'PrizmBrief adjusts the language and detail level automatically.</li>'
            '<li><strong>Set the purpose</strong> — Status update, project '
            'kickoff, risk review, or milestone celebration. Each purpose '
            'changes which data gets pulled from the board.</li>'
            '<li><strong>Generate</strong> — PrizmBrief reads your live '
            'board data (tasks, progress, blockers, metrics) and produces '
            'structured slide content with titles, key points, and '
            'supporting data for each slide.</li>'
            '</ol>'
            '<p class="text-muted small mt-2">'
            'Tip: Copy individual slides or the full deck. Works best '
            'when your board has at least a few tasks with progress and due dates.'
            '</p>'
        ),
    },
    {
        'feature_key': 'knowledge_graph',
        'feature_name': 'Knowledge Graph — Project Memory',
        'order': 20,
        'brief_description': (
            'An interconnected memory of your project\'s decisions, risk '
            'events, lessons learned, conflicts, scope changes, and '
            'milestones. AI discovers causal links between events and '
            'surfaces relevant past patterns when similar situations '
            'arise — preserving organizational memory across projects.'
        ),
        'detailed_description': (
            '<h6>What gets captured</h6>'
            '<p>The Knowledge Graph automatically records significant '
            'events as memory nodes: decisions made, lessons learned, '
            'risk events, conflict resolutions, scope changes, and '
            'milestones. Each node is scored by importance so the most '
            'critical memories surface first.</p>'
            '<h6>How connections work</h6>'
            '<p>AI discovers causal links between events — for example, '
            'a scope change that <em>led to</em> a deadline slip, or a '
            'risk mitigation that <em>prevented</em> a budget overrun. '
            'Connection types include: Caused, Similar To, Led To, '
            'Prevented, and Repeated From.</p>'
            '<h6>Manual memories</h6>'
            '<p>You can also add your own entries — decisions, lessons, '
            'or important observations — using the <strong>Add Decision / '
            'Lesson</strong> button. These are indexed alongside '
            'auto-captured events.</p>'
            '<p class="text-muted small mt-2">'
            'Tip: Use the Organizational Memory search to ask questions '
            'across all projects — e.g., "What happened last time we '
            'tried to migrate the database?"'
            '</p>'
        ),
    },
    {
        'feature_key': 'org_memory',
        'feature_name': 'Organizational Memory',
        'order': 25,
        'brief_description': (
            'Search across your entire organization\'s project history '
            '— decisions, lessons, outcomes, and risks — using natural '
            'language queries. AI finds relevant past patterns and '
            'surfaces them before you repeat the same mistakes.'
        ),
        'detailed_description': (
            '<h6>How it works</h6>'
            '<ol>'
            '<li><strong>Ask a question</strong> — Type a natural language '
            'query about anything in your project history, e.g., "What '
            'happened when we expanded scope on the mobile app?"</li>'
            '<li><strong>AI searches your memory graph</strong> — Gemini '
            'scans all captured memory nodes across every project to find '
            'relevant decisions, lessons, risk events, and outcomes.</li>'
            '<li><strong>Get contextual answers</strong> — Results include '
            'what happened, which project it was on, causal links to other '
            'events, and whether the memory was helpful or unhelpful based '
            'on past feedback.</li>'
            '</ol>'
            '<p class="text-muted small mt-2">'
            'Tip: The more projects your organization runs, the more '
            'valuable this becomes — it\'s your organization\'s collective '
            'experience, searchable and always available.'
            '</p>'
        ),
    },
    {
        'feature_key': 'premortem',
        'feature_name': 'Pre-Mortem AI',
        'order': 30,
        'brief_description': (
            'Before work begins, AI simulates five distinct ways your '
            'project could fail. Each scenario includes a risk level, '
            'root-cause analysis, and mitigation strategy — with team '
            'acknowledgment tracking so no critical risk goes unaddressed.'
        ),
        'detailed_description': (
            '<h6>How it works</h6>'
            '<ol>'
            '<li><strong>Run the analysis</strong> — AI reads your board\'s '
            'tasks, dependencies, team allocation, and deadlines, then '
            'imagines the project has already failed.</li>'
            '<li><strong>Review 5 failure scenarios</strong> — Each '
            'scenario describes a plausible way the project could fall apart, '
            'with a risk level (High / Medium / Low), a root-cause '
            'explanation, and a concrete mitigation strategy.</li>'
            '<li><strong>Acknowledge risks</strong> — Team members sign off '
            'on each scenario to confirm they\'ve read and understood it. '
            'The dashboard tracks who has acknowledged which risks.</li>'
            '</ol>'
            '<p class="text-muted small mt-2">'
            'Tip: Run Pre-Mortem before scope locks in, then feed the '
            'results into the Stress Test for deeper resilience analysis.'
            '</p>'
        ),
    },
    {
        'feature_key': 'stress_test',
        'feature_name': 'Project Stress Test',
        'order': 40,
        'brief_description': (
            'A "Red Team" AI that tries to break your project plan before '
            'real life does. It simulates five targeted attacks, scores '
            'your resilience from 0 to 100 across five dimensions, and '
            'prescribes structural "Vaccine" fixes you can apply to '
            'strengthen your plan.'
        ),
        'detailed_description': (
            '<h6>How it works</h6>'
            '<ol>'
            '<li><strong>Run the Stress Test</strong> — The Red Team AI '
            'reads your live project data and simulates five targeted '
            'attacks — e.g., a key person leaving, a critical dependency '
            'breaking, a sudden budget spike.</li>'
            '<li><strong>Review your Immunity Score</strong> — A resilience '
            'score from 0\u2013100 across five dimensions: Schedule, Budget, '
            'Team, Dependencies, and Scope Stability.</li>'
            '<li><strong>Apply Vaccines</strong> — For each attack, the AI '
            'prescribes a concrete structural fix. Mark vaccines as applied '
            'when you\'ve made the change — the AI stops attacking that '
            'weakness next run and finds new ones instead.</li>'
            '</ol>'
            '<h6>Addressed vs. Applied</h6>'
            '<ul>'
            '<li><strong>Mark Addressed</strong> = "I\'m aware of this risk" '
            '(+3\u20138 pts)</li>'
            '<li><strong>Apply Vaccine</strong> = "I\'ve structurally fixed '
            'this weakness" (+8\u201320 pts each)</li>'
            '</ul>'
            '<p class="text-muted small mt-2">'
            'Tip: Your Immunity Score is cumulative across sessions — every '
            'vaccine you apply is permanently banked. Re-run the test to '
            'find new vulnerabilities as you strengthen the plan.'
            '</p>'
        ),
    },
    {
        'feature_key': 'scope_autopsy',
        'feature_name': 'Scope Creep Autopsy',
        'order': 50,
        'brief_description': (
            'Forensic post-mortem that traces every scope expansion to its '
            'exact cause, contributor, date, and cost or delay impact. '
            'Generates exportable PDF reports that turn scope history into '
            'actionable lessons for future projects.'
        ),
        'detailed_description': (
            '<h6>What the autopsy reveals</h6>'
            '<p>The Scope Autopsy reconstructs how your project\'s scope '
            'grew over time. For each expansion, it identifies:</p>'
            '<ul>'
            '<li><strong>When</strong> — the exact date of each scope change</li>'
            '<li><strong>Who</strong> — who made or approved the change</li>'
            '<li><strong>Why</strong> — the root cause (requirement change, '
            'stakeholder request, discovered complexity, etc.)</li>'
            '<li><strong>Cost</strong> — the impact in days delayed or '
            'budget overrun</li>'
            '</ul>'
            '<p>Results are presented as a forensic timeline with AI-generated '
            'analysis, and can be exported as a PDF report.</p>'
            '<p class="text-muted small mt-2">'
            'Tip: The autopsy is most useful on completed or late-stage '
            'projects where scope has drifted from the original baseline.'
            '</p>'
        ),
    },
    {
        'feature_key': 'whatif',
        'feature_name': 'What-If Scenario Analyzer',
        'order': 60,
        'brief_description': (
            'Simulate the cascading impact of scope changes (\u00b120 tasks), '
            'team size adjustments (\u00b15 members with Brooks\'s Law), and '
            'deadline shifts (\u00b18 weeks) before committing. Each scenario '
            'shows a feasibility score, detected conflicts, and a Gemini-'
            'powered strategic recommendation.'
        ),
        'detailed_description': (
            '<h6>How it works</h6>'
            '<ol>'
            '<li><strong>Adjust the sliders</strong> — Change scope (add or '
            'remove up to 20 tasks), team size (add or remove up to 5 '
            'members), and deadline (shift by up to 8 weeks in either '
            'direction).</li>'
            '<li><strong>Analyze Impact</strong> — PrizmAI computes a live '
            'baseline from your velocity history, budget, and burndown data, '
            'then simulates the projected state under your scenario.</li>'
            '<li><strong>Review results</strong> — You get a feasibility '
            'score (0\u2013100), a before/after comparison table, detected '
            'conflicts (resource overload, deadline infeasibility, budget '
            'overrun), and a Gemini-powered strategic recommendation.</li>'
            '</ol>'
            '<p class="text-muted small mt-2">'
            'Tip: Save interesting scenarios and promote them to Shadow '
            'Board branches for live, ongoing comparison.'
            '</p>'
        ),
    },
    {
        'feature_key': 'shadow_board',
        'feature_name': 'Shadow Board \u2014 Parallel Universe Simulator',
        'order': 70,
        'brief_description': (
            'Run multiple "what-if" scenarios as living, parallel branches '
            'of your project. Each branch updates automatically as real '
            'work progresses, so you can compare options side-by-side with '
            'live feasibility scores. When you\'re ready, commit one branch '
            'to reality and archive the rest.'
        ),
        'detailed_description': (
            '<h6>How it works</h6>'
            '<ol>'
            '<li><strong>Run a What-If scenario</strong> — Use the sliders '
            'in the What-If Analyzer (scope, team size, deadline) and click '
            'Analyze Impact. Save a scenario that looks interesting.</li>'
            '<li><strong>Promote to a Shadow Branch</strong> — Click '
            '"Promote to Shadow Branch" to create a living parallel clone '
            'of your project under that scenario. Repeat for each option '
            'you want to compare.</li>'
            '<li><strong>Watch them update automatically</strong> — As real '
            'work progresses on your board, all active branches recalculate '
            'instantly. You always see current feasibility scores, not '
            'stale what-ifs.</li>'
            '<li><strong>Commit when ready</strong> — When one branch '
            'clearly wins, click Commit This Branch. The others are '
            'archived with a full audit trail.</li>'
            '</ol>'
            '<p class="text-muted small mt-2">'
            'Tip: Check the Quantum Standup at the top of the page — '
            'it shows how today\'s real progress changed each branch\'s '
            'feasibility score.'
            '</p>'
        ),
    },
    {
        'feature_key': 'commitments',
        'feature_name': 'Living Commitment Protocols',
        'order': 80,
        'brief_description': (
            'Replace rigid project plans with living commitments that '
            'honestly track how confident your team actually is. Each '
            'protocol has a real-time confidence score that decays over '
            'time, a prediction market where team members bet on outcomes, '
            'and an AI coach that triggers renegotiation when confidence '
            'drops too low.'
        ),
        'detailed_description': (
            '<h6>The four parts of a Commitment Protocol</h6>'
            '<ol>'
            '<li><strong>Confidence Decay</strong> — Every commitment '
            'starts with a confidence score that automatically decreases '
            'over time. You choose the decay model (exponential, linear, '
            'or stepped) and a half-life that controls the speed.</li>'
            '<li><strong>Prediction Market</strong> — Team members bet '
            'tokens on what they think the real outcome will be. The '
            'Market Consensus is often more accurate than the official '
            'score because it surfaces what the team actually believes.</li>'
            '<li><strong>Signal Log</strong> — Every event that affects '
            'confidence is recorded: task completions, blockers, scope '
            'changes, or manual signals from the team. Full visibility '
            'into what moved the needle.</li>'
            '<li><strong>AI Renegotiation Bot</strong> — When confidence '
            'drops below the threshold you set, the AI coach automatically '
            'steps in with three concrete options to get back on track.</li>'
            '</ol>'
            '<p class="text-muted small mt-2">'
            'Tip: A big divergence between the Market Consensus and the '
            'official confidence score is an early warning sign — it means '
            'the team privately believes something different from the plan.'
            '</p>'
        ),
    },
    {
        'feature_key': 'exit_protocol',
        'feature_name': 'Exit Protocol \u2014 Project Wind-Down',
        'order': 90,
        'brief_description': (
            'A structured system for ending projects deliberately instead '
            'of letting them die quietly. PrizmAI guides the team through '
            'knowledge extraction, transition memos, component preservation, '
            'and a searchable Project Cemetery — so lessons and reusable '
            'parts survive for future projects.'
        ),
        'detailed_description': (
            '<h6>The three parts of Exit Protocol</h6>'
            '<ol>'
            '<li><strong>Project Hospice</strong> — PrizmAI monitors '
            'project health nightly. When the risk score crosses 75%, it '
            'suggests a structured review. Initiate wind-down to get an AI '
            'assessment, knowledge extraction checklist, personalised '
            'transition memos for each team member, and automatic '
            'identification of reusable components.</li>'
            '<li><strong>Organ Transplant</strong> — Reusable parts '
            '(templates, workflows, automation rules, knowledge entries) '
            'are extracted and scored for compatibility. Browse the Organ '
            'Library to transplant proven components into new projects '
            'with one click.</li>'
            '<li><strong>Project Cemetery</strong> — Every archived project '
            'gets a permanent autopsy report: vital statistics, AI-classified '
            'cause of death, timeline of decline, lessons learned, and a '
            'record of which components were transplanted elsewhere.</li>'
            '</ol>'
            '<p class="text-muted small mt-2">'
            'Tip: Buried projects can be resurrected as a fresh board '
            'pre-loaded with all the lessons and a Pre-Mortem analysis '
            'warning about every risk from the original.'
            '</p>'
        ),
    },
]


class Command(BaseCommand):
    help = 'Seed Feature Guide entries for the 9 AI features with dedicated pages.'

    def handle(self, *args, **options):
        created_count = 0
        updated_count = 0

        for data in FEATURE_GUIDES:
            key = data.pop('feature_key')
            obj, created = FeatureGuide.objects.update_or_create(
                feature_key=key,
                defaults=data,
            )
            data['feature_key'] = key  # restore for potential re-run
            if created:
                created_count += 1
            else:
                updated_count += 1

        self.stdout.write(self.style.SUCCESS(
            f'Feature Guides: {created_count} created, {updated_count} updated '
            f'({created_count + updated_count} total).'
        ))
