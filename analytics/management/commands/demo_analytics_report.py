"""
Django management command to generate demo analytics report
Usage: python manage.py demo_analytics_report
"""
from django.core.management.base import BaseCommand
from django.db.models import Count, Avg, Q
from django.utils import timezone
from datetime import timedelta
from analytics.models import DemoSession, DemoAnalytics


class Command(BaseCommand):
    help = 'Generate comprehensive demo analytics report'

    def add_arguments(self, parser):
        parser.add_argument(
            '--days',
            type=int,
            default=7,
            help='Number of days to analyze (default: 7)'
        )

    def handle(self, *args, **options):
        days = options['days']
        start_date = timezone.now() - timedelta(days=days)
        
        self.stdout.write("=" * 80)
        self.stdout.write(self.style.SUCCESS(f"Demo Analytics Report - Last {days} Days"))
        self.stdout.write("=" * 80)
        
        # Overall metrics
        self.print_section("📊 OVERALL METRICS")
        total_sessions = DemoSession.objects.filter(created_at__gte=start_date).count()
        anonymous_sessions = DemoSession.objects.filter(
            created_at__gte=start_date,
            user__isnull=True
        ).count()
        authenticated_sessions = total_sessions - anonymous_sessions
        
        self.stdout.write(f"Total Demo Sessions: {total_sessions}")
        self.stdout.write(f"  Anonymous Users: {anonymous_sessions} ({self.percentage(anonymous_sessions, total_sessions)})")
        self.stdout.write(f"  Authenticated Users: {authenticated_sessions} ({self.percentage(authenticated_sessions, total_sessions)})")
        
        # Conversion metrics
        self.print_section("\n💰 CONVERSION METRICS")
        
        # Anonymous conversion
        anonymous_converted = DemoSession.objects.filter(
            created_at__gte=start_date,
            user__isnull=True,
            converted_to_signup=True
        ).count()
        anonymous_rate = self.safe_divide(anonymous_converted, anonymous_sessions)
        
        # Authenticated conversion (users who were logged in during demo)
        auth_converted = DemoSession.objects.filter(
            created_at__gte=start_date,
            user__isnull=False,
            converted_to_signup=True
        ).count()
        auth_rate = self.safe_divide(auth_converted, authenticated_sessions)
        
        # Overall conversion
        total_converted = anonymous_converted + auth_converted
        overall_rate = self.safe_divide(total_converted, total_sessions)
        
        self.stdout.write(f"Anonymous Conversion: {anonymous_converted}/{anonymous_sessions} ({anonymous_rate:.1f}%)")
        self.stdout.write(f"Authenticated Conversion: {auth_converted}/{authenticated_sessions} ({auth_rate:.1f}%)")
        self.stdout.write(self.style.SUCCESS(f"Overall Conversion: {total_converted}/{total_sessions} ({overall_rate:.1f}%)"))
        
        # Time to conversion
        avg_time = DemoSession.objects.filter(
            created_at__gte=start_date,
            converted_to_signup=True,
            time_to_conversion_seconds__isnull=False
        ).aggregate(Avg('time_to_conversion_seconds'))['time_to_conversion_seconds__avg']
        
        if avg_time:
            self.stdout.write(f"Avg Time to Conversion: {int(avg_time / 60)} minutes")
        
        # Engagement metrics
        self.print_section("\n🎯 ENGAGEMENT METRICS")
        
        avg_duration = DemoSession.objects.filter(
            created_at__gte=start_date
        ).aggregate(Avg('duration_seconds'))['duration_seconds__avg']
        
        avg_features = DemoSession.objects.filter(
            created_at__gte=start_date
        ).aggregate(Avg('features_explored'))['features_explored__avg']
        
        sessions_with_aha = DemoSession.objects.filter(
            created_at__gte=start_date,
            aha_moments__gte=1
        ).count()
        aha_rate = self.safe_divide(sessions_with_aha, total_sessions)
        
        if avg_duration:
            self.stdout.write(f"Avg Session Duration: {int(avg_duration / 60)} minutes")
        if avg_features:
            self.stdout.write(f"Avg Features Explored: {avg_features:.1f}")
        self.stdout.write(f"Sessions with Aha Moment: {sessions_with_aha}/{total_sessions} ({aha_rate:.1f}%)")
        
        # Aha moment impact
        self.print_section("\n✨ AHA MOMENT IMPACT")
        
        no_aha = DemoSession.objects.filter(
            created_at__gte=start_date,
            aha_moments=0
        )
        no_aha_converted = no_aha.filter(converted_to_signup=True).count()
        no_aha_rate = self.safe_divide(no_aha_converted, no_aha.count())
        
        with_aha = DemoSession.objects.filter(
            created_at__gte=start_date,
            aha_moments__gte=1
        )
        with_aha_converted = with_aha.filter(converted_to_signup=True).count()
        with_aha_rate = self.safe_divide(with_aha_converted, with_aha.count())
        
        if no_aha_rate > 0:
            lift = ((with_aha_rate / no_aha_rate) - 1) * 100
            self.stdout.write(f"No Aha Moment: {no_aha_converted}/{no_aha.count()} ({no_aha_rate:.1f}%)")
            self.stdout.write(f"With Aha Moment: {with_aha_converted}/{with_aha.count()} ({with_aha_rate:.1f}%)")
            self.stdout.write(self.style.SUCCESS(f"Conversion Lift: +{lift:.0f}%"))
        
        # Top features explored
        self.print_section("\n🔥 TOP FEATURES EXPLORED")
        
        features = DemoAnalytics.objects.filter(
            timestamp__gte=start_date,
            event_type='feature_explored'
        ).values('event_data__feature_name').annotate(
            count=Count('id')
        ).order_by('-count')[:5]
        
        for i, feature in enumerate(features, 1):
            feature_name = feature.get('event_data__feature_name', 'Unknown')
            count = feature['count']
            self.stdout.write(f"{i}. {feature_name}: {count} interactions")
        
        # Device breakdown
        self.print_section("\n📱 DEVICE BREAKDOWN")
        
        devices = DemoSession.objects.filter(
            created_at__gte=start_date
        ).values('device_type').annotate(
            count=Count('id'),
            conversions=Count('id', filter=Q(converted_to_signup=True))
        ).order_by('-count')
        
        for device in devices:
            device_type = device['device_type']
            count = device['count']
            conversions = device['conversions']
            rate = self.safe_divide(conversions, count)
            self.stdout.write(f"{device_type.capitalize()}: {count} sessions, {conversions} conversions ({rate:.1f}%)")
        
        # Demo mode breakdown
        self.print_section("\n🎮 DEMO MODE BREAKDOWN")
        
        modes = DemoSession.objects.filter(
            created_at__gte=start_date
        ).values('demo_mode').annotate(
            count=Count('id'),
            conversions=Count('id', filter=Q(converted_to_signup=True))
        ).order_by('-count')
        
        for mode in modes:
            mode_name = mode['demo_mode']
            count = mode['count']
            conversions = mode['conversions']
            rate = self.safe_divide(conversions, count)
            self.stdout.write(f"{mode_name.capitalize()} Mode: {count} sessions, {conversions} conversions ({rate:.1f}%)")
        
        # Nudge effectiveness
        self.print_section("\n💡 NUDGE EFFECTIVENESS")
        
        total_nudges_shown = DemoSession.objects.filter(
            created_at__gte=start_date
        ).aggregate(total=Count('id', filter=Q(nudges_shown__gt=0)))['total'] or 0
        
        total_nudges_clicked = DemoSession.objects.filter(
            created_at__gte=start_date
        ).aggregate(total=Count('id', filter=Q(nudges_clicked__gt=0)))['total'] or 0
        
        click_rate = self.safe_divide(total_nudges_clicked, total_nudges_shown)
        
        self.stdout.write(f"Sessions with Nudges: {total_nudges_shown}")
        self.stdout.write(f"Nudge Click-Through: {total_nudges_clicked}/{total_nudges_shown} ({click_rate:.1f}%)")
        
        # Key insights
        self.print_section("\n💡 KEY INSIGHTS")
        
        if anonymous_rate > overall_rate:
            self.stdout.write(self.style.WARNING(
                f"⚠️  Anonymous users convert BETTER than authenticated ({anonymous_rate:.1f}% vs {auth_rate:.1f}%)"
            ))
        elif anonymous_rate < overall_rate:
            self.stdout.write(self.style.WARNING(
                f"⚠️  Anonymous users convert WORSE than authenticated ({anonymous_rate:.1f}% vs {auth_rate:.1f}%)"
            ))
        
        if with_aha_rate > no_aha_rate * 2:
            self.stdout.write(self.style.SUCCESS(
                f"✅ Aha moments double conversion rate! Focus on triggering more aha moments."
            ))
        
        if avg_features and avg_features < 3:
            self.stdout.write(self.style.WARNING(
                f"⚠️  Users explore only {avg_features:.1f} features on average. Improve feature discovery."
            ))
        
        self.stdout.write("\n" + "=" * 80)
        self.stdout.write(self.style.SUCCESS("Report Complete!"))
        self.stdout.write("=" * 80)
    
    def print_section(self, title):
        """Print section header"""
        self.stdout.write(self.style.HTTP_INFO(title))
    
    def percentage(self, part, total):
        """Calculate percentage"""
        if total == 0:
            return "0%"
        return f"{(part / total * 100):.1f}%"
    
    def safe_divide(self, numerator, denominator):
        """Safe division that returns 0 for division by zero"""
        if denominator == 0:
            return 0
        return (numerator / denominator) * 100
