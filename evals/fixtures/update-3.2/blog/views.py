import hmac
import json
import logging

from django.conf import settings
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, render
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST

from . import tribunedesk
from .models import Post

logger = logging.getLogger(__name__)


def post_list(request):
    posts = Post.objects.filter(status=Post.PUBLISHED)
    return render(request, "blog/post_list.html", {"posts": posts})


def post_detail(request, slug):
    post = get_object_or_404(Post, slug=slug, status=Post.PUBLISHED)
    return render(request, "blog/post_detail.html", {"post": post})


@csrf_exempt
@require_POST
def tribunedesk_webhook(request):
    """The `article.delivered` webhook of Tribune Desk (guide/1-article-delivery.md)."""
    secret = settings.TD_WEBHOOK_SECRET
    if not secret:
        # Not configured: 503 makes Tribune Desk retry, any 4xx would end the send for good.
        logger.error("TD_WEBHOOK_SECRET is not set")
        return JsonResponse({"error": "not configured"}, status=503)
    try:
        if "webhook-signature" in request.headers:
            tribunedesk.verify_signature(secret, request.headers, request.body)
        elif not hmac.compare_digest(request.headers.get("X-Webhook-Secret", ""), secret):
            # Organizations without a signing secret yet send only the shared secret (3.2.0).
            raise tribunedesk.InvalidSignature("no signature and no matching shared secret")
    except tribunedesk.InvalidSignature:
        return JsonResponse({"error": "invalid signature"}, status=401)
    except ValueError:
        logger.error("TD_WEBHOOK_SECRET is not a valid whsec_ secret")
        return JsonResponse({"error": "not configured"}, status=503)
    try:
        article = json.loads(request.body)
        if not isinstance(article, dict):
            raise ValueError("the body is not a JSON object")
        answer = tribunedesk.apply_delivery(article, request.headers.get("webhook-id", ""))
    except (ValueError, KeyError, TypeError):
        return JsonResponse({"error": "invalid body"}, status=400)
    return JsonResponse(answer)
