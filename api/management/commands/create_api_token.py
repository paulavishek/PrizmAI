"""
Management command to create API tokens
"""
from django.core.management.base import BaseCommand, CommandError
from django.contrib.auth.models import User
from django.utils import timezone
from datetime import timedelta
from api.models import APIToken


class Command(BaseCommand):
    help = 'Create an API token for a user'

    def add_arguments(self, parser):
        parser.add_argument('username', type=str, help='Username of the user')
        parser.add_argument('name', type=str, help='Name/description for the token')
        parser.add_argument(
            '--scopes',
            type=str,
            help='Comma-separated list of scopes (e.g., boards.read,tasks.write)',
            default='*'
        )
        parser.add_argument(
            '--expires-in-days',
            type=int,
            help='Number of days until token expires',
            default=None
        )
        parser.add_argument(
            '--rate-limit',
            type=int,
            help='Rate limit per hour',
            default=1000
        )

    def handle(self, *args, **options):
        username = options['username']
        name = options['name']
        scopes_str = options['scopes']
        expires_in_days = options['expires_in_days']
        rate_limit = options['rate_limit']

        # Get user
        try:
            user = User.objects.get(username=username)
        except User.DoesNotExist:
            raise CommandError(f'User "{username}" does not exist')

        # Parse scopes
        if scopes_str == '*':
            scopes = ['*']
        else:
            scopes = [s.strip() for s in scopes_str.split(',')]

        # Calculate expiration
        expires_at = None
        if expires_in_days:
            expires_at = timezone.now() + timedelta(days=expires_in_days)

        # Create token
        token = APIToken.objects.create(
            user=user,
            name=name,
            scopes=scopes,
            expires_at=expires_at,
            rate_limit_per_hour=rate_limit
        )

        self.stdout.write(self.style.SUCCESS('API token created successfully!'))
        self.stdout.write('')
        self.stdout.write(f'Token ID: {token.id}')
        self.stdout.write(f'Token: {token.token}')
        self.stdout.write(f'User: {user.username}')
        self.stdout.write(f'Name: {name}')
        self.stdout.write(f'Scopes: {", ".join(scopes)}')
        self.stdout.write(f'Rate Limit: {rate_limit}/hour')
        if expires_at:
            self.stdout.write(f'Expires: {expires_at}')
        else:
            self.stdout.write('Expires: Never')
        self.stdout.write('')
        self.stdout.write(self.style.WARNING('⚠️  Save this token now - you won\'t be able to see it again!'))
        self.stdout.write('')
        self.stdout.write('Usage example:')
        self.stdout.write('  curl -H "Authorization: Bearer ' + token.token + '" http://localhost:8000/api/v1/boards/')
