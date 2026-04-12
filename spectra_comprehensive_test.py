#!/usr/bin/env python
"""
Spectra Comprehensive Test — 109 Questions
Tests all Spectra questions from spectra_test_questions.md against live API,
records responses, and generates a report.

Usage:
    python spectra_comprehensive_test.py [--start N] [--end N] [--question N]
"""
import os, sys, json, time, argparse, datetime, re
os.environ['DJANGO_SETTINGS_MODULE'] = 'kanban_board.settings'

import django
django.setup()

import requests
from django.contrib.auth.models import User
from django.test import Client
from ai_assistant.models import AIAssistantSession

# ─── Config ──────────────────────────────────────────────────────────────
USERNAME = 'testuser1'
BOARD_ID = 78  # Software Development sandbox board
OUTPUT_FILE = 'spectra_test_results.md'

# ─── All 109 Questions ──────────────────────────────────────────────────
QUESTIONS = [
    # Section 1: User Profile & Workspace Context (Q1-Q8)
    "Who am I logged in as, and what is my role in the Software Development board?",
    "What workspace am I currently in?",
    "What is the difference between the Demo workspace and My Workspace?",
    "What boards do I have access to in this demo?",
    "Who are the other members of the Software Development board and what are their roles?",
    "What skills does Sam Rivera have listed in their profile?",
    "What is Jordan Taylor's weekly capacity?",
    "What timezone is this demo workspace set to?",
    # Section 2: Dashboard & Focus Today (Q9-Q16)
    "What is my 'Your Focus Today' summary telling me right now?",
    "How many tasks do I currently have assigned to me?",
    "How many tasks are overdue on the Software Development board?",
    "How many tasks are marked as High Risk?",
    "What does the '7 Done (23.3%)' completion rate tell me about the project?",
    "Which tasks are flagged as requiring my action today?",
    "What are the 3 tasks listed under 'My Tasks' and what are their priorities?",
    "Which of my tasks has the earliest due date?",
    # Section 3: Strategic Hierarchy (Q17-Q24)
    "What is the current organizational goal for this workspace?",
    "What is the status of the goal 'Increase Market Share in Asia by 15%'?",
    "What missions are linked to this goal?",
    "What strategy connects the mission to the Software Development board?",
    "How does the Software Development board contribute to the overall organizational goal?",
    "What is the AI Briefing telling me about the 'Prevent AI Security Threats' mission?",
    "Can you give me a summary of the full hierarchy — from Goal down to the active boards?",
    "How many boards, strategies, and missions are currently tracked in this workspace?",
    # Section 4: Kanban Board Overview (Q25-Q34)
    "How many tasks are currently in each column of the Software Development board?",
    "What are the WIP limits for the 'In Progress' and 'In Review' columns?",
    "Which tasks in the 'To Do' column have the highest priority?",
    "Which tasks are currently 'In Review' and what is their progress?",
    "Tell me about the task 'File Upload System' — what is its current status, progress, and due date?",
    "Who is assigned to the 'Notification Service' task?",
    "What Lean Six Sigma label is applied to the 'Requirements Analysis & Planning' task?",
    "Which tasks are classified as 'Waste/Eliminate'?",
    "What is the scope creep indicator (Scope +3.5%) on the Software Development board telling me?",
    "List all tasks assigned to Jordan Taylor.",
    # Section 5: Task Details & Intelligence (Q35-Q44)
    "What is the full description of the 'Authentication System' task?",
    "How many comments are on the 'User Registration Flow' task?",
    "What are the blocking dependencies for the 'API Rate Limiting' task?",
    "What is the risk score for the 'Database Schema & Migrations' task and why?",
    "Which tasks are past their due date?",
    "What progress percentage is the 'File Upload System' at, and is it on track?",
    "What is the estimated complexity of the 'Integration Testing Suite' task?",
    "Which tasks in Phase 3 (Polish & Launch) have not yet started?",
    "What tasks are related to 'Authentication System'?",
    "Give me a summary of all tasks with 'High' priority on this board.",
    # Section 6: Spectra Actions — Creating & Updating Tasks (Q45-Q50)
    "Create a task called 'Write API Documentation' on the Software Development board with high priority, due in two weeks, assigned to Jordan Taylor.",
    "Update the 'Notification Service' task status to 'In Review'.",
    "Change the priority of 'API Rate Limiting' from To Do to high priority.",
    "Create a new task 'Implement OAuth2 Login' in the To Do column assigned to Sam Rivera due next Friday.",
    "Update the progress of 'Data Caching Layer' to 25%.",
    "Add 'Integration Testing Suite' to the next sprint milestone.",
    # Section 7: Spectra Actions — Messaging, Time & Calendar (Q51-Q55)
    "Send a message to Sam Rivera saying the 'Database Schema & Migrations' task needs review by end of this week.",
    "Log 3 hours of time on the 'Notification Service' task for today.",
    "Schedule a sprint planning event for next Monday at 10 AM for the Software Development board.",
    "Schedule a team retrospective meeting for this Friday at 3 PM.",
    "Send a message to the whole team announcing that 'Authentication System' has moved to In Review.",
    # Section 8: Spectra Actions — Automations (Q56-Q60)
    "Create an automation that moves a task to 'In Review' when its progress reaches 100%.",
    "Set up an automation to notify Jordan Taylor whenever a task assigned to them becomes overdue.",
    "Create a scheduled automation that sends a weekly summary of all 'In Progress' tasks every Monday morning.",
    "Activate a preset automation template for overdue task notifications on the Software Development board.",
    "Create an automation that changes priority to 'Urgent' when a task's due date is within 3 days.",
    # Section 9: Spectra Actions — Retrospectives & Boards (Q61-Q64)
    "Generate a retrospective for the Software Development board covering the last sprint.",
    "What were the main blockers identified in the most recent retrospective?",
    "What lessons were learned in the last retrospective?",
    "Create a new board called 'QA & Testing' with the description 'Track all quality assurance and testing activities'.",
    # Section 10: Commitment Protocols (Q65-Q69)
    "What is the current commitment status of the Software Development board?",
    "Are there any commitments currently below 70% confidence?",
    "What signals have been affecting the confidence score on this board recently?",
    "I want to place a prediction market bet that 'Authentication System' will be done by May 15.",
    "Which commitments are most at risk right now?",
    # Section 11: Analytics & Burndown (Q70-Q75)
    "How is the Software Development team's velocity trending over the last few sprints?",
    "What is the current burndown prediction — when will the project complete at this pace?",
    "Are there any burndown alerts active for this board?",
    "What is the team's overall completion rate compared to the planned rate?",
    "Show me the task completion trend for the past 4 weeks.",
    "How many tasks were completed this week vs. last week?",
    # Section 12: AI Coach (PrizmBrief) (Q76-Q81)
    "What is the AI Coach's top recommendation for the Software Development board right now?",
    "Is anyone on the team currently overloaded based on the AI Coach analysis?",
    "What patterns has the AI Coach detected in this project so far?",
    "What does the 'Status Report' say about the overall health of the Software Development board?",
    "What are the AI Coach's coaching insights for Alex Chen as Project Manager?",
    "Are there any quick wins the AI Coach has identified for this sprint?",
    # Section 13: Resource Optimization & Skill Gaps (Q82-Q88)
    "Who is the most overloaded team member on the Software Development board right now?",
    "What skill gaps exist on the team for the current set of tasks?",
    "Who would be the best person to assign the 'Performance Optimization' task to, and why?",
    "What does the Resource Optimization report recommend for balancing the workload?",
    "What skills does the team still need to complete Phase 3 (Polish & Launch)?",
    "Are there any tasks where the assigned person's skills don't match the task requirements?",
    "What is Jordan Taylor's current workload as a percentage of capacity?",
    # Section 14: What-If Scenario Analyzer (Q89-Q94)
    "What happens to the project timeline if we remove 5 tasks from scope?",
    "What is the impact if Sam Rivera is unavailable for the next 2 weeks?",
    "What if we compress the deadline by 3 weeks — is the project still feasible?",
    "Simulate adding 2 more team members — how does it affect the completion date?",
    "What is the current feasibility score for the Software Development board?",
    "Run a scenario where scope increases by 8 tasks — what is the budget impact?",
    # Section 15: Shadow Board (Q95-Q99)
    "Does the Software Development board have any active shadow branches?",
    "Create a shadow branch simulating 'cut 10 tasks from scope' on the Software Development board.",
    "Compare the main project to the shadow branch — which is more likely to finish on time?",
    "What is the divergence log showing between the main project and any shadow branch?",
    "What is the feasibility score on the shadow branch vs. the main project?",
    # Section 16: Pre-Mortem Analysis (Q100-Q104)
    "Have any pre-mortem analyses been run on the Software Development board?",
    "What are the top 3 failure scenarios identified in the pre-mortem for this project?",
    "What mitigation strategies does the pre-mortem recommend for the 'budget overrun' scenario?",
    "Has the team acknowledged the pre-mortem risk scenarios? Who has signed off?",
    "What is the risk level for the 'key person leaving mid-sprint' scenario?",
    # Section 17: Stress Test (Red Team) (Q105-Q109)
    "What is the current Immunity Score for the Software Development board?",
    "How resilient is the project's schedule based on the stress test results?",
    "What 'vaccines' has the stress test recommended to strengthen the project plan?",
    "Which stress test dimension is weakest — Schedule, Budget, Team, Dependencies, or Scope?",
    "Run a stress test on the 'critical dependency breaking' scenario for this board.",
]

