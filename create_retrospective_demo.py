"""
Create retrospective demo data only
This script adds retrospective data to the existing demo boards
"""
import os
import django
from decimal import Decimal
from datetime import timedelta

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'kanban_board.settings')
django.setup()

from django.contrib.auth.models import User
from django.utils import timezone
from kanban.models import Board
from kanban.retrospective_models import (
    ProjectRetrospective, LessonLearned, ImprovementMetric, 
    RetrospectiveActionItem
)

print("=" * 80)
print(" " * 20 + "RETROSPECTIVE DEMO DATA CREATION")
print("=" * 80)

# Get demo boards
software_board = Board.objects.filter(name='Software Project').first()
marketing_board = Board.objects.filter(name='Marketing Campaign').first()
bug_board = Board.objects.filter(name='Bug Tracking').first()

boards_data = []
if software_board:
    boards_data.append(('software', software_board))
if marketing_board:
    boards_data.append(('marketing', marketing_board))
if bug_board:
    boards_data.append(('bug', bug_board))

if not boards_data:
    print('❌ No demo boards found!')
    exit(1)

print(f'\n📊 Found {len(boards_data)} demo boards')

now = timezone.now()
created_count = 0

for board_type, board in boards_data:
    print(f'\n📝 Creating retrospectives for {board.name}...')
    
    # Get board members for assignments
    board_members = list(board.members.all())
    if not board_members:
        board_members = [User.objects.filter(is_superuser=True).first()]
    
    if board_type == 'software':
        # Sprint Retrospective 1 - Completed sprint (30 days ago)
        retro1, created = ProjectRetrospective.objects.get_or_create(
            board=board,
            title='Sprint 23 Retrospective - Authentication Module',
            defaults={
                'retrospective_type': 'sprint',
                'status': 'finalized',
                'period_start': (now - timedelta(days=44)).date(),
                'period_end': (now - timedelta(days=30)).date(),
                'metrics_snapshot': {
                    'tasks_completed': 18,
                    'tasks_planned': 20,
                    'velocity': 45,
                    'completion_rate': 90,
                    'average_cycle_time': 3.5,
                    'quality_score': 8.5
                },
                'what_went_well': 'Team collaboration was excellent with daily standups keeping everyone aligned. Code review process worked smoothly with most PRs reviewed within 4 hours. Authentication module was delivered ahead of schedule with comprehensive test coverage (94%). Documentation was completed alongside implementation.',
                'what_needs_improvement': 'Testing environment had intermittent issues causing delays. Some tasks had unclear requirements requiring multiple clarification rounds. Tech debt from previous sprint affected implementation speed in some areas.',
                'lessons_learned': [
                    {'lesson': 'Early integration testing catches issues faster', 'priority': 'high', 'category': 'quality'},
                    {'lesson': 'Detailed acceptance criteria reduce rework', 'priority': 'high', 'category': 'planning'},
                    {'lesson': 'Pair programming accelerates complex features', 'priority': 'medium', 'category': 'teamwork'}
                ],
                'key_achievements': [
                    'Authentication module completed with OAuth2 integration',
                    'Test coverage increased from 78% to 94%',
                    'Zero critical bugs in production',
                    'All sprint goals met ahead of schedule'
                ],
                'challenges_faced': [
                    {'challenge': 'Testing environment instability', 'impact': 'medium'},
                    {'challenge': 'Unclear requirements for password reset flow', 'impact': 'low'}
                ],
                'improvement_recommendations': [
                    'Set up dedicated staging environment for testing',
                    'Create requirement checklist template',
                    'Allocate time for tech debt in each sprint'
                ],
                'overall_sentiment_score': Decimal('0.82'),
                'team_morale_indicator': 'high',
                'performance_trend': 'improving',
                'ai_generated_at': now - timedelta(days=30),
                'ai_confidence_score': Decimal('0.88'),
                'created_by': board_members[0],
                'finalized_by': board_members[0],
                'finalized_at': now - timedelta(days=29)
            }
        )
        if created:
            print(f'  ✓ Created: {retro1.title}')
            created_count += 1
            
            # Create lessons learned for retro1
            lesson1, _ = LessonLearned.objects.get_or_create(
                retrospective=retro1,
                board=board,
                title='Early Integration Testing Prevents Late-Stage Issues',
                defaults={
                    'description': 'Running integration tests early in the sprint helped us catch authentication flow issues before they became blockers. This saved approximately 2 days of debugging time.',
                    'category': 'quality',
                    'priority': 'high',
                    'status': 'implemented',
                    'recommended_action': 'Run integration tests daily starting from sprint day 2',
                    'implementation_date': (now - timedelta(days=15)).date(),
                    'expected_benefit': 'Reduce bug discovery time by 40%',
                    'actual_benefit': 'Reduced debugging time by 50% in subsequent sprint',
                    'ai_suggested': True,
                    'ai_confidence': Decimal('0.92'),
                    'action_owner': board_members[0]
                }
            )
            
            LessonLearned.objects.get_or_create(
                retrospective=retro1,
                board=board,
                title='Detailed Acceptance Criteria Reduce Rework',
                defaults={
                    'description': 'Tasks with comprehensive acceptance criteria had 60% less rework compared to vague requirements. Password reset feature required 3 iterations due to unclear requirements.',
                    'category': 'planning',
                    'priority': 'high',
                    'status': 'in_progress',
                    'recommended_action': 'Require detailed acceptance criteria checklist for all tasks before sprint planning',
                    'expected_benefit': 'Reduce rework by 50%',
                    'ai_suggested': True,
                    'ai_confidence': Decimal('0.87'),
                    'action_owner': board_members[1] if len(board_members) > 1 else board_members[0]
                }
            )
            
            # Create improvement metrics
            ImprovementMetric.objects.get_or_create(
                retrospective=retro1,
                board=board,
                metric_name='Team Velocity',
                defaults={
                    'metric_type': 'velocity',
                    'metric_value': Decimal('45'),
                    'previous_value': Decimal('38'),
                    'target_value': Decimal('50'),
                    'change_amount': Decimal('7'),
                    'change_percentage': Decimal('18.42'),
                    'trend': 'improving',
                    'unit_of_measure': 'story points',
                    'measured_at': (now - timedelta(days=30)).date()
                }
            )
            
            ImprovementMetric.objects.get_or_create(
                retrospective=retro1,
                board=board,
                metric_name='Code Coverage',
                defaults={
                    'metric_type': 'quality',
                    'metric_value': Decimal('94'),
                    'previous_value': Decimal('78'),
                    'target_value': Decimal('90'),
                    'change_amount': Decimal('16'),
                    'change_percentage': Decimal('20.51'),
                    'trend': 'improving',
                    'unit_of_measure': 'percentage',
                    'measured_at': (now - timedelta(days=30)).date()
                }
            )
            
            # Create action items
            RetrospectiveActionItem.objects.get_or_create(
                retrospective=retro1,
                board=board,
                title='Set up Dedicated Staging Environment',
                defaults={
                    'description': 'Configure separate staging environment with production-like data to avoid testing environment conflicts.',
                    'action_type': 'technical_improvement',
                    'status': 'completed',
                    'assigned_to': board_members[0],
                    'target_completion_date': (now - timedelta(days=20)).date(),
                    'actual_completion_date': (now - timedelta(days=18)).date(),
                    'priority': 'high',
                    'expected_impact': 'Eliminate 80% of testing environment issues',
                    'actual_impact': 'Reduced testing blockers from 12 to 2 per sprint',
                    'progress_percentage': 100,
                    'ai_suggested': True,
                    'ai_confidence': Decimal('0.91'),
                    'related_lesson': lesson1
                }
            )
        else:
            print(f'  ℹ Already exists: {retro1.title}')
        
        # Sprint Retrospective 2 - Recent sprint (2 weeks ago)
        retro2, created = ProjectRetrospective.objects.get_or_create(
            board=board,
            title='Sprint 24 Retrospective - Dashboard Development',
            defaults={
                'retrospective_type': 'sprint',
                'status': 'reviewed',
                'period_start': (now - timedelta(days=28)).date(),
                'period_end': (now - timedelta(days=14)).date(),
                'metrics_snapshot': {
                    'tasks_completed': 22,
                    'tasks_planned': 24,
                    'velocity': 52,
                    'completion_rate': 91.7,
                    'average_cycle_time': 3.2,
                    'quality_score': 9.1
                },
                'what_went_well': 'Velocity improved significantly (+15%). Dashboard MVP delivered with all core features. Staging environment eliminated testing delays. Team member onboarding went smoothly with updated documentation. Cross-team collaboration with UX team was productive.',
                'what_needs_improvement': 'Some features took longer than estimated due to API complexity. One team member was overburdened with code reviews. Real-time updates feature had performance issues requiring optimization. Communication gaps with product team on feature priorities.',
                'lessons_learned': [
                    {'lesson': 'Dedicated staging environment eliminates testing bottlenecks', 'priority': 'high', 'category': 'technical'},
                    {'lesson': 'Distribute code review responsibility across team', 'priority': 'high', 'category': 'process'},
                    {'lesson': 'Early performance testing for real-time features', 'priority': 'medium', 'category': 'quality'}
                ],
                'key_achievements': [
                    'Dashboard MVP launched to beta users',
                    'Velocity increased by 15% from previous sprint',
                    'Zero testing environment blockers',
                    'Real-time notifications implemented successfully'
                ],
                'challenges_faced': [
                    {'challenge': 'API integration complexity underestimated', 'impact': 'medium'},
                    {'challenge': 'Code review bottleneck with single reviewer', 'impact': 'medium'},
                    {'challenge': 'Performance issues with WebSocket implementation', 'impact': 'high'}
                ],
                'improvement_recommendations': [
                    'Add buffer time for complex API integrations',
                    'Rotate code review duties among senior developers',
                    'Include performance testing in definition of done',
                    'Schedule weekly sync with product team'
                ],
                'overall_sentiment_score': Decimal('0.78'),
                'team_morale_indicator': 'high',
                'performance_trend': 'improving',
                'previous_retrospective': retro1,
                'ai_generated_at': now - timedelta(days=14),
                'ai_confidence_score': Decimal('0.85'),
                'created_by': board_members[0]
            }
        )
        if created:
            print(f'  ✓ Created: {retro2.title}')
            created_count += 1
            
            LessonLearned.objects.get_or_create(
                retrospective=retro2,
                board=board,
                title='Staging Environment Eliminates Testing Bottlenecks',
                defaults={
                    'description': 'Dedicated staging environment completely eliminated testing conflicts. Zero environment-related delays this sprint vs. 5 incidents in previous sprint.',
                    'category': 'technical',
                    'priority': 'high',
                    'status': 'validated',
                    'recommended_action': 'Maintain dedicated staging environment with production-like data',
                    'implementation_date': (now - timedelta(days=25)).date(),
                    'validation_date': (now - timedelta(days=14)).date(),
                    'expected_benefit': 'Eliminate testing environment issues',
                    'actual_benefit': '100% reduction in testing blockers, saved ~8 hours of debugging time',
                    'success_metrics': [
                        {'metric': 'environment_issues', 'before': 5, 'after': 0},
                        {'metric': 'debugging_hours', 'before': 8, 'after': 0}
                    ],
                    'ai_suggested': False,
                    'action_owner': board_members[0]
                }
            )
            
            RetrospectiveActionItem.objects.get_or_create(
                retrospective=retro2,
                board=board,
                title='Implement Code Review Rotation Policy',
                defaults={
                    'description': 'Create rotation schedule for code reviews to distribute workload and knowledge sharing among all senior developers.',
                    'action_type': 'process_change',
                    'status': 'in_progress',
                    'assigned_to': board_members[1] if len(board_members) > 1 else board_members[0],
                    'target_completion_date': (now + timedelta(days=7)).date(),
                    'priority': 'high',
                    'expected_impact': 'Balance review workload, improve knowledge sharing',
                    'progress_percentage': 60,
                    'progress_notes': 'Draft rotation schedule created, gathering team feedback',
                    'ai_suggested': True,
                    'ai_confidence': Decimal('0.88')
                }
            )
        else:
            print(f'  ℹ Already exists: {retro2.title}')
        
        # Sprint Retrospective 3 - Current/ongoing sprint
        retro3, created = ProjectRetrospective.objects.get_or_create(
            board=board,
            title='Sprint 25 Mid-Sprint Checkpoint',
            defaults={
                'retrospective_type': 'sprint',
                'status': 'draft',
                'period_start': (now - timedelta(days=7)).date(),
                'period_end': now.date(),
                'metrics_snapshot': {
                    'tasks_completed': 8,
                    'tasks_planned': 26,
                    'tasks_in_progress': 12,
                    'velocity_tracking': 24,
                    'projected_velocity': 55,
                    'completion_rate': 30.8
                },
                'what_went_well': 'Code review rotation working well. API documentation improvements helping new team members. Performance optimization efforts showing good results.',
                'what_needs_improvement': 'Still tracking preliminary data for ongoing sprint.',
                'team_morale_indicator': 'high',
                'performance_trend': 'improving',
                'previous_retrospective': retro2,
                'created_by': board_members[0]
            }
        )
        if created:
            print(f'  ✓ Created: {retro3.title}')
            created_count += 1
        else:
            print(f'  ℹ Already exists: {retro3.title}')
            
    elif board_type == 'marketing':
        # Marketing Campaign Retrospective
        retro1, created = ProjectRetrospective.objects.get_or_create(
            board=board,
            title='Q3 Campaign Retrospective',
            defaults={
                'retrospective_type': 'quarterly',
                'status': 'finalized',
                'period_start': (now - timedelta(days=90)).date(),
                'period_end': (now - timedelta(days=7)).date(),
                'metrics_snapshot': {
                    'campaigns_completed': 12,
                    'engagement_rate': 4.8,
                    'conversion_rate': 2.3,
                    'roi': 285,
                    'leads_generated': 1847,
                    'content_pieces': 45
                },
                'what_went_well': 'Social media engagement increased by 67%. Video content performed exceptionally well with 3x engagement vs. static posts. Email campaigns had 25% higher open rates with personalized subject lines. Cross-functional collaboration with sales team improved lead quality.',
                'what_needs_improvement': 'Content approval process too slow, creating bottlenecks. Analytics reporting scattered across multiple tools. Some campaigns launched without proper A/B testing. Budget tracking needs better real-time visibility.',
                'lessons_learned': [
                    {'lesson': 'Video content drives 3x engagement', 'priority': 'high', 'category': 'other'},
                    {'lesson': 'Personalization improves email performance', 'priority': 'high', 'category': 'customer'},
                    {'lesson': 'Early sales alignment improves lead quality', 'priority': 'medium', 'category': 'communication'}
                ],
                'key_achievements': [
                    '67% increase in social media engagement',
                    'Generated 1,847 qualified leads (45% above target)',
                    '285% ROI on campaign investments',
                    'Launched 12 successful campaigns across all channels'
                ],
                'challenges_faced': [
                    {'challenge': 'Slow content approval workflow', 'impact': 'high'},
                    {'challenge': 'Fragmented analytics tools', 'impact': 'medium'},
                    {'challenge': 'Insufficient A/B testing', 'impact': 'medium'}
                ],
                'improvement_recommendations': [
                    'Streamline content approval with automated workflow',
                    'Consolidate analytics into unified dashboard',
                    'Make A/B testing mandatory for all campaigns',
                    'Implement real-time budget tracking dashboard'
                ],
                'overall_sentiment_score': Decimal('0.85'),
                'team_morale_indicator': 'excellent',
                'performance_trend': 'improving',
                'ai_generated_at': now - timedelta(days=7),
                'ai_confidence_score': Decimal('0.89'),
                'created_by': board_members[0],
                'finalized_by': board_members[0],
                'finalized_at': now - timedelta(days=5)
            }
        )
        if created:
            print(f'  ✓ Created: {retro1.title}')
            created_count += 1
            
            LessonLearned.objects.get_or_create(
                retrospective=retro1,
                board=board,
                title='Video Content Drives 3x Higher Engagement',
                defaults={
                    'description': 'Analysis shows video posts generate 3x more engagement than static images. Video content also has 2x higher shareability and longer average view time.',
                    'category': 'other',
                    'priority': 'high',
                    'status': 'in_progress',
                    'recommended_action': 'Increase video content production to 60% of total content mix',
                    'expected_benefit': 'Increase overall engagement by 40%',
                    'success_metrics': [
                        {'metric': 'engagement_rate', 'before': 2.8, 'after': 4.8},
                        {'metric': 'video_vs_static', 'ratio': 3.0}
                    ],
                    'ai_suggested': True,
                    'ai_confidence': Decimal('0.94'),
                    'action_owner': board_members[0]
                }
            )
            
            ImprovementMetric.objects.get_or_create(
                retrospective=retro1,
                board=board,
                metric_name='Social Media Engagement Rate',
                defaults={
                    'metric_type': 'customer_satisfaction',
                    'metric_value': Decimal('4.8'),
                    'previous_value': Decimal('2.8'),
                    'target_value': Decimal('5.0'),
                    'change_amount': Decimal('2.0'),
                    'change_percentage': Decimal('71.43'),
                    'trend': 'improving',
                    'unit_of_measure': 'percentage',
                    'measured_at': (now - timedelta(days=7)).date()
                }
            )
            
            RetrospectiveActionItem.objects.get_or_create(
                retrospective=retro1,
                board=board,
                title='Increase Video Content Production to 60%',
                defaults={
                    'description': 'Shift content mix to 60% video, 40% static/text based on engagement data. Partner with video production team for resources.',
                    'action_type': 'process_change',
                    'status': 'in_progress',
                    'assigned_to': board_members[0],
                    'target_completion_date': (now + timedelta(days=30)).date(),
                    'priority': 'high',
                    'expected_impact': 'Increase overall engagement by 40-50%',
                    'progress_percentage': 35,
                    'progress_notes': 'Video production capacity increased, training content team',
                    'ai_suggested': True,
                    'ai_confidence': Decimal('0.92')
                }
            )
        else:
            print(f'  ℹ Already exists: {retro1.title}')
            
    elif board_type == 'bug':
        # Bug Tracking Retrospective
        retro1, created = ProjectRetrospective.objects.get_or_create(
            board=board,
            title='Bug Resolution Performance Review',
            defaults={
                'retrospective_type': 'milestone',
                'status': 'finalized',
                'period_start': (now - timedelta(days=60)).date(),
                'period_end': (now - timedelta(days=10)).date(),
                'metrics_snapshot': {
                    'bugs_resolved': 87,
                    'critical_bugs': 5,
                    'average_resolution_time': 2.3,
                    'first_response_time': 0.8,
                    'reopened_bugs': 7,
                    'regression_rate': 8
                },
                'what_went_well': 'Response time improved significantly with on-call rotation. Critical bugs resolved within 4 hours average. Root cause analysis prevented recurring issues. Bug triage process working effectively.',
                'what_needs_improvement': 'Regression rate still higher than target. Some bugs lack sufficient reproduction steps. Documentation of fixes could be better. Need better tooling for bug tracking analytics.',
                'lessons_learned': [
                    {'lesson': 'Root cause analysis prevents recurrence', 'priority': 'high', 'category': 'quality'},
                    {'lesson': 'On-call rotation improves response time', 'priority': 'high', 'category': 'process'},
                    {'lesson': 'Detailed reproduction steps accelerate fixes', 'priority': 'medium', 'category': 'process'}
                ],
                'key_achievements': [
                    'Resolved 87 bugs (12% above target)',
                    'Critical bug response time under 1 hour',
                    'Reduced average resolution time by 30%',
                    'Implemented effective triage process'
                ],
                'challenges_faced': [
                    {'challenge': 'Higher than expected regression rate', 'impact': 'medium'},
                    {'challenge': 'Inconsistent bug report quality', 'impact': 'medium'}
                ],
                'improvement_recommendations': [
                    'Expand automated regression testing',
                    'Create bug report template with required fields',
                    'Implement fix documentation checklist',
                    'Set up bug analytics dashboard'
                ],
                'overall_sentiment_score': Decimal('0.76'),
                'team_morale_indicator': 'moderate',
                'performance_trend': 'improving',
                'ai_generated_at': now - timedelta(days=10),
                'ai_confidence_score': Decimal('0.84'),
                'created_by': board_members[0],
                'finalized_by': board_members[0],
                'finalized_at': now - timedelta(days=8)
            }
        )
        if created:
            print(f'  ✓ Created: {retro1.title}')
            created_count += 1
            
            LessonLearned.objects.get_or_create(
                retrospective=retro1,
                board=board,
                title='Root Cause Analysis Prevents Bug Recurrence',
                defaults={
                    'description': 'Implementing thorough root cause analysis for all critical bugs reduced recurrence rate from 15% to 5%. Time invested in analysis pays off long-term.',
                    'category': 'quality',
                    'priority': 'high',
                    'status': 'implemented',
                    'recommended_action': 'Require root cause analysis documentation for all critical and high-priority bugs',
                    'implementation_date': (now - timedelta(days=45)).date(),
                    'expected_benefit': 'Reduce bug recurrence by 60%',
                    'actual_benefit': 'Reduced recurrence from 15% to 5% (67% reduction)',
                    'success_metrics': [
                        {'metric': 'recurrence_rate', 'before': 15, 'after': 5}
                    ],
                    'ai_suggested': True,
                    'ai_confidence': Decimal('0.91'),
                    'action_owner': board_members[0]
                }
            )
            
            ImprovementMetric.objects.get_or_create(
                retrospective=retro1,
                board=board,
                metric_name='Average Bug Resolution Time',
                defaults={
                    'metric_type': 'cycle_time',
                    'metric_value': Decimal('2.3'),
                    'previous_value': Decimal('3.3'),
                    'target_value': Decimal('2.0'),
                    'change_amount': Decimal('-1.0'),
                    'change_percentage': Decimal('-30.30'),
                    'trend': 'improving',
                    'unit_of_measure': 'days',
                    'higher_is_better': False,
                    'measured_at': (now - timedelta(days=10)).date()
                }
            )
        else:
            print(f'  ℹ Already exists: {retro1.title}')

# Count totals
total_retrospectives = ProjectRetrospective.objects.filter(
    board__in=[b for _, b in boards_data]
).count()
total_lessons = LessonLearned.objects.filter(
    board__in=[b for _, b in boards_data]
).count()
total_metrics = ImprovementMetric.objects.filter(
    board__in=[b for _, b in boards_data]
).count()
total_actions = RetrospectiveActionItem.objects.filter(
    board__in=[b for _, b in boards_data]
).count()

print('\n' + '=' * 80)
print('✅ RETROSPECTIVE DEMO DATA CREATION COMPLETE!')
print('=' * 80)
print(f'\n📊 Summary:')
print(f'   New retrospectives created: {created_count}')
print(f'   Total retrospectives: {total_retrospectives}')
print(f'   Total lessons learned: {total_lessons}')
print(f'   Total improvement metrics: {total_metrics}')
print(f'   Total action items: {total_actions}')
print('\n💡 You can now view retrospectives in the demo boards!')
print('=' * 80)
