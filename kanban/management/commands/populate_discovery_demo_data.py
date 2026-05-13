"""
Management command: populate_discovery_demo_data

Seeds PrizmDiscovery with 7 realistic demo ideas for the Acme Corporation demo
organisation, following the Asia-market expansion story used elsewhere in the
demo data.

Safe to run multiple times — idempotent (skips if demo ideas already exist).
"""
from django.core.management.base import BaseCommand
from django.utils import timezone


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

        # Idempotency guard — skip if all 8 demo ideas already exist
        if DiscoveryIdea.objects.filter(organization=demo_org, is_demo=True).count() >= 8:
            self.stdout.write(self.style.NOTICE('Discovery demo ideas already exist — skipping.'))
            return

        # ── Demo users ─────────────────────────────────────────────────
        alex = User.objects.filter(username='alex_chen_demo').first()
        sam = User.objects.filter(username='sam_rivera_demo').first()
        jordan = User.objects.filter(username='jordan_taylor_demo').first()

        if not (alex and sam and jordan):
            self.stderr.write(self.style.ERROR(
                'Demo users not found (alex_chen_demo, sam_rivera_demo, jordan_taylor_demo). '
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

        # ── Idea 1: Mobile App for Asian Markets (approved + promoted) ─
        idea1 = DiscoveryIdea.objects.create(
            organization=demo_org,
            title='Mobile App for Asian Markets',
            description=(
                'Build a mobile-first application optimised for users in South-East Asia, '
                'Japan, and South Korea. Must support local languages, offline mode, and '
                'integrate with regional payment gateways (Alipay, GrabPay, PayPay).'
            ),
            source='customer_research',
            stage='approved',
            submitted_by=jordan,
            ai_score_impact=87,
            ai_score_effort=72,
            ai_score_confidence=81,
            ai_score_recommendation='Prioritise — high strategic value, manageable effort.',
            ai_score_reasoning=(
                'Strong market opportunity in APAC, validated by customer interviews. '
                'Effort is moderate due to localisation complexity but offset by large '
                'addressable user base and competitive differentiation.'
            ),
            ai_scored_at=now,
            promoted_at=now,
            promoted_by=alex,
            is_demo=True,
        )

        # Promotion record for idea1
        promotion1 = IdeaPromotion.objects.create(
            idea=idea1,
            board=software_board,
            promoted_at=now,
            promoted_by=alex,
        )

        # Comment thread — decision journey
        IdeaComment.objects.create(
            idea=idea1,
            author=jordan,
            content=(
                'Customer interviews with 12 enterprise clients in APAC all mentioned '
                'mobile experience as a top pain point. I think we should fast-track this.'
            ),
        )
        IdeaComment.objects.create(
            idea=idea1,
            author=sam,
            content=(
                'Agreed — I ran a quick feasibility check and our React Native team '
                'can deliver an MVP in Q3. Biggest risk is payment gateway certification '
                'timelines (Alipay takes 8-12 weeks).'
            ),
        )
        IdeaComment.objects.create(
            idea=idea1,
            author=alex,
            content=(
                'I\'ve spoken to finance and we can ring-fence £180k budget for this. '
                'Moving to Approved and promoting to the APAC Sprint board.'
            ),
        )
        IdeaComment.objects.create(
            idea=idea1,
            author=alex,
            content='✅ Promoted to APAC Sprint Q3 board. Three tasks created. Kicking off next Monday.',
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
            ai_score_recommendation='Strong bet — aligns with APAC expansion and reduces localisation cost by est. 60%.',
            ai_score_reasoning=(
                'High leverage relative to effort — LLM translation is now mature enough '
                'for production use with human review. Main risk is regulatory sensitivity '
                'in some target markets.'
            ),
            ai_scored_at=now,
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
            ai_score_recommendation='Pursue in parallel with mobile app — a dependency, not optional.',
            ai_score_reasoning=(
                'Without payment localisation, conversion rates in APAC will remain low. '
                'Legal and compliance work is the main bottleneck; technical integration '
                'is well-documented for all target gateways.'
            ),
            ai_scored_at=now,
            is_demo=True,
        )

        # ── Idea 4: Offline Mode (new, unscored) ──────────────────────
        DiscoveryIdea.objects.create(
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

        # ── Idea 5: Competitor Feature Parity — Dashboard Export (new, unscored) ──
        DiscoveryIdea.objects.create(
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
            ai_score_recommendation='Deprioritise — low impact relative to effort for our B2B segment.',
            ai_score_reasoning=(
                'Gamification is a B2C pattern. Our enterprise buyers prioritise ROI '
                'and workflow efficiency, not engagement loops. Complexity cost is high '
                'for marginal adoption benefit.'
            ),
            ai_scored_at=now,
            is_demo=True,
        )
        IdeaComment.objects.create(
            idea=idea6,
            author=alex,
            content=(
                'Rejecting this for now. We spoke to 5 enterprise buyers — none of them '
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
            ai_score_recommendation='Quick Win — high impact with relatively low implementation effort.',
            ai_score_reasoning=(
                'Pricing localisation is a well-understood process and primarily a commercial '
                'and billing-system change rather than a deep technical investment. '
                'Expected 15-25% conversion uplift in target markets based on comparable data.'
            ),
            ai_scored_at=now,
            promoted_at=now,
            promoted_by=alex,
            is_demo=True,
        )
        IdeaPromotion.objects.create(
            idea=idea7,
            board=software_board,
            promoted_at=now,
            promoted_by=alex,
        )

        # ── Idea 8: Update FAQ & Help Centre copy (new, unscored) ───────
        # Intentionally left unscored so demo users can experience clicking
        # "Score with Spectra" themselves and see the AI analysis in action.
        DiscoveryIdea.objects.get_or_create(
            organization=demo_org,
            title='Update FAQ & Help Centre Copy',
            defaults=dict(
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
            ),
        )

        count = DiscoveryIdea.objects.filter(organization=demo_org, is_demo=True).count()
        self.stdout.write(self.style.SUCCESS(
            f'Created {count} Discovery demo ideas for "{demo_org.name}".'
        ))