SECTION_NAMES = {
    1: "User Profile & Workspace Context",
    9: "Dashboard & Focus Today",
    17: "Strategic Hierarchy",
    25: "Kanban Board Overview",
    35: "Task Details & Intelligence",
    45: "Spectra Actions — Creating & Updating Tasks",
    51: "Spectra Actions — Messaging, Time & Calendar",
    56: "Spectra Actions — Automations",
    61: "Spectra Actions — Retrospectives & Boards",
    65: "Commitment Protocols",
    70: "Analytics & Burndown",
    76: "AI Coach (PrizmBrief)",
    82: "Resource Optimization & Skill Gaps",
    89: "What-If Scenario Analyzer",
    95: "Shadow Board (Parallel Universe Simulator)",
    100: "Pre-Mortem Analysis",
    105: "Stress Test (Red Team)",
}

# Action questions that should return v1.0 disabled fallback
ACTION_QUESTIONS = list(range(45, 65))  # Q45-Q64


def get_section(q_num):
    """Get section name for a question number."""
    section = "Unknown"
    for start, name in sorted(SECTION_NAMES.items()):
        if q_num >= start:
            section = name
    return section


def setup_session():
    """Create a Django test client session and AI assistant session."""
    client = Client()
    user = User.objects.get(username=USERNAME)
    client.force_login(user)
    
    # Create AI session
    session = AIAssistantSession.objects.create(
        user=user,
        board_id=BOARD_ID,
        title='Spectra Comprehensive Test'
    )
    return client, session, user


