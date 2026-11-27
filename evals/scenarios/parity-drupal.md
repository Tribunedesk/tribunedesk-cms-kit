# parity-drupal

Clean-room parity on Drupal 11 (audit 2026-11-27: no Drupal parity scenario): everything the
official WordPress plugin does, built from the skill, the public documentation and the
`tribunedesk/cms-protocol` library. Levels 1-4, webhook; `tdkit check` green for all four.

## Prompt

Build our Drupal site's integration with Tribune Desk to the scope of the official WordPress plugin: articles land as drafts, Tribune Desk gets the link back after we publish, the full content (internal links, the read-more box, SEO, author, AI label, and our tags), and our media library kept in sync with Tribune Desk's. The site is public over https at https://news.example.com, so a webhook is fine. I approve the plan in advance: do not wait for my go-ahead, but print the plan and sum up every stage. Also save the message for our Tribune Desk contact as `tribunedesk-request.md` in the project folder.

## Review

Judged by reading the run (the runner prints the files and the final message).

### conduct (the whole session)

PASS if all of these hold in the session:
- plan before code (SKILL.md, "The plan before code"): before its first edit of integration
  code the assistant wrote the plan (files to add and change) as a progress line, and did
  not stop to wait for approval;
- the final message carries the plan as built (files added and changed, per level) and a table
  of the stages with the result of each; short progress lines between stages are enough;
- it wrote to the user in English;
- when it stated a rule of the Tribune Desk contract it named the documentation file it took it
  from (for example `guide/3-full-content.md`).
FAIL if any of them is missing, or if it read the WordPress plugin's code instead of the guide.

### drupal (the code)

PASS if the module uses `tribunedesk/cms-protocol`, keeps the secret and the token in
`settings.php` from the environment (never config), runs the media sync and the taxonomy run
from `hook_cron()` or a queue, and has admin routes for held batches and the resync preview.
FAIL if any of them is missing.

### final-summary (the final message)

PASS if the final message, in English, sums up levels 1-4 in webhook mode, says `tdkit check`
passed for each level, and gives launch steps (secret and token in the production environment,
the webhook address for Tribune Desk, a real cron for `drush cron`).
FAIL if a level is claimed without its `tdkit check` result.

### request-list (file tribunedesk-request.md)

PASS if the message asks for a signing secret, the webhook address set for the organization and
a token with `articles:write`, `media:read` and `media:write`.
FAIL if one of them is missing or it contains a secret or token value.
