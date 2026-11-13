# parity-node

Clean-room parity (spec 2026-11-13 kontrakt najpierw, D4): everything the official WordPress
plugin does, built from scratch in an Express 5 blog on `node:sqlite` (tables `posts` and `photos`, files in `media/`), from the skill and the public documentation alone.
Levels 1-4, webhook; `tdkit check` green for all four.

## Prompt

Build our Tribune Desk integration with the same scope as the official WordPress plugin: articles arrive in our CMS as drafts, Tribune Desk gets the link back once a post is published, the full content (internal links, the "read more" box, SEO, author, the AI label) and our photo library kept in sync with the Tribune Desk media library. The site is public over https at https://blog.example.com, so a webhook is fine. I approve the plan up front: don't wait for my approval, but print the plan and sum up each stage. Also save the message for our Tribune Desk contact in `tribunedesk-request.md` in the project folder.

## Review

Judged by reading the run (the runner prints the files and the final message).

### conduct (the whole session)

PASS if all of these hold in the session:
- before writing integration code the assistant printed a plan (files to add or change) and did
  not stop to wait for approval;
- it ended stages with short summaries (what was done, the result, what is next);
- it wrote to the user in English;
- when it stated a rule of the Tribune Desk contract it named the documentation file it took it
  from (for example `guide/3-full-content.md`).
FAIL if any of them is missing, or if it read the WordPress plugin's code instead of the guide.

### final-summary (the final message)

PASS if the final message sums up levels 1-4 in webhook mode, says `tdkit check` passed for
each level, and gives launch steps (secret and token in the production environment, the webhook
address for Tribune Desk, the schedule of the media sync).
FAIL if a level is claimed without its `tdkit check` result.

### request-list (file tribunedesk-request.md)

PASS if the message asks for a signing secret, the webhook address set for the organization and
a token with `articles:write`, `media:read` and `media:write` (it may ask for more read scopes).
FAIL if one of them is missing or it contains a secret or token value.
