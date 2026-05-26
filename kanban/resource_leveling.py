"""
Resource Leveling AI Service
Algorithms for workload optimization, skill matching, and intelligent task assignment
"""
from django.contrib.auth.models import User
from django.utils import timezone
from django.db.models import Q, Avg, Count, Sum
from datetime import timedelta
from typing import List, Dict, Optional, Tuple
import logging

from kanban.resource_leveling_models import (
    UserPerformanceProfile,
    TaskAssignmentHistory,
    ResourceLevelingSuggestion
)

logger = logging.getLogger(__name__)


class ResourceLevelingService:
    """
    Main service for AI-powered resource leveling and optimization
    """
    
    def __init__(self, organization=None):
        # Organization is optional - simplified mode doesn't require it
        self.organization = organization
    
    def _is_qualified_candidate(self, profile):
        """
        Check if a user has enough data to be a valid reassignment candidate.
        
        A user must have at least ONE of:
        - 1+ completed tasks (demonstrates velocity/history)
        - 1+ skill keywords configured (enables skill matching)
        - 1+ hours logged in current workload (actively working)
        
        Users with zero history provide no basis for velocity or skill-match
        calculations and should not receive AI-generated reassignment suggestions.
        """
        has_completed_tasks = profile.total_tasks_completed > 0
        has_skills = bool(profile.skill_keywords)
        has_logged_hours = profile.current_workload_hours > 0
        return has_completed_tasks or has_skills or has_logged_hours
    
    def get_or_create_profile(self, user, board=None):
        """
        Get or create performance profile for user
        Always fetches fresh data from database and updates workload.

        ``board`` (optional): when provided, the workload is computed against
        this specific board instead of the user's own workspace scope. Pass
        this from per-board reports so a user's demo-mode flag doesn't hide
        their tasks on the board being analyzed.
        """
        profile, created = UserPerformanceProfile.objects.get_or_create(
            user=user,
            defaults={
                'organization': self.organization,
                'weekly_capacity_hours': 40.0,
                'velocity_score': 1.0,
                'quality_score': 3.0
            }
        )

        # For existing profiles, refresh from database to avoid stale data
        if not created:
            profile.refresh_from_db()

        if created or not profile.total_tasks_completed:
            # Initialize with historical data
            profile.update_metrics(board=board)

        # Always refresh current workload to ensure real-time accuracy
        profile.update_current_workload(board=board)
        
        # Merge user's declared profile skills into AI skill_keywords so the
        # resource optimizer can use them for skill matching and qualification.
        # Declared skills get a weight of 5 (moderate confidence) so they
        # contribute meaningfully but don't overwhelm task-history-derived skills.
        self._sync_profile_skills(user, profile)
        
        return profile
    
    def _sync_profile_skills(self, user, performance_profile):
        """
        Merge user-declared skills from UserProfile into the AI's skill_keywords.
        This bridges the gap between the profile page skills and the AI engine.
        """
        try:
            user_profile = user.profile  # accounts.UserProfile via OneToOneField
        except Exception:
            return  # No UserProfile exists
        
        declared_skills = getattr(user_profile, 'skills', None)
        if not declared_skills:
            return
        
        # Extract skill names and normalize to lowercase keywords
        skill_names = []
        for skill in declared_skills:
            name = skill.get('name', '') if isinstance(skill, dict) else str(skill)
            if name:
                # Split multi-word skills into individual keywords too
                # e.g. "Project Management" -> ["project", "management"]
                skill_names.extend(name.lower().split())
        
        if not skill_names:
            return
        
        # Merge into skill_keywords with a base weight of 5 for declared skills
        keywords = dict(performance_profile.skill_keywords or {})
        changed = False
        for kw in skill_names:
            if len(kw) < 3:
                continue  # Skip very short words to match existing filtering
            if kw not in keywords or keywords[kw] < 5:
                keywords[kw] = max(keywords.get(kw, 0), 5)
                changed = True
        
        if changed:
            performance_profile.skill_keywords = keywords
            performance_profile.save(update_fields=['skill_keywords'])
    
    def analyze_task_assignment(self, task, potential_assignees=None, requesting_user=None, temp_workload_adjustments=None, board=None, diversity_penalties=None):
        """
        Analyze a task and suggest optimal assignment

        Args:
            task: Task object to analyze
            potential_assignees: Optional list of User objects to consider.
                                If None, considers all board members
            requesting_user: User requesting the analysis (unused, kept for API compatibility)
            temp_workload_adjustments: Dict of {user_id: task_count_delta} for tracking
                                       pending suggestions. Values can be POSITIVE (user is
                                       projected to receive tasks from earlier suggestions
                                       in this run) or NEGATIVE (user is projected to lose
                                       tasks). This enables cascading projected-state
                                       generation: each suggestion is analyzed against the
                                       state that would result after all earlier accepted
                                       suggestions in the same run are applied.
            board: Optional Board object. If provided, used instead of task.column.board
                   (allows analysis of unsaved/proxy tasks during task creation)
            diversity_penalties: Dict of {user_id: penalty_points} to subtract from each
                                 candidate's overall_score. Used to deprioritize team
                                 members who have already been selected as the target of
                                 prior suggestions in the same generation run, so a
                                 single user isn't recommended for every task.

        Returns:
            Dict with suggestions and impact analysis
        """
        from kanban.models import Task
        
        # Resolve board first so profile fetching uses board-specific utilization.
        # Without board context, demo personas (who have no personal boards) appear
        # at 0% utilization, making the AI think they are not overloaded and setting
        # the reassignment threshold to 15 pts instead of 5 — so no suggestions fire.
        if board is None:
            board = task.column.board if hasattr(task, 'column') and task.column else None

        # Get potential assignees - all board members are eligible
        if potential_assignees is None:
            if not board:
                return {'error': 'Task must be in a column on a board'}
            # Show ALL board members as potential assignees
            potential_assignees = list(User.objects.filter(board_memberships__board=board))

        if not potential_assignees:
            return {'error': 'No potential assignees available'}

        # IMPORTANT: Include current assignee in analysis for comparison
        # even if they're not a board member (e.g., demo users)
        current_assignee = task.assigned_to
        if current_assignee and current_assignee not in potential_assignees:
            potential_assignees = [current_assignee] + potential_assignees

        # Get profiles with board context so utilization_percentage reflects this
        # board's actual workload (not the user's cross-board workspace total).
        profiles = []
        for user in potential_assignees:
            profile = self.get_or_create_profile(user, board=board)
            # Always include the current assignee for comparison, even if unqualified
            is_current = (current_assignee and user.id == current_assignee.id)
            if is_current or self._is_qualified_candidate(profile):
                profiles.append(profile)

        if not profiles:
            return {
                'error': 'No reallocation suggestions — insufficient team data for other members',
                'no_qualified_candidates': True
            }

        # Build task context
        task_text = f"{task.title} {task.description or ''}"
        
        # Analyze each candidate
        candidates = []
        for profile in profiles:
            analysis = self._analyze_candidate(
                task, task_text, profile, temp_workload_adjustments, board, diversity_penalties
            )
            candidates.append(analysis)
        
        # Sort by overall score
        candidates.sort(key=lambda x: x['overall_score'], reverse=True)
        
        # Identify top recommendation
        top_candidate = candidates[0] if candidates else None
        current_assignee = task.assigned_to
        
        result = {
            'task_id': getattr(task, 'id', None),
            'task_title': task.title,
            'current_assignee': current_assignee.username if current_assignee else None,
            'top_recommendation': top_candidate,
            'all_candidates': candidates,
            'should_reassign': False,
            'reasoning': ""
        }
        
        # Determine if reassignment is recommended
        if top_candidate and current_assignee:
            current_analysis = next((c for c in candidates if c['user_id'] == current_assignee.id), None)
            if current_analysis:
                # Use a lower threshold when the current assignee is overloaded (>90% utilization)
                # to make the system more responsive to workload imbalance
                if current_analysis['utilization'] > 90:
                    threshold = 5  # Lower bar when assignee is overloaded
                else:
                    threshold = 15  # Standard: at least 15 points improvement
                
                improvement = top_candidate['overall_score'] - current_analysis['overall_score']
                if improvement > threshold:
                    result['should_reassign'] = True
                    result['reasoning'] = self._generate_reassignment_reasoning(
                        top_candidate, current_analysis, improvement
                    )
        elif top_candidate and not current_assignee:
            # Unassigned task - recommend top candidate only if they're not already overloaded
            if top_candidate['utilization'] <= 90:
                result['should_reassign'] = True
                result['reasoning'] = self._generate_initial_assignment_reasoning(top_candidate)
        
        return result
    
    def _analyze_candidate(self, task, task_text, profile, temp_workload_adjustments=None, board=None, diversity_penalties=None):
        """
        Analyze a single candidate for task assignment

        Returns dict with scores and metrics
        """
        # Check if user has task history on this board
        has_history = profile.total_tasks_completed > 0

        # 1. Skill match score (0-100)
        skill_score = profile.calculate_skill_match(task_text)

        # 2. Calculate ACTUAL current workload for this board
        # This is more accurate than profile.current_active_tasks which might be org-filtered
        from kanban.models import Task
        if board:
            actual_task_count = Task.objects.filter(
                assigned_to=profile.user,
                column__board=board,
                completed_at__isnull=True
            ).exclude(column__name__icontains='done').count()
        else:
            # Fallback to profile's stored count
            actual_task_count = profile.current_active_tasks

        # Adjust for projected workload changes from earlier suggestions in this run.
        # Delta can be POSITIVE (user is projected to receive tasks from prior accepted
        # suggestions) or NEGATIVE (user is projected to lose tasks because they were
        # the current_assignee in a prior suggestion that moves work elsewhere).
        temp_task_count = 0
        if temp_workload_adjustments and profile.user.id in temp_workload_adjustments:
            temp_task_count = temp_workload_adjustments[profile.user.id]

        total_task_count = max(actual_task_count + temp_task_count, 0)

        # Adjust utilization to reflect the projected state. ~15% per task is a
        # rough but consistent overhead estimate matching the per-task workload
        # we apply elsewhere. Clamp at 0 — a user can't have negative utilization.
        adjusted_utilization = max(profile.utilization_percentage + (temp_task_count * 15), 0)
        availability_score = max(100 - adjusted_utilization, 0)
        
        # 3. Velocity score (normalized to 0-100)
        # Only use velocity if they have history, otherwise use neutral baseline
        if has_history:
            velocity_normalized = min(profile.velocity_score * 50, 100)  # 2.0 velocity = 100 points
        else:
            velocity_normalized = 50.0  # Neutral - no data available
        
        # 4. Reliability score (on-time completion rate)
        # Only use if they have history, otherwise neutral
        if has_history:
            reliability_score = profile.on_time_completion_rate
        else:
            reliability_score = 50.0  # Neutral - no data available
        
        # 5. Quality score (normalized to 0-100)
        quality_normalized = (profile.quality_score / 5.0) * 100
        
        # For users without history, increase weight on availability and skills
        # For users with history, use historical performance metrics
        if has_history:
            # Standard weighted score with full metrics
            overall_score = (
                skill_score * 0.30 +          # 30% weight on skills
                availability_score * 0.25 +    # 25% weight on availability
                velocity_normalized * 0.20 +   # 20% weight on velocity
                reliability_score * 0.15 +     # 15% weight on reliability
                quality_normalized * 0.10      # 10% weight on quality
            )
        else:
            # For users without history: same weight scheme as above but apply
            # a confidence discount since we have no track record to back
            # velocity, reliability, and quality scores.
            # Users with skills get a smaller discount than those without.
            has_skills = bool(profile.skill_keywords)
            raw_score = (
                skill_score * 0.30 +          # 30% weight on skills
                availability_score * 0.25 +    # 25% weight on availability
                velocity_normalized * 0.20 +   # 20% weight on velocity
                reliability_score * 0.15 +     # 15% weight on reliability
                quality_normalized * 0.10      # 10% weight on quality
            )
            # Apply confidence discount: 25% discount if they have skills, 40% if they don't
            confidence_factor = 0.75 if has_skills else 0.60
            overall_score = raw_score * confidence_factor

        # Diversity penalty: deprioritize users who have already been selected as the
        # target of one or more prior suggestions in the same generation run. Without
        # this, the candidate with the lowest baseline utilization wins every task
        # because the per-task projected overhead (15%) is smaller than the
        # availability gap to the next-best candidate.
        if diversity_penalties:
            penalty = diversity_penalties.get(profile.user.id, 0)
            overall_score = max(overall_score - penalty, 0)

        # Predict completion time (use actual task count for workload calculation)
        estimated_hours = self._predict_completion_time_with_workload(profile, task, total_task_count)
        estimated_completion_date = timezone.now() + timedelta(hours=estimated_hours)
        
        return {
            'user_id': profile.user.id,
            'username': profile.user.username,
            'display_name': profile.user.get_full_name() or profile.user.username,
            'overall_score': round(overall_score, 1),
            'skill_match': round(skill_score, 1),
            'availability': round(availability_score, 1),
            'velocity': round(velocity_normalized, 1),
            'reliability': round(reliability_score, 1),
            'quality': round(quality_normalized, 1),
            'estimated_hours': round(estimated_hours, 1),
            'estimated_completion': estimated_completion_date.isoformat(),
            'current_workload': total_task_count,  # Use actual + temporary count
            'utilization': round(adjusted_utilization, 1)  # Use adjusted utilization
        }
    
    def _predict_completion_time_with_workload(self, profile, task, actual_task_count):
        """
        Predict completion time based on actual workload
        
        FORMULA FOR TASK COMPLETION TIME ESTIMATION:
        ============================================
        
        estimated_time = base_time × complexity_multiplier × workload_multiplier
        
        Where:
        1. base_time = User's historical avg (or 8.0h default for new users)
           - Clamped between 4-40 hours to prevent extreme values
           - Uses historical data when available (profile.avg_completion_time_hours)
        
        2. complexity_multiplier = task.complexity_score / 5
           - Complexity score ranges from 1 (simple) to 5 (very complex)
           - Normalized to 0.2-1.0 multiplier range
           - If no complexity score set, multiplier = 1.0
        
        3. workload_multiplier = 1.0 + (active_tasks × 0.08)
           - Each active task adds 8% overhead for context switching
           - Based on research showing productivity loss from task switching
           - Example: 10 active tasks = 1.0 + (10 × 0.08) = 1.8x multiplier
        
        EXAMPLE CALCULATION:
        -------------------
        For a user with 27 active tasks and complexity score of 3:
        - base_time = 8.0 hours (new user default)
        - complexity_multiplier = 3/5 = 0.6
        - workload_multiplier = 1.0 + (27 × 0.08) = 1.0 + 2.16 = 3.16
        - estimated_time = 8.0 × 0.6 × 3.16 = 15.17 hours per task
        
        Note: Total workload shown in UI (e.g., "123h") is the sum of all
        active task estimates, not the estimate for a single task.
        
        Args:
            profile: UserPerformanceProfile
            task: Task object
            actual_task_count: Actual number of active tasks for this user
        
        Returns:
            Estimated hours to complete this specific task
        """
        # Ensure base_time is always positive (min 4 hours, max 40 hours)
        # Some profiles may have corrupted/negative values
        raw_base = profile.avg_completion_time_hours or 8.0
        base_time = max(4.0, min(abs(raw_base) if raw_base != 0 else 8.0, 40.0))
        
        # Adjust for complexity
        if task.complexity_score:
            complexity_multiplier = task.complexity_score / 5
            estimated_time = base_time * complexity_multiplier
        else:
            estimated_time = base_time
        
        # Adjust for current workload - each active task adds overhead
        if actual_task_count > 0:
            # Each active task adds ~8% overhead due to context switching
            workload_multiplier = 1.0 + (actual_task_count * 0.08)
            estimated_time *= workload_multiplier
        
        return estimated_time
    
    def _generate_reassignment_reasoning(self, recommended, current, improvement):
        """Generate human-readable reasoning for reassignment"""
        reasons = []
        
        # Workload comparison - most important for balancing
        if recommended['current_workload'] == 0:
            reasons.append(f"{recommended['display_name']} is available (0 tasks, 100% capacity free)")
        elif recommended['utilization'] < current['utilization'] - 20:
            reasons.append(
                f"Better workload balance: {recommended['display_name']} has {recommended['current_workload']} tasks "
                f"({recommended['utilization']:.0f}%) vs {current['username']} with {current['current_workload']} tasks "
                f"({current['utilization']:.0f}%)"
            )
        elif recommended['current_workload'] < current['current_workload'] - 1:
            reasons.append(
                f"{recommended['display_name']} less loaded: {recommended['current_workload']} tasks vs {current['current_workload']} tasks"
            )
        
        # Skill match comparison
        if recommended['skill_match'] > 60:
            if current['skill_match'] > 0 and recommended['skill_match'] > current['skill_match'] + 10:
                reasons.append(f"Better skill match ({recommended['skill_match']:.0f}% vs {current['skill_match']:.0f}%)")
            elif recommended['skill_match'] > 70:
                reasons.append(f"Good skill match ({recommended['skill_match']:.0f}%)")
        
        # Time savings (if available)
        time_diff = current.get('estimated_hours', 0) - recommended.get('estimated_hours', 0)
        if time_diff > 0.5 and current.get('estimated_hours', 0) > 0:
            time_saved_pct = (time_diff / current['estimated_hours']) * 100
            reasons.append(f"{time_saved_pct:.0f}% faster estimated completion")
        
        if not reasons:
            reasons.append(f"Better overall fit based on availability and skills")
        
        return f"Move task to {recommended['display_name']}: " + ", ".join(reasons)
    
    def _generate_initial_assignment_reasoning(self, recommended):
        """Generate reasoning for initial assignment - provide objective facts"""
        reasons = []
        
        # 1. Availability (most objective metric)
        if recommended['current_workload'] == 0:
            reasons.append(f"Available (0 tasks, 100% capacity free)")
        else:
            task_info = f"{recommended['current_workload']} tasks, {recommended['utilization']:.0f}% capacity used"
            if recommended['utilization'] < 30:
                reasons.append(f"Low workload ({task_info})")
            elif recommended['utilization'] < 60:
                reasons.append(f"Moderate workload ({task_info})")
            else:
                reasons.append(f"Current workload: {task_info}")
        
        # 2. Skill match (objective assessment)
        if recommended['skill_match'] >= 70:
            reasons.append(f"Strong skill match ({recommended['skill_match']:.0f}%)")
        elif recommended['skill_match'] >= 50:
            reasons.append(f"Moderate skill match ({recommended['skill_match']:.0f}%)")
        elif recommended['skill_match'] > 0:
            reasons.append(f"Skill match: {recommended['skill_match']:.0f}%")
        
        # 3. Performance (only if data available - velocity > 50 means they have history)
        if recommended['velocity'] > 55:
            reasons.append(f"High velocity ({recommended['velocity']:.0f} score)")
        
        if not reasons:
            reasons.append("Best available based on current capacity")
        
        return f"Assign to {recommended['display_name']}: " + ", ".join(reasons)
    
    def create_suggestion(self, task, force_analysis=False, requesting_user=None, temp_workload_adjustments=None, diversity_penalties=None):
        """
        Create and store a ResourceLevelingSuggestion if beneficial

        Args:
            task: Task object
            force_analysis: If True, create suggestion even for well-assigned tasks
            requesting_user: User requesting the suggestion
            temp_workload_adjustments: Dict of {user_id: task_count_delta} for cascading
                                       projected state across a multi-suggestion run.
                                       See analyze_task_assignment for full semantics.
            diversity_penalties: Dict of {user_id: penalty_points} to deprioritize users
                                 who have already been targeted in earlier suggestions
                                 in this run.

        Returns:
            ResourceLevelingSuggestion object or None
        """
        # --- Guard: require sufficient task and team data before generating a suggestion ---
        # This prevents fabricated metrics (e.g. "88% savings vs team median") for brand-new
        # tasks that lack any real historical grounding.

        # 1. Task must have at least one time log entry OR a due date set.
        #    A task with neither has no concrete scope or pacing data.
        from kanban.budget_models import TimeEntry
        has_time_log = TimeEntry.objects.filter(task=task).exists()
        has_due_date = bool(task.due_date)
        if not (has_time_log or has_due_date):
            logger.debug(
                f"Suppressing resource suggestion for task {task.id}: no time log entries and no due date."
            )
            return None

        # 2. At least one board member (other than the current assignee) must have
        #    completed at least one task, so the team median is backed by real data.
        board = task.column.board if hasattr(task, 'column') and task.column else None
        if board:
            exclude_user_ids = [task.assigned_to.id] if task.assigned_to else []
            has_peer_history = UserPerformanceProfile.objects.filter(
                user__in=User.objects.filter(board_memberships__board=board),
                total_tasks_completed__gt=0,
            ).exclude(user_id__in=exclude_user_ids).exists()
            if not has_peer_history:
                logger.debug(
                    f"Suppressing resource suggestion for task {task.id}: no peer with completed-task history on this board."
                )
                return None

        # 3. Task must have been open for at least 1 hour before any suggestion is shown.
        #    This prevents a banner firing the instant a task is saved.
        #    Tasks with future created_at (e.g. demo/refreshed boards) are always allowed.
        if hasattr(task, 'created_at') and task.created_at:
            task_age = timezone.now() - task.created_at
            if timedelta(0) <= task_age < timedelta(hours=1):
                logger.debug(
                    f"Suppressing resource suggestion for task {task.id}: task is only "
                    f"{task_age.total_seconds() / 60:.1f} minutes old (< 1 hour required)."
                )
                return None

        # --- End of guard conditions ---

        analysis = self.analyze_task_assignment(
            task,
            requesting_user=requesting_user,
            temp_workload_adjustments=temp_workload_adjustments,
            diversity_penalties=diversity_penalties,
        )
        
        if 'error' in analysis:
            logger.warning(f"Cannot analyze task {task.id}: {analysis['error']}")
            return None
        
        if not analysis['should_reassign'] and not force_analysis:
            return None
        
        top = analysis['top_recommendation']
        if not top:
            return None
        
        current_assignee = task.assigned_to
        suggested_user = User.objects.get(id=top['user_id'])
        
        # Calculate time savings
        current_analysis = None
        time_savings_explanation = ""
        if current_assignee:
            current_analysis = next(
                (c for c in analysis['all_candidates'] if c['user_id'] == current_assignee.id),
                None
            )
        
        # Check if EACH user individually has work history for accurate explainability
        suggested_profile = self.get_or_create_profile(suggested_user)
        current_profile = self.get_or_create_profile(current_assignee) if current_assignee else None
        suggested_has_history = suggested_profile.total_tasks_completed > 0
        current_has_history = current_profile and current_profile.total_tasks_completed > 0
        
        if current_analysis:
            # Direct comparison when task is already assigned
            time_savings = current_analysis['estimated_hours'] - top['estimated_hours']
            time_savings_pct = (time_savings / current_analysis['estimated_hours']) * 100 if current_analysis['estimated_hours'] > 0 else 0
            # Explainability: Accurately describe what data each estimate is based on
            if suggested_has_history and current_has_history:
                # Both users have history - mention velocity, workload, and skill match
                time_savings_explanation = f" The {time_savings_pct:.0f}% time savings is calculated by comparing estimated completion times: {current_assignee.get_full_name() or current_assignee.username} ({current_analysis['estimated_hours']:.1f}h) vs {top['display_name']} ({top['estimated_hours']:.1f}h) based on their workload, velocity, and skill match."
            elif current_has_history and not suggested_has_history:
                # Only current assignee has history - be transparent about suggested user's lack of data
                time_savings_explanation = f" The {time_savings_pct:.0f}% time savings is calculated by comparing estimated completion times: {current_assignee.get_full_name() or current_assignee.username} ({current_analysis['estimated_hours']:.1f}h, based on historical data) vs {top['display_name']} ({top['estimated_hours']:.1f}h, based on availability and baseline estimate — limited historical data)."
            elif suggested_has_history and not current_has_history:
                time_savings_explanation = f" The {time_savings_pct:.0f}% time savings is calculated by comparing estimated completion times: {current_assignee.get_full_name() or current_assignee.username} ({current_analysis['estimated_hours']:.1f}h, baseline estimate) vs {top['display_name']} ({top['estimated_hours']:.1f}h, based on historical data)."
            else:
                # Neither has history
                time_savings_explanation = f" The {time_savings_pct:.0f}% time savings is calculated by comparing estimated completion times: {current_assignee.get_full_name() or current_assignee.username} ({current_analysis['estimated_hours']:.1f}h) vs {top['display_name']} ({top['estimated_hours']:.1f}h). Since team members are new, estimates use baseline assumptions (8h per task) adjusted by current workload and task complexity."
        else:
            # For unassigned tasks, compare against team average or median
            all_estimates = [c['estimated_hours'] for c in analysis['all_candidates']]
            if all_estimates:
                # Use median as baseline (more robust than mean)
                all_estimates.sort()
                median_estimate = all_estimates[len(all_estimates) // 2]
                time_savings = median_estimate - top['estimated_hours']
                time_savings_pct = (time_savings / median_estimate) * 100 if median_estimate > 0 else 0
                # Explainability: Show calculation for unassigned tasks
                if suggested_has_history:
                    time_savings_explanation = f" The {time_savings_pct:.0f}% time savings is calculated by comparing {top['display_name']}'s estimated time ({top['estimated_hours']:.1f}h) against the team median ({median_estimate:.1f}h), factoring in their workload, velocity, and skill match."
                else:
                    time_savings_explanation = f" The {time_savings_pct:.0f}% time savings is calculated by comparing {top['display_name']}'s estimated time ({top['estimated_hours']:.1f}h) against the team median ({median_estimate:.1f}h). Since team members are new, estimates use baseline assumptions (8h per task) adjusted by current workload and task complexity."
            else:
                time_savings = 0
                time_savings_pct = 0
        
        # Determine workload impact
        workload_impact = self._determine_workload_impact(top, current_analysis)
        
        # Calculate actual AI confidence in this suggestion (not user suitability)
        ai_confidence = self._calculate_suggestion_confidence(top, current_analysis, workload_impact)
        
        # Enhance reasoning with explainability - add calculation explanation
        enhanced_reasoning = analysis['reasoning']
        if time_savings_explanation:
            enhanced_reasoning += time_savings_explanation
        
        # Create suggestion
        suggestion = ResourceLevelingSuggestion.objects.create(
            task=task,
            organization=self.organization,
            current_assignee=current_assignee,
            suggested_assignee=suggested_user,
            confidence_score=ai_confidence,  # AI confidence in the suggestion
            time_savings_hours=max(time_savings, 0),
            time_savings_percentage=max(time_savings_pct, 0),
            skill_match_score=top['skill_match'],
            workload_impact=workload_impact,
            current_projected_date=timezone.now() + timedelta(hours=current_analysis['estimated_hours']) if current_analysis else None,
            suggested_projected_date=timezone.now() + timedelta(hours=top['estimated_hours']),
            reasoning=enhanced_reasoning,
            expires_at=timezone.now() + timedelta(hours=48)
        )
        
        return suggestion
    
    def _calculate_suggestion_confidence(self, recommended, current, workload_impact):
        """
        Calculate AI's confidence in this suggestion (0-100).

        Confidence has two distinct components:

        1. Data-quality ceiling: how much real historical data backs this
           recommendation. A suggestion based on dozens of completed tasks and
           a populated skill profile can credibly claim 90%; a suggestion based
           on a user with no completed tasks and no declared skills cannot
           credibly claim more than ~70% regardless of how clean the workload
           math is.
        2. Improvement signal: how strong the case for this specific move is —
           workload imbalance corrected, availability gap, skill fit, score
           delta. Strong signals push toward the ceiling; weak signals leave
           confidence well below it.

        The two components multiply, not add. This is why every suggestion no
        longer pegs at 92% — the ceiling itself moves with the data.
        """
        recommended_profile = UserPerformanceProfile.objects.filter(user_id=recommended['user_id']).first()
        current_profile = UserPerformanceProfile.objects.filter(user_id=current['user_id']).first() if current else None

        recommended_has_history = recommended_profile and recommended_profile.total_tasks_completed > 0
        current_has_history = current_profile and current_profile.total_tasks_completed > 0

        # -------- Component 1: Data-quality ceiling (50–92) --------
        # Start at a modest 50; each piece of real data raises the ceiling.
        ceiling = 50.0

        # Recommended user's velocity backing: each completed task adds a little,
        # capped so a single prolific person doesn't max out alone.
        if recommended_profile:
            completed = recommended_profile.total_tasks_completed
            ceiling += min(completed * 1.5, 18)  # up to +18 from 12+ completed tasks

        # Current assignee's history makes the comparison more reliable.
        if current_profile:
            current_completed = current_profile.total_tasks_completed
            ceiling += min(current_completed * 0.8, 10)  # up to +10
        elif not current:
            # Unassigned task — no comparison needed, neutral.
            ceiling += 5

        # Skill keyword coverage on the recommended profile.
        if recommended_profile and recommended_profile.skill_keywords:
            ceiling += min(len(recommended_profile.skill_keywords) * 0.3, 8)  # up to +8

        # On-time history on the recommended profile adds reliability evidence.
        if recommended_profile and recommended_profile.on_time_completion_rate > 0:
            ceiling += 3

        # Hard cap at 92 — never claim certainty.
        ceiling = min(ceiling, 92.0)

        # -------- Component 2: Improvement signal (0.0–1.0) --------
        # 1.0 = strong, clear, multi-dimensional improvement.
        # 0.5 = mild improvement.
        # <0.5 = weak case; recommended barely beats current.
        signal = 0.55  # neutral starting point

        # Workload improvement (the most objective evidence).
        if current:
            util_diff = current['utilization'] - recommended['utilization']
            if util_diff > 40:
                signal += 0.20
            elif util_diff > 20:
                signal += 0.13
            elif util_diff > 10:
                signal += 0.08
            elif util_diff > 0:
                signal += 0.03
            elif util_diff < -10:
                signal -= 0.10
        else:
            signal += 0.05  # first assignment — small boost

        # Overall suitability score gap.
        if current:
            score_diff = recommended['overall_score'] - current['overall_score']
            if score_diff > 20:
                signal += 0.12
            elif score_diff > 10:
                signal += 0.07
            elif score_diff > 3:
                signal += 0.03
            elif score_diff < 0:
                signal -= 0.08
        else:
            if recommended['overall_score'] > 75:
                signal += 0.08
            elif recommended['overall_score'] > 60:
                signal += 0.04
            elif recommended['overall_score'] < 45:
                signal -= 0.05

        # Skill match contributes — but only if the profile has real skill data
        # (otherwise the score is a neutral 50 placeholder, not real evidence).
        has_real_skills = recommended_profile and bool(recommended_profile.skill_keywords)
        if has_real_skills:
            if recommended['skill_match'] > 70:
                signal += 0.08
            elif recommended['skill_match'] > 50:
                signal += 0.04
            elif recommended['skill_match'] < 20:
                signal -= 0.03

        # Recommended user's current workload — penalize piling onto someone
        # already loaded; reward when they're in the sweet spot.
        if 1 <= recommended['current_workload'] <= 3:
            signal += 0.05
        elif 4 <= recommended['current_workload'] <= 7:
            signal += 0.02
        elif recommended['current_workload'] > 10:
            signal -= 0.08

        # Workload impact type — small additive nudges.
        impact_boost = {
            'reduces_bottleneck': 0.06,
            'balances_load': 0.04,
            'better_skills': 0.03,
            'improves_timeline': 0.02,
        }
        signal += impact_boost.get(workload_impact, 0)

        # Clamp signal to [0.35, 1.05] — even a weak case has some merit if it
        # was generated, and a great case can briefly exceed 1.0 before clamping.
        signal = max(0.35, min(signal, 1.05))

        # -------- Combine: ceiling × signal, with a floor --------
        # Floor of 38 means we never show truly unconfident suggestions — they
        # would have been filtered out upstream by the reassignment threshold.
        confidence = ceiling * signal
        confidence = max(38.0, min(confidence, ceiling))

        return round(confidence, 1)
    
    def _determine_workload_impact(self, recommended, current):
        """Determine the type of workload impact"""
        if not current:
            return 'better_skills'
        
        util_diff = current['utilization'] - recommended['utilization']
        skill_diff = recommended['skill_match'] - current['skill_match']
        
        if util_diff > 30:
            return 'reduces_bottleneck'
        elif util_diff > 10:
            return 'balances_load'
        elif skill_diff > 20:
            return 'better_skills'
        else:
            return 'improves_timeline'
    
    def _create_suggestion_for_candidate(self, task, candidate, current_analysis, analysis):
        """
        Create a ResourceLevelingSuggestion for a specific alternative candidate.
        Used when the top candidate has hit the per-user suggestion cap.
        """
        suggested_user = User.objects.get(id=candidate['user_id'])
        current_assignee = task.assigned_to
        
        workload_impact = self._determine_workload_impact(candidate, current_analysis)
        
        # Calculate time savings
        if current_analysis:
            time_savings = current_analysis['estimated_hours'] - candidate['estimated_hours']
            time_savings_pct = (time_savings / current_analysis['estimated_hours']) * 100 if current_analysis['estimated_hours'] > 0 else 0
        else:
            time_savings = 0
            time_savings_pct = 0
        
        # Generate reasoning
        if current_analysis:
            reasoning = self._generate_reassignment_reasoning(
                candidate, current_analysis,
                candidate['overall_score'] - current_analysis['overall_score']
            )
        else:
            reasoning = self._generate_initial_assignment_reasoning(candidate)
        
        ai_confidence = self._calculate_suggestion_confidence(candidate, current_analysis, workload_impact)
        
        try:
            suggestion = ResourceLevelingSuggestion.objects.create(
                task=task,
                current_assignee=current_assignee,
                suggested_assignee=suggested_user,
                reasoning=reasoning,
                time_savings_percentage=max(time_savings_pct, 0),
                time_savings_hours=max(time_savings, 0),
                confidence_score=ai_confidence,
                skill_match_score=candidate['skill_match'],
                workload_impact=workload_impact,
                suggested_projected_date=timezone.now() + timedelta(hours=candidate['estimated_hours']),
                expires_at=timezone.now() + timedelta(days=7),
                status='pending'
            )
            return suggestion
        except Exception as e:
            logger.error(f"Error creating alternative suggestion: {e}")
            return None
    
    def get_board_optimization_suggestions(self, board, limit=10, requesting_user=None):
        """
        Analyze all tasks on a board and return top optimization opportunities
        Always regenerates suggestions with current workload data to ensure relevance
        
        Args:
            board: Board object
            limit: Maximum number of suggestions to return
            requesting_user: User requesting suggestions (unused, kept for API compatibility)
        
        Returns:
            List of ResourceLevelingSuggestion objects
        """
        from kanban.models import Task
        
        # Expire all old pending suggestions for this board to ensure fresh recommendations
        # This prevents showing stale suggestions based on outdated workload
        ResourceLevelingSuggestion.objects.filter(
            task__column__board=board,
            status='pending'
        ).update(status='expired')
        
        # Get all incomplete tasks on the board - no filtering by organization
        # All board members should see suggestions for all tasks
        tasks = Task.objects.filter(
            column__board=board,
            completed_at__isnull=True
        ).exclude(
            column__name__icontains='done'
        ).select_related('assigned_to', 'column')
        
        suggestions = []

        # Track how many suggestions target each user to avoid flooding one person.
        # Used both to enforce a hard per-user cap and to drive the diversity penalty
        # so that subsequent suggestions in the same run consider other candidates.
        suggestion_counts_per_user = {}
        max_suggestions_per_user = 3

        # Cascading projected state across the run. After each suggestion is accepted
        # into the result list, we mutate this dict so the NEXT analysis sees the
        # workload as it would be AFTER the prior accepted suggestion(s) are applied.
        # Positive delta = user gained tasks; negative = user lost tasks.
        projected_adjustments = {}

        # Diversity penalty grows linearly per prior suggestion targeting a given
        # user. 20 points per hit is large enough to overcome the typical 20–25
        # point availability advantage a single low-utilization person enjoys
        # over peers on a busy board, so suggestion #2 picks someone else when
        # any other credible candidate exists. The hard cap (3 per user) still
        # bounds the worst case if no alternative qualifies.
        DIVERSITY_PENALTY_PER_HIT = 20.0

        def _build_diversity_penalties():
            return {
                uid: DIVERSITY_PENALTY_PER_HIT * count
                for uid, count in suggestion_counts_per_user.items()
                if count > 0
            }

        for task in tasks:
            # Generate the suggestion against the projected state from prior accepted
            # suggestions in this run, with a diversity penalty against already-picked
            # targets so the engine doesn't keep recommending the same person.
            suggestion = self.create_suggestion(
                task,
                requesting_user=requesting_user,
                temp_workload_adjustments=projected_adjustments,
                diversity_penalties=_build_diversity_penalties(),
            )
            if suggestion:
                suggested_user_id = suggestion.suggested_assignee.id
                current_count = suggestion_counts_per_user.get(suggested_user_id, 0)

                # Only add suggestion if user hasn't reached the hard cap
                if current_count < max_suggestions_per_user:
                    suggestions.append(suggestion)
                    suggestion_counts_per_user[suggested_user_id] = current_count + 1
                    # Reflect the projected reassignment in the running state so the
                    # NEXT iteration sees workload as it would be after this move.
                    projected_adjustments[suggested_user_id] = (
                        projected_adjustments.get(suggested_user_id, 0) + 1
                    )
                    if suggestion.current_assignee:
                        cur_id = suggestion.current_assignee.id
                        projected_adjustments[cur_id] = (
                            projected_adjustments.get(cur_id, 0) - 1
                        )
                else:
                    # Top candidate hit the cap — try the next-best candidate, still
                    # operating against the projected state so the alternative also
                    # accounts for earlier accepted suggestions in this run.
                    suggestion.delete()

                    analysis = self.analyze_task_assignment(
                        task,
                        temp_workload_adjustments=projected_adjustments,
                        diversity_penalties=_build_diversity_penalties(),
                    )
                    if 'error' not in analysis and analysis.get('all_candidates'):
                        current_assignee = task.assigned_to
                        current_analysis = next(
                            (c for c in analysis['all_candidates']
                             if current_assignee and c['user_id'] == current_assignee.id), None
                        )
                        # Try candidates in score order, skipping the capped one and current assignee
                        for candidate in analysis['all_candidates']:
                            if candidate['user_id'] == suggested_user_id:
                                continue  # Already capped
                            if current_assignee and candidate['user_id'] == current_assignee.id:
                                continue  # Don't suggest keeping current assignee
                            if candidate['utilization'] > 90:
                                continue  # Don't pile more work onto overloaded members
                            alt_count = suggestion_counts_per_user.get(candidate['user_id'], 0)
                            if alt_count >= max_suggestions_per_user:
                                continue  # This candidate also capped
                            # Check if this candidate is meaningfully better than current
                            if current_analysis:
                                threshold = 5 if current_analysis['utilization'] > 90 else 15
                                if candidate['overall_score'] - current_analysis['overall_score'] <= threshold:
                                    continue
                            # Create suggestion for this alternative candidate
                            alt_suggestion = self._create_suggestion_for_candidate(
                                task, candidate, current_analysis, analysis
                            )
                            if alt_suggestion:
                                suggestions.append(alt_suggestion)
                                suggestion_counts_per_user[candidate['user_id']] = alt_count + 1
                                projected_adjustments[candidate['user_id']] = (
                                    projected_adjustments.get(candidate['user_id'], 0) + 1
                                )
                                if current_assignee:
                                    cur_id = current_assignee.id
                                    projected_adjustments[cur_id] = (
                                        projected_adjustments.get(cur_id, 0) - 1
                                    )
                                break  # Use first valid alternative

        # Sort by impact (time savings percentage * confidence)
        suggestions.sort(
            key=lambda s: s.time_savings_percentage * (s.confidence_score / 100),
            reverse=True
        )

        return suggestions[:limit]
    
    def optimize_board_workload(self, board, auto_apply=False):
        """
        Perform comprehensive workload optimization for a board
        
        Args:
            board: Board object
            auto_apply: If True, automatically apply top suggestions (be careful!)
        
        Returns:
            Dict with optimization results
        """
        suggestions = self.get_board_optimization_suggestions(board, limit=20)
        
        result = {
            'total_suggestions': len(suggestions),
            'potential_time_savings': sum(s.time_savings_hours for s in suggestions),
            'suggestions': [],
            'applied': 0
        }
        
        for suggestion in suggestions:
            suggestion_data = {
                'id': suggestion.id,
                'task': suggestion.task.title,
                'from': suggestion.current_assignee.username if suggestion.current_assignee else 'unassigned',
                'to': suggestion.suggested_assignee.username,
                'time_savings': f"{suggestion.time_savings_percentage:.0f}%",
                'confidence': f"{suggestion.confidence_score:.0f}%",
                'reasoning': suggestion.reasoning
            }
            result['suggestions'].append(suggestion_data)
            
            # Auto-apply if requested and confidence is high
            if auto_apply and suggestion.confidence_score > 75:
                suggestion.accept(board.created_by)
                result['applied'] += 1
        
        return result
    
    def get_team_workload_report(self, board, requesting_user=None):
        """
        Generate team workload report for a board
        
        Args:
            board: Board object
            requesting_user: User requesting the report (unused, kept for API compatibility)
        
        Returns:
            Dict with team member workloads and recommendations
        """
        # Show ALL board members - this is the expected UX behavior
        # All members of a board should see all other members in the workload report
        members = User.objects.filter(board_memberships__board=board)
        
        report = {
            'board': board.name,
            'team_size': members.count(),
            'members': [],
            'bottlenecks': [],
            'underutilized': []
        }
        
        for member in members:
            profile = self.get_or_create_profile(member, board=board)
            
            # Profile is already fresh from get_or_create_profile()
            
            member_data = {
                'username': member.username,
                'name': member.get_full_name() or member.username,
                'active_tasks': profile.current_active_tasks,
                'workload_hours': round(profile.current_workload_hours, 1),
                'utilization': round(profile.utilization_percentage, 1),
                'velocity': round(profile.velocity_score, 2),
                'on_time_rate': round(profile.on_time_completion_rate, 1),
                'status': 'balanced'
            }
            
            # Classify member status
            if profile.utilization_percentage > 90:
                member_data['status'] = 'overloaded'
                report['bottlenecks'].append(member_data)
            elif profile.utilization_percentage < 40:
                member_data['status'] = 'underutilized'
                report['underutilized'].append(member_data)
            
            report['members'].append(member_data)
        
        # Sort by utilization
        report['members'].sort(key=lambda x: x['utilization'], reverse=True)
        
        # Check for team capacity issues
        avg_utilization = sum(m['utilization'] for m in report['members']) / len(report['members']) if report['members'] else 0
        overloaded_count = len(report['bottlenecks'])
        
        report['average_utilization'] = round(avg_utilization, 1)
        report['team_capacity_warning'] = None
        
        # Generate capacity warnings
        if avg_utilization > 85 and overloaded_count >= len(report['members']) * 0.5:
            report['team_capacity_warning'] = {
                'level': 'critical',
                'message': f'Team is at {avg_utilization:.0f}% capacity with {overloaded_count} overloaded members. Consider adding resources or extending deadlines.',
                'recommendation': 'add_resources'
            }
        elif avg_utilization > 75:
            report['team_capacity_warning'] = {
                'level': 'warning',
                'message': f'Team is at {avg_utilization:.0f}% capacity. Monitor workload closely.',
                'recommendation': 'monitor'
            }
        
        return report
    
    def update_all_profiles(self, board):
        """
        Update performance profiles for all board members
        Useful for batch updates or scheduled tasks
        """
        members = User.objects.filter(board_memberships__board=board)
        updated = 0
        
        for member in members:
            try:
                profile = self.get_or_create_profile(member, board=board)
                profile.update_metrics(board=board)
                updated += 1
            except Exception as e:
                logger.error(f"Error updating profile for {member.username}: {e}")
        
        return {
            'total_members': members.count(),
            'updated': updated
        }


class WorkloadBalancer:
    """
    Advanced workload balancing algorithms
    """
    
    def __init__(self, organization=None):
        # Organization is optional - simplified mode doesn't require it
        self.organization = organization
        self.service = ResourceLevelingService(organization)
    
    def balance_workload(self, board, target_utilization=75.0):
        """
        Redistribute tasks to achieve target utilization across team
        
        Args:
            board: Board object
            target_utilization: Target utilization percentage for team members
        
        Returns:
            List of suggested task movements
        """
        from kanban.models import Task
        
        # Get all profiles
        members = User.objects.filter(board_memberships__board=board)
        profiles = {m.id: self.service.get_or_create_profile(m) for m in members}
        
        # Identify overloaded and underutilized members
        overloaded = [p for p in profiles.values() if p.utilization_percentage > target_utilization + 15]
        underutilized = [p for p in profiles.values() if p.utilization_percentage < target_utilization - 15]
        
        if not overloaded or not underutilized:
            return {'message': 'Team workload is already balanced', 'suggestions': []}
        
        suggestions = []
        
        # For each overloaded member, find tasks to move
        for overloaded_profile in overloaded:
            # Get their tasks, sorted by least specific to their skills
            tasks = Task.objects.filter(
                assigned_to=overloaded_profile.user,
                column__board=board,
                completed_at__isnull=True
            ).exclude(column__name__icontains='done')
            
            for task in tasks:
                if overloaded_profile.utilization_percentage <= target_utilization:
                    break  # This person is now balanced
                
                # Find best underutilized person for this task
                best_match = None
                best_score = 0
                
                for under_profile in underutilized:
                    if under_profile.utilization_percentage > target_utilization:
                        continue  # They've been assigned enough
                    
                    task_text = f"{task.title} {task.description or ''}"
                    skill_score = under_profile.calculate_skill_match(task_text)
                    
                    # Combined score: skill match + availability
                    combined_score = skill_score * 0.6 + under_profile.get_availability_score() * 0.4
                    
                    if combined_score > best_score:
                        best_score = combined_score
                        best_match = under_profile
                
                if best_match and best_score > 40:  # Minimum threshold
                    # Create suggestion
                    suggestion = self.service.create_suggestion(task, force_analysis=True)
                    if suggestion:
                        suggestions.append({
                            'task': task.title,
                            'from': overloaded_profile.user.username,
                            'to': best_match.user.username,
                            'reason': f"Balance workload: {overloaded_profile.user.username} at {overloaded_profile.utilization_percentage:.0f}% utilization"
                        })
                        
                        # Update theoretical utilization for planning
                        task_hours = overloaded_profile.predict_completion_time(task)
                        overloaded_profile.current_workload_hours -= task_hours
                        overloaded_profile.utilization_percentage = (overloaded_profile.current_workload_hours / overloaded_profile.weekly_capacity_hours) * 100
                        
                        best_match.current_workload_hours += task_hours
                        best_match.utilization_percentage = (best_match.current_workload_hours / best_match.weekly_capacity_hours) * 100
        
        return {
            'message': f'Generated {len(suggestions)} balancing suggestions',
            'suggestions': suggestions
        }
