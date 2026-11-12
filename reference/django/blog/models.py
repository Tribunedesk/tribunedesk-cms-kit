from django.db import models
from django.urls import reverse


class Post(models.Model):
    DRAFT = "draft"
    PUBLISHED = "published"
    STATUS_CHOICES = [(DRAFT, "Draft"), (PUBLISHED, "Published")]

    title = models.CharField(max_length=300)
    slug = models.SlugField(max_length=300, unique=True)
    excerpt = models.TextField(blank=True)
    body = models.TextField(help_text="HTML")
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default=DRAFT)
    published_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["-published_at"]

    def __str__(self) -> str:
        return self.title

    def get_absolute_url(self) -> str:
        return reverse("blog:post_detail", args=[self.slug])


class TribuneDeskArticle(models.Model):
    """A post made from a Tribune Desk delivery, keyed by the article's id."""

    article_id = models.UUIDField(unique=True)
    post = models.OneToOneField(Post, on_delete=models.CASCADE, related_name="tribunedesk")
    last_sent_at = models.DateTimeField()
    last_delivery_id = models.CharField(max_length=200, blank=True)
    featured_image_url = models.URLField(max_length=2000, blank=True)
    # Level 2: link back.
    reported_url = models.URLField(max_length=2000, blank=True)
    link_back_pending = models.BooleanField(default=False)
    link_back_error = models.CharField(max_length=200, blank=True)

    def __str__(self) -> str:
        return str(self.article_id)
