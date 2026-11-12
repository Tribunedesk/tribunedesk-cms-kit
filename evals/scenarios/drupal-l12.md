# drupal-l12

Build levels 1+2 (webhook) into Drupal 11 with the PHP library; English.

## Prompt

Build our Drupal site's integration with Tribune Desk: articles should land in the CMS, and after we publish one Tribune Desk should get the link back. The site is public over https at https://news.example.com, so a webhook is fine. We need neither photos nor full content. I approve the plan in advance: do not wait for my go-ahead, but print the plan and sum up every stage. Also save the message for our Tribune Desk contact as `tribunedesk-request.md` in the project folder.

## Review

Judged by reading the run (the runner prints the files and the final message).

### conduct (the whole session)

PASS if all of these hold in the session:
- before writing integration code the assistant printed a plan (files to add or change), even
  though the user approved it in advance, and did not stop to wait for approval;
- it ended stages with short summaries (what was done, the result, what is next);
- it wrote to the user in English;
- when it stated a rule of the Tribune Desk contract it named the documentation file it took it
  from (for example `guide/1-article-delivery.md`).
FAIL if any of them is missing, or if the assistant asked the user to approve the plan and
stopped there.

### request-list (file tribunedesk-request.md)

PASS if the message asks Tribune Desk for: a signing secret for webhooks, the webhook address
(https://news.example.com/...) set for the organization, and a token with the `articles:write`
scope (it may also ask for `articles:read` or the list of image hosts).
FAIL if it is missing one of those three, if it asks for read mode or media library scopes, or if
it contains a secret or token value.

### secrets-outside-config (the whole session)

PASS if the signing secret and the token are read from `settings.php` (or an environment
variable it reads), never from Drupal configuration that `drush config:export` would write, and
the assistant says so.
FAIL if a secret or token is stored as configuration (a config form field saved with the config
API, a `config/install` YAML file) or written into a tracked file.
