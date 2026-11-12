import json

from django.core.management.base import BaseCommand

from blog import tribunedesk
from blog.models import TribuneDeskArticle


class Command(BaseCommand):
    help = "Developer tool for tdkit: print the post made from a Tribune Desk article as JSON."

    def add_arguments(self, parser):
        parser.add_argument("article_id")

    def handle(self, *args, article_id, **options):
        link = (
            TribuneDeskArticle.objects.select_related("post")
            .filter(article_id=article_id).first()
        )
        data = None
        if link:
            post = link.post
            data = {
                "cms_post_id": str(post.pk),
                "title": post.title,
                "html": post.body,
                "excerpt": post.excerpt,
                "status": post.status,
                "featured_image_url": link.featured_image_url or None,
                "permalink": tribunedesk.permalink(post),
            }
        # ASCII escapes keep the output valid whatever the console encoding (Windows).
        self.stdout.write(json.dumps(data))
