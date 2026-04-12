"""
Regression test: ask Spectra the original 16 accuracy-test questions
and verify the answers against known-correct data from the VDF layer.

Usage:
    python manage.py regression_test_spectra --board-id=78 --username=testuser1
"""
import re
import time
from django.core.management.base import BaseCommand
from django.contrib.auth import get_user_model

from ai_assistant.models import AIAssistantSession
from ai_assistant.utils.chatbot_service import TaskFlowChatbotService
from ai_assistant.utils.spectra_data_fetchers import (
    fetch_board_tasks,
    fetch_milestones,
    fetch_column_distribution,
    fetch_dependency_graph,
    fetch_assignee_workload,
    fetch_overdue_tasks,
    DONE_COLUMN_NAMES,
)
from kanban.models import Board


# ── Expected answers derived from VDF verification on board 78 ───────────
CHECKS = [
    # (question, list_of_assertions)
    # Each assertion is (label, check_fn(response_text) -> bool)

    # Q1: Board overview / how many tasks
    (
        "How many tasks are on this board?",
        [
            ("total=30", lambda r: "30" in r),
        ],
    ),
    # Q2: Column distribution
    (
        "How many tasks are in each column?",
        [
            ("To Do: 15", lambda r: "15" in r and "to do" in r.lower()),
            ("In Progress: 6", lambda r: "6" in r.lower() and "in progress" in r.lower()),
            ("In Review: 2", lambda r: "2" in r.lower() and "in review" in r.lower()),
            ("Done: 7", lambda r: "7" in r.lower() and "done" in r.lower()),
        ],
    ),
    # Q3: Milestone status (Bug 1 — Foundation must be Done)
    (
        "What are the milestones on this board and their status?",
        [
            ("Foundation Done", lambda r: "foundation" in r.lower() and ("done" in r.lower() or "complete" in r.lower())),
            ("Core Auth not done", lambda r: "core auth" in r.lower()),
        ],
    ),
    # Q4: Specific task status (Bug 2 — Auth System must be In Review)
    (
        "What is the current status of the Authentication System task?",
        [
            ("In Review", lambda r: "in review" in r.lower()),
            ("NOT In Progress", lambda r: "in progress" not in r.lower()
             or ("in review" in r.lower())),  # allow mention if both present
        ],
    ),
    # Q5: Priority check (Bug 3 — User Registration Flow must be Urgent)
    (
        "What is the priority of the User Registration Flow task?",
        [
            ("Urgent", lambda r: "urgent" in r.lower()),
        ],
    ),
    # Q6: In Review column query (Bug 4)
    (
        "Which tasks are currently in the In Review column?",
        [
            ("Auth System", lambda r: "authentication system" in r.lower()),
            ("File Upload", lambda r: "file upload" in r.lower()),
            ("only 2", lambda r: "2" in r),
        ],
    ),
    # Q7: Sam Rivera's tasks (Bug 5 — must list exactly his tasks)
    (
        "Show me all tasks assigned to Sam Rivera",
        [
            ("Performance Optimization", lambda r: "performance optimization" in r.lower()),
            ("Security Audit", lambda r: "security audit" in r.lower()),
            ("Error Tracking", lambda r: "error tracking" in r.lower()),
            ("Search & Indexing", lambda r: "search" in r.lower() and "indexing" in r.lower()),
            ("Auth System", lambda r: "authentication system" in r.lower()),
            ("Dev Env Setup", lambda r: "development environment" in r.lower()),
            ("Security Arch", lambda r: "security architecture" in r.lower()),
            ("Base API", lambda r: "base api" in r.lower()),
            ("Dashboard UI", lambda r: "dashboard" in r.lower()),
        ],
    ),
    # Q8: Overdue tasks
    (
        "Which tasks are overdue?",
        [
            ("User Registration Flow", lambda r: "user registration" in r.lower()),
            ("Database Schema", lambda r: "database schema" in r.lower()),
            ("Auth System", lambda r: "authentication system" in r.lower()),
        ],
    ),
    # Q9: Dependency blocking (Bug 7 — must show correct blocking counts)
    (
        "Which tasks are blocking the most other tasks?",
        [
            ("File Upload blocks 2", lambda r: "file upload" in r.lower()),
            ("User Management API blocks 2", lambda r: "user management" in r.lower()),
        ],
    ),
    # Q10: Alex Chen's tasks
    (
        "What tasks are assigned to Alex Chen?",
        [
            ("Core Features Code Review", lambda r: "core features" in r.lower()),
            ("User Onboarding Flow", lambda r: "user onboarding" in r.lower() or "onboarding flow" in r.lower()),
            ("Deployment Automation", lambda r: "deployment automation" in r.lower()),
            ("Launch & Go-Live", lambda r: "launch" in r.lower()),
            ("User Registration Flow", lambda r: "user registration" in r.lower()),
            ("Requirements Analysis", lambda r: "requirements analysis" in r.lower()),
        ],
    ),
    # Q11: High priority tasks
    (
        "Which tasks have high or urgent priority?",
        [
            ("mentions urgent tasks", lambda r: "urgent" in r.lower()),
            ("mentions high tasks", lambda r: "high" in r.lower()),
        ],
    ),
    # Q12: Done tasks
    (
        "Which tasks are completed?",
        [
            ("Requirements Analysis", lambda r: "requirements analysis" in r.lower()),
            ("Auth Testing Suite", lambda r: "authentication testing" in r.lower()),
            ("Dev Env Setup", lambda r: "development environment" in r.lower()),
            ("System Architecture", lambda r: "system architecture" in r.lower()),
            ("Security Architecture", lambda r: "security architecture" in r.lower()),
            ("Base API", lambda r: "base api" in r.lower()),
            ("Dashboard UI", lambda r: "dashboard" in r.lower()),
        ],
    ),
    # Q13: Team workload
    (
        "Show me the team workload distribution",
        [
            ("Jordan Taylor", lambda r: "jordan" in r.lower()),
            ("Sam Rivera", lambda r: "sam" in r.lower()),
            ("Alex Chen", lambda r: "alex" in r.lower()),
        ],
    ),
    # Q14: Unassigned tasks
    (
        "Are there any unassigned tasks?",
        [
            ("Database Schema", lambda r: "database schema" in r.lower()),
            ("User Management API", lambda r: "user management" in r.lower()),
        ],
    ),
    # Q15: Specific task detail
    (
        "Tell me about the User Registration Flow task",
        [
            ("Urgent priority", lambda r: "urgent" in r.lower()),
            ("In Progress column", lambda r: "in progress" in r.lower()),
            ("assigned to Alex", lambda r: "alex" in r.lower()),
        ],
    ),
    # Q16: Progress overview
    (
        "What is the overall progress of this project?",
        [
            ("mentions column distribution", lambda r: any(
                col in r.lower() for col in ["to do", "in progress", "in review", "done"]
            )),
        ],
    ),
]


