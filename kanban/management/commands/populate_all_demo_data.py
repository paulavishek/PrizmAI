"""
Consolidated Demo Data Population Command
=========================================
A single command to populate ALL demo data for PrizmAI application.

This file consolidates demo data creation for:
- Tasks, dependencies, and labels
- Wiki pages and categories
- Messaging (chat rooms, messages, notifications)
- Conflicts (resource, dependency, schedule conflicts)
- AI Assistant (chat sessions, Q&A history)
- Time tracking, budgets, retrospectives, coaching

Usage:
    python manage.py populate_all_demo_data
    python manage.py populate_all_demo_data --reset  # Clear and recreate all

This creates a comprehensive demo environment showcasing all PrizmAI features.
"""
from django.core.management.base import BaseCommand
from django.contrib.auth.models import User
from django.utils import timezone
from django.db import transaction
from datetime import timedelta, date
from decimal import Decimal
import random
import json

# Import all required models
from accounts.models import Organization
from kanban.models import Board, Column, Task, TaskLabel, Comment, TaskActivity, TaskFile, Mission, Strategy, OrganizationGoal, BoardMembership
from kanban.budget_models import TimeEntry, ProjectBudget, TaskCost, ProjectROI
from kanban.burndown_models import TeamVelocitySnapshot, BurndownPrediction
from kanban.retrospective_models import ProjectRetrospective, LessonLearned, ImprovementMetric, RetrospectiveActionItem
from kanban.coach_models import CoachingSuggestion, PMMetrics, CoachingInsight
from kanban.stakeholder_models import ProjectStakeholder, StakeholderTaskInvolvement
from kanban.conflict_models import ConflictDetection, ConflictResolution, ConflictNotification

# Wiki models
from wiki.models import WikiPage, WikiCategory, WikiLink

# Messaging models
from messaging.models import ChatRoom, ChatMessage, Notification, FileAttachment, TaskThreadComment

# AI Assistant models
from ai_assistant.models import (
    AIAssistantSession, AIAssistantMessage, ProjectKnowledgeBase,
    AIAssistantAnalytics, AITaskRecommendation, UserPreference
)

# Commitment Protocol models
from kanban.commitment_models import CommitmentProtocol, ConfidenceSignal, CommitmentBet, UserCredibilityScore