def ask_spectra(client, session, question, board_id=BOARD_ID):
    """Send a question to Spectra and return the response."""
    response = client.post(
        '/assistant/api/send-message/',
        data=json.dumps({
            'message': question,
            'session_id': session.id,
            'board_id': board_id,
        }),
        content_type='application/json',
    )
    
    if response.status_code == 200:
        data = response.json()
        return {
            'status': 'success',
            'response': data.get('response', ''),
            'source': data.get('source', ''),
            'http_status': 200,
        }
    else:
        try:
            data = response.json()
        except Exception:
            data = {'raw': response.content.decode()[:500]}
        return {
            'status': 'error',
            'response': data.get('error', data.get('response', str(data))),
            'http_status': response.status_code,
        }


def run_tests(start=1, end=109, single=None):
    """Run all test questions and collect results."""
    client, session, user = setup_session()
    results = []
    
    if single:
        indices = [single - 1]
    else:
        indices = list(range(start - 1, min(end, len(QUESTIONS))))
    
    total = len(indices)
    print(f"\n{'='*60}")
    print(f"  SPECTRA COMPREHENSIVE TEST")
    print(f"  Questions: {total} | Board: {BOARD_ID} | User: {USERNAME}")
    print(f"{'='*60}\n")
    
    for i, idx in enumerate(indices):
        q_num = idx + 1
        question = QUESTIONS[idx]
        section = get_section(q_num)
        
        print(f"[{i+1}/{total}] Q{q_num}: {question[:70]}...")
        
        t0 = time.time()
        try:
            result = ask_spectra(client, session, question)
        except Exception as e:
            result = {'status': 'error', 'response': f'EXCEPTION: {e}', 'http_status': 0}
        elapsed = time.time() - t0
        
        result['question_num'] = q_num
        result['question'] = question
        result['section'] = section
        result['elapsed_seconds'] = round(elapsed, 2)
        result['is_action_question'] = q_num in ACTION_QUESTIONS
        
        results.append(result)
        
        status_icon = "OK" if result['status'] == 'success' else "ERR"
        resp_preview = str(result.get('response', ''))[:80]
        print(f"  [{status_icon}] {elapsed:.1f}s | {resp_preview}...\n")
        
        # Small delay to avoid hammering the API
        time.sleep(0.3)
    
    return results


