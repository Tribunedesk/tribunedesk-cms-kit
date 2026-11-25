from django.core.management.base import BaseCommand
from django.utils import timezone

from blog.models import Post


class Command(BaseCommand):
    help = "Cron: publish the scheduled posts whose time has come (Tribune Desk publication mode)."

    def handle(self, *args, **options):
        due = Post.objects.filter(status=Post.SCHEDULED, published_at__lte=timezone.now())
        for post in due:
            post.status = Post.PUBLISHED
            post.save()  # the same save as in the admin, so the link back fires
        self.stdout.write(f"published {len(due)}")
