"""
Commitment Service — Core Business Logic for Living Commitment Protocols

All confidence calculations, signal processing, negotiation session generation,
and market consensus computations live here.
"""
import json
import math
import logging
from datetime import date, timedelta

from django.core.cache import cache
from django.utils import timezone

logger = logging.getLogger(__name__)


class CommitmentService:
    """
    Stateless service for managing Living Commitment Protocol logic.
    All methods can be called as class methods — no instance state needed.
    """

    # -------------------------------------------------------------------------
    # 1. Confidence Decay
    # -------------------------------------------------------------------------

    @staticmethod
    def calculate_decay(protocol) -> float:
        """
        Calculate the decayed confidence value given the time elapsed since
        the last positive signal. Does NOT save to database.

        Returns a float 0.05–current_confidence (decay can never increase confidence).
        """
        from django.utils.timezone import now as tz_now

        if protocol.last_signal_date:
            ref_date = protocol.last_signal_date
        else:
            ref_date = protocol.created_at

        days_elapsed = max(0, (tz_now() - ref_date).total_seconds() / 86400)

        current = protocol.current_confidence

        if protocol.decay_model == 'exponential':
            lambda_val = math.log(2) / max(1, protocol.confidence_halflife_days)
            decayed = current * math.exp(-lambda_val * days_elapsed)
        elif protocol.decay_model == 'linear':
            daily_decay = current / (max(1, protocol.confidence_halflife_days) * 2)
            decayed = current - (daily_decay * days_elapsed)
        else:
            # Stepped: drop by 10% for each half-life period elapsed
            periods = days_elapsed / max(1, protocol.confidence_halflife_days)
            decayed = current * (0.9 ** int(periods))

        # Never increase via decay; floor at 5%
        return max(0.05, min(decayed, current))

    # -------------------------------------------------------------------------
    # 2. Signal Application
    # -------------------------------------------------------------------------

    @staticmethod
    def apply_signal(
        protocol,
        signal_type: str,
        signal_value: float,
        description: str,
        user=None,
        task=None,
        ai_generated: bool = False,
    ):
        """
        Apply a confidence signal to the protocol, create a ConfidenceSignal
        record, update protocol status, and check negotiation threshold.

        Returns the created ConfidenceSignal.
        """
        from kanban.commitment_models import ConfidenceSignal

        confidence_before = protocol.current_confidence

        # Additive update formula from the plan doc:
        # Positive: new = before + (1 - before) * value * 0.5
        # Negative: new = before + before * value * 0.5  (value is negative)
        if signal_value > 0:
            new_confidence = confidence_before + (1 - confidence_before) * signal_value * 0.5
        else:
            new_confidence = confidence_before + confidence_before * signal_value * 0.5

        new_confidence = max(0.05, min(0.99, new_confidence))

        # Create signal record
        signal = ConfidenceSignal.objects.create(
            protocol=protocol,
            signal_type=signal_type,
            signal_value=signal_value,
            description=description,
            confidence_before=confidence_before,
            confidence_after=new_confidence,
            ai_generated=ai_generated,
            recorded_by=user,
            related_task=task,
        )

        # Update protocol
        protocol.current_confidence = new_confidence
        if signal_value > 0:
            protocol.last_signal_date = timezone.now()

        # Update status
        if new_confidence >= 0.70:
            protocol.status = 'active'
        elif new_confidence >= 0.40:
            protocol.status = 'at_risk'
        else:
            protocol.status = 'critical'

        protocol.last_decay_calculation = timezone.now()
        protocol.save(update_fields=[
            'current_confidence', 'last_signal_date',
            'last_decay_calculation', 'status',
        ])

        # Invalidate market cache
        cache.delete(f'commitment_market_{protocol.pk}')

        # Check if negotiation should be triggered
        if signal_value < 0:
            CommitmentService.check_negotiation_threshold(protocol)

        return signal

    # -------------------------------------------------------------------------
    # 3. Negotiation Threshold Check
    # -------------------------------------------------------------------------

    @staticmethod
    def check_negotiation_threshold(protocol):
        """
        If confidence is below the negotiation threshold and no active
        NegotiationSession exists, initiate one.

        Idempotent — will never create duplicates.
        """
        from kanban.commitment_models import NegotiationSession

        if protocol.current_confidence >= protocol.negotiation_threshold:
            return None

        # Check for an already-active session
        active_exists = NegotiationSession.objects.filter(
            protocol=protocol,
            status__in=['draft', 'sent', 'acknowledged'],
        ).exists()

        if active_exists:
            logger.debug(
                'Skipping negotiation for protocol %s — active session exists', protocol.pk
            )
            return None

        return CommitmentService.generate_negotiation_session(protocol)

    # -------------------------------------------------------------------------
    # 4. Negotiation Session Generation
    # -------------------------------------------------------------------------

    @staticmethod
    def generate_negotiation_session(protocol):
        """
        Generate a full negotiation package using Gemini and create a
        NegotiationSession record.
        """
        from kanban.commitment_models import NegotiationSession
        from kanban.commitment_prompts import NEGOTIATION_BOT_PROMPT

        # Gather board health context
        context = CommitmentService._build_negotiation_context(protocol)

        # Build prompt
        prompt = NEGOTIATION_BOT_PROMPT.format(**context)

        # Call Gemini
        ai_result = CommitmentService._call_gemini_for_negotiation(prompt)

        # Create NegotiationSession
        session = NegotiationSession.objects.create(
            protocol=protocol,
            trigger_confidence=protocol.current_confidence,
            trigger_reason=context.get('trigger_reason', 'Confidence dropped below threshold'),
            ai_drafted_message=ai_result.get('stakeholder_message', ''),
            option_a_description=ai_result.get('option_a', {}).get('description', ''),
            option_a_impact=ai_result.get('option_a', {}),
            option_b_description=ai_result.get('option_b', {}).get('description', ''),
            option_b_impact=ai_result.get('option_b', {}),
            option_c_description=ai_result.get('option_c', {}).get('description', ''),
            option_c_impact=ai_result.get('option_c', {}),
            status='draft',
            initiated_by_ai=True,
        )

        logger.info(
            'NegotiationSession %s created for protocol %s at confidence %.0f%%',
            session.pk, protocol.pk, protocol.current_confidence * 100,
        )

        # Log to Knowledge Graph
        try:
            CommitmentService._log_kg_event(
                protocol=protocol,
                event_type='negotiation_initiated',
                title=f'Negotiation triggered for "{protocol.title}"',
                content=(
                    f'Confidence dropped to {protocol.current_confidence:.0%}, '
                    f'below threshold {protocol.negotiation_threshold:.0%}. '
                    f'AI drafted renegotiation package.'
                ),
            )
        except Exception:
            logger.warning('KG log failed for negotiation initiation', exc_info=True)

        return session

    # -------------------------------------------------------------------------
    # 5. Market Consensus
    # -------------------------------------------------------------------------

    @staticmethod
    def calculate_market_consensus(protocol) -> dict:
        """
        Calculate credibility-weighted consensus from all active bets.
        Cached for 5 minutes.
        Returns dict: {consensus, divergence, bet_count, distribution, ...}
        """
        from kanban.commitment_models import UserCredibilityScore

        cache_key = f'commitment_market_{protocol.pk}'
        cached = cache.get(cache_key)
        if cached is not None:
            return cached

        bets = protocol.bets.filter(resolved=False).select_related('bettor')

        if not bets.exists():
            return {
                'consensus': None,
                'divergence': 0,
                'bet_count': 0,
                'distribution': [],
                'anomaly': False,
                'show_market': False,
                'total_tokens': 0,
            }

        weighted_sum = 0.0
        total_weight = 0.0
        distribution_buckets = [0] * 10  # 0-9%, 10-19%, ..., 90-99%

        for bet in bets:
            try:
                credibility = bet.bettor.betting_credibility.score
            except UserCredibilityScore.DoesNotExist:
                credibility = 50.0
            weight = credibility / 100.0
            weighted_sum += bet.confidence_estimate * weight
            total_weight += weight
            bucket = min(9, int(bet.confidence_estimate * 10))
            distribution_buckets[bucket] += 1

        consensus = weighted_sum / total_weight if total_weight > 0 else None
        bet_count = bets.count()
        divergence = abs(protocol.current_confidence - consensus) if consensus else 0
        anomaly = divergence > 0.20 and bet_count >= 3

        result = {
            'consensus': round(consensus * 100, 1) if consensus is not None else None,
            'divergence': round(divergence * 100, 1),
            'bet_count': bet_count,
            'distribution': distribution_buckets,
            'anomaly': anomaly,
            'show_market': bet_count >= 3,
            'total_tokens': sum(b.tokens_wagered for b in bets),
        }

        cache.set(cache_key, result, 300)
        return result

    # -------------------------------------------------------------------------
    # 6. Auto Signal Detection
    # -------------------------------------------------------------------------

    @staticmethod
    def detect_auto_signals(board):
        """
        Scan board activity and apply confidence signals to all active
        CommitmentProtocols for the board.

        Returns list of created ConfidenceSignal objects.
        """
        from kanban.commitment_models import CommitmentProtocol
        from kanban.models import Task

        protocols = CommitmentProtocol.objects.filter(
            board=board,
            status__in=['active', 'at_risk', 'critical'],
        )

        created_signals = []

        for protocol in protocols:
            ref_date = protocol.last_signal_date or protocol.created_at

            # Check tasks completed since last signal date
            completed_tasks = Task.objects.filter(
                column__board=board,
                progress=100,
                updated_at__gte=ref_date,
            ).exclude(
                commitment_signals__protocol=protocol,
                commitment_signals__signal_type='task_completed',
            )

            for task in completed_tasks[:10]:  # Cap at 10 per run
                sig = CommitmentService.apply_signal(
                    protocol=protocol,
                    signal_type='task_completed',
                    signal_value=0.10,
                    description=f'Task "{task.title}" completed.',
                    task=task,
                    ai_generated=True,
                )
                created_signals.append(sig)

            # Check for new tasks added since baseline (scope creep)
            baseline_task_count = protocol.baseline_snapshot.get('task_count', 0)
            current_task_count = Task.objects.filter(
                column__board=board, item_type='task'
            ).count()

            if baseline_task_count > 0:
                scope_growth = (current_task_count - baseline_task_count) / baseline_task_count
                last_recorded_growth = protocol.baseline_snapshot.get('_last_recorded_growth', 0)

                if scope_growth > last_recorded_growth + 0.05:  # >5% new growth since last check
                    delta = scope_growth - last_recorded_growth
                    sig = CommitmentService.apply_signal(
                        protocol=protocol,
                        signal_type='task_added',
                        signal_value=-min(0.3, delta),
                        description=(
                            f'Scope grew by {delta:.0%} since last check '
                            f'({current_task_count} vs {baseline_task_count} baseline tasks).'
                        ),
                        ai_generated=True,
                    )
                    created_signals.append(sig)
                    # Update tracked growth in snapshot
                    snapshot = protocol.baseline_snapshot.copy()
                    snapshot['_last_recorded_growth'] = scope_growth
                    protocol.baseline_snapshot = snapshot
                    protocol.save(update_fields=['baseline_snapshot'])

        return created_signals

    # -------------------------------------------------------------------------
    # 7. Confidence Curve Data (for charting)
    # -------------------------------------------------------------------------

    @staticmethod
    def get_confidence_curve_data(protocol) -> list:
        """
        Build {date, confidence, signal_type, description, projected} data for Chart.js.
        Includes historical signal points + projected decay until target_date.
        """
        from django.utils.timezone import now as tz_now
        import copy

        data = []

        # Historical: the starting point
        data.append({
            'date': protocol.created_at.date().isoformat(),
            'confidence': protocol.initial_confidence,
            'signal_type': 'start',
            'description': 'Commitment created',
            'projected': False,
        })

        # All signals in order
        for sig in protocol.signals.order_by('timestamp'):
            data.append({
                'date': sig.timestamp.date().isoformat(),
                'confidence': sig.confidence_after,
                'signal_type': sig.signal_type,
                'description': sig.description,
                'projected': False,
            })

        # Forward projection: simulate decay from today to target_date
        today = date.today()
        target = protocol.target_date
        remaining_days = (target - today).days

        if remaining_days > 0:
            # Create a temporary protocol-like object for simulation
            class _Sim:
                current_confidence = protocol.current_confidence
                last_signal_date = tz_now()
                created_at = tz_now()
                confidence_halflife_days = protocol.confidence_halflife_days
                decay_model = protocol.decay_model

            sim = _Sim()

            step = max(1, remaining_days // 10)
            for offset in range(step, remaining_days + 1, step):
                sim.last_signal_date = tz_now() - timedelta(days=offset - step)
                sim.created_at = sim.last_signal_date

                projected_conf = CommitmentService.calculate_decay(sim)
                projected_date = (today + timedelta(days=offset)).isoformat()

                data.append({
                    'date': projected_date,
                    'confidence': projected_conf,
                    'signal_type': 'projected',
                    'description': 'Projected decay (no new signals)',
                    'projected': True,
                })
                sim.current_confidence = projected_conf

        return data

    # -------------------------------------------------------------------------
    # 8. AI Reasoning Generation (called from Celery task)
    # -------------------------------------------------------------------------

    @staticmethod
    def generate_ai_reasoning(protocol_id: int):
        """
        Generate plain-English AI explanation for current confidence level.
        Updates protocol.ai_reasoning in-place.
        """
        from kanban.commitment_models import CommitmentProtocol
        from kanban.commitment_prompts import DECAY_EXPLANATION_PROMPT

        try:
            protocol = CommitmentProtocol.objects.get(pk=protocol_id)
        except CommitmentProtocol.DoesNotExist:
            return

        today = date.today()
        days_remaining = (protocol.target_date - today).days
        initial_pct = round(protocol.initial_confidence * 100)
        current_pct = round(protocol.current_confidence * 100)
        change_pct = initial_pct - current_pct
        direction = 'decrease' if change_pct >= 0 else 'increase'

        days_since_signal = 0
        if protocol.last_signal_date:
            days_since_signal = (timezone.now() - protocol.last_signal_date).days

        recent_signals = protocol.signals.order_by('-timestamp')[:5]
        signals_summary = '; '.join(
            f'{s.get_signal_type_display()}: {s.description[:80]}'
            for s in recent_signals
        ) or 'No recent signals'

        prompt = DECAY_EXPLANATION_PROMPT.format(
            title=protocol.title,
            target_date=str(protocol.target_date),
            days_remaining=days_remaining,
            initial_confidence_pct=initial_pct,
            current_confidence_pct=current_pct,
            confidence_change_pct=abs(change_pct),
            direction=direction,
            days_since_signal=days_since_signal,
            halflife=protocol.confidence_halflife_days,
            signals_summary=signals_summary,
        )

        ai_text = CommitmentService._call_gemini_simple(prompt)
        if ai_text:
            try:
                parsed = json.loads(ai_text)
                reasoning = parsed.get('explanation', ai_text)
            except (json.JSONDecodeError, ValueError):
                reasoning = ai_text

            CommitmentProtocol.objects.filter(pk=protocol_id).update(ai_reasoning=reasoning)

    # -------------------------------------------------------------------------
    # Private helpers
    # -------------------------------------------------------------------------

    @staticmethod
    def _build_negotiation_context(protocol) -> dict:
        """Gather board health metrics for the negotiation prompt."""
        from kanban.models import Task
        from django.utils.timezone import now as tz_now

        board = protocol.board
        today = date.today()

        all_tasks = Task.objects.filter(column__board=board, item_type='task')
        total = all_tasks.count()
        completed = all_tasks.filter(progress=100).count()
        remaining = total - completed

        # Basic velocity: tasks completed in last 14 days
        two_weeks_ago = tz_now() - timedelta(days=14)
        recent_completed = all_tasks.filter(
            progress=100,
            updated_at__gte=two_weeks_ago,
        ).count()
        velocity = round(recent_completed / 2, 1)  # per week

        weeks_remaining = max(0, (protocol.target_date - today).days / 7)

        # Budget
        try:
            from kanban.budget_models import ProjectBudget
            budget = ProjectBudget.objects.get(board=board)
            budget_pct = round(budget.get_budget_utilization_percent(), 1)
        except Exception:
            budget_pct = 0

        # Recent signals as risk summary
        recent_negative = protocol.signals.filter(
            signal_value__lt=0,
        ).order_by('-timestamp')[:3]
        risks_summary = '; '.join(s.description[:80] for s in recent_negative) or 'None identified'

        # Stakeholders
        stakeholders_list = '\n'.join(
            f'- {s.get_full_name() or s.username}'
            for s in protocol.stakeholders.all()
        ) or '- (No stakeholders assigned)'

        # Trigger reason (most recent negative signal)
        last_negative = protocol.signals.filter(signal_value__lt=0).order_by('-timestamp').first()
        trigger_reason = (
            last_negative.description if last_negative
            else f'Confidence dropped to {protocol.current_confidence:.0%}'
        )

        return {
            'board_name': board.name,
            'commitment_title': protocol.title,
            'target_date': str(protocol.target_date),
            'current_confidence_pct': round(protocol.current_confidence * 100),
            'threshold_pct': round(protocol.negotiation_threshold * 100),
            'trigger_reason': trigger_reason,
            'tasks_remaining': remaining,
            'velocity': velocity,
            'weeks_remaining': round(weeks_remaining, 1),
            'budget_pct': budget_pct,
            'risks_summary': risks_summary,
            'stakeholders_list': stakeholders_list,
        }

    @staticmethod
    def _call_gemini_for_negotiation(prompt: str) -> dict:
        """
        Call Gemini to get a negotiation package JSON.
        Falls back gracefully if the API is unavailable.
        """
        try:
            from ai_assistant.utils.ai_clients import GeminiClient
            client = GeminiClient()
            response = client.get_response(
                prompt=prompt,
                task_complexity='complex',
                temperature=0.4,
            )
            raw = response.strip()
            if '```json' in raw:
                raw = raw.split('```json')[1].split('```')[0].strip()
            elif raw.startswith('```'):
                raw = raw.split('\n', 1)[1] if '\n' in raw else raw[3:]
                if raw.endswith('```'):
                    raw = raw[:-3].strip()
            return json.loads(raw)
        except Exception as e:
            logger.error('Gemini negotiation call failed: %s', e, exc_info=True)
            return {
                'stakeholder_message': (
                    'We are reaching out regarding the project commitment. '
                    'The AI-drafted message could not be generated at this time. '
                    'Please review and draft a message manually.'
                ),
                'option_a': {
                    'title': 'Reduce Scope',
                    'description': 'Review and remove lower-priority tasks.',
                    'tasks_to_remove': 0,
                    'new_confidence': 0.75,
                    'tradeoffs': 'Less features, original deadline',
                    'recommended': False,
                },
                'option_b': {
                    'title': 'Extend Deadline',
                    'description': 'Move target date to allow full delivery.',
                    'new_target_date': '',
                    'new_confidence': 0.80,
                    'tradeoffs': 'Full scope, later delivery',
                    'recommended': True,
                },
                'option_c': {
                    'title': 'Add Resources',
                    'description': 'Add team members to accelerate delivery.',
                    'resources_needed': 'Additional developers',
                    'new_confidence': 0.70,
                    'tradeoffs': 'More people, original scope and deadline (Brooks Law risk)',
                    'recommended': False,
                },
                'ai_recommendation': 'AI recommendation unavailable. Please review options manually.',
            }

    @staticmethod
    def _call_gemini_simple(prompt: str) -> str:
        """Call Gemini for a simple text response. Returns raw text or empty string."""
        try:
            from ai_assistant.utils.ai_clients import GeminiClient
            client = GeminiClient()
            return client.get_response(
                prompt=prompt,
                task_complexity='complex',
                temperature=0.4,
            )
        except Exception as e:
            logger.error('Gemini simple call failed: %s', e, exc_info=True)
            return ''

    @staticmethod
    def _log_kg_event(protocol, event_type: str, title: str, content: str):
        """Log a commitment event to the Knowledge Graph."""
        try:
            from knowledge_graph.models import MemoryNode
            MemoryNode.objects.create(
                board=protocol.board,
                node_type='ai_recommendation',
                title=title,
                content=content,
                context_data={
                    'source': 'commitment_protocol',
                    'event_type': event_type,
                    'protocol_id': protocol.pk,
                    'protocol_title': protocol.title,
                    'confidence': protocol.current_confidence,
                },
                source_object_type='CommitmentProtocol',
                source_object_id=protocol.pk,
                is_auto_captured=True,
                importance_score=0.7,
                tags=['commitment', event_type],
            )
        except Exception as e:
            logger.warning('Failed to log KG event for commitment: %s', e)
