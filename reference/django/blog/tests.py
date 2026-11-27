from django.test import TestCase
from django.utils import timezone

from .models import Post


class PostTests(TestCase):
    def test_published_post_is_shown(self):
        Post.objects.create(
            title="Hello", slug="hello", body="<p>Hi</p>", status=Post.PUBLISHED,
            published_at=timezone.now(),
        )
        self.assertContains(self.client.get("/hello/"), "Hello")


import base64
import hashlib
import hmac
import json
import time
import uuid
from pathlib import Path
from unittest import mock

from django.test import override_settings

from . import tribunedesk
from .models import TribuneDeskArticle

SECRET = "whsec_" + base64.b64encode(b"blog-test-signing-secret-000000").decode()
VECTORS = Path(__file__).resolve().parent / "testdata" / "webhook-signature.json"


def sign(body: bytes, msg_id: str, timestamp: int, secret: str = SECRET) -> dict:
    key = base64.b64decode(secret.removeprefix("whsec_"))
    digest = hmac.new(key, f"{msg_id}.{timestamp}.".encode() + body, hashlib.sha256).digest()
    return {
        "HTTP_WEBHOOK_ID": msg_id,
        "HTTP_WEBHOOK_TIMESTAMP": str(timestamp),
        "HTTP_WEBHOOK_SIGNATURE": "v1," + base64.b64encode(digest).decode(),
    }


class SignatureVectorTests(TestCase):
    def test_contract_vectors(self):
        data = json.loads(VECTORS.read_text(encoding="utf-8"))
        for vector in data["vectors"]:
            with self.subTest(vector["name"]):
                body = base64.b64decode(vector["body_base64"])
                call = lambda: tribunedesk.verify_signature(  # noqa: E731
                    vector["verify_with"], vector["headers"], body, now=vector["now"]
                )
                if vector["valid"]:
                    call()
                else:
                    self.assertRaises(tribunedesk.InvalidSignature, call)


@override_settings(TD_WEBHOOK_SECRET=SECRET, SITE_URL="https://blog.example.com",
                   TD_CMS_TOKEN="tdcms_test", TD_API_BASE="http://td.test")
