from django.db import transaction
from django.db.models.signals import post_save
from django.dispatch import receiver

from . import tribunedesk
from .models import Post


@receiver(post_save, sender=Post)
def report_published_post(sender, instance, **kwargs):
    # Tribune Desk link back (level 2): report the address once the post is public. A failed
    # report stays queued for `manage.py td_send_links`.
    if tribunedesk.mark_link_back(instance):
        transaction.on_commit(tribunedesk.send_pending_link_backs)
