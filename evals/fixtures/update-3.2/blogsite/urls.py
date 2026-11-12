from django.contrib import admin
from django.urls import include, path

from blog.views import tribunedesk_webhook

urlpatterns = [
    path("admin/", admin.site.urls),
    path("td/webhook/", tribunedesk_webhook, name="tribunedesk_webhook"),
    path("", include("blog.urls")),
]
