"""
Management command: populate_discovery_demo_data

Seeds PrizmDiscovery with 8 realistic demo ideas for the Acme Corporation demo
organisation, following the Asia-market expansion story used elsewhere in the
demo data.

Idempotent by reset: deletes all existing demo ideas first, then recreates
them fresh. This ensures stages and scores are always restored to seed state
(e.g. after a user approves / scores an idea during a demo session).
"""
from datetime import timedelta

from django.core.management.base import BaseCommand
from django.utils import timezone

from accounts.demo_personas import DEMO_PERSONAS


class Command(BaseCommand):
    help = 'Seed PrizmDiscovery demo ideas for the Acme Corporation demo organisation.'

    def handle(self, *args, **options):
        from django.contrib.auth import get_user_model
        from accounts.models import Organization
        from kanban.models import Board
        from kanban.discovery_models import DiscoveryIdea, IdeaComment, IdeaPromotion

        User = get_user_model()

        # ── Locate demo org ────────────────────────────────────────────
        demo_org = Organization.objects.filter(is_demo=True).first()
        if not demo_org:
            self.stderr.write(self.style.ERROR('No demo organisation found. Run create_demo_organization first.'))
            return

        # Always reset: delete all existing demo ideas and recreate them fresh.
        # This ensures stages and AI scores are restored to seed state even if
        # a demo user approved, scored, or promoted an idea before resetting.
        existing = DiscoveryIdea.objects.filter(organization=demo_org, is_demo=True)
        if existing.exists():
            # Clear M2M and cascade-related records before bulk delete
            for idea in existing:
                try:
                    if hasattr(idea, 'promotion'):
                        # Delete the delivery tasks this idea seeded (not just the
                        # M2M link) so reruns don't accumulate duplicate tickets.
                        idea.promotion.tasks.all().delete()
                        idea.promotion.delete()
                except Exception:
                    pass
            IdeaComment.objects.filter(idea__in=existing).delete()
            existing.delete()
            self.stdout.write(self.style.NOTICE('Discovery demo ideas cleared - recreating fresh.'))

        # ── Demo users ─────────────────────────────────────────────────
        alex = User.objects.filter(username=DEMO_PERSONAS['lead']['username']).first()
        sam = User.objects.filter(username=DEMO_PERSONAS['frontend']['username']).first()
        jordan = User.objects.filter(username=DEMO_PERSONAS['devops']['username']).first()

        if not (alex and sam and jordan):
            self.stderr.write(self.style.ERROR(
                f'Demo users not found ({", ".join(p["username"] for p in DEMO_PERSONAS.values())}). '
                'Run create_demo_organization first.'
            ))
            return

        # ── Demo board for promotions ──────────────────────────────────
        # Try to find a software/engineering-flavoured board to link promoted ideas to.
        software_board = (
            Board.objects.filter(organization=demo_org, is_official_demo_board=True)
            .order_by('id')
            .first()
        )

        now = timezone.now()

        # ── Staggered timeline ─────────────────────────────────────────
        # created_at uses auto_now_add, so it can't be set on create() - all
        # ideas would otherwise share the seeder's run time. We assign each
        # idea a distinct backdated submission time and write created_at via a
        # queryset .update() at the end (which bypasses auto_now_add).
        # Older = further along the funnel (approved/rejected); newest = "new".
        t_idea1 = now - timedelta(days=14, hours=3)   # Mobile App (approved + promoted)
        t_idea7 = now - timedelta(days=11, hours=6)   # Regional Pricing (approved + promoted)
        t_idea6 = now - timedelta(days=8, hours=2)    # Gamification (rejected)
        t_idea3 = now - timedelta(days=5, hours=7)    # Payment Gateways (under_review)
        t_idea2 = now - timedelta(days=4, hours=1)    # AI Localisation (under_review)
        t_idea4 = now - timedelta(days=2, hours=4)    # Offline Mode (new)
        t_idea5 = now - timedelta(days=1, hours=5)    # Dashboard Export (new)
        t_idea8 = now - timedelta(hours=3)            # Update FAQ (new)

        # ── Idea 1: Mobile App for Asian Markets (under_review, scored) ─
        # The parent strategic bet. Deliberately kept Under Review (not yet
        # approved) because its mandatory pillars - Offline Mode, Payment
        # Gateway partnerships, and the Localisation engine - are still being
        # evaluated in parallel. Approving the parent before its dependencies
        # are scored would be a logical disconnect, so the demo shows the team
        # holding it under review until those prerequisites clear.
        idea1 = DiscoveryIdea.objects.create(
            organization=demo_org,
            title='Mobile App for Asian Markets',
            description=(
                'Build a mobile-first application optimised for users in South-East Asia, '
                'Japan, and South Korea. Must support local languages, offline mode, and '
                'integrate with regional payment gateways (Alipay, GrabPay, PayPay).'
            ),
            source='customer_research',
            stage='under_review',
            submitted_by=jordan,
            ai_score_impact=87,
            ai_score_effort=72,
            ai_score_confidence=81,
            ai_score_recommendation='Prioritise - high strategic value, but resolve its dependencies first.',
            ai_score_reasoning=(
                'Strong market opportunity in APAC, validated by customer interviews. '
                'Effort is moderate due to localisation complexity but offset by large '
                'addressable user base and competitive differentiation. Note: this is a '
                'parent initiative - Offline Mode, payment gateway partnerships, and the '
                'localisation engine are hard prerequisites that should be scored and '
                'approved before this is greenlit.'
            ),
            ai_scored_at=t_idea1 + timedelta(days=1),
            is_demo=True,
        )

        # Comment thread - decision journey
        c1 = IdeaComment.objects.create(
            idea=idea1,
            author=jordan,
            content=(
                'Customer interviews with 12 enterprise clients in APAC all mentioned '
                'mobile experience as a top pain point. I think we should fast-track this.'
            ),
        )
        c2 = IdeaComment.objects.create(
            idea=idea1,
            author=sam,
            content=(
                'Agreed - I ran a quick feasibility check and our React Native team '
                'can deliver an MVP in Q3. Biggest risk is payment gateway certification '
                'timelines (Alipay takes 8-12 weeks).'
            ),
        )
        c3 = IdeaComment.objects.create(
            idea=idea1,
            author=alex,
            content=(
                'Finance can ring-fence £180k for this, but I don\'t want to approve the '
                'parent until its pillars are scored. Offline Mode, the payment gateway '
                'partnerships, and the localisation engine are all hard requirements - '
                'not nice-to-haves.'
            ),
        )
        c4 = IdeaComment.objects.create(
            idea=idea1,
            author=alex,
            content=(
                'Keeping this Under Review and pursuing the three dependencies in parallel. '
                'Once they\'re assessed we approve the whole APAC initiative together and '
                'promote it to a delivery board.'
            ),
        )

        # ── Idea 2: AI-Powered Language Localisation (under_review, scored) ──
        idea2 = DiscoveryIdea.objects.create(
            organization=demo_org,
            title='AI-Powered Language Localisation Engine',
            description=(
                'Replace manual translation workflow with an LLM-powered pipeline that '
                'auto-translates UI strings, documentation, and in-app help content into '
                'Mandarin, Japanese, Korean, and Thai. Requires human review gates.'
            ),
            source='internal_team',
            stage='under_review',
            submitted_by=sam,
            ai_score_impact=78,
            ai_score_effort=65,
            ai_score_confidence=72,
            ai_score_recommendation='Strong bet - aligns with APAC expansion and reduces localisation cost by est. 60%.',
            ai_score_reasoning=(
                'High leverage relative to effort - LLM translation is now mature enough '
                'for production use with human review. Main risk is regulatory sensitivity '
                'in some target markets.'
            ),
            ai_scored_at=t_idea2 + timedelta(hours=20),
            is_demo=True,
        )

        # ── Idea 3: Partnerships with Local Payment Gateways (under_review, scored) ──
        idea3 = DiscoveryIdea.objects.create(
            organization=demo_org,
            title='Partnerships with Regional Payment Gateways',
            description=(
                'Formal partnership agreements and technical integrations with Alipay, '
                'GrabPay, PayPay, and PromptPay. Essential for monetisation in target markets.'
            ),
            source='market_analysis',
            stage='under_review',
            submitted_by=jordan,
            ai_score_impact=83,
            ai_score_effort=58,
            ai_score_confidence=76,
            ai_score_recommendation='Pursue in parallel with mobile app - a dependency, not optional.',
            ai_score_reasoning=(
                'Without payment localisation, conversion rates in APAC will remain low. '
                'Legal and compliance work is the main bottleneck; technical integration '
                'is well-documented for all target gateways.'
            ),
            ai_scored_at=t_idea3 + timedelta(hours=18),
            is_demo=True,
        )

        # ── Idea 4: Offline Mode (new, unscored) ──────────────────────
        idea4 = DiscoveryIdea.objects.create(
            organization=demo_org,
            title='Offline Mode for Low-Connectivity Regions',
            description=(
                'Allow key app workflows to function without an active internet connection. '
                'Essential for rural Indonesia, Vietnam, and parts of India where 4G is '
                'patchy. Data syncs when connectivity is restored.'
            ),
            source='customer_research',
            stage='new',
            submitted_by=sam,
            is_demo=True,
        )

        # ── Idea 5: Competitor Feature Parity - Dashboard Export (new, unscored) ──
        idea5 = DiscoveryIdea.objects.create(
            organization=demo_org,
            title='Dashboard Export to PowerPoint / PDF',
            description=(
                'Several APAC enterprise prospects have asked for the ability to export '
                'dashboard views as polished slide decks for executive reporting. '
                'Competitors Asana and Monday.com already offer this.'
            ),
            source='competitor_analysis',
            stage='new',
            submitted_by=alex,
            is_demo=True,
        )

        # ── Idea 6: Gamification / Loyalty Programme (rejected) ───────
        idea6 = DiscoveryIdea.objects.create(
            organization=demo_org,
            title='Gamification & Loyalty Programme',
            description=(
                'Add points, badges, and leaderboards to incentivise daily active usage. '
                'Users earn rewards for completing tasks, maintaining streaks, and '
                'collaborating with teammates.'
            ),
            source='internal_team',
            stage='rejected',
            submitted_by=jordan,
            ai_score_impact=34,
            ai_score_effort=62,
            ai_score_confidence=68,
            ai_score_recommendation='Deprioritise - low impact relative to effort for our B2B segment.',
            ai_score_reasoning=(
                'Gamification is a B2C pattern. Our enterprise buyers prioritise ROI '
                'and workflow efficiency, not engagement loops. Complexity cost is high '
                'for marginal adoption benefit.'
            ),
            ai_scored_at=t_idea6 + timedelta(hours=20),
            is_demo=True,
        )
        c6 = IdeaComment.objects.create(
            idea=idea6,
            author=alex,
            content=(
                'Rejecting this for now. We spoke to 5 enterprise buyers - none of them '
                'cited engagement as a pain point. Not the right fit for our current ICP.'
            ),
        )

        # ── Idea 7: Regional Pricing Tiers (approved + promoted) ──────
        idea7 = DiscoveryIdea.objects.create(
            organization=demo_org,
            title='Regional Pricing Tiers for APAC',
            description=(
                'Introduce market-specific pricing plans for South-East Asia and Japan. '
                'USD-denominated pricing is a significant barrier. Local currency pricing '
                'with local payment methods will improve conversion.'
            ),
            source='sales_feedback',
            stage='approved',
            submitted_by=alex,
            ai_score_impact=74,
            ai_score_effort=40,
            ai_score_confidence=79,
            ai_score_recommendation='Quick Win - high impact with relatively low implementation effort.',
            ai_score_reasoning=(
                'Pricing localisation is a well-understood process and primarily a commercial '
                'and billing-system change rather than a deep technical investment. '
                'Expected 15-25% conversion uplift in target markets based on comparable data.'
            ),
            ai_scored_at=t_idea7 + timedelta(days=1),
            promoted_at=t_idea7 + timedelta(days=2),
            promoted_by=alex,
            is_demo=True,
        )
        promotion7 = IdeaPromotion.objects.create(
            idea=idea7,
            board=software_board,
            promoted_at=t_idea7 + timedelta(days=2),
            promoted_by=alex,
        )

        # Seed a real delivery task for the promoted idea so the detail page
        # shows what a generated feature ticket looks like (instead of the
        # "No task created yet" stub). Mirrors kanban.discovery_views.idea_promote.
        if software_board:
            import re
            from kanban.models import Column, Task
            _intake_names = re.compile(r'\b(to.?do|backlog|inbox|todo|open|new|ideas?|ready)\b', re.I)
            all_cols = list(Column.objects.filter(board=software_board).order_by('position'))
            first_col = next((c for c in all_cols if _intake_names.search(c.name)), None) or (all_cols[0] if all_cols else None)
            if first_col:
                pricing_task = Task.objects.create(
                    title=idea7.title,
                    description=f'Promoted from PrizmDiscovery.\n\n{idea7.description}',
                    column=first_col,
                    created_by=alex,
                    position=Task.objects.filter(column=first_col).count(),
                )
                promotion7.tasks.add(pricing_task)
                # Backdate so the ticket isn't stamped with the seeder run time.
                Task.objects.filter(pk=pricing_task.pk).update(
                    created_at=t_idea7 + timedelta(days=2),
                )

        # ── Idea 8: Update FAQ & Help Centre copy (new, unscored) ───────
        # Intentionally left unscored so demo users can experience clicking
        # "Score with Spectra" themselves and see the AI analysis in action.
        idea8 = DiscoveryIdea.objects.create(
            organization=demo_org,
            title='Update FAQ & Help Centre Copy',
            description=(
                'Refresh the FAQ page and in-app help tooltips with accurate '
                'content covering new APAC features, local payment methods, '
                'and updated onboarding steps. '
                'Current content is 18 months out of date.'
            ),
            source='internal_team',
            stage='new',
            submitted_by=jordan,
            is_demo=True,
        )

        # ── Backdate created_at (bypasses auto_now_add via queryset.update) ──
        for idea, created in (
            (idea1, t_idea1),
            (idea2, t_idea2),
            (idea3, t_idea3),
            (idea4, t_idea4),
            (idea5, t_idea5),
            (idea6, t_idea6),
            (idea7, t_idea7),
            (idea8, t_idea8),
        ):
            DiscoveryIdea.objects.filter(pk=idea.pk).update(created_at=created)

        # Backdate comment timestamps so the decision journey reads in order
        # (IdeaComment.created_at is also auto_now_add).
        for comment, created in (
            (c1, t_idea1 + timedelta(hours=2)),
            (c2, t_idea1 + timedelta(hours=6)),
            (c3, t_idea1 + timedelta(days=1, hours=2)),
            (c4, t_idea1 + timedelta(days=2)),
            (c6, t_idea6 + timedelta(days=1)),
        ):
            IdeaComment.objects.filter(pk=comment.pk).update(created_at=created)

        count = DiscoveryIdea.objects.filter(organization=demo_org, is_demo=True).count()
        self.stdout.write(self.style.SUCCESS(
            f'Created {count} Discovery demo ideas for "{demo_org.name}".'
        ))
