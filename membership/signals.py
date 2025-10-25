#from django.contrib.auth.models import User
from account.models import CustomUser
from django.db.models.signals import post_save
from django.dispatch import receiver
from .models import MemberProfile

@receiver(post_save, sender=CustomUser)
def create_member_profile(sender, instance, created, **kwargs):
    if created:
        MemberProfile.objects.create(user=instance)