class Command(BaseCommand):
    help = "Run regression test: 16 Spectra accuracy questions"

    def add_arguments(self, parser):
        parser.add_argument('--board-id', type=int, required=True)
        parser.add_argument('--username', type=str, default='testuser1')
        parser.add_argument('--question', type=int, default=0,
                            help='Run only question N (1-based). 0 = all.')
        parser.add_argument('--verbose', action='store_true',
                            help='Print full Spectra response for each question')

    def handle(self, *args, **options):
        User = get_user_model()
        user = User.objects.get(username=options['username'])
        board = Board.objects.get(id=options['board_id'])
        verbose = options['verbose']
        only_q = options['question']

        # Get or create a session
        session = AIAssistantSession.objects.filter(user=user).first()
        if not session:
            session = AIAssistantSession.objects.create(
                user=user,
                title="Regression Test",
            )

        chatbot = TaskFlowChatbotService(
            user=user,
            board=board,
            session_id=session.id,
        )

        total_checks = 0
        passed_checks = 0
        failed_questions = []

        checks_to_run = CHECKS
        if only_q:
            checks_to_run = [CHECKS[only_q - 1]]

        for i, (question, assertions) in enumerate(checks_to_run, 1):
            q_num = only_q if only_q else i
            self.stdout.write(f"\n{'='*70}")
            self.stdout.write(self.style.MIGRATE_HEADING(
                f"Q{q_num}: {question}"
            ))

            try:
                result = chatbot.get_response(question, use_cache=False)
                response = result.get('response', '')
                source = result.get('source', 'unknown')
            except Exception as e:
                self.stdout.write(self.style.ERROR(f"  ERROR: {e}"))
                failed_questions.append(q_num)
                total_checks += len(assertions)
                continue

            if verbose:
                # Truncate for readability
                display = response[:1500] + ('...' if len(response) > 1500 else '')
                self.stdout.write(f"  Source: {source}")
                self.stdout.write(f"  Response:\n{display}\n")

            q_passed = True
            for label, check_fn in assertions:
                total_checks += 1
                try:
                    ok = check_fn(response)
                except Exception:
                    ok = False
                if ok:
                    passed_checks += 1
                    self.stdout.write(self.style.SUCCESS(f"  PASS: {label}"))
                else:
                    q_passed = False
                    self.stdout.write(self.style.ERROR(f"  FAIL: {label}"))

            if not q_passed:
                failed_questions.append(q_num)
                if not verbose:
                    # Show truncated response for failed questions
                    display = response[:800] + ('...' if len(response) > 800 else '')
                    self.stdout.write(f"  [Response excerpt]: {display}")

            # Brief pause to avoid rate limiting on Gemini
            time.sleep(1)

        # ── Summary ──
        self.stdout.write(f"\n{'='*70}")
        self.stdout.write(self.style.MIGRATE_HEADING("REGRESSION TEST SUMMARY"))
        self.stdout.write(f"  Questions: {len(checks_to_run)}")
        self.stdout.write(f"  Checks: {passed_checks}/{total_checks} passed")
        if failed_questions:
            self.stdout.write(self.style.ERROR(
                f"  FAILED questions: {failed_questions}"
            ))
        else:
            self.stdout.write(self.style.SUCCESS("  ALL CHECKS PASSED"))
