from django.core.management.base import BaseCommand

from blog import tribunedesk


class Command(BaseCommand):
    help = "Send queued Tribune Desk link backs (run it from cron, e.g. every 5 minutes)."

    def handle(self, *args, **options):
        sent = tribunedesk.send_pending_link_backs()
        self.stdout.write(f"reported {sent} post(s)")
