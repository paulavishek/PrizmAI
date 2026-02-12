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
    
    def __init__(self, organization):
        self.organization = organization
    
    def get_or_create_profile(self, user):
        """Get or create performance profile for user"""
        profile, created = UserPerformanceProfile.objects.get_or_create(
            user=user,
            organization=self.organization,
            defaults={
                'weekly_capacity_hours': 40.0,
                'velocity_score': 1.0,
                'quality_score': 3.0
            }
        )
        
        if created or not profile.total_tasks_completed:
            # Initialize with historical data
            profile.update_metrics()
        
        # Always refresh current workload to ensure real-time accuracy
        profile.update_current_workload()
        
        return profile
    
    def analyze_task_assignment(self, task, potential_assignees=None, requesting_user=None, temp_workload_adjustments=None):
        """
        Analyze a task and suggest optimal assignment
        
        Args:
            task: Task object to analyze
            potential_assignees: Optional list of User objects to consider. 
                                If None, considers all board members
            requesting_user: User requesting the analysis (unused, kept for API compatibility)
            temp_workload_adjustments: Dict of {user_id: additional_task_count} for tracking pending suggestions
        
        Returns:
            Dict with suggestions and impact analysis
        """
        from kanban.models import Task
        
        # Get potential assignees - all board members are eligible
        if potential_assignees is None:
            board = task.column.board if task.column else None
            if not board:
                return {'error': 'Task must be in a column on a board'}
            # Show ALL board members as potential assignees
            potential_assignees = list(board.members.all())
        
        if not potential_assignees:
            return {'error': 'No potential assignees available'}
        
        # IMPORTANT: Include current assignee in analysis for comparison
        # even if they're not a board member (e.g., demo users)
        current_assignee = task.assigned_to
        if current_assignee and current_assignee not in potential_assignees:
            potential_assignees = [current_assignee] + potential_assignees
        
        # Get profiles for all candidates
        profiles = []
        for user in potential_assignees:
            profile = self.get_or_create_profile(user)
            profiles.append(profile)
        
        # Build task context
        task_text = f"{task.title} {task.description or ''}"
        
        # Analyze each candidate
        candidates = []
        for profile in profiles:
            analysis = self._analyze_candidate(task, task_text, profile, temp_workload_adjustments)
            candidates.append(analysis)
        
        # Sort by overall score
        candidates.sort(key=lambda x: x['overall_score'], reverse=True)
        
        # Identify top recommendation
        top_candidate = candidates[0] if candidates else None
        current_assignee = task.assigned_to
        
        result = {
            'task_id': task.id,
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
                # Recommend reassignment if top candidate is significantly better
                improvement = top_candidate['overall_score'] - current_analysis['overall_score']
                if improvement > 15:  # At least 15 points improvement
                    result['should_reassign'] = True
                    result['reasoning'] = self._generate_reassignment_reasoning(
                        top_candidate, current_analysis, improvement
                    )
        elif top_candidate and not current_assignee:
            # Unassigned task - recommend top candidate
            result['should_reassign'] = True
            result['reasoning'] = self._generate_initial_assignment_reasoning(top_candidate)
        
        return result
    
    def _analyze_candidate(self, task, task_text, profile, temp_workload_adjustments=None):
        """
        Analyze a single candidate for task assignment
        
        Returns dict with scores and metrics
        """
        # Check if user has task history on this board
        has_history = profile.total_tasks_completed > 0
        
        # 1. Skill match score (0-100)
        skill_score = profile.calculate_skill_match(task_text)
        
        # 2. Availability score (0-100) adjusted for temporary assignments
        # If we've already suggested tasks to this user in this batch, reduce their availability
        temp_task_count = 0
        if temp_workload_adjustments and profile.user.id in temp_workload_adjustments:
            temp_task_count = temp_workload_adjustments[profile.user.id]
        
        # Each suggested task reduces availability
        adjusted_utilization = profile.utilization_percentage + (temp_task_count * 15)  # ~15% per task
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
            # For users without history: prioritize availability and skills more
            overall_score = (
                skill_score * 0.35 +          # 35% weight on skills (can assess from profile)
                availability_score * 0.45 +    # 45% weight on availability (objective fact)
                velocity_normalized * 0.10 +   # 10% weight on velocity (no data, less important)
                reliability_score * 0.05 +     # 5% weight on reliability (no data, less important)
                quality_normalized * 0.05      # 5% weight on quality (minimal weight without data)
            )
        
        # Predict completion time
        estimated_hours = profile.predict_completion_time(task)
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
            'current_workload': profile.current_active_tasks + temp_task_count,  # Include temporary suggestions
            'utilization': round(adjusted_utilization, 1)  # Use adjusted utilization
        }
    
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
    
    def create_suggestion(self, task, force_analysis=False, requesting_user=None, temp_workload_adjustments=None):
        """
        Create and store a ResourceLevelingSuggestion if beneficial
        
        Args:
            task: Task object
            force_analysis: If True, create suggestion even for well-assigned tasks
            requesting_user: User requesting the suggestion
            temp_workload_adjustments: Dict of {user_id: additional_task_count} for tracking pending suggestions
        
        Returns:
            ResourceLevelingSuggestion object or None
        """
        analysis = self.analyze_task_assignment(task, requesting_user=requesting_user, temp_workload_adjustments=temp_workload_adjustments)
        
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
        if current_assignee:
            current_analysis = next(
                (c for c in analysis['all_candidates'] if c['user_id'] == current_assignee.id),
                None
            )
        
        if current_analysis:
            # Direct comparison when task is already assigned
            time_savings = current_analysis['estimated_hours'] - top['estimated_hours']
            time_savings_pct = (time_savings / current_analysis['estimated_hours']) * 100 if current_analysis['estimated_hours'] > 0 else 0
        else:
            # For unassigned tasks, compare against team average or median
            all_estimates = [c['estimated_hours'] for c in analysis['all_candidates']]
            if all_estimates:
                # Use median as baseline (more robust than mean)
                all_estimates.sort()
                median_estimate = all_estimates[len(all_estimates) // 2]
                time_savings = median_estimate - top['estimated_hours']
                time_savings_pct = (time_savings / median_estimate) * 100 if median_estimate > 0 else 0
            else:
                time_savings = 0
                time_savings_pct = 0
        
        # Determine workload impact
        workload_impact = self._determine_workload_impact(top, current_analysis)
        
        # Calculate actual AI confidence in this suggestion (not user suitability)
        ai_confidence = self._calculate_suggestion_confidence(top, current_analysis, workload_impact)
        
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
            reasoning=analysis['reasoning'],
            expires_at=timezone.now() + timedelta(hours=48)
        )
        
        return suggestion
    
    def _calculate_suggestion_confidence(self, recommended, current, workload_impact):
        """
        Calculate AI's confidence in this suggestion (0-100)
        This is different from user suitability score - it's about how certain
        we are that this action will improve the situation.
        
        High confidence factors:
        - Large workload imbalance being corrected
        - Good availability data (objective)
        - Clear improvement in multiple dimensions
        """
        base_confidence = 65.0  # Start lower for more realistic scores
        
        # Factor 1: Workload improvement (most objective)
        if current:
            util_diff = current['utilization'] - recommended['utilization']
            if util_diff > 40:  # Major imbalance
                base_confidence += 12
            elif util_diff > 20:  # Significant imbalance
                base_confidence += 8
            elif util_diff > 10:  # Moderate imbalance
                base_confidence += 4
            elif util_diff < -10:  # Would make things worse
                base_confidence -= 5
        else:
            # First assignment - moderate confidence
            base_confidence += 3
        
        # Factor 2: Availability difference (objective data)
        if current:
            avail_diff = recommended['availability'] - current['availability']
            if avail_diff > 30:
                base_confidence += 6
            elif avail_diff > 15:
                base_confidence += 4
            elif avail_diff < -15:  # Recommended person is MORE loaded
                base_confidence -= 3
        
        # Factor 3: Skill match of recommended person
        # Higher match = higher confidence, but not linear
        if recommended['skill_match'] > 70:
            base_confidence += 5
        elif recommended['skill_match'] > 50:
            base_confidence += 3
        elif recommended['skill_match'] < 30:
            base_confidence -= 2  # Low skill match reduces confidence
        
        # Factor 4: Overall suitability score difference
        if current:
            score_diff = recommended['overall_score'] - current['overall_score']
            if score_diff > 20:
                base_confidence += 5
            elif score_diff > 10:
                base_confidence += 3
            elif score_diff < 5:  # Marginal improvement
                base_confidence -= 3
        else:
            # For unassigned, use absolute score
            if recommended['overall_score'] > 75:
                base_confidence += 4
            elif recommended['overall_score'] > 60:
                base_confidence += 2
            elif recommended['overall_score'] < 45:
                base_confidence -= 2
        
        # Factor 5: Workload impact type
        if workload_impact == 'reduces_bottleneck':
            base_confidence += 5
        elif workload_impact == 'balances_load':
            base_confidence += 3
        
        # Factor 6: Recommended person's current workload (availability is objective)
        # But being completely free isn't always a positive signal
        if recommended['current_workload'] == 0:
            base_confidence += 3  # Available, but moderate confidence
        elif 1 <= recommended['current_workload'] <= 3:
            base_confidence += 4  # Ideal workload range
        elif recommended['current_workload'] > 8:
            base_confidence -= 4  # Already overloaded
        
        # Add slight randomness for variety (±2 points)
        import random
        random.seed(recommended['user_id'] + (current['user_id'] if current else 0))  # Deterministic per user pair
        variance = random.uniform(-2, 2)
        base_confidence += variance
        
        # Cap at 92 (never claim extreme certainty) and floor at 45
        return max(45.0, min(round(base_confidence, 1), 92.0))
    
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
        
        # Track suggested assignments to prevent overloading one person
        # Key: user_id, Value: number of tasks suggested to be assigned
        suggested_task_counts = {}
        
        for task in tasks:
            # Always create fresh suggestion with current workload data
            suggestion = self.create_suggestion(
                task, 
                requesting_user=requesting_user,
                temp_workload_adjustments=suggested_task_counts
            )
            if suggestion:
                suggestions.append(suggestion)
                # Track this suggestion to adjust workload for subsequent evaluations
                suggested_user_id = suggestion.suggested_assignee.id
                suggested_task_counts[suggested_user_id] = suggested_task_counts.get(suggested_user_id, 0) + 1
        
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
        members = board.members.all()
        
        report = {
            'board': board.name,
            'team_size': members.count(),
            'members': [],
            'bottlenecks': [],
            'underutilized': []
        }
        
        for member in members:
            profile = self.get_or_create_profile(member)
            
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
        members = board.members.all()
        updated = 0
        
        for member in members:
            try:
                profile = self.get_or_create_profile(member)
                profile.update_metrics()
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
    
    def __init__(self, organization):
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
        members = board.members.all()
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
