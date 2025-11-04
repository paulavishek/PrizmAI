from django.core.management.base import BaseCommand
from django.contrib.sites.models import Site
from allauth.socialaccount.models import SocialApp
import os
from dotenv import load_dotenv

load_dotenv()


class Command(BaseCommand):
    help = 'Setup Google OAuth social app for django-allauth'

    def handle(self, *args, **options):
        # Get Google OAuth credentials from environment
        client_id = os.getenv('GOOGLE_OAUTH2_CLIENT_ID', '')
        client_secret = os.getenv('GOOGLE_OAUTH2_CLIENT_SECRET', '')

        if not client_id or not client_secret:
            self.stdout.write(
                self.style.ERROR(
                    'Google OAuth credentials not found in .env file. '
                    'Please set GOOGLE_OAUTH2_CLIENT_ID and GOOGLE_OAUTH2_CLIENT_SECRET.'
                )
            )
            return

        # Get the default site
        site = Site.objects.get_or_create(
            id=1,
            defaults={'domain': 'localhost:8000', 'name': 'TaskFlow'}
        )[0]

        # Create or update Google SocialApp
        google_app, created = SocialApp.objects.get_or_create(
            provider='google',
            defaults={
                'name': 'Google',
                'client_id': client_id,
                'secret': client_secret,
            }
        )

        if not created:
            # Update if it already exists
            google_app.client_id = client_id
            google_app.secret = client_secret
            google_app.save()
            self.stdout.write(
                self.style.SUCCESS('✓ Updated existing Google OAuth configuration')
            )
        else:
            self.stdout.write(
                self.style.SUCCESS('✓ Created Google OAuth configuration')
            )

        # Ensure the app is associated with the site
        if site not in google_app.sites.all():
            google_app.sites.add(site)
            self.stdout.write(
                self.style.SUCCESS(f'✓ Associated Google OAuth with site: {site.name}')
            )

        self.stdout.write(
            self.style.SUCCESS(
                '\n✅ Google OAuth setup complete! '
                'The Google sign-in button should now appear on the login page.'
            )
        )