class Command(BaseCommand):
    help = 'Populate ALL demo data in a single command (tasks, wiki, messaging, conflicts, AI assistant)'

    @staticmethod
    def _next_quarter_label():
        """Return a label like 'Q2 2025' for the next calendar quarter."""
        today = date.today()
        quarter = (today.month - 1) // 3 + 1  # current quarter (1-4)
        next_q = quarter % 4 + 1
        year = today.year if next_q > quarter else today.year + 1
        return f'Q{next_q} {year}'

    def add_arguments(self, parser):
        parser.add_argument(
            '--reset',
            action='store_true',
            help='Delete ALL existing demo data before creating new data',
        )
        parser.add_argument(
            '--skip-tasks',
            action='store_true',
            help='Skip task creation (useful if tasks already exist)',
        )

    def handle(self, *args, **options):
        self.stdout.write(self.style.SUCCESS('\n' + '=' * 80))
        self.stdout.write(self.style.SUCCESS('CONSOLIDATED DEMO DATA POPULATION'))
        self.stdout.write(self.style.SUCCESS('=' * 80 + '\n'))

        # =====================================================================
        # SELF-HEALING: Ensure demo organization exists before proceeding
        # =====================================================================
        try:
            self.demo_org = Organization.objects.get(is_demo=True)
            self.stdout.write(self.style.SUCCESS(f'✅ Found organization: {self.demo_org.name}'))
        except Organization.DoesNotExist:
            self.stdout.write(self.style.WARNING(
                '⚠️ Demo organization not found. Auto-creating...'
            ))
            # Self-healing: create demo organization
            from django.core.management import call_command
            call_command('create_demo_organization')
            try:
                self.demo_org = Organization.objects.get(is_demo=True)
                self.stdout.write(self.style.SUCCESS(f'✅ Created organization: {self.demo_org.name}'))
            except Organization.DoesNotExist:
                self.stdout.write(self.style.ERROR(
                    '❌ Failed to create demo organization.'
                ))
                return

        # Get demo users (self-healing: will be created by create_demo_organization if missing)
        self.alex = User.objects.filter(username='alex_chen_demo').first()
        self.sam = User.objects.filter(username='sam_rivera_demo').first()
        self.jordan = User.objects.filter(username='jordan_taylor_demo').first()

        self.demo_users = [u for u in [self.alex, self.sam, self.jordan] if u]
        if len(self.demo_users) < 3:
            self.stdout.write(self.style.WARNING(
                '⚠️ Demo users not found. Running create_demo_organization to fix...'
            ))
            from django.core.management import call_command
            call_command('create_demo_organization')
            # Refresh user references
            self.alex = User.objects.filter(username='alex_chen_demo').first()
            self.sam = User.objects.filter(username='sam_rivera_demo').first()
            self.jordan = User.objects.filter(username='jordan_taylor_demo').first()
            self.demo_users = [u for u in [self.alex, self.sam, self.jordan] if u]
            
        self.stdout.write(f'   Found {len(self.demo_users)} demo users')

        # Get demo boards (self-healing: recreate if missing)
        self.demo_boards = Board.objects.filter(organization=self.demo_org, is_official_demo_board=True)
        self.software_board = self.demo_boards.filter(name__icontains='software').first()
        self.marketing_board = self.demo_boards.filter(name__icontains='marketing').first()
        self.bug_board = self.demo_boards.filter(name__icontains='bug').first()

        if not self.software_board:
            self.stdout.write(self.style.WARNING(
                '⚠️ Demo board not found. Running create_demo_organization to fix...'
            ))
            from django.core.management import call_command
            call_command('create_demo_organization')
            # Refresh board references
            self.demo_boards = Board.objects.filter(organization=self.demo_org, is_official_demo_board=True)
            self.software_board = self.demo_boards.filter(name__icontains='software').first()
            self.marketing_board = None
            self.bug_board = None
            
        self.stdout.write(f'   Found {self.demo_boards.count()} demo boards')

        # Reset if requested
        if options['reset']:
            self.reset_all_demo_data()

        with transaction.atomic():
            # 1. Create tasks and related data (unless skipped)
            if not options['skip_tasks']:
                self.stdout.write(self.style.NOTICE('\n📝 PHASE 1: Creating Tasks & Core Data...'))
                from django.core.management import call_command
                try:
                    if options['reset']:
                        call_command('populate_demo_data', '--reset')
                    else:
                        call_command('populate_demo_data')
                except Exception as e:
                    self.stdout.write(self.style.WARNING(f'   ⚠️ Task creation via existing command: {e}'))
                    self.stdout.write('   Creating tasks directly...')
                    # Fallback: tasks are created by the existing command

            # 2. Populate Marketing Campaign & Bug Tracking boards
            self.stdout.write(self.style.NOTICE('\n📋 PHASE 1b: Creating Marketing & Bug Tracking Tasks...'))
            extra_stats = self.create_extra_board_tasks()
            self.stdout.write(self.style.SUCCESS(
                f'   ✅ Extra boards: {extra_stats["boards"]} boards, {extra_stats["tasks"]} tasks'
            ))

            # 3. Wiki Demo Data
            self.stdout.write(self.style.NOTICE('\n📚 PHASE 2: Creating Wiki Demo Data...'))
            wiki_stats = self.create_wiki_demo_data()
            self.stdout.write(self.style.SUCCESS(
                f'   ✅ Wiki: {wiki_stats["categories"]} categories, {wiki_stats["pages"]} pages, {wiki_stats["links"]} links'
            ))

            # 3. Messaging Demo Data
            self.stdout.write(self.style.NOTICE('\n💬 PHASE 3: Creating Messaging Demo Data...'))
            msg_stats = self.create_messaging_demo_data()
            self.stdout.write(self.style.SUCCESS(
                f'   ✅ Messaging: {msg_stats["rooms"]} rooms, {msg_stats["messages"]} messages'
            ))

            # 4. Conflict Demo Data
            self.stdout.write(self.style.NOTICE('\n⚠️ PHASE 4: Creating Conflict Demo Data...'))
            conflict_stats = self.create_conflict_demo_data()
            self.stdout.write(self.style.SUCCESS(
                f'   ✅ Conflicts: {conflict_stats["conflicts"]} conflicts, {conflict_stats["resolutions"]} resolutions'
            ))

            # 5. AI Assistant Demo Data
            self.stdout.write(self.style.NOTICE('\n🤖 PHASE 5: Creating AI Assistant Demo Data...'))
            ai_stats = self.create_ai_assistant_demo_data()
            self.stdout.write(self.style.SUCCESS(
                f'   ✅ AI Assistant: {ai_stats["sessions"]} sessions, {ai_stats["messages"]} messages, '
                f'{ai_stats["analytics"]} analytics, {ai_stats["knowledge_base"]} KB entries, '
                f'{ai_stats["recommendations"]} recommendations'
            ))

            # 6. Time Tracking Demo Data
            self.stdout.write(self.style.NOTICE('\n⏱️ PHASE 6: Creating Time Tracking Demo Data...'))
            time_stats = self.create_time_tracking_demo_data()
            self.stdout.write(self.style.SUCCESS(
                f'   ✅ Time Tracking: {time_stats["entries"]} time entries for {time_stats["users"]} users'
            ))

            # 7. Mission & Strategy (hierarchy layer above Boards)
            self.stdout.write(self.style.NOTICE('\n🎯 PHASE 7: Creating Demo Mission & Strategy...'))
            self.seed_demo_mission_strategy()
            self.stdout.write(self.style.SUCCESS('   ✅ Demo Mission & Strategy seeded'))

            # 8. Organization Goal (apex of hierarchy — sits above Mission)
            self.stdout.write(self.style.NOTICE('\n🏆 PHASE 8: Creating Demo Organization Goal...'))
            self.seed_demo_organization_goal()
            self.stdout.write(self.style.SUCCESS('   ✅ Demo Organization Goal seeded'))

            # 9. Commitment Protocols Demo Data
            self.stdout.write(self.style.NOTICE('\n📋 PHASE 9: Creating Commitment Protocol Demo Data...'))
            from django.core.management import call_command as _call
            try:
                _call('populate_commitment_demo_data')
            except Exception as e:
                self.stdout.write(self.style.WARNING(f'   ⚠️ Commitment protocol creation: {e}'))

            # 10. AI Tools Demo Data (What-If, Shadow Board, Pre-Mortem, Stress Test, Scope Autopsy, Exit Protocol)
            self.stdout.write(self.style.NOTICE('\n🧠 PHASE 10: Creating AI Tools Demo Data...'))
            ai_tools_stats = self.create_ai_tools_demo_data()
            self.stdout.write(self.style.SUCCESS(
                f'   ✅ AI Tools: {ai_tools_stats["whatif"]} What-If scenarios, '
                f'{ai_tools_stats["shadow_branches"]} Shadow Branches, '
                f'{ai_tools_stats["premortem"]} Pre-Mortem analyses, '
                f'{ai_tools_stats["stress_tests"]} Stress Tests, '
                f'{ai_tools_stats["scope_autopsies"]} Scope Autopsies, '
                f'{ai_tools_stats["exit_protocol"]} Exit Protocol entries'
            ))

        # Final Summary
        self.print_final_summary()

    def reset_all_demo_data(self):
        """Reset ALL demo data - removes user-created content and prepares for fresh population"""
        self.stdout.write(self.style.WARNING('\n🗑️ Resetting ALL demo data...'))

        from django.db import connection
        from kanban.models import Comment, TaskActivity, TaskFile
        from kanban.resource_leveling_models import TaskAssignmentHistory
        from kanban.stakeholder_models import StakeholderTaskInvolvement

        # =====================================================================
        # STEP 1: Delete user-created boards (non-official demo boards)
        #         — must delete all related artifacts before the boards
        # =====================================================================
        user_created_boards = list(Board.objects.filter(
            organization=self.demo_org,
            is_official_demo_board=False
        ))

        deleted_board_count = 0
        for board in user_created_boards:
            task_ids = list(Task.objects.filter(column__board=board).values_list('id', flat=True))

            if task_ids:
                # Clear M2M on tasks first
                for task in Task.objects.filter(id__in=task_ids):
                    try:
                        task.dependencies.clear()
                    except Exception:
                        pass
                    try:
                        task.related_tasks.clear()
                    except Exception:
                        pass

                # Task-level children
                TaskActivity.objects.filter(task_id__in=task_ids).delete()
                Comment.objects.filter(task_id__in=task_ids).delete()
                TaskFile.objects.filter(task_id__in=task_ids).delete()
                try:
                    TaskAssignmentHistory.objects.filter(task_id__in=task_ids).delete()
                except Exception:
                    pass
                try:
                    StakeholderTaskInvolvement.objects.filter(task_id__in=task_ids).delete()
                except Exception:
                    pass
                try:
                    TaskThreadComment.objects.filter(task_id__in=task_ids).delete()
                except Exception:
                    pass
                try:
                    TimeEntry.objects.filter(task_id__in=task_ids).delete()
                except Exception:
                    pass
                try:
                    from kanban.budget_models import TaskCost
                    TaskCost.objects.filter(task_id__in=task_ids).delete()
                except Exception:
                    pass
                try:
                    from wiki.models import WikiLink as WL
                    WL.objects.filter(task_id__in=task_ids).delete()
                except Exception:
                    pass

                Task.objects.filter(id__in=task_ids).delete()

            # Board-level children
            try:
                from webhooks.models import WebhookEvent as WE, Webhook as WH
                WE.objects.filter(board=board).delete()
                WH.objects.filter(board=board).delete()
            except Exception:
                pass
            try:
                FileAttachment.objects.filter(chat_room__board=board).delete()
                ChatMessage.objects.filter(chat_room__board=board).delete()
                ChatRoom.objects.filter(board=board).delete()
            except Exception:
                pass
            try:
                ConflictNotification.objects.filter(conflict__board=board).delete()
                ConflictResolution.objects.filter(conflict__board=board).delete()
                ConflictDetection.objects.filter(board=board).delete()
            except Exception:
                pass
            try:
                AIAssistantMessage.objects.filter(session__board=board).delete()
                AIAssistantSession.objects.filter(board=board).delete()
                AITaskRecommendation.objects.filter(board=board).delete()
                ProjectKnowledgeBase.objects.filter(board=board).delete()
                AIAssistantAnalytics.objects.filter(board=board).delete()
            except Exception:
                pass
            try:
                from kanban.stakeholder_models import (
                    StakeholderEngagementRecord
                )
                StakeholderEngagementRecord.objects.filter(
                    stakeholder__board=board
                ).delete()
                StakeholderTaskInvolvement.objects.filter(
                    stakeholder__board=board
                ).delete()
                from kanban.stakeholder_models import ProjectStakeholder
                ProjectStakeholder.objects.filter(board=board).delete()
            except Exception:
                pass
            try:
                from kanban.retrospective_models import (
                    RetrospectiveTrend, ImprovementMetric, LessonLearned,
                    RetrospectiveActionItem, ProjectRetrospective
                )
                RetrospectiveTrend.objects.filter(board=board).delete()
                ImprovementMetric.objects.filter(board=board).delete()
                LessonLearned.objects.filter(board=board).delete()
                RetrospectiveActionItem.objects.filter(board=board).delete()
                ProjectRetrospective.objects.filter(board=board).delete()
            except Exception:
                pass
            try:
                from kanban.coach_models import CoachingSuggestion, PMMetrics
                CoachingSuggestion.objects.filter(board=board).delete()
                PMMetrics.objects.filter(board=board).delete()
            except Exception:
                pass
            try:
                from kanban.budget_models import ProjectBudget, ProjectROI
                ProjectROI.objects.filter(board=board).delete()
                ProjectBudget.objects.filter(board=board).delete()
            except Exception:
                pass
            try:
                from kanban.burndown_models import (
                    TeamVelocitySnapshot, BurndownPrediction, BurndownAlert, SprintMilestone
                )
                BurndownAlert.objects.filter(board=board).delete()
                BurndownPrediction.objects.filter(board=board).delete()
                TeamVelocitySnapshot.objects.filter(board=board).delete()
                SprintMilestone.objects.filter(board=board).delete()
            except Exception:
                pass
            try:
                from kanban.models import (
                    TeamSkillProfile, SkillGap, SkillDevelopmentPlan,
                    ScopeChangeSnapshot, ScopeCreepAlert,
                    WorkloadDistributionRecommendation, TeamCapacityAlert,
                    ResourceDemandForecast, MeetingTranscript
                )
                SkillGap.objects.filter(board=board).delete()
                SkillDevelopmentPlan.objects.filter(board=board).delete()
                TeamSkillProfile.objects.filter(board=board).delete()
                ScopeCreepAlert.objects.filter(board=board).delete()
                ScopeChangeSnapshot.objects.filter(board=board).delete()
                WorkloadDistributionRecommendation.objects.filter(board=board).delete()
                TeamCapacityAlert.objects.filter(board=board).delete()
                ResourceDemandForecast.objects.filter(board=board).delete()
                MeetingTranscript.objects.filter(board=board).delete()
            except Exception:
                pass
            try:
                from analytics.models import EngagementMetrics
                EngagementMetrics.objects.filter(board=board).delete()
            except Exception:
                pass
            try:
                from kanban.models import BoardMembership
                BoardMembership.objects.filter(board=board).delete()
            except Exception:
                pass

            # Delete columns then board (with FK safety)
            board.columns.all().delete()
            with connection.cursor() as c:
                c.execute('PRAGMA foreign_keys = OFF;')
            board.delete()
            with connection.cursor() as c:
                c.execute('PRAGMA foreign_keys = ON;')
            deleted_board_count += 1

        if deleted_board_count:
            self.stdout.write(f'   ✓ Deleted {deleted_board_count} user-created boards')

        # Fix any orphaned webhook events from previously-deleted boards
        try:
            with connection.cursor() as c:
                c.execute(
                    'DELETE FROM webhooks_webhookevent '
                    'WHERE board_id NOT IN (SELECT id FROM kanban_board)'
                )
        except Exception:
            pass

        # =====================================================================
        # STEP 2: Delete user-created tasks on official demo boards
        # =====================================================================
        user_tasks_on_demo_boards = Task.objects.filter(
            column__board__in=self.demo_boards,
            is_seed_demo_data=False
        )
        if user_tasks_on_demo_boards.exists():
            user_task_ids = list(user_tasks_on_demo_boards.values_list('id', flat=True))
            # Clean children first
            Comment.objects.filter(task_id__in=user_task_ids).delete()
            TaskActivity.objects.filter(task_id__in=user_task_ids).delete()
            TaskFile.objects.filter(task_id__in=user_task_ids).delete()
            for t in Task.objects.filter(id__in=user_task_ids):
                try:
                    t.dependencies.clear()
                except Exception:
                    pass
                try:
                    t.related_tasks.clear()
                except Exception:
                    pass
            deleted = user_tasks_on_demo_boards.delete()[0]
            self.stdout.write(f'   ✓ Deleted {deleted} user-created tasks on demo boards')

        # Delete ALL comments on demo boards (will be repopulated by seed data)
        Comment.objects.filter(
            task__column__board__in=self.demo_boards
        ).delete()

        # =====================================================================
        # STEP 3: Clear Wiki data (all data in demo org, will be repopulated)
        # =====================================================================
        WikiLink.objects.filter(wiki_page__organization=self.demo_org).delete()
        WikiPage.objects.filter(organization=self.demo_org).delete()
        WikiCategory.objects.filter(organization=self.demo_org).delete()
        self.stdout.write('   ✓ Cleared Wiki data')

        # =====================================================================
        # STEP 4: Clear Messaging data (all — will be repopulated)
        # =====================================================================
        Notification.objects.filter(recipient__in=self.demo_users).delete()
        # Also clear notifications for ALL users on demo boards
        try:
            Notification.objects.filter(board__in=self.demo_boards).delete()
        except Exception:
            pass
        FileAttachment.objects.filter(chat_room__board__in=self.demo_boards).delete()
        ChatMessage.objects.filter(chat_room__board__in=self.demo_boards).delete()
        TaskThreadComment.objects.filter(task__column__board__in=self.demo_boards).delete()
        ChatRoom.objects.filter(board__in=self.demo_boards).delete()
        self.stdout.write('   ✓ Cleared Messaging data')

        # =====================================================================
        # STEP 5: Clear Conflicts data
        # =====================================================================
        ConflictNotification.objects.filter(conflict__board__in=self.demo_boards).delete()
        ConflictResolution.objects.filter(conflict__board__in=self.demo_boards).delete()
        ConflictDetection.objects.filter(board__in=self.demo_boards).delete()
        self.stdout.write('   ✓ Cleared Conflict data')

        # =====================================================================
        # STEP 6: Clear AI Assistant data
        # =====================================================================
        AIAssistantMessage.objects.filter(session__board__in=self.demo_boards).delete()
        AIAssistantSession.objects.filter(board__in=self.demo_boards).delete()
        AIAssistantMessage.objects.filter(session__user__in=self.demo_users).delete()
        AIAssistantSession.objects.filter(user__in=self.demo_users).delete()
        ProjectKnowledgeBase.objects.filter(board__in=self.demo_boards).delete()
        AIAssistantAnalytics.objects.filter(user__in=self.demo_users).delete()
        AIAssistantAnalytics.objects.filter(board__in=self.demo_boards).delete()
        AITaskRecommendation.objects.filter(board__in=self.demo_boards).delete()
        self.stdout.write('   ✓ Cleared AI Assistant data')

        # =====================================================================
        # STEP 7: Clear Time Tracking data
        # =====================================================================
        TimeEntry.objects.filter(task__column__board__in=self.demo_boards).delete()
        self.stdout.write('   ✓ Cleared Time Tracking data')

        # =====================================================================
        # STEP 8: Clear Stakeholder data
        # =====================================================================
        try:
            from kanban.stakeholder_models import (
                ProjectStakeholder, StakeholderTaskInvolvement, StakeholderEngagementRecord
            )
            StakeholderEngagementRecord.objects.filter(
                stakeholder__board__in=self.demo_boards
            ).delete()
            StakeholderTaskInvolvement.objects.filter(
                stakeholder__board__in=self.demo_boards
            ).delete()
            ProjectStakeholder.objects.filter(board__in=self.demo_boards).delete()
        except Exception:
            pass
        self.stdout.write('   ✓ Cleared Stakeholder data')

        # =====================================================================
        # STEP 9: Clear Skill Profiles and Skill Gaps
        # =====================================================================
        from kanban.models import TeamSkillProfile, SkillGap
        SkillGap.objects.filter(board__in=self.demo_boards).delete()
        try:
            from kanban.models import SkillDevelopmentPlan
            SkillDevelopmentPlan.objects.filter(board__in=self.demo_boards).delete()
        except Exception:
            pass
        TeamSkillProfile.objects.filter(board__in=self.demo_boards).delete()
        self.stdout.write('   ✓ Cleared Skill data')

        # =====================================================================
        # STEP 10: Clear Scope Change data
        # =====================================================================
        from kanban.models import ScopeChangeSnapshot, ScopeCreepAlert
        ScopeCreepAlert.objects.filter(board__in=self.demo_boards).delete()
        ScopeChangeSnapshot.objects.filter(board__in=self.demo_boards).delete()
        self.demo_boards.update(
            baseline_task_count=None,
            baseline_complexity_total=None,
            baseline_set_date=None,
            baseline_set_by=None
        )
        self.stdout.write('   ✓ Cleared Scope Change data and board baselines')

        # =====================================================================
        # STEP 11: Clear Sprint Milestones
        # =====================================================================
        from kanban.burndown_models import SprintMilestone
        SprintMilestone.objects.filter(board__in=self.demo_boards).delete()
        self.stdout.write('   ✓ Cleared Sprint Milestone data')

        # =====================================================================
        # STEP 12: Clear Retrospective data
        # =====================================================================
        try:
            from kanban.retrospective_models import (
                RetrospectiveTrend, ImprovementMetric, LessonLearned,
                RetrospectiveActionItem, ProjectRetrospective
            )
            RetrospectiveTrend.objects.filter(board__in=self.demo_boards).delete()
            ImprovementMetric.objects.filter(board__in=self.demo_boards).delete()
            LessonLearned.objects.filter(board__in=self.demo_boards).delete()
            RetrospectiveActionItem.objects.filter(board__in=self.demo_boards).delete()
            ProjectRetrospective.objects.filter(board__in=self.demo_boards).delete()
        except Exception:
            pass
        self.stdout.write('   ✓ Cleared Retrospective data')

        # =====================================================================
        # STEP 13: Clear Analytics engagement metrics
        # =====================================================================
        try:
            from analytics.models import EngagementMetrics
            EngagementMetrics.objects.filter(board__in=self.demo_boards).delete()
        except Exception:
            pass

        # =====================================================================
        # STEP 14: Clear Webhook events on demo boards
        # =====================================================================
        try:
            from webhooks.models import WebhookEvent
            WebhookEvent.objects.filter(board__in=self.demo_boards).delete()
        except Exception:
            pass

        # =====================================================================
        # STEP 15: Clear Commitment Protocol data
        # =====================================================================
        try:
            CommitmentProtocol.objects.filter(board__in=self.demo_boards).delete()
            UserCredibilityScore.objects.filter(user__in=self.demo_users).delete()
        except Exception:
            pass
        self.stdout.write('   ✓ Cleared Commitment Protocol data')

        # =====================================================================
        # STEP 16: Clear Decision Center data
        # =====================================================================
        try:
            from decision_center.models import (
                DecisionItem, DecisionCenterBriefing
            )
            from django.core.cache import cache as dc_cache

            # Delete all decision items for demo boards
            DecisionItem.objects.filter(board__in=self.demo_boards).delete()
            # Also delete any items created for demo users (board-less items)
            DecisionItem.objects.filter(created_for__in=self.demo_users).delete()
            # Delete briefings for demo users
            DecisionCenterBriefing.objects.filter(user__in=self.demo_users).delete()
            # Also clear items/briefings for ALL users tied to demo boards
            DecisionItem.objects.filter(
                board__is_official_demo_board=True
            ).delete()
            # Invalidate widget cache for all known users
            for u in self.demo_users:
                dc_cache.delete(f'dc_widget_{u.id}_demo')
                dc_cache.delete(f'dc_widget_{u.id}_real')
        except Exception:
            pass
        self.stdout.write('   ✓ Cleared Decision Center data')

        # =====================================================================
        # STEP 17: Clear What-If Scenario data
        # =====================================================================
        try:
            from kanban.whatif_models import WhatIfScenario
            WhatIfScenario.objects.filter(board__in=self.demo_boards).delete()
        except Exception:
            pass
        self.stdout.write('   ✓ Cleared What-If Scenario data')

        # =====================================================================
        # STEP 18: Clear Shadow Board data
        # =====================================================================
        try:
            from kanban.shadow_models import ShadowBranch, BranchSnapshot, BranchDivergenceLog
            BranchDivergenceLog.objects.filter(branch__board__in=self.demo_boards).delete()
            BranchSnapshot.objects.filter(branch__board__in=self.demo_boards).delete()
            ShadowBranch.objects.filter(board__in=self.demo_boards).delete()
        except Exception:
            pass
        self.stdout.write('   ✓ Cleared Shadow Board data')

        # =====================================================================
        # STEP 19: Clear Pre-Mortem data
        # =====================================================================
        try:
            from kanban.premortem_models import PreMortemAnalysis, PreMortemScenarioAcknowledgment
            PreMortemScenarioAcknowledgment.objects.filter(pre_mortem__board__in=self.demo_boards).delete()
            PreMortemAnalysis.objects.filter(board__in=self.demo_boards).delete()
        except Exception:
            pass
        self.stdout.write('   ✓ Cleared Pre-Mortem data')

        # =====================================================================
        # STEP 20: Clear Stress Test data
        # =====================================================================
        try:
            from kanban.stress_test_models import StressTestSession, ImmunityScore, StressTestScenario, Vaccine
            Vaccine.objects.filter(session__board__in=self.demo_boards).delete()
            StressTestScenario.objects.filter(session__board__in=self.demo_boards).delete()
            ImmunityScore.objects.filter(session__board__in=self.demo_boards).delete()
            StressTestSession.objects.filter(board__in=self.demo_boards).delete()
        except Exception:
            pass
        self.stdout.write('   ✓ Cleared Stress Test data')

        # =====================================================================
        # STEP 21: Clear Scope Autopsy data
        # =====================================================================
        try:
            from kanban.scope_autopsy_models import ScopeAutopsyReport, ScopeTimelineEvent
            ScopeTimelineEvent.objects.filter(report__board__in=self.demo_boards).delete()
            ScopeAutopsyReport.objects.filter(board__in=self.demo_boards).delete()
        except Exception:
            pass
        self.stdout.write('   ✓ Cleared Scope Autopsy data')

        # =====================================================================
        # STEP 22: Clear Exit Protocol data
        # =====================================================================
        try:
            from exit_protocol.models import (
                ProjectHealthSignal, HospiceSession, ProjectOrgan,
                OrganTransplant, CemeteryEntry, HospiceDismissal,
            )
            HospiceDismissal.objects.filter(board__in=self.demo_boards).delete()
            OrganTransplant.objects.filter(organ__source_board__in=self.demo_boards).delete()
            ProjectOrgan.objects.filter(source_board__in=self.demo_boards).delete()
            CemeteryEntry.objects.filter(board__in=self.demo_boards).delete()
            HospiceSession.objects.filter(board__in=self.demo_boards).delete()
            ProjectHealthSignal.objects.filter(board__in=self.demo_boards).delete()
        except Exception:
            pass
        self.stdout.write('   ✓ Cleared Exit Protocol data')

        self.stdout.write(self.style.SUCCESS('   ✓ All demo data cleared\n'))

    # =========================================================================
    # WIKI DEMO DATA
    # =========================================================================
    def create_wiki_demo_data(self):
        """Create wiki categories, pages, and links"""
        demo_user = self.alex
        
        # Create categories
        categories_data = self.get_wiki_categories_data()
        created_categories = {}
        
        for cat_data in categories_data:
            category, _ = WikiCategory.objects.update_or_create(
                organization=self.demo_org,
                slug=cat_data['slug'],
                defaults={
                    'name': cat_data['name'],
                    'description': cat_data['description'],
                    'icon': cat_data['icon'],
                    'color': cat_data['color'],
                    'ai_assistant_type': cat_data['ai_assistant_type'],
                    'position': cat_data['position'],
                }
            )
            created_categories[cat_data['slug']] = category

        # Create pages
        pages_data = self.get_wiki_pages_data()
        created_pages = []
        
        for page_data in pages_data:
            category = created_categories.get(page_data['category'])
            if not category:
                continue
            
            page, _ = WikiPage.objects.update_or_create(
                organization=self.demo_org,
                slug=page_data['slug'],
                defaults={
                    'title': page_data['title'],
                    'content': page_data['content'],
                    'category': category,
                    'created_by': demo_user,
                    'updated_by': demo_user,
                    'is_published': True,
                    'is_pinned': page_data.get('is_pinned', False),
                    'tags': page_data.get('tags', []),
                }
            )
            created_pages.append(page)

        # Create links to tasks
        links_created = self.create_wiki_links(demo_user)

        return {
            'categories': len(created_categories),
            'pages': len(created_pages),
            'links': links_created
        }

    def get_wiki_categories_data(self):
        """Wiki category configurations"""
        return [
            {'slug': 'getting-started', 'name': 'Getting Started', 'description': 'Onboarding and setup guides', 'icon': '🚀', 'color': '#3498db', 'ai_assistant_type': 'onboarding', 'position': 1},
            {'slug': 'technical-docs', 'name': 'Technical Documentation', 'description': 'API references and architecture', 'icon': '📖', 'color': '#2ecc71', 'ai_assistant_type': 'technical', 'position': 2},
            {'slug': 'meeting-notes', 'name': 'Meeting Notes', 'description': 'Sprint and team meeting notes', 'icon': '📝', 'color': '#9b59b6', 'ai_assistant_type': 'meetings', 'position': 3},
            {'slug': 'process-workflows', 'name': 'Process & Workflows', 'description': 'Standard procedures', 'icon': '⚙️', 'color': '#e74c3c', 'ai_assistant_type': 'process', 'position': 4},
            {'slug': 'project-resources', 'name': 'Project Resources', 'description': 'Roadmaps and requirements', 'icon': '📊', 'color': '#f39c12', 'ai_assistant_type': 'documentation', 'position': 5},
        ]

    def get_wiki_pages_data(self):
        """Wiki page configurations (condensed for brevity)"""
        current_date = timezone.now().strftime('%B %d, %Y')
        
        return [
            # Getting Started
            {
                'category': 'getting-started',
                'title': 'Welcome to Acme Corporation',
                'slug': 'welcome-to-acme',
                'is_pinned': True,
                'tags': ['onboarding', 'welcome'],
                'content': f"""# Welcome to Acme Corporation! 🎉

Welcome to the team! This knowledge hub contains everything you need to get started.

## Quick Links
- **[Team Setup Guide](team-setup-guide)** - Set up your development environment
- **[Coding Standards](coding-standards)** - Our code quality guidelines

## Who to Contact
| Role | Person | Contact |
|------|--------|---------|
| Project Manager | Alex Chen | alex.chen@acme.com |
| Lead Developer | Sam Rivera | sam.rivera@acme.com |

*Last updated: {current_date}*"""
            },
            {
                'category': 'getting-started',
                'title': 'Team Setup Guide',
                'slug': 'team-setup-guide',
                'tags': ['setup', 'environment'],
                'content': """# Team Setup Guide

## Prerequisites
- Python 3.10+ installed
- Node.js 18+ installed
- Git configured

## Quick Start
```bash
# Example repository (fictional — replace with your project URL)
git clone git@github.com:acme-corp/main-project.git
cd main-project
python -m venv venv
pip install -r requirements.txt
python manage.py migrate
```"""
            },
            # Technical Docs
            {
                'category': 'technical-docs',
                'title': 'API Documentation',
                'slug': 'api-documentation',
                'is_pinned': True,
                'tags': ['api', 'rest', 'reference'],
                'content': """# API Documentation

## Authentication
All API requests require JWT tokens.

```bash
POST /api/auth/token/
{
    "email": "user@example.com",
    "password": "your_password"
}
```

## Endpoints
| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/boards/` | List all boards |
| POST | `/api/tasks/` | Create task |"""
            },
            {
                'category': 'technical-docs',
                'title': 'Coding Standards',
                'slug': 'coding-standards',
                'tags': ['coding', 'standards'],
                'content': """# Coding Standards

## Python Standards
- Follow PEP 8
- Use type hints
- Docstrings for all public functions

## Code Review Checklist
- [ ] Code follows style guidelines
- [ ] All tests pass
- [ ] Documentation updated"""
            },
            # Meeting Notes
            {
                'category': 'meeting-notes',
                'title': 'Sprint 45 Planning Meeting',
                'slug': 'sprint-45-planning',
                'is_pinned': True,
                'tags': ['sprint', 'planning'],
                'content': f"""# Sprint 45 Planning Meeting

**Date:** {current_date}
**Attendees:** Alex Chen, Sam Rivera, Jordan Taylor

## Sprint Goals
1. Complete user authentication improvements
2. Launch new dashboard analytics
3. Fix critical bugs from Sprint 44

## High Priority
- AUTH-234: Implement password reset flow
- DASH-567: Add burndown chart widget"""
            },
            # Process & Workflows
            {
                'category': 'process-workflows',
                'title': 'Sprint Workflow Guide',
                'slug': 'sprint-workflow',
                'is_pinned': True,
                'tags': ['sprint', 'agile', 'scrum'],
                'content': """# Sprint Workflow Guide

## Sprint Timeline
- Week 1 Monday: Planning
- Daily: Standups at 9:30 AM
- Week 2 Thursday: Demo
- Week 2 Friday: Retrospective

## Task States
| State | Description | WIP Limit |
|-------|-------------|-----------|
| To Do | Ready to start | No limit |
| In Progress | Being worked on | 3/person |
| Done | Completed | No limit |"""
            },
            # Project Resources - dynamic quarter calculation
            {
                'category': 'project-resources',
                'title': f'{self._next_quarter_label()} Product Roadmap',
                'slug': f'{self._next_quarter_label().lower().replace(" ", "-")}-roadmap',
                'is_pinned': True,
                'tags': ['roadmap', 'planning'],
                'content': f"""# {self._next_quarter_label()} Product Roadmap

## Vision
"Enable teams to work smarter with AI-powered project management"

## Month 1: Foundation
- AI Task Suggestions v2
- Dashboard Redesign
- Performance Optimization

## Month 2: Enhancement
- Advanced Analytics
- Enterprise SSO

## Month 3: Growth
- AI Meeting Assistant
- Integration Marketplace"""
            },
        ]

    def create_wiki_links(self, demo_user):
        """Create links between wiki pages and tasks"""
        links_created = 0
        demo_tasks = Task.objects.filter(column__board__in=self.demo_boards)
        
        api_doc = WikiPage.objects.filter(organization=self.demo_org, slug='api-documentation').first()
        coding_standards = WikiPage.objects.filter(organization=self.demo_org, slug='coding-standards').first()
        
        if api_doc:
            api_tasks = demo_tasks.filter(title__icontains='api')[:3]
            for task in api_tasks:
                _, created = WikiLink.objects.get_or_create(
                    wiki_page=api_doc,
                    link_type='task',
                    task=task,
                    defaults={'created_by': demo_user, 'description': 'Related API documentation'}
                )
                if created:
                    links_created += 1

        if coding_standards:
            code_tasks = demo_tasks.filter(title__iregex=r'(code|review|implement)')[:3]
            for task in code_tasks:
                _, created = WikiLink.objects.get_or_create(
                    wiki_page=coding_standards,
                    link_type='task',
                    task=task,
                    defaults={'created_by': demo_user, 'description': 'Follow coding standards'}
                )
                if created:
                    links_created += 1

        return links_created

    # =========================================================================
    # MESSAGING DEMO DATA
    # =========================================================================
    def create_messaging_demo_data(self):
        """Create chat rooms, messages, and notifications"""
        rooms_created = 0
        messages_created = 0
        now = timezone.now()
        
        chat_configs = self.get_chat_room_configs()
        
        for board in self.demo_boards:
            board_name = board.name
            if board_name not in chat_configs:
                continue
            
            board_members = list(
                User.objects.filter(board_memberships__board=board)
            )
            creator = board_members[0] if board_members else self.alex
            
            for room_config in chat_configs[board_name]:
                room, created = ChatRoom.objects.get_or_create(
                    board=board,
                    name=room_config['name'],
                    defaults={
                        'description': room_config['description'],
                        'created_by': creator,
                    }
                )
                
                if created:
                    rooms_created += 1
                    for member in board_members:
                        room.members.add(member)
                
                # Create messages if none exist
                if ChatMessage.objects.filter(chat_room=room).count() == 0:
                    for msg_data in room_config['messages']:
                        author = self.get_user_by_key(msg_data['author'])
                        if author and author in board_members:
                            msg_time = now - timedelta(minutes=msg_data['minutes_ago'])
                            msg = ChatMessage.objects.create(
                                chat_room=room,
                                author=author,
                                content=msg_data['content'],
                            )
                            ChatMessage.objects.filter(pk=msg.pk).update(created_at=msg_time)
                            messages_created += 1
        
        return {'rooms': rooms_created, 'messages': messages_created}

    def get_user_by_key(self, key):
        """Get user by short key name"""
        return {
            'alex': self.alex,
            'sam': self.sam,
            'jordan': self.jordan,
        }.get(key)

    def get_chat_room_configs(self):
        """Chat room configurations for each board"""
        return {
            'Software Development': [
                {
                    'name': 'General Discussion',
                    'description': 'Team updates and announcements',
                    'messages': [
                        {'author': 'alex', 'content': 'Good morning team! 🌅 Ready for sprint planning?', 'minutes_ago': 360},
                        {'author': 'sam', 'content': 'Morning! Yes, I finished reviewing the backlog.', 'minutes_ago': 355},
                        {'author': 'jordan', 'content': 'Good morning! I have the architecture notes ready for the planning session.', 'minutes_ago': 350},
                        {'author': 'alex', 'content': 'Perfect. Let\'s prioritize the Auth System and API tasks first — those are blocking everything else.', 'minutes_ago': 340},
                        {'author': 'sam', 'content': 'Agreed. The Base API Framework is nearly done. We can start integration with Auth by tomorrow.', 'minutes_ago': 335},
                        {'author': 'jordan', 'content': 'I\'ll review the Auth design doc and flag any concerns before end of day.', 'minutes_ago': 330},
                        {'author': 'alex', 'content': 'Just updated the sprint board — 12 tasks assigned, 18 remaining. Looks manageable.', 'minutes_ago': 240},
                        {'author': 'sam', 'content': 'The Dashboard UI is coming together nicely. Should be ready for review by Thursday. 🎨', 'minutes_ago': 180},
                        {'author': 'jordan', 'content': 'Great work everyone! The API integration looks solid. 👏', 'minutes_ago': 120},
                        {'author': 'alex', 'content': 'Quick reminder: stakeholder demo is next Friday. Let\'s make sure the critical path tasks are green. 🟢', 'minutes_ago': 60},
                    ]
                },
                {
                    'name': 'Technical Support',
                    'description': 'Technical questions and debugging help',
                    'messages': [
                        {'author': 'sam', 'content': 'Has anyone encountered issues with PostgreSQL 15 migration?', 'minutes_ago': 480},
                        {'author': 'alex', 'content': 'Try `python manage.py migrate --fake-initial` first.', 'minutes_ago': 475},
                        {'author': 'sam', 'content': 'That worked! Thanks 🙏', 'minutes_ago': 470},
                        {'author': 'jordan', 'content': 'FYI — I updated the setup guide on the wiki with that fix. Check the Team Setup Guide page.', 'minutes_ago': 460},
                        {'author': 'sam', 'content': 'Quick question: are we using Redis for caching or just the default DB cache?', 'minutes_ago': 300},
                        {'author': 'alex', 'content': 'Redis in production, DB cache for local dev. Config is in settings/base.py.', 'minutes_ago': 295},
                        {'author': 'jordan', 'content': 'The Search & Indexing Engine task requires Elasticsearch. I\'ve added setup steps to the wiki.', 'minutes_ago': 200},
                        {'author': 'sam', 'content': 'Running into a rate-limiting edge case on the API. The tests pass but manual testing shows 429s under burst load.', 'minutes_ago': 120},
                        {'author': 'jordan', 'content': 'I\'ll take a look — might need to adjust the token bucket window. Can you share the test payload?', 'minutes_ago': 115},
                        {'author': 'sam', 'content': 'Pushed a repro script to the branch. Check `tests/test_rate_limit_burst.py`.', 'minutes_ago': 110},
                    ]
                },
            ],
        }

    # =========================================================================
    # CONFLICT DEMO DATA
    # =========================================================================
    def create_conflict_demo_data(self):
        """Create conflict detection demo data"""
        conflicts_created = 0
        resolutions_created = 0
        now = timezone.now()
        
        conflict_configs = self.get_conflict_configs()
        
        for board in self.demo_boards:
            board_name = board.name
            if board_name not in conflict_configs:
                continue
            
            tasks = list(Task.objects.filter(column__board=board)[:10])
            if not tasks:
                continue
            
            for config in conflict_configs[board_name]:
                # Get tasks for this conflict
                task1 = tasks[config.get('task1_idx', 0) % len(tasks)]
                task2_idx = config.get('task2_idx')
                task2 = tasks[task2_idx % len(tasks)] if task2_idx else None
                
                affected_user = self.get_user_by_key(config.get('affected_user', 'sam'))
                
                conflict = ConflictDetection.objects.create(
                    board=board,
                    conflict_type=config['type'],
                    severity=config['severity'],
                    title=config['title'],
                    description=config['description'],
                    status=config.get('status', 'active'),
                    ai_confidence_score=int(config.get('confidence', 0.85) * 100),
                    detected_at=now - timedelta(days=config.get('days_ago', 1)),
                    suggested_resolutions=[
                        {
                            'action': config.get('recommendation', ''),
                            'confidence': config.get('confidence', 0.85),
                        }
                    ],
                    conflict_data={
                        'task1_id': task1.id,
                        'task1_title': task1.title,
                        'task2_id': task2.id if task2 else None,
                        'task2_title': task2.title if task2 else None,
                        'user_id': affected_user.id if affected_user else None,
                        'user_name': affected_user.get_full_name() if affected_user else None,
                    }
                )
                
                # Add tasks
                conflict.tasks.add(task1)
                if task2:
                    conflict.tasks.add(task2)
                
                # Add affected user
                if affected_user:
                    conflict.affected_users.add(affected_user)
                
                conflicts_created += 1
                
                # Generate actual ConflictResolution objects for active conflicts
                if config.get('status') != 'resolved':
                    # Use ConflictResolutionSuggester to generate proper resolutions
                    from kanban.utils.conflict_detection import ConflictResolutionSuggester
                    suggester = ConflictResolutionSuggester(conflict)
                    generated_resolutions = suggester.generate_suggestions()
                    resolutions_created += len(generated_resolutions)
                else:
                    # Create resolution if already resolved
                    resolution = ConflictResolution.objects.create(
                        conflict=conflict,
                        resolution_type=config.get('resolution_type', 'custom'),
                        title=config.get('resolution_action', 'Manually resolved'),
                        description='Resolved after team discussion.',
                        ai_confidence=int(config.get('confidence', 0.85) * 100),
                        applied_by=self.alex,
                    )
                    # Update the conflict to point to this resolution
                    conflict.chosen_resolution = resolution
                    conflict.save()
                    resolutions_created += 1
        
        return {'conflicts': conflicts_created, 'resolutions': resolutions_created}

    def get_conflict_configs(self):
        """Conflict configurations for each board"""
        return {
            'Software Development': [
                {
                    'type': 'resource',
                    'severity': 'high',
                    'title': 'Resource Overload: Sam Rivera',
                    'description': 'Sam Rivera is assigned to 11 concurrent tasks, exceeding recommended capacity.',
                    'task1_idx': 0, 'task2_idx': 1,
                    'affected_user': 'sam',
                    'confidence': 0.92,
                    'recommendation': 'Consider redistributing 2-3 tasks to other team members.',
                },
                {
                    'type': 'dependency',
                    'severity': 'medium',
                    'title': 'Circular Dependency Detected',
                    'description': 'Task chain creates a circular dependency that may cause scheduling issues.',
                    'task1_idx': 2, 'task2_idx': 3,
                    'confidence': 0.88,
                    'recommendation': 'Review and break the dependency cycle.',
                },
            ],
        }

    # =========================================================================
    # AI ASSISTANT DEMO DATA
    # =========================================================================
    def create_ai_assistant_demo_data(self):
        """Create AI assistant sessions, messages, analytics, and recommendations"""
        sessions_created = 0
        messages_created = 0
        analytics_created = 0
        recommendations_created = 0
        kb_created = 0
        now = timezone.now()
        
        primary_user = self.alex
        
        # Create user preferences for all demo users
        for user in self.demo_users:
            UserPreference.objects.get_or_create(
                user=user,
                defaults={
                    'enable_web_search': True,
                    'enable_task_insights': True,
                    'enable_risk_alerts': True,
                    'enable_resource_recommendations': True,
                }
            )
        
        # Create sessions with rich data
        sessions_data = self.get_ai_sessions_data()
        
        for session_data in sessions_data:
            board = None
            if session_data.get('board') == 'software':
                board = self.software_board
            elif session_data.get('board') == 'marketing':
                board = self.marketing_board
            elif session_data.get('board') == 'bug':
                board = self.bug_board
            
            # Calculate tokens
            total_tokens = sum(msg_data.get('tokens', 150) for msg_data in session_data['messages'])
            
            session = AIAssistantSession.objects.create(
                user=primary_user,
                board=board,
                title=session_data['title'],
                description=session_data.get('description', ''),
                is_active=session_data.get('is_active', False),
                is_demo=True,  # Mark as demo session visible to all users
                message_count=len(session_data['messages']),
                total_tokens_used=total_tokens,
            )
            
            # Backdate session
            days_ago = session_data.get('days_ago', 0)
            backdated = now - timedelta(days=days_ago)
            AIAssistantSession.objects.filter(pk=session.pk).update(
                created_at=backdated, 
                updated_at=backdated
            )
            
            sessions_created += 1
            
            # Create messages with realistic timing
            for idx, msg_data in enumerate(session_data['messages']):
                msg_time = backdated + timedelta(minutes=idx * 2)
                msg = AIAssistantMessage.objects.create(
                    session=session,
                    role=msg_data['role'],
                    content=msg_data['content'],
                    model='gemini' if msg_data['role'] == 'assistant' else None,
                    tokens_used=msg_data.get('tokens', 150),
                    used_web_search=msg_data.get('web_search', False),
                    context_data={'knowledge_base_used': msg_data.get('kb_used', False)},
                )
                AIAssistantMessage.objects.filter(pk=msg.pk).update(created_at=msg_time)
                messages_created += 1
        
        # Create analytics for the last 30 days
        analytics_created = self.create_ai_analytics(primary_user)
        
        # Create knowledge base entries
        kb_created = self.create_knowledge_base()
        
        # Create task recommendations
        recommendations_created = self.create_task_recommendations()
        
        return {
            'sessions': sessions_created, 
            'messages': messages_created,
            'analytics': analytics_created,
            'knowledge_base': kb_created,
            'recommendations': recommendations_created,
        }
    
    def create_ai_analytics(self, user):
        """Create analytics data for the last 30 days"""
        from django.db import IntegrityError
        analytics_created = 0
        now = timezone.now()
        
        # First, delete any existing analytics for demo boards to avoid conflicts
        if self.software_board:
            AIAssistantAnalytics.objects.filter(board=self.software_board).delete()
        if self.marketing_board:
            AIAssistantAnalytics.objects.filter(board=self.marketing_board).delete()
        
        # Create analytics for last 31 days with realistic progression
        # Note: date field has auto_now_add=True, so we need to update it after creation
        for days_back in range(30, -1, -1):
            target_date = (now - timedelta(days=days_back)).date()
            
            # Vary activity by day (less on weekends)
            is_weekend = target_date.weekday() >= 5
            multiplier = 0.3 if is_weekend else 1.0
            
            # Always create analytics for software board (main board)
            if self.software_board:
                messages = max(1, int(random.randint(5, 15) * multiplier))
                gemini = messages
                kb_queries = max(1, int(random.randint(2, 8) * multiplier))
                web_searches = max(0, int(random.randint(1, 4) * multiplier))
                
                try:
                    with transaction.atomic():
                        obj = AIAssistantAnalytics.objects.create(
                            user=user,
                            board=self.software_board,
                            sessions_created=random.randint(1, 3),
                            messages_sent=messages,
                            gemini_requests=gemini,
                            web_searches_performed=web_searches,
                            knowledge_base_queries=kb_queries,
                            total_tokens_used=messages * random.randint(100, 250),
                            input_tokens=messages * random.randint(40, 80),
                            output_tokens=messages * random.randint(60, 170),
                            helpful_responses=int(messages * 0.8),
                            unhelpful_responses=int(messages * 0.1),
                            avg_response_time_ms=random.randint(800, 2500),
                        )
                        # Update the date field (bypasses auto_now_add)
                        AIAssistantAnalytics.objects.filter(pk=obj.pk).update(date=target_date)
                        analytics_created += 1
                except IntegrityError:
                    pass  # Record already exists
            
            # Create analytics for marketing board every 3-4 days
            if self.marketing_board and days_back % 3 == 0:
                messages = max(1, int(random.randint(2, 8) * multiplier))
                gemini = messages
                
                try:
                    with transaction.atomic():
                        obj = AIAssistantAnalytics.objects.create(
                            user=user,
                            board=self.marketing_board,
                            sessions_created=random.randint(0, 2),
                            messages_sent=messages,
                            gemini_requests=gemini,
                            web_searches_performed=max(0, int(random.randint(0, 2) * multiplier)),
                            knowledge_base_queries=max(1, int(random.randint(1, 4) * multiplier)),
                            total_tokens_used=messages * random.randint(100, 200),
                            input_tokens=messages * random.randint(40, 70),
                            output_tokens=messages * random.randint(60, 130),
                            helpful_responses=int(messages * 0.85),
                            unhelpful_responses=int(messages * 0.05),
                            avg_response_time_ms=random.randint(700, 2000),
                        )
                        # Update the date field (bypasses auto_now_add)
                        AIAssistantAnalytics.objects.filter(pk=obj.pk).update(date=target_date)
                        analytics_created += 1
                except IntegrityError:
                    pass  # Record already exists
        
        return analytics_created
    
    def create_knowledge_base(self):
        """Create knowledge base entries"""
        kb_created = 0
        demo_user = self.alex
        
        kb_entries = [
            {
                'board': self.software_board,
                'content_type': 'project_overview',
                'title': 'Software Development Sprint Goals',
                'content': 'Focus on user authentication, API development, and dashboard improvements. Team includes 3 members working on 2-week sprints.',
            },
            {
                'board': self.software_board,
                'content_type': 'risk_assessment',
                'title': 'Technical Debt Analysis',
                'content': 'Database migration pending. Security vulnerabilities identified in authentication module. Performance optimization needed for dashboard queries.',
            },
            {
                'board': self.marketing_board,
                'content_type': 'project_overview',
                'title': 'Q1 Marketing Campaign',
                'content': 'Social media campaign launch planned. Focus on brand awareness and lead generation. Budget allocated for ads and content creation.',
            },
            {
                'board': self.bug_board,
                'content_type': 'documentation',
                'title': 'Bug Tracking Process',
                'content': 'All production bugs should be logged immediately. Critical bugs require immediate attention. Security bugs must be escalated.',
            },
        ]
        
        for entry_data in kb_entries:
            if entry_data['board']:
                ProjectKnowledgeBase.objects.create(
                    board=entry_data['board'],
                    content_type=entry_data['content_type'],
                    title=entry_data['title'],
                    content=entry_data['content'],
                    summary=entry_data['content'][:200],
                    is_active=True,
                )
                kb_created += 1
        
        return kb_created
    
    def create_task_recommendations(self):
        """Create AI task recommendations"""
        recommendations_created = 0
        
        # Get some tasks from software board
        software_tasks = list(Task.objects.filter(column__board=self.software_board)[:5])
        
        if len(software_tasks) >= 3:
            # Optimization recommendation
            AITaskRecommendation.objects.create(
                task=software_tasks[0],
                board=self.software_board,
                recommendation_type='optimization',
                title='Consider breaking down this large task',
                description='This task has high complexity. Breaking it into smaller subtasks could improve tracking and reduce risk.',
                potential_impact='medium',
                confidence_score=Decimal('0.82'),
                suggested_action='Split into 3-4 smaller tasks focusing on: authentication logic, API integration, testing, documentation',
                expected_benefit='Better progress tracking, easier to assign, reduced delivery risk',
                status='pending',
            )
            recommendations_created += 1
            
            # Resource allocation recommendation
            AITaskRecommendation.objects.create(
                task=software_tasks[1],
                board=self.software_board,
                recommendation_type='resource_allocation',
                title='Sam Rivera may be overloaded',
                description='Sam Rivera is assigned to 8 concurrent tasks. This task might benefit from reassignment.',
                potential_impact='high',
                confidence_score=Decimal('0.89'),
                suggested_action='Consider reassigning to Jordan Taylor who has capacity',
                expected_benefit='Better workload distribution, faster task completion',
                status='pending',
            )
            recommendations_created += 1
            
            # Priority recommendation
            AITaskRecommendation.objects.create(
                task=software_tasks[2],
                board=self.software_board,
                recommendation_type='priority',
                title='This task blocks 3 other tasks',
                description='Several tasks depend on this one. Prioritizing it could unblock team progress.',
                potential_impact='high',
                confidence_score=Decimal('0.91'),
                suggested_action='Move to high priority and assign to available developer immediately',
                expected_benefit='Unblock dependent tasks, maintain sprint velocity',
                status='accepted',
            )
            recommendations_created += 1
        
        return recommendations_created

    def get_ai_sessions_data(self):
        """AI Assistant session configurations"""
        return [
            {
                'title': 'Sprint Planning Help',
                'description': 'Getting help with sprint planning',
                'is_active': True,
                'days_ago': 0,
                'board': 'software',
                'messages': [
                    {'role': 'user', 'content': 'What tasks should I prioritize for this sprint?', 'tokens': 80},
                    {'role': 'assistant', 'content': """Based on your current board status, I recommend prioritizing:

**High Priority:**
1. **Implement user authentication** - Blocking other features
2. **Design database schema** - Foundation task
3. **Fix critical security vulnerability** - Security first

**Medium Priority:**
4. **Build REST API endpoints** - Can proceed after auth
5. **Create responsive dashboard** - Good for parallel work

Would you like help with task estimation?""", 'tokens': 220, 'kb_used': True},
                    {'role': 'user', 'content': 'Yes, how long should the authentication task take?', 'tokens': 75},
                    {'role': 'assistant', 'content': """For the user authentication task, I estimate:

**Development:** 3-5 days
- Backend API: 2 days
- Frontend integration: 1-2 days
- Testing: 1 day

**Dependencies:** Database schema must be ready first.

**Risks:** Third-party OAuth integration may add 1-2 days if needed.

This assumes one developer working full-time. Should I create subtasks?""", 'tokens': 195, 'kb_used': True, 'web_search': False},
                ]
            },
            {
                'title': 'Team Workload Analysis',
                'description': 'Analyzing team capacity',
                'is_active': False,
                'days_ago': 2,
                'board': 'software',
                'messages': [
                    {'role': 'user', 'content': 'Is anyone on my team overloaded?', 'tokens': 60},
                    {'role': 'assistant', 'content': """I've analyzed the current workload:

| Team Member | Tasks | Hours | Utilization |
|-------------|-------|-------|-------------|
| Sam Rivera | 11 | 44h | ⚠️ 110% |
| Jordan Taylor | 12 | 38h | ✅ 95% |
| Alex Chen | 7 | 28h | ✅ 70% |

**⚠️ Alert:** Sam Rivera is overloaded with implementation tasks.

**Recommendation:** Reassign 1-2 implementation tasks from Sam to balance the workload.""", 'tokens': 245, 'kb_used': True},
                    {'role': 'user', 'content': 'Which tasks should I reassign?', 'tokens': 70},
                    {'role': 'assistant', 'content': """I recommend reassigning these tasks:

1. **Error Tracking & Monitoring** → Jordan Taylor - Configuration task, matches Jordan's QA skills
2. **Security Audit & Fixes** → Jordan Taylor - Testing-adjacent, complements Jordan's QA role

Both tasks are well-defined and don't require deep system knowledge. This will bring Sam down to 90% utilization while Jordan stays at a healthy 95%.""", 'tokens': 180, 'kb_used': True},
                ]
            },
            {
                'title': 'Bug Prioritization Strategy',
                'description': 'Help prioritizing bugs',
                'is_active': False,
                'days_ago': 1,
                'board': 'bug',
                'messages': [
                    {'role': 'user', 'content': 'How should I prioritize the bugs in our backlog?', 'tokens': 75},
                    {'role': 'assistant', 'content': """Here's a prioritization framework:

**🔴 Critical Priority (Fix Immediately)**
1. **Login Authentication Failure** - 100% users blocked
2. **Data Loss on Form Submit** - All submissions affected

**🟠 High Priority (This Sprint)**
3. **Dashboard Performance** - Page load > 10s
4. **Email Notifications** - Alerts not delivered

**🟡 Medium Priority (Next Sprint)**
5. **UI Alignment Issues** - Minor UX issues

Would you like a detailed fix plan?""", 'tokens': 230, 'kb_used': True},
                ]
            },
            {
                'title': 'Risk Assessment Query',
                'description': 'Checking project risks',
                'is_active': False,
                'days_ago': 5,
                'board': 'software',
                'messages': [
                    {'role': 'user', 'content': 'What are the biggest risks in my current sprint?', 'tokens': 75},
                    {'role': 'assistant', 'content': """I've identified these key risks:

**🔴 High Risk**
- **Database Migration** - Not started, blocks 5 tasks
- **Security Vulnerability** - Unpatched, production exposure

**🟠 Medium Risk**
- **API Dependencies** - External service reliability unknown
- **Resource Overallocation** - Sam Rivera at 112% capacity

**Mitigation Actions:**
1. Start database migration immediately
2. Apply security patch today
3. Rebalance Sam's workload

Would you like detailed mitigation plans?""", 'tokens': 280, 'kb_used': True, 'web_search': True},
                    {'role': 'user', 'content': 'Yes, give me the security patch details', 'tokens': 70},
                    {'role': 'assistant', 'content': """For the security vulnerability:

**Issue:** SQL injection vulnerability in user input validation
**Severity:** High - Production exposure
**Fix:** Update to Django 4.2.8 (patch available)

**Action Steps:**
1. Update requirements.txt: `Django==4.2.8`
2. Run: `pip install -r requirements.txt`
3. Test authentication flows
4. Deploy to staging, then production

**Time Estimate:** 2-3 hours including testing

This should be done today to prevent potential data breach.""", 'tokens': 240, 'web_search': True},
                ]
            },
            {
                'title': 'Marketing Campaign Insights',
                'description': 'Strategy discussion',
                'is_active': False,
                'days_ago': 7,
                'board': 'marketing',
                'messages': [
                    {'role': 'user', 'content': 'What should be our focus for the Q1 campaign?', 'tokens': 75},
                    {'role': 'assistant', 'content': """Based on your board and project goals:

**Primary Focus Areas:**
1. **Social Media Campaign** - 40% of budget
   - LinkedIn for B2B outreach
   - Twitter for product updates
   
2. **Content Marketing** - 30% of budget
   - Blog posts (2/week)
   - Case studies (1/month)
   
3. **Email Marketing** - 20% of budget
   - Newsletter series
   - Product announcements

**Success Metrics:**
- Lead generation: 500+ qualified leads
- Engagement rate: >5%
- Conversion rate: >2%

Should I help draft the campaign timeline?""", 'tokens': 320, 'kb_used': True, 'web_search': True},
                ]
            },
            {
                'title': 'Dependency Chain Analysis',
                'description': 'Checking task dependencies',
                'is_active': False,
                'days_ago': 3,
                'board': 'software',
                'messages': [
                    {'role': 'user', 'content': 'Show me the dependency chain for the API tasks', 'tokens': 75},
                    {'role': 'assistant', 'content': """Here's the dependency chain:

```
Database Schema Design
    ↓
User Authentication API
    ↓
    ├→ Dashboard API Endpoints
    ├→ Project Management API
    └→ Reporting API
        ↓
        Frontend Integration
```

**Critical Path:** Database → Auth → Dashboard (12 days)

**Parallel Work Possible:**
- Documentation can start now
- UI mockups independent of backend

**Bottleneck:** User Authentication API - blocks 3 major tasks

Priority should be: Schema first, then Auth immediately.""", 'tokens': 290, 'kb_used': True},
                ]
            },
        ]

    # =========================================================================
    # TIME TRACKING DEMO DATA
    # =========================================================================
    def create_time_tracking_demo_data(self):
        """Create comprehensive time tracking demo data for all demo users"""
        entries_created = 0
        now = timezone.now().date()
        
        # Time entry descriptions for variety
        descriptions = [
            "Worked on core implementation",
            "Code review and testing",
            "Bug fixing and debugging",
            "Feature development",
            "Documentation updates",
            "Meeting and planning session",
            "Research and analysis",
            "Deployment and configuration",
            "Performance optimization",
            "Unit testing",
            "Integration work",
            "Design review",
            "Sprint planning activities",
            "Client communication",
            "Technical documentation",
            "Code refactoring",
            "Security review",
            "Database optimization",
            "API development",
            "UI/UX improvements",
        ]
        
        # Create time entries for each demo user
        users_with_entries = set()
        
        for board in self.demo_boards:
            # Get tasks from this board that are in progress or done
            tasks = Task.objects.filter(
                column__board=board,
                progress__gt=0
            ).select_related('assigned_to')
            
            for task in tasks:
                # Determine which user should log time
                # Use assigned user or cycle through demo users
                if task.assigned_to in self.demo_users:
                    primary_user = task.assigned_to
                else:
                    # Assign to a random demo user
                    primary_user = random.choice(self.demo_users) if self.demo_users else None
                
                if not primary_user:
                    continue
                
                users_with_entries.add(primary_user.username)
                
                # Create 1-4 time entries per task based on progress
                num_entries = 1
                if task.progress >= 75:
                    num_entries = random.randint(2, 4)
                elif task.progress >= 50:
                    num_entries = random.randint(2, 3)
                elif task.progress >= 25:
                    num_entries = random.randint(1, 2)
                
                for i in range(num_entries):
                    # Hours based on task complexity and progress
                    base_hours = random.uniform(0.5, 4.0)
                    if hasattr(task, 'complexity') and task.complexity:
                        base_hours *= (1 + task.complexity * 0.1)
                    hours = Decimal(str(round(base_hours, 2)))
                    
                    # Spread entries over the last 14 days with realistic distribution
                    # More recent entries for tasks with higher progress
                    max_days_ago = 14 if task.progress < 50 else 7
                    days_ago = random.randint(0, max_days_ago)
                    entry_date = now - timedelta(days=days_ago)
                    
                    # Avoid weekends for more realistic data
                    while entry_date.weekday() >= 5:  # Saturday=5, Sunday=6
                        days_ago += 1
                        entry_date = now - timedelta(days=days_ago)
                    
                    description = random.choice(descriptions)
                    
                    # Check if entry already exists
                    existing = TimeEntry.objects.filter(
                        task=task,
                        user=primary_user,
                        work_date=entry_date
                    ).exists()
                    
                    if not existing:
                        TimeEntry.objects.create(
                            task=task,
                            user=primary_user,
                            hours_spent=hours,
                            description=f"{description} - {task.title[:30]}",
                            work_date=entry_date,
                        )
                        entries_created += 1
                
                # Occasionally add a secondary collaborator's time
                if task.progress >= 50 and random.random() < 0.3:
                    other_users = [u for u in self.demo_users if u != primary_user]
                    if other_users:
                        collaborator = random.choice(other_users)
                        users_with_entries.add(collaborator.username)
                        collab_hours = Decimal(str(round(random.uniform(0.5, 2.0), 2)))
                        collab_date = now - timedelta(days=random.randint(0, 7))
                        
                        # Avoid weekends
                        while collab_date.weekday() >= 5:
                            collab_date = collab_date - timedelta(days=1)
                        
                        existing = TimeEntry.objects.filter(
                            task=task,
                            user=collaborator,
                            work_date=collab_date
                        ).exists()
                        
                        if not existing:
                            TimeEntry.objects.create(
                                task=task,
                                user=collaborator,
                                hours_spent=collab_hours,
                                description=f"Collaboration on {task.title[:30]}",
                                work_date=collab_date,
                            )
                            entries_created += 1
        
        return {
            'entries': entries_created,
            'users': len(users_with_entries)
        }

    def create_extra_board_tasks(self):
        """
        Populate Marketing Campaign and Bug Tracking demo boards with 30 tasks each.
        Idempotent — skips boards that already have tasks.
        """
        today = date.today()
        creator = self.alex or User.objects.filter(is_superuser=True).first()
        stats = {'boards': 0, 'tasks': 0}

        # Refresh board references
        self.marketing_board = Board.objects.filter(
            organization=self.demo_org, is_official_demo_board=True,
            name__icontains='marketing',
        ).first()
        self.bug_board = Board.objects.filter(
            organization=self.demo_org, is_official_demo_board=True,
            name__icontains='bug',
        ).first()

        for board, tasks_data in [
            (self.marketing_board, self._marketing_tasks()),
            (self.bug_board, self._bug_tracking_tasks()),
        ]:
            if board is None:
                self.stdout.write(f'   ⚠️ Board not found, skipping')
                continue
            existing = Task.objects.filter(column__board=board).count()
            if existing >= 25:
                self.stdout.write(f'   [EXISTS] {board.name} already has {existing} tasks')
                stats['boards'] += 1
                stats['tasks'] += existing
                continue

            cols = {c.name: c for c in board.columns.all()}
            col_list = list(cols.values())
            if not col_list:
                self.stdout.write(f'   ⚠️ {board.name} has no columns')
                continue

            board.num_phases = 3
            board.save(update_fields=['num_phases'])

            board_tasks = 0
            for td in tasks_data:
                col = cols.get(td['column'], col_list[0])
                offset_start = td.get('start_offset', -30)
                offset_due = td.get('due_offset', 0)
                Task.objects.create(
                    column=col,
                    title=td['title'],
                    description=td.get('description', ''),
                    priority=td.get('priority', 'medium'),
                    complexity_score=td.get('complexity', 3),
                    assigned_to=td.get('assignee', creator),
                    created_by=creator,
                    progress=td.get('progress', 0),
                    start_date=today + timedelta(days=offset_start),
                    due_date=today + timedelta(days=offset_due),
                    phase=td.get('phase', 'Phase 1'),
                    is_seed_demo_data=True,
                )
                board_tasks += 1

            stats['boards'] += 1
            stats['tasks'] += board_tasks
            self.stdout.write(f'   ✅ {board.name}: {board_tasks} tasks created')

        # Create and assign labels for marketing and bug boards
        self._create_extra_board_labels()

        return stats

    def _create_extra_board_labels(self):
        """Create domain-specific + Lean labels for Marketing & Bug Tracking boards and assign to tasks."""
        import random as _rng

        MARKETING_LABELS = [
            {'name': 'Content', 'color': '#6366f1'},
            {'name': 'Paid Ads', 'color': '#f59e0b'},
            {'name': 'SEO', 'color': '#10b981'},
            {'name': 'Email', 'color': '#3b82f6'},
            {'name': 'Social Media', 'color': '#ec4899'},
            {'name': 'Analytics', 'color': '#8b5cf6'},
            {'name': 'Strategy', 'color': '#14b8a6'},
            {'name': 'Design', 'color': '#f97316'},
        ]
        BUG_LABELS = [
            {'name': 'Frontend', 'color': '#3b82f6'},
            {'name': 'Backend', 'color': '#6366f1'},
            {'name': 'API', 'color': '#14b8a6'},
            {'name': 'Security', 'color': '#dc3545'},
            {'name': 'Performance', 'color': '#f59e0b'},
            {'name': 'UX', 'color': '#ec4899'},
            {'name': 'Database', 'color': '#8b5cf6'},
            {'name': 'Regression', 'color': '#f97316'},
        ]
        LEAN_LABELS = [
            {'name': 'Value-Added', 'color': '#28a745', 'category': 'lean'},
            {'name': 'Necessary NVA', 'color': '#ffc107', 'category': 'lean'},
            {'name': 'Waste/Eliminate', 'color': '#dc3545', 'category': 'lean'},
            {'name': 'Kaizen (Improvement)', 'color': '#28a745', 'category': 'lean'},
            {'name': 'Poka-yoke (Error-Proofing)', 'color': '#6f42c1', 'category': 'lean'},
        ]

        KEYWORD_MAPS = {
            'marketing': {
                'Content': ['blog', 'content', 'case study', 'white paper', 'video', 'webinar'],
                'Paid Ads': ['ad', 'paid', 'campaign', 'launch', 'bid'],
                'SEO': ['seo', 'keyword', 'search', 'organic', 'rank'],
                'Email': ['email', 'nurture', 'drip', 'newsletter'],
                'Social Media': ['social', 'linkedin', 'twitter', 'meta', 'community'],
                'Analytics': ['analytics', 'tracking', 'utm', 'dashboard', 'report', 'kpi', 'metric'],
                'Strategy': ['strategy', 'research', 'persona', 'audience', 'planning', 'budget', 'review'],
                'Design': ['design', 'wireframe', 'creative', 'landing page', 'brand', 'visual'],
            },
            'bug': {
                'Frontend': ['ui', 'frontend', 'css', 'layout', 'display', 'visual', 'render', 'responsive', 'button', 'modal'],
                'Backend': ['backend', 'server', 'logic', 'process', 'service', 'handler', 'upload'],
                'API': ['api', 'endpoint', 'request', 'response', 'rest', 'webhook'],
                'Security': ['security', 'auth', 'permission', 'xss', 'injection', 'csrf', 'session', 'password', 'token'],
                'Performance': ['performance', 'slow', 'memory', 'leak', 'timeout', 'latency', 'load', 'cache', 'optimization'],
                'UX': ['ux', 'usability', 'accessibility', 'user experience', 'navigation', 'confus', 'overflow', 'truncat'],
                'Database': ['database', 'query', 'migration', 'index', 'data', 'sql'],
                'Regression': ['regression', 'broke', 'used to work', 'revert', 'intermittent', 'flak'],
            },
        }

        for board, custom_labels, board_type in [
            (self.marketing_board, MARKETING_LABELS, 'marketing'),
            (self.bug_board, BUG_LABELS, 'bug'),
        ]:
            if not board:
                continue

            all_labels = []
            for lbl in custom_labels + LEAN_LABELS:
                obj, _ = TaskLabel.objects.get_or_create(
                    board=board, name=lbl['name'],
                    defaults={'color': lbl['color'], 'category': lbl.get('category', '')},
                )
                all_labels.append(obj)

            custom_objs = [l for l in all_labels if l.name not in [x['name'] for x in LEAN_LABELS]]
            lean_objs = [l for l in all_labels if l.name in [x['name'] for x in LEAN_LABELS]]
            kw_map = KEYWORD_MAPS.get(board_type, {})

            for task in Task.objects.filter(column__board=board, item_type='task'):
                if task.labels.exists():
                    continue
                title_lower = task.title.lower()
                desc_lower = (task.description or '').lower()
                matching = []
                for label_name, keywords in kw_map.items():
                    if any(kw in title_lower or kw in desc_lower for kw in keywords):
                        obj = next((l for l in custom_objs if l.name == label_name), None)
                        if obj:
                            matching.append(obj)
                if not matching:
                    matching = _rng.sample(custom_objs, min(2, len(custom_objs)))
                for lbl in matching[:3]:
                    task.labels.add(lbl)
                # Lean label
                r = _rng.random()
                va = next((l for l in lean_objs if l.name == 'Value-Added'), None)
                nnva = next((l for l in lean_objs if l.name == 'Necessary NVA'), None)
                waste = next((l for l in lean_objs if l.name == 'Waste/Eliminate'), None)
                if r < 0.5 and va:
                    task.labels.add(va)
                elif r < 0.8 and nnva:
                    task.labels.add(nnva)
                elif waste:
                    task.labels.add(waste)

            self.stdout.write(f'   🏷️  Labels assigned for {board.name}')


    def _marketing_tasks(self):
        alex = self.alex
        sam = self.sam
        jordan = self.jordan
        return [
            # Phase 1: Strategy & Planning (10 tasks)
            {'title': 'Market Research & Competitive Analysis', 'description': 'Analyze competitors, identify market gaps, evaluate positioning opportunities across digital channels.', 'priority': 'high', 'complexity': 6, 'assignee': alex, 'progress': 100, 'column': 'Done', 'phase': 'Phase 1', 'start_offset': -40, 'due_offset': -35},
            {'title': 'Define Target Audience Personas', 'description': 'Create detailed buyer personas for enterprise, SMB, and individual user segments with pain points and goals.', 'priority': 'high', 'complexity': 5, 'assignee': jordan, 'progress': 100, 'column': 'Done', 'phase': 'Phase 1', 'start_offset': -38, 'due_offset': -33},
            {'title': 'Campaign Strategy & Budget Allocation', 'description': 'Define overall campaign strategy, set KPIs, allocate budget across channels (paid, organic, events).', 'priority': 'urgent', 'complexity': 7, 'assignee': alex, 'progress': 100, 'column': 'Done', 'phase': 'Phase 1', 'start_offset': -35, 'due_offset': -30},
            {'title': 'Brand Messaging & Value Proposition', 'description': 'Craft core messaging framework, taglines, and elevator pitches for each audience segment.', 'priority': 'high', 'complexity': 6, 'assignee': jordan, 'progress': 100, 'column': 'Done', 'phase': 'Phase 1', 'start_offset': -33, 'due_offset': -28},
            {'title': 'Content Calendar Development', 'description': 'Plan 90-day content calendar covering blog posts, social media, webinars, and case studies.', 'priority': 'medium', 'complexity': 4, 'assignee': sam, 'progress': 100, 'column': 'Done', 'phase': 'Phase 1', 'start_offset': -30, 'due_offset': -25},
            {'title': 'SEO Keyword Strategy', 'description': 'Research high-value keywords, map to content pillars, set up rank tracking dashboards.', 'priority': 'medium', 'complexity': 5, 'assignee': sam, 'progress': 80, 'column': 'Review', 'phase': 'Phase 1', 'start_offset': -28, 'due_offset': -22},
            {'title': 'Landing Page Wireframes', 'description': 'Design wireframes for campaign landing pages with A/B test variants for headlines and CTAs.', 'priority': 'high', 'complexity': 5, 'assignee': jordan, 'progress': 70, 'column': 'In Progress', 'phase': 'Phase 1', 'start_offset': -25, 'due_offset': -18},
            {'title': 'Email Nurture Sequence Design', 'description': 'Map out 6-email drip campaign for each persona with personalization tokens and triggers.', 'priority': 'medium', 'complexity': 4, 'assignee': alex, 'progress': 60, 'column': 'In Progress', 'phase': 'Phase 1', 'start_offset': -22, 'due_offset': -15},
            {'title': 'Social Media Ad Creative Brief', 'description': 'Prepare creative briefs for LinkedIn, Twitter/X, and Meta ad campaigns with targeting specs.', 'priority': 'medium', 'complexity': 3, 'assignee': sam, 'progress': 0, 'column': 'Backlog', 'phase': 'Phase 1', 'start_offset': -20, 'due_offset': -12},
            {'title': 'Campaign Analytics Setup', 'description': 'Configure UTM parameters, conversion tracking, attribution model, and reporting dashboards.', 'priority': 'high', 'complexity': 5, 'assignee': jordan, 'progress': 0, 'column': 'Backlog', 'phase': 'Phase 1', 'start_offset': -18, 'due_offset': -10},
            # Phase 2: Execution & Content (10 tasks)
            {'title': 'Blog Series: AI in Project Management', 'description': 'Write 5-part thought leadership blog series on AI-powered PM with SEO optimization.', 'priority': 'high', 'complexity': 6, 'assignee': jordan, 'progress': 40, 'column': 'In Progress', 'phase': 'Phase 2', 'start_offset': -15, 'due_offset': -5},
            {'title': 'Product Demo Video Production', 'description': 'Script, record, and edit 3-minute product demo video showcasing key features and AI capabilities.', 'priority': 'high', 'complexity': 7, 'assignee': sam, 'progress': 30, 'column': 'In Progress', 'phase': 'Phase 2', 'start_offset': -12, 'due_offset': 0},
            {'title': 'Customer Case Study Development', 'description': 'Interview 3 beta customers, write detailed case studies with metrics and testimonials.', 'priority': 'medium', 'complexity': 5, 'assignee': alex, 'progress': 0, 'column': 'Backlog', 'phase': 'Phase 2', 'start_offset': -10, 'due_offset': 3},
            {'title': 'Landing Page Development & Testing', 'description': 'Build responsive landing pages, integrate forms, set up A/B tests for conversion optimization.', 'priority': 'urgent', 'complexity': 6, 'assignee': sam, 'progress': 0, 'column': 'Backlog', 'phase': 'Phase 2', 'start_offset': -8, 'due_offset': 5},
            {'title': 'Email Campaign Setup & Automation', 'description': 'Build email sequences in marketing automation platform, test deliverability, configure triggers.', 'priority': 'high', 'complexity': 5, 'assignee': alex, 'progress': 0, 'column': 'Backlog', 'phase': 'Phase 2', 'start_offset': -5, 'due_offset': 8},
            {'title': 'Paid Ad Campaign Launch', 'description': 'Launch LinkedIn and Google Ads campaigns with initial bid strategy and audience targeting.', 'priority': 'high', 'complexity': 5, 'assignee': sam, 'progress': 0, 'column': 'Backlog', 'phase': 'Phase 2', 'start_offset': -3, 'due_offset': 10},
            {'title': 'Webinar Planning & Speaker Prep', 'description': 'Plan product launch webinar: speaker prep, slide deck, rehearsal, registration page.', 'priority': 'medium', 'complexity': 5, 'assignee': jordan, 'progress': 0, 'column': 'Backlog', 'phase': 'Phase 2', 'start_offset': 0, 'due_offset': 12},
            {'title': 'Social Media Content Batch Creation', 'description': 'Create 30 days of social posts across platforms with graphics, hashtags, and scheduling.', 'priority': 'medium', 'complexity': 4, 'assignee': jordan, 'progress': 0, 'column': 'Backlog', 'phase': 'Phase 2', 'start_offset': 2, 'due_offset': 14},
            {'title': 'Press Release & Media Outreach', 'description': 'Draft press release for product launch, build media list, pitch to tech journalists.', 'priority': 'medium', 'complexity': 4, 'assignee': alex, 'progress': 0, 'column': 'Backlog', 'phase': 'Phase 2', 'start_offset': 5, 'due_offset': 16},
            {'title': 'Partner Co-Marketing Campaign', 'description': 'Coordinate joint campaign with integration partners: co-branded content, cross-promotion.', 'priority': 'low', 'complexity': 4, 'assignee': alex, 'progress': 0, 'column': 'Backlog', 'phase': 'Phase 2', 'start_offset': 7, 'due_offset': 18},
            # Phase 3: Optimization & Scale (10 tasks)
            {'title': 'Campaign Performance Analysis', 'description': 'Weekly analysis of campaign metrics: CTR, CPC, conversion rates, ROAS across all channels.', 'priority': 'high', 'complexity': 5, 'assignee': alex, 'progress': 0, 'column': 'Backlog', 'phase': 'Phase 3', 'start_offset': 10, 'due_offset': 22},
            {'title': 'A/B Test Results & Optimization', 'description': 'Analyze landing page and email A/B test results, implement winning variants, plan next tests.', 'priority': 'high', 'complexity': 5, 'assignee': sam, 'progress': 0, 'column': 'Backlog', 'phase': 'Phase 3', 'start_offset': 12, 'due_offset': 24},
            {'title': 'Retargeting Campaign Setup', 'description': 'Set up retargeting pixels, create lookalike audiences, build retargeting ad sequences.', 'priority': 'medium', 'complexity': 4, 'assignee': sam, 'progress': 0, 'column': 'Backlog', 'phase': 'Phase 3', 'start_offset': 14, 'due_offset': 26},
            {'title': 'Lead Scoring Model Refinement', 'description': 'Refine lead scoring based on campaign data, adjust MQL/SQL thresholds, sync with sales.', 'priority': 'medium', 'complexity': 5, 'assignee': jordan, 'progress': 0, 'column': 'Backlog', 'phase': 'Phase 3', 'start_offset': 16, 'due_offset': 28},
            {'title': 'Influencer Partnership Program', 'description': 'Identify and recruit 5 industry influencers for product reviews and sponsored content.', 'priority': 'low', 'complexity': 4, 'assignee': alex, 'progress': 0, 'column': 'Backlog', 'phase': 'Phase 3', 'start_offset': 18, 'due_offset': 30},
            {'title': 'Content Repurposing Strategy', 'description': 'Convert top blog posts into infographics, short videos, podcasts, and LinkedIn carousels.', 'priority': 'low', 'complexity': 3, 'assignee': jordan, 'progress': 0, 'column': 'Backlog', 'phase': 'Phase 3', 'start_offset': 20, 'due_offset': 32},
            {'title': 'Community Building & Engagement', 'description': 'Launch Discord/Slack community, seed discussions, establish community guidelines and moderation.', 'priority': 'medium', 'complexity': 4, 'assignee': jordan, 'progress': 0, 'column': 'Backlog', 'phase': 'Phase 3', 'start_offset': 22, 'due_offset': 34},
            {'title': 'Post-Launch Webinar Series', 'description': 'Plan 4-part webinar series covering advanced use cases, customer stories, and best practices.', 'priority': 'medium', 'complexity': 4, 'assignee': alex, 'progress': 0, 'column': 'Backlog', 'phase': 'Phase 3', 'start_offset': 24, 'due_offset': 36},
            {'title': 'Campaign ROI Report & Recommendations', 'description': 'Compile comprehensive campaign report with ROI analysis, learnings, and Q2 recommendations.', 'priority': 'high', 'complexity': 6, 'assignee': alex, 'progress': 0, 'column': 'Backlog', 'phase': 'Phase 3', 'start_offset': 26, 'due_offset': 38},
            {'title': 'Marketing Automation Optimization', 'description': 'Review and optimize all automation workflows, clean up underperforming sequences, add new triggers.', 'priority': 'medium', 'complexity': 5, 'assignee': sam, 'progress': 0, 'column': 'Backlog', 'phase': 'Phase 3', 'start_offset': 28, 'due_offset': 40},
        ]

    def _bug_tracking_tasks(self):
        alex = self.alex
        sam = self.sam
        jordan = self.jordan
        return [
            # Phase 1: Critical & High Priority (10 tasks)
            {'title': 'Login Page Crashes on Safari iOS 17', 'description': 'Users report blank white screen on Safari iOS 17. Console shows TypeError in auth module. Affects ~12% of mobile users.', 'priority': 'urgent', 'complexity': 7, 'assignee': sam, 'progress': 100, 'column': 'Resolved', 'phase': 'Phase 1', 'start_offset': -40, 'due_offset': -37},
            {'title': 'Data Loss on Concurrent Board Edit', 'description': 'When two users edit the same task simultaneously, the second save overwrites the first without conflict resolution.', 'priority': 'urgent', 'complexity': 8, 'assignee': sam, 'progress': 100, 'column': 'Resolved', 'phase': 'Phase 1', 'start_offset': -38, 'due_offset': -34},
            {'title': 'API Rate Limiter Returns 500 Instead of 429', 'description': 'Rate limit exceeded requests return HTTP 500 instead of proper 429 with Retry-After header.', 'priority': 'high', 'complexity': 4, 'assignee': sam, 'progress': 100, 'column': 'Resolved', 'phase': 'Phase 1', 'start_offset': -36, 'due_offset': -32},
            {'title': 'Memory Leak in WebSocket Connection Pool', 'description': 'Long-running browser sessions cause memory growth of ~50 MB/hour due to unreleased WebSocket handlers.', 'priority': 'urgent', 'complexity': 8, 'assignee': sam, 'progress': 100, 'column': 'Resolved', 'phase': 'Phase 1', 'start_offset': -34, 'due_offset': -30},
            {'title': 'CSRF Token Mismatch After Session Timeout', 'description': 'Users get 403 errors after returning from idle. CSRF token in cookie doesn\'t match the one in the form.', 'priority': 'high', 'complexity': 5, 'assignee': jordan, 'progress': 100, 'column': 'Resolved', 'phase': 'Phase 1', 'start_offset': -32, 'due_offset': -28},
            {'title': 'Notification Badge Shows Wrong Count', 'description': 'Unread notification count includes dismissed items. Badge shows "12" when only 3 are unread.', 'priority': 'high', 'complexity': 4, 'assignee': jordan, 'progress': 80, 'column': 'In Progress', 'phase': 'Phase 1', 'start_offset': -30, 'due_offset': -25},
            {'title': 'File Upload Fails for Names with Unicode', 'description': 'Uploading files with Japanese/Korean characters in filename causes 500 error. Path encoding issue.', 'priority': 'high', 'complexity': 5, 'assignee': sam, 'progress': 70, 'column': 'In Progress', 'phase': 'Phase 1', 'start_offset': -28, 'due_offset': -22},
            {'title': 'Gantt Chart Overlapping Task Bars', 'description': 'Tasks with identical start/end dates render on top of each other instead of stacking vertically.', 'priority': 'medium', 'complexity': 5, 'assignee': jordan, 'progress': 50, 'column': 'In Progress', 'phase': 'Phase 1', 'start_offset': -25, 'due_offset': -18},
            {'title': 'Dark Mode Color Contrast Failures', 'description': 'Several UI elements fail WCAG AA contrast ratio in dark mode: sidebar labels, input borders, muted text.', 'priority': 'medium', 'complexity': 4, 'assignee': jordan, 'progress': 0, 'column': 'Triaged', 'phase': 'Phase 1', 'start_offset': -22, 'due_offset': -15},
            {'title': 'Search Indexing Delay of 30+ Minutes', 'description': 'Newly created tasks don\'t appear in search results for 30+ minutes. Index refresh interval too long.', 'priority': 'high', 'complexity': 5, 'assignee': sam, 'progress': 0, 'column': 'Triaged', 'phase': 'Phase 1', 'start_offset': -20, 'due_offset': -12},
            # Phase 2: Medium Priority (10 tasks)
            {'title': 'Drag-and-Drop Fails on Touch Devices', 'description': 'Kanban card drag-and-drop doesn\'t work on iPad/Android tablets. Touch events not properly handled.', 'priority': 'high', 'complexity': 6, 'assignee': sam, 'progress': 30, 'column': 'In Progress', 'phase': 'Phase 2', 'start_offset': -15, 'due_offset': -5},
            {'title': 'Email Notifications Sent in Wrong Timezone', 'description': 'Scheduled notification emails use UTC instead of user\'s configured timezone. Due dates appear wrong.', 'priority': 'medium', 'complexity': 4, 'assignee': jordan, 'progress': 0, 'column': 'Triaged', 'phase': 'Phase 2', 'start_offset': -12, 'due_offset': 0},
            {'title': 'Board Export CSV Missing Task Descriptions', 'description': 'CSV export includes all columns except task description. Field omitted from serializer.', 'priority': 'medium', 'complexity': 2, 'assignee': sam, 'progress': 0, 'column': 'Triaged', 'phase': 'Phase 2', 'start_offset': -10, 'due_offset': 3},
            {'title': 'Infinite Scroll Loads Duplicate Tasks', 'description': 'Scrolling board list view shows duplicate tasks when new items are created during pagination.', 'priority': 'medium', 'complexity': 5, 'assignee': sam, 'progress': 0, 'column': 'New', 'phase': 'Phase 2', 'start_offset': -8, 'due_offset': 5},
            {'title': 'Profile Image Upload Crops Incorrectly', 'description': 'Avatar crop tool doesn\'t preserve aspect ratio on non-square images. Faces get squished.', 'priority': 'low', 'complexity': 3, 'assignee': jordan, 'progress': 0, 'column': 'New', 'phase': 'Phase 2', 'start_offset': -5, 'due_offset': 8},
            {'title': 'Automation Rule Triggers Twice on Rapid Edit', 'description': 'Editing a task field twice within 1 second triggers the automation rule twice, creating duplicate actions.', 'priority': 'high', 'complexity': 6, 'assignee': sam, 'progress': 0, 'column': 'Triaged', 'phase': 'Phase 2', 'start_offset': -3, 'due_offset': 10},
            {'title': 'Calendar Event Duration Off by 1 Hour DST', 'description': 'Events created near DST transition show duration 1 hour shorter/longer than configured.', 'priority': 'medium', 'complexity': 5, 'assignee': jordan, 'progress': 0, 'column': 'New', 'phase': 'Phase 2', 'start_offset': 0, 'due_offset': 12},
            {'title': 'Markdown Renderer XSS in Task Description', 'description': 'Crafted markdown with nested HTML bypasses sanitizer. Script tags execute in description preview.', 'priority': 'urgent', 'complexity': 6, 'assignee': sam, 'progress': 0, 'column': 'Triaged', 'phase': 'Phase 2', 'start_offset': 2, 'due_offset': 5},
            {'title': 'Board Favorite Toggle Requires Page Refresh', 'description': 'Clicking the star icon toggles favorite in DB but the star icon doesn\'t update until page reload.', 'priority': 'low', 'complexity': 2, 'assignee': jordan, 'progress': 0, 'column': 'New', 'phase': 'Phase 2', 'start_offset': 5, 'due_offset': 16},
            {'title': 'Bulk Task Delete Ignores Permission Check', 'description': 'Members can bulk-delete tasks they shouldn\'t be able to. Individual delete works; bulk bypasses RBAC.', 'priority': 'high', 'complexity': 5, 'assignee': sam, 'progress': 0, 'column': 'Triaged', 'phase': 'Phase 2', 'start_offset': 7, 'due_offset': 14},
            # Phase 3: Low Priority & Polish (10 tasks)
            {'title': 'Tooltip Flickers on Fast Mouse Movement', 'description': 'Task card tooltips rapidly show/hide when moving mouse between adjacent cards. Needs debounce.', 'priority': 'low', 'complexity': 2, 'assignee': jordan, 'progress': 0, 'column': 'New', 'phase': 'Phase 3', 'start_offset': 10, 'due_offset': 22},
            {'title': 'Keyboard Shortcut Help Modal Outdated', 'description': 'Command palette (Ctrl+K) shows shortcuts that no longer exist + missing new shortcuts.', 'priority': 'low', 'complexity': 2, 'assignee': jordan, 'progress': 0, 'column': 'New', 'phase': 'Phase 3', 'start_offset': 12, 'due_offset': 24},
            {'title': 'Slow Page Load on Boards with 200+ Tasks', 'description': 'Board detail page takes 8+ seconds to render with 200 tasks. Need lazy loading or virtual scroll.', 'priority': 'high', 'complexity': 7, 'assignee': sam, 'progress': 0, 'column': 'Triaged', 'phase': 'Phase 3', 'start_offset': 14, 'due_offset': 26},
            {'title': 'Comment Timestamp Shows "NaN" for Old Tasks', 'description': 'Comments created before timezone migration show "NaN minutes ago" instead of formatted date.', 'priority': 'medium', 'complexity': 3, 'assignee': jordan, 'progress': 0, 'column': 'New', 'phase': 'Phase 3', 'start_offset': 16, 'due_offset': 28},
            {'title': 'PDF Export Truncates Long Task Titles', 'description': 'Analytics PDF export cuts off task titles at 50 chars without ellipsis. Layout breaks on 2-line titles.', 'priority': 'medium', 'complexity': 3, 'assignee': sam, 'progress': 0, 'column': 'New', 'phase': 'Phase 3', 'start_offset': 18, 'due_offset': 30},
            {'title': 'Stale Cache After Board Member Role Change', 'description': 'Changing a user\'s role from viewer to member doesn\'t invalidate permission cache. User still blocked until cache expires.', 'priority': 'high', 'complexity': 5, 'assignee': sam, 'progress': 0, 'column': 'Triaged', 'phase': 'Phase 3', 'start_offset': 20, 'due_offset': 28},
            {'title': 'Missing Alt Text on Dashboard Charts', 'description': 'Chart.js canvas elements have no aria-label or alt text. Screen readers skip analytics entirely.', 'priority': 'medium', 'complexity': 3, 'assignee': jordan, 'progress': 0, 'column': 'New', 'phase': 'Phase 3', 'start_offset': 22, 'due_offset': 34},
            {'title': 'Webhook Retry Backoff Capped Too Low', 'description': 'Max retry delay is 60 seconds when it should be exponential up to 1 hour. Hammers failing endpoints.', 'priority': 'medium', 'complexity': 3, 'assignee': sam, 'progress': 0, 'column': 'Triaged', 'phase': 'Phase 3', 'start_offset': 24, 'due_offset': 34},
            {'title': 'Tab Title Doesn\'t Update on Navigation', 'description': 'Browser tab always shows "PrizmAI" regardless of which page is active. Should show board/page name.', 'priority': 'low', 'complexity': 2, 'assignee': jordan, 'progress': 0, 'column': 'New', 'phase': 'Phase 3', 'start_offset': 26, 'due_offset': 38},
            {'title': 'API Docs Missing Rate Limit Headers', 'description': 'Swagger/OpenAPI spec doesn\'t document X-RateLimit-Remaining and X-RateLimit-Reset response headers.', 'priority': 'low', 'complexity': 2, 'assignee': sam, 'progress': 0, 'column': 'New', 'phase': 'Phase 3', 'start_offset': 28, 'due_offset': 40},
        ]

    def seed_demo_organization_goal(self):
        """
        Create (or ensure) a demo Organization Goal and link the demo Mission to it.
        Idempotent — safe to run multiple times.
        """
        creator = self.alex or User.objects.filter(is_superuser=True).first()

        # --- Organization Goal ---
        goal, created = OrganizationGoal.objects.get_or_create(
            name='Increase Market Share in Asia by 15%',
            defaults=dict(
                description=(
                    'Capture 15% of the Asia-Pacific enterprise security market within 24 months '
                    'by launching localized AI-driven security products, building a regional partner '
                    'ecosystem, and establishing brand recognition in key markets including India, '
                    'Japan, and Singapore.'
                ),
                target_metric='15% market share increase in Asia-Pacific',
                status='active',
                organization=self.demo_org,
                created_by=creator,
                is_demo=True,
                is_seed_demo_data=True,
            )
        )

        # --- Link the demo Mission to this Goal ---
        linked_count = Mission.objects.filter(
            name='Build Enterprise Security Platform',
            is_seed_demo_data=True,
        ).exclude(organization_goal=goal).update(organization_goal=goal)

        action = 'created' if created else 'already exists'
        self.stdout.write(
            f'   Organization Goal "{goal.name}" ({action}) | '
            f'Missions linked/updated: {linked_count}'
        )

    def seed_demo_mission_strategy(self):
        """
        Create (or ensure) a demo Mission and Strategy and link all official
        demo boards to the Strategy. Idempotent — safe to run multiple times.
        """
        creator = self.alex or User.objects.filter(is_superuser=True).first()

        # --- Mission ---
        mission, _ = Mission.objects.get_or_create(
            name='Build Enterprise Security Platform',
            defaults=dict(
                description=(
                    'Enterprise security threats are growing rapidly, especially with the increasing adoption '
                    'of AI tools. This Mission focuses on building a robust platform that helps organizations '
                    'identify, monitor, and eliminate security vulnerabilities across their infrastructure.'
                ),
                status='active',
                created_by=creator,
                is_demo=True,
                is_seed_demo_data=True,
            )
        )

        # --- Strategy ---
        strategy, _ = Strategy.objects.get_or_create(
            name='Develop Security Software Platform',
            mission=mission,
            defaults=dict(
                description=(
                    'Build a comprehensive enterprise software platform with built-in security features '
                    'including real-time threat detection, automated vulnerability scanning, '
                    'and secure user management with role-based access controls.'
                ),
                status='active',
                created_by=creator,
                is_seed_demo_data=True,
            )
        )

        # --- Link all official demo boards to the Strategy ---
        linked = 0
        for board in self.demo_boards:
            if board.strategy_id != strategy.id:
                board.strategy = strategy
                board.save(update_fields=['strategy'])
                linked += 1

        self.stdout.write(
            f'   Mission: "{mission.name}" | Strategy: "{strategy.name}" | '
            f'Boards linked: {linked}'
        )

    # =========================================================================
    # AI TOOLS DEMO DATA (What-If, Shadow Board, Pre-Mortem, Stress Test,
    #                      Scope Autopsy, Exit Protocol)
    # =========================================================================
    def create_ai_tools_demo_data(self):
        """Create demo data for all AI Tools features on the Software Development board."""
        now = timezone.now()
        board = self.software_board
        alex = self.alex
        sam = self.sam
        jordan = self.jordan

        if not board:
            self.stdout.write(self.style.WARNING('   ⚠️ Software Development board not found, skipping AI tools'))
            return {'whatif': 0, 'shadow_branches': 0, 'premortem': 0, 'stress_tests': 0, 'scope_autopsies': 0, 'exit_protocol': 0}

        stats = {'whatif': 0, 'shadow_branches': 0, 'premortem': 0, 'stress_tests': 0, 'scope_autopsies': 0, 'exit_protocol': 0}

        # -----------------------------------------------------------------
        # 1. WHAT-IF SCENARIOS
        # -----------------------------------------------------------------
        try:
            from kanban.whatif_models import WhatIfScenario

            whatif_scenarios = [
                {
                    'name': 'Add Mobile App Module (+8 tasks)',
                    'scenario_type': 'scope_change',
                    'created_by': alex,
                    'input_parameters': {
                        'tasks_added': 8,
                        'team_size_delta': 0,
                        'deadline_shift_days': 0,
                    },
                    'baseline_snapshot': {
                        'total_tasks': 30,
                        'completed_tasks': 10,
                        'in_progress_tasks': 8,
                        'team_size': 3,
                        'current_velocity': 4.2,
                        'deadline': (now + timedelta(days=45)).isoformat(),
                    },
                    'impact_results': {
                        'before': {'completion_date': (now + timedelta(days=38)).strftime('%Y-%m-%d'), 'workload_per_member': 6.7, 'risk_level': 'medium'},
                        'after': {'completion_date': (now + timedelta(days=52)).strftime('%Y-%m-%d'), 'workload_per_member': 9.3, 'risk_level': 'high'},
                        'delta': {'days_added': 14, 'workload_increase_pct': 39, 'risk_escalation': True},
                    },
                    'ai_analysis': {
                        'summary': 'Adding 8 mobile app tasks will push the projected completion by ~2 weeks. The current team velocity of 4.2 tasks/week means the new scope requires roughly 2 additional sprints. Consider adding a mobile-focused developer or deferring the mobile module to Phase 2.',
                        'risk_factors': ['Increased workload per team member exceeds sustainable threshold', 'Mobile development requires specialized skills not fully covered by current team', 'Testing effort will grow non-linearly with cross-platform requirements'],
                        'recommendations': ['Hire a contract mobile developer for 6 weeks', 'Split mobile app into MVP and full-feature phases', 'Extend deadline by 2 weeks to maintain quality standards'],
                    },
                    'is_starred': True,
                },
                {
                    'name': 'Reduce Team by 1 Member',
                    'scenario_type': 'team_change',
                    'created_by': sam,
                    'input_parameters': {
                        'tasks_added': 0,
                        'team_size_delta': -1,
                        'deadline_shift_days': 0,
                    },
                    'baseline_snapshot': {
                        'total_tasks': 30,
                        'completed_tasks': 10,
                        'in_progress_tasks': 8,
                        'team_size': 3,
                        'current_velocity': 4.2,
                        'deadline': (now + timedelta(days=45)).isoformat(),
                    },
                    'impact_results': {
                        'before': {'completion_date': (now + timedelta(days=38)).strftime('%Y-%m-%d'), 'workload_per_member': 6.7, 'risk_level': 'medium'},
                        'after': {'completion_date': (now + timedelta(days=55)).strftime('%Y-%m-%d'), 'workload_per_member': 10.0, 'risk_level': 'high'},
                        'delta': {'days_added': 17, 'workload_increase_pct': 49, 'risk_escalation': True},
                    },
                    'ai_analysis': {
                        'summary': 'Losing one team member drops velocity from 4.2 to ~2.8 tasks/week. The 20 remaining tasks would take an additional 2.5 weeks. Critical path items like Authentication System and Database Schema currently assigned to Sam Rivera would need redistribution.',
                        'risk_factors': ['Single points of failure on security-critical tasks', 'Remaining members may face burnout with 49% workload increase', 'Knowledge silos in backend architecture'],
                        'recommendations': ['Redistribute tasks based on skill overlap analysis', 'Prioritize critical path items and defer low-priority tasks', 'Consider part-time contractor to bridge the gap'],
                    },
                    'is_starred': False,
                },
                {
                    'name': 'Extend Deadline by 3 Weeks + Add QA Tasks',
                    'scenario_type': 'combined',
                    'created_by': jordan,
                    'input_parameters': {
                        'tasks_added': 4,
                        'team_size_delta': 0,
                        'deadline_shift_days': 21,
                    },
                    'baseline_snapshot': {
                        'total_tasks': 30,
                        'completed_tasks': 10,
                        'in_progress_tasks': 8,
                        'team_size': 3,
                        'current_velocity': 4.2,
                        'deadline': (now + timedelta(days=45)).isoformat(),
                    },
                    'impact_results': {
                        'before': {'completion_date': (now + timedelta(days=38)).strftime('%Y-%m-%d'), 'workload_per_member': 6.7, 'risk_level': 'medium'},
                        'after': {'completion_date': (now + timedelta(days=51)).strftime('%Y-%m-%d'), 'workload_per_member': 8.0, 'risk_level': 'low'},
                        'delta': {'days_added': 13, 'workload_increase_pct': 19, 'risk_escalation': False},
                    },
                    'ai_analysis': {
                        'summary': 'This is the safest combined option. Adding 4 QA tasks with a 3-week deadline extension keeps workload within sustainable limits. The extra time allows for comprehensive integration testing, security audits, and performance optimization without rushing the team.',
                        'risk_factors': ['Extended timeline may impact stakeholder expectations', 'QA tasks could uncover issues requiring additional rework'],
                        'recommendations': ['Communicate updated timeline to stakeholders proactively', 'Use the buffer to implement automated regression tests', 'Schedule a mid-sprint checkpoint to validate QA progress'],
                    },
                    'is_starred': True,
                },
            ]

            for scenario_data in whatif_scenarios:
                WhatIfScenario.objects.update_or_create(
                    board=board,
                    name=scenario_data['name'],
                    defaults={
                        'created_by': scenario_data['created_by'],
                        'scenario_type': scenario_data['scenario_type'],
                        'input_parameters': scenario_data['input_parameters'],
                        'baseline_snapshot': scenario_data['baseline_snapshot'],
                        'impact_results': scenario_data['impact_results'],
                        'ai_analysis': scenario_data['ai_analysis'],
                        'is_starred': scenario_data['is_starred'],
                    },
                )
                stats['whatif'] += 1
            self.stdout.write('   ✓ What-If Scenarios created')
        except Exception as e:
            self.stdout.write(self.style.WARNING(f'   ⚠️ What-If Scenarios: {e}'))

        # -----------------------------------------------------------------
        # 2. SHADOW BRANCHES
        # -----------------------------------------------------------------
        try:
            from kanban.shadow_models import ShadowBranch, BranchSnapshot, BranchDivergenceLog
            from kanban.whatif_models import WhatIfScenario

            # Get the starred scope_change scenario to link as source
            source_scenario = WhatIfScenario.objects.filter(
                board=board, name='Add Mobile App Module (+8 tasks)'
            ).first()

            branches = [
                {
                    'name': 'Mobile-First Launch',
                    'description': 'Explores prioritizing the mobile app module alongside web development, sharing API resources across platforms.',
                    'created_by': alex,
                    'status': 'active',
                    'source_scenario': source_scenario,
                    'branch_color': '#0d6efd',
                    'is_starred': True,
                    'snapshots': [
                        {
                            'scope_delta': 8, 'team_delta': 0, 'deadline_delta_weeks': 2,
                            'feasibility_score': 62, 'projected_completion_date': (now + timedelta(days=52)).date(),
                            'projected_budget_utilization': 87.5,
                            'conflicts_detected': {'resource_conflicts': 2, 'details': ['Sam Rivera over-allocated by 15 hours', 'QA pipeline bottleneck in Week 6']},
                            'gemini_recommendation': 'Consider adding a mobile developer or shifting 2 non-critical web tasks to next sprint to free capacity.',
                            'days_ago': 5,
                        },
                        {
                            'scope_delta': 8, 'team_delta': 1, 'deadline_delta_weeks': 2,
                            'feasibility_score': 74, 'projected_completion_date': (now + timedelta(days=48)).date(),
                            'projected_budget_utilization': 92.0,
                            'conflicts_detected': {'resource_conflicts': 1, 'details': ['QA pipeline bottleneck in Week 6']},
                            'gemini_recommendation': 'With an additional team member, feasibility improves significantly. Main risk is now QA throughput.',
                            'days_ago': 2,
                        },
                    ],
                },
                {
                    'name': 'Lean MVP Approach',
                    'description': 'Strips scope to bare essentials: core API, auth, and dashboard. Defers file upload, real-time collab, and caching to Phase 2.',
                    'created_by': sam,
                    'status': 'active',
                    'source_scenario': None,
                    'branch_color': '#198754',
                    'is_starred': False,
                    'snapshots': [
                        {
                            'scope_delta': -6, 'team_delta': 0, 'deadline_delta_weeks': -1,
                            'feasibility_score': 89, 'projected_completion_date': (now + timedelta(days=31)).date(),
                            'projected_budget_utilization': 68.0,
                            'conflicts_detected': {'resource_conflicts': 0, 'details': []},
                            'gemini_recommendation': 'Lean MVP has high feasibility. Ship early and gather user feedback before building Phase 2 features.',
                            'days_ago': 3,
                        },
                    ],
                },
                {
                    'name': 'Extended QA Timeline',
                    'description': 'Keeps full scope but adds 3 weeks for dedicated QA, security audit, and load testing. Based on the combined deadline extension scenario.',
                    'created_by': jordan,
                    'status': 'archived',
                    'source_scenario': None,
                    'branch_color': '#6f42c1',
                    'is_starred': False,
                    'snapshots': [
                        {
                            'scope_delta': 4, 'team_delta': 0, 'deadline_delta_weeks': 3,
                            'feasibility_score': 81, 'projected_completion_date': (now + timedelta(days=55)).date(),
                            'projected_budget_utilization': 78.0,
                            'conflicts_detected': {'resource_conflicts': 0, 'details': []},
                            'gemini_recommendation': 'This approach balances quality and delivery. The extra QA time significantly reduces post-launch defect risk.',
                            'days_ago': 7,
                        },
                    ],
                },
            ]

            for branch_data in branches:
                branch, _ = ShadowBranch.objects.update_or_create(
                    board=board,
                    name=branch_data['name'],
                    defaults={
                        'description': branch_data['description'],
                        'created_by': branch_data['created_by'],
                        'status': branch_data['status'],
                        'source_scenario': branch_data['source_scenario'],
                        'branch_color': branch_data['branch_color'],
                        'is_starred': branch_data['is_starred'],
                    },
                )
                stats['shadow_branches'] += 1

                # Create snapshots (delete old ones first for idempotency)
                branch.snapshots.all().delete()
                prev_score = None
                for snap_data in branch_data['snapshots']:
                    snap = BranchSnapshot.objects.create(
                        branch=branch,
                        scope_delta=snap_data['scope_delta'],
                        team_delta=snap_data['team_delta'],
                        deadline_delta_weeks=snap_data['deadline_delta_weeks'],
                        feasibility_score=snap_data['feasibility_score'],
                        projected_completion_date=snap_data['projected_completion_date'],
                        projected_budget_utilization=snap_data['projected_budget_utilization'],
                        conflicts_detected=snap_data['conflicts_detected'],
                        gemini_recommendation=snap_data['gemini_recommendation'],
                    )
                    # Backdate the snapshot
                    BranchSnapshot.objects.filter(pk=snap.pk).update(
                        captured_at=now - timedelta(days=snap_data['days_ago'])
                    )

                    # Create divergence log if score changed
                    if prev_score is not None and prev_score != snap_data['feasibility_score']:
                        BranchDivergenceLog.objects.create(
                            branch=branch,
                            old_score=prev_score,
                            new_score=snap_data['feasibility_score'],
                            trigger_event=f'Board recalculation after scope/team adjustment',
                        )
                    prev_score = snap_data['feasibility_score']

            self.stdout.write('   ✓ Shadow Branches created')
        except Exception as e:
            self.stdout.write(self.style.WARNING(f'   ⚠️ Shadow Branches: {e}'))

        # -----------------------------------------------------------------
        # 3. PRE-MORTEM ANALYSIS
        # -----------------------------------------------------------------
        try:
            from kanban.premortem_models import PreMortemAnalysis, PreMortemScenarioAcknowledgment

            analysis_json = [
                {
                    'scenario_number': 1,
                    'title': 'Authentication System Breach',
                    'probability': 'medium',
                    'impact': 'critical',
                    'risk_score': 8,
                    'failure_story': 'Six weeks after launch, a security researcher discovers that the JWT token refresh mechanism has a race condition allowing token reuse after revocation. Attackers exploit this to maintain persistent sessions. The team scrambles to patch the vulnerability while managing a public disclosure timeline.',
                    'warning_signs': ['Authentication testing suite still at 0% completion', 'Security architecture patterns completed but not validated against OWASP Top 10', 'No penetration testing scheduled before launch'],
                    'prevention_steps': ['Prioritize Authentication Testing Suite (Task #8) immediately', 'Schedule external security audit before go-live', 'Implement token blacklisting with Redis-backed store'],
                    'affected_tasks': ['Authentication System', 'Authentication Testing Suite', 'Security Audit & Fixes'],
                },
                {
                    'scenario_number': 2,
                    'title': 'Database Migration Catastrophe',
                    'probability': 'medium',
                    'impact': 'high',
                    'risk_score': 7,
                    'failure_story': 'During the first production deployment, the database migration fails halfway through due to incompatible schema changes. The rollback script has never been tested. Production data is in an inconsistent state for 6 hours while the team manually repairs tables.',
                    'warning_signs': ['Database Schema & Migrations task only at 40% with complex dependencies', 'No rollback procedure documented', 'Migration testing not included in CI/CD pipeline'],
                    'prevention_steps': ['Complete Database Schema task with rollback scripts for each migration', 'Add migration dry-run step to deployment pipeline', 'Test migration on production-size dataset copy'],
                    'affected_tasks': ['Database Schema & Migrations', 'Deployment Automation', 'Integration Testing Suite'],
                },
                {
                    'scenario_number': 3,
                    'title': 'Real-time Collaboration Performance Collapse',
                    'probability': 'high',
                    'impact': 'medium',
                    'risk_score': 6,
                    'failure_story': 'The real-time collaboration feature works fine in development with 3 users but collapses under 50 concurrent connections. WebSocket connections leak memory, and the message queue backs up causing 30-second delays. Users abandon the feature and revert to email.',
                    'warning_signs': ['Real-time Collaboration task not yet started (0%)', 'Data Caching Layer not implemented — no read-through cache for frequently accessed data', 'Load Testing task still in backlog'],
                    'prevention_steps': ['Begin Data Caching Layer before Real-time Collaboration', 'Set up load testing infrastructure early', 'Implement connection pooling and backpressure mechanisms'],
                    'affected_tasks': ['Real-time Collaboration', 'Data Caching Layer', 'Load Testing & Optimization'],
                },
                {
                    'scenario_number': 4,
                    'title': 'Key Developer Departure',
                    'probability': 'low',
                    'impact': 'critical',
                    'risk_score': 7,
                    'failure_story': 'Sam Rivera, who owns the majority of critical-path backend tasks (Base API, Authentication, Search Engine, API Rate Limiting), receives an offer and gives 2-week notice. The remaining team cannot maintain velocity on highly specialized code. Launch is delayed by 6 weeks.',
                    'warning_signs': ['Heavy task concentration on single team member (12 of 30 tasks)', 'Incomplete documentation of architectural decisions', 'No cross-training sessions scheduled'],
                    'prevention_steps': ['Distribute critical-path knowledge via pair programming sessions', 'Ensure Project Documentation Setup captures all architectural decisions', 'Cross-train Jordan on API and authentication patterns'],
                    'affected_tasks': ['Base API Structure', 'Authentication System', 'Search & Indexing Engine', 'API Rate Limiting'],
                },
                {
                    'scenario_number': 5,
                    'title': 'Scope Creep Through Feature Requests',
                    'probability': 'high',
                    'impact': 'medium',
                    'risk_score': 5,
                    'failure_story': 'Stakeholders begin requesting "just one more feature" during the In Review phase. Each small addition seems manageable individually, but collectively they add 40% more scope. The team burns out trying to accommodate changes while maintaining the original deadline. Quality drops, bugs multiply.',
                    'warning_signs': ['No formal change request process in place', 'User Onboarding Flow and UI/UX Polish tasks have vague acceptance criteria', 'Core Features Code Review marked urgent but not started'],
                    'prevention_steps': ['Implement a formal scope change request process with impact analysis', 'Define clear acceptance criteria for all Phase 3 tasks', 'Set a feature freeze date 2 weeks before launch'],
                    'affected_tasks': ['User Onboarding Flow', 'UI/UX Polish', 'Core Features Code Review', 'Launch & Go-Live'],
                },
            ]

            premortem, _ = PreMortemAnalysis.objects.update_or_create(
                board=board,
                defaults={
                    'created_by': alex,
                    'overall_risk_level': 'high',
                    'analysis_json': analysis_json,
                    'board_snapshot': {
                        'total_tasks': 30,
                        'completed_tasks': 10,
                        'in_progress_tasks': 8,
                        'team_members': ['Alex Chen', 'Sam Rivera', 'Jordan Taylor'],
                        'phases': ['Foundation & Setup', 'Core Features', 'Polish & Launch'],
                        'critical_path': ['Authentication System', 'Database Schema', 'Integration Testing', 'Security Audit', 'Launch'],
                    },
                },
            )

            # Add acknowledgments (sam acknowledged scenarios 1 and 4, jordan acknowledged 3)
            for scenario_idx, user, notes in [
                (0, sam, 'Acknowledged. I will prioritize the auth testing suite this sprint and schedule a security review with the team.'),
                (3, sam, 'Valid concern. I will start documenting all API architecture decisions and schedule pair programming sessions with Jordan.'),
                (2, jordan, 'Agreed on the load testing priority. I will set up the k6 load testing framework this week and create baseline benchmarks.'),
            ]:
                PreMortemScenarioAcknowledgment.objects.update_or_create(
                    pre_mortem=premortem,
                    scenario_index=scenario_idx,
                    acknowledged_by=user,
                    defaults={'notes': notes},
                )

            stats['premortem'] += 1
            self.stdout.write('   ✓ Pre-Mortem Analysis created')
        except Exception as e:
            self.stdout.write(self.style.WARNING(f'   ⚠️ Pre-Mortem Analysis: {e}'))

        # -----------------------------------------------------------------
        # 4. STRESS TEST (Red Team AI)
        # -----------------------------------------------------------------
        try:
            from kanban.stress_test_models import StressTestSession, ImmunityScore, StressTestScenario, Vaccine

            session, _ = StressTestSession.objects.update_or_create(
                board=board,
                defaults={
                    'run_by': alex,
                    'score_rationale': (
                        'The project shows moderate resilience with significant vulnerabilities in '
                        'dependency management and schedule buffer. The heavy concentration of critical '
                        'tasks on a single developer creates a fragile single-point-of-failure. '
                        'Budget utilization is healthy but schedule pressure is mounting with 20 '
                        'incomplete tasks and no contingency time built in.'
                    ),
                    'assumptions_made': [
                        'Current team velocity of 4.2 tasks/week is sustainable',
                        'No major scope changes expected from stakeholders',
                        'Third-party API dependencies remain stable',
                        'Team members maintain current availability (no PTO or sick leave)',
                    ],
                },
            )

            # Immunity Score
            ImmunityScore.objects.update_or_create(
                session=session,
                defaults={
                    'overall': 58,
                    'schedule': 45,
                    'budget': 72,
                    'team': 48,
                    'dependencies': 52,
                    'scope_stability': 65,
                    'schedule_rationale': 'With 20 of 30 tasks incomplete and no schedule buffer, any disruption cascades directly into deadline risk. The critical path has zero float.',
                    'budget_rationale': 'Budget utilization at 68% with project roughly 50% complete. Healthy ratio but leaves limited room for emergency contractor hiring.',
                    'team_rationale': 'Heavy single-developer dependency on Sam Rivera (12 tasks) creates a critical vulnerability. Bus factor is effectively 1 for backend systems.',
                    'dependencies_rationale': '5 external dependencies identified with no fallback strategy. Authentication system blocks 4 downstream tasks.',
                    'scope_stability_rationale': 'Scope has been relatively stable but Phase 3 tasks lack clear acceptance criteria, creating creep risk during review cycles.',
                },
            )

            # Stress Test Scenarios (attack simulations)
            scenarios_data = [
                {
                    'scenario_number': 1,
                    'attack_type': 'KEY_PERSON_RISK',
                    'title': 'Lead Backend Developer Unavailable for 2 Weeks',
                    'attack_description': 'Sam Rivera becomes unavailable (medical emergency) for 2 weeks during the critical Authentication System and Database Schema sprint. No backup developer has context on these systems.',
                    'cascade_effect': 'Authentication System (80% complete) stalls. Database Schema (40%) halts. 4 dependent tasks (API Rate Limiting, Search Engine, Integration Testing, Security Audit) are blocked. Projected delay: 3-4 weeks. Team morale drops as remaining members absorb additional scope.',
                    'outcome': 'FAIL',
                    'severity': 9,
                    'tasks_blocked': 6,
                    'estimated_delay_weeks': 4,
                    'has_recovery_path': True,
                    'early_warning_sign': 'Single developer assigned to >40% of remaining critical-path tasks',
                    'tags': ['team', 'single-point-of-failure', 'critical-path'],
                },
                {
                    'scenario_number': 2,
                    'attack_type': 'DEPENDENCY_FAILURE',
                    'title': 'Third-Party Auth Provider API Breaking Change',
                    'attack_description': 'The chosen OAuth provider pushes a breaking API change with 7-day migration window. The Authentication System must be partially rewritten to accommodate new token format and endpoint changes.',
                    'cascade_effect': 'Authentication System requires 40+ hours of rework. User Registration Flow needs corresponding updates. All testing must be redone. Integration Testing Suite scope expands by 30%.',
                    'outcome': 'SURVIVED_BARELY',
                    'severity': 7,
                    'tasks_blocked': 3,
                    'estimated_delay_weeks': 2,
                    'has_recovery_path': True,
                    'early_warning_sign': 'No abstraction layer between application and auth provider SDK',
                    'tags': ['dependencies', 'external-api', 'architecture'],
                },
                {
                    'scenario_number': 3,
                    'attack_type': 'SCOPE_EXPLOSION',
                    'title': 'Stakeholder Demands Mobile Responsive MVP',
                    'attack_description': 'Two weeks before launch, the executive sponsor mandates that all features must work on mobile browsers. This was not in the original requirements and impacts Dashboard UI, File Upload, User Management, and Notification Service.',
                    'cascade_effect': 'UI/UX Polish scope triples. Performance Optimization must cover mobile devices. Accessibility Compliance becomes critical rather than nice-to-have. Testing effort increases by 50%.',
                    'outcome': 'FAIL',
                    'severity': 8,
                    'tasks_blocked': 5,
                    'estimated_delay_weeks': 3,
                    'has_recovery_path': True,
                    'early_warning_sign': 'No mobile requirements discussed in Requirements Analysis phase',
                    'tags': ['scope', 'stakeholder', 'requirements'],
                },
                {
                    'scenario_number': 4,
                    'attack_type': 'INFRASTRUCTURE_FAILURE',
                    'title': 'CI/CD Pipeline Corruption Loses 3 Days of Builds',
                    'attack_description': 'A misconfigured deployment script corrupts the CI/CD pipeline. Build artifacts for the last 3 days are lost. The Deployment Automation task (not yet started) has no disaster recovery plan.',
                    'cascade_effect': 'Team loses 2 days recreating build configurations. Integration Testing must restart from clean state. Developer confidence in deployment process drops. Risk of similar issues during actual launch.',
                    'outcome': 'SURVIVED',
                    'severity': 5,
                    'tasks_blocked': 2,
                    'estimated_delay_weeks': 1,
                    'has_recovery_path': True,
                    'early_warning_sign': 'Deployment Automation task at 0% with no infrastructure-as-code',
                    'tags': ['infrastructure', 'devops', 'recovery'],
                },
                {
                    'scenario_number': 5,
                    'attack_type': 'QUALITY_CRISIS',
                    'title': 'Security Vulnerability Discovered in Production Dependencies',
                    'attack_description': 'A critical CVE is published for a core dependency used in the Base API Structure. The vulnerability allows remote code execution. Immediate patching requires updating the dependency which breaks 3 internal modules.',
                    'cascade_effect': 'Security Audit becomes urgent blocker. Base API compatibility tests must be rerun. Performance benchmarks invalidated. Potential 2-week delay while dependency is updated and all affected modules are verified.',
                    'outcome': 'SURVIVED_BARELY',
                    'severity': 8,
                    'tasks_blocked': 4,
                    'estimated_delay_weeks': 2,
                    'has_recovery_path': True,
                    'early_warning_sign': 'No automated dependency vulnerability scanning in place',
                    'tags': ['security', 'dependencies', 'quality'],
                },
            ]

            # Delete old scenarios for idempotency
            session.scenarios.all().delete()
            session.vaccines.all().delete()

            for s_data in scenarios_data:
                StressTestScenario.objects.create(
                    session=session,
                    scenario_number=s_data['scenario_number'],
                    attack_type=s_data['attack_type'],
                    title=s_data['title'],
                    attack_description=s_data['attack_description'],
                    cascade_effect=s_data['cascade_effect'],
                    outcome=s_data['outcome'],
                    severity=s_data['severity'],
                    tasks_blocked=s_data['tasks_blocked'],
                    estimated_delay_weeks=s_data['estimated_delay_weeks'],
                    has_recovery_path=s_data['has_recovery_path'],
                    early_warning_sign=s_data['early_warning_sign'],
                    tags=s_data['tags'],
                )

            # Vaccines (structural fix recommendations)
            vaccines_data = [
                {
                    'vaccine_number': 1,
                    'targets_scenario_number': 1,
                    'name': 'Cross-Training Program',
                    'description': 'Implement mandatory pair programming sessions so that at least 2 team members have context on every critical-path system. Focus on Authentication and Database subsystems first.',
                    'effort_level': 'MEDIUM',
                    'effort_rationale': 'Requires 4-6 hours/week of structured pair programming for 3 weeks.',
                    'projected_score_improvement': 12,
                    'implementation_hint': 'Schedule 2-hour pair programming blocks: Sam+Jordan on Auth, Sam+Alex on Database. Document architectural decisions in wiki.',
                },
                {
                    'vaccine_number': 2,
                    'targets_scenario_number': 2,
                    'name': 'Auth Provider Abstraction Layer',
                    'description': 'Introduce an adapter pattern between the application and the OAuth provider. This isolates the codebase from provider-specific breaking changes.',
                    'effort_level': 'LOW',
                    'effort_rationale': 'Estimated 8-12 hours of refactoring for an experienced developer.',
                    'projected_score_improvement': 8,
                    'implementation_hint': 'Create an AuthProviderInterface with methods for token exchange, refresh, and revocation. Current provider becomes one implementation.',
                },
                {
                    'vaccine_number': 3,
                    'targets_scenario_number': 3,
                    'name': 'Scope Freeze Protocol',
                    'description': 'Establish a formal scope freeze date 3 weeks before launch. Any post-freeze requests must go through an impact assessment with PM sign-off.',
                    'effort_level': 'LOW',
                    'effort_rationale': 'Process change requiring 2-hour team meeting and documentation update.',
                    'projected_score_improvement': 10,
                    'implementation_hint': 'Create a scope change request template in the wiki. Configure a "Scope Freeze" milestone on the board. Communicate to all stakeholders.',
                },
                {
                    'vaccine_number': 4,
                    'targets_scenario_number': 4,
                    'name': 'Infrastructure-as-Code Setup',
                    'description': 'Move all CI/CD configuration into version-controlled infrastructure-as-code. Add automated backup of build artifacts and pipeline configs.',
                    'effort_level': 'MEDIUM',
                    'effort_rationale': 'Requires 2-3 days of DevOps work to codify existing manual configurations.',
                    'projected_score_improvement': 7,
                    'implementation_hint': 'Use Terraform/Pulumi for infra, GitHub Actions for CI/CD. Store all configs in the repo. Add daily artifact backups to cloud storage.',
                },
                {
                    'vaccine_number': 5,
                    'targets_scenario_number': 5,
                    'name': 'Automated Dependency Scanning',
                    'description': 'Integrate Dependabot or Snyk into the CI pipeline to automatically detect and flag vulnerable dependencies before they reach production.',
                    'effort_level': 'LOW',
                    'effort_rationale': 'Takes 1-2 hours to configure automated scanning in CI pipeline.',
                    'projected_score_improvement': 9,
                    'implementation_hint': 'Enable GitHub Dependabot for the repo. Add Snyk test to CI. Create policy: critical CVEs block merge, high CVEs require review within 48h.',
                },
            ]

            for v_data in vaccines_data:
                Vaccine.objects.create(
                    session=session,
                    board=board,
                    vaccine_number=v_data['vaccine_number'],
                    targets_scenario_number=v_data['targets_scenario_number'],
                    name=v_data['name'],
                    description=v_data['description'],
                    effort_level=v_data['effort_level'],
                    effort_rationale=v_data['effort_rationale'],
                    projected_score_improvement=v_data['projected_score_improvement'],
                    implementation_hint=v_data['implementation_hint'],
                )

            stats['stress_tests'] += 1
            self.stdout.write('   ✓ Stress Test session created')
        except Exception as e:
            self.stdout.write(self.style.WARNING(f'   ⚠️ Stress Test: {e}'))

        # -----------------------------------------------------------------
        # 5. SCOPE AUTOPSY
        # -----------------------------------------------------------------
        try:
            from kanban.scope_autopsy_models import ScopeAutopsyReport, ScopeTimelineEvent

            report, _ = ScopeAutopsyReport.objects.update_or_create(
                board=board,
                defaults={
                    'created_by': alex,
                    'status': 'complete',
                    'baseline_task_count': 24,
                    'baseline_date': now - timedelta(days=35),
                    'final_task_count': 30,
                    'total_scope_growth_percentage': 25.0,
                    'total_delay_days': 12,
                    'total_budget_impact': Decimal('18500.00'),
                    'pattern_analysis': (
                        'Analysis reveals a pattern of incremental scope additions concentrated in '
                        'Phases 2 and 3. The majority of scope growth (4 of 6 added tasks) was driven '
                        'by security and quality requirements that were underestimated during initial '
                        'planning. Two tasks were added based on stakeholder feedback during sprint reviews. '
                        'The additions follow a "requirements discovery" pattern common in agile projects '
                        'where the full scope becomes clear only as development progresses.\n\n'
                        'Key pattern: Security-related tasks were the largest single category of scope '
                        'growth, suggesting the initial security architecture review did not adequately '
                        'capture implementation complexity.'
                    ),
                    'ai_summary': (
                        'The Software Development project experienced 25% scope growth over 5 weeks, '
                        'growing from 24 to 30 tasks. This is above the industry average of 15-20% for '
                        'similar-sized projects. The growth was primarily driven by security requirements '
                        'discovery (API Rate Limiting, Security Audit) and quality assurance gaps '
                        '(Integration Testing, Load Testing). Total estimated impact: 12 days delay '
                        'and $18,500 in additional costs. The scope growth was not chaotic — it followed '
                        'a predictable pattern of requirements maturation that could have been partially '
                        'mitigated with a more thorough initial security threat modeling exercise.'
                    ),
                    'recommendations': [
                        {'title': 'Implement Security Threat Modeling in Phase 1', 'description': 'Add a dedicated security threat modeling session during the Requirements Analysis phase to surface security tasks earlier.', 'priority': 'high'},
                        {'title': 'Add 20% Scope Buffer to Estimates', 'description': 'Based on this project\'s growth pattern, include a 20% task buffer in future project estimates to account for requirements discovery.', 'priority': 'medium'},
                        {'title': 'Bi-weekly Scope Health Check', 'description': 'Schedule bi-weekly scope reviews comparing current task count against baseline to catch drift early.', 'priority': 'medium'},
                        {'title': 'Stakeholder Feedback Integration Windows', 'description': 'Define specific sprint review windows where stakeholder feedback can add scope, rather than ad-hoc additions throughout the project.', 'priority': 'low'},
                    ],
                    'board_snapshot': {
                        'total_tasks': 30,
                        'completed_tasks': 10,
                        'phases': 3,
                        'team_size': 3,
                        'project_start': (now - timedelta(days=40)).strftime('%Y-%m-%d'),
                    },
                },
            )

            # Create timeline events
            report.timeline_events.all().delete()
            timeline_events = [
                {
                    'event_date': now - timedelta(days=35),
                    'title': 'Project Kickoff — Baseline Set',
                    'description': 'Initial project scope defined with 24 tasks across 3 phases. Baseline captured after Requirements Analysis & Planning completion.',
                    'source_type': 'task_added',
                    'tasks_added': 24, 'tasks_removed': 0, 'net_task_change': 0,
                    'added_by': alex,
                    'estimated_delay_days': 0,
                    'estimated_budget_impact': Decimal('0'),
                    'cumulative_task_count': 24,
                    'is_major_event': True,
                },
                {
                    'event_date': now - timedelta(days=28),
                    'title': 'API Rate Limiting Added',
                    'description': 'During security architecture review, the team identified that API rate limiting was missing from the original scope. Added as a high-priority task to prevent abuse.',
                    'source_type': 'scope_alert',
                    'tasks_added': 1, 'tasks_removed': 0, 'net_task_change': 1,
                    'added_by': sam,
                    'estimated_delay_days': 2,
                    'estimated_budget_impact': Decimal('3200.00'),
                    'cumulative_task_count': 25,
                    'is_major_event': False,
                },
                {
                    'event_date': now - timedelta(days=23),
                    'title': 'Integration Testing Suite Expanded',
                    'description': 'Sprint retrospective revealed gaps in test coverage. Integration Testing Suite added to ensure cross-module compatibility before release.',
                    'source_type': 'meeting',
                    'tasks_added': 1, 'tasks_removed': 0, 'net_task_change': 1,
                    'added_by': jordan,
                    'estimated_delay_days': 2,
                    'estimated_budget_impact': Decimal('2800.00'),
                    'cumulative_task_count': 26,
                    'is_major_event': False,
                },
                {
                    'event_date': now - timedelta(days=18),
                    'title': 'Security Audit & Load Testing Added',
                    'description': 'Stakeholder review meeting raised concerns about production readiness. Two new tasks added: Security Audit & Fixes and Load Testing & Optimization.',
                    'source_type': 'meeting',
                    'tasks_added': 2, 'tasks_removed': 0, 'net_task_change': 2,
                    'added_by': alex,
                    'estimated_delay_days': 5,
                    'estimated_budget_impact': Decimal('7500.00'),
                    'cumulative_task_count': 28,
                    'is_major_event': True,
                },
                {
                    'event_date': now - timedelta(days=12),
                    'title': 'Accessibility Compliance Requirement',
                    'description': 'Legal team flagged WCAG 2.1 compliance as a requirement for enterprise clients. Accessibility Compliance task added to Phase 3.',
                    'source_type': 'scope_alert',
                    'tasks_added': 1, 'tasks_removed': 0, 'net_task_change': 1,
                    'added_by': alex,
                    'estimated_delay_days': 2,
                    'estimated_budget_impact': Decimal('3000.00'),
                    'cumulative_task_count': 29,
                    'is_major_event': False,
                },
                {
                    'event_date': now - timedelta(days=7),
                    'title': 'Error Tracking & Monitoring Added',
                    'description': 'After a production incident on a related project, the team proactively added Error Tracking & Monitoring to ensure observability from day one.',
                    'source_type': 'ai_suggestion',
                    'tasks_added': 1, 'tasks_removed': 0, 'net_task_change': 1,
                    'added_by': sam,
                    'estimated_delay_days': 1,
                    'estimated_budget_impact': Decimal('2000.00'),
                    'cumulative_task_count': 30,
                    'is_major_event': False,
                },
            ]

            for evt in timeline_events:
                ScopeTimelineEvent.objects.create(report=report, **evt)

            stats['scope_autopsies'] += 1
            self.stdout.write('   ✓ Scope Autopsy Report created')
        except Exception as e:
            self.stdout.write(self.style.WARNING(f'   ⚠️ Scope Autopsy: {e}'))

        # -----------------------------------------------------------------
        # 6. EXIT PROTOCOL (Cemetery entry for a demo "dead" project)
        #    NOTE: We create a CemeteryEntry on the Bug Tracking board
        #    to show the cemetery feature. We do NOT create a HospiceSession
        #    on the Software Development board (that would mark it as dying).
        # -----------------------------------------------------------------
        try:
            from exit_protocol.models import (
                ProjectHealthSignal, CemeteryEntry,
            )

            # Create health signals on the Software Development board for context
            ProjectHealthSignal.objects.filter(board=board).delete()
            signal_data = [
                {'days_ago': 14, 'velocity_last_sprint': 5.0, 'velocity_3sprint_avg': 4.8, 'velocity_decline_pct': 0, 'budget_spent_pct': 45, 'tasks_complete_pct': 33, 'deadlines_missed_30d': 0, 'days_since_last_activity': 0, 'dimensions_available': 4, 'hospice_risk_score': 0.15, 'score_is_valid': True},
                {'days_ago': 7, 'velocity_last_sprint': 4.2, 'velocity_3sprint_avg': 4.5, 'velocity_decline_pct': 6.7, 'budget_spent_pct': 58, 'tasks_complete_pct': 40, 'deadlines_missed_30d': 1, 'days_since_last_activity': 0, 'dimensions_available': 4, 'hospice_risk_score': 0.25, 'score_is_valid': True},
                {'days_ago': 0, 'velocity_last_sprint': 4.0, 'velocity_3sprint_avg': 4.4, 'velocity_decline_pct': 9.1, 'budget_spent_pct': 68, 'tasks_complete_pct': 47, 'deadlines_missed_30d': 2, 'days_since_last_activity': 0, 'dimensions_available': 4, 'hospice_risk_score': 0.30, 'score_is_valid': True},
            ]
            for sig in signal_data:
                days_ago = sig.pop('days_ago')
                health = ProjectHealthSignal.objects.create(board=board, **sig)
                ProjectHealthSignal.objects.filter(pk=health.pk).update(
                    recorded_at=now - timedelta(days=days_ago)
                )

            # Create a Cemetery Entry for the Bug Tracking board (if it exists)
            # This gives users a "dead project" to explore in the cemetery
            cemetery_board = self.bug_board
            if cemetery_board:
                CemeteryEntry.objects.filter(board=cemetery_board).delete()
                CemeteryEntry.objects.create(
                    board=cemetery_board,
                    project_name='Legacy Bug Tracker v1',
                    project_description='The original bug tracking system built on a monolithic architecture. Replaced by the new microservices-based Bug Tracking board after persistent scalability issues.',
                    board_id_snapshot=cemetery_board.pk,
                    team_size=4,
                    total_tasks=45,
                    completed_tasks=38,
                    budget_allocated=Decimal('75000.00'),
                    budget_spent=Decimal('82000.00'),
                    start_date=(now - timedelta(days=180)).date(),
                    end_date=(now - timedelta(days=15)).date(),
                    cause_of_death='scope_creep_spiral',
                    ai_cause_rationale=(
                        'The Legacy Bug Tracker project experienced a classic scope creep spiral. '
                        'What began as a simple defect tracking tool grew to include feature requests, '
                        'sprint planning, and reporting capabilities — each addition stretching the '
                        'monolithic architecture beyond its design limits. The final trigger was a '
                        'database performance collapse when the bug count exceeded 10,000 records, '
                        'revealing fundamental scaling limitations that could not be fixed without '
                        'a complete rewrite.'
                    ),
                    contributing_factors=[
                        'Monolithic architecture hit scaling ceiling at 10K records',
                        'Scope expanded 3x from original requirements without architecture review',
                        'Budget overrun of 9.3% ($7,000) with diminishing returns on new features',
                        'Team morale declined as technical debt accumulated',
                        'No automated testing — manual QA could not keep pace with changes',
                    ],
                    autopsy_report={
                        'phases': [
                            {'name': 'Launch (6 months ago)', 'health': 'green', 'notes': 'Strong start with clear scope and enthusiastic team'},
                            {'name': 'Feature Expansion (4 months ago)', 'health': 'yellow', 'notes': 'Scope began growing. Sprint planning and reporting features added'},
                            {'name': 'Performance Issues (2 months ago)', 'health': 'orange', 'notes': 'Database queries slowed. Team spent 40% of time on hotfixes'},
                            {'name': 'Death Spiral (1 month ago)', 'health': 'red', 'notes': 'Critical performance failure. Decision to rebuild on microservices'},
                        ],
                        'final_velocity': 1.2,
                        'peak_velocity': 5.8,
                    },
                    autopsy_summary=(
                        'The Legacy Bug Tracker project achieved 84% task completion but ultimately '
                        'failed due to architectural limitations that could not support the expanded '
                        'scope. The project delivered significant value in its first 4 months but the '
                        'decision to continuously add features without revisiting the architecture '
                        'led to an unsustainable technical debt spiral. Key lesson: monolithic '
                        'architectures need explicit scaling reviews when scope grows beyond 2x original.'
                    ),
                    lessons_to_repeat=[
                        'Strong initial requirements gathering and team alignment',
                        'Regular sprint retrospectives caught issues early (even if not always acted upon)',
                        'Comprehensive bug categorization taxonomy proved valuable and was carried forward',
                    ],
                    lessons_to_avoid=[
                        'Never expand scope 3x without an architecture review checkpoint',
                        'Establish performance budgets and load test regularly from sprint 2 onwards',
                        'Do not defer automated testing — manual QA does not scale',
                        'Set hard budget gates that trigger automatic scope review',
                    ],
                    open_questions=[
                        'Should we have pivoted to microservices earlier, or was the monolith the right choice for the MVP phase?',
                        'Could the project have been saved with a dedicated performance engineer?',
                    ],
                    decline_timeline=[
                        {'week': 1, 'score': 95}, {'week': 4, 'score': 90},
                        {'week': 8, 'score': 82}, {'week': 12, 'score': 70},
                        {'week': 16, 'score': 55}, {'week': 20, 'score': 35},
                        {'week': 24, 'score': 15},
                    ],
                    tags=['monolith', 'scope-creep', 'scaling', 'technical-debt', 'performance'],
                )
                stats['exit_protocol'] += 1
                self.stdout.write('   ✓ Exit Protocol (Cemetery Entry + Health Signals) created')
            else:
                self.stdout.write('   ⚠️ Bug Tracking board not found — skipping Cemetery Entry')
        except Exception as e:
            self.stdout.write(self.style.WARNING(f'   ⚠️ Exit Protocol: {e}'))

        return stats

    def print_final_summary(self):
        """Print final summary of all demo data"""
        self.stdout.write(self.style.SUCCESS('\n' + '=' * 80))
        self.stdout.write(self.style.SUCCESS('✅ ALL DEMO DATA POPULATION COMPLETE'))
        self.stdout.write(self.style.SUCCESS('=' * 80))
        
        # Count all data
        task_count = Task.objects.filter(column__board__in=self.demo_boards).count()
        wiki_pages = WikiPage.objects.filter(organization=self.demo_org).count()
        wiki_categories = WikiCategory.objects.filter(organization=self.demo_org).count()
        chat_rooms = ChatRoom.objects.filter(board__in=self.demo_boards).count()
        chat_messages = ChatMessage.objects.filter(chat_room__board__in=self.demo_boards).count()
        conflicts = ConflictDetection.objects.filter(board__in=self.demo_boards).count()
        ai_sessions = AIAssistantSession.objects.filter(user__in=self.demo_users).count()
        ai_messages = AIAssistantMessage.objects.filter(session__user__in=self.demo_users).count()
        ai_analytics = AIAssistantAnalytics.objects.filter(user__in=self.demo_users).count()
        kb_entries = ProjectKnowledgeBase.objects.filter(board__in=self.demo_boards).count()
        ai_recommendations = AITaskRecommendation.objects.filter(board__in=self.demo_boards).count()
        time_entries = TimeEntry.objects.filter(task__column__board__in=self.demo_boards).count()
        commitment_protocols = CommitmentProtocol.objects.filter(board__in=self.demo_boards).count()
        commitment_signals = ConfidenceSignal.objects.filter(protocol__board__in=self.demo_boards).count()
        commitment_bets = CommitmentBet.objects.filter(protocol__board__in=self.demo_boards).count()
        
        # AI Tools counts
        try:
            from kanban.whatif_models import WhatIfScenario
            whatif_count = WhatIfScenario.objects.filter(board__in=self.demo_boards).count()
        except Exception:
            whatif_count = 0
        try:
            from kanban.shadow_models import ShadowBranch
            shadow_count = ShadowBranch.objects.filter(board__in=self.demo_boards).count()
        except Exception:
            shadow_count = 0
        try:
            from kanban.premortem_models import PreMortemAnalysis
            premortem_count = PreMortemAnalysis.objects.filter(board__in=self.demo_boards).count()
        except Exception:
            premortem_count = 0
        try:
            from kanban.stress_test_models import StressTestSession
            stress_count = StressTestSession.objects.filter(board__in=self.demo_boards).count()
        except Exception:
            stress_count = 0
        try:
            from kanban.scope_autopsy_models import ScopeAutopsyReport
            autopsy_count = ScopeAutopsyReport.objects.filter(board__in=self.demo_boards).count()
        except Exception:
            autopsy_count = 0
        try:
            from exit_protocol.models import CemeteryEntry
            cemetery_count = CemeteryEntry.objects.filter(board__in=self.demo_boards).count()
        except Exception:
            cemetery_count = 0

        self.stdout.write(f'''
📊 Demo Data Summary:
   ├── Tasks: {task_count}
   ├── Wiki: {wiki_categories} categories, {wiki_pages} pages
   ├── Messaging: {chat_rooms} rooms, {chat_messages} messages
   ├── Conflicts: {conflicts}
   ├── AI Assistant: {ai_sessions} sessions, {ai_messages} messages
   │   ├── Analytics: {ai_analytics} daily records
   │   ├── Knowledge Base: {kb_entries} entries
   │   └── Recommendations: {ai_recommendations}
   ├── Time Entries: {time_entries}
   ├── Commitments: {commitment_protocols} protocols, {commitment_signals} signals, {commitment_bets} bets
   └── AI Tools: {whatif_count} What-If, {shadow_count} Shadow Branches, {premortem_count} Pre-Mortem, {stress_count} Stress Tests, {autopsy_count} Scope Autopsies, {cemetery_count} Cemetery Entries

🎉 Demo environment is now fully populated!

To access the demo:
   • Visit: http://localhost:8000
   • Login as demo user or view demo boards
''')
