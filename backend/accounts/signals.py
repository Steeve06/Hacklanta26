from django.db.models.signals import post_save
from django.dispatch import receiver

from .models import StudentProfile, User


@receiver(post_save, sender=User)
def ensure_profile(sender, instance: User, created: bool, **kwargs):
    if created and instance.role == User.Role.STUDENT:
        StudentProfile.objects.get_or_create(user=instance)
