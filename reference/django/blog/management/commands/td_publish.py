from django.core.management.base import BaseCommand, CommandError
from django.utils import timezone

from blog.models import TribuneDeskArticle


class Command(BaseCommand):
    help = "Developer tool for tdkit: publish the post made from a Tribune Desk article."

    def add_arguments(self, parser):
        parser.add_argument("article_id")

    def handle(self, *args, article_id, **options):
        link = TribuneDeskArticle.objects.select_related("post").filter(article_id=article_id).first()
        if link is None:
            raise CommandError(f"no post for article {article_id}")
        post = link.post
        post.status = post.PUBLISHED
        post.published_at = post.published_at or timezone.now()
        post.save()  # the same save as in the admin, so the link back fires
        link.refresh_from_db()
        if link.link_back_pending or link.link_back_error:
            raise CommandError(f"link back not sent: {link.link_back_error or 'still queued'}")
        self.stdout.write(f"published {post.get_absolute_url()}")