def generate_report(results):
    """Generate comprehensive markdown report."""
    now = datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    
    success_count = sum(1 for r in results if r['status'] == 'success')
    error_count = sum(1 for r in results if r['status'] != 'success')
    action_count = sum(1 for r in results if r.get('is_action_question'))
    avg_time = sum(r['elapsed_seconds'] for r in results) / len(results) if results else 0
    total_time = sum(r['elapsed_seconds'] for r in results)
    
    report = []
    report.append(f"# Spectra Comprehensive Test Report")
    report.append(f"")
    report.append(f"> Generated: {now}")
    report.append(f"> Board: Software Development (id={BOARD_ID})")
    report.append(f"> User: {USERNAME}")
    report.append(f"> Total Questions: {len(results)}")
    report.append(f"> Successful: {success_count} | Errors: {error_count}")
    report.append(f"> Avg Response Time: {avg_time:.1f}s | Total Time: {total_time:.0f}s")
    report.append(f"")
    report.append(f"---")
    report.append(f"")
    
    # Group by section
    current_section = None
    for r in results:
        if r['section'] != current_section:
            current_section = r['section']
            report.append(f"## {current_section}")
            report.append(f"")
        
        q_num = r['question_num']
        status_badge = "PASS" if r['status'] == 'success' else "FAIL"
        if r.get('is_action_question'):
            status_badge = "ACTION(v1.0 disabled)"
        
        report.append(f"### Q{q_num}. {r['question']}")
        report.append(f"")
        report.append(f"**Status**: {status_badge} | **Time**: {r['elapsed_seconds']}s")
        report.append(f"")
        report.append(f"**Spectra's Response:**")
        report.append(f"")
        # Clean and format the response
        response_text = r.get('response', 'No response')
        report.append(f"> {response_text}")
        report.append(f"")
        report.append(f"---")
        report.append(f"")
    
    return "\n".join(report)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='Spectra Comprehensive Test')
    parser.add_argument('--start', type=int, default=1, help='Start question number')
    parser.add_argument('--end', type=int, default=109, help='End question number')
    parser.add_argument('--question', type=int, help='Single question number')
    parser.add_argument('--output', type=str, default=OUTPUT_FILE, help='Output file')
    args = parser.parse_args()
    
    results = run_tests(start=args.start, end=args.end, single=args.question)
    
    # Save JSON intermediate results
    json_file = args.output.replace('.md', '.json')
    
    # Load existing results if appending
    existing = []
    if os.path.exists(json_file) and not args.question:
        try:
            with open(json_file, 'r', encoding='utf-8') as f:
                existing = json.load(f)
        except Exception:
            existing = []
    
    # Merge: replace any existing questions with new results
    existing_nums = {r['question_num'] for r in results}
    merged = [r for r in existing if r['question_num'] not in existing_nums] + results
    merged.sort(key=lambda r: r['question_num'])
    
    with open(json_file, 'w', encoding='utf-8') as f:
        json.dump(merged, f, indent=2, ensure_ascii=False)
    
    report = generate_report(merged)
    with open(args.output, 'w', encoding='utf-8') as f:
        f.write(report)
    
    print(f"\n{'='*60}")
    print(f"  REPORT SAVED: {args.output}")
    print(f"  Total: {len(results)} questions tested")
    print(f"{'='*60}")