class WebhookTests(TestCase):
    def deliver(self, article_id, *, title="Title", sent_at="2026-11-04T09:00:00+00:00",
                msg_id=None, timestamp=None, secret=SECRET, extra=None):
        article = {
            "article_id": article_id, "org_code": "example-org", "sent_at": sent_at,
            "title": title, "html": "<p>Body</p>", "excerpt": "Short",
            "featured_image": {"url": "https://storage.tribunedesk.test/a.jpg"},
            **(extra or {}),
        }
        body = json.dumps(article).encode()
        headers = sign(body, msg_id or f"msg_{uuid.uuid4().hex}", timestamp or int(time.time()),
                       secret)
        return self.client.post("/td/webhook/", body, content_type="application/json", **headers)

    def test_creates_draft_and_answers(self):
        article_id = str(uuid.uuid4())
        response = self.deliver(article_id, extra={"unknown_field": 1})
        self.assertEqual(response.status_code, 200)
        answer = response.json()
        post = Post.objects.get(pk=answer["cms_post_id"])
        self.assertEqual((post.title, post.body, post.excerpt, post.status),
                         ("Title", "<p>Body</p>", "Short", Post.DRAFT))
        self.assertEqual(answer["status"], "created")
        self.assertEqual(answer["edit_url"],
                         f"https://blog.example.com/admin/blog/post/{post.pk}/change/")
        self.assertNotIn("permalink", answer)
        self.assertEqual(post.tribunedesk.featured_image_url,
                         "https://storage.tribunedesk.test/a.jpg")

    def test_embeds_trusted_kept_script_removed(self):
        """Guide 1, The HTML body (3.5): trusted players stay; scripts and other iframes go."""
        label = '<script type="application/ld+json" data-hf-provenance>{"a": 1}</script>'
        html = (
            '<p>Body</p><iframe src="https://www.youtube.com/embed/x"></iframe>'
            '<iframe src="https://evil.example/embed/x"></iframe>'
            '<iframe src="https://www.youtube.com.evil.example/embed/x"></iframe>'
            "<script>alert('marker')</script>" + label
        )
        answer = self.deliver(str(uuid.uuid4()), extra={"html": html}).json()
        body = Post.objects.get(pk=answer["cms_post_id"]).body
        self.assertIn("https://www.youtube.com/embed/x", body)
        self.assertNotIn("evil.example", body)
        self.assertNotIn("marker", body)
        self.assertIn("data-hf-provenance", body)  # the AI label block may stay

    def test_unsafe_samples_of_the_guide_are_filtered(self):
        """guide/complete-integration.md, Filtering the HTML (3.9): the unsafe samples go, the
        safe ones stay."""
        html = (
            '<p><img src="x" onerror="alert(1)"></p>'
            '<a href="javascript:alert(1)">a</a><a href="JaVa&#115;cript:alert(1)">b</a>'
            '<svg onload="alert(1)"></svg>'
            '<iframe src="https://evil.example/x" title="https://www.youtube.com/embed/x"></iframe>'
            '<figure class="alignleft"><img src="https://img.test/a.jpg" data-td-asset-id="1" '
            'data-td-cms-media-id="2"></figure>'
            '<a href="https://example.com/" target="_blank" rel="noopener">ok</a>'
            '<iframe src="https://evil.example/unclosed">'
        )
        answer = self.deliver(str(uuid.uuid4()), extra={"html": html}).json()
        body = Post.objects.get(pk=answer["cms_post_id"]).body.lower()
        for unsafe in ("onerror", "onload", "javascript", "evil.example", "<svg"):
            self.assertNotIn(unsafe, body)
        for safe in ('data-td-cms-media-id="2"', 'target="_blank"', 'class="alignleft"'):
            self.assertIn(safe, body)

    def test_bad_signature_and_old_timestamp_get_401(self):
        other = "whsec_" + base64.b64encode(b"another-secret").decode()
        self.assertEqual(self.deliver(str(uuid.uuid4()), secret=other).status_code, 401)
        old = int(time.time()) - 301
        self.assertEqual(self.deliver(str(uuid.uuid4()), timestamp=old).status_code, 401)
        self.assertFalse(Post.objects.exists())

    def test_repeat_and_resend_update_the_same_post(self):
        article_id = str(uuid.uuid4())
        self.deliver(article_id, msg_id="msg_1")
        self.deliver(article_id, msg_id="msg_1")
        response = self.deliver(article_id, title="New", sent_at="2026-11-04T10:00:00+00:00")
        self.assertEqual(response.json()["status"], "updated")
        self.assertEqual(Post.objects.get().title, "New")

    def test_older_send_does_not_overwrite(self):
        article_id = str(uuid.uuid4())
        self.deliver(article_id, title="Newer", sent_at="2026-11-04T10:00:00+00:00")
        response = self.deliver(article_id, title="Older", sent_at="2026-11-04T09:00:00+00:00")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(Post.objects.get().title, "Newer")

    def test_publication_modes(self):
        """Contract 3.7: draft, schedule (a new send updates it like a draft), publish; a
        published post is never unpublished."""
        article_id = str(uuid.uuid4())
        later = (timezone.now() + timezone.timedelta(days=2)).replace(microsecond=0)
        at = later.strftime("%Y-%m-%dT%H:%M:%SZ")
        answer = self.deliver(article_id, sent_at="2026-11-04T09:00:00+00:00",
                              extra={"publication": {"mode": "schedule", "at": at}}).json()
        self.assertEqual(answer["publication"], {"status": "scheduled", "at": at})
        post = Post.objects.get()
        self.assertEqual((post.status, post.published_at), (Post.SCHEDULED, later))
        self.assertEqual(self.client.get(f"/{post.slug}/").status_code, 404)
        answer = self.deliver(article_id, title="Moved", sent_at="2026-11-04T09:01:00+00:00",
                              extra={"publication": {"mode": "draft"}}).json()
        self.assertEqual(answer["publication"], {"status": "draft", "at": None})
        self.assertEqual((Post.objects.get().title, Post.objects.get().status),
                         ("Moved", Post.DRAFT))
        reply = mock.Mock(status_code=200)
        reply.json.return_value = {"results": [{"article_id": article_id, "status": "ok"}]}
        with mock.patch("blog.tribunedesk.requests.post", return_value=reply):
            with self.captureOnCommitCallbacks(execute=True):
                answer = self.deliver(article_id, sent_at="2026-11-04T09:02:00+00:00",
                                      extra={"publication": {"mode": "publish"}}).json()
            self.assertEqual(answer["publication"]["status"], "published")
            answer = self.deliver(article_id, sent_at="2026-11-04T09:03:00+00:00",
                                  extra={"publication": {"mode": "schedule", "at": at}}).json()
        self.assertEqual(answer["publication"]["status"], "published")
        self.assertEqual(Post.objects.get().status, Post.PUBLISHED)

    def test_without_publication_the_status_stays(self):
        article_id = str(uuid.uuid4())
        self.deliver(article_id)
        answer = self.deliver(article_id, sent_at="2026-11-04T10:00:00+00:00").json()
        self.assertEqual(Post.objects.get().status, Post.DRAFT)
        self.assertEqual(answer["publication"], {"status": "draft", "at": None})

    def test_due_scheduled_post_is_published_by_the_cron_command(self):
        from django.core.management import call_command

        post = Post.objects.create(title="Due", slug="due", body="x", status=Post.SCHEDULED,
                                   published_at=timezone.now() - timezone.timedelta(minutes=1))
        call_command("td_publish_due")
        post.refresh_from_db()
        self.assertEqual(post.status, Post.PUBLISHED)

    def test_unconfigured_secret_answers_503(self):
        with override_settings(TD_WEBHOOK_SECRET=""):
            self.assertEqual(self.deliver(str(uuid.uuid4())).status_code, 503)

    def test_publishing_reports_the_link_back(self):
        article_id = str(uuid.uuid4())
        self.deliver(article_id)
        post = Post.objects.get()
        reply = mock.Mock(status_code=200)
        reply.json.return_value = {"results": [{"article_id": article_id, "status": "ok"}]}
        with mock.patch("blog.tribunedesk.requests.post", return_value=reply) as post_mock:
            post.status, post.published_at = Post.PUBLISHED, timezone.now()
            with self.captureOnCommitCallbacks(execute=True):
                post.save()
            # Saving again with the same address reports nothing new.
            with self.captureOnCommitCallbacks(execute=True):
                post.save()
        self.assertEqual(post_mock.call_count, 1)
        args, kwargs = post_mock.call_args
        self.assertEqual(args[0], "http://td.test/v3/cms/articles/published")
        self.assertEqual(kwargs["headers"], {"Authorization": "Bearer tdcms_test"})
        item = kwargs["json"]["items"][0]
        self.assertEqual(item["url"], f"https://blog.example.com/{post.slug}/")
        link = TribuneDeskArticle.objects.get()
        self.assertEqual((link.reported_url, link.link_back_pending), (item["url"], False))

    def test_link_back_stays_queued_on_server_error(self):
        article_id = str(uuid.uuid4())
        self.deliver(article_id)
        post = Post.objects.get()
        with mock.patch("blog.tribunedesk.requests.post",
                        return_value=mock.Mock(status_code=503)):
            post.status, post.published_at = Post.PUBLISHED, timezone.now()
            with self.captureOnCommitCallbacks(execute=True):
                post.save()
        self.assertTrue(TribuneDeskArticle.objects.get().link_back_pending)

    def test_not_found_item_is_logged_not_retried(self):
        article_id = str(uuid.uuid4())
        self.deliver(article_id)
        post = Post.objects.get()
        reply = mock.Mock(status_code=200)
        reply.json.return_value = {"results": [{"article_id": article_id, "status": "not_found"}]}
        with mock.patch("blog.tribunedesk.requests.post", return_value=reply):
            post.status, post.published_at = Post.PUBLISHED, timezone.now()
            with self.captureOnCommitCallbacks(execute=True):
                post.save()
        link = TribuneDeskArticle.objects.get()
        self.assertEqual((link.link_back_pending, link.link_back_error), (False, "not_found"))
