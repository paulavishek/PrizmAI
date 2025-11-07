from django.db.models.signals import post_save
from django.dispatch import receiver
from .models import WikiPage, MeetingNotes, WikiPageAccess
from django.contrib.auth.models import User


@receiver(post_save, sender=WikiPage)
def create_wiki_page_access(sender, instance, created, **kwargs):
    """Create access records for wiki page creator and organization members"""
    if created:
        # Grant creator admin access
        WikiPageAccess.objects.get_or_create(
            page=instance,
            user=instance.created_by,
            defaults={'access_level': 'admin', 'granted_by': instance.created_by}
        )
        
        # Grant view access to all organization members
        # Note: members is a related_name from UserProfile, so we need to get the user from each profile
        org_member_profiles = instance.organization.members.all()
        for profile in org_member_profiles:
            if profile.user != instance.created_by:
                WikiPageAccess.objects.get_or_create(
                    page=instance,
                    user=profile.user,
                    defaults={'access_level': 'view', 'granted_by': instance.created_by}
                )


@receiver(post_save, sender=MeetingNotes)
def notify_meeting_attendees(sender, instance, created, **kwargs):
    """Notify attendees when meeting notes are created"""
    if created:
        # Here you could add notification logic
        # For example, send messages to all attendees
        pass
