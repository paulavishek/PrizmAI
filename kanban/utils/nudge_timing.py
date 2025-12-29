"""
Conversion Nudge Timing Logic
Determines when and which nudges to show based on user behavior and session state
"""
from datetime import datetime, timedelta
from django.utils import timezone


class NudgeType:
    """Enum for nudge types"""
    SOFT = 'soft'  # Toast notification - low pressure
    MEDIUM = 'medium'  # Soft modal - value reinforcement
    PEAK = 'peak'  # Contextual inline - aha-triggered
    EXIT_INTENT = 'exit_intent'  # Prominent modal - last chance


class NudgeTiming:
    """
    Smart nudge timing based on user engagement and behavior
    
    Nudge Hierarchy:
    1. SOFT: 3 min OR 3 features explored (unobtrusive toast)
    2. MEDIUM: 5 min OR 1 aha moment (soft modal)
    3. PEAK: Triggered by aha moment (contextual)
    4. EXIT_INTENT: Mouse leaves screen + 2 min in demo (desktop only)
    
    Rules:
    - Maximum 3 nudges per session
    - Progressive escalation (soft → medium → peak/exit)
    - Respect dismissals (if dismissed, wait longer)
    - Context awareness (don't interrupt active tasks)
    """
    
    # Timing thresholds
    SOFT_MIN_TIME = 180  # 3 minutes in seconds
    SOFT_MIN_FEATURES = 3
    
    MEDIUM_MIN_TIME = 300  # 5 minutes
    MEDIUM_MIN_AHA = 1
    
    EXIT_MIN_TIME = 120  # 2 minutes
    
    # Frequency caps
    MAX_NUDGES_PER_SESSION = 3
    
    # Cooldown periods (seconds)
    SOFT_COOLDOWN = 120  # 2 minutes after soft dismissal
    MEDIUM_COOLDOWN = 180  # 3 minutes after medium dismissal
    
    @staticmethod
    def get_time_in_demo(session):
        """
        Calculate time user has spent in demo (in seconds)
        
        Args:
            session: Django request.session object
            
        Returns:
            int: Time in seconds
        """
        started_at = session.get('demo_started_at')
        if not started_at:
            return 0
        
        # Parse ISO format datetime
        try:
            started = datetime.fromisoformat(started_at)
            # Make timezone aware if needed
            if timezone.is_naive(started):
                started = timezone.make_aware(started)
            
            now = timezone.now()
            delta = now - started
            return int(delta.total_seconds())
        except (ValueError, TypeError):
            return 0
    
    @staticmethod
    def get_features_explored_count(session):
        """
        Get count of features explored
        
        Args:
            session: Django request.session object
            
        Returns:
            int: Number of unique features explored
        """
        features = session.get('features_explored', [])
        return len(features) if isinstance(features, list) else 0
    
    @staticmethod
    def get_aha_moments_count(session):
        """
        Get count of aha moments experienced
        
        Args:
            session: Django request.session object
            
        Returns:
            int: Number of aha moments
        """
        aha_moments = session.get('aha_moments', [])
        return len(aha_moments) if isinstance(aha_moments, list) else 0
    
    @staticmethod
    def get_nudges_shown(session):
        """
        Get list of nudges already shown
        
        Args:
            session: Django request.session object
            
        Returns:
            list: List of nudge types shown
        """
        nudges = session.get('nudges_shown', [])
        return nudges if isinstance(nudges, list) else []
    
    @staticmethod
    def get_nudges_dismissed(session):
        """
        Get dictionary of dismissed nudges with timestamps
        
        Args:
            session: Django request.session object
            
        Returns:
            dict: {nudge_type: dismissed_timestamp}
        """
        dismissed = session.get('nudges_dismissed', {})
        return dismissed if isinstance(dismissed, dict) else {}
    
    @staticmethod
    def is_in_cooldown(session, nudge_type):
        """
        Check if nudge type is in cooldown period after dismissal
        
        Args:
            session: Django request.session object
            nudge_type: Type of nudge to check
            
        Returns:
            bool: True if in cooldown, False otherwise
        """
        dismissed = NudgeTiming.get_nudges_dismissed(session)
        
        if nudge_type not in dismissed:
            return False
        
        dismissed_at = dismissed[nudge_type]
        
        try:
            dismissed_time = datetime.fromisoformat(dismissed_at)
            if timezone.is_naive(dismissed_time):
                dismissed_time = timezone.make_aware(dismissed_time)
            
            now = timezone.now()
            time_since_dismissal = (now - dismissed_time).total_seconds()
            
            # Check cooldown period
            if nudge_type == NudgeType.SOFT:
                return time_since_dismissal < NudgeTiming.SOFT_COOLDOWN
            elif nudge_type == NudgeType.MEDIUM:
                return time_since_dismissal < NudgeTiming.MEDIUM_COOLDOWN
            
            return False
        except (ValueError, TypeError):
            return False
    
    @staticmethod
    def should_show_soft_nudge(session):
        """
        Check if soft nudge should be shown
        
        Conditions:
        - 3 minutes in demo OR 3 features explored
        - Not already shown
        - Not in cooldown
        - Haven't hit frequency cap
        
        Args:
            session: Django request.session object
            
        Returns:
            bool: True if should show
        """
        # Check if already shown
        nudges_shown = NudgeTiming.get_nudges_shown(session)
        if NudgeType.SOFT in nudges_shown:
            return False
        
        # Check frequency cap
        if len(nudges_shown) >= NudgeTiming.MAX_NUDGES_PER_SESSION:
            return False
        
        # Check cooldown
        if NudgeTiming.is_in_cooldown(session, NudgeType.SOFT):
            return False
        
        # Check time or features threshold
        time_in_demo = NudgeTiming.get_time_in_demo(session)
        features_count = NudgeTiming.get_features_explored_count(session)
        
        return (time_in_demo >= NudgeTiming.SOFT_MIN_TIME or 
                features_count >= NudgeTiming.SOFT_MIN_FEATURES)
    
    @staticmethod
    def should_show_medium_nudge(session):
        """
        Check if medium nudge should be shown
        
        Conditions:
        - 5 minutes in demo OR 1 aha moment experienced
        - Not already shown
        - Not in cooldown
        - Haven't hit frequency cap
        
        Args:
            session: Django request.session object
            
        Returns:
            bool: True if should show
        """
        # Check if already shown
        nudges_shown = NudgeTiming.get_nudges_shown(session)
        if NudgeType.MEDIUM in nudges_shown:
            return False
        
        # Check frequency cap
        if len(nudges_shown) >= NudgeTiming.MAX_NUDGES_PER_SESSION:
            return False
        
        # Check cooldown
        if NudgeTiming.is_in_cooldown(session, NudgeType.MEDIUM):
            return False
        
        # Check time or aha threshold
        time_in_demo = NudgeTiming.get_time_in_demo(session)
        aha_count = NudgeTiming.get_aha_moments_count(session)
        
        return (time_in_demo >= NudgeTiming.MEDIUM_MIN_TIME or 
                aha_count >= NudgeTiming.MEDIUM_MIN_AHA)
    
    @staticmethod
    def should_show_peak_nudge(session, moment_type):
        """
        Check if peak nudge should be shown for a specific aha moment
        
        Conditions:
        - Aha moment just occurred
        - Not already shown for this moment type
        - Haven't hit frequency cap
        
        Args:
            session: Django request.session object
            moment_type: Type of aha moment that triggered
            
        Returns:
            bool: True if should show
        """
        # Check frequency cap
        nudges_shown = NudgeTiming.get_nudges_shown(session)
        if len(nudges_shown) >= NudgeTiming.MAX_NUDGES_PER_SESSION:
            return False
        
        # Check if peak nudge already shown for this moment
        peak_nudges = [n for n in nudges_shown if n.startswith('peak_')]
        peak_shown_for_moment = f'peak_{moment_type}' in peak_nudges
        
        return not peak_shown_for_moment
    
    @staticmethod
    def should_show_exit_intent_nudge(session):
        """
        Check if exit intent nudge should be shown
        
        Conditions:
        - User spent >2 minutes in demo
        - Not already shown
        - Haven't hit frequency cap
        - Desktop only (checked client-side)
        
        Args:
            session: Django request.session object
            
        Returns:
            bool: True if should show
        """
        # Check if already shown
        nudges_shown = NudgeTiming.get_nudges_shown(session)
        if NudgeType.EXIT_INTENT in nudges_shown:
            return False
        
        # Check frequency cap
        if len(nudges_shown) >= NudgeTiming.MAX_NUDGES_PER_SESSION:
            return False
        
        # Check minimum time threshold
        time_in_demo = NudgeTiming.get_time_in_demo(session)
        return time_in_demo >= NudgeTiming.EXIT_MIN_TIME
    
    @staticmethod
    def get_next_nudge(session):
        """
        Determine which nudge should be shown next
        
        Returns the highest priority nudge that meets its conditions.
        Priority order: Peak > Exit Intent > Medium > Soft
        
        Args:
            session: Django request.session object
            
        Returns:
            str or None: Nudge type to show, or None if no nudge should show
        """
        # Check soft nudge (lowest priority, check last)
        if NudgeTiming.should_show_soft_nudge(session):
            return NudgeType.SOFT
        
        # Check medium nudge
        if NudgeTiming.should_show_medium_nudge(session):
            return NudgeType.MEDIUM
        
        # Note: Peak and exit intent are event-driven, not returned here
        # Peak is triggered by aha moments
        # Exit intent is triggered client-side by mouse movement
        
        return None
    
    @staticmethod
    def mark_nudge_shown(session, nudge_type):
        """
        Mark that a nudge has been shown
        
        Args:
            session: Django request.session object
            nudge_type: Type of nudge shown
        """
        nudges_shown = NudgeTiming.get_nudges_shown(session)
        
        if nudge_type not in nudges_shown:
            nudges_shown.append(nudge_type)
            session['nudges_shown'] = nudges_shown
            session.modified = True
    
    @staticmethod
    def mark_nudge_dismissed(session, nudge_type):
        """
        Mark that a nudge has been dismissed
        
        Args:
            session: Django request.session object
            nudge_type: Type of nudge dismissed
        """
        dismissed = NudgeTiming.get_nudges_dismissed(session)
        dismissed[nudge_type] = timezone.now().isoformat()
        session['nudges_dismissed'] = dismissed
        session.modified = True
    
    @staticmethod
    def get_nudge_context(session):
        """
        Get context data for rendering nudges
        
        Args:
            session: Django request.session object
            
        Returns:
            dict: Context data including feature count, time, etc.
        """
        return {
            'time_in_demo': NudgeTiming.get_time_in_demo(session),
            'features_explored_count': NudgeTiming.get_features_explored_count(session),
            'aha_moments_count': NudgeTiming.get_aha_moments_count(session),
            'nudges_shown': NudgeTiming.get_nudges_shown(session),
            'nudges_dismissed': NudgeTiming.get_nudges_dismissed(session),
            'can_show_more': len(NudgeTiming.get_nudges_shown(session)) < NudgeTiming.MAX_NUDGES_PER_SESSION,
            'next_nudge': NudgeTiming.get_next_nudge(session),
        }